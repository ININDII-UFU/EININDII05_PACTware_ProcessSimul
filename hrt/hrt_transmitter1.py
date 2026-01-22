from __future__ import annotations

# HrtTransmitter (versão síncrona)
# - Usa ReactFactory + ReactVar (sem storage).
# - Leitura via ReactVar.translate(_value, ..., DBState.machineValue, DBState.humanValue) — 100% síncrona.
# - Escrita via ReactVar.setValue(hex, stateAtual=DBState.machineValue).
# - Cabeçalho do HrtFrame em snake_case.
#
# Observação: ReactVar.getValue é async no seu projeto — por isso NÃO usamos getValue aqui.

from typing import Union, Optional
from db_files.db_types import DBState

try:
    from hrt.hrt_frame import HrtFrame  # ajuste se necessário
except Exception:
    from hrt_frame import HrtFrame  # fallback

try:
    from react.react_factory import ReactFactory
    from react.react_var import ReactVar
except Exception:
    from react.react_factory import ReactFactory  # fallback
    from react.react_var import ReactVar  # fallback

import re
class HrtTransmitter:
    def __init__(self, react_factory: ReactFactory, table_name: str = "HART"):
        self.rf = react_factory
        self.table = table_name
        self.col: str = ""
        self._hrt_frame_write: Optional[HrtFrame] = None

    # --------------------------- Helpers (util) ---------------------------
    @staticmethod
    def _norm_cmd(cmd: str) -> str:
        """Normaliza comando para 2-hex uppercase (ex: 'a'->'0A', '8a'->'8A')."""
        cmd = (cmd or "").strip()
        if not cmd:
            return ""
        cmd = cmd.upper()
        if len(cmd) == 1:
            cmd = "0" + cmd
        return cmd

    def _setattr_safe(self, obj: object, name: str, value) -> None:
        """Seta atributo se existir; se não existir, tenta mesmo assim (python permite)."""
        try:
            setattr(obj, name, value)
        except Exception:
            pass

    def _rv(self, row_key: str) -> ReactVar:
        rv = self.rf.df[self.table].at[row_key, self.col]
        if not isinstance(rv, ReactVar):
            raise TypeError(
                f"Célula não é ReactVar: {self.table}.{self.col}.{row_key} → {type(rv).__name__}"
            )
        return rv

    def _has(self, row_key: str) -> bool:
        try:
            return isinstance(self.rf.df[self.table].at[row_key, self.col], ReactVar)
        except Exception:
            return False

    _HEX_RE = re.compile(r"^[0-9A-Fa-f]*$")

    def _get(self, row_key: str) -> str:
        """
        Retorna HEX SEMPRE.
        - Tenta traduzir human→machine.
        - Se vier texto (ex: 'Smar', 'No Command...'), tenta fallback:
            1) se _value for int -> converte para hex do tamanho
            2) se _value for None -> retorna zeros do tamanho
            3) caso contrário -> retorna zeros (para não quebrar checksum)
        """
        rv = self._rv(row_key)
        human_val = getattr(rv, "_value", None)

        try:
            print(f"[DBG] {row_key=} {human_val=} type={rv.type()} byteSize={rv.byteSize()}")
        except Exception:
            pass

        # 1) tenta translate normal (human -> machine)
        try:
            out = rv.translate(human_val, rv.type(), rv.byteSize(), DBState.machineValue, DBState.humanValue)
            out = (out or "").strip()
        except Exception:
            out = ""

        # 2) se retorno é HEX válido, ok
        if out and _HEX_RE.fullmatch(out):
            return out.upper()

        # 3) fallback: gera HEX coerente para não quebrar frame
        nbytes = int(getattr(rv, "byteSize", lambda: 1)() or 1)

        if human_val is None:
            return ("00" * nbytes)

        if isinstance(human_val, int):
            # converte int para hex com padding
            return f"{human_val:0{nbytes*2}X}"[-(nbytes*2):]

        # se for string “humana” (ENUM/BIT_ENUM) e não conseguimos traduzir,
        # devolve 00s para não explodir checksum
        return ("00" * nbytes)

    def _set(self, row_key: str, hex_str: str) -> None:
        """Grava **HEX** via ReactVar.setValue(..., stateAtual=DBState.machineValue)."""
        rv = self._rv(row_key)
        rv.setValue(hex_str, stateAtual=DBState.machineValue, isWidgetValueChanged=False)

    def _g_try(self, key: str, default_hex: str = "") -> str:
        """Lê uma key do DB; se não existir, retorna default_hex."""
        try:
            return self._get(key)
        except Exception:
            return default_hex

    def _s_try(self, key: str, hex_str: str) -> None:
        """Escreve uma key do DB; se não existir, ignora."""
        try:
            self._set(key, hex_str)
        except Exception:
            pass

    # --------------------------- Cabeçalho ---------------------------
    def _prime_header(self, hrt_frame_read: HrtFrame) -> bool:
        """
        Preenche header do frame de escrita baseado no frame lido.
        Retorna True se não encontrou uma coluna/instância que case com o address do frame lido.
        """
        if self._hrt_frame_write is None:
            raise RuntimeError("_hrt_frame_write não inicializado")

        # Copia campos base do request recebido
        self._hrt_frame_write.command = hrt_frame_read.command
        self._hrt_frame_write.addressType = hrt_frame_read.addressType  # False curto, True longo
        self._hrt_frame_write.masterAddress = hrt_frame_read.masterAddress
        self._hrt_frame_write.burstMode = hrt_frame_read.burstMode

        # Se tabela não existe, falha
        if self.table not in self.rf.df:
            return True

        cols = list(self.rf.df[self.table].columns)
        if len(cols) <= 2:
            return True

        # Varre as colunas de devices (a partir da 3ª coluna)
        for self.col in cols[2:]:
            # Monta endereço atual da coluna
            if self._hrt_frame_write.addressType:  # Long address
                mid = self._g_try("manufacturer_id", "00")
                dtype = self._g_try("device_type", "00")
                did = self._g_try("device_id", "000000")

                # Corrige typo clássico: alguns HrtFrame usam manufacturerId, outros manufacterId
                self._setattr_safe(self._hrt_frame_write, "manufacturerId", mid)
                self._setattr_safe(self._hrt_frame_write, "manufacterId", mid)
                self._setattr_safe(self._hrt_frame_write, "deviceType", dtype)
                self._setattr_safe(self._hrt_frame_write, "deviceId", did)
            else:  # Short address
                pa = self._g_try("polling_address", "00")
                self._setattr_safe(self._hrt_frame_write, "pollingAddress", pa)

            # Se o HrtFrame calcula "address" a partir dos campos acima, compare agora
            try:
                if self._hrt_frame_write.address == hrt_frame_read.address:
                    break
            except Exception:
                # Se não existe .address calculado, não dá para comparar -> falha
                return True
        else:
            # Não achou nenhum address compatível
            return True

        # Espelha header em variáveis do DB (se existirem)
        self._s_try("frame_type", getattr(self._hrt_frame_write, "frameType", "06"))
        self._s_try("address_type", "80" if self._hrt_frame_write.addressType else "00")
        self._s_try("master_address", "80" if self._hrt_frame_write.masterAddress else "00")
        self._s_try("burst_mode", "20" if self._hrt_frame_write.burstMode else "00")
        return False

    # --------------------------- API pública ---------------------------
    def request(self, hrt_frame_read: HrtFrame) -> Union[HrtFrame, str]:
        """
        Monta um REQUEST (frameType '02') com base no que o DTM mandou.
        Para universais de leitura, body vazio. Para writes universais, body com valores atuais.
        """
        self._hrt_frame_write = HrtFrame()
        self._hrt_frame_write.frameType = "02"  # Request

        if self._prime_header(hrt_frame_read):
            return ""

        cmd = self._norm_cmd(hrt_frame_read.command)

        # Universais que não carregam payload no request (leitura)
        if cmd in ("00", "01", "02", "03", "04", "05", "07", "08", "09", "0A", "0C", "0D", "10", "21", "50"):
            self._hrt_frame_write.body = ""

        elif cmd == "06":  # Write Polling Address
            # HART cmd 06 request: [polling_address][loop_current_mode]
            self._hrt_frame_write.body = f"{self._g_try('polling_address','00')}{self._g_try('loop_current_mode','00')}"

        elif cmd == "11":  # Write Message (24 bytes packed ASCII)
            self._hrt_frame_write.body = self._g_try("message", "")

        elif cmd == "12":  # Write Tag, Descriptor, Date
            self._hrt_frame_write.body = (
                self._g_try("tag", "") +
                self._g_try("descriptor", "") +
                self._g_try("date", "")
            )

        elif cmd == "13":  # Write Final Assembly Number
            self._hrt_frame_write.body = self._g_try("final_assembly_number", "000000")

        else:
            # Por padrão, sem body
            self._hrt_frame_write.body = ""

        return self._hrt_frame_write

    def response(self, hrt_frame_read: HrtFrame) -> HrtFrame:
        """
        Monta uma RESPONSE (frameType '06') compatível com parsing do DTM (LD301),
        iniciando sempre com 2 bytes: response_code + device_status.
        """
        self._hrt_frame_write = HrtFrame()
        self._hrt_frame_write.frameType = "06"  # Response
        self._prime_header(hrt_frame_read)
        cmd = self._norm_cmd(hrt_frame_read.command)

        # ----- helpers locais -----
        def status_ok() -> str:
            rc = self._g_try("response_code", self._g_try("error_code", "00"))
            ds = self._g_try("device_status", "00")
            return rc + ds

        def status_fail(rc_hex: str) -> str:
            ds = self._g_try("device_status", "00")
            return rc_hex + ds

        def identity_payload() -> str:
            # LD301 costuma usar universal_revision; alguns bancos usam hart_revision.
            uni_rev = self._g_try("universal_revision", self._g_try("hart_revision", "05"))
            return (
                self._g_try("manufacturer_id", "00") +
                self._g_try("device_type", "00") +
                self._g_try("request_preambles", "05") +
                uni_rev +
                self._g_try("software_revision", "00") +
                self._g_try("transmitter_revision", "00") +
                self._g_try("hardware_revision", "00") +
                self._g_try("device_flags", "00") +
                self._g_try("device_id", "000000")
            )

        # --------------------------- Universais ---------------------------
        if cmd == "00":  # Identity Command
            self._hrt_frame_write.body = status_ok() + identity_payload()

        elif cmd == "01":  # Read Primary Variable
            self._hrt_frame_write.body = (
                status_ok() +
                self._g_try("process_variable_unit_code", "FA") +
                self._g_try("PROCESS_VARIABLE", "7FC00000")  # NaN float fallback
            )

        elif cmd == "02":  # Read Loop Current And Percent Of Range
            self._hrt_frame_write.body = (
                status_ok() +
                self._g_try("loop_current", "00000000") +
                self._g_try("percent_of_range", "00000000")
            )

        elif cmd == "03":  # Read Dynamic Variables And Loop Current
            body = status_ok() + self._g_try("loop_current", "00000000")
            for _ in range(4):
                body += self._g_try("process_variable_unit_code", "FA")
                body += self._g_try("PROCESS_VARIABLE", "7FC00000")
            self._hrt_frame_write.body = body

        elif cmd in ("04", "05", "09", "0A", "2A"):
            self._hrt_frame_write.body = status_ok()

        elif cmd == "06":  # Write Polling Address (eco)
            polling_address = (hrt_frame_read.body[:2] or "00").upper()
            loop_current_mode = (hrt_frame_read.body[2:4] or "00").upper()
            self._s_try("polling_address", polling_address)
            self._s_try("loop_current_mode", loop_current_mode)
            self._hrt_frame_write.body = status_ok() + polling_address + loop_current_mode

        elif cmd == "07":  # Read Loop Configuration
            self._hrt_frame_write.body = (
                status_ok() +
                self._g_try("polling_address", "00") +
                self._g_try("loop_current_mode", "00")
            )

        elif cmd == "08":  # Read Dynamic Variable Classifications
            self._hrt_frame_write.body = status_ok() + ("00" * 4)

        elif cmd == "0B":  # Read Unique Identifier Associated With Tag
            tag_db = self._g_try("tag", "").upper()
            match = "00" if (hrt_frame_read.body or "").upper() == tag_db else "01"
            # cmd 0B: [match_code][device_status] + identity_payload (sem response_code)
            self._hrt_frame_write.body = match + self._g_try("device_status", "00") + identity_payload()

        elif cmd == "0C":  # Read Message
            self._hrt_frame_write.body = status_ok() + self._g_try("message", "")

        elif cmd == "0D":  # Read Tag, Descriptor, Date
            self._hrt_frame_write.body = (
                status_ok() +
                self._g_try("tag", "") +
                self._g_try("descriptor", "") +
                self._g_try("date", "")
            )

        elif cmd == "0E":  # Read Primary Variable Transducer Information
            self._hrt_frame_write.body = (
                status_ok() +
                self._g_try("sensor1_serial_number", "000000") +
                self._g_try("process_variable_unit_code", "FA") +
                self._g_try("pressure_upper_range_limit", "00000000") +
                self._g_try("pressure_lower_range_limit", "00000000") +
                self._g_try("pressure_minimum_span", "00000000")
            )

        elif cmd == "0F":  # Read Device / PV Output Information
            self._hrt_frame_write.body = (
                status_ok() +
                self._g_try("alarm_selection_code", "00") +
                self._g_try("transfer_function_code", "00") +
                self._g_try("process_variable_unit_code", "FA") +
                self._g_try("upper_range_value", "00000000") +
                self._g_try("lower_range_value", "00000000") +
                self._g_try("pressure_damping_value", "00000000") +
                self._g_try("write_protect_code", "00") +
                self._g_try("manufacturer_id", "00") +
                self._g_try("analog_output_numbers_code", "00")
            )

        elif cmd == "10":  # Read Final Assembly Number
            self._hrt_frame_write.body = status_ok() + self._g_try("final_assembly_number", "000000")

        elif cmd == "11":  # Write Message
            msg_hex = (hrt_frame_read.body or "").upper()
            self._s_try("message", msg_hex)
            self._hrt_frame_write.body = status_ok() + msg_hex

        elif cmd == "12":  # Write Tag, Descriptor, Date
            body = (hrt_frame_read.body or "").upper()
            tag_hex = body[:12].ljust(12, "0")
            descriptor_hex = body[12:36].ljust(24, "0")
            date_hex = body[36:42].ljust(6, "0")
            self._s_try("tag", tag_hex)
            self._s_try("descriptor", descriptor_hex)
            self._s_try("date", date_hex)
            self._hrt_frame_write.body = status_ok() + (tag_hex + descriptor_hex + date_hex)

        elif cmd == "13":  # Write Final Assembly Number
            fan_hex = (hrt_frame_read.body[:6] or "000000").upper()
            self._s_try("final_assembly_number", fan_hex)
            self._hrt_frame_write.body = status_ok() + fan_hex

        elif cmd == "21":  # Read Device Variables
            req = (hrt_frame_read.body or "").strip().upper()
            if len(req) == 2:
                codes = [req]
            else:
                n = int(req[:2], 16) if len(req) >= 2 else 0
                codes = [req[i:i + 2] for i in range(2, 2 + 2 * n, 2)]

            out = status_ok()
            for code_hex in codes:
                if code_hex == "00":  # PV
                    out += self._g_try("process_variable_unit_code", "FA")
                    out += self._g_try("PROCESS_VARIABLE", "7FC00000")
                else:
                    out += "FA" + "7FC00000"  # unidade "não usada" + NaN
            self._hrt_frame_write.body = out

        elif cmd == "26":  # Resetar as Flags de Erro (stub seguro)
            self._s_try("config_changed", "00")
            self._hrt_frame_write.body = status_ok() + self._g_try("comm_status", "00")

        elif cmd == "28":  # Enter/Exit Fixed Current Mode (eco)
            requested_hex = (hrt_frame_read.body or "").upper()
            self._hrt_frame_write.body = status_ok() + requested_hex

        elif cmd == "29":  # Perform Self Test (stub)
            self._hrt_frame_write.body = status_ok()

        elif cmd in ("2D", "2E"):  # Trim 4 mA / Trim 20 mA (stub)
            self._hrt_frame_write.body = status_ok()

        elif cmd == "50":  # Read Dynamic Variable Assignments
            self._hrt_frame_write.body = (
                status_ok() +
                (self._g_try("pv_code", "FA") if self._has("pv_code") else "FA") +
                (self._g_try("sv_code", "FA") if self._has("sv_code") else "FA") +
                (self._g_try("tv_code", "FA") if self._has("tv_code") else "FA") +
                (self._g_try("qv_code", "FA") if self._has("qv_code") else "FA")
            )

        # --------------------------- Estendidos (stubs) ---------------------------
        # IMPORTANTE: prefixar sempre status_ok() para não “deslocar” parsing do DTM.
        elif cmd == "82":
            self._hrt_frame_write.body = status_ok() + "00000201020101"
        elif cmd == "84":
            self._hrt_frame_write.body = status_ok() + "000002012543D2000040A99999"
        elif cmd == "87":
            self._hrt_frame_write.body = status_ok() + "00400201"
        elif cmd == "88":
            self._hrt_frame_write.body = status_ok() + "700002FFFFFF"
        elif cmd == "8A":
            self._hrt_frame_write.body = status_ok() + "000002FF"
        elif cmd == "8C":
            self._hrt_frame_write.body = status_ok() + "7000023941AC33E939000000003942480000FFFF3900000000"
        elif cmd == "98":
            self._hrt_frame_write.body = status_ok()
        elif cmd == "A2":
            self._hrt_frame_write.body = status_ok() + "00000201"
        elif cmd == "A4":
            self._hrt_frame_write.body = status_ok() + "0000020200"
        elif cmd == "A6":
            self._hrt_frame_write.body = status_ok() + "00000222040000130A270000010B00"
        elif cmd == "A8":
            self._hrt_frame_write.body = status_ok() + "00000201FF"
        elif cmd == "AD":
            self._hrt_frame_write.body = status_ok() + "0000025454333031313131302D425549314C335030543459"
        elif cmd == "B9":
            self._hrt_frame_write.body = status_ok() + "004002"
        elif cmd == "BB":
            self._hrt_frame_write.body = status_ok() + "000002FF"
        elif cmd == "C6":
            self._hrt_frame_write.body = status_ok() + "00000242480000"
        elif cmd == "DF":
            self._hrt_frame_write.body = status_ok() + "00000242C800003B801132B51B057FAC932D1D"

        else:
            # Comando não suportado -> response_code 0x40 (Command not implemented)
            self._hrt_frame_write.body = status_fail("40")

        return self._hrt_frame_write