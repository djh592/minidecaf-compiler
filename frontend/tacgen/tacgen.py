from frontend.ast.node import Optional
from frontend.ast.tree import Function, Optional, ParameterList
from frontend.ast import node
from frontend.ast.tree import *
from frontend.ast.visitor import Visitor
from frontend.symbol.varsymbol import VarSymbol
from frontend.type.array import ArrayType
from utils.label.blocklabel import BlockLabel
from utils.label.funclabel import FuncLabel
from utils.tac import tacop
from utils.tac.temp import Temp
from utils.tac.tacinstr import *
from utils.tac.tacfunc import TACFunc
from utils.tac.tacprog import TACProg
from utils.tac.tacvisitor import TACVisitor


"""
The TAC generation phase: translate the abstract syntax tree into three-address code.
"""


class LabelManager:
    """
    A global label manager (just a counter).
    We use this to create unique (block) labels accross functions.
    """

    def __init__(self):
        self.nextTempLabelId = 0

    def freshLabel(self) -> BlockLabel:
        self.nextTempLabelId += 1
        return BlockLabel(str(self.nextTempLabelId))


class TACFuncEmitter(TACVisitor):
    """
    Translates a minidecaf (AST) function into low-level TAC function.
    """

    def __init__(
        self, entry: FuncLabel, numArgs: int, labelManager: LabelManager
    ) -> None:
        self.labelManager = labelManager
        self.func = TACFunc(entry, numArgs)
        self.visitLabel(entry)
        self.nextTempId = 0

        self.continueLabelStack = []
        self.breakLabelStack = []

    # To get a fresh new temporary variable.
    def freshTemp(self) -> Temp:
        temp = Temp(self.nextTempId)
        self.nextTempId += 1
        return temp

    # To get a fresh new label (for jumping and branching, etc).
    def freshLabel(self) -> Label:
        return self.labelManager.freshLabel()

    # To count how many temporary variables have been used.
    def getUsedTemp(self) -> int:
        return self.nextTempId

    # In fact, the following methods can be named 'appendXXX' rather than 'visitXXX'.
    # E.g., by calling 'visitAssignment', you add an assignment instruction at the end of current function.
    def visitAssignment(self, dst: Temp, src: Temp) -> Temp:
        self.func.add(Assign(dst, src))
        return src

    def visitLoad(self, value: Union[int, str]) -> Temp:
        temp = self.freshTemp()
        self.func.add(LoadImm4(temp, value))
        return temp

    def visitLoadSymbol(self, symbol: VarSymbol) -> Temp:
        temp = self.freshTemp()
        self.func.add(LoadSymbol(temp, symbol.name))
        return temp
    
    def visitLoadMem(self, src: Temp, offset: int) -> Temp:
        temp = self.freshTemp()
        self.func.add(Load(temp, src, offset))
        return temp
    
    def visitStoreMem(self, src: Temp, dst: Temp, offset: int) -> None:
        self.func.add(Store(dst, offset, src))

    def visitAlloc(self, size: int) -> Temp:
        temp = self.freshTemp()
        self.func.add(Alloc(temp, size))
        return temp

    def visitUnary(self, op: UnaryOp, operand: Temp) -> Temp:
        temp = self.freshTemp()
        self.func.add(Unary(op, temp, operand))
        return temp

    def visitUnarySelf(self, op: UnaryOp, operand: Temp) -> None:
        self.func.add(Unary(op, operand, operand))

    def visitCall(self, label: FuncLabel, args: list[Temp]) -> Temp:
        temp = self.freshTemp()
        self.func.add(Call(temp, label, args))
        return temp

    def visitBinary(self, op: BinaryOp, lhs: Temp, rhs: Temp) -> Temp:
        temp = self.freshTemp()
        self.func.add(Binary(op, temp, lhs, rhs))
        return temp

    def visitBinarySelf(self, op: BinaryOp, lhs: Temp, rhs: Temp) -> None:
        self.func.add(Binary(op, lhs, lhs, rhs))

    def visitBranch(self, target: Label) -> None:
        self.func.add(Branch(target))

    def visitCondBranch(self, op: CondBranchOp, cond: Temp, target: Label) -> None:
        self.func.add(CondBranch(op, cond, target))

    def visitReturn(self, value: Optional[Temp]) -> None:
        self.func.add(Return(value))

    def visitLabel(self, label: Label) -> None:
        self.func.add(Mark(label))

    def visitMemo(self, content: str) -> None:
        self.func.add(Memo(content))

    def visitRaw(self, instr: TACInstr) -> None:
        self.func.add(instr)

    def visitEnd(self) -> TACFunc:
        if (len(self.func.instrSeq) == 0) or (not self.func.instrSeq[-1].isReturn()):
            self.func.add(Return(None))
        self.func.tempUsed = self.getUsedTemp()
        return self.func

    # To open a new loop (for break/continue statements)
    def openLoop(self, breakLabel: Label, continueLabel: Label) -> None:
        self.breakLabelStack.append(breakLabel)
        self.continueLabelStack.append(continueLabel)

    # To close the current loop.
    def closeLoop(self) -> None:
        self.breakLabelStack.pop()
        self.continueLabelStack.pop()

    # To get the label for 'break' in the current loop.
    def getBreakLabel(self) -> Label:
        return self.breakLabelStack[-1]

    # To get the label for 'continue' in the current loop.
    def getContinueLabel(self) -> Label:
        return self.continueLabelStack[-1]


class TACGen(Visitor[TACFuncEmitter, None]):
    # Entry of this phase
    def transform(self, program: Program) -> TACProg:
        labelManager = LabelManager()
        tacFuncs = []
        for funcName, astFunc in program.functions().items():
            # in step9, you need to use real parameter count
            emitter = TACFuncEmitter(FuncLabel(funcName), len(astFunc.params), labelManager)
            astFunc.params.accept(self, emitter)
            astFunc.body.accept(self, emitter)
            tacFuncs.append(emitter.visitEnd())
        globals: list[VarSymbol] = []
        for decl in program.globals():
            globals.append(decl.getattr("symbol"))     
        return TACProg(tacFuncs, globals)

    def visitParameter(self, param: Parameter, mv: TACFuncEmitter) -> None:
        temp = mv.freshTemp()
        param.getattr('symbol').temp = temp
        mv.func.argTemps.append(temp)
    
    def visitParameterList(self, params: ParameterList, mv: TACFuncEmitter) -> None:
        for param in params.children:
            param.accept(self, mv)

    def visitBlock(self, block: Block, mv: TACFuncEmitter) -> None:
        for child in block:
            child.accept(self, mv)

    def visitReturn(self, stmt: Return, mv: TACFuncEmitter) -> None:
        stmt.expr.accept(self, mv)
        mv.visitReturn(stmt.expr.getattr("val"))

    def visitBreak(self, stmt: Break, mv: TACFuncEmitter) -> None:
        mv.visitBranch(mv.getBreakLabel())

    def visitContinue(self, stmt: Continue, mv: TACFuncEmitter) -> None:
        mv.visitBranch(mv.getContinueLabel())

    def visitIdentifier(self, ident: Identifier, mv: TACFuncEmitter) -> None:
        """
        1. Set the 'val' attribute of ident as the temp variable of the 'symbol' attribute of ident.
        """
        symbol: VarSymbol = ident.getattr('symbol')
        if symbol.isGlobal:
            temp = mv.visitLoadSymbol(symbol)
            ident.setattr("val", mv.visitLoadMem(temp, 0))
        else:
            ident.setattr("val", symbol.temp)
        # raise NotImplementedError

    def visitDeclaration(self, decl: Declaration, mv: TACFuncEmitter) -> None:
        """
        1. Get the 'symbol' attribute of decl.
        2. Use mv.freshTemp to get a new temp variable for this symbol.
        3. If the declaration has an initial value, use mv.visitAssignment to set it.
        """
        symbol: VarSymbol = decl.getattr("symbol")
        if isinstance(symbol.type, ArrayType):
            symbol.temp = mv.visitAlloc(symbol.type.size)
            if decl.init_expr is not NULL:
                raise NotImplementedError
        else:
            symbol.temp = mv.freshTemp()
            if decl.init_expr is not NULL:
                decl.init_expr.accept(self, mv)
                mv.visitAssignment(symbol.temp, decl.init_expr.getattr("val"))
        # raise NotImplementedError

    def visitAssignment(self, expr: Assignment, mv: TACFuncEmitter) -> None:
        """
        1. Visit the right hand side of expr, and get the temp variable of left hand side.
        2. Use mv.visitAssignment to emit an assignment instruction.
        3. Set the 'val' attribute of expr as the value of assignment instruction.
        """
        expr.rhs.accept(self, mv)
        if isinstance(expr.lhs, IndexExpression):
            rhsTemp = expr.rhs.getattr("val")
            lhsSymbol: VarSymbol = expr.lhs.getattr("symbol")
            sizes = lhsSymbol.type.dims
            indexes = expr.lhs.indexes
            indexes[0].accept(self, mv)
            offset: Temp = indexes[0].getattr("val")
            for size, index in zip(sizes[1:], indexes[1:]):
                length: Temp = mv.visitLoad(size)
                offset: Temp = mv.visitBinary(tacop.TacBinaryOp.MUL, offset, length)
                index.accept(self, mv)
                indexTemp: Temp = index.getattr("val")
                offset: Temp = mv.visitBinary(tacop.TacBinaryOp.ADD, offset, indexTemp)
            if lhsSymbol.isGlobal:
                temp = mv.visitLoadSymbol(lhsSymbol)
            else:
                temp = lhsSymbol.temp
            sizeTemp = mv.visitLoad(lhsSymbol.type.full_indexed.size)
            offset: Temp = mv.visitBinary(tacop.TacBinaryOp.MUL, offset, sizeTemp)
            addr: Temp = mv.visitBinary(tacop.TacBinaryOp.ADD, temp, offset)
            mv.visitStoreMem(rhsTemp, addr, 0)
            expr.setattr("val", rhsTemp)
        elif isinstance(expr.lhs, Identifier):
            lhsSymbol: VarSymbol = expr.lhs.getattr("symbol")
            if lhsSymbol.isGlobal:
                mv.visitStoreMem(expr.rhs.getattr("val"), mv.visitLoadSymbol(lhsSymbol), 0)
                expr.setattr("val", expr.rhs.getattr("val"))
            else:
                expr.lhs.accept(self, mv)
                expr.setattr("val", mv.visitAssignment(expr.lhs.getattr("symbol").temp, expr.rhs.getattr("val")))
        else:
            raise NotImplementedError

    def visitIf(self, stmt: If, mv: TACFuncEmitter) -> None:
        stmt.cond.accept(self, mv)

        if stmt.otherwise is NULL:
            skipLabel = mv.freshLabel()
            mv.visitCondBranch(
                tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), skipLabel
            )
            stmt.then.accept(self, mv)
            mv.visitLabel(skipLabel)
        else:
            skipLabel = mv.freshLabel()
            exitLabel = mv.freshLabel()
            mv.visitCondBranch(
                tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), skipLabel
            )
            stmt.then.accept(self, mv)
            mv.visitBranch(exitLabel)
            mv.visitLabel(skipLabel)
            stmt.otherwise.accept(self, mv)
            mv.visitLabel(exitLabel)

    def visitWhile(self, stmt: While, mv: TACFuncEmitter) -> None:
        beginLabel = mv.freshLabel()
        loopLabel = mv.freshLabel()
        breakLabel = mv.freshLabel()
        mv.openLoop(breakLabel, loopLabel)

        mv.visitLabel(beginLabel)
        stmt.cond.accept(self, mv)
        mv.visitCondBranch(tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), breakLabel)

        stmt.body.accept(self, mv)
        mv.visitLabel(loopLabel)
        mv.visitBranch(beginLabel)
        mv.visitLabel(breakLabel)
        mv.closeLoop()

    def visitFor(self, stmt: For, mv: TACFuncEmitter) -> None:
        beginLabel = mv.freshLabel()
        loopLabel = mv.freshLabel()
        breakLabel = mv.freshLabel()
        mv.openLoop(breakLabel, loopLabel)

        if stmt.init is not NULL:
            stmt.init.accept(self, mv)
        mv.visitLabel(beginLabel)
        if stmt.cond is not NULL:
            stmt.cond.accept(self, mv)
            mv.visitCondBranch(tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), breakLabel)
        stmt.body.accept(self, mv)
        mv.visitLabel(loopLabel)
        if stmt.update is not NULL:
            stmt.update.accept(self, mv)
        mv.visitBranch(beginLabel)
        mv.visitLabel(breakLabel)
        mv.closeLoop()

    def visitUnary(self, expr: Unary, mv: TACFuncEmitter) -> None:
        expr.operand.accept(self, mv)

        op = {
            node.UnaryOp.Neg: tacop.TacUnaryOp.NEG,
            # You can add unary operations here.
            node.UnaryOp.BitNot: tacop.TacUnaryOp.NOT,
            node.UnaryOp.LogicNot: tacop.TacUnaryOp.LNOT,
        }[expr.op]
        expr.setattr("val", mv.visitUnary(op, expr.operand.getattr("val")))

    def visitExpressionList(self, exprs: ExpressionList, mv: TACFuncEmitter) -> None:
        for expr in exprs.children:
            expr.accept(self, mv)

    def visitCall(self, expr: Call, mv: TACFuncEmitter) -> None:
        expr.args.accept(self, mv)
        argTemps = [arg.getattr("val") for arg in expr.args.children]
        expr.setattr("val", mv.visitCall(FuncLabel(expr.getattr("symbol").name), argTemps))

    def visitBinary(self, expr: Binary, mv: TACFuncEmitter) -> None:
        expr.lhs.accept(self, mv)
        expr.rhs.accept(self, mv)

        op = {
            node.BinaryOp.Add: tacop.TacBinaryOp.ADD,
            node.BinaryOp.LogicOr: tacop.TacBinaryOp.LOR,
            # You can add binary operations here.
            node.BinaryOp.Sub: tacop.TacBinaryOp.SUB,
            node.BinaryOp.Mul: tacop.TacBinaryOp.MUL,
            node.BinaryOp.Div: tacop.TacBinaryOp.DIV,
            node.BinaryOp.Mod: tacop.TacBinaryOp.MOD,
            node.BinaryOp.LogicAnd: tacop.TacBinaryOp.LAND,
            node.BinaryOp.EQ: tacop.TacBinaryOp.EQU,
            node.BinaryOp.NE: tacop.TacBinaryOp.NEQ,
            node.BinaryOp.LT: tacop.TacBinaryOp.SLT,
            node.BinaryOp.LE: tacop.TacBinaryOp.LEQ,
            node.BinaryOp.GT: tacop.TacBinaryOp.SGT,
            node.BinaryOp.GE: tacop.TacBinaryOp.GEQ,
        }[expr.op]
        expr.setattr(
            "val", mv.visitBinary(op, expr.lhs.getattr("val"), expr.rhs.getattr("val"))
        )

    def visitCondExpr(self, expr: ConditionExpression, mv: TACFuncEmitter) -> None:
        """
        1. Refer to the implementation of visitIf and visitBinary.
        """
        expr.cond.accept(self, mv)
        skipLabel = mv.freshLabel()
        exitLabel = mv.freshLabel()
        temp = mv.freshTemp()
        mv.visitCondBranch(
            tacop.CondBranchOp.BEQ, expr.cond.getattr("val"), skipLabel
        )

        expr.then.accept(self, mv)
        mv.visitAssignment(temp, expr.then.getattr("val"))
        mv.visitBranch(exitLabel)
        mv.visitLabel(skipLabel)
        
        expr.otherwise.accept(self, mv)
        mv.visitAssignment(temp, expr.otherwise.getattr("val"))
        mv.visitLabel(exitLabel)
        expr.setattr("val", temp)
        # raise NotImplementedError

    def visitIndexExpr(self, expr: IndexExpression, mv: TACFuncEmitter) -> None:
        for index in expr.indexes:
            index.accept(self, mv)
        symbol: VarSymbol = expr.getattr("symbol")
        sizes = symbol.type.dims
        indexes = expr.indexes
        indexes[0].accept(self, mv)
        offset: Temp = indexes[0].getattr("val")
        for size, index in zip(sizes[1:], indexes[1:]):
            length: Temp = mv.visitLoad(size)
            offset: Temp = mv.visitBinary(tacop.TacBinaryOp.MUL, offset, length)
            index.accept(self, mv)
            indexTemp: Temp = index.getattr("val")
            offset: Temp = mv.visitBinary(tacop.TacBinaryOp.ADD, offset, indexTemp)
        if symbol.isGlobal:
            temp = mv.visitLoadSymbol(symbol)
        else:
            temp = symbol.temp
        sizeTemp = mv.visitLoad(symbol.type.full_indexed.size)
        offset: Temp = mv.visitBinary(tacop.TacBinaryOp.MUL, offset, sizeTemp)
        addr = mv.visitBinary(tacop.TacBinaryOp.ADD, temp, offset)
        expr.setattr("val", mv.visitLoadMem(addr, 0))

    def visitIntLiteral(self, expr: IntLiteral, mv: TACFuncEmitter) -> None:
        expr.setattr("val", mv.visitLoad(expr.value))
