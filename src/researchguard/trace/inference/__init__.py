"""Canonical TraceGuard inference kernel."""

from .engine import infer_model
from .contradiction_core import (
    ConsistencyOracle,
    ContradictionCore,
    ContradictionCoreStatus,
    find_deletion_minimal_contradiction_core,
)
from .policy import DEFAULT_POLICY, InferencePolicy
from .types import (
    CompiledProblem,
    FactorContribution,
    HardConstraint,
    HingeFactor,
    InferenceReceipt,
    InferenceSolution,
    LatentAtom,
    LinearExpression,
    ObservedAtom,
)

__all__ = [
    "CompiledProblem",
    "ConsistencyOracle",
    "ContradictionCore",
    "ContradictionCoreStatus",
    "DEFAULT_POLICY",
    "FactorContribution",
    "HardConstraint",
    "HingeFactor",
    "InferencePolicy",
    "InferenceReceipt",
    "InferenceSolution",
    "LatentAtom",
    "LinearExpression",
    "ObservedAtom",
    "infer_model",
    "find_deletion_minimal_contradiction_core",
]
