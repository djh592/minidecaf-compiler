from enum import Enum, auto, unique


# Kinds of instructions.
@unique
class InstrKind(Enum):
    # Labels.
    LABEL = auto()
    # Sequential instructions (unary operations, binary operations, etc).
    SEQ = auto()
    # Branching instructions.
    JMP = auto()
    # Branching with conditions.
    COND_JMP = auto()
    # Return instruction.
    RET = auto()
    # Call instruction.
    CALL = auto()


# Kinds of unary operations.
@unique
class TacUnaryOp(Enum):
    NEG = auto()
    NOT = auto()
    LNOT = auto()

# Kinds of binary operations.
@unique
class TacBinaryOp(Enum):
    ADD = auto()
    LOR = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    MOD = auto()
    LAND = auto()
    EQU = auto()
    NEQ = auto()
    SLT = auto()
    LEQ = auto()
    SGT = auto()
    GEQ = auto()


# Kinds of branching with conditions.
@unique
class CondBranchOp(Enum):
    BEQ = auto()
    BNE = auto()
