from typing import Final, Optional

from utils.label.funclabel import FuncLabel
from utils.label.label import Label, LabelKind
from utils.tac.reg import Reg
from utils.tac.tacop import InstrKind
from utils.tac.temp import Temp
from utils.tac.backendinstr import BackendInstr

from enum import Enum, auto, unique

WORD_SIZE: Final[int] = 4  # in bytes
MAX_INT: Final[int] = 0x7FFF_FFFF


@unique
class RvUnaryOp(Enum):
    NEG = auto()
    SNEZ = auto()
    NOT = auto()
    SEQZ = auto()

@unique
class RvBinaryOp(Enum):
    ADD = auto()
    OR = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    REM = auto()
    AND = auto()
    XOR = auto()
    SLT = auto()

class Riscv:

    ZERO = Reg(0, "x0")  # always zero
    RA = Reg(1, "ra")  # return address
    SP = Reg(2, "sp")  # stack pointer
    GP = Reg(3, "gp")  # global pointer
    TP = Reg(4, "tp")  # thread pointer
    T0 = Reg(5, "t0")
    T1 = Reg(6, "t1")
    T2 = Reg(7, "t2")
    FP = Reg(8, "fp")  # frame pointer
    S1 = Reg(9, "s1")
    A0 = Reg(10, "a0")
    A1 = Reg(11, "a1")
    A2 = Reg(12, "a2")
    A3 = Reg(13, "a3")
    A4 = Reg(14, "a4")
    A5 = Reg(15, "a5")
    A6 = Reg(16, "a6")
    A7 = Reg(17, "a7")
    S2 = Reg(18, "s2")
    S3 = Reg(19, "s3")
    S4 = Reg(20, "s4")
    S5 = Reg(21, "s5")
    S6 = Reg(22, "s6")
    S7 = Reg(23, "s7")
    S8 = Reg(24, "s8")
    S9 = Reg(25, "s9")
    S10 = Reg(26, "s10")
    S11 = Reg(27, "s11")
    T3 = Reg(28, "t3")
    T4 = Reg(29, "t4")
    T5 = Reg(30, "t5")
    T6 = Reg(31, "t6")

    CallerSaved = [T0, T1, T2, T3, T4, T5, T6, A0, A1, A2, A3, A4, A5, A6, A7]

    CalleeSaved = [S1, S2, S3, S4, S5, S6, S7, S8, S9, S10, S11]

    AllocatableRegs = CallerSaved + CalleeSaved

    ArgRegs = [A0, A1, A2, A3, A4, A5, A6, A7]

    EPILOGUE_SUFFIX = "_exit"

    FMT1 = "{}"
    FMT2 = "{}, {}"
    FMT3 = "{}, {}, {}"
    FMT_OFFSET = "{}, {}({})"
    # Todo FMT4

    class JumpToEpilogue(BackendInstr):
        def __init__(self, label: Label) -> None:
            super().__init__(
                InstrKind.RET,
                [],
                [],
                Label(LabelKind.TEMP, label.name + Riscv.EPILOGUE_SUFFIX),
            )

        def __str__(self) -> str:
            return "j " + str(self.label)

    class RiscvLabel(BackendInstr):
        def __init__(self, label: Label) -> None:
            super().__init__(InstrKind.LABEL, [], [], label)

        def __str__(self) -> str:
            return str(self.label) + ":"

        def isLabel(self) -> bool:
            return True

    class LoadImm(BackendInstr):
        def __init__(self, dst: Temp, value: int) -> None:
            super().__init__(InstrKind.SEQ, [dst], [], None)
            self.value = value

        def __str__(self) -> str:
            return "li " + Riscv.FMT2.format(str(self.dsts[0]), self.value)

    class LoadAddr(BackendInstr):
        def __init__(self, dst: Temp, label: Label) -> None:
            super().__init__(InstrKind.SEQ, [dst], [], None)
            self.label = label

        def __str__(self) -> str:
            return "la " + Riscv.FMT2.format(str(self.dsts[0]), str(self.label))
        
    class LoadWord(BackendInstr):
        def __init__(self, dst: Temp, src: Temp, offset: int) -> None:
            super().__init__(InstrKind.SEQ, [dst], [src], None)
            self.offset = offset

        def __str__(self) -> str:
            return "lw " + Riscv.FMT_OFFSET.format(str(self.dsts[0]), str(self.offset), str(self.srcs[0]))
        
    class StoreWord(BackendInstr):
        def __init__(self, src: Temp, dst: Temp, offset: int) -> None:
            super().__init__(InstrKind.SEQ, [], [src, dst], None)
            self.offset = offset

        def __str__(self) -> str:
            return "sw " + Riscv.FMT_OFFSET.format(str(self.srcs[0]), str(self.offset), str(self.srcs[1]))

    class AllocStack(BackendInstr):
        def __init__(self, offset: int) -> None:
            super().__init__(InstrKind.SEQ, [], [], None)
            self.offset = offset

        def __str__(self) -> str:
            return "addi " + Riscv.FMT3.format(str(Riscv.SP), str(Riscv.SP), str(-self.offset))

    class Move(BackendInstr):
        def __init__(self, dst: Temp, src: Temp) -> None:
            super().__init__(InstrKind.SEQ, [dst], [src], None)

        def __str__(self) -> str:
            return "mv " + Riscv.FMT2.format(str(self.dsts[0]), str(self.srcs[0]))

    class Unary(BackendInstr):
        def __init__(self, op: RvUnaryOp, dst: Temp, src: Temp) -> None:
            super().__init__(InstrKind.SEQ, [dst], [src], None)
            self.op = op.__str__()[10:].lower()

        def __str__(self) -> str:
            return "{} ".format(self.op) + Riscv.FMT2.format(
                str(self.dsts[0]), str(self.srcs[0])
            )

    class Call(BackendInstr):
        def __init__(self, dst: Temp, label: FuncLabel, args: list[Temp]) -> None:
            super().__init__(InstrKind.CALL, [dst], args, label)
            self.args = args
            
        def __str__(self) -> str:
            return "call " + str(self.label.name)

    class Binary(BackendInstr):
        def __init__(self, op: RvBinaryOp, dst: Temp, src0: Temp, src1: Temp) -> None:
            super().__init__(InstrKind.SEQ, [dst], [src0, src1], None)
            self.op = op.__str__()[11:].lower()

        def __str__(self) -> str:
            return "{} ".format(self.op) + Riscv.FMT3.format(
                str(self.dsts[0]), str(self.srcs[0]), str(self.srcs[1])
            )
    
    class Branch(BackendInstr):
        def __init__(self, cond: Temp, target: Label) -> None:
            super().__init__(InstrKind.COND_JMP, [], [cond], target)
            self.target = target
        
        def __str__(self) -> str:
            return "beq " + Riscv.FMT3.format(str(Riscv.ZERO), str(self.srcs[0]), str(self.target))

    class Jump(BackendInstr):
        def __init__(self, target: Label) -> None:
            super().__init__(InstrKind.JMP, [], [], target)
            self.target = target
        
        def __str__(self) -> str:
            return "j " + str(self.target)

    class SPAdd(BackendInstr):
        def __init__(self, offset: int) -> None:
            super().__init__(InstrKind.SEQ, [], [], None)
            self.offset = offset

        def __str__(self) -> str:
            assert -2048 <= self.offset <= 2047  # Riscv imm [11:0]
            return "addi " + Riscv.FMT3.format(
                str(Riscv.SP), str(Riscv.SP), str(self.offset)
            )

    class NativeStoreWord(BackendInstr):
        def __init__(self, src: Reg, base: Reg, offset: int) -> None:
            super().__init__(InstrKind.SEQ, [], [], None)
            self.src = src
            self.base = base
            self.offset = offset

        def __str__(self) -> str:
            assert -2048 <= self.offset <= 2047  # Riscv imm [11:0]
            return "sw " + Riscv.FMT_OFFSET.format(
                str(self.src), str(self.offset), str(self.base)
            )

    class NativeLoadWord(BackendInstr):
        def __init__(self, dst: Reg, base: Reg, offset: int) -> None:
            super().__init__(InstrKind.SEQ, [], [], None)
            self.dst = dst
            self.base = base
            self.offset = offset

        def __str__(self) -> str:
            assert -2048 <= self.offset <= 2047  # Riscv imm [11:0]
            return "lw " + Riscv.FMT_OFFSET.format(
                str(self.dst), str(self.offset), str(self.base)
            )

    class NativeReturn(BackendInstr):
        def __init__(self) -> None:
            super().__init__(InstrKind.RET, [], [], None)

        def __str__(self) -> str:
            return "ret"
