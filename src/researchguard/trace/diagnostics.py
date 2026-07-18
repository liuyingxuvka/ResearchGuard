"""TraceGuard diagnostics and ledgers.

Purpose: Represent hard-gate findings, gaps, contradictions, and repair hints.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: TraceGuard
Math boundary: Diagnostics explain rule and gate status, not factual certainty.
CLI: researchguard trace diagnose <model.yaml>
Boundary: Blocking diagnostics prevent validation wording but do not prove the opposite fact.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Diagnostic:
    diagnostic_id: str
    severity: str
    message: str
    affected_object_ids: tuple[str, ...] = ()
    blocking: bool = False
    repair_hint: str = ""
    family: str = "diagnostic"

    def to_dict(self) -> dict[str, object]:
        return {
            "diagnostic_id": self.diagnostic_id,
            "severity": self.severity,
            "message": self.message,
            "affected_object_ids": list(self.affected_object_ids),
            "blocking": self.blocking,
            "repair_hint": self.repair_hint,
            "family": self.family,
        }


@dataclass(frozen=True)
class Gap:
    gap_id: str
    severity: str
    message: str
    trace_id: str | None = None
    suggested_next_evidence: str = ""
    blocking: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "gap_id": self.gap_id,
            "severity": self.severity,
            "message": self.message,
            "trace_id": self.trace_id,
            "suggested_next_evidence": self.suggested_next_evidence,
            "blocking": self.blocking,
        }


@dataclass(frozen=True)
class Contradiction:
    contradiction_id: str
    severity: str
    message: str
    affected_object_ids: tuple[str, ...]
    blocking: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "contradiction_id": self.contradiction_id,
            "severity": self.severity,
            "message": self.message,
            "affected_object_ids": list(self.affected_object_ids),
            "blocking": self.blocking,
        }
