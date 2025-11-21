import pandas as pd
import sqlite3

def excel_to_sqlite(excel_file, db_name, table_name):
    try:
        # Ler o arquivo Excel e definir a primeira coluna como índice
        df = pd.read_excel(excel_file, index_col=0, dtype=str)  # A primeira coluna se torna o índice
        print("Primeiras linhas do DataFrame:")
        print(df.head())
        # Conectar ao banco de dados SQLite
        with sqlite3.connect(db_name) as conn:
            cursor = conn.cursor()
            # Criar a tabela com o índice como PRIMARY KEY
            columns = ", ".join([f'"{col}" TEXT' for col in df.columns])  # Cria as colunas com tipo TEXT
            create_table_query = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                NAME TEXT PRIMARY KEY,
                {columns}
            )
            """
            cursor.execute(create_table_query)
            # Inserir os dados no banco, mantendo o índice
            df.to_sql(table_name, conn, if_exists='append', index=True)  # `index=True` para manter o índice como uma coluna
        print(f"✅ Dados salvos na tabela '{table_name}' do banco '{db_name}'.")
    except Exception as e:
        print(f"❌ Erro ao salvar os dados: {e}")
# Exemplo de uso
excel_to_sqlite('db/dados.xlsx', 'db/banco.db', 'hrt_tabela')
