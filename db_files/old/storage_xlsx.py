from functools import reduce
from react.qt_compat import Signal, QObject
import pandas as pd
import operator

class Storage(QObject):
    data_updated = Signal()  # 🔥 Declarando o sinal corretamente
    
    def __init__(self, caminho_excel: str):
        super().__init__()  # 🔥 Inicializa QObject explicitamente        
        self.caminho_excel = caminho_excel
        try:
            self.df = pd.read_excel(self.caminho_excel, index_col='NAME')
        except FileNotFoundError:
            # Se o arquivo não existir, cria uma tabela vazia
            self.df = pd.DataFrame(columns=["BYTE_SIZE", "TYPE", "TIT100"])
            self.saveAllData()
        
    def saveAllData(self):
        """Escreve os dados de volta ao arquivo Excel."""
        self.df.to_excel(self.caminho_excel, index=True)
        self.data_updated.emit()  # Emite o sinal de atualização              
        
    def rowKeys(self):
        return self.df.index

    def colKeys(self):
        return self.df.columns
    
    def getStrData(self, id_variable: str, column: str) -> str:
        # Identifica o operador bitwise e separa as variáveis
        if '|' in id_variable:
            variables = id_variable.split(' | ')
            operation = operator.or_
        elif '&' in id_variable:
            variables = id_variable.split(' & ')
            operation = operator.and_
        else:
            variables = [id_variable]
            operation = None

        # Função para obter o valor de uma variável
        def get_value(var: str, column: str) -> str:
            # Buscar a linha onde o índice é igual a 'var'
            row = self.df.loc[var]
            # Verificar se a linha contém a coluna e retornar o valor
            if column in row.index:  # Verifica se a coluna existe na linha
                return row[column]
            return None
        
        # Obtém os valores das variáveis
        values = [get_value(var) for var in variables]

        # Verifica se houve algum erro na obtenção dos valores
        if any(x in values for x in ["ERROR", None]):
            return None

        # Aplica a operação bitwise, se houver mais de uma variável
        if operation:
            result = reduce(operation, values)
            return str(result)
        else:
            return str(values[0])
        
    def setStrData(self, id_variable: str, column: str, value: str):
        # Verificar se o id_variable já está no índice (NAME)
        if id_variable in self.df.index:
            # Atualizar o valor na coluna específica para o índice (NAME)
            self.df.loc[id_variable, column] = value
        else:
            # Adicionar uma nova linha, configurando o índice (NAME) corretamente
            new_row = pd.DataFrame({column: [value]}, index=[id_variable])
            self.df = pd.concat([self.df, new_row])
        self.saveAllData()

        
# Exemplo de uso
if __name__ == '__main__':
    storage = Storage('dados.xlsx')
    storage.data_updated.connect(lambda: print("Dados foram atualizados!"))
    storage.set_variable('PROCESS_VARIABLE', 'TIT100', '42480000')
    valor = storage.get_variable('PROCESS_VARIABLE', 'TIT100')
    print(f"Valor obtido para 'PROCESS_VARIABLE' em TIT100: {valor}")
