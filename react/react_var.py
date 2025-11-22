import asyncio
from .qt_compat import QObject, Signal, Slot
from hrt.hrt_type import hrt_type_hex_to, hrt_type_hex_from
from db_files.db_types import DBState, DBModel
from asteval import Interpreter
from numpy import exp, log
import random
import math
import re

class ReactVar(QObject):
    valueChangedSignal = Signal(object)
    isTFuncSignal = Signal(object, bool)

    def __init__(self, tableName: str, rowName: str, colName: str, reactFactory):
        super().__init__()
        self.tableName = tableName
        self.rowName = rowName
        self.colName = colName
        self.reactFactory = reactFactory
        self.isWidgetValueChanged = False
        self._evaluator = Interpreter()

        # Async init tracking
        self._initialized = False
        self._init_event = asyncio.Event()

        # Internal state
        self._value = None
        self.inputValue = None
        self.model = None
        self._func = None
        self._tFunc = None
        self._tokens: list[str] = []

    async def _startDatabase(self):
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None,
            self.reactFactory.storage.getData,
            self.tableName,
            self.rowName,
            self.colName
        )

        newModel = self.getModel(data)
        if newModel == DBModel.Value:
            self.setValue(data, stateAtual=DBState.machineValue)
        elif newModel == DBModel.Func:
            self.setFunc(data[1:])
        elif newModel == DBModel.tFunc:
            self.setTFunc(data[1:])

        self._initialized = True
        self._init_event.set()

    async def getValue(self, stateDesejado: DBState = DBState.humanValue) -> float | str:
        if not self._initialized:
            await self._init_event.wait()

        if self.colName in ['NAME', 'TYPE', 'BYTE_SIZE', 'MB_POINT', 'ADDRESS']:
            return self._value

        return self.translate(
            self._value,
            self.type(),
            self.byteSize(),
            stateDesejado,
            DBState.humanValue
        )

    def getFunc(self) -> str | None:
        """Retorna a expressão da função (sem prefixo)"""
        return self._func

    def getTFunc(self) -> str | None:
        """Retorna a expressão de tFunc (sem prefixo)"""
        return self._tFunc

    @staticmethod
    def translate(value, type: str, byteSize: int,
                  stateDesejado: DBState, stateAtual: DBState = DBState.humanValue):
        if stateDesejado == stateAtual or \
           (stateDesejado == DBState.originValue and stateAtual == DBState.machineValue) or \
           (stateDesejado == DBState.machineValue and stateAtual == DBState.originValue):
            return value
        if stateDesejado == DBState.humanValue:
            return hrt_type_hex_to(value, type)
        return hrt_type_hex_from(value, type, byteSize)

    def type(self, tableName=None, rowName=None):
        if tableName is None or rowName is None:
            tableName = self.tableName
            rowName = self.rowName
        return self.reactFactory.storage.getData(tableName, rowName, 'TYPE')

    def byteSize(self, tableName=None, rowName=None):
        if tableName is None or rowName is None:
            tableName = self.tableName
            rowName = self.rowName
        return int(self.reactFactory.storage.getData(tableName, rowName, 'BYTE_SIZE'))

    def getModel(self, value=None) -> DBModel:
        if value is None:
            value = self.reactFactory.storage.getData(self.tableName, self.rowName, self.colName)
        if isinstance(value, str):
            if value.startswith('@'):
                return DBModel.Func
            elif value.startswith('$'):
                return DBModel.tFunc
        return DBModel.Value

    def setValue(self, value, stateAtual: DBState = DBState.humanValue, isWidgetValueChanged: bool = False):
        self.isWidgetValueChanged = isWidgetValueChanged

        # 1) Valor "humano" para a UI (_value)
        if self.colName in ['NAME', 'TYPE', 'BYTE_SIZE', 'MB_POINT', 'ADDRESS']:
            valueAux = value
            storage_value = value  # meta-campos gravam como texto puro
        else:
            self._checkModel(DBModel.Value)
            valueAux = self.translate(value, self.type(), self.byteSize(),
                                    DBState.humanValue, stateAtual)
            # 2) Valor "machine" para o banco
            storage_value = self.translate(value, self.type(), self.byteSize(),
                                        DBState.machineValue, stateAtual)

        self._func = None
        self._tFunc = None
        isChanged = (self._value != valueAux)
        self._value = valueAux
        self.model = DBModel.Value

        # 3) PERSISTE no SQLite
        try:
            self.reactFactory.storage.setRawData(self.tableName, self.rowName, self.colName, storage_value)
        except Exception as e:
            print(f"[WARN] Persistência Value falhou em {self.tableName}.{self.colName}.{self.rowName}: {e}")

        if isChanged:
            self.valueChangedSignal.emit(self)


    def setFunc(self, func: str):
        if self._func != func:
            self._checkModel(DBModel.Func)
            self._tFunc = None
            self.model = DBModel.Func

            # PERSISTE com prefixo '@'
            try:
                self.reactFactory.storage.setRawData(self.tableName, self.rowName, self.colName, '@' + (func or ''))
            except Exception as e:
                print(f"[WARN] Persistência Func falhou em {self.tableName}.{self.colName}.{self.rowName}: {e}")

            self._startFunc(func)


    def setTFunc(self, tFunc: str):
        if self._tFunc != tFunc:
            self._checkModel(DBModel.tFunc)
            self.model = DBModel.tFunc
            self._value = 0
            self._tFunc = tFunc

            # PERSISTE com prefixo '$'
            try:
                self.reactFactory.storage.setRawData(self.tableName, self.rowName, self.colName, '$' + (tFunc or ''))
            except Exception as e:
                print(f"[WARN] Persistência TFunc falhou em {self.tableName}.{self.colName}.{self.rowName}: {e}")

            # Mantém a lógica original
            _, __, ___, inp = tFunc.split(',')
            self._startFunc(inp[1:])
            self.isTFuncSignal.emit(self, True)


    def _checkModel(self, newModel: DBModel):
        oldModel = self.model
        if oldModel is not None and oldModel != newModel:
            self._connectTokens(self._tokens, False)
            if oldModel == DBModel.tFunc:
                self.isTFuncSignal.emit(self, False)

    def _startFunc(self, func: str):
        self._func = func
        tokens = re.findall(r'[A-Z]\w+\.[A-Z0-9]\w+\.[A-Za-z_0-9]\w+', func)
        if self._tokens != tokens:
            self._evaluator.symtable.clear()
            self._evaluator.symtable.update({
                'math':   math,
                'exp':    exp,
                'random': random,
                'log':    log,
                'abs':    abs,
                'int':    int                
            })
            self._connectTokens(tokens, True)
            self._tokens = tokens

    def _evaluate_expression(self, expr: str) -> float:
        sanitized = re.sub(r'([A-Z]\w+)\.([A-Z0-9]\w+)\.([A-Za-z_0-9]\w+)', r"\1_\2_\3", expr)
        result = self._evaluator(sanitized)
        return float(result) if result is not None else 0.0

    def _connectTokens(self, tokens: list[str], isconnect: bool = True):
        for token in tokens:
            table, col, row = token.split('.')
            other: ReactVar = self.reactFactory.df[table].at[row, col]
            if isconnect:
                val = other._value
                self._evaluator.symtable[f'{table}_{col}_{row}'] = val
                other.valueChangedSignal.connect(self._update_from_other_slot)
            else:
                other.valueChangedSignal.disconnect(self._update_from_other_slot)
        if isconnect and self._func:
            result = self._evaluate_expression(self._func)
            if self.model == DBModel.tFunc:
                self.inputValue = result
            else:
                self._value = result               
                self.valueChangedSignal.emit(self)

    @Slot(object)
    def _update_from_other_slot(self, data: "ReactVar"):
        val = data._value
        self._evaluator.symtable[f'{data.tableName}_{data.colName}_{data.rowName}'] = val
        result = self._evaluate_expression(self._func)
        if self.model == DBModel.tFunc:
            self.inputValue = result
        else:
            self._value = result
            self.isWidgetValueChanged = data.isWidgetValueChanged
            self.valueChangedSignal.emit(self)           