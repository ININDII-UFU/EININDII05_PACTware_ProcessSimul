from functools import reduce
import pandas as pd
import operator
import sqlite3
import sys
import os
import shutil
import platform

def get_app_data_dir(app_name="processSimul"):
    """Retorna a pasta apropriada para dados persistentes da aplicação."""
    system = platform.system()
    if system == "Windows":
        return os.path.join(os.getenv("APPDATA"), app_name)
    elif system == "Darwin":  # macOS
        return os.path.join(os.path.expanduser("~/Library/Application Support"), app_name)
    else:  # Linux e outros Unix-like
        return os.path.join(os.path.expanduser("~/.local/share"), app_name)

def get_persistent_db_path(relative_path="db/banco.db", app_name="processSimul"):
    target_dir = get_app_data_dir(app_name)
    os.makedirs(target_dir, exist_ok=True)
    target_db_path = os.path.join(target_dir, os.path.basename(relative_path))

    if not os.path.exists(target_db_path):
        if hasattr(sys, "_MEIPASS"):
            source_path = os.path.join(sys._MEIPASS, *relative_path.replace('\\','/').split("/"))
        else:
            source_path = os.path.abspath(relative_path)
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Arquivo de banco não encontrado: {source_path}")
        print(f"[INFO] Copiando banco para: {target_db_path}")
        shutil.copy2(source_path, target_db_path)

    return target_db_path

class DBStorage():
    # data_updated = Signal()  # Sinal emitido ao atualizar dados
        
    def __init__(self, db_name: str):
        # super().__init__()
        self.db_name = get_persistent_db_path(db_name, 'processSimul')

    def rowKeys(self, tableName: str) -> list:
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(f'SELECT NAME FROM {tableName}_tabela;')
            return [linha[0] for linha in cursor.fetchall()]

    def colKeys(self, tableName: str) -> list:
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            # Executa PRAGMA para obter informações da estrutura da tabela
            cursor.execute(f"PRAGMA table_info({tableName}_tabela)")
            colunas = cursor.fetchall()    
            return [coluna[1] for coluna in colunas[1:]]
        
    def getRawData(self, tableName: str, rowName: str, colName: str) -> str:
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT {colName} FROM {tableName}_tabela WHERE NAME = ?", (rowName,))
            result = cursor.fetchone()
            return result[0] if result else None    
        
    def getData(self, tableName: str, rowName: str, colName: str) -> str:
        if '|' in rowName:
            variables = rowName.split(' | ')
            operation = operator.or_
        elif '&' in rowName:
            variables = rowName.split(' & ')
            operation = operator.and_
        else:
            variables = [rowName]
            operation = None
        values = []
        for var in variables:
            values.append(self.getRawData(tableName, var, colName))  # usar 'var' aqui

        if any(v in (None, "ERROR") for v in values):
            return None

        if operation:
            return str(reduce(operation, map(int, values)))
        return str(values[0])

    def setRawData(self, tableName: str, rowName: str, colName: str, value: str):
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()

                # Garante que a tabela exista
                cursor.execute(f'''
                    CREATE TABLE IF NOT EXISTS {tableName}_tabela (
                        NAME TEXT PRIMARY KEY
                    )
                ''')

                # Garante que a coluna exista
                cursor.execute(f"PRAGMA table_info({tableName}_tabela)")
                columns = [col[1] for col in cursor.fetchall()]
                if colName not in columns:
                    cursor.execute(f"ALTER TABLE {tableName}_tabela ADD COLUMN {colName} TEXT")

                # Atualiza ou insere o valor
                cursor.execute(f"SELECT 1 FROM {tableName}_tabela WHERE NAME = ?", (rowName,))
                if cursor.fetchone():
                    cursor.execute(f"UPDATE {tableName}_tabela SET {colName} = ? WHERE NAME = ?", (value, rowName))
                else:
                    cursor.execute(f"INSERT INTO {tableName}_tabela (NAME, {colName}) VALUES (?, ?)", (rowName, value))

        except Exception as e:
            print(f"❌ Erro ao atualizar ou inserir no SQLite: {e}")        
    
    def dataFrame(self, tableName: str):
        with sqlite3.connect(self.db_name) as conn:
            df = pd.read_sql_query(f"SELECT * FROM {tableName}_tabela", conn, index_col='NAME')
        return df
                                
# Exemplo de uso
if __name__ == '__main__':
    storage = DBStorage('banco.db', 'HART_tabela')
    print(storage.colKeys())
    print(storage.rowKeys())