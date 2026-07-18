"""Stable public result types for TraceGuard evaluation.

These types contain projections from one inference receipt. They do not score,
solve, or import facade modules.
"""

from __future__ import annotations

from dataclasses import dataclass

from .diagnostics import Contradiction, Diagnostic, Gap
from .entity_resolution import EntityScore


@dataclass(frozen=True)
class RuleResult:
    """Canonical explanation projected from one inference factor."""

    rule_id: str
    family: str
    description: str
    weight: float
    violation: float
    loss: float
    affected_object_ids: tuple[str, ...] = ()
    why_it_matters: str = ""
    repair_hint: str = ""
    blocking: bool = False
    affects_validation_status: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "family": self.family,
            "description": self.description,
            "weight": self.weight,
            "violation": round(self.violation, 6),
            "loss": round(self.loss, 6),
            "affected_object_ids": list(self.affected_object_ids),
            "why_it_matters": self.why_it_matters,
            "repair_hint": self.repair_hint,
            "blocking": self.blocking,
            "affects_validation_status": self.affects_validation_status,
        }


@dataclass(frozen=True)
class TraceEvaluation:
    trace_id: str
    title: str
    trace_type: str
    validation_status: str
    support: float
    current_stage: str
    evidence_ids: tuple[str, ...]
    rule_results: tuple[RuleResult, ...]
    diagnostics: tuple[Diagnostic, ...]
    gaps: tuple[Gap, ...]
    contradictions: tuple[Contradiction, ...]
    claim_boundary: str
    safe_wording: str
    unsafe_wording_avoided: str
    structure_unit_id: str = ""
    source_unit_id: str = ""
    destination_unit_id: str = ""
    trace_layer: str = ""
    weakest_link: str = ""
    conclusion_transfer_status: str = ""
    downstream_consumer: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "trace_id": self.trace_id,
            "title": self.title,
            "trace_type": self.trace_type,
            "validation_status": self.validation_status,
            "support": round(self.support, 6),
            "current_stage": self.current_stage,
            "evidence_ids": list(self.evidence_ids),
            "rule_results": [item.to_dict() for item in self.rule_results],
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "gaps": [item.to_dict() for item in self.gaps],
            "contradictions": [item.to_dict() for item in self.contradictions],
            "claim_boundary": self.claim_boundary,
            "safe_wording": self.safe_wording,
            "unsafe_wording_avoided": self.unsafe_wording_avoided,
            "structure_unit_id": self.structure_unit_id,
            "source_unit_id": self.source_unit_id,
            "destination_unit_id": self.destination_unit_id,
            "trace_layer": self.trace_layer,
            "weakest_link": self.weakest_link,
            "conclusion_transfer_status": self.conclusion_transfer_status,
            "downstream_consumer": self.downstream_consumer,
        }


@dataclass(frozen=True)
class EvaluationResult:
    ok: bool
    objective_score: float
    traces: tuple[TraceEvaluation, ...]
    entity_scores: tuple[EntityScore, ...]
    diagnostics: tuple[Diagnostic, ...]
    gaps: tuple[Gap, ...]
    contradictions: tuple[Contradiction, ...]
    inference_receipt: object
    handoffs: tuple[object, ...] = ()
    consolidation_findings: tuple[object, ...] = ()
    storyline_depth: object | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "objective_score": self.objective_score,
            "traces": [trace.to_dict() for trace in self.traces],
            "entity_scores": [score.to_dict() for score in self.entity_scores],
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "gaps": [item.to_dict() for item in self.gaps],
            "contradictions": [item.to_dict() for item in self.contradictions],
            "inference_receipt": (
                self.inference_receipt.to_dict()
                if hasattr(self.inference_receipt, "to_dict")
                else None
            ),
            "handoffs": [
                item.to_dict() for item in self.handoffs if hasattr(item, "to_dict")
            ],
            "consolidation_findings": [
                item.to_dict()
                for item in self.consolidation_findings
                if hasattr(item, "to_dict")
            ],
            "storyline_depth": (
                self.storyline_depth.to_dict()
                if hasattr(self.storyline_depth, "to_dict")
                else None
            ),
        }
