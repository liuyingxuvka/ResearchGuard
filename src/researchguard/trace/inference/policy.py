"""Versioned policy for the one TraceGuard inference authority."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Mapping

from .types import fingerprint


@dataclass(frozen=True)
class InferencePolicy:
    policy_id: str = "researchguard.trace.inference-policy.v2"
    factor_set_id: str = "researchguard.trace.factor-set.v2"
    solver_id: str = "osqp.direct.v1"
    sparsity_weight: float = 0.12
    evidence_support_weight: float = 1.0
    independent_source_weight: float = 0.6
    entity_weight: float = 0.45
    temporal_weight: float = 0.8
    stage_weight: float = 0.8
    hypothesis_support_weight: float = 1.0
    hypothesis_opposition_weight: float = 1.15
    alternative_competition_weight: float = 0.75
    mechanism_weight: float = 0.9
    chronology_weight: float = 0.9
    confounder_weight: float = 1.0
    causal_scope_weight: float = 0.8
    validated_threshold: float = 0.75
    candidate_threshold: float = 0.40
    weak_signal_threshold: float = 0.18
    causal_supported_threshold: float = 0.68
    causal_contested_threshold: float = 0.38
    alternative_live_margin: float = 0.12
    binding_constraint_tolerance: float = 1e-5
    eps_abs: float = 1e-7
    eps_rel: float = 1e-7
    max_iter: int = 100_000
    polish: bool = True
    maximum_primal_residual: float = 1e-5
    maximum_dual_residual: float = 1e-5
    maximum_constraint_violation: float = 1e-5
    accepted_statuses: tuple[str, ...] = ("solved", "solved inaccurate")
    evidence_type_strength: Mapping[str, float] = field(
        default_factory=lambda: {
            "funding_award": 0.95,
            "funding_awarded": 0.95,
            "contract_award": 0.95,
            "official_project_page": 0.90,
            "company_announcement": 0.82,
            "tender_notice": 0.72,
            "procurement": 0.72,
            "design_note": 0.68,
            "log_entry": 0.78,
            "issue": 0.72,
            "pr": 0.82,
            "meeting_note": 0.70,
            "news": 0.42,
            "patent": 0.32,
            "hiring": 0.28,
            "keyword_hit": 0.20,
            "source_only": 0.08,
            "unknown": 0.25,
        }
    )

    @property
    def policy_fingerprint(self) -> str:
        return fingerprint(asdict(self))

    @property
    def solver_configuration_fingerprint(self) -> str:
        return fingerprint(
            {
                "solver_id": self.solver_id,
                "eps_abs": self.eps_abs,
                "eps_rel": self.eps_rel,
                "max_iter": self.max_iter,
                "polish": self.polish,
                "maximum_primal_residual": self.maximum_primal_residual,
                "maximum_dual_residual": self.maximum_dual_residual,
                "maximum_constraint_violation": self.maximum_constraint_violation,
                "accepted_statuses": self.accepted_statuses,
            }
        )


DEFAULT_POLICY = InferencePolicy()
