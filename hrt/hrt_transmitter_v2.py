from __future__ import annotations

# HrtTransmitter (versão síncrona)
# - Usa ReactFactory + ReactVar (sem storage).
# - Leitura via ReactVar.translate(_value, ..., DBState.machineValue, DBState.humanValue) — 100% síncrona.
# - Escrita via ReactVar.setValue(hex, stateAtual=DBState.machineValue).
# - Cabeçalho do HrtFrame em snake_case.
#
# Observação: ReactVar.getValue é async no seu projeto — por isso NÃO usamos getValue aqui.

from db_files.db_types import DBState
from typing import Union

try:
    from hrt.hrt_frame import HrtFrame      # ajuste se necessário
except Exception:
    from hrt_frame import HrtFrame          # fallback

try:
    from react.react_factory import ReactFactory
    from react.react_var import ReactVar
except Exception:
    from react.react_factory import ReactFactory   # fallback
    from react.react_var import ReactVar           # fallback


class HrtTransmitter:
    def __init__(self, react_factory: ReactFactory, table_name: str = "HART"):
        self.rf = react_factory
        self.table = table_name
        self.col = ""
        self._hrt_frame_write: HrtFrame | None = None
    # --------------------------- Cabeçalho ---------------------------
    def _prime_header(self, hrt_frame_read: HrtFrame) -> bool:
        s = self._set
        g = self._get        
        self._hrt_frame_write.command       = hrt_frame_read.command
        self._hrt_frame_write.addressType   = hrt_frame_read.addressType # False curto ou True Longo  
        self._hrt_frame_write.masterAddress = hrt_frame_read.masterAddress   # Master (True primário, False secundário)
        self._hrt_frame_write.burstMode     = hrt_frame_read.burstMode  # True - in Burst Mode; False - not Burst Mode or Slave
             
        for self.col in self.rf.df[self.table].columns[2:]:                    
            if self._hrt_frame_write.addressType: # False curto ou True Longo    
                self._hrt_frame_write.manufacterId   = g('manufacturer_id')
                self._hrt_frame_write.deviceType     = g('device_type')
                self._hrt_frame_write.deviceId       = g('device_id')
            else:
                self._hrt_frame_write.pollingAddress = g('polling_address')
            if self._hrt_frame_write.address == hrt_frame_read.address: break
        else: # Só cai aqui se NÃO houve break (varreu tudo e não encontrou)
            return True  
                             
        s('frame_type'    , self._hrt_frame_write.frameType)                        
        s('address_type'  , ('80' if self._hrt_frame_write.addressType else '00'))
        s('master_address', ('80' if self._hrt_frame_write.masterAddress else '00'))     
        s('burst_mode'    , ('20' if self._hrt_frame_write.burstMode else '00'))   
        return False           
    # --------------------------- Helpers (ReactVar) ---------------------------
    # --------------------------- API pública ---------------------------
    def request(self, hrt_frame_read: HrtFrame) -> Union[HrtFrame, str]:
        g = self._get  
        self._hrt_frame_write               = HrtFrame()        
        self._hrt_frame_write.frameType = "02" # 02 Request ou 06 Response
        if self._prime_header(hrt_frame_read): return ""
        cmd = hrt_frame_read.command

        if cmd in ('00','01','02','03','04','05','07','08','09','10','0C','0D','21'):
            self._hrt_frame_write.body = ""
        elif cmd == '06':  # Write Polling Address
            self._hrt_frame_write.body = f"{g('polling_address')}{g('loop_current_mode')}"
        elif cmd == '11':  # Write Message (24 bytes packed ASCII)
            self._hrt_frame_write.body = g('message')
        elif cmd == '12':  # Write Tag, Descriptor, Date
            self._hrt_frame_write.body  = g('tag')
            self._hrt_frame_write.body += g('descriptor')
            self._hrt_frame_write.body += g('date')
        elif cmd == '13':  # Write Final Assembly Number
            self._hrt_frame_write.body = g('final_assembly_number')
        else:
            self._hrt_frame_write.body = ""

        return self._hrt_frame_write

    def response(self, hrt_frame_read: HrtFrame) -> HrtFrame:
        g = self._get
        s = self._set       
        self._hrt_frame_write               = HrtFrame()         
        self._hrt_frame_write.frameType = "06" # 02 Request ou 06 Response        
        self._prime_header(hrt_frame_read)
        cmd = hrt_frame_read.command
        
        if cmd == '00':  # Identity Command         
            self._hrt_frame_write.body = g('error_code')
            self._hrt_frame_write.body += 'FE'
            self._hrt_frame_write.body += g('manufacturer_id')
            self._hrt_frame_write.body += g('device_type')
            self._hrt_frame_write.body += g('request_preambles')
            self._hrt_frame_write.body += g('hart_revision')
            self._hrt_frame_write.body += g('software_revision')
            self._hrt_frame_write.body += g('transmitter_revision')
            self._hrt_frame_write.body += g('hardware_revision')
            self._hrt_frame_write.body += g('device_flags')
            self._hrt_frame_write.body += g('device_id')

        elif cmd == '01':  # Read Primary Variable
            self._hrt_frame_write.body  = g('error_code')
            self._hrt_frame_write.body += g('process_variable_unit_code')
            self._hrt_frame_write.body += g('PROCESS_VARIABLE')

        elif cmd == '02':  # Read Loop Current And Percent Of Range
            self._hrt_frame_write.body  = g('error_code')
            self._hrt_frame_write.body += g('loop_current')
            self._hrt_frame_write.body += g('percent_of_range')

        elif cmd == '03':  # Read Dynamic Variables And Loop Current
            self._hrt_frame_write.body  = g('error_code')
            self._hrt_frame_write.body += g('loop_current')
            for _ in range(4):
                self._hrt_frame_write.body += g('process_variable_unit_code')
                self._hrt_frame_write.body += g('PROCESS_VARIABLE')

        elif cmd == '04':
            self._hrt_frame_write.body = g('error_code')

        elif cmd == '05':
            self._hrt_frame_write.body = g('error_code')

        elif cmd == '06':  # Write Polling Address (eco)
            polling_address  = hrt_frame_read.body[:2]
            loop_current_mode = hrt_frame_read.body[2:]
            s('polling_address', polling_address)
            s('loop_current_mode', loop_current_mode)
            self._hrt_frame_write.body  = g('error_code')
            self._hrt_frame_write.body += polling_address
            self._hrt_frame_write.body += loop_current_mode

        elif cmd == '07':  # Read Loop Configuration
            self._hrt_frame_write.body  = g('error_code')
            self._hrt_frame_write.body += g('polling_address')
            self._hrt_frame_write.body += g('loop_current_mode')

        elif cmd == '08':  # Read Dynamic Variable Classifications
            self._hrt_frame_write.body  = g('error_code')
            self._hrt_frame_write.body += '00' * 4

        elif cmd == '09':
            self._hrt_frame_write.body = g('error_code')

        elif cmd == '0A':
            self._hrt_frame_write.body = g('error_code')

        elif cmd == '0B':  # Read Unique Identifier Associated With Tag
            self._hrt_frame_write.body  = '00' if (hrt_frame_read.body == g('tag')) else '01'
            self._hrt_frame_write.body += 'FE'
            self._hrt_frame_write.body += g('manufacturer_id')
            self._hrt_frame_write.body += g('device_type')
            self._hrt_frame_write.body += g('request_preambles')
            self._hrt_frame_write.body += g('hart_revision')
            self._hrt_frame_write.body += g('software_revision')
            self._hrt_frame_write.body += g('transmitter_revision')
            self._hrt_frame_write.body += g('hardware_revision')
            self._hrt_frame_write.body += g('device_flags')
            self._hrt_frame_write.body += g('device_id')

        elif cmd == '0C':  # Read Message
            self._hrt_frame_write.body  = g('error_code')
            self._hrt_frame_write.body += g('message')

        elif cmd == '0D':  # Read Tag, Descriptor, Date
            self._hrt_frame_write.body  = g('error_code')
            self._hrt_frame_write.body += g('tag')
            self._hrt_frame_write.body += g('descriptor')
            self._hrt_frame_write.body += g('date')

        elif cmd == '0E':  # Read Primary Variable Transducer Information
            self._hrt_frame_write.body  = g('error_code')
            self._hrt_frame_write.body += g('sensor1_serial_number')
            self._hrt_frame_write.body += g('process_variable_unit_code')
            self._hrt_frame_write.body += g('pressure_upper_range_limit')
            self._hrt_frame_write.body += g('pressure_lower_range_limit')
            self._hrt_frame_write.body += g('pressure_minimum_span')

        elif cmd == '0F':  # Read Device / PV Output Information
            self._hrt_frame_write.body  = g('error_code')
            self._hrt_frame_write.body += g('alarm_selection_code')
            self._hrt_frame_write.body += g('transfer_function_code')
            self._hrt_frame_write.body += g('process_variable_unit_code')
            self._hrt_frame_write.body += g('upper_range_value')
            self._hrt_frame_write.body += g('lower_range_value')
            self._hrt_frame_write.body += g('pressure_damping_value')
            self._hrt_frame_write.body += g('write_protect_code')
            self._hrt_frame_write.body += g('manufacturer_id')
            self._hrt_frame_write.body += g('analog_output_numbers_code')

        elif cmd == '10':  # Read Final Assembly Number
            self._hrt_frame_write.body  = g('error_code')
            self._hrt_frame_write.body += g('final_assembly_number')

        elif cmd == '11':  # Write Message
            msg_hex = hrt_frame_read.body
            s('message', msg_hex)
            self._hrt_frame_write.body  = g('error_code')
            self._hrt_frame_write.body += msg_hex

        elif cmd == '12':  # Write Tag, Descriptor, Date
            body = hrt_frame_read.body
            tag_hex        = body[:12]
            descriptor_hex = body[12:12+24]
            date_hex       = body[36:42]
            s('tag', tag_hex)
            s('descriptor', descriptor_hex)
            s('date', date_hex)
            self._hrt_frame_write.body  = g('error_code')
            self._hrt_frame_write.body += tag_hex + descriptor_hex + date_hex

        elif cmd == '13':  # Write Final Assembly Number
            fan_hex = hrt_frame_read.body[:6]
            s('final_assembly_number', fan_hex)
            self._hrt_frame_write.body  = g('error_code')
            self._hrt_frame_write.body += fan_hex

        elif cmd == '21':  # Read Device Variables
            req = hrt_frame_read.body
            if len(req) == 2:
                codes = [req.upper()]
            else:
                n = int(req[:2], 16)
                codes = [req[i:i+2].upper() for i in range(2, 2+2*n, 2)]

            self._hrt_frame_write.body = g('error_code')
            for code_hex in codes:
                if code_hex == '00':  # PV
                    self._hrt_frame_write.body += g('process_variable_unit_code')
                    self._hrt_frame_write.body += g('PROCESS_VARIABLE')
                else:
                    self._hrt_frame_write.body += 'FA' + '7FC00000'  # unidade "não usada" + NaN

        elif cmd == '26':  # Resetar as Flags de Erro
            self._hrt_frame_write.body  = '02'
            self._hrt_frame_write.body += g('error_code')
            self._hrt_frame_write.body += g('response_code')
            self._hrt_frame_write.body += g('device_status')
            self._hrt_frame_write.body += g('comm_status')
            s('config_changed', '00')

        elif cmd == '28':  # Enter/Exit Fixed Current Mode
            requested_hex = hrt_frame_read.body
            self._hrt_frame_write.body  = g('error_code')
            self._hrt_frame_write.body += requested_hex

        elif cmd == '29':  # Perform Self Test
            self._hrt_frame_write.body  = g('response_code')
            self._hrt_frame_write.body += g('device_status')

        elif cmd == '2A':  # Perform Device Reset
            self._hrt_frame_write.body = g('error_code')

        elif cmd == '2D':  # Trim 4 mA
            self._hrt_frame_write.body  = g('response_code')
            self._hrt_frame_write.body += g('device_status')

        elif cmd == '2E':  # Trim 20 mA
            self._hrt_frame_write.body  = g('response_code')
            self._hrt_frame_write.body += g('device_status')

        elif cmd == '50':  # Read Dynamic Variable Assignments
            self._hrt_frame_write.body  = g('error_code')
            self._hrt_frame_write.body += (g('pv_code') if self._has('pv_code') else 'FA')
            self._hrt_frame_write.body += (g('sv_code') if self._has('sv_code') else 'FA')
            self._hrt_frame_write.body += (g('tv_code') if self._has('tv_code') else 'FA')
            self._hrt_frame_write.body += (g('qv_code') if self._has('qv_code') else 'FA')

        elif cmd == '82':
            self._hrt_frame_write.body = '00000201020101'
        elif cmd == '84':
            self._hrt_frame_write.body = '000002012543D2000040A99999'
        elif cmd == '87':
            self._hrt_frame_write.body = '00400201'
        elif cmd == '88':
            self._hrt_frame_write.body = '700002FFFFFF'
        elif cmd == '8A':
            self._hrt_frame_write.body = '000002FF'
        elif cmd == '8C':
            self._hrt_frame_write.body = '7000023941AC33E939000000003942480000FFFF3900000000'
        elif cmd == '98':
            self._hrt_frame_write.body = ''
        elif cmd == 'A2':
            self._hrt_frame_write.body = '00000201'
        elif cmd == 'A4':
            self._hrt_frame_write.body = '0000020200'
        elif cmd == 'A6':
            self._hrt_frame_write.body = '00000222040000130A270000010B00'
        elif cmd == 'A8':
            self._hrt_frame_write.body = '00000201FF'
        elif cmd == 'AD':
            self._hrt_frame_write.body = '0000025454333031313131302D425549314C335030543459'
        elif cmd == 'B9':
            self._hrt_frame_write.body = '004002'
        elif cmd == 'BB':
            self._hrt_frame_write.body = '000002FF'
        elif cmd == 'C6':
            self._hrt_frame_write.body = '00000242480000'
        elif cmd == 'DF':
            self._hrt_frame_write.body = '00000242C800003B801132B51B057FAC932D1D'

        return self._hrt_frame_write

    def _rv(self, row_key: str) -> ReactVar:
        rv = self.rf.df[self.table].at[row_key, self.col]
        if not isinstance(rv, ReactVar):
            raise TypeError(f"Célula não é ReactVar: {self.table}.{self.col}.{row_key} → {type(rv).__name__}")
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
        return rv.translate(human_val, rv.type(), rv.byteSize(), DBState.machineValue, DBState.humanValue)


    def _set(self, row_key: str, hex_str: str) -> None:
        """Grava **HEX** via ReactVar.setValue(..., stateAtual=DBState.machineValue)."""
        rv = self._rv(row_key)
        rv.setValue(hex_str, stateAtual=DBState.machineValue, isWidgetValueChanged=False)

