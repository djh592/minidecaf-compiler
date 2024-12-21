from typing import Sequence, Tuple

from frontend.symbol.varsymbol import VarSymbol
from utils.error import IllegalArgumentException
from utils.label.label import Label, LabelKind
from utils.riscv import Riscv, RvBinaryOp, RvUnaryOp
from utils.tac.reg import Reg
from utils.tac.tacfunc import TACFunc
from utils.tac.tacinstr import *
from utils.tac.tacvisitor import TACVisitor
from utils.asmcodeprinter import AsmCodePrinter
from utils.tac.backendinstr import BackendInstr
from ..subroutineinfo import SubroutineInfo

"""
RiscvAsmEmitter: an AsmEmitter for RiscV
"""


class RiscvAsmEmitter():
    def __init__(
        self,
        allocatableRegs: list[Reg],
        callerSaveRegs: list[Reg],
        globals: list[VarSymbol],
    ):
        self.allocatableRegs = allocatableRegs
        self.callerSaveRegs = callerSaveRegs
        self.globals = globals
        self.printer = AsmCodePrinter()
    
        # the start of the asm code
        # int step10, you need to add the declaration of global var here

        # Add global variable declarations
        initialized_globals = [var for var in globals if var.initValue is not None]
        uninitialized_globals = [var for var in globals if var.initValue is None]

        if len(initialized_globals) > 0:
            self.printer.println(".data")
            for var in initialized_globals:
                self.printer.println(f".globl {var.name}")
                self.printer.println(f"{var.name}:")
                self.printer.println(f"    .word {var.initValue}")
            self.printer.println("")

        if len(uninitialized_globals) > 0:
            self.printer.println(".bss")
            for var in uninitialized_globals:
                self.printer.println(f".globl {var.name}")
                self.printer.println(f"{var.name}:")
                self.printer.println(f"    .space {var.type.size}")
            self.printer.println("")
        
        self.printer.println(".text")
        self.printer.println(".global main")
        self.printer.println("")

    # transform tac instrs to RiscV instrs
    # collect some info which is saved in SubroutineInfo for SubroutineEmitter
    def selectInstr(self, func: TACFunc) -> tuple[list[str], SubroutineInfo]:

        selector: RiscvAsmEmitter.RiscvInstrSelector = (
            RiscvAsmEmitter.RiscvInstrSelector(func.entry)
        )
        for instr in func.getInstrSeq():
            instr.accept(selector)

        info = SubroutineInfo(func.entry, func.argTemps)

        return (selector.seq, info)

    # return all the string stored in asmcodeprinter
    def emitEnd(self):
        return self.printer.close()

    class RiscvInstrSelector(TACVisitor):
        def __init__(self, entry: Label) -> None:
            self.entry = entry
            self.seq = []

        def visitOther(self, instr: TACInstr) -> None:
            raise NotImplementedError("RiscvInstrSelector visit{} not implemented".format(type(instr).__name__))

        # in step11, you need to think about how to deal with globalTemp in almost all the visit functions. 
        def visitReturn(self, instr: Return) -> None:
            if instr.value is not None:
                self.seq.append(Riscv.Move(Riscv.A0, instr.value))
            else:
                self.seq.append(Riscv.LoadImm(Riscv.A0, 0))
            self.seq.append(Riscv.JumpToEpilogue(self.entry))

        def visitMark(self, instr: Mark) -> None:
            self.seq.append(Riscv.RiscvLabel(instr.label))

        def visitLoadImm4(self, instr: LoadImm4) -> None:
            self.seq.append(Riscv.LoadImm(instr.dst, instr.value))

        def visitLoadSymbol(self, instr: LoadSymbol) -> None:
            self.seq.append(Riscv.LoadAddr(instr.dst, instr.symbol))

        def visitLoad(self, instr: Load) -> None:
            self.seq.append(Riscv.LoadWord(instr.dst, instr.src, instr.offset))

        def visitStore(self, instr: Store) -> None:
            self.seq.append(Riscv.StoreWord(instr.src, instr.dst, instr.offset))

        def visitAlloc(self, instr: Alloc) -> None:
            self.seq.append(Riscv.AllocStack(instr.size))
            self.seq.append(Riscv.Move(instr.dst, Riscv.SP))  

        def visitUnary(self, instr: Unary) -> None:
            op = {
                TacUnaryOp.NEG: RvUnaryOp.NEG,
                # You can add unary operations here.
                TacUnaryOp.NOT: RvUnaryOp.NOT,
                TacUnaryOp.LNOT: RvUnaryOp.SEQZ,
            }[instr.op]
            self.seq.append(Riscv.Unary(op, instr.dst, instr.operand))

        def visitCall(self, instr: Call) -> None:
            self.seq.append(Riscv.Call(instr.dst, instr.label, instr.args))
            self.seq.append(Riscv.Move(instr.dst, Riscv.A0))

        def visitBinary(self, instr: Binary) -> None:
            """
            For different tac operation, you should translate it to different RiscV code
            A tac operation may need more than one RiscV instruction
            """
            if instr.op == TacBinaryOp.LOR:
                self.seq.append(Riscv.Binary(RvBinaryOp.OR, instr.dst, instr.lhs, instr.rhs))
                self.seq.append(Riscv.Unary(RvUnaryOp.SNEZ, instr.dst, instr.dst))
            elif instr.op == TacBinaryOp.LAND:
                self.seq.append(Riscv.Unary(RvUnaryOp.SNEZ, instr.dst, instr.lhs))
                self.seq.append(Riscv.Binary(RvBinaryOp.SUB, instr.dst, Riscv.ZERO, instr.dst))
                self.seq.append(Riscv.Binary(RvBinaryOp.AND, instr.dst, instr.dst, instr.rhs))
                self.seq.append(Riscv.Unary(RvUnaryOp.SNEZ, instr.dst, instr.dst))
            elif instr.op == TacBinaryOp.EQU:
                self.seq.append(Riscv.Binary(RvBinaryOp.XOR, instr.dst, instr.lhs, instr.rhs))
                self.seq.append(Riscv.Unary(RvUnaryOp.SEQZ, instr.dst, instr.dst))
            elif instr.op == TacBinaryOp.NEQ:
                self.seq.append(Riscv.Binary(RvBinaryOp.XOR, instr.dst, instr.lhs, instr.rhs))
                self.seq.append(Riscv.Unary(RvUnaryOp.SNEZ, instr.dst, instr.dst))
            elif instr.op == TacBinaryOp.SLT:
                self.seq.append(Riscv.Binary(RvBinaryOp.SLT, instr.dst, instr.lhs, instr.rhs))
            elif instr.op == TacBinaryOp.SGT:
                self.seq.append(Riscv.Binary(RvBinaryOp.SLT, instr.dst, instr.rhs, instr.lhs))
            elif instr.op == TacBinaryOp.LEQ:
                self.seq.append(Riscv.Binary(RvBinaryOp.SLT, instr.dst, instr.rhs, instr.lhs))
                self.seq.append(Riscv.Unary(RvUnaryOp.SEQZ, instr.dst, instr.dst))
            elif instr.op == TacBinaryOp.GEQ:
                self.seq.append(Riscv.Binary(RvBinaryOp.SLT, instr.dst, instr.lhs, instr.rhs))
                self.seq.append(Riscv.Unary(RvUnaryOp.SEQZ, instr.dst, instr.dst))
            else:
                op = {
                    TacBinaryOp.ADD: RvBinaryOp.ADD,
                    # You can add binary operations here.
                    TacBinaryOp.SUB: RvBinaryOp.SUB,
                    TacBinaryOp.MUL: RvBinaryOp.MUL,
                    TacBinaryOp.DIV: RvBinaryOp.DIV,
                    TacBinaryOp.MOD: RvBinaryOp.REM,
                }[instr.op]
                self.seq.append(Riscv.Binary(op, instr.dst, instr.lhs, instr.rhs))

        def visitCondBranch(self, instr: CondBranch) -> None:
            self.seq.append(Riscv.Branch(instr.cond, instr.label))
        
        def visitBranch(self, instr: Branch) -> None:
            self.seq.append(Riscv.Jump(instr.target))

        def visitAssign(self, instr: Assign) -> None:
            self.seq.append(Riscv.Move(instr.dst, instr.src))

        # in step9, you need to think about how to pass the parameters and how to store and restore callerSave regs
        # in step11, you need to think about how to store the array 
"""
RiscvAsmEmitter: an SubroutineEmitter for RiscV
"""

class RiscvSubroutineEmitter():
    def __init__(self, emitter: RiscvAsmEmitter, info: SubroutineInfo) -> None:
        self.info = info
        self.printer = emitter.printer
        
        # + 4 is for the RA reg 
        self.nextLocalOffset = 4 * len(Riscv.CalleeSaved) + 8
        
        # the buf which stored all the NativeInstrs in this function
        self.buf: list[BackendInstr] = []

        # from temp to int
        # record where a temp is stored in the stack
        self.offsets = {}

        self.printer.printLabel(info.funcLabel)

        # in step9, step11 you can compute the offset of local array and parameters here

    def emitComment(self, comment: str) -> None:
        # you can add some log here to help you debug
        pass
    
    # store some temp to stack
    # usually happen when reaching the end of a basicblock
    # in step9, you need to think about the fuction parameters here
    def emitStoreToStack(self, src: Reg) -> None:
        if src.temp.index not in self.offsets:
            self.offsets[src.temp.index] = self.nextLocalOffset
            self.nextLocalOffset += 4
        self.buf.append(
            Riscv.NativeStoreWord(src, Riscv.FP, self.offsets[src.temp.index])
        )

    # load some temp from stack
    # usually happen when using a temp which is stored to stack before
    # in step9, you need to think about the fuction parameters here
    def emitLoadFromStack(self, dst: Reg, src: Temp):
        if src.index not in self.offsets:
            raise IllegalArgumentException()
        else:
            self.buf.append(
                Riscv.NativeLoadWord(dst, Riscv.FP, self.offsets[src.index])
            )

    # add a NativeInstr to buf
    # when calling the fuction emitAsm, all the instr in buf will be transformed to RiscV code
    def emitAsm(self, instr: BackendInstr):
        self.buf.append(instr)

    def emitLabel(self, label: Label):
        self.buf.append(Riscv.RiscvLabel(label))

    
    def emitFunc(self):
        self.printer.printComment("start of prologue")
        self.printer.printInstr(Riscv.SPAdd(-self.nextLocalOffset))
        self.printer.printInstr(Riscv.NativeStoreWord(Riscv.FP, Riscv.SP, len(Riscv.CalleeSaved) * 4 + 4))
        self.printer.printInstr(Riscv.Move(Riscv.FP, Riscv.SP))


        # in step9, you need to think about how to store RA here
        # you can get some ideas from how to save CalleeSaved regs
        for i in range(len(Riscv.CalleeSaved)):
            if Riscv.CalleeSaved[i].isUsed():
                self.printer.printInstr(
                    Riscv.NativeStoreWord(Riscv.CalleeSaved[i], Riscv.FP, 4 * i)
                )

        self.printer.printInstr(Riscv.NativeStoreWord(Riscv.RA, Riscv.FP, len(Riscv.CalleeSaved) * 4))

        self.printer.printComment("end of prologue")
        self.printer.println("")

        self.printer.printComment("start of body")

        # in step9, you need to think about how to pass the parameters here
        # you can use the stack or regs

        # using asmcodeprinter to output the RiscV code
        for instr in self.buf:
            self.printer.printInstr(instr)

        self.printer.printComment("end of body")
        self.printer.println("")

        self.printer.printLabel(
            Label(LabelKind.TEMP, self.info.funcLabel.name + Riscv.EPILOGUE_SUFFIX)
        )
        self.printer.printComment("start of epilogue")

        for i in range(len(Riscv.CalleeSaved)):
            if Riscv.CalleeSaved[i].isUsed():
                self.printer.printInstr(
                    Riscv.NativeLoadWord(Riscv.CalleeSaved[i], Riscv.FP, 4 * i)
                )

        self.printer.printInstr(Riscv.NativeLoadWord(Riscv.RA, Riscv.FP, len(Riscv.CalleeSaved) * 4))

        self.printer.printInstr(Riscv.Move(Riscv.SP, Riscv.FP))
        self.printer.printInstr(Riscv.NativeLoadWord(Riscv.FP, Riscv.SP, len(Riscv.CalleeSaved) * 4 + 4))
        self.printer.printInstr(Riscv.SPAdd(self.nextLocalOffset))
        self.printer.printComment("end of epilogue")
        self.printer.println("")

        self.printer.printInstr(Riscv.NativeReturn())
        self.printer.println("")
