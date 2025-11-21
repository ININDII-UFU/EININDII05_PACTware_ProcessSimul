import sqlite3
import pandas as pd
from typing import Dict, Tuple, Union

# ['NAME', 'BYTE_SIZE', 'TYPE', 'MB_POINT', 'ADDRESS', 'CLP100']
# MB_POINT = di, co, hr, ir
mb_banco: Dict[str, Tuple[str, str, str, str]] = {
    
    'FIT100CA'  : (4, 'UNSIGNED', 'ir', '01','@int(65535*HART.FIT100CA.percent_of_range)'),   
    'FIT100AR'  : (4, 'UNSIGNED', 'ir', '02','@int(65535*HART.FIT100AR.percent_of_range)'),        
    'TIT100'    : (4, 'UNSIGNED', 'ir', '03','@int(65535*HART.TIT100.percent_of_range)'),
    'W_FIT100V' : (4, 'UNSIGNED', 'ir', '04','3F000000'), 
    'PIT100V'   : (4, 'UNSIGNED', 'ir', '05','@int(65535*HART.PIT100V.percent_of_range)'),
    'LIT100'    : (4, 'UNSIGNED', 'ir', '06','@int(65535*HART.LIT100.percent_of_range)'),      
    'W_PIT100A' : (4, 'UNSIGNED', 'ir', '07','3F000000'),      
    'FIT100A'   : (4, 'UNSIGNED', 'ir', '08','@int(65535*HART.FIT100A.percent_of_range)'),
    'W_FV100CA' : (4, 'UNSIGNED', 'ir', '09','3F000000'),         
    'W_FV100AR' : (4, 'UNSIGNED', 'ir', '10','3F000000'),   
    'W_FV100A'  : (4, 'UNSIGNED', 'ir', '11','3F000000'), 
    'W_AUX'     : (4, 'UNSIGNED', 'ir', '12','3F000000'),        
    
    'FV100CA' : (4, 'UNSIGNED', 'hr', '01', '3F000000'),   
    'FV100AR' : (4, 'UNSIGNED', 'hr', '02', '3F000000'), 
    'FIT100V' : (4, 'UNSIGNED', 'hr', '03', '3F000000'),
    'PIT100A' : (4, 'UNSIGNED', 'hr', '04', '3F000000'),    
    'FV100A'  : (4, 'UNSIGNED', 'hr', '05', '3F000000'), 
    
    'AM_FV100CA' : (1, 'BOOL', 'co', '01','0'),
    'AM_FV100AR' : (1, 'BOOL', 'co', '02','0'),        
    'AM_FV100A'  : (1, 'BOOL', 'co', '03','0'),  
}
# ['NAME', 'BYTE_SIZE', 'TYPE', 'FV100CA', 'FIT100CA', 'FV100AR', 'FIT100AR', 'TIT100', 'FIT100V', 'PIT100V', 'LIT100', 'PIT100A', 'FV100A', 'FIT100A']
hrt_banco: Dict[str, Tuple[Union[int, float], str, str]] = {
    'frame_type': (1, 'UNSIGNED', '06', '06', '06', '06', '06', '06', '06', '06', '06', '06', '06'),
    'address_type': (1, 'UNSIGNED', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00'),
    'error_code': (2, 'ENUM00', '0000', '0000', '0000', '0000', '0000', '0000', '0000', '0000', '0000', '0000', '0000'),
    'response_code': (1, 'ENUM27', '30', '30', '30', '30', '30', '30', '30', '30', '30', '30', '30'),
    'device_status': (1, 'BIT_ENUM02', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00'),
    'comm_status': (1, 'BIT_ENUM03', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00'),
    'master_address': (1, 'BIT_ENUM01', '80', '80', '80', '80', '80', '80', '80', '80', '80', '80', '80'),
    'manufacturer_id': (1, 'ENUM08', '3E', '3E', '3E', '3E', '3E', '3E', '3E', '3E', '3E', '3E', '3E'),
    'device_type': (1, 'ENUM01', '02', '02', '02', '02', '02', '02', '02', '02', '02', '02', '02'),
    'request_preambles': (1, 'UNSIGNED', '05', '05', '05', '05', '05', '05', '05', '05', '05', '05', '05'),
    'hart_revision': (1, 'UNSIGNED', '05', '05', '05', '05', '05', '05', '05', '05', '05', '05', '05'),
    'transmitter_revision': (1, 'UNSIGNED', '30', '30', '30', '30', '30', '30', '30', '30', '30', '30', '30'),
    'software_revision': (1, 'UNSIGNED', '04', '04', '04', '04', '04', '04', '04', '04', '04', '04', '04'),
    'hardware_revision': (1, 'UNSIGNED', '01', '01', '01', '01', '01', '01', '01', '01', '01', '01', '01'),
    'device_flags': (1, 'BIT_ENUM04', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00'),
    'device_id': (5, 'UNSIGNED', '1F00000010', '1F00000010', '1F00000010', '1F00000010', '1F00000010', '1F00000010', '1F00000010', '1F00000010', '1F00000010', '1F00000010', '1F00000010'),
    'polling_address': (1, 'UNSIGNED', '80', '80', '80', '80', '80', '80', '80', '80', '80', '80', '80'),
    'tag': (8,'PACKED_ASCII','514CF0C60820','514CF0C60820','514CF0C60820','514CF0C60820','514CF0C60820','514CF0C60820','514CF0C60820','514CF0C60820','514CF0C60820','514CF0C60820','514CF0C60820'),  # TT301
    'message': (32,'PACKED_ASCII',
        '34510910F4A010581414D405481515481820820820820820', # MEDIDOR DE TEMPERATURA
        '34510910F4A010581414D405481515481820820820820820', # MEDIDOR DE TEMPERATURA
        '34510910F4A010581414D405481515481820820820820820', # MEDIDOR DE TEMPERATURA
        '34510910F4A010581414D405481515481820820820820820', # MEDIDOR DE TEMPERATURA
        '34510910F4A010581414D405481515481820820820820820', # MEDIDOR DE TEMPERATURA
        '34510910F4A010581414D405481515481820820820820820', # MEDIDOR DE TEMPERATURA
        '34510910F4A010581414D405481515481820820820820820', # MEDIDOR DE TEMPERATURA
        '34510910F4A010581414D405481515481820820820820820', # MEDIDOR DE TEMPERATURA
        '34510910F4A010581414D405481515481820820820820820', # MEDIDOR DE TEMPERATURA
        '34510910F4A010581414D405481515481820820820820820', # MEDIDOR DE TEMPERATURA
        '34510910F4A010581414D405481515481820820820820820', # MEDIDOR DE TEMPERATURA
    ),  
    'descriptor': (16,'PACKED_ASCII','505350152054552060820820','505350152054552060820820','505350152054552060820820','505350152054552060820820','505350152054552060820820','505350152054552060820820','505350152054552060820820','505350152054552060820820','505350152054552060820820','505350152054552060820820','505350152054552060820820'),  # TEMPERATURA
    'date': (3, 'DATE', '130879', '130879', '130879', '130879', '130879', '130879', '130879', '130879', '130879', '130879', '130879'),  # 19/08/2021
    'upper_range_value': (4, 'FLOAT', '42C80000', '3CB9F559', '42C80000', '3E199999', '447A0000', '3EB33333', '41200000', '42C80000', '44160000', '42C80000', '3F0CCCCC'),  # Varia
    'lower_range_value': (4, 'FLOAT', '00000000', '3727C5AC', '00000000', '3727C5AC', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000'),  # 0
    'PROCESS_VARIABLE': (4,'FLOAT',
        '@HART.FV100CA.percent_of_range * (HART.FV100CA.upper_range_value - HART.FV100CA.lower_range_value) + HART.FV100CA.lower_range_value',
        '@HART.FIT100CA.percent_of_range * (HART.FIT100CA.upper_range_value - HART.FIT100CA.lower_range_value) + HART.FIT100CA.lower_range_value',
        '@HART.FV100AR.percent_of_range * (HART.FV100AR.upper_range_value - HART.FV100AR.lower_range_value) + HART.FV100AR.lower_range_value',
        '@HART.FIT100AR.percent_of_range * (HART.FIT100AR.upper_range_value - HART.FIT100AR.lower_range_value) + HART.FIT100AR.lower_range_value',
        '@HART.TIT100.percent_of_range * (HART.TIT100.upper_range_value - HART.TIT100.lower_range_value) + HART.TIT100.lower_range_value',
        '@HART.FIT100V.percent_of_range * (HART.FIT100V.upper_range_value - HART.FIT100V.lower_range_value) + HART.FIT100V.lower_range_value',
        '@HART.PIT100V.percent_of_range * (HART.PIT100V.upper_range_value - HART.PIT100V.lower_range_value) + HART.PIT100V.lower_range_value',
        '@HART.LIT100.percent_of_range * (HART.LIT100.upper_range_value - HART.LIT100.lower_range_value) + HART.LIT100.lower_range_value',
        '@HART.PIT100A.percent_of_range * (HART.PIT100A.upper_range_value - HART.PIT100A.lower_range_value) + HART.PIT100A.lower_range_value',
        '@HART.FV100A.percent_of_range * (HART.FV100A.upper_range_value - HART.FV100A.lower_range_value) + HART.FV100A.lower_range_value',
        '@HART.FIT100A.percent_of_range * (HART.FIT100A.upper_range_value - HART.FIT100A.lower_range_value) + HART.FIT100A.lower_range_value'
    ),  # 50
    'percent_of_range': (4, 'FLOAT', 
        '@(MODBUS.CLP100.FV100CA / 65535)', # FV100CA -> 0@100% esta em 50%
        '$[1.0],[3.0 1.0], 1,@HART.FV100CA.percent_of_range', # FIT100CA  -> 0.00001@0.0227kg/s
        '@MODBUS.CLP100.FV100AR/65535', # FV100AR -> 0@100% esta em 50%
        '$[1.0],[1.5 1.0], 0.5,@HART.FV100AR.percent_of_range', #FIT100AR -> 0.00001@0.15kg/s        
        '$[1.0],[5.0 1.0], 1.2,@exp(-0.05*((15.0*HART.FIT100AR.percent_of_range/HART.FIT100CA.percent_of_range)-15.0)**2.0)', # TIT100 -> 0@1000ºC
        '@MODBUS.CLP100.FIT100V/65535', # FIT100V -> 0@0.35kg/s esta em 0.175 (50%)
        '$[1.0],[4.0 0.000001], 0.8,@HART.TIT100.percent_of_range - 0.5*HART.FIT100V.percent_of_range', # PIT100V -> 0@10Bar
        '$[1.0],[4.0 0.000001], 0.8,@HART.FIT100A.percent_of_range - HART.FIT100V.percent_of_range', # LIT100 -> 0@100%
        '@MODBUS.CLP100.PIT100A/65535', # PIT100A -> 0@600kPa esta em 400 (66,66%)  
        '@MODBUS.CLP100.FV100A/65535', # FV100A -> 0@100% esta em 50% 
        '$[1.0],[6.0 1.0], 2,@math.sqrt(HART.PIT100A.percent_of_range/0.6666)*HART.FV100A.percent_of_range' # FIT100A -> 0@0.55kg/s
    ),
    'loop_current_mode': (1, 'ENUM00', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00'),
    'loop_current': (4, 'FLOAT', 
        '@(HART.FV100CA.percent_of_range * 0.16) + 4',
        '@(HART.FIT100CA.percent_of_range * 0.16) + 4',
        '@(HART.FV100AR.percent_of_range * 0.16) + 4',
        '@(HART.FIT100AR.percent_of_range * 0.16) + 4',
        '@(HART.TIT100.percent_of_range * 0.16) + 4',
        '@(HART.FIT100V.percent_of_range * 0.16) + 4',
        '@(HART.PIT100V.percent_of_range * 0.16) + 4',
        '@(HART.LIT100.percent_of_range * 0.16) + 4',
        '@(HART.PIT100A.percent_of_range * 0.16) + 4',
        '@(HART.FV100A.percent_of_range * 0.16) + 4',
        '@(HART.FIT100A.percent_of_range * 0.16) + 4'
    ),
    'write_protect': (1, 'ENUM00', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00'),
    'private_label_distributor': (1, 'ENUM00', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00'),
    'final_assembly_number': (3, 'UNSIGNED', '00FBC6', '00FBC6', '00FBC6', '00FBC6', '00FBC6', '00FBC6', '00FBC6', '00FBC6', '00FBC6', '00FBC6', '00FBC6'),
    'physical_signaling_code': (1, 'ENUM10', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00'),  # (Bell 202 Current)
    'units_code': (1, 'ENUM02', '20', '20', '20', '20', '20', '20', '20', '20', '20', '20', '20'),  # (32 - Degrees Celsius)
    'transfer_function_code': (1, 'ENUM03', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00'),  # (0 - Linear)
    'alarm_selection_code': (1, 'ENUM06', 'FB', 'FB', 'FB', 'FB', 'FB', 'FB', 'FB', 'FB', 'FB', 'FB', 'FB'),  # (None)
    'material_code': (1, 'ENUM04', '02', '02', '02', '02', '02', '02', '02', '02', '02', '02', '02'),  # (Stainless Steel 316)
    'write_protect_code': (1, 'ENUM07', 'FB', 'FB', 'FB', 'FB', 'FB', 'FB', 'FB', 'FB', 'FB', 'FB', 'FB'),  # (None)
    'burst_mode_control_code': (1, 'ENUM09', 'FB', 'FB', 'FB', 'FB', 'FB', 'FB', 'FB', 'FB', 'FB', 'FB', 'FB'),  # (None)
    'flag_assignment': (1, 'ENUM11', '01', '01', '01', '01', '01', '01', '01', '01', '01', '01', '01'),  # (Multi-Sensor Field Device)
    'operating_mode_code': (1, 'ENUM14', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00'),  # (None)
    'analog_output_numbers_code': (1, 'ENUM15', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00'),  # (Analog Channel 0)
    'ma_analog_output_1_value': (4, 'FLOAT', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000'),
    'sensor1_serial_number': (3, 'UNSIGNED', '000000', '000000', '000000', '000000', '000000', '000000', '000000', '000000', '000000', '000000', '000000'),
    'SETPOINT': (4, 'FLOAT', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000'),
    'MANIPULATED_VARIABLE': (4, 'FLOAT', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00'),
    'ERROR_PERCENT_RANGE': (4, 'FLOAT', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00'),
    'PROPORTIONAL_GAIN': (4, 'FLOAT', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000'),
    'INTEGRAL_TIME': (4, 'FLOAT', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000'),
    'DERIVATIVE_TIME': (4, 'FLOAT', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000'),
    'MV_HIGH_LIMIT': (4, 'FLOAT', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000'),
    'MV_LOW_LIMIT': (4, 'FLOAT', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000'),
    'MV_ROC_LIMIT': (4, 'FLOAT', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000'),
    'POWER_UP_SETPOINT_PERCENT_RANGE': (4, 'FLOAT', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000'),
    'POWER_UP_OUTPUT': (4, 'FLOAT', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000'),
    'set_point_time': (4, 'FLOAT', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000'),
    'range_units': (1, 'UNSIGNED', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00', '00'),
    'output_variable': (4, 'FLOAT', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000'),
    'mv_ohms': (4, 'FLOAT', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000'),
    'upper_cal_point_value': (4, 'FLOAT', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000'),
    'lower_cal_point_value': (4, 'FLOAT', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000', '00000000'),
}


# Exemplo de uso
if __name__ == '__main__':
    # Colunas adicionais
    extra_columns = ['LI100', 'FI100V', 'FI100A', 'FV100A', 'PI100', 'TI100']

    # Converter o dicionário em DataFrame com colunas repetidas
    rows = []
    for key, val in hrt_banco.items():
        row = [key, val[0], val[1]] + [val[2]] * len(extra_columns)
        rows.append(row)

    columns = ['NAME', 'BYTE_SIZE', 'TYPE'] + extra_columns

    df = pd.DataFrame(rows, columns=columns)

    # Conectar (ou criar) o banco SQLite
    with sqlite3.connect('db/banco.db') as conn:
        # Salvar o DataFrame em SQLite (replace substitui se a tabela já existir)
        df.to_sql('hrt_tabela', conn, if_exists='replace', index=False)

    print('Dados salvos com sucesso na tabela hrt_settings.')