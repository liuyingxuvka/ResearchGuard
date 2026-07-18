"""Canonical immutable types for the TraceGuard HL-MRF/MAP kernel."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from math import isfinite
from typing import Any, Mapping


class InferenceError(RuntimeError):
    """Base error for fail-closed inference."""


class CompilationError(InferenceError):
    """Raised when a model cannot compile into one canonical problem."""


class SolverError(InferenceError):
    """Raised when the only configured solver does not produce valid evidence."""


def _canonical(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return _canonical(value.to_dict())
    if hasattr(value, "__dataclass_fields__"):
        return _canonical(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("non-finite values cannot be canonically serialized")
        return round(value, 12)
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        _canonical(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def fingerprint(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ObservedAtom:
    atom_id: str
    value: float
    kind: str
    object_id: str
    evidence_ids: tuple[str, ...] = ()
    lineage_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.value) <= 1.0:
            raise ValueError(f"observed atom {self.atom_id} must be in [0, 1]")

    def to_dict(self) -> dict[str, Any]:
        return _canonical(asdict(self))


@dataclass(frozen=True)
class LatentAtom:
    atom_id: str
    kind: str
    object_id: str
    lower: float = 0.0
    upper: float = 1.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.lower) <= float(self.upper) <= 1.0:
            raise ValueError(f"invalid bounds for latent atom {self.atom_id}")

    def to_dict(self) -> dict[str, Any]:
        return _canonical(asdict(self))


@dataclass(frozen=True)
class LinearExpression:
    terms: tuple[tuple[str, float], ...] = ()
    constant: float = 0.0

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for atom_id, coefficient in self.terms:
            if atom_id in seen:
                raise ValueError(f"duplicate term {atom_id}; combine coefficients first")
            if not isfinite(float(coefficient)):
                raise ValueError(f"non-finite coefficient for {atom_id}")
            seen.add(atom_id)
        if not isfinite(float(self.constant)):
            raise ValueError("linear expression constant must be finite")

    def value(self, atom_values: Mapping[str, float]) -> float:
        return float(self.constant) + sum(
            float(coefficient) * float(atom_values[atom_id])
            for atom_id, coefficient in self.terms
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "terms": [[atom_id, coefficient] for atom_id, coefficient in self.terms],
            "constant": self.constant,
        }


@dataclass(frozen=True)
class HingeFactor:
    factor_id: str
    family: str
    description: str
    expression: LinearExpression
    weight: float
    power: int = 2
    affected_object_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    direction: str = "regularize"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if float(self.weight) <= 0 or not isfinite(float(self.weight)):
            raise ValueError(f"factor {self.factor_id} weight must be positive and finite")
        if self.power not in {1, 2}:
            raise ValueError(f"factor {self.factor_id} power must be 1 or 2")

    def violation(self, atom_values: Mapping[str, float]) -> float:
        return max(0.0, self.expression.value(atom_values))

    def loss(self, atom_values: Mapping[str, float]) -> float:
        violation = self.violation(atom_values)
        return float(self.weight) * violation**self.power

    def to_dict(self) -> dict[str, Any]:
        return _canonical(asdict(self))


@dataclass(frozen=True)
class HardConstraint:
    constraint_id: str
    description: str
    expression: LinearExpression
    lower: float | None = None
    upper: float | None = None
    affected_object_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.lower is None and self.upper is None:
            raise ValueError(f"constraint {self.constraint_id} has no bound")
        if self.lower is not None and not isfinite(float(self.lower)):
            raise ValueError(f"constraint {self.constraint_id} lower bound is non-finite")
        if self.upper is not None and not isfinite(float(self.upper)):
            raise ValueError(f"constraint {self.constraint_id} upper bound is non-finite")
        if (
            self.lower is not None
            and self.upper is not None
            and float(self.lower) > float(self.upper)
        ):
            raise ValueError(f"constraint {self.constraint_id} has inverted bounds")

    def violation(self, atom_values: Mapping[str, float]) -> float:
        value = self.expression.value(atom_values)
        below = 0.0 if self.lower is None else max(0.0, float(self.lower) - value)
        above = 0.0 if self.upper is None else max(0.0, value - float(self.upper))
        return max(below, above)

    def to_dict(self) -> dict[str, Any]:
        return _canonical(asdict(self))


@dataclass(frozen=True)
class CompiledProblem:
    schema_id: str
    policy_id: str
    factor_set_id: str
    solver_id: str
    observed_atoms: tuple[ObservedAtom, ...]
    latent_atoms: tuple[LatentAtom, ...]
    factors: tuple[HingeFactor, ...]
    hard_constraints: tuple[HardConstraint, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        observed_ids = [atom.atom_id for atom in self.observed_atoms]
        latent_ids = [atom.atom_id for atom in self.latent_atoms]
        if len(observed_ids) != len(set(observed_ids)):
            raise CompilationError("observed atom ids must be unique")
        if len(latent_ids) != len(set(latent_ids)):
            raise CompilationError("latent atom ids must be unique")
        overlap = set(observed_ids) & set(latent_ids)
        if overlap:
            raise CompilationError(f"atom ids cannot be both observed and latent: {sorted(overlap)}")
        known = set(observed_ids) | set(latent_ids)
        for owner in (*self.factors, *self.hard_constraints):
            unknown = {atom_id for atom_id, _ in owner.expression.terms} - known
            if unknown:
                raise CompilationError(
                    f"{getattr(owner, 'factor_id', getattr(owner, 'constraint_id', 'owner'))} "
                    f"references unknown atoms {sorted(unknown)}"
                )

    @property
    def problem_fingerprint(self) -> str:
        return fingerprint(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "policy_id": self.policy_id,
            "factor_set_id": self.factor_set_id,
            "solver_id": self.solver_id,
            "observed_atoms": [item.to_dict() for item in self.observed_atoms],
            "latent_atoms": [item.to_dict() for item in self.latent_atoms],
            "factors": [item.to_dict() for item in self.factors],
            "hard_constraints": [item.to_dict() for item in self.hard_constraints],
            "metadata": _canonical(self.metadata),
        }


@dataclass(frozen=True)
class InferenceSolution:
    backend: str
    backend_version: str
    status: str
    objective: float
    atom_values: Mapping[str, float]
    primal_residual: float
    dual_residual: float
    maximum_constraint_violation: float
    iterations: int
    run_time_seconds: float
    problem_fingerprint: str

    @property
    def solution_fingerprint(self) -> str:
        return fingerprint(
            {
                "backend": self.backend,
                "backend_version": self.backend_version,
                "status": self.status,
                "objective": self.objective,
                "atom_values": self.atom_values,
                "problem_fingerprint": self.problem_fingerprint,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return _canonical(asdict(self))


@dataclass(frozen=True)
class FactorContribution:
    factor_id: str
    family: str
    direction: str
    violation: float
    loss: float
    affected_object_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return _canonical(asdict(self))


@dataclass(frozen=True)
class TraceProjection:
    trace_id: str
    support: float
    validation_status: str
    current_stage: str
    evidence_ids: tuple[str, ...]
    top_support_factor_ids: tuple[str, ...]
    top_opposition_factor_ids: tuple[str, ...]
    binding_constraint_ids: tuple[str, ...]
    claim_boundary: str
    safe_wording: str
    unsafe_wording_avoided: str

    def to_dict(self) -> dict[str, Any]:
        return _canonical(asdict(self))


@dataclass(frozen=True)
class HypothesisProjection:
    hypothesis_id: str
    support: float
    rank: int
    live: bool
    causal_support: float | None
    causal_status: str
    top_support_factor_ids: tuple[str, ...]
    top_opposition_factor_ids: tuple[str, ...]
    claim_boundary: str

    def to_dict(self) -> dict[str, Any]:
        return _canonical(asdict(self))


@dataclass(frozen=True)
class InferenceReceipt:
    receipt_id: str
    problem_fingerprint: str
    solution_fingerprint: str
    atom_values_fingerprint: str
    factor_catalog_fingerprint: str
    hard_constraint_catalog_fingerprint: str
    provenance_fingerprint: str
    schema_id: str
    policy_id: str
    factor_set_id: str
    solver_id: str
    solver_configuration_fingerprint: str
    solver_backend: str
    solver_backend_version: str
    solver_status: str
    primal_residual: float
    dual_residual: float
    maximum_constraint_violation: float
    iterations: int
    objective: float
    hard_constraint_ids: tuple[str, ...]
    contributions: tuple[FactorContribution, ...]
    trace_projections: tuple[TraceProjection, ...]
    hypothesis_projections: tuple[HypothesisProjection, ...]
    diagnostics: tuple[Any, ...]
    gaps: tuple[Any, ...]
    contradictions: tuple[Any, ...]
    claim_boundary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "problem_fingerprint": self.problem_fingerprint,
            "solution_fingerprint": self.solution_fingerprint,
            "atom_values_fingerprint": self.atom_values_fingerprint,
            "factor_catalog_fingerprint": self.factor_catalog_fingerprint,
            "hard_constraint_catalog_fingerprint": self.hard_constraint_catalog_fingerprint,
            "provenance_fingerprint": self.provenance_fingerprint,
            "schema_id": self.schema_id,
            "policy_id": self.policy_id,
            "factor_set_id": self.factor_set_id,
            "solver_id": self.solver_id,
            "solver_configuration_fingerprint": self.solver_configuration_fingerprint,
            "solver_backend": self.solver_backend,
            "solver_backend_version": self.solver_backend_version,
            "solver_status": self.solver_status,
            "primal_residual": round(self.primal_residual, 12),
            "dual_residual": round(self.dual_residual, 12),
            "maximum_constraint_violation": round(
                self.maximum_constraint_violation, 12
            ),
            "iterations": self.iterations,
            "objective": round(self.objective, 12),
            "hard_constraint_ids": list(self.hard_constraint_ids),
            "contributions": [item.to_dict() for item in self.contributions],
            "trace_projections": [item.to_dict() for item in self.trace_projections],
            "hypothesis_projections": [
                item.to_dict() for item in self.hypothesis_projections
            ],
            "diagnostics": [
                item.to_dict() if hasattr(item, "to_dict") else _canonical(item)
                for item in self.diagnostics
            ],
            "gaps": [
                item.to_dict() if hasattr(item, "to_dict") else _canonical(item)
                for item in self.gaps
            ],
            "contradictions": [
                item.to_dict() if hasattr(item, "to_dict") else _canonical(item)
                for item in self.contradictions
            ],
            "claim_boundary": self.claim_boundary,
        }
