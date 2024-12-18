from typing import Any, Optional, Union

from frontend.symbol.varsymbol import VarSymbol

from .tacfunc import TACFunc


# A TAC program consists of several TAC functions.
class TACProg:
    def __init__(self, funcs: list[TACFunc], globals: list[VarSymbol]) -> None:
        self.funcs = funcs
        self.globals = globals

    def printTo(self) -> None:
        for func in self.funcs:
            func.printTo()
