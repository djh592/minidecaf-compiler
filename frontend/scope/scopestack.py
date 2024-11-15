from typing import Optional

from frontend.symbol.symbol import Symbol

from .scope import Scope

class ScopeStack:
    def __init__(self, globalscope: Scope) -> None:
        self.globalscope = globalscope
        self.stack: list[Scope] = [globalscope]
        self.loopCount = 0

    def push(self, scope: Scope) -> None:
        self.stack.append(scope)

    def pop(self) -> Scope:
        return self.stack.pop()
    
    def top(self) -> Scope:
        return self.stack[-1]
    
    def lookup(self, name: str) -> Optional[Symbol]:
        for scope in reversed(self.stack):
            symbol = scope.lookup(name)
            if symbol is not None:
                return symbol
        return None

    def openLoop(self) -> None:
        self.loopCount += 1

    def closeLoop(self) -> None:
        self.loopCount -= 1

    def inLoop(self) -> bool:
        return self.loopCount > 0