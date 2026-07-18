"""Canonical TraceGuard inference kernel."""

from .engine import infer_model
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
]
