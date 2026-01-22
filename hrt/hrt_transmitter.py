from __future__ import annotations

"""
HrtTransmitter (versão síncrona) — revisado

Objetivos desta revisão:
- Manter 100% das funcionalidades atuais.
- Tornar leitura/escrita de rows mais robusta (não falhar se uma key não existir).
- Normalizar o tratamento de comando (upper, validações de tamanho).
- Tornar o _prime_header mais claro e seguro (inclusive quando não encontra o endereço).
- Reduzir duplicação de código em respostas comuns (Identity, etc.).

Obs.: continua NÃO usando ReactVar.getValue (async). Apenas translate + setValue (sync).
"""

from typing import Union, Iterable
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


class HrtTransmitter:
    def __init__(self, react_factory: ReactFactory, table_name: str = "HART"):
        self.rf = react_factory
        self.table = table_name
        self.col: str = ""
        self._hrt_frame_write: HrtFrame | None = None

    # --------------------------- Safe DB helpers (não falha se row não existe) ---------------------------
    def _g_try(self, key: str, default_hex: str = "") -> str:
        """Lê uma key do DB; se não existir/der erro, retorna default_hex."""
        try:
            return self._get(key)
        except Exception:
            return default_hex

    def _s_try(self, key: str, hex_str: str) -> None:
        """Escreve uma key do DB; se não existir/der erro, ignora."""
        try:
            self._set(key, hex_str)
        except Exception:
            pass

    # --------------------------- Cabeçalho ---------------------------
    def _prime_header(self, hrt_frame_read: HrtFrame) -> bool:
        """
        Prepara o frame de escrita (cabeçalho + seleção da coluna/self.col de acordo com o address).
        Retorna True se NÃO encontrou um dispositivo (coluna) compatível com o address recebido.
        """
        assert self._hrt_frame_write is not None

        g = self._g_try
        s = self._s_try

        # Copia flags do frame recebido
        self._hrt_frame_write.command = hrt_frame_read.command
        self._hrt_frame_write.addressType = hrt_frame_read.addressType  # False curto / True longo
        self._hrt_frame_write.masterAddress = hrt_frame_read.masterAddress
        self._hrt_frame_write.burstMode = hrt_frame_read.burstMode

        # Procura coluna que gera o mesmo endereço (curto ou longo)
        found = False
        for col in self.rf.df[self.table].columns[2:]:
            self.col = col

            if self._hrt_frame_write.addressType:  # longo
                # (mantém o mesmo nome "manufacterId" do seu HrtFrame atual)
                self._hrt_frame_write.manufacterId = g("manufacturer_id", "00")
                self._hrt_frame_write.deviceType = g("device_type", "00")
                self._hrt_frame_write.deviceId = g("device_id", "000000")
            else:  # curto
                self._hrt_frame_write.pollingAddress = g("polling_address", "00")

            if self._hrt_frame_write.address == hrt_frame_read.address:
                found = True
                break

        if not found:
            return True

        # Atualiza “header rows” no DB (se existirem)
        s("frame_type", self._hrt_frame_write.frameType)
        s("address_type", ("80" if self._hrt_frame_write.addressType else "00"))
        s("master_address", ("80" if self._hrt_frame_write.masterAddress else "00"))
        s("burst_mode", ("20" if self._hrt_frame_write.burstMode else "00"))
        return False

    # --------------------------- API pública ---------------------------
    def request(self, hrt_frame_read: HrtFrame) -> Union[HrtFrame, str]:
        """
        Monta um REQUEST (frameType=02) para o comando recebido.
        Observação: alguns comandos “write” têm request body; os “read” geralmente têm body vazio.
        """
        self._hrt_frame_write = HrtFrame()
        self._hrt_frame_write.frameType = "02"

        if self._prime_header(hrt_frame_read):
            return ""  # mantém o comportamento atual

        cmd = (hrt_frame_read.command or "").upper()
        g = self._g_try

        # Comandos cujo request é vazio (leitura/poll)
        empty_req = {
            "00", "01", "02", "03", "04", "05",
            "07", "08", "09", "0A", "0B", "0C", "0D", "0E", "0F",
            "10", "14", "15", "16", "17", "18", "19",
            "21", "26", "28", "29", "2A", "2D", "2E", "50",
            # comandos estendidos normalmente “read” (mantém compatibilidade)
            "82", "84", "87", "88", "8A", "8C", "98", "A2", "A4", "A6", "A8", "AD", "B9", "BB", "C6", "DF",
        }

        if cmd in empty_req:
            self._hrt_frame_write.body = ""

        elif cmd == "06":  # Write Polling Address (eco)
            # body = polling_address (1B) + loop_current_mode (1B)
            self._hrt_frame_write.body = f"{g('polling_address', '00')}{g('loop_current_mode', '00')}"

        elif cmd == "11":  # Write Message (24 bytes packed ASCII)
            self._hrt_frame_write.body = g("message", "")

        elif cmd == "12":  # Write Tag, Descriptor, Date
            self._hrt_frame_write.body = (
                g("tag", "")
                + g("descriptor", "")
                + g("date", "")
            )

        elif cmd == "13":  # Write Final Assembly Number
            self._hrt_frame_write.body = g("final_assembly_number", "")

        else:
            # default seguro (não falha)
            self._hrt_frame_write.body = ""

        return self._hrt_frame_write

    def response(self, hrt_frame_read: HrtFrame) -> HrtFrame:
        """
        Monta um RESPONSE (frameType=06) para o comando recebido.
        """
        self._hrt_frame_write = HrtFrame()
        self._hrt_frame_write.frameType = "06"

        # Se não encontrou coluna/endereço: devolve frame vazio (mais seguro que crash)
        if self._prime_header(hrt_frame_read):
            self._hrt_frame_write.body = ""
            return self._hrt_frame_write

        cmd = (hrt_frame_read.command or "").upper()
        g = self._g_try
        s = self._s_try

        # Helpers de composição
        def cat(*parts: str) -> str:
            return "".join(parts)

        def identity_payload() -> str:
            # Layout igual ao que você já fazia no cmd 00/0B
            return cat(
                g("manufacturer_id", "00"),
                g("device_type", "00"),
                g("request_preambles", "05"),
                g("hart_revision", "07"),
                g("software_revision", "01"),
                g("transmitter_revision", "01"),
                g("hardware_revision", "01"),
                g("device_flags", "00"),
                g("device_id", "000000"),
            )

        if cmd == "00":  # Identity Command
            self._hrt_frame_write.body = cat(g("error_code", "00"), "FE", identity_payload())

        elif cmd == "01":  # Read Primary Variable
            self._hrt_frame_write.body = cat(
                g("error_code", "00"),
                g("process_variable_unit_code", "FA"),
                g("PROCESS_VARIABLE", "7FC00000"),  # NaN por padrão
            )

        elif cmd == "02":  # Read Loop Current And Percent Of Range
            self._hrt_frame_write.body = cat(
                g("error_code", "00"),
                g("loop_current", "00000000"),
                g("percent_of_range", "00000000"),
            )

        elif cmd == "03":  # Read Dynamic Variables And Loop Current
            body = [g("error_code", "00"), g("loop_current", "00000000")]
            for _ in range(4):
                body += [g("process_variable_unit_code", "FA"), g("PROCESS_VARIABLE", "7FC00000")]
            self._hrt_frame_write.body = "".join(body)

        elif cmd in {"04", "05", "09", "0A", "2A"}:
            self._hrt_frame_write.body = g("error_code", "00")

        elif cmd == "06":  # Write Polling Address (eco)
            body = hrt_frame_read.body or ""
            polling_address = (body[:2] if len(body) >= 2 else "00")
            loop_current_mode = (body[2:4] if len(body) >= 4 else "00")
            s("polling_address", polling_address)
            s("loop_current_mode", loop_current_mode)
            self._hrt_frame_write.body = cat(g("error_code", "00"), polling_address, loop_current_mode)

        elif cmd == "07":  # Read Loop Configuration
            self._hrt_frame_write.body = cat(
                g("error_code", "00"),
                g("polling_address", "00"),
                g("loop_current_mode", "00"),
            )

        elif cmd == "08":  # Read Dynamic Variable Classifications
            self._hrt_frame_write.body = cat(g("error_code", "00"), "00" * 4)

        elif cmd == "0B":  # Read Unique Identifier Associated With Tag
            ok = "00" if ((hrt_frame_read.body or "").upper() == g("tag", "").upper()) else "01"
            self._hrt_frame_write.body = cat(ok, "FE", identity_payload())

        elif cmd == "0C":  # Read Message
            self._hrt_frame_write.body = cat(g("error_code", "00"), g("message", ""))

        elif cmd == "0D":  # Read Tag, Descriptor, Date
            self._hrt_frame_write.body = cat(
                g("error_code", "00"),
                g("tag", ""),
                g("descriptor", ""),
                g("date", ""),
            )

        elif cmd == "0E":  # Read Primary Variable Transducer Information
            self._hrt_frame_write.body = cat(
                g("error_code", "00"),
                g("sensor1_serial_number", "000000"),
                g("process_variable_unit_code", "FA"),
                g("pressure_upper_range_limit", "7FC00000"),
                g("pressure_lower_range_limit", "7FC00000"),
                g("pressure_minimum_span", "7FC00000"),
            )

        elif cmd == "0F":  # Read Device / PV Output Information
            self._hrt_frame_write.body = cat(
                g("error_code", "00"),
                g("alarm_selection_code", "00"),
                g("transfer_function_code", "00"),
                g("process_variable_unit_code", "FA"),
                g("upper_range_value", "7FC00000"),
                g("lower_range_value", "7FC00000"),
                g("pressure_damping_value", "0000"),
                g("write_protect_code", "00"),
                g("manufacturer_id", "00"),
                g("analog_output_numbers_code", "00"),
            )

        elif cmd == "10":  # Read Final Assembly Number
            self._hrt_frame_write.body = cat(g("error_code", "00"), g("final_assembly_number", "000000"))

        elif cmd == "11":  # Write Message
            msg_hex = (hrt_frame_read.body or "")
            s("message", msg_hex)
            self._hrt_frame_write.body = cat(g("error_code", "00"), msg_hex)

        elif cmd == "12":  # Write Tag, Descriptor, Date
            body = hrt_frame_read.body or ""
            tag_hex = body[:12].ljust(12, "0")
            descriptor_hex = body[12:36].ljust(24, "0")
            date_hex = body[36:42].ljust(6, "0")
            s("tag", tag_hex)
            s("descriptor", descriptor_hex)
            s("date", date_hex)
            self._hrt_frame_write.body = cat(g("error_code", "00"), tag_hex, descriptor_hex, date_hex)

        elif cmd == "13":  # Write Final Assembly Number
            fan_hex = (hrt_frame_read.body or "")[:6].ljust(6, "0")
            s("final_assembly_number", fan_hex)
            self._hrt_frame_write.body = cat(g("error_code", "00"), fan_hex)

        elif cmd == "21":  # Read Device Variables
            req = (hrt_frame_read.body or "").upper()

            if len(req) == 2:
                codes = [req]
            elif len(req) >= 2:
                try:
                    n = int(req[:2], 16)
                    codes = [req[i:i + 2] for i in range(2, 2 + 2 * n, 2)]
                except Exception:
                    codes = []
            else:
                codes = []

            out = [g("error_code", "00")]
            for code_hex in codes:
                if code_hex == "00":  # PV
                    out += [g("process_variable_unit_code", "FA"), g("PROCESS_VARIABLE", "7FC00000")]
                else:
                    out += ["FA", "7FC00000"]  # unidade "não usada" + NaN
            self._hrt_frame_write.body = "".join(out)

        elif cmd == "26":  # Resetar as Flags de Erro
            self._hrt_frame_write.body = cat(
                "02",
                g("error_code", "00"),
                g("response_code", "00"),
                g("device_status", "00"),
                g("comm_status", "00"),
            )
            s("config_changed", "00")

        elif cmd == "28":  # Enter/Exit Fixed Current Mode
            requested_hex = (hrt_frame_read.body or "")
            self._hrt_frame_write.body = cat(g("error_code", "00"), requested_hex)

        elif cmd == "29":  # Perform Self Test
            self._hrt_frame_write.body = cat(g("response_code", "00"), g("device_status", "00"))

        elif cmd in {"2D", "2E"}:  # Trim 4 mA / Trim 20 mA
            self._hrt_frame_write.body = cat(g("response_code", "00"), g("device_status", "00"))

        elif cmd == "50":  # Read Dynamic Variable Assignments
            self._hrt_frame_write.body = cat(
                g("error_code", "00"),
                g("pv_code", "FA"),
                g("sv_code", "FA"),
                g("tv_code", "FA"),
                g("qv_code", "FA"),
            )

        # --------------------------- Comandos estendidos (mantidos como estavam) ---------------------------
        elif cmd == "82":
            self._hrt_frame_write.body = "00000201020101"
        elif cmd == "84":
            self._hrt_frame_write.body = "000002012543D2000040A99999"
        elif cmd == "87":
            self._hrt_frame_write.body = "00400201"
        elif cmd == "88":
            self._hrt_frame_write.body = "700002FFFFFF"
        elif cmd == "8A":
            self._hrt_frame_write.body = "000002FF"
        elif cmd == "8C":
            self._hrt_frame_write.body = "7000023941AC33E939000000003942480000FFFF3900000000"
        elif cmd == "98":
            self._hrt_frame_write.body = ""
        elif cmd == "A2":
            self._hrt_frame_write.body = "00000201"
        elif cmd == "A4":
            self._hrt_frame_write.body = "0000020200"
        elif cmd == "A6":
            self._hrt_frame_write.body = "00000222040000130A270000010B00"
        elif cmd == "A8":
            self._hrt_frame_write.body = "00000201FF"
        elif cmd == "AD":
            self._hrt_frame_write.body = "0000025454333031313131302D425549314C335030543459"
        elif cmd == "B9":
            self._hrt_frame_write.body = "004002"
        elif cmd == "BB":
            self._hrt_frame_write.body = "000002FF"
        elif cmd == "C6":
            self._hrt_frame_write.body = "00000242480000"
        elif cmd == "DF":
            self._hrt_frame_write.body = "00000242C800003B801132B51B057FAC932D1D"

        else:
            # fallback seguro
            self._hrt_frame_write.body = g("error_code", "00")

        return self._hrt_frame_write

    # --------------------------- Helpers (ReactVar) ---------------------------
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

    def _get(self, row_key: str) -> str:
        """Retorna **HEX** convertendo de human→machine via ReactVar.translate (síncrono)."""
        rv = self._rv(row_key)
        human_val = getattr(rv, "_value", None)
        return rv.translate(
            human_val,
            rv.type(),
            rv.byteSize(),
            DBState.machineValue,
            DBState.humanValue,
        )

    def _set(self, row_key: str, hex_str: str) -> None:
        """Grava **HEX** via ReactVar.setValue(..., stateAtual=DBState.machineValue)."""
        rv = self._rv(row_key)
        rv.setValue(hex_str, stateAtual=DBState.machineValue, isWidgetValueChanged=False)
