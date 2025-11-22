from enum import Enum

class DBState(Enum):
    none = 0
    originValue = 1
    machineValue = 2
    humanValue = 3
    
class DBModel(Enum):
    Value = 0
    Func = 1
    tFunc = 2