from datetime import date, time, datetime
try:
    from hrt.hrt_enum import hrt_enum
    from hrt.hrt_bitenum import hrt_bitEnum
except Exception:
    from hrt_enum import hrt_enum
    from hrt_bitenum import hrt_bitEnum    
from typing import Union
import math
import unittest
import re

def format_number(num):
    if abs(num) >= 0.0001:  # Se for maior ou igual a 0.0001, formata normal
        return f"{num:.4f}"
    else:  # Se for menor que 0.0001, usa notação científica
        return f"{num:.2e}"
    
def str2type(value: str, type: str):
    if value != None and (type.find('UNSIGNED') != -1 or type.find('INTEGER') != -1):
        return int(value)
    elif value != None and type.find('FLOAT') != -1:
        return float(value)
    elif value != None and type.find('DATE') != -1:
        return value
    elif value != None and type.find('TIME') != -1:
        return value
    else:
        return None
    
def type2str(value: str, type: str):
    if value != None and (type.find('UNSIGNED') != -1 or type.find('INTEGER') != -1):
        return str(value)
    elif value != None and type.find('FLOAT') != -1:
        return format_number(value)
    elif value != None and type.find('DATE') != -1:
        return value
    elif value != None and type.find('TIME') != -1:
        return value
    else:
        return None
###################################################################################
###################################################################################
# Funções auxiliares para manipulação de bits
###################################################################################
###################################################################################
def get_bits(value: int, start: int, count: int) -> int:
    mask = (1 << count) - 1
    return (value >> start) & mask

def set_bits(value: int, start: int, count: int, new_value: int) -> int:
    mask = ((1 << count) - 1) << start
    value &= ~mask
    value |= (new_value << start) & mask
    return value

def split_by_length(s: str, n: int) -> list:
    return [s[i:i+n] for i in range(0, len(s), n)]

def to_signed_16(value):
    value &= 0xFFFF  # Garante que o valor esteja dentro de 16 bits
    if value >= 0x8000:  # Se o bit mais significativo estiver definido, é um número negativo
        value -= 0x10000
    return value
###################################################################################
###################################################################################
# Funções de conversão de HEX para os tipos
###################################################################################
###################################################################################
def _hrt_type_hex2_uint(str_uint: str) -> int:
    if not str_uint:
        raise ValueError("Função _hrt_type_hex2_uint recebeu string vazia")
    if len(str_uint) > 4:
        raise ValueError("Função _hrt_type_hex2_uint recebeu hex com mais de 4 caracteres")
    return int(str_uint, 16)

def _hrt_type_hex2_int(str_int: str) -> int:
    if not str_int:
        raise ValueError("Função _hrt_type_hex2_int recebeu string vazia")
    if len(str_int) > 4:
        raise ValueError("Função _hrt_type_hex2_int recebeu hex com mais de 4 caracteres")
    val = int(str_int, 16)
    return to_signed_16(val)

def _hrt_type_hex2_sreal(str_float: str) -> float:
    number = int(str_float, 16)
    s = get_bits(number, 31, 1)
    e = get_bits(number, 23, 8)
    f = get_bits(number, 0, 23) / 8388608.0
    return ((-1) ** s) * (2 ** (e - 127)) * (1 + f)

def _hrt_type_hex2_pascii(valor: str) -> str:
    # Converte o valor hexadecimal para inteiro e depois para uma string binária de múltiplos de 6 bits
    binary_str = bin(int(valor, 16))[2:]
    binary_str = binary_str.zfill(6*(int(len(binary_str) / 6)+(1 if len(binary_str) % 6 > 0 else 0)))  # Garante que o binário tenha o tamanho correto
    numbers = split_by_length(binary_str, 6)
    # Mapeia os valores binários para caracteres ASCII ajustando o bit de posição 6
    ascii_values = []
    for e in numbers:
        resp = int(e, 2)
        if get_bits(resp, 5, 1) == 1:
            resp = set_bits(resp, 6, 1, 0)
        else:
            resp = set_bits(resp, 6, 1, 1)
        ascii_values.append(resp)
    # Decodifica os valores ASCII para string
    return ''.join(map(chr, ascii_values))

def _hrt_type_hex2_date(valor: str) -> date:
    parts = split_by_length(valor, 2)
    aux = [int(p, 16) for p in parts]
    if len(aux) < 3:
        raise ValueError("Formato do HEX para data incorreto")
    return f"{aux[0]:02}/{aux[1]:02}/{1900+aux[2]:04}"

def _hrt_type_hex2_time(valor: str) -> datetime:
    partes = split_by_length(valor, 2)
    if len(partes) != 4:
        raise ValueError("Formato do HEX para tempo incorreto")
    valores = [int(x, 16) for x in partes]
    total_ms = valores[0] * 524288 + valores[1] * 2048 + valores[2] * 8 + valores[2] * 0.03125
    hours = int(total_ms // 3600000)
    minutes = int((total_ms % 3600000) // 60000)
    seconds = int((total_ms % 60000) // 1000)
    milliseconds = int(total_ms % 1000)
    return datetime(1900, 1, 1, hours, minutes, seconds, milliseconds * 1000)

def encontrar_valor_no_dicionario(dicionario, valor):
    """
    Varre um dicionário e verifica se a chave é igual ao valor ou,
    caso a chave contenha um intervalo (A-B), verifica se o valor está na faixa.
    
    :param dicionario: Dicionário onde as chaves podem ser valores únicos ou intervalos (ex: "F0-F9")
    :param valor: O valor hexadecimal a ser buscado (ex: "F1")
    :return: O valor correspondente à chave encontrada, ou None se não encontrar.
    """
    for chave, v in dicionario.items():
        if "-" in chave:  # Se a chave for um intervalo (ex: "F0-F9")
            inicio, fim = chave.split("-")  # Divide o intervalo
            if int(inicio, 16) <= int(valor, 16) <= int(fim, 16):  # Converte para int e verifica a faixa
                return v  # Retorna o valor correspondente
        elif int(chave, 16) == int(valor, 16):  # Se for uma correspondência exata
            return v
    
    return None  # Se não encontrar, retorna None

# Funções principais
def hrt_type_hex_to(valor: str, type_str: str):
    t = type_str.upper()
    if t.find('UNSIGNED') != -1:
        return int(''.join(str(_hrt_type_hex2_uint(e)) for e in split_by_length(valor, 2)))
    elif t.find('FLOAT') != -1:
        return _hrt_type_hex2_sreal(valor)
    elif t.find("ENUM") != -1:
        return encontrar_valor_no_dicionario(hrt_enum[int(t[-2:])],valor)
    elif t.find("BIT_ENUM") != -1:
        return hrt_bitEnum[int(t[-2:])][int(valor,16)]   
    elif t.find('DATE') != -1:
        return _hrt_type_hex2_date(valor)
    elif t.find('TIME') != -1:
        return _hrt_type_hex2_time(valor)
    elif t.find('INTEGER') != -1:
        return _hrt_type_hex2_int(valor)
    elif t.find("PACKED") != -1:
        return _hrt_type_hex2_pascii(valor)
    elif t.find("BOOL") != -1:
        return True if valor == 'True' else False   
    else:
        return "INVALID TYPE"
###################################################################################
###################################################################################
# Funções de conversão dos tipos para HEX
###################################################################################
###################################################################################
def _hrt_type_uint2_hex(u_int: int, byte_size: int) -> str:
    if u_int > 65535:
        raise ValueError("Valor acima do limite máximo")
    return format(u_int, f'0{2*byte_size}X')

def _hrt_type_int2_hex(i_val: int, byte_size: int) -> str:
    if not (-32768 <= i_val <= 65535):
        raise ValueError("Valor fora do intervalo permitido")
    if i_val < 0:
        i_val = (i_val + (1 << 16)) % (1 << 16)
    return format(i_val, f'0{2*byte_size}X')

def _hrt_type_sreal2_hex(valor_float: float, byte_size: int) -> str:
    bits_array = 0
    if valor_float == 0.0:
        return '0'.zfill(2*byte_size)
    if valor_float < 0:
        bits_array = set_bits(bits_array, 31, 1, 1)
        valor_float = -valor_float
    e = 127 + math.floor(math.log(valor_float, 2))
    bits_array = set_bits(bits_array, 23, 8, e)
    f = math.floor(((valor_float / (2 ** (e - 127))) - 1) * 8388608)
    bits_array = set_bits(bits_array, 0, 23, f)
    return format(bits_array, f'0{2*byte_size}X').upper()

def _hrt_type_pascii2_hex(valor: str, byte_size: int) -> str:
    """
    Converte string para HART PACKED ASCII (6 bits/char) em HEX com exatamente `byte_size` bytes.

    Regras implementadas (conforme pedido):
      - a..z -> A..Z
      - fora de 0x20..0x5F -> ' '
      - se faltar: completa com espaço à direita (sempre)
      - se sobrar: ERRO (não corta)
      - SEMPRE retorna exatamente `byte_size` bytes:
          * se 8*byte_size não for múltiplo de 6, faz padding de bits 0 no final
            (isso é necessário para fechar o último byte).
    """
    if byte_size <= 0:
        return ""

    s = (valor or "")

    # Quantos caracteres de 6 bits cabem em byte_size bytes?
    # Precisamos de n_chars tal que n_chars*6 <= byte_size*8 (cabe em bits).
    n_chars = (byte_size * 8) // 6  # floor

    # Se sobrar: erro (conforme pedido)
    if len(s) > n_chars:
        raise ValueError(
            f"Texto maior que o máximo permitido para PACKED ASCII em {byte_size} bytes. "
            f"len={len(s)} > max_chars={n_chars}."
        )

    # Se faltar: completa com espaços
    if len(s) < n_chars:
        s = s.ljust(n_chars, " ")

    # Normalização e conversão para 6 bits
    sixbit_vals = []
    for ch in s:
        if "a" <= ch <= "z":
            ch = ch.upper()

        code = ord(ch)
        if not (0x20 <= code <= 0x5F):
            code = 0x20  # espaço

        sixbit_vals.append(code & 0x3F)

    # Empacotar em fluxo de bits (MSB-first)
    out = bytearray()
    acc = 0
    acc_bits = 0

    for v in sixbit_vals:
        acc = (acc << 6) | v
        acc_bits += 6

        while acc_bits >= 8:
            shift = acc_bits - 8
            out.append((acc >> shift) & 0xFF)
            acc_bits -= 8
            acc &= (1 << acc_bits) - 1 if acc_bits > 0 else 0

    # Aqui pode sobrar de 1..7 bits se byte_size*8 não for múltiplo de 6.
    # Precisamos produzir exatamente byte_size bytes -> completar o último byte com zeros.
    if acc_bits > 0:
        out.append((acc << (8 - acc_bits)) & 0xFF)
        acc_bits = 0

    # Agora garante exatamente byte_size bytes (padding com 0x00 se ainda faltar 1 byte por arredondamento)
    if len(out) < byte_size:
        out.extend(b"\x00" * (byte_size - len(out)))
    elif len(out) > byte_size:
        # Isso não deveria acontecer com n_chars calculado via floor, mas fica a segurança
        out = out[:byte_size]

    return out.hex().upper()

def _hrt_type_date2_hex(valor: str, byte_size: int) -> str:
    aux = valor.split("/")
    if len(aux) < 3:
        raise ValueError("Formato de DATE para hex incorreto")
    return f"{int(aux[0]):02X}{int(aux[1]):02X}{(int(aux[2]) - 1900):02X}".zfill(2*byte_size)

def _hrt_type_time2_hex(valor: datetime, byte_size: int) -> str:
    total_ms = valor.hour * 3600000 + valor.minute * 60000 + valor.second * 1000 + int(valor.microsecond / 1000)
    aux = int(total_ms / 0.03125)
    return f"{(aux >> 24) & 0xFF:02X}{(aux >> 16) & 0xFF:02X}{(aux >> 8) & 0xFF:02X}{aux & 0xFF:02X}".zfill(2*byte_size)

def hrt_type_hex_from(valor, type_str: str, byte_size: int) -> str:
    t = type_str.upper()
    if t.find('UNSIGNED') != -1:
        # try:
            return _hrt_type_uint2_hex(int(valor), byte_size)
        # except Exception as e:
        #     return "00"
    elif t.find('FLOAT') != -1:
        return _hrt_type_sreal2_hex(float(valor), byte_size)
    elif t.find("ENUM") != -1:
        return f'{next((k[:2] for k, v in hrt_enum[int(t[-2:])].items() if v == valor), None)}'.zfill(2*byte_size)        
    elif "BIT_ENUM" in t:
        # Extrai o índice do tipo, aceitando qualquer quantidade de dígitos no final (ex.: BIT_ENUM0, BIT_ENUM05, BIT_ENUM99)
        m = re.search(r'(\d+)$', t)
        if not m:
            return None
        enum_idx = int(m.group(1))

        # Busca o dicionário de mapeamento para este BIT_ENUM
        d = hrt_bitEnum.get(enum_idx)
        if not d:
            return None

        # valor pode vir como "A|B|C" (rótulos), número (int/str) ou string hex ("01", "00FF", "0x1F" ou "01 02")
        if isinstance(valor, str) and "|" in valor:
            # Mapa nome -> código inteiro
            name2code = {}
            for code_key, name in d.items():
                s = str(code_key).strip()
                try:
                    # base=0 aceita "0x..", "0b..", decimal etc.
                    c = int(s, 0)
                except Exception:
                    # tenta como hex puro
                    try:
                        c = int(s, 16)
                    except Exception:
                        continue
                name2code[name] = c

            mask = 0
            for part in (s.strip() for s in valor.split("|") if s.strip()):
                if part in name2code:
                    mask |= name2code[part]
                else:
                    # resiliente: ignora rótulos desconhecidos
                    pass
            return f"{mask:0{byte_size*2}X}"

        if isinstance(valor, str):
            v = valor.strip()

            # "0x.." (qualquer caixa)
            if v.lower().startswith("0x"):
                try:
                    mask = int(v, 16)
                    return f"{mask:0{byte_size*2}X}"
                except Exception:
                    return None

            # HEX com espaços "01 02 0A"
            if re.fullmatch(r"[0-9A-Fa-f ]+", v):
                try:
                    mask = int(v.replace(" ", ""), 16)
                    return f"{mask:0{byte_size*2}X}"
                except Exception:
                    return None

            # Decimal em string
            try:
                mask = int(v, 10)
                return f"{mask:0{byte_size*2}X}"
            except Exception:
                return None

        # Caso geral: veio como inteiro
        try:
            mask = int(valor)
            return f"{mask:0{byte_size*2}X}"
        except Exception:
            return None
    elif t.find('DATE') != -1:
        return _hrt_type_date2_hex(valor, byte_size)
    elif t.find('TIME') != -1:
        return _hrt_type_time2_hex(valor, byte_size)
    elif t.find('INTEGER') != -1:
        return _hrt_type_int2_hex(int(valor), byte_size)    
    elif t.find('PACKED') != -1:
        return _hrt_type_pascii2_hex(valor, byte_size)  
    elif t.find('BOOL') != -1:
        return str(valor)
    else:
        return "INVALID TYPE"
    

class TestHrtType(unittest.TestCase):
    # # Teste para Int
    # def test_valor_hex_vazio(self):
    #     with self.assertRaises(ValueError):
    #         hrt_type_hex_to('', 'Int')

    # def test_valor_hex_maior_4_caracteres(self):
    #     with self.assertRaises(ValueError):
    #         hrt_type_hex_to('00FFF', 'Int')

    # def test_valor_hex_caracteres_invalidos(self):
    #     with self.assertRaises(ValueError):
    #         hrt_type_hex_to('AZF', 'Int')

    # def test_valor_hex_00FF_para_255(self):
    #     self.assertEqual(hrt_type_hex_to('00FF', 'Int'), 255)

    # def test_valor_hex_80FF_para_negativo_32513(self):
    #     self.assertEqual(hrt_type_hex_to('80FF', 'Int'), -32513)

    # def test_valor_hex_0BCD_para_3021(self):
    #     self.assertEqual(hrt_type_hex_to('0BCD', 'Int'), 3021)
        
    # def test_valor_negativo_32513_para_hex(self):
    #     resultado = _hrt_type_int2_hex(-32513)
    #     self.assertEqual(resultado, '80FF')

    # def test_valor_int_maior_65535_erro(self):
    #     with self.assertRaises(ValueError):
    #         _hrt_type_int2_hex(65536)       
    
    # # Teste para data
    # def test_valor_date_para_hex_12032024(self):
    #     valor_date = datetime(2024, 3, 12)
    #     resultado = hrt_type_hex_from(valor_date, 'Date', 3)
    #     self.assertEqual(resultado, '0C037C')

    # def test_valor_hex_para_date_12032024(self):
    #     valor_hex = '0C037C'
    #     resultado = hrt_type_hex_to(valor_hex, 'Date')
    #     self.assertEqual(resultado, datetime(2024, 3, 12, 0, 0).date())     
    
    # Teste para PASCII
    def test_transmissor_para_hex(self):
        valor = 'TRANSMISSOR DE TEMPERATURA'
        self.assertEqual(hrt_type_hex_from(valor, 'PACKED', 20), '051204E4CD2534CF4A010581414D405481515481')
     
    def test_transmissor_para_hex(self):
        valor_hex = '051204E4CD2534CF4A010581414D405481515481' 
        self.assertEqual(hrt_type_hex_to(valor_hex, 'PACKED'), 'TRANSMISSOR DE TEMPERATURA')
                    
    def test_abacate_para_hex(self):
        valor = 'ABACATE'
        self.assertEqual(hrt_type_hex_from(valor, 'PACKED', 6), '0010810C1505')

    def test_hex_para_abacate(self):
        valor_hex = '0010810C1505'
        self.assertEqual(hrt_type_hex_to(valor_hex, 'PACKED'), 'ABACATE')

    # # Teste para SREAL
    # def test_double_para_hex(self):
    #     valor = 1.4861602783203125
    #     self.assertEqual(hrt_type_hex_from(valor, 'SReal', 4), '3fbe3a80')

    # def test_hex_para_double(self):
    #     valor_hex = '3FBE3A80'
    #     self.assertAlmostEqual(hrt_type_hex_to(valor_hex, 'SReal'), 1.4861602783203125)

    # # Teste para TIME
    # def test_datetime_para_hex(self):
    #     valor = datetime.strptime('1900-01-01 00:23:18.526', '%Y-%m-%d %H:%M:%S.%f')
    #     self.assertEqual(hrt_type_hex_from(valor, 'Time', 4), '02AADFC0')

    # def test_hex_para_datetime(self):
    #     valor_esperado = datetime.strptime('1900-01-01 00:23:18.526', '%Y-%m-%d %H:%M:%S.%f')
    #     self.assertEqual(hrt_type_hex_to('02AADFC0', 'Time'), valor_esperado)

    # # Teste para UINT
    # def test_int_maior_65535_deve_erro(self):
    #     valor_int = 65536
    #     with self.assertRaises(ValueError):
    #         hrt_type_hex_from(valor_int, 'UInt', 1)

    # def test_int_para_hex(self):
    #     valor_int = 255
    #     self.assertEqual(hrt_type_hex_from(valor_int, 'UInt', 2), '00FF')

    # def test_hex_vazio_deve_erro(self):
    #     valor_hex = ''
    #     with self.assertRaises(ValueError):
    #         hrt_type_hex_to(valor_hex, 'UInt')

    # def test_hex_maior_4_caracteres_deve_erro(self):
    #     valor_hex = '00FFF'
    #     with self.assertRaises(ValueError):
    #         hrt_type_hex_to(valor_hex, 'UInt')

    # def test_hex_caracteres_invalidos_deve_erro(self):
    #     valor_hex = 'AZF'
    #     with self.assertRaises(ValueError):
    #         hrt_type_hex_to(valor_hex, 'UInt')

    # def test_hex_para_int(self):
    #     valor_hex = '00FF'
    #     self.assertEqual(hrt_type_hex_to(valor_hex, 'UInt'), 255)

    # def test_hex_abcd_para_int(self):
    #     valor_hex = 'ABCD'
    #     self.assertEqual(hrt_type_hex_to(valor_hex, 'UInt'), 43981)    

if __name__ == '__main__':
    unittest.main()
    def processar_valor(valor):
        return ''.join(map(_hrt_type_hex2_uint, split_by_length(valor, 2)))

    # Exemplo de uso:
    valor = "1A2B3C4D"
    resultado = processar_valor(valor)
    print(resultado)
