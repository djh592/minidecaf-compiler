from typing import Optional
from utils.tac.temp import Temp

from .symbol import *

"""
Variable symbol, representing a variable definition.
"""


class VarSymbol(Symbol):
    def __init__(self, name: str, type: DecafType, isGlobal: bool = False) -> None:
        super().__init__(name, type)
        self.temp: Temp
        self.isGlobal = isGlobal
        self.initValue = None

    def __str__(self) -> str:
        return "variable %s : %s" % (self.name, str(self.type))

    # To set the initial value of a variable symbol (used for global variable).
    def setInitValue(self, value: Optional[int]) -> None:
        self.initValue = value
