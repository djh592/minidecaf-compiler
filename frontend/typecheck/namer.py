from typing import Protocol, TypeVar, cast

from frontend.ast.node import T, Node, NullType
from frontend.ast.tree import *
from frontend.ast.tree import T, For
from frontend.ast.visitor import T, RecursiveVisitor, Visitor
from frontend.scope.globalscope import GlobalScope
from frontend.scope.scope import Scope, ScopeKind
from frontend.scope.scopestack import ScopeStack
from frontend.symbol.funcsymbol import FuncSymbol
from frontend.symbol.symbol import Symbol
from frontend.symbol.varsymbol import VarSymbol
from frontend.type.array import ArrayType
from frontend.type.type import DecafType
from utils.error import *
from utils.riscv import MAX_INT

"""
The namer phase: resolve all symbols defined in the abstract 
syntax tree and store them in symbol tables (i.e. scopes).
"""


class Namer(Visitor[ScopeStack, None]):
    def __init__(self) -> None:
        pass

    # Entry of this phase
    def transform(self, program: Program) -> Program:
        # Global scope. You don't have to consider it until Step 6.
        program.globalScope = GlobalScope
        ctx: ScopeStack = ScopeStack(program.globalScope)

        program.accept(self, ctx)
        return program

    def visitProgram(self, program: Program, ctx: ScopeStack) -> None:
        # Check if the 'main' function is missing
        if not program.hasMainFunc():
            raise DecafNoMainFuncError

        for func in program.children:
            func.accept(self, ctx)

    def visitParameter(self, param: Parameter, ctx: ScopeStack) -> None:
        if ctx.top().lookup(param.ident.value) is not None:
            raise DecafDeclConflictError(param.ident.value)
        symbol = VarSymbol(param.ident.value, param.var_t.type)
        ctx.top().declare(symbol)
        param.setattr("symbol", symbol)

    def visitParameterList(self, params: ParameterList, ctx: ScopeStack) -> None:
        for param in params:
            param.accept(self, ctx)

    def visitFunction(self, func: Function, ctx: ScopeStack) -> None:
        if ctx.globalscope.lookup(func.ident.value) is not None:
            raise DecafDeclConflictError(func)
        symbol = FuncSymbol(func.ident.value, func.ret_t.type, ctx.globalscope)
        for param in func.params.children:
            symbol.addParaType(param.var_t.type)
        ctx.globalscope.declare(symbol)
        func.setattr("symbol", symbol)

        ctx.push(Scope(ScopeKind.LOCAL))
        func.params.accept(self, ctx)
        for child in func.body:
            child.accept(self, ctx)
        ctx.pop()

    def visitBlock(self, block: Block, ctx: ScopeStack) -> None:
        ctx.push(Scope(ScopeKind.LOCAL))
        for child in block:
            child.accept(self, ctx)
        ctx.pop()

    def visitReturn(self, stmt: Return, ctx: ScopeStack) -> None:
        stmt.expr.accept(self, ctx)

    """
    def visitFor(self, stmt: For, ctx: Scope) -> None:

    1. Open a local scope for stmt.init.
    2. Visit stmt.init, stmt.cond, stmt.update.
    3. Open a loop in ctx (for validity checking of break/continue)
    4. Visit body of the loop.
    5. Close the loop and the local scope.
    """

    def visitIf(self, stmt: If, ctx: ScopeStack) -> None:
        stmt.cond.accept(self, ctx)
        stmt.then.accept(self, ctx)

        # check if the else branch exists
        if not stmt.otherwise is NULL:
            stmt.otherwise.accept(self, ctx)

    def visitWhile(self, stmt: While, ctx: ScopeStack) -> None:
        stmt.cond.accept(self, ctx)
        ctx.openLoop()
        stmt.body.accept(self, ctx)
        ctx.closeLoop()

    def visitFor(self, stmt: For, ctx: ScopeStack) -> None:
        ctx.push(Scope(ScopeKind.LOCAL))
        if stmt.init is not NULL:
            stmt.init.accept(self, ctx)
        if stmt.cond is not NULL:
            stmt.cond.accept(self, ctx)
        if stmt.update is not NULL:
            stmt.update.accept(self, ctx)
        ctx.openLoop()
        stmt.body.accept(self, ctx)
        ctx.closeLoop()
        ctx.pop()
        ctx

    def visitBreak(self, stmt: Break, ctx: ScopeStack) -> None:
        """
        You need to check if it is currently within the loop.
        To do this, you may need to check 'visitWhile'.

        if not in a loop:
            raise DecafBreakOutsideLoopError()
        """
        if not ctx.inLoop():
            raise DecafBreakOutsideLoopError()
        # raise NotImplementedError

    """
    def visitContinue(self, stmt: Continue, ctx: Scope) -> None:
    
    1. Refer to the implementation of visitBreak.
    """
    def visitContinue(self, stmt: Continue, ctx: ScopeStack) -> None:
        if not ctx.inLoop():
            raise DecafContinueOutsideLoopError()

    def visitDeclaration(self, decl: Declaration, ctx: ScopeStack) -> None:
        """
        1. Use ctx.lookup to find if a variable with the same name has been declared.
        2. If not, build a new VarSymbol, and put it into the current scope using ctx.declare.
        3. Set the 'symbol' attribute of decl.
        4. If there is an initial value, visit it.
        """
        if ctx.top().lookup(decl.ident.value) is not None:
            raise DecafDeclConflictError(decl.ident.name)
        symbol = VarSymbol(decl.ident.value, decl.var_t.type)
        ctx.top().declare(symbol)
        decl.setattr("symbol", symbol)
        if decl.init_expr is not None:
            decl.init_expr.accept(self, ctx)
        # raise NotImplementedError

    def visitAssignment(self, expr: Assignment, ctx: ScopeStack) -> None:
        """
        1. Refer to the implementation of visitBinary.
        """
        expr.lhs.accept(self, ctx)
        expr.rhs.accept(self, ctx)
        # raise NotImplementedError

    def visitUnary(self, expr: Unary, ctx: ScopeStack) -> None:
        expr.operand.accept(self, ctx)

    def visitExpressionList(self, exprs: ExpressionList, ctx: ScopeStack) -> None:
        for expr in exprs:
            expr.accept(self, ctx)

    def visitCall(self, expr: Call, ctx: ScopeStack) -> None:
        if not ctx.lookup(expr.ident.value).isFunc:
            raise DecafBadFuncCallError(expr.ident.value)
        func: FuncSymbol = GlobalScope.lookup(expr.ident.value)
        if func is None:
            raise DecafUndefinedFuncError(expr.ident.value)
        expr.setattr("symbol", func)

        expr.args.accept(self, ctx)
        if len(expr.args) != func.parameterNum:
            raise DecafBadFuncCallError(expr.ident.value)
        for i in range(len(expr.args.children)):
            if not func.getParaType(i) == INT:
                raise DecafBadFuncCallError(expr.ident.value)

    def visitBinary(self, expr: Binary, ctx: ScopeStack) -> None:
        expr.lhs.accept(self, ctx)
        expr.rhs.accept(self, ctx)

    def visitCondExpr(self, expr: ConditionExpression, ctx: ScopeStack) -> None:
        """
        1. Refer to the implementation of visitBinary.
        """
        expr.cond.accept(self, ctx)
        expr.then.accept(self, ctx)
        expr.otherwise.accept(self, ctx)
        # raise NotImplementedError

    def visitIdentifier(self, ident: Identifier, ctx: ScopeStack) -> None:
        """
        1. Use ctx.lookup to find the symbol corresponding to ident.
        2. If it has not been declared, raise a DecafUndefinedVarError.
        3. Set the 'symbol' attribute of ident.
        """
        symbol = ctx.lookup(ident.value)
        if symbol is None:
            raise DecafUndefinedVarError(ident.value)
        ident.setattr("symbol", symbol)
        # raise NotImplementedError

    def visitIntLiteral(self, expr: IntLiteral, ctx: ScopeStack) -> None:
        value = expr.value
        if value > MAX_INT:
            raise DecafBadIntValueError(value)
