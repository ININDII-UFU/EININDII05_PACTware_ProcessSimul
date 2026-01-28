from __future__ import annotations
"""
HrtTransmitter — SYNC — Dict/DSL style (modelo v4)

- COMMANDS é o único ponto de configuração (req/write/resp/after).
- Leitura/Escrita 100% síncrona via ReactVar.translate / ReactVar.setValue.
- DSL suportada em COMMANDS:
    * Strings:
        - "$BODY"            -> body recebido (HEX string)
        - "$SEL2"            -> 2º byte do body (chars 2..4)
        - "$BODY[a:b]"       -> fatia do body (a inclusive, b exclusivo). b vazio => até o fim.
        - "$code"            -> usado dentro de FOR_CODES
        - Literal HEX        -> ex.: "FE", "7FC00000"
        - RowKey do DB       -> ex.: "manufacturer_id", "PROCESS_VARIABLE"
    * Dicts:
        - {"SET": {"row":"tag", "value":"$BODY[0:12]"}}     (side-effect)
        - {"IF": {"EQ":[A,B], "THEN":[...], "ELSE":[...]}}
        - {"MAP":{"KEY":X, "TABLE":{...}, "DEFAULT":Y}}
        - {"FOR_CODES":{"SRC":"$BODY","PREFIX":[...], "DO": <expr|list>}}

Notas:
- Esta versão mantém 0B e 21 com o comportamento especial (status/tag e lista de variáveis).
- Literais mínimos de protocolo (ex.: "FA" e "7FC00000") permanecem como HEX literal por design.
"""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from db_files.db_types import DBState

try:
    from hrt.hrt_frame import HrtFrame
except Exception:
    from hrt_frame import HrtFrame

try:
    from react.react_factory import ReactFactory
    from react.react_var import ReactVar
except Exception:
    from react.react_factory import ReactFactory
    from react.react_var import ReactVar


# ======================================================================================
# MACROS
# ======================================================================================

IDENTITY_BLOCK = [
    "FE",
    "manufacturer_id",
    "device_type",
    "request_preambles",
    "hart_revision",
    "software_revision",
    "transmitter_revision",
    "hardware_revision",
    "device_flags",
    "device_id",
]

PV_UNIT_AND_VALUE = ["process_variable_unit_code", "PROCESS_VARIABLE"]


# ======================================================================================
# ÚNICO PONTO DE CONFIGURAÇÃO
# ======================================================================================

COMMANDS: Dict[str, Dict[str, Any]] = {
    # -------- Universais --------
    "00": {"resp": ["error_code", *IDENTITY_BLOCK]},
    "01": {"resp": ["error_code", *PV_UNIT_AND_VALUE]},
    "02": {"resp": ["error_code", "loop_current", "percent_of_range"]},
    "03": {"resp": ["error_code", "loop_current", *(PV_UNIT_AND_VALUE * 4)]},
    "04": {"resp": ["error_code"]},
    "05": {"resp": ["error_code"]},

    "06": {
        "req": ["polling_address", "loop_current_mode"],
        "resp": ["error_code"],
        "write": [
            {"SET": {"row": "polling_address", "value": "$BODY[0:2]"}},
            {"SET": {"row": "loop_current_mode", "value": "$BODY[2:]"}},
        ],
    },

    "07": {"resp": ["error_code", "polling_address", "loop_current_mode"]},
    "08": {"resp": ["error_code", "00000000"]},
    "09": {"resp": ["error_code"]},
    "0A": {"resp": ["error_code"]},

    # 0B especial: status 00/01 e bloco de identidade (igual cmd 00, mas sem error_code)
    "0B": {"resp": [
        {"IF": {
            "EQ": ["$BODY", "tag"],
            "THEN": ["00", *IDENTITY_BLOCK],
            "ELSE": ["01", *IDENTITY_BLOCK],
        }}
    ]},

    "0C": {"resp": ["error_code", "message"]},
    "0D": {"resp": ["error_code", "tag", "descriptor", "date"]},

    "0E": {"resp": ["error_code", "sensor1_serial_number", "process_variable_unit_code",
                    "pressure_upper_range_limit", "pressure_lower_range_limit", "pressure_minimum_span"]},

    "0F": {"resp": ["error_code", "alarm_selection_code", "transfer_function_code", "process_variable_unit_code",
                    "upper_range_value", "lower_range_value", "pressure_damping_value", "write_protect_code",
                    "manufacturer_id", "analog_output_numbers_code"]},

    "10": {"resp": ["error_code", "final_assembly_number"]},

    "11": {
        "req": ["message"],
        "resp": ["error_code"],
        "write": [{"SET": {"row": "message", "value": "$BODY"}}],
    },

    "12": {
        "req": ["tag", "descriptor", "date"],
        "resp": ["error_code"],
        "write": [
            {"SET": {"row": "tag", "value": "$BODY[0:12]"}},
            {"SET": {"row": "descriptor", "value": "$BODY[12:36]"}},
            {"SET": {"row": "date", "value": "$BODY[36:42]"}},
        ],
    },

    "13": {
        "req": ["final_assembly_number"],
        "resp": ["error_code"],
        "write": [{"SET": {"row": "final_assembly_number", "value": "$BODY[0:6]"}}],
    },

    # 21 especial: lista de códigos e retorno PV para 00, senão FA + NaN
    "21": {"resp": [
        {"FOR_CODES": {
            "SRC": "$BODY",
            "PREFIX": ["error_code"],
            "DO": {"IF": {
                "EQ": ["$code", "00"],
                "THEN": [*PV_UNIT_AND_VALUE],
                "ELSE": ["FA", "7FC00000"],
            }},
        }}
    ]},

    # Melhor prática: side effects fora do resp
    "26": {"resp": ["02", "error_code", "response_code", "device_status", "comm_status"],
           "after": [{"SET": {"row": "config_changed", "value": "00"}}]},

    "28": {"resp": ["error_code", "$BODY"]},
    "29": {"resp": ["response_code", "device_status"]},
    "2A": {"resp": ["error_code"]},
    "2D": {"resp": ["response_code", "device_status"]},
    "2E": {"resp": ["response_code", "device_status"]},

    "50": {"resp": ["error_code", "pv_code", "sv_code", "tv_code", "qv_code"]},

    # -------- Vendor/Extended --------
    # (Se você quiser "DB-only estrito", troque estes literais por row_keys do DB.)
    "80": {"resp": ["00400C020A0102FBFBFBFB010200000443FEFFFC00000000FA00"]},
    "88": {"resp": ["704017FFFF"]},
    "8A": {"resp": ["error_code", "FF"]},
    "8C": {"resp": ["704039000000003900000000390000000001FF39FFFFFFFF"]},
    "A4": {"resp": ["error_code", "0400"]},
    "A6": {"resp": ["00401701000002000000000000000300"]},
    "B9": {"resp": ["7640FFFB4E1C4363"]},

    "85": {"req": ["$BODY"], "resp": ["error_code", {"MAP": {"KEY": "$BODY", "TABLE": {
        "00": "00020000000042C8000042CC000042CE0000",
        "08": "040242D0000042D2000042D4000042D60000",
        "10": "0C0242E0000042E2000042E4000042E60000",
        "18": "140242D0000042D2000042D4000042D60000",
        "1C": "1C0242E0000042E2000042E4000042E60000",
    }, "DEFAULT": "0002000000000000000000000000000000"}}]},

    "A0": {"req": ["$BODY"], "resp": ["error_code", "$BODY", "0F05", {"MAP": {"KEY": "$BODY", "TABLE": {
        "00": "0000000000000000",
        "01": "42FF659F42FF659F",
        "02": "437F659F437F659F",
        "03": "43BF8C3743BF8C37",
        "04": "43FF659F43FF659F",
    }, "DEFAULT": "0000000000000000"}}]},

    "8E": {"resp": ["70403F8000003DCCCCCC00000000000000003DCCCCCC"]},
    "2B": {"req": ["$BODY"], "resp": ["error_code", "00"]},
    "9C": {"resp": ["error_code", "0040C00000"]},
    "B0": {"resp": ["error_code", "796D332F6800"]},
    "B2": {"resp": ["error_code", "00000000000000000000"]},
    "BA": {"resp": ["764042C800003F800000"]},
    "BD": {"resp": ["7640FB4E4F4E4520"]},
    "CC": {"req": ["$BODY"], "resp": ["error_code", "$BODY", "00"]},
    "AD": {"resp": ["error_code", "4C443330314431314954553131303131202020202020"]},
}


# ======================================================================================
# Compilação do DSL (uma vez) para reduzir custo por frame
# ======================================================================================

Token = Any  # str | dict | CompiledBodySlice | tuple


@dataclass(frozen=True)
class CompiledBodySlice:
    start: int
    end: Optional[int]  # None = até o fim

    def eval(self, body: str) -> str:
        return body[self.start:self.end]


@dataclass(frozen=True)
class CompiledSpec:
    req: Tuple[Token, ...]
    write: Tuple[Token, ...]
    resp: Tuple[Token, ...]
    after: Tuple[Token, ...]


_HEX_CHARS = set("0123456789ABCDEF")


def _is_hex_literal(s: str) -> bool:
    if not s or (len(s) % 2) != 0:
        return False
    u = s.upper()
    return all(ch in _HEX_CHARS for ch in u)


def _compile_body_slice(expr: str) -> Optional[CompiledBodySlice]:
    if not (expr.startswith("$BODY[") and expr.endswith("]")):
        return None
    inner = expr[6:-1]
    if ":" not in inner:
        return None
    a, b = inner.split(":", 1)
    a = a.strip()
    b = b.strip()
    start = int(a) if a else 0
    end = int(b) if b else None
    if start < 0 or (end is not None and end < 0):
        return None
    return CompiledBodySlice(start=start, end=end)


def _compile_token(tok: Token) -> Token:
    if isinstance(tok, str):
        s = tok.strip()
        bs = _compile_body_slice(s)
        return bs if bs is not None else s

    if isinstance(tok, list):
        return tuple(_compile_token(x) for x in tok)

    if isinstance(tok, dict):
        if "SET" in tok:
            spec = tok["SET"]
            return {"SET": {"row": spec["row"], "value": _compile_token(spec["value"])}}

        if "IF" in tok:
            spec = tok["IF"]
            return {"IF": {
                "EQ": (_compile_token(spec["EQ"][0]), _compile_token(spec["EQ"][1])),
                "THEN": tuple(_compile_token(x) for x in spec["THEN"]),
                "ELSE": tuple(_compile_token(x) for x in spec["ELSE"]),
            }}

        if "MAP" in tok:
            spec = tok["MAP"]
            return {"MAP": {
                "KEY": _compile_token(spec["KEY"]),
                "TABLE": {str(k).upper(): str(v).upper() for k, v in (spec.get("TABLE") or {}).items()},
                "DEFAULT": _compile_token(spec.get("DEFAULT", "error_code")),
            }}

        if "FOR_CODES" in tok:
            spec = tok["FOR_CODES"]
            do = spec["DO"]
            return {"FOR_CODES": {
                "SRC": _compile_token(spec["SRC"]),
                "PREFIX": tuple(_compile_token(x) for x in (spec.get("PREFIX") or ())),
                "DO": _compile_token(do) if isinstance(do, (str, dict, CompiledBodySlice)) else tuple(_compile_token(x) for x in do),
            }}

    return tok


def compile_commands(commands: Dict[str, Dict[str, Any]]) -> Dict[str, CompiledSpec]:
    compiled: Dict[str, CompiledSpec] = {}
    for cmd, spec in commands.items():
        c = (cmd or "").upper()
        req = tuple(_compile_token(x) for x in (spec.get("req") or ()))
        write = tuple(_compile_token(x) for x in (spec.get("write") or ()))
        resp = tuple(_compile_token(x) for x in (spec.get("resp") or ()))
        after = tuple(_compile_token(x) for x in (spec.get("after") or ()))
        compiled[c] = CompiledSpec(req=req, write=write, resp=resp, after=after)
    return compiled


# ======================================================================================
# Implementação
# ======================================================================================

class HrtTransmitter:
    def __init__(self, react_factory: ReactFactory, table_name: str = "HART", commands: Optional[Dict[str, Dict[str, Any]]] = None):
        self.rf = react_factory
        self.table = table_name
        self.col = ""
        self._hrt_frame_write: Optional[HrtFrame] = None
        self._compiled = compile_commands(commands or COMMANDS)

    # ---------- ReactVar ----------
    def _rv(self, row_key: str) -> ReactVar:
        rv = self.rf.df[self.table].at[row_key, self.col]
        if not isinstance(rv, ReactVar):
            raise TypeError(f"{self.table}.{self.col}.{row_key} não é ReactVar ({type(rv).__name__})")
        return rv

    def _has(self, row_key: str) -> bool:
        try:
            return isinstance(self.rf.df[self.table].at[row_key, self.col], ReactVar)
        except Exception:
            return False

    def _get(self, row_key: str, default_hex: Optional[str] = None) -> str:
        """Retorna HEX via translate (human->machine)."""
        if not self._has(row_key):
            if default_hex is None:
                raise KeyError(f"DB missing row '{row_key}'")
            return default_hex

        rv = self._rv(row_key)
        human_val = getattr(rv, "_value", None)
        out = rv.translate(human_val, rv.type(), rv.byteSize(), DBState.machineValue, DBState.humanValue)
        out = (out or "").strip().upper().replace(" ", "")
        if out.startswith("0X"):
            out = out[2:]
        if len(out) % 2 == 1:
            out = "0" + out
        if not _is_hex_literal(out):
            if default_hex is None:
                raise ValueError(f"DB.translate('{row_key}') returned non-HEX: {out!r}")
            return default_hex
        return out

    def _set(self, row_key: str, hex_str: str) -> None:
        if not self._has(row_key):
            return
        rv = self._rv(row_key)
        rv.setValue(hex_str, stateAtual=DBState.machineValue, isWidgetValueChanged=False)

    # ---------- Header ----------
    def _prime_header(self, hrt_frame_read: HrtFrame) -> bool:
        """Seleciona coluna (device) e preenche campos de endereçamento."""
        g = self._get
        s = self._set

        # copia bits do mestre (padrão do projeto)
        self._hrt_frame_write.command = hrt_frame_read.command
        self._hrt_frame_write.addressType = hrt_frame_read.addressType
        self._hrt_frame_write.masterAddress = hrt_frame_read.masterAddress
        self._hrt_frame_write.burstMode = hrt_frame_read.burstMode

        # procura coluna cujo address bate
        for self.col in self.rf.df[self.table].columns[2:]:
            if self._hrt_frame_write.addressType:
                self._hrt_frame_write.manufacterId = g("manufacturer_id", "00")
                self._hrt_frame_write.deviceType = g("device_type", "00")
                self._hrt_frame_write.deviceId = g("device_id", "000000")
            else:
                self._hrt_frame_write.pollingAddress = g("polling_address", "00")

            if self._hrt_frame_write.address == hrt_frame_read.address:
                break
        else:
            return True

        # espelha para o DB (se existir)
        try:
            s("frame_type", self._hrt_frame_write.frameType)
            s("address_type", "80" if self._hrt_frame_write.addressType else "00")
            s("master_address", "80" if self._hrt_frame_write.masterAddress else "00")
            s("burst_mode", "20" if self._hrt_frame_write.burstMode else "00")
        except Exception:
            pass

        return False

    # ---------- Engine ----------
    def _sel2(self, body: str) -> str:
        return body[2:4].upper() if len(body) >= 4 else "00"

    def _parse_codes(self, body_hex: str) -> List[str]:
        body_hex = (body_hex or "").upper()
        if len(body_hex) == 2 and _is_hex_literal(body_hex):
            return [body_hex]
        if len(body_hex) < 2 or any(ch not in _HEX_CHARS for ch in body_hex):
            return []
        try:
            n = int(body_hex[:2], 16)
        except Exception:
            n = 0
        codes: List[str] = []
        for i in range(2, 2 + 2 * n, 2):
            c = body_hex[i:i + 2]
            if len(c) == 2:
                codes.append(c.upper())
        return codes

    def _eval_token(self, token: Token, ctx: Dict[str, str]) -> str:
        if token is None:
            return ""

        if isinstance(token, CompiledBodySlice):
            return token.eval(ctx.get("BODY", "")).upper()

        if isinstance(token, tuple):
            return "".join(self._eval_token(x, ctx) for x in token)

        if isinstance(token, str):
            t = token.strip()

            if t == "$BODY":
                return ctx.get("BODY", "").upper()
            if t == "$SEL2":
                return self._sel2(ctx.get("BODY", ""))
            if t.startswith("$") and t[1:] in ctx:
                return ctx[t[1:]].upper()

            if _is_hex_literal(t):
                return t.upper()

            # DB row key
            return self._get(t)

        if isinstance(token, dict):
            if "SET" in token:
                spec = token["SET"]
                row = spec["row"]
                val_hex = self._eval_token(spec["value"], ctx)
                self._set(row, val_hex)
                return ""

            if "IF" in token:
                spec = token["IF"]
                left = self._eval_token(spec["EQ"][0], ctx).upper()
                right = self._eval_token(spec["EQ"][1], ctx).upper()
                branch = spec["THEN"] if left == right else spec["ELSE"]
                return "".join(self._eval_token(x, ctx) for x in branch)

            if "MAP" in token:
                spec = token["MAP"]
                key = self._eval_token(spec["KEY"], ctx).upper()
                table = spec.get("TABLE") or {}
                if key in table:
                    return str(table[key]).upper()
                return self._eval_token(spec.get("DEFAULT", "error_code"), ctx)

            if "FOR_CODES" in token:
                spec = token["FOR_CODES"]
                src = self._eval_token(spec["SRC"], ctx)
                codes = self._parse_codes(src)
                out: List[str] = []
                for p in (spec.get("PREFIX") or ()):
                    out.append(self._eval_token(p, ctx))
                do = spec["DO"]
                for c in codes:
                    ctx2 = dict(ctx)
                    ctx2["code"] = c
                    out.append(self._eval_token(do, ctx2))
                return "".join(out)

        return ""

    def _eval_list(self, items: Iterable[Token], ctx: Dict[str, str]) -> str:
        return "".join(self._eval_token(x, ctx) for x in items)

    def _err_body(self, response_code: str = "02") -> str:
        """Corpo mínimo de erro."""
        ec = self._get("error_code", "0000")
        ds = self._get("device_status", "40")
        cs = self._get("comm_status", "00")
        return (ec + response_code.upper().zfill(2) + ds + cs).upper()

    def _make_reply(self, command: str, body: str) -> HrtFrame:
        # headers já primeados
        self._hrt_frame_write.frameType = "06"
        self._hrt_frame_write.command = (command or "").upper()
        self._hrt_frame_write.body = (body or "").upper()
        self._hrt_frame_write.byte_count = f"{len(self._hrt_frame_write.body) // 2:02X}"
        return self._hrt_frame_write

    # ---------- Public API ----------
    def request(self, hrt_frame_read: HrtFrame) -> Union[HrtFrame, str]:
        self._hrt_frame_write = HrtFrame()
        self._hrt_frame_write.frameType = "02"
        if self._prime_header(hrt_frame_read):
            return ""

        cmd = (hrt_frame_read.command or "").upper()
        spec = self._compiled.get(cmd)

        ctx = {"BODY": (hrt_frame_read.body or "").upper()}
        self._hrt_frame_write.body = self._eval_list(spec.req, ctx) if spec else ""
        return self._hrt_frame_write

    def response(self, hrt_frame_read: HrtFrame) -> HrtFrame:
        self._hrt_frame_write = HrtFrame()
        # começa como resposta (06)
        self._hrt_frame_write.frameType = "06"
        if self._prime_header(hrt_frame_read):
            # se não achar address, responde erro genérico
            body = self._err_body("02")
            return self._make_reply(hrt_frame_read.command or "", body)

        cmd = (hrt_frame_read.command or "").upper()
        spec = self._compiled.get(cmd)
        ctx = {"BODY": (hrt_frame_read.body or "").upper()}

        if spec is None:
            body = self._err_body("02")
            return self._make_reply(cmd, body)

        try:
            # write (antes)
            self._eval_list(spec.write, ctx)

            # resp
            body = self._eval_list(spec.resp, ctx)

            # after (depois)
            self._eval_list(spec.after, ctx)

        except Exception:
            body = self._err_body("02")

        return self._make_reply(cmd, body)
