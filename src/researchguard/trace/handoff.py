"""Report handoff and consolidation helpers for TraceGuard."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Iterable

from .schema import EvidenceItem, TraceGuardModel


@dataclass(frozen=True)
class TraceHandoff:
    trace_id: str
    lead_id: str
    lead_question: str
    claim_id: str
    status: str
    supporting_evidence_ids: tuple[str, ...] = ()
    limiting_evidence_ids: tuple[str, ...] = ()
    execution_evidence_ids: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    safe_wording: str = ""
    claim_boundary: str = ""
    paragraph_target: str = ""
    next_search_task: str = ""
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
            "lead_id": self.lead_id,
            "lead_question": self.lead_question,
            "claim_id": self.claim_id,
            "status": self.status,
            "supporting_evidence_ids": list(self.supporting_evidence_ids),
            "limiting_evidence_ids": list(self.limiting_evidence_ids),
            "execution_evidence_ids": list(self.execution_evidence_ids),
            "missing_evidence": list(self.missing_evidence),
            "safe_wording": self.safe_wording,
            "claim_boundary": self.claim_boundary,
            "paragraph_target": self.paragraph_target,
            "next_search_task": self.next_search_task,
            "structure_unit_id": self.structure_unit_id,
            "source_unit_id": self.source_unit_id,
            "destination_unit_id": self.destination_unit_id,
            "trace_layer": self.trace_layer,
            "weakest_link": self.weakest_link,
            "conclusion_transfer_status": self.conclusion_transfer_status,
            "downstream_consumer": self.downstream_consumer,
        }


@dataclass(frozen=True)
class ConsolidationFinding:
    finding_id: str
    finding_type: str
    severity: str
    affected_ids: tuple[str, ...]
    rationale: str
    recommendation: str
    evidence_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "finding_id": self.finding_id,
            "finding_type": self.finding_type,
            "severity": self.severity,
            "affected_ids": list(self.affected_ids),
            "rationale": self.rationale,
            "recommendation": self.recommendation,
            "evidence_ids": list(self.evidence_ids),
        }


def _text_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left.lower().strip(), right.lower().strip()).ratio()


def _event_evidence_ids(model: TraceGuardModel, trace_id: str) -> tuple[str, ...]:
    events = model.event_by_id()
    seen: dict[str, None] = {}
    trace = next((item for item in model.traces if item.trace_id == trace_id), None)
    if trace is None:
        return ()
    for event_id in trace.event_ids:
        event = events.get(event_id)
        if event is None:
            continue
        for evidence_id in event.evidence_ids:
            seen[evidence_id] = None
    return tuple(seen)


def derive_trace_handoffs(result: Any) -> tuple[TraceHandoff, ...]:
    handoffs: list[TraceHandoff] = []
    for trace in getattr(result, "traces", ()):
        missing = tuple(f"{gap.gap_id}: {gap.message}" for gap in getattr(trace, "gaps", ()))
        next_task = getattr(trace.gaps[0], "suggested_next_evidence", "") if getattr(trace, "gaps", ()) else ""
        limiting = tuple(
            evidence_id
            for diagnostic in getattr(trace, "diagnostics", ())
            for evidence_id in getattr(diagnostic, "affected_ids", ())
            if str(evidence_id).startswith("ev_")
        )
        execution = tuple(trace.evidence_ids if trace.current_stage in {"operation", "deployed", "deployment"} else ())
        handoffs.append(
            TraceHandoff(
                trace_id=trace.trace_id,
                lead_id=f"lead_{trace.trace_id}",
                lead_question=f"What bounded claim is licensed for {trace.title}?",
                claim_id=f"claim_{trace.trace_id}",
                status=trace.validation_status,
                supporting_evidence_ids=tuple(trace.evidence_ids),
                limiting_evidence_ids=limiting,
                execution_evidence_ids=execution,
                missing_evidence=missing,
                safe_wording=trace.safe_wording,
                claim_boundary=trace.claim_boundary,
                paragraph_target=getattr(trace, "structure_unit_id", "") or f"trace:{trace.trace_id}",
                next_search_task=next_task,
                structure_unit_id=getattr(trace, "structure_unit_id", ""),
                source_unit_id=getattr(trace, "source_unit_id", ""),
                destination_unit_id=getattr(trace, "destination_unit_id", ""),
                trace_layer=getattr(trace, "trace_layer", ""),
                weakest_link=getattr(trace, "weakest_link", ""),
                conclusion_transfer_status=getattr(trace, "conclusion_transfer_status", ""),
                downstream_consumer=getattr(trace, "downstream_consumer", ""),
            )
        )
    return tuple(handoffs)


def review_trace_consolidation(model: TraceGuardModel, result: Any) -> tuple[ConsolidationFinding, ...]:
    findings: list[ConsolidationFinding] = []
    traces = list(model.traces)
    for left_index, left in enumerate(traces):
        for right in traces[left_index + 1:]:
            left_evidence = set(_event_evidence_ids(model, left.trace_id))
            right_evidence = set(_event_evidence_ids(model, right.trace_id))
            shared = tuple(sorted(left_evidence & right_evidence))
            title_similarity = _text_similarity(left.title or left.trace_id, right.title or right.trace_id)
            claim_similarity = _text_similarity(left.claim or left.title, right.claim or right.title)
            if shared and (title_similarity >= 0.86 or claim_similarity >= 0.86):
                findings.append(
                    ConsolidationFinding(
                        finding_id=f"duplicate_lead:{left.trace_id}:{right.trace_id}",
                        finding_type="duplicate_lead",
                        severity="warning",
                        affected_ids=(left.trace_id, right.trace_id),
                        rationale="Two trace leads share evidence and similar wording.",
                        recommendation="Merge the repeated lead, or explain why each lead has a distinct report role.",
                        evidence_ids=shared,
                    )
                )
            elif shared and left.current_stage != right.current_stage:
                findings.append(
                    ConsolidationFinding(
                        finding_id=f"false_friend_lead:{left.trace_id}:{right.trace_id}",
                        finding_type="false_friend_lead",
                        severity="info",
                        affected_ids=(left.trace_id, right.trace_id),
                        rationale="Two trace leads share evidence but differ in stage or boundary.",
                        recommendation="Keep them separate unless the stage and claim boundary are reconciled.",
                        evidence_ids=shared,
                    )
                )
    findings.extend(_review_evidence_duplicates(model.evidence))
    findings.extend(_review_same_class_overclaims(model, result))
    return tuple(findings)


def _review_evidence_duplicates(evidence: Iterable[EvidenceItem]) -> tuple[ConsolidationFinding, ...]:
    findings: list[ConsolidationFinding] = []
    items = list(evidence)
    for left_index, left in enumerate(items):
        left_text = left.normalized_summary or left.raw_text
        for right in items[left_index + 1:]:
            right_text = right.normalized_summary or right.raw_text
            if left.evidence_id == right.evidence_id:
                continue
            if _text_similarity(left_text, right_text) >= 0.94:
                findings.append(
                    ConsolidationFinding(
                        finding_id=f"possible_duplicate_evidence:{left.evidence_id}:{right.evidence_id}",
                        finding_type="possible_duplicate_evidence",
                        severity="info",
                        affected_ids=(left.evidence_id, right.evidence_id),
                        rationale="Two evidence records have near-identical normalized text.",
                        recommendation="Review whether one record should reference the other or whether their roles differ.",
                        evidence_ids=(left.evidence_id, right.evidence_id),
                    )
                )
    return tuple(findings)


def _review_same_class_overclaims(model: TraceGuardModel, result: Any) -> tuple[ConsolidationFinding, ...]:
    evidence_by_id = model.evidence_by_id()
    evaluated_by_id = {trace.trace_id: trace for trace in getattr(result, "traces", ())}
    findings: list[ConsolidationFinding] = []
    review_classes = {
        "patent": ("patent_deployment_review", "Patent evidence cannot carry deployment or operation wording by itself."),
        "hiring": ("hiring_operation_review", "Hiring evidence cannot carry operation wording by itself."),
        "source_only": ("source_only_promotion_review", "Source registry rows must stay separate from trace or final claim evidence."),
    }
    for trace in model.traces:
        evaluated = evaluated_by_id.get(trace.trace_id)
        evidence_ids = _event_evidence_ids(model, trace.trace_id)
        evidence_types = {evidence_by_id[eid].evidence_type for eid in evidence_ids if eid in evidence_by_id}
        for evidence_type, (finding_type, rationale) in review_classes.items():
            if evidence_type in evidence_types:
                findings.append(
                    ConsolidationFinding(
                        finding_id=f"same_class_overclaim:{trace.trace_id}:{evidence_type}",
                        finding_type=finding_type,
                        severity="warning" if evaluated and evaluated.validation_status in {"candidate", "validated"} else "info",
                        affected_ids=(trace.trace_id,),
                        rationale=rationale,
                        recommendation="Review sibling leads before using confirmed, operational, deployed, or validated wording.",
                        evidence_ids=tuple(eid for eid in evidence_ids if evidence_by_id.get(eid) and evidence_by_id[eid].evidence_type == evidence_type),
                    )
                )
    return tuple(findings)
