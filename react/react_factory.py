import asyncio
from .qt_compat import QObject, Signal, Slot
import pandas as pd
from db_files.db_storage import DBStorage
from react.react_var import ReactVar  # ajuste conforme seu pacote

class ReactFactory(QObject):
    """
    Fábrica assíncrona para ReactVar.
    Cria dataframes vazios, instancia todos os ReactVar e então carrega seus dados.
    """
    df: dict
    autoCompleteList: dict
    isTFuncSignal = Signal(object, bool)

    def __init__(self):
        super().__init__()

    @classmethod
    async def create(cls, tableNames: list[str]) -> "ReactFactory":
        """
        Cria ReactFactory e inicializa todos os ReactVar para as tabelas listadas.
        Exemplo:
            react_factory = await ReactFactory.create(['HART', 'MODBUS'])
        """
        self = cls.__new__(cls)
        QObject.__init__(self)
        self.tableNames = tableNames
        self.storage = DBStorage('db/banco.db')
        self.df = {}
        self.autoCompleteList = {}

        # 1) Cria DataFrames e instancia ReactVar (sem carregar DB)
        for table in tableNames:
            rows = self.storage.rowKeys(table)
            cols = self.storage.colKeys(table)
            self.df[table] = pd.DataFrame(index=rows, columns=cols, dtype=object)
            for row in rows:
                for col in cols:
                    var = ReactVar(table, row, col, self)
                    self.df[table].at[row, col] = var
                    var.isTFuncSignal.connect(self._tFDataSlot)

        # 2) Carrega dados de todas as variáveis em paralelo
        tasks = []
        for table in tableNames:
            for row in self.df[table].index:
                for col in self.df[table].columns:
                    var: ReactVar = self.df[table].at[row, col]
                    tasks.append(asyncio.create_task(var._startDatabase()))
        await asyncio.gather(*tasks)

        # 3) Inicializa listas de autocomplete
        for table in tableNames:
            self.autoCompleteList[table] = {
                col: {row: {} for row in self.df[table].index}
                for col in self.df[table].columns
            }

        return self

    @Slot(object, bool)
    def _tFDataSlot(self, data: ReactVar, isConnect: bool):
        """Repropaga sinal de tFunc"""
        self.isTFuncSignal.emit(data, isConnect)
