from hrt_data import HrtData
from hrt_frame import HrtFrame

class HrtTransmitter:
    def __init__(self, hrt_data, hrt_frame_read):
        self._hrt_frame_write = HrtFrame()
        self._hrt_frame_write.command = hrt_frame_read.command
        self._hrt_frame_write.address_type = hrt_frame_read.address_type
        hrt_data.set_variable('address_type', ('00' if hrt_frame_read.address_type == False else '80'))
        self._hrt_frame_write.frame_type = hrt_data.get_variable('frame_type')
        self._hrt_frame_write.master_address = (True if hrt_data.get_variable('master_address') == "00" else False)

        if self._hrt_frame_write.address_type:
            self._hrt_frame_write.manufacter_id = hrt_data.get_variable('manufacturer_id')
            self._hrt_frame_write.device_type = hrt_data.get_variable('device_type')
            self._hrt_frame_write.device_id = hrt_data.get_variable('device_id')
        else:
            self._hrt_frame_write.polling_address = hrt_data.get_variable('polling_address')

            if self._hrt_frame_write.frame_type == "02":
                self._request(hrt_data, hrt_frame_read)
            else:
                self._response(hrt_data, hrt_frame_read)

    @property
    def frame(self):
        return self._hrt_frame_write.frame

    # ========================= REQUEST (quando o simulador atua como mestre) =========================
    def _request(self, hrt_data, hrt_frame_read):
        command = hrt_frame_read.command

        # Observação: aqui só montamos corpo de requisição quando necessário.
        if command in ('00','01','02','03','04','05','07','08','09','10','0C','0D','21'):
            self._hrt_frame_write.body = ""
        elif command == '06':  # Write Polling Address
            self._hrt_frame_write.body = f"{hrt_data.get_variable('polling_address')}{hrt_data.get_variable('loop_current_mode')}"
        elif command == '11':  # Write Message (envia mensagem packed ASCII 24 bytes)
            self._hrt_frame_write.body = hrt_data.get_variable('message')
        elif command == '12':  # Write Tag, Descriptor, Date
            self._hrt_frame_write.body  = hrt_data.get_variable('tag')
            self._hrt_frame_write.body += hrt_data.get_variable('descriptor')
            self._hrt_frame_write.body += hrt_data.get_variable('date')
        elif command == '13':  # Write Final Assembly Number
            self._hrt_frame_write.body = hrt_data.get_variable('final_assembly_number')
        else:
            # por padrão, nenhuma carga em requisições não-mapeadas
            self._hrt_frame_write.body = ""

    # ========================= RESPONSE (quando o simulador atua como dispositivo) =========================
    def _response(self, hrt_data, hrt_frame_read):
        command = hrt_frame_read.command

        if command == '00':  # Identity Command
            self._hrt_frame_write.body  = hrt_data.get_variable('error_code')
            self._hrt_frame_write.body += "FE"
            self._hrt_frame_write.body += hrt_data.get_variable('master_address | manufacturer_id')
            self._hrt_frame_write.body += hrt_data.get_variable('device_type')
            self._hrt_frame_write.body += hrt_data.get_variable('request_preambles')
            self._hrt_frame_write.body += hrt_data.get_variable('hart_revision')
            self._hrt_frame_write.body += hrt_data.get_variable('software_revision')
            self._hrt_frame_write.body += hrt_data.get_variable('transmitter_revision')
            self._hrt_frame_write.body += hrt_data.get_variable('hardware_revision')
            self._hrt_frame_write.body += hrt_data.get_variable('device_flags')
            self._hrt_frame_write.body += hrt_data.get_variable('device_id')

        elif command == '01':  # Read Primary Variable
            self._hrt_frame_write.body  = hrt_data.get_variable('error_code')
            self._hrt_frame_write.body += hrt_data.get_variable('unit_code')
            self._hrt_frame_write.body += hrt_data.get_variable('PROCESS_VARIABLE')

        elif command == '02':  # Read Loop Current And Percent Of Range
            self._hrt_frame_write.body  = hrt_data.get_variable('error_code')
            self._hrt_frame_write.body += hrt_data.get_variable('loop_current')
            self._hrt_frame_write.body += hrt_data.get_variable('percent_of_range')

        elif command == '03':  # Read Dynamic Variables And Loop Current
            self._hrt_frame_write.body  = hrt_data.get_variable('error_code')
            self._hrt_frame_write.body += hrt_data.get_variable('loop_current')
            # Para HART5, frequentemente apenas PV está ativo; se quiser, repita PV nas 4 posições ou use 0xFA/NaN nas demais.
            self._hrt_frame_write.body += hrt_data.get_variable('unit_code')
            self._hrt_frame_write.body += hrt_data.get_variable('PROCESS_VARIABLE')
            self._hrt_frame_write.body += hrt_data.get_variable('unit_code')
            self._hrt_frame_write.body += hrt_data.get_variable('PROCESS_VARIABLE')
            self._hrt_frame_write.body += hrt_data.get_variable('unit_code')
            self._hrt_frame_write.body += hrt_data.get_variable('PROCESS_VARIABLE')
            self._hrt_frame_write.body += hrt_data.get_variable('unit_code')
            self._hrt_frame_write.body += hrt_data.get_variable('PROCESS_VARIABLE')

        elif command == '04':  # reservado
            self._hrt_frame_write.body = hrt_data.get_variable('error_code')

        elif command == '05':  # reservado
            self._hrt_frame_write.body = hrt_data.get_variable('error_code')

        elif command == '06':  # Write Polling Address (eco do que foi escrito)
            # request body: 1 byte polling + 1 byte loop_current_mode (seu simulador já envia assim em _request)
            polling_address = hrt_frame_read.body[:2]
            loop_current_mode = hrt_frame_read.body[2:]
            hrt_data.set_variable('polling_address', polling_address)
            hrt_data.set_variable('loop_current_mode', loop_current_mode)
            self._hrt_frame_write.body  = hrt_data.get_variable('error_code')
            self._hrt_frame_write.body += polling_address
            self._hrt_frame_write.body += loop_current_mode

        elif command == '07':  # Read Loop Configuration
            self._hrt_frame_write.body  = hrt_data.get_variable('error_code')
            self._hrt_frame_write.body += hrt_data.get_variable('polling_address')
            self._hrt_frame_write.body += hrt_data.get_variable('loop_current_mode')

        elif command == '08':  # Read Dynamic Variable Classifications
            self._hrt_frame_write.body  = hrt_data.get_variable('error_code')
            self._hrt_frame_write.body += hrt_data.get_variable('primary_variable_classification')
            self._hrt_frame_write.body += hrt_data.get_variable('secondary_variable_classification')
            self._hrt_frame_write.body += hrt_data.get_variable('tertiary_variable_classification')
            self._hrt_frame_write.body += hrt_data.get_variable('quaternary_variable_classification')

        elif command == '09':  # Read Device Variables with Status (HART6/7)
            self._hrt_frame_write.body = hrt_data.get_variable('error_code')

        elif command == '0A':  # reservado
            self._hrt_frame_write.body = hrt_data.get_variable('error_code')

        elif command == '0B':  # Read Unique Identifier Associated With Tag (11 dec)
            self._hrt_frame_write.body = "00" if (hrt_frame_read.body == hrt_data.get_variable('tag')) else '01'
            self._hrt_frame_write.body += "FE"
            self._hrt_frame_write.body += hrt_data.get_variable('master_slave | manufacturer_id')
            self._hrt_frame_write.body += hrt_data.get_variable('device_type')
            self._hrt_frame_write.body += hrt_data.get_variable('request_preambles')
            self._hrt_frame_write.body += hrt_data.get_variable('hart_revision')
            self._hrt_frame_write.body += hrt_data.get_variable('software_revision')
            self._hrt_frame_write.body += hrt_data.get_variable('transmitter_revision')
            self._hrt_frame_write.body += hrt_data.get_variable('hardware_revision')
            self._hrt_frame_write.body += hrt_data.get_variable('device_flags')
            self._hrt_frame_write.body += hrt_data.get_variable('device_id')

        elif command == '0C':  # Read Message (12)
            self._hrt_frame_write.body  = hrt_data.get_variable('error_code')
            self._hrt_frame_write.body += hrt_data.get_variable('message')

        elif command == '0D':  # Read Tag, Descriptor, Date (13)
            self._hrt_frame_write.body  = hrt_data.get_variable('error_code')
            self._hrt_frame_write.body += hrt_data.get_variable('tag')
            self._hrt_frame_write.body += hrt_data.get_variable('descriptor')
            self._hrt_frame_write.body += hrt_data.get_variable('date')

        elif command == '0E':  # Read Primary Variable Transducer Information (14)
            self._hrt_frame_write.body  = hrt_data.get_variable('error_code')
            self._hrt_frame_write.body += hrt_data.get_variable('sensor_serial_number')     # 3 bytes
            self._hrt_frame_write.body += hrt_data.get_variable('pv_sensor_units_code')     # 1 byte
            self._hrt_frame_write.body += hrt_data.get_variable('sensor_upper_range_limit') # 4 bytes
            self._hrt_frame_write.body += hrt_data.get_variable('sensor_lower_range_limit') # 4 bytes
            self._hrt_frame_write.body += hrt_data.get_variable('sensor_minimum_span')      # 4 bytes

        elif command == '0F':  # Read Device / PV Output Information (15)
            self._hrt_frame_write.body  = hrt_data.get_variable('error_code')
            self._hrt_frame_write.body += hrt_data.get_variable('pv_alarm_selection')       # 1
            self._hrt_frame_write.body += hrt_data.get_variable('pv_transfer_function')     # 1
            self._hrt_frame_write.body += hrt_data.get_variable('pv_engineering_units')     # 1
            self._hrt_frame_write.body += hrt_data.get_variable('pv_upper_range_value')     # 4
            self._hrt_frame_write.body += hrt_data.get_variable('pv_lower_range_value')     # 4
            self._hrt_frame_write.body += hrt_data.get_variable('pv_damping_seconds')       # 4
            self._hrt_frame_write.body += hrt_data.get_variable('write_protect_status')     # 1
            self._hrt_frame_write.body += hrt_data.get_variable('manufacturer_id')          # 1
            self._hrt_frame_write.body += hrt_data.get_variable('analog_channel_flag')      # 1

        elif command == '10':  # Read Final Assembly Number (16)
            self._hrt_frame_write.body  = hrt_data.get_variable('error_code')
            self._hrt_frame_write.body += hrt_data.get_variable('final_assembly_number')

        elif command == '11':  # Write Message (17)
            # request: 24 bytes (packed ASCII) no body; atualiza banco e ecoa os 24 bytes
            msg_hex = hrt_frame_read.body
            hrt_data.set_variable('message', msg_hex)
            self._hrt_frame_write.body  = hrt_data.get_variable('error_code')
            self._hrt_frame_write.body += msg_hex

        elif command == '12':  # Write Tag, Descriptor, Date (18)
            # request: 6 (tag) + 12 (descriptor) + 3 (date) bytes = 21 bytes = 42 hex chars
            body = hrt_frame_read.body
            tag_hex        = body[:12]
            descriptor_hex = body[12:12+24]
            date_hex       = body[36:42]
            hrt_data.set_variable('tag', tag_hex)
            hrt_data.set_variable('descriptor', descriptor_hex)
            hrt_data.set_variable('date', date_hex)
            self._hrt_frame_write.body  = hrt_data.get_variable('error_code')
            self._hrt_frame_write.body += tag_hex + descriptor_hex + date_hex

        elif command == '13':  # Write Final Assembly Number (19)
            # request: 3 bytes
            fan_hex = hrt_frame_read.body[:6]
            hrt_data.set_variable('final_assembly_number', fan_hex)
            self._hrt_frame_write.body  = hrt_data.get_variable('error_code')
            self._hrt_frame_write.body += fan_hex

        elif command == '21':  # Read Device Variables (33)
            req = hrt_frame_read.body  # hex
            # Suporta tanto formato "XX" (1 var) quanto "NN + NN codes"
            codes = []
            if len(req) == 2:
                codes = [req.upper()]
            else:
                n = int(req[:2], 16)
                codes = [req[i:i+2].upper() for i in range(2, 2+2*n, 2)]

            self._hrt_frame_write.body = hrt_data.get_variable('error_code')
            for code_hex in codes:
                if code_hex == '00':  # PV
                    self._hrt_frame_write.body += hrt_data.get_variable('unit_code')
                    self._hrt_frame_write.body += hrt_data.get_variable('PROCESS_VARIABLE')
                else:
                    self._hrt_frame_write.body += 'FA' + '7FC00000' # fallback genérico: unidade "não usada" + NaN float

        elif command == '26':  # Resetar as Flags de Erro (38)
            self._hrt_frame_write.body  = '02'
            self._hrt_frame_write.body += hrt_data.get_variable('error_code')     # '0000'
            self._hrt_frame_write.body += hrt_data.get_variable('response_code')  # ex. 'E6' p/ este cmd
            self._hrt_frame_write.body += hrt_data.get_variable('device_status')  # ex. '3F'
            self._hrt_frame_write.body += hrt_data.get_variable('comm_status')    # ex. '3F'
            hrt_data.set_variable('config_changed', '00') # efeito do reset no banco, se quiser

        elif command == '28':  # Enter/Exit Fixed Current Mode (40)
            # request: 4 bytes float (mA) em hex -> ecoa nível alcançado
            requested_hex = hrt_frame_read.body
            self._hrt_frame_write.body  = hrt_data.get_variable('error_code')
            self._hrt_frame_write.body += requested_hex

        elif command == '29':  # Perform Self Test (41)
            # formato dos seus traces: response_code + device_status
            self._hrt_frame_write.body  = hrt_data.get_variable('response_code')
            self._hrt_frame_write.body += hrt_data.get_variable('device_status')

        elif command == '2A':  # Perform Device Reset (42)
            self._hrt_frame_write.body = hrt_data.get_variable('error_code')

        elif command == '2D':  # Trim 4 mA (45)
            self._hrt_frame_write.body  = hrt_data.get_variable('response_code')
            self._hrt_frame_write.body += hrt_data.get_variable('device_status')

        elif command == '2E':  # Trim 20 mA (46)
            self._hrt_frame_write.body  = hrt_data.get_variable('response_code')
            self._hrt_frame_write.body += hrt_data.get_variable('device_status')

        elif command == '50':  # Read Dynamic Variable Assignments (80)
            # retorna códigos PV,SV,TV,QV; se não houver no banco, devolve 0xFA (not used)
            self._hrt_frame_write.body  = hrt_data.get_variable('error_code')
            self._hrt_frame_write.body += (hrt_data.get_variable('pv_code') if hrt_data.has('pv_code') else 'FA')
            self._hrt_frame_write.body += (hrt_data.get_variable('sv_code') if hrt_data.has('sv_code') else 'FA')
            self._hrt_frame_write.body += (hrt_data.get_variable('tv_code') if hrt_data.has('tv_code') else 'FA')
            self._hrt_frame_write.body += (hrt_data.get_variable('qv_code') if hrt_data.has('qv_code') else 'FA')

        # ===================== Device-specific abaixo (mantidos conforme seu banco/traces) =====================
        elif command == '82':  # Write Device Variable Trim Point (130)
            self._hrt_frame_write.body = '00000201020101'
        elif command == '84':  # 132
            self._hrt_frame_write.body = '000002012543D2000040A99999'
        elif command == '87':  # Write I/O System Master Mode (135)
            self._hrt_frame_write.body = '00400201'
        elif command == '88':  # 136
            self._hrt_frame_write.body = '700002FFFFFF'
        elif command == '8A':  # 138
            self._hrt_frame_write.body = '000002FF'
        elif command == '8C':  # 140
            self._hrt_frame_write.body = '7000023941AC33E939000000003942480000FFFF3900000000'
        elif command == '98':  # 152
            self._hrt_frame_write.body = ''
        elif command == 'A2':  # 162
            self._hrt_frame_write.body = '00000201'
        elif command == 'A4':  # 164
            self._hrt_frame_write.body = '0000020200'
        elif command == 'A6':  # 166
            self._hrt_frame_write.body = '00000222040000130A270000010B00'
        elif command == 'A8':  # 168
            self._hrt_frame_write.body = '00000201FF'
        elif command == 'AD':  # 173
            self._hrt_frame_write.body = '0000025454333031313131302D425549314C335030543459'
        elif command == 'B9':  # 185
            self._hrt_frame_write.body = '004002'
        elif command == 'BB':  # 187
            self._hrt_frame_write.body = '000002FF'
        elif command == 'C6':  # 198
            self._hrt_frame_write.body = '00000242480000'
        elif command == 'DF':  # 223
            self._hrt_frame_write.body = '00000242C800003B801132B51B057FAC932D1D'


# Example usage (assuming you have instances of HrtTransmitter and HrtFrame)
if __name__ == "__main__":
    hrt_Data = HrtData('TIT100','dados.xlsx')
    hrt_frame_read = HrtFrame()
    hrt_frame_read.command = '00'
    hrt_frame_read.address_type = False

    hrt_transmitter = HrtTransmitter(hrt_Data, hrt_frame_read)
    print(hrt_transmitter.frame)
