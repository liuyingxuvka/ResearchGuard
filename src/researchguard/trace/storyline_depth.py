"""Model-derived storyline-depth analysis for TraceGuard.

The module perturbs the current TraceGuard model, not storage order or a fixed
historical fixture.  Results describe local model behavior under declared
changes; they never establish factual or causal truth.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Iterable

from .schema import (
    EvidenceItem,
    EventCandidate,
    SourceRecord,
    StorylineHypothesis,
    TimeInterval,
    TraceCandidate,
    TraceGuardModel,
    clamp01,
)
from .stage_model import ORDERED_STAGE_INDEX, stage_for_event


CRITICAL_PERTURBATION_THRESHOLD = 2.0
CRITICAL_OBJECT_IMPORTANCE_THRESHOLD = 0.6
RESOLVED_CONFOUNDER_STATUSES = {"addressed", "not_applicable"}


@dataclass(frozen=True)
class HypothesisSnapshot:
    hypothesis_id: str
    rank: int
    score: float
    confidence: float
    event_support: int
    evidence_support: int
    contradiction_count: int
    gap_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StorylineAlternative:
    hypothesis_id: str
    alternative_ids: tuple[str, ...] = ()
    out_of_scope_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "alternative_ids": list(self.alternative_ids),
            "out_of_scope_reason": self.out_of_scope_reason,
        }


@dataclass(frozen=True)
class PerturbationPlanItem:
    perturbation_id: str
    kind: str
    target_hypothesis_id: str = ""
    target_trace_id: str = ""
    target_event_id: str = ""
    target_evidence_id: str = ""
    declared_perturbation_id: str = ""
    expected_sensitivity_id: str = ""
    priority_score: float = 0.0
    reasons: tuple[str, ...] = ()
    expected_effect: str = "challenge_storyline_support"
    model_derived: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["reasons"] = list(self.reasons)
        return data


@dataclass(frozen=True)
class PerturbationEffect:
    perturbation: PerturbationPlanItem
    before: tuple[HypothesisSnapshot, ...]
    after: tuple[HypothesisSnapshot, ...]
    deltas: dict[str, dict[str, Any]]
    effective: bool
    informative_null: bool
    counts_toward_depth: bool
    baseline_inference_receipt_id: str = ""
    perturbed_inference_receipt_id: str = ""
    baseline_problem_fingerprint: str = ""
    perturbed_problem_fingerprint: str = ""
    baseline_solver_id: str = ""
    perturbed_solver_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "perturbation": self.perturbation.to_dict(),
            "before": [item.to_dict() for item in self.before],
            "after": [item.to_dict() for item in self.after],
            "deltas": self.deltas,
            "effective": self.effective,
            "informative_null": self.informative_null,
            "counts_toward_depth": self.counts_toward_depth,
            "baseline_inference_receipt_id": self.baseline_inference_receipt_id,
            "perturbed_inference_receipt_id": self.perturbed_inference_receipt_id,
            "baseline_problem_fingerprint": self.baseline_problem_fingerprint,
            "perturbed_problem_fingerprint": self.perturbed_problem_fingerprint,
            "baseline_solver_id": self.baseline_solver_id,
            "perturbed_solver_id": self.perturbed_solver_id,
        }


@dataclass(frozen=True)
class StorylineDepthReceipt:
    schema_version: str
    receipt_id: str
    model_fingerprint: str
    baseline: dict[str, Any]
    hypotheses: tuple[dict[str, Any], ...]
    alternatives: tuple[StorylineAlternative, ...]
    causal_coverage: tuple[dict[str, Any], ...]
    object_universe_fingerprint: str
    object_coverage_counts: dict[str, int]
    object_depth_rows: tuple[dict[str, Any], ...]
    temporal_coverage: tuple[dict[str, Any], ...]
    native_obligation_evidence: tuple[dict[str, Any], ...]
    perturbation_plan: tuple[PerturbationPlanItem, ...]
    effects: tuple[PerturbationEffect, ...]
    unresolved_gaps: tuple[dict[str, Any], ...]
    untested_high_impact: tuple[dict[str, Any], ...]
    candidate_universe_fingerprint: str
    critical_threshold: float
    coverage_counts: dict[str, int]
    coverage_by_kind: tuple[dict[str, Any], ...]
    critical_uncovered_ids: tuple[str, ...]
    critical_ineffective_ids: tuple[str, ...]
    sensitivity_mismatch_ids: tuple[str, ...]
    effective_perturbation_count: int
    requested_claim_scope: str
    covered_claim_scope: str
    broad_claim_licensed: bool
    predictive_holdout_status: str
    predictive_claim_licensed: bool
    closure_status: str
    claim_boundary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "model_fingerprint": self.model_fingerprint,
            "baseline": self.baseline,
            "hypotheses": list(self.hypotheses),
            "alternatives": [item.to_dict() for item in self.alternatives],
            "causal_coverage": list(self.causal_coverage),
            "object_universe_fingerprint": self.object_universe_fingerprint,
            "object_coverage_counts": self.object_coverage_counts,
            "object_depth_rows": list(self.object_depth_rows),
            "temporal_coverage": list(self.temporal_coverage),
            "native_obligation_evidence": list(self.native_obligation_evidence),
            "perturbation_plan": [item.to_dict() for item in self.perturbation_plan],
            "effects": [item.to_dict() for item in self.effects],
            "unresolved_gaps": list(self.unresolved_gaps),
            "untested_high_impact": list(self.untested_high_impact),
            "candidate_universe_fingerprint": self.candidate_universe_fingerprint,
            "critical_threshold": self.critical_threshold,
            "coverage_counts": self.coverage_counts,
            "coverage_by_kind": list(self.coverage_by_kind),
            "critical_uncovered_ids": list(self.critical_uncovered_ids),
            "critical_ineffective_ids": list(self.critical_ineffective_ids),
            "sensitivity_mismatch_ids": list(self.sensitivity_mismatch_ids),
            "effective_perturbation_count": self.effective_perturbation_count,
            "requested_claim_scope": self.requested_claim_scope,
            "covered_claim_scope": self.covered_claim_scope,
            "broad_claim_licensed": self.broad_claim_licensed,
            "predictive_holdout_status": self.predictive_holdout_status,
            "predictive_claim_licensed": self.predictive_claim_licensed,
            "closure_status": self.closure_status,
            "claim_boundary": self.claim_boundary,
        }


def _model_fingerprint(model: TraceGuardModel) -> str:
    payload = json.dumps(asdict(model), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _native_obligation_observations(
    model: TraceGuardModel,
    hypotheses: tuple[StorylineHypothesis, ...],
    object_depth_rows: tuple[dict[str, Any], ...],
    plan: tuple[PerturbationPlanItem, ...],
    effects: tuple[PerturbationEffect, ...],
) -> tuple[dict[str, Any], ...]:
    """Bind every native depth obligation to exact target-owned artifacts.

    Counts and object names remain useful summaries, but they cannot prove
    which current event/evidence/perturbation discharged an obligation.  These
    observations preserve the exact semantic content and its hash so a
    supervisor can verify the native judgment without recomputing it.
    """

    object_maps: dict[str, dict[str, object]] = {
        "hypothesis": {item.hypothesis_id: item for item in hypotheses},
        "trace": {item.trace_id: item for item in model.traces},
        "event": {item.event_id: item for item in model.events},
        "evidence": {item.evidence_id: item for item in model.evidence},
        "mechanism": {item.mechanism_id: item for item in model.causal_mechanisms},
        "confounder": {item.confounder_id: item for item in model.confounder_reviews},
        "ablation": {item.ablation_id: item for item in model.evidence_ablations},
        "expected_sensitivity": {
            item.sensitivity_id: item for item in model.expected_sensitivities
        },
        "source": {item.source_id: item for item in model.sources},
    }

    def artifact_row(kind: str, object_id: str) -> dict[str, Any] | None:
        value = object_maps.get(kind, {}).get(object_id)
        if value is None:
            return None
        content = asdict(value)
        return {
            "artifact_ref": f"traceguard:{kind}:{object_id}",
            "artifact_sha256": _canonical_sha256(content),
            "artifact_kind": kind,
            "artifact_id": object_id,
        }

    observations: list[dict[str, Any]] = []
    for row in object_depth_rows:
        object_type = str(row.get("object_type", ""))
        object_id = str(row.get("object_id", ""))
        artifact_rows: dict[str, dict[str, Any]] = {}

        def include(kind: str, item_id: str) -> None:
            artifact = artifact_row(kind, item_id)
            if artifact:
                artifact_rows[str(artifact["artifact_ref"])] = artifact

        include(object_type, object_id)
        for trace_id in row.get("trace_ids", []):
            include("trace", str(trace_id))
        for event_id in row.get("event_ids", []):
            include("event", str(event_id))
        for evidence_id in row.get("evidence_ids", []):
            evidence_id = str(evidence_id)
            include("evidence", evidence_id)
            evidence = object_maps["evidence"].get(evidence_id)
            if evidence is not None:
                include("source", str(getattr(evidence, "source_id", "")))
        if object_type == "evidence":
            include("source", str(row.get("source_id", "")))

        content = {
            "object_depth_row": row,
            "artifact_evidence": [artifact_rows[key] for key in sorted(artifact_rows)],
        }
        obligation_ids = ["obligation:traceguard-object-depth"]
        if object_type == "trace":
            obligation_ids.append("obligation:traceguard-temporal-depth")
        observations.append(
            {
                "native_object_id": f"{object_type}:{object_id}",
                "target_obligation_ids": obligation_ids,
                "evidence_ref": f"traceguard:depth-object:{object_type}:{object_id}",
                "evidence_sha256": _canonical_sha256(content),
                "content": content,
            }
        )

    effect_by_id = {
        effect.perturbation.perturbation_id: effect
        for effect in effects
    }
    for planned in plan:
        effect = effect_by_id.get(planned.perturbation_id)
        content = {
            "plan": planned.to_dict(),
            "effect": effect.to_dict() if effect is not None else None,
        }
        observations.append(
            {
                "native_object_id": f"perturbation:{planned.perturbation_id}",
                "target_obligation_ids": ["obligation:traceguard-perturbation-depth"],
                "evidence_ref": f"traceguard:perturbation:{planned.perturbation_id}",
                "evidence_sha256": _canonical_sha256(content),
                "content": content,
            }
        )
    return tuple(observations)


def _event_time_token(event: EventCandidate) -> str:
    if event.time_interval is None or event.time_interval.precision == "unknown":
        return ""
    return str(
        event.time_interval.start
        or event.time_interval.end
        or event.time_interval.text
        or ""
    ).strip()


def _ordered_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _ratio(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return min(1.0, max(0.0, parsed))


def _longest_unqualified_run(
    ordered_ids: list[str],
    qualified_ids: set[str],
) -> int:
    longest = 0
    current = 0
    for item_id in ordered_ids:
        if item_id in qualified_ids:
            current = 0
        else:
            current += 1
            longest = max(longest, current)
    return longest


def _object_depth_coverage(
    model: TraceGuardModel,
    hypotheses: tuple[StorylineHypothesis, ...],
    *,
    requested_claim_scope: str = "broad",
) -> tuple[str, dict[str, int], tuple[dict[str, Any], ...], tuple[dict[str, Any], ...], list[dict[str, Any]]]:
    """Build a fingerprinted, target-owned object and temporal denominator."""

    hypothesis_by_id = {item.hypothesis_id: item for item in hypotheses}
    trace_by_id = {item.trace_id: item for item in model.traces}
    event_by_id = model.event_by_id()
    evidence_by_id = model.evidence_by_id()
    source_ids = {item.source_id for item in model.sources}
    critical_hypothesis_ids = {
        item.hypothesis_id
        for item in hypotheses
        if item.importance >= CRITICAL_OBJECT_IMPORTANCE_THRESHOLD
    }
    critical_trace_ids = {
        item.trace_id
        for item in model.traces
        if item.importance >= CRITICAL_OBJECT_IMPORTANCE_THRESHOLD
    }
    for hypothesis in hypotheses:
        if hypothesis.hypothesis_id in critical_hypothesis_ids:
            critical_trace_ids.update(hypothesis.trace_ids)
    if requested_claim_scope == "broad":
        # Every explicit trace participates in a broad storyline claim.  A
        # caller may not make a shallow trace disappear merely by lowering its
        # declared importance.
        critical_trace_ids.update(item.trace_id for item in model.traces)
    critical_event_ids = {
        item.event_id
        for item in model.events
        if item.importance >= CRITICAL_OBJECT_IMPORTANCE_THRESHOLD
    }
    for hypothesis in hypotheses:
        if hypothesis.hypothesis_id in critical_hypothesis_ids:
            critical_event_ids.update(hypothesis.event_ids)
    critical_evidence_ids = {
        item.evidence_id
        for item in model.evidence
        if item.importance >= CRITICAL_OBJECT_IMPORTANCE_THRESHOLD
    }
    for event_id in critical_event_ids:
        event = event_by_id.get(event_id)
        if event:
            critical_evidence_ids.update(event.evidence_ids)
    for hypothesis in hypotheses:
        if hypothesis.hypothesis_id in critical_hypothesis_ids:
            critical_evidence_ids.update(hypothesis.evidence_ids)
            critical_evidence_ids.update(hypothesis.contradicting_evidence_ids)

    rows: list[dict[str, Any]] = []
    temporal_rows: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []

    def add_row(object_type: str, object_id: str, critical: bool, findings: list[str], details: dict[str, Any]) -> None:
        status = "pass" if not findings else "fail"
        rows.append(
            {
                "object_type": object_type,
                "object_id": object_id,
                "critical": critical,
                "status": status,
                "findings": findings,
                **details,
            }
        )
        if critical and findings:
            gaps.append(
                {
                    "gap_id": "critical_object_depth_incomplete",
                    "object_type": object_type,
                    "object_id": object_id,
                    "severity": "blocking_for_broad_claim",
                    "findings": findings,
                    "message": "A critical TraceGuard object lacks required internal depth.",
                }
            )

    for hypothesis in hypotheses:
        event_ids = sorted(_event_ids_for_hypothesis(hypothesis, model))
        evidence_ids = sorted(
            set(hypothesis.evidence_ids)
            | set(hypothesis.contradicting_evidence_ids)
            | {
                evidence_id
                for event_id in event_ids
                for evidence_id in (event_by_id.get(event_id).evidence_ids if event_by_id.get(event_id) else [])
            }
        )
        findings: list[str] = []
        if not any(trace_id in trace_by_id for trace_id in hypothesis.trace_ids):
            findings.append("trace_binding_missing")
        if len(set(event_ids) & set(event_by_id)) < 2:
            findings.append("event_depth_below_native_floor")
        if len(set(evidence_ids) & set(evidence_by_id)) < 2:
            findings.append("evidence_depth_below_native_floor")
        add_row(
            "hypothesis",
            hypothesis.hypothesis_id,
            hypothesis.hypothesis_id in critical_hypothesis_ids,
            findings,
            {"trace_ids": list(hypothesis.trace_ids), "event_ids": event_ids, "evidence_ids": evidence_ids},
        )

    raw_policy = model.metadata.get("storyline_depth_policy") or {}
    if not isinstance(raw_policy, dict):
        raw_policy = {}
    declared_minimum_count = _positive_int(
        raw_policy.get("minimum_per_trace_qualified_event_count"),
        0,
    )
    declared_minimum_ratio = _ratio(
        raw_policy.get("minimum_per_trace_qualified_event_ratio"),
        0.0,
    )
    declared_maximum_run = _positive_int(
        raw_policy.get("maximum_per_trace_unqualified_run"),
        0,
    )

    for trace in model.traces:
        eligible_event_ids = _ordered_unique(trace.event_ids)
        events = [event_by_id[item] for item in eligible_event_ids if item in event_by_id]
        time_tokens = [_event_time_token(item) for item in events]
        distinct_times = sorted({item for item in time_tokens if item})
        evidence_ids = sorted({evidence_id for event in events for evidence_id in event.evidence_ids})
        qualified_event_ids: list[str] = []
        for event_id in eligible_event_ids:
            event = event_by_id.get(event_id)
            if event is None or not _event_time_token(event) or not event.action.strip():
                continue
            qualified_evidence = [
                evidence_by_id[evidence_id]
                for evidence_id in event.evidence_ids
                if evidence_id in evidence_by_id
                and evidence_by_id[evidence_id].source_id in source_ids
                and evidence_by_id[evidence_id].raw_text.strip()
                and evidence_by_id[evidence_id].extraction_confidence >= 0.5
                and evidence_by_id[evidence_id].evidence_specificity >= 0.5
                and evidence_by_id[evidence_id].usable_as_trace_evidence is not False
            ]
            if qualified_evidence:
                qualified_event_ids.append(event_id)
        eligible_count = len(eligible_event_ids)
        native_minimum_count = max(3, math.ceil(math.sqrt(eligible_count)))
        policy_ratio_count = math.ceil(eligible_count * declared_minimum_ratio)
        required_qualified_count = max(
            native_minimum_count,
            declared_minimum_count,
            policy_ratio_count,
        )
        native_maximum_run = max(1, math.ceil(math.sqrt(max(eligible_count, 1))))
        allowed_maximum_run = (
            min(native_maximum_run, declared_maximum_run)
            if declared_maximum_run
            else native_maximum_run
        )
        qualified_set = set(qualified_event_ids)
        maximum_unqualified_run = _longest_unqualified_run(
            eligible_event_ids,
            qualified_set,
        )
        phase_rows: list[dict[str, Any]] = []
        for phase_index, phase_name in enumerate(("early", "middle", "late")):
            phase_ids = [
                event_id
                for index, event_id in enumerate(eligible_event_ids)
                if eligible_count and min(2, (index * 3) // eligible_count) == phase_index
            ]
            phase_qualified = [item for item in phase_ids if item in qualified_set]
            phase_rows.append(
                {
                    "phase": phase_name,
                    "eligible_event_ids": phase_ids,
                    "qualified_event_ids": phase_qualified,
                    "status": "pass" if phase_qualified else "fail",
                }
            )
        phase_coverage_complete = all(row["status"] == "pass" for row in phase_rows)
        temporal_findings: list[str] = []
        if len(qualified_event_ids) < required_qualified_count:
            temporal_findings.append("trace_qualified_event_count_below_dynamic_floor")
        if declared_minimum_ratio and (
            len(qualified_event_ids) / eligible_count if eligible_count else 0.0
        ) < declared_minimum_ratio:
            temporal_findings.append("trace_qualified_event_ratio_below_policy_floor")
        if not phase_coverage_complete or len(distinct_times) < 3:
            temporal_findings.append("trace_temporal_strata_incomplete")
        if maximum_unqualified_run > allowed_maximum_run:
            temporal_findings.append("trace_temporal_gap_above_dynamic_ceiling")
        findings: list[str] = []
        if eligible_count < 3:
            findings.append("trace_event_count_below_native_floor")
        if len(trace.event_ids) != eligible_count:
            findings.append("trace_event_inventory_has_duplicates")
        findings.extend(temporal_findings)
        if len(evidence_ids) < 2:
            findings.append("trace_evidence_depth_below_native_floor")
        temporal_row = {
            "trace_id": trace.trace_id,
            "event_count": eligible_count,
            "eligible_event_count": eligible_count,
            "eligible_event_ids": eligible_event_ids,
            "qualified_event_count": len(qualified_event_ids),
            "qualified_event_ids": qualified_event_ids,
            "qualified_event_ratio": (
                len(qualified_event_ids) / eligible_count if eligible_count else 0.0
            ),
            "native_minimum_qualified_event_count": native_minimum_count,
            "declared_minimum_qualified_event_count": declared_minimum_count,
            "declared_minimum_qualified_event_ratio": declared_minimum_ratio,
            "required_qualified_event_count": required_qualified_count,
            "native_maximum_unqualified_run": native_maximum_run,
            "declared_maximum_unqualified_run": declared_maximum_run,
            "allowed_maximum_unqualified_run": allowed_maximum_run,
            "maximum_consecutive_unqualified_run": maximum_unqualified_run,
            "native_floor_algorithm": "max(3,ceil(sqrt(eligible_event_count)))",
            "temporal_distribution_algorithm": "declared_trace_sequence_thirds_with_sqrt_gap_ceiling",
            "phase_coverage": phase_rows,
            "dated_event_count": sum(bool(item) for item in time_tokens),
            "distinct_time_count": len(distinct_times),
            "start_middle_end_covered": phase_coverage_complete and len(distinct_times) >= 3,
            "missing_time_event_ids": [
                event_id
                for event_id in eligible_event_ids
                if event_id not in event_by_id or not _event_time_token(event_by_id[event_id])
            ],
            "findings": temporal_findings,
            "status": "pass" if eligible_count >= 3 and not temporal_findings else "fail",
        }
        temporal_rows.append(temporal_row)
        add_row(
            "trace",
            trace.trace_id,
            trace.trace_id in critical_trace_ids,
            findings,
            {"event_ids": eligible_event_ids, "evidence_ids": evidence_ids, "temporal": temporal_row},
        )

    for event in model.events:
        findings: list[str] = []
        existing_evidence = [item for item in event.evidence_ids if item in evidence_by_id]
        if not existing_evidence:
            findings.append("event_evidence_missing")
        if not _event_time_token(event):
            findings.append("event_time_missing_or_unknown")
        if not event.action.strip():
            findings.append("event_action_missing")
        add_row(
            "event",
            event.event_id,
            event.event_id in critical_event_ids,
            findings,
            {"evidence_ids": existing_evidence, "time_token": _event_time_token(event)},
        )

    for evidence in model.evidence:
        findings: list[str] = []
        if evidence.source_id not in source_ids:
            findings.append("evidence_source_missing")
        if not evidence.raw_text.strip():
            findings.append("evidence_content_missing")
        if evidence.extraction_confidence < 0.5 or evidence.evidence_specificity < 0.5:
            findings.append("evidence_semantic_threshold_failed")
        if evidence.usable_as_trace_evidence is False:
            findings.append("evidence_not_trace_usable")
        add_row(
            "evidence",
            evidence.evidence_id,
            evidence.evidence_id in critical_evidence_ids,
            findings,
            {"source_id": evidence.source_id},
        )

    for mechanism in model.causal_mechanisms:
        critical = mechanism.hypothesis_id in critical_hypothesis_ids
        findings: list[str] = []
        if not mechanism.description.strip():
            findings.append("mechanism_description_missing")
        if not mechanism.evidence_ids or any(item not in evidence_by_id for item in mechanism.evidence_ids):
            findings.append("mechanism_evidence_missing")
        add_row("mechanism", mechanism.mechanism_id, critical, findings, {"hypothesis_id": mechanism.hypothesis_id})

    for confounder in model.confounder_reviews:
        critical = confounder.hypothesis_id in critical_hypothesis_ids or confounder.importance >= CRITICAL_OBJECT_IMPORTANCE_THRESHOLD
        findings: list[str] = []
        if confounder.status.strip().lower() not in RESOLVED_CONFOUNDER_STATUSES:
            findings.append("confounder_not_resolved_or_bounded")
        if not confounder.description.strip():
            findings.append("confounder_description_missing")
        add_row("confounder", confounder.confounder_id, critical, findings, {"hypothesis_id": confounder.hypothesis_id, "review_status": confounder.status})

    for ablation in model.evidence_ablations:
        findings: list[str] = []
        if not ablation.description.strip():
            findings.append("ablation_description_missing")
        if not ablation.remove_event_ids and not ablation.remove_evidence_ids:
            findings.append("ablation_has_no_state_change")
        if any(item not in event_by_id for item in ablation.remove_event_ids):
            findings.append("ablation_event_unknown")
        if any(item not in evidence_by_id for item in ablation.remove_evidence_ids):
            findings.append("ablation_evidence_unknown")
        add_row(
            "ablation",
            ablation.ablation_id,
            True,
            findings,
            {"hypothesis_id": ablation.hypothesis_id or ""},
        )

    perturbation_ids = {item.ablation_id for item in model.evidence_ablations}
    perturbation_ids.update(
        item.perturbation_id for item in model.scenario_perturbations
    )
    for sensitivity in model.expected_sensitivities:
        findings: list[str] = []
        if sensitivity.perturbation_id not in perturbation_ids:
            findings.append("expected_sensitivity_perturbation_missing")
        if sensitivity.expected_direction.strip().lower() in {"", "unknown"}:
            findings.append("expected_sensitivity_direction_missing")
        add_row(
            "expected_sensitivity",
            sensitivity.sensitivity_id,
            True,
            findings,
            {
                "hypothesis_id": (
                    sensitivity.target_id
                    if sensitivity.target_kind == "hypothesis"
                    else ""
                ),
                "expected_direction": sensitivity.expected_direction,
            },
        )

    fingerprint_payload = {
        "owner": "researchguard.trace.storyline-object-depth",
        "critical_importance_threshold": CRITICAL_OBJECT_IMPORTANCE_THRESHOLD,
        "requested_claim_scope": requested_claim_scope,
        "temporal_policy": {
            "minimum_per_trace_qualified_event_count": declared_minimum_count,
            "minimum_per_trace_qualified_event_ratio": declared_minimum_ratio,
            "maximum_per_trace_unqualified_run": declared_maximum_run,
            "native_floor_algorithm": "max(3,ceil(sqrt(eligible_event_count)))",
            "temporal_distribution_algorithm": "declared_trace_sequence_thirds_with_sqrt_gap_ceiling",
        },
        "temporal_rows": temporal_rows,
        "rows": [
            {
                "object_type": row["object_type"],
                "object_id": row["object_id"],
                "critical": row["critical"],
            }
            for row in rows
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    critical_rows = [row for row in rows if row["critical"]]
    counts = {
        "eligible_count": len(rows),
        "critical_count": len(critical_rows),
        "covered_count": sum(row["status"] == "pass" for row in rows),
        "critical_covered_count": sum(row["status"] == "pass" for row in critical_rows),
        "critical_uncovered_count": sum(row["status"] != "pass" for row in critical_rows),
    }
    return fingerprint, counts, tuple(rows), tuple(temporal_rows), gaps


def hypotheses_for_model(model: TraceGuardModel) -> tuple[StorylineHypothesis, ...]:
    if model.storyline_hypotheses:
        return model.storyline_hypotheses
    derived: list[StorylineHypothesis] = []
    for index, trace in enumerate(model.traces):
        claim = trace.claim or trace.title
        derived.append(
            StorylineHypothesis(
                hypothesis_id=f"implicit:{trace.trace_id}",
                claim=claim,
                role="primary" if index == 0 else "alternative",
                trace_ids=[trace.trace_id],
                event_ids=list(trace.event_ids),
                importance=trace.importance,
                uncertainty=0.5,
                causal=False,
                bounded_non_causal=True,
            )
        )
    return tuple(derived)


def _event_ids_for_hypothesis(
    hypothesis: StorylineHypothesis,
    model: TraceGuardModel,
) -> set[str]:
    event_ids = set(hypothesis.event_ids)
    trace_ids = set(hypothesis.trace_ids)
    for trace in model.traces:
        if trace.trace_id in trace_ids:
            event_ids.update(trace.event_ids)
    return event_ids


def _trace_ids_for_hypothesis(
    hypothesis: StorylineHypothesis,
    model: TraceGuardModel,
) -> set[str]:
    trace_ids = set(hypothesis.trace_ids)
    event_ids = set(hypothesis.event_ids)
    for trace in model.traces:
        if event_ids.intersection(trace.event_ids):
            trace_ids.add(trace.trace_id)
    return trace_ids


def hypothesis_snapshots(
    model: TraceGuardModel,
    result: Any,
    hypotheses: Iterable[StorylineHypothesis],
) -> tuple[HypothesisSnapshot, ...]:
    trace_results = {trace.trace_id: trace for trace in result.traces}
    inference_projections = {
        item.hypothesis_id: item
        for item in getattr(
            getattr(result, "inference_receipt", None),
            "hypothesis_projections",
            (),
        )
    }
    event_by_id = model.event_by_id()
    snapshots: list[HypothesisSnapshot] = []
    for hypothesis in hypotheses:
        trace_ids = _trace_ids_for_hypothesis(hypothesis, model)
        evaluations = [trace_results[item] for item in trace_ids if item in trace_results]
        event_ids = _event_ids_for_hypothesis(hypothesis, model)
        events = [event_by_id[item] for item in event_ids if item in event_by_id]
        evidence_ids = set(hypothesis.evidence_ids)
        evidence_ids.update(
            evidence_id
            for evaluation in evaluations
            for evidence_id in evaluation.evidence_ids
        )
        evidence_ids.update(
            evidence_id for event in events for evidence_id in event.evidence_ids
        )
        projection = inference_projections.get(hypothesis.hypothesis_id)
        confidence = float(projection.support) if projection is not None else 0.0
        event_support = sum(1 for event in events if event.evidence_ids)
        contradiction_count = sum(len(item.contradictions) for item in evaluations)
        gap_count = sum(len(item.gaps) for item in evaluations)
        score = confidence
        snapshots.append(
            HypothesisSnapshot(
                hypothesis_id=hypothesis.hypothesis_id,
                rank=0,
                score=round(score, 6),
                confidence=round(confidence, 6),
                event_support=event_support,
                evidence_support=len(evidence_ids),
                contradiction_count=contradiction_count,
                gap_count=gap_count,
            )
        )
    ranked = sorted(snapshots, key=lambda item: (-item.score, item.hypothesis_id))
    return tuple(
        replace(
            item,
            rank=(
                inference_projections[item.hypothesis_id].rank
                if item.hypothesis_id in inference_projections
                else index + 1
            ),
        )
        for index, item in enumerate(ranked)
    )


def _alternative_rows(
    hypotheses: tuple[StorylineHypothesis, ...],
) -> tuple[tuple[StorylineAlternative, ...], list[dict[str, Any]]]:
    rows: list[StorylineAlternative] = []
    gaps: list[dict[str, Any]] = []
    for hypothesis in hypotheses:
        alternatives = {
            other.hypothesis_id
            for other in hypotheses
            if other.hypothesis_id != hypothesis.hypothesis_id
            and (
                other.hypothesis_id in hypothesis.alternative_to
                or hypothesis.hypothesis_id in other.alternative_to
                or (hypothesis.role == "primary" and other.role == "alternative")
            )
        }
        rows.append(
            StorylineAlternative(
                hypothesis_id=hypothesis.hypothesis_id,
                alternative_ids=tuple(sorted(alternatives)),
                out_of_scope_reason=hypothesis.alternative_out_of_scope_reason
                or "",
            )
        )
        if (
            hypothesis.causal
            and hypothesis.importance >= 0.5
            and not alternatives
            and not hypothesis.alternative_out_of_scope_reason
        ):
            gaps.append(
                {
                    "gap_id": "missing_alternative",
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "severity": "blocking",
                    "message": "Broad causal storyline has no competing hypothesis or bounded exclusion reason.",
                }
            )
    return tuple(rows), gaps


def _causal_rows(
    model: TraceGuardModel,
    hypotheses: tuple[StorylineHypothesis, ...],
    baseline_result: Any,
) -> tuple[tuple[dict[str, Any], ...], list[dict[str, Any]]]:
    mechanisms = {item.mechanism_id: item for item in model.causal_mechanisms}
    confounders = {item.confounder_id: item for item in model.confounder_reviews}
    candidates = {
        item.hypothesis_id: item for item in model.causal_candidates
    }
    projections = {
        item.hypothesis_id: item
        for item in getattr(
            getattr(baseline_result, "inference_receipt", None),
            "hypothesis_projections",
            (),
        )
    }
    rows: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for hypothesis in hypotheses:
        candidate = candidates.get(hypothesis.hypothesis_id)
        projection = projections.get(hypothesis.hypothesis_id)
        if candidate is None:
            rows.append(
                {
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "causal_requested": False,
                    "causal_support": None,
                    "mechanism_ids": [],
                    "confounder_ids": [],
                    "status": "not_requested",
                    "claim_boundary": (
                        "No typed causal candidate was declared; chronology or "
                        "causal wording in text does not create a causal model."
                    ),
                }
            )
            continue
        mechanism_ids = [
            item for item in candidate.mechanism_ids if item in mechanisms
        ]
        confounder_ids = [
            item for item in candidate.confounder_ids if item in confounders
        ]
        mechanism_evidence_complete = bool(mechanism_ids) and all(
            mechanisms[item].description.strip()
            and mechanisms[item].evidence_ids
            and all(evidence_id in model.evidence_by_id() for evidence_id in mechanisms[item].evidence_ids)
            for item in mechanism_ids
        )
        resolved_confounder_ids = [
            item
            for item in confounder_ids
            if confounders[item].status.strip().lower() in RESOLVED_CONFOUNDER_STATUSES
        ]
        status = projection.causal_status if projection is not None else "insufficient"
        causal_support = (
            projection.causal_support if projection is not None else None
        )
        if status != "supported":
            gaps.append(
                {
                    "gap_id": f"qualitative_causal_{status}",
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "severity": "blocking_for_causal_wording",
                    "message": (
                        "The unified objective did not license supported qualitative "
                        "causal wording. Inspect chronology, mechanism evidence, "
                        "alternative comparison, confounder disposition, and scope."
                    ),
                }
            )
        if not mechanism_ids:
            gaps.append(
                {
                    "gap_id": "missing_causal_mechanism",
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "severity": "blocking_for_causal_wording",
                    "message": "The typed causal candidate has no mechanism.",
                }
            )
        elif not mechanism_evidence_complete:
            gaps.append(
                {
                    "gap_id": "mechanism_evidence_incomplete",
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "severity": "blocking_for_causal_wording",
                    "message": "Every declared mechanism requires current evidence.",
                }
            )
        if not confounder_ids:
            gaps.append(
                {
                    "gap_id": "missing_confounder_review",
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "severity": "blocking_for_causal_wording",
                    "message": "The typed causal candidate has no confounder review.",
                }
            )
        elif len(resolved_confounder_ids) != len(confounder_ids):
            gaps.append(
                {
                    "gap_id": "unresolved_confounder_review",
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "severity": "blocking_for_causal_wording",
                    "message": "Every linked confounder requires an addressed or not-applicable disposition.",
                }
            )
        if not candidate.alternative_hypothesis_ids:
            gaps.append(
                {
                    "gap_id": "missing_causal_alternative",
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "severity": "blocking_for_causal_wording",
                    "message": "The causal candidate has no typed alternative comparison.",
                }
            )
        if not candidate.scope_id:
            gaps.append(
                {
                    "gap_id": "missing_causal_scope",
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "severity": "blocking_for_causal_wording",
                    "message": "The causal candidate has no explicit scope boundary.",
                }
            )
        rows.append(
            {
                "hypothesis_id": hypothesis.hypothesis_id,
                "causal_requested": True,
                "causal_support": causal_support,
                "mechanism_ids": mechanism_ids,
                "confounder_ids": confounder_ids,
                "resolved_confounder_ids": resolved_confounder_ids,
                "mechanism_evidence_complete": mechanism_evidence_complete,
                "cause_event_ids": list(candidate.cause_event_ids),
                "effect_event_ids": list(candidate.effect_event_ids),
                "alternative_hypothesis_ids": list(
                    candidate.alternative_hypothesis_ids
                ),
                "scope_id": candidate.scope_id or "",
                "status": status,
                "claim_boundary": (
                    projection.claim_boundary
                    if projection is not None
                    else "No canonical causal projection is available."
                ),
            }
        )
    return tuple(rows), gaps


def _known_year(event: EventCandidate) -> int | None:
    if event.time_interval is None:
        return None
    token = event.time_interval.start or event.time_interval.text or ""
    match = re.search(r"\b(\d{4})\b", token)
    return int(match.group(1)) if match else None


def _evidence_candidate_score(
    model: TraceGuardModel,
    hypotheses: tuple[StorylineHypothesis, ...],
    event: EventCandidate,
    evidence_id: str,
) -> tuple[float, tuple[str, ...], str]:
    evidence = model.evidence_by_id().get(evidence_id)
    related: list[StorylineHypothesis] = []
    for hypothesis in hypotheses:
        if (
            event.event_id in _event_ids_for_hypothesis(hypothesis, model)
            or evidence_id in hypothesis.evidence_ids
            or evidence_id in hypothesis.contradicting_evidence_ids
        ):
            related.append(hypothesis)
    trace_centrality = sum(
        1 for trace in model.traces if event.event_id in trace.event_ids
    )
    hypothesis_centrality = len(related)
    discrimination = sum(
        1
        for hypothesis in related
        if evidence_id in hypothesis.evidence_ids
        or evidence_id in hypothesis.contradicting_evidence_ids
    )
    importance = (evidence.importance if evidence else 0.0) + event.importance
    hypothesis_importance = max((item.importance for item in related), default=0.0)
    uncertainty = (
        (1.0 - evidence.extraction_confidence) if evidence else 1.0
    ) + (1.0 - event.extraction_confidence) + (
        1.0 if event.time_interval is None else 0.0
    )
    score = (
        2.0 * hypothesis_centrality
        + 1.25 * trace_centrality
        + 2.0 * discrimination
        + importance
        + hypothesis_importance
        + 0.5 * uncertainty
    )
    reasons = (
        f"hypothesis_centrality={hypothesis_centrality}",
        f"trace_centrality={trace_centrality}",
        f"alternative_discrimination={discrimination}",
        f"declared_importance={importance + hypothesis_importance:.3f}",
        f"uncertainty={uncertainty:.3f}",
    )
    target_hypothesis = max(related, key=lambda item: item.importance).hypothesis_id if related else ""
    return score, reasons, target_hypothesis


def perturbation_candidates(
    model: TraceGuardModel,
    hypotheses: tuple[StorylineHypothesis, ...] | None = None,
) -> tuple[PerturbationPlanItem, ...]:
    hypotheses = hypotheses or hypotheses_for_model(model)
    candidates: list[PerturbationPlanItem] = []
    trace_by_event: dict[str, list[TraceCandidate]] = {}
    for trace in model.traces:
        for event_id in trace.event_ids:
            trace_by_event.setdefault(event_id, []).append(trace)
    for event in model.events:
        for evidence_id in event.evidence_ids:
            score, reasons, hypothesis_id = _evidence_candidate_score(
                model, hypotheses, event, evidence_id
            )
            target_trace = max(
                trace_by_event.get(event.event_id, []),
                key=lambda item: item.importance,
                default=None,
            )
            candidates.append(
                PerturbationPlanItem(
                    perturbation_id=f"remove:{event.event_id}:{evidence_id}",
                    kind="evidence_removal",
                    target_hypothesis_id=hypothesis_id,
                    target_trace_id=target_trace.trace_id if target_trace else "",
                    target_event_id=event.event_id,
                    target_evidence_id=evidence_id,
                    priority_score=round(score, 6),
                    reasons=reasons,
                )
            )
    event_by_id = model.event_by_id()
    for trace in model.traces:
        challenge_events = [
            event_by_id[event_id]
            for event_id in trace.event_ids
            if event_id in event_by_id
            and _known_year(event_by_id[event_id]) is not None
            and ORDERED_STAGE_INDEX.get(
                stage_for_event(
                    event_by_id[event_id].event_type,
                    event_by_id[event_id].stage_hint,
                ),
                99,
            )
            < ORDERED_STAGE_INDEX["operation"]
        ]
        if not challenge_events:
            continue
        target_event = min(challenge_events, key=lambda item: (_known_year(item) or 9999, item.event_id))
        related = [
            hypothesis
            for hypothesis in hypotheses
            if trace.trace_id in _trace_ids_for_hypothesis(hypothesis, model)
        ]
        hypothesis = max(related, key=lambda item: item.importance, default=None)
        score = 2.0 * trace.importance + target_event.importance + (hypothesis.importance if hypothesis else 0.0) + (hypothesis.uncertainty if hypothesis else 0.5)
        candidates.append(
            PerturbationPlanItem(
                perturbation_id=f"contradict:{trace.trace_id}:{target_event.event_id}",
                kind="contradiction_injection",
                target_hypothesis_id=hypothesis.hypothesis_id if hypothesis else "",
                target_trace_id=trace.trace_id,
                target_event_id=target_event.event_id,
                priority_score=round(score, 6),
                reasons=(
                    f"trace_importance={trace.importance:.3f}",
                    f"target_event_importance={target_event.importance:.3f}",
                    f"target_year={_known_year(target_event)}",
                    "inject operation before a model-linked earlier stage",
                ),
            )
        )
    for ablation in model.evidence_ablations:
        hypothesis = next(
            (item for item in hypotheses if item.hypothesis_id == ablation.hypothesis_id),
            None,
        )
        candidates.append(
            PerturbationPlanItem(
                perturbation_id=f"evidence_ablation:{ablation.ablation_id}",
                kind="evidence_ablation",
                target_hypothesis_id=ablation.hypothesis_id or "",
                target_trace_id=ablation.trace_id or "",
                declared_perturbation_id=ablation.ablation_id,
                priority_score=max(
                    CRITICAL_PERTURBATION_THRESHOLD,
                    round(ablation.importance + (hypothesis.importance if hypothesis else 0.0) + (hypothesis.uncertainty if hypothesis else 0.0), 6),
                ),
                reasons=("declared evidence ablation", f"importance={ablation.importance:.3f}"),
            )
        )
    for sensitivity in model.expected_sensitivities:
        hypothesis = next(
            (
                item
                for item in hypotheses
                if sensitivity.target_kind == "hypothesis"
                and item.hypothesis_id == sensitivity.target_id
            ),
            None,
        )
        candidates.append(
            PerturbationPlanItem(
                perturbation_id=f"expected_sensitivity:{sensitivity.sensitivity_id}",
                kind="expected_sensitivity",
                target_hypothesis_id=(
                    sensitivity.target_id
                    if sensitivity.target_kind == "hypothesis"
                    else ""
                ),
                target_trace_id=(
                    sensitivity.target_id
                    if sensitivity.target_kind == "trace"
                    else ""
                ),
                declared_perturbation_id=sensitivity.perturbation_id,
                expected_sensitivity_id=sensitivity.sensitivity_id,
                priority_score=max(
                    CRITICAL_PERTURBATION_THRESHOLD,
                    round(
                        sensitivity.minimum_absolute_change
                        + (hypothesis.importance if hypothesis else 0.0)
                        + (hypothesis.uncertainty if hypothesis else 0.0),
                        6,
                    ),
                ),
                reasons=(
                    "declared expected sensitivity",
                    f"expected_direction={sensitivity.expected_direction}",
                ),
            )
        )
    return tuple(sorted(candidates, key=lambda item: (-item.priority_score, item.perturbation_id)))


def select_perturbation_plan(
    model: TraceGuardModel,
    hypotheses: tuple[StorylineHypothesis, ...] | None = None,
    *,
    max_perturbations: int | None = None,
    critical_threshold: float = CRITICAL_PERTURBATION_THRESHOLD,
) -> tuple[tuple[PerturbationPlanItem, ...], tuple[dict[str, Any], ...]]:
    candidates = perturbation_candidates(model, hypotheses)
    if max_perturbations is not None and max_perturbations < 0:
        raise ValueError("max_perturbations must be non-negative")
    selected_ids = {
        item.perturbation_id
        for item in candidates
        if item.priority_score >= critical_threshold
    }
    for kind in (
        "evidence_removal",
        "contradiction_injection",
        "evidence_ablation",
        "expected_sensitivity",
    ):
        same_kind = [item for item in candidates if item.kind == kind]
        if same_kind and not any(item.perturbation_id in selected_ids for item in same_kind):
            selected_ids.add(same_kind[0].perturbation_id)
    selected = [item for item in candidates if item.perturbation_id in selected_ids]
    if max_perturbations is not None:
        selected = selected[:max_perturbations]
    executed_ids = {item.perturbation_id for item in selected}
    untested = [
        {
            "perturbation_id": item.perturbation_id,
            "kind": item.kind,
            "priority_score": item.priority_score,
            "reason": (
                "explicit perturbation budget exhausted before all critical candidates executed"
                if max_perturbations is not None
                else "critical candidate was not selected"
            ),
        }
        for item in candidates
        if item.priority_score >= critical_threshold and item.perturbation_id not in executed_ids
    ]
    return tuple(selected), tuple(untested)


def _candidate_universe_fingerprint(
    candidates: tuple[PerturbationPlanItem, ...],
    critical_threshold: float,
) -> str:
    payload = {
        "owner": "researchguard.trace.storyline-depth",
        "critical_threshold": critical_threshold,
        "candidates": [item.to_dict() for item in candidates],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _unique(existing: set[str], base: str) -> str:
    if base not in existing:
        return base
    index = 2
    while f"{base}_{index}" in existing:
        index += 1
    return f"{base}_{index}"


def _remove_evidence_link(
    model: TraceGuardModel,
    plan: PerturbationPlanItem,
) -> TraceGuardModel:
    events = tuple(
        replace(
            event,
            evidence_ids=[
                item
                for item in event.evidence_ids
                if not (
                    event.event_id == plan.target_event_id
                    and item == plan.target_evidence_id
                )
            ],
        )
        if event.event_id == plan.target_event_id
        else event
        for event in model.events
    )
    hypotheses = tuple(
        replace(
            hypothesis,
            evidence_ids=[
                item
                for item in hypothesis.evidence_ids
                if item != plan.target_evidence_id
            ],
            contradicting_evidence_ids=[
                item
                for item in hypothesis.contradicting_evidence_ids
                if item != plan.target_evidence_id
            ],
        )
        for hypothesis in model.storyline_hypotheses
    )
    return replace(
        model,
        events=events,
        storyline_hypotheses=hypotheses,
        hypothesis_evidence_links=tuple(
            link
            for link in model.hypothesis_evidence_links
            if link.evidence_id != plan.target_evidence_id
        ),
    )


def _inject_contradiction(
    model: TraceGuardModel,
    plan: PerturbationPlanItem,
    *,
    attach_to_trace: bool = True,
) -> TraceGuardModel:
    target_event = model.event_by_id().get(plan.target_event_id)
    target_trace = next(
        (trace for trace in model.traces if trace.trace_id == plan.target_trace_id),
        None,
    )
    target_year = _known_year(target_event) if target_event else None
    if target_event is None or target_trace is None or target_year is None:
        return model
    source_id = _unique({item.source_id for item in model.sources}, "src_model_derived_probe")
    evidence_id = _unique({item.evidence_id for item in model.evidence}, "ev_model_derived_probe")
    event_id = _unique({item.event_id for item in model.events}, "event_model_derived_probe")
    source = SourceRecord(
        source_id=source_id,
        title=f"Model-derived contradiction probe for {target_trace.trace_id}",
        source_type="simulation_probe",
        lineage_id=f"lineage:{source_id}",
        independence_group=f"simulation:{plan.perturbation_id}",
        source_reliability=0.5,
        source_status="stable_keep",
        notes="Synthetic local perturbation; not factual evidence.",
    )
    evidence = EvidenceItem(
        evidence_id=evidence_id,
        source_id=source_id,
        raw_text="Synthetic operation claim positioned before a model-linked earlier-stage event.",
        evidence_type="news",
        extraction_confidence=0.5,
        evidence_specificity=0.7,
        importance=target_event.importance,
        supports=[event_id],
        limits=["local model perturbation only"],
        warnings=["not a factual source"],
        usable_as_trace_evidence=True,
        usable_as_project_evidence=True,
    )
    event = EventCandidate(
        event_id=event_id,
        evidence_ids=[evidence_id],
        actor_ids=list(target_trace.entity_ids[:1]),
        action="model-derived early operation challenge",
        object_ids=list(target_trace.entity_ids[:1]),
        event_type="operation_start",
        time_interval=TimeInterval(
            start=str(max(1, target_year - 1)),
            precision="year",
            confidence=0.5,
        ),
        location_ids=list(target_trace.location_ids[:1]),
        stage_hint="operation",
        extraction_confidence=0.5,
        importance=target_event.importance,
        extraction_notes="Synthetic perturbation selected from current trace importance and chronology.",
    )
    traces = model.traces
    if attach_to_trace:
        traces = tuple(
            replace(trace, event_ids=[event_id, *trace.event_ids])
            if trace.trace_id == target_trace.trace_id
            else trace
            for trace in model.traces
        )
    return replace(
        model,
        sources=(*model.sources, source),
        evidence=(*model.evidence, evidence),
        events=(*model.events, event),
        traces=traces,
    )


def _apply_declared_perturbation(
    model: TraceGuardModel,
    perturbation_id: str,
) -> TraceGuardModel:
    perturbation = next(
        (
            item
            for item in model.evidence_ablations
            if item.ablation_id == perturbation_id
        ),
        None,
    )
    if perturbation is None:
        perturbation = next(
            (
                item
                for item in model.scenario_perturbations
                if item.perturbation_id == perturbation_id
            ),
            None,
        )
    if perturbation is None:
        return model
    remove_evidence = set(perturbation.remove_evidence_ids)
    remove_events = set(perturbation.remove_event_ids)
    add_evidence = set(getattr(perturbation, "add_evidence_ids", ()))
    add_events = set(getattr(perturbation, "add_event_ids", ()))
    target_event_ids: set[str] = set()
    if perturbation.trace_id:
        target_trace = next(
            (item for item in model.traces if item.trace_id == perturbation.trace_id),
            None,
        )
        if target_trace is not None:
            target_event_ids.update(target_trace.event_ids)
    if perturbation.hypothesis_id:
        target_hypothesis = next(
            (
                item
                for item in model.storyline_hypotheses
                if item.hypothesis_id == perturbation.hypothesis_id
            ),
            None,
        )
        if target_hypothesis is not None:
            target_event_ids.update(target_hypothesis.event_ids)
            for trace in model.traces:
                if trace.trace_id in target_hypothesis.trace_ids:
                    target_event_ids.update(trace.event_ids)
    events = tuple(
        replace(
            event,
            evidence_ids=sorted(
                {
                    evidence_id
                    for evidence_id in event.evidence_ids
                    if evidence_id not in remove_evidence
                }
                | (add_evidence if event.event_id in target_event_ids else set())
            ),
        )
        for event in model.events
        if event.event_id not in remove_events
    )
    traces = tuple(
        replace(
            trace,
            event_ids=sorted(
                {
                    event_id
                    for event_id in trace.event_ids
                    if event_id not in remove_events
                }
                | (
                    add_events
                    if trace.trace_id == perturbation.trace_id
                    else set()
                )
            ),
        )
        for trace in model.traces
    )
    hypotheses = tuple(
        replace(
            hypothesis,
            evidence_ids=[
                evidence_id
                for evidence_id in hypothesis.evidence_ids
                if evidence_id not in remove_evidence
            ],
            contradicting_evidence_ids=[
                evidence_id
                for evidence_id in hypothesis.contradicting_evidence_ids
                if evidence_id not in remove_evidence
            ],
            event_ids=sorted(
                {
                    event_id
                    for event_id in hypothesis.event_ids
                    if event_id not in remove_events
                }
                | (
                    add_events
                    if hypothesis.hypothesis_id == perturbation.hypothesis_id
                    else set()
                )
            ),
        )
        for hypothesis in model.storyline_hypotheses
    )
    return replace(
        model,
        events=events,
        traces=traces,
        storyline_hypotheses=hypotheses,
        hypothesis_evidence_links=tuple(
            link
            for link in model.hypothesis_evidence_links
            if link.evidence_id not in remove_evidence
        ),
        causal_mechanisms=tuple(
            replace(
                item,
                evidence_ids=[
                    evidence_id
                    for evidence_id in item.evidence_ids
                    if evidence_id not in remove_evidence
                ],
            )
            for item in model.causal_mechanisms
        ),
        confounder_reviews=tuple(
            replace(
                item,
                evidence_ids=[
                    evidence_id
                    for evidence_id in item.evidence_ids
                    if evidence_id not in remove_evidence
                ],
            )
            for item in model.confounder_reviews
        ),
        causal_candidates=tuple(
            replace(
                item,
                cause_event_ids=[
                    event_id
                    for event_id in item.cause_event_ids
                    if event_id not in remove_events
                ],
                effect_event_ids=[
                    event_id
                    for event_id in item.effect_event_ids
                    if event_id not in remove_events
                ],
            )
            for item in model.causal_candidates
        ),
    )


def apply_perturbation(
    model: TraceGuardModel,
    plan: PerturbationPlanItem,
) -> TraceGuardModel:
    if plan.kind == "evidence_removal":
        return _remove_evidence_link(model, plan)
    if plan.kind == "contradiction_injection":
        return _inject_contradiction(model, plan)
    if plan.kind in {"evidence_ablation", "expected_sensitivity"}:
        return _apply_declared_perturbation(
            model,
            plan.declared_perturbation_id,
        )
    if plan.kind == "irrelevant_event_injection":
        return _inject_contradiction(model, plan, attach_to_trace=False)
    return model


def compare_perturbation(
    plan: PerturbationPlanItem,
    before: tuple[HypothesisSnapshot, ...],
    after: tuple[HypothesisSnapshot, ...],
) -> PerturbationEffect:
    before_by_id = {item.hypothesis_id: item for item in before}
    after_by_id = {item.hypothesis_id: item for item in after}
    deltas: dict[str, dict[str, Any]] = {}
    effective = False
    for hypothesis_id in sorted(set(before_by_id) | set(after_by_id)):
        old = before_by_id.get(hypothesis_id)
        new = after_by_id.get(hypothesis_id)
        if old is None or new is None:
            deltas[hypothesis_id] = {
                "before": old.to_dict() if old else None,
                "after": new.to_dict() if new else None,
            }
            effective = True
            continue
        row = {
            "rank": {"before": old.rank, "after": new.rank, "delta": new.rank - old.rank},
            "score": {"before": old.score, "after": new.score, "delta": round(new.score - old.score, 6)},
            "confidence": {"before": old.confidence, "after": new.confidence, "delta": round(new.confidence - old.confidence, 6)},
            "event_support": {"before": old.event_support, "after": new.event_support, "delta": new.event_support - old.event_support},
            "evidence_support": {"before": old.evidence_support, "after": new.evidence_support, "delta": new.evidence_support - old.evidence_support},
            "contradictions": {"before": old.contradiction_count, "after": new.contradiction_count, "delta": new.contradiction_count - old.contradiction_count},
            "gaps": {"before": old.gap_count, "after": new.gap_count, "delta": new.gap_count - old.gap_count},
        }
        deltas[hypothesis_id] = row
        if any(
            values["delta"] != 0
            for values in row.values()
        ):
            effective = True
    informative_null = not effective and plan.expected_effect == "informative_null"
    return PerturbationEffect(
        perturbation=plan,
        before=before,
        after=after,
        deltas=deltas,
        effective=effective,
        informative_null=informative_null,
        counts_toward_depth=effective or informative_null,
    )


def _expected_sensitivity_matches(
    model: TraceGuardModel,
    effect: PerturbationEffect,
) -> bool:
    sensitivity = next(
        (
            item
            for item in model.expected_sensitivities
            if item.sensitivity_id
            == effect.perturbation.expected_sensitivity_id
        ),
        None,
    )
    if sensitivity is None:
        return False
    direction = (
        sensitivity.expected_direction.strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )
    target_ids = [sensitivity.target_id]
    if sensitivity.target_kind == "trace":
        target_ids = [
            f"implicit:{sensitivity.target_id}",
            *[
                item.hypothesis_id
                for item in model.storyline_hypotheses
                if sensitivity.target_id in item.trace_ids
            ],
        ]
    rows = [
        effect.deltas[target_id]
        for target_id in target_ids
        if target_id in effect.deltas
    ]
    if direction in {"stable", "no_change", "unchanged", "informative_null"}:
        return bool(rows) and all(
            all(
                float(change.get("delta", 0.0)) == 0.0
                for change in row.values()
                if isinstance(change, dict)
            )
            for row in rows
        )
    if not rows:
        return False
    minimum_change = sensitivity.minimum_absolute_change
    signed_changes = [
        float(row.get("score", {}).get("delta", 0.0))
        for row in rows
    ]
    if direction in {"decrease", "decrease_support", "weaken", "weaker", "down", "negative"}:
        return any(value < 0 and abs(value) >= minimum_change for value in signed_changes)
    if direction in {"increase", "increase_support", "strengthen", "stronger", "up", "positive"}:
        return any(value > 0 and abs(value) >= minimum_change for value in signed_changes)
    if direction in {"change", "different", "any_change"}:
        return any(abs(value) >= minimum_change for value in signed_changes)
    return False


def run_single_perturbation(
    model: TraceGuardModel,
    baseline_result: Any,
    plan: PerturbationPlanItem,
    hypotheses: tuple[StorylineHypothesis, ...] | None = None,
) -> tuple[PerturbationEffect, TraceGuardModel, Any]:
    from .evaluator import evaluate_model

    hypotheses = hypotheses or hypotheses_for_model(model)
    before = hypothesis_snapshots(model, baseline_result, hypotheses)
    perturbed_model = apply_perturbation(model, plan)
    perturbed_result = evaluate_model(
        perturbed_model,
        include_storyline_depth=False,
    )
    after = hypothesis_snapshots(
        perturbed_model,
        perturbed_result,
        hypotheses_for_model(perturbed_model),
    )
    effect = compare_perturbation(plan, before, after)
    baseline_receipt = baseline_result.inference_receipt
    perturbed_receipt = perturbed_result.inference_receipt
    effect = replace(
        effect,
        baseline_inference_receipt_id=baseline_receipt.receipt_id,
        perturbed_inference_receipt_id=perturbed_receipt.receipt_id,
        baseline_problem_fingerprint=baseline_receipt.problem_fingerprint,
        perturbed_problem_fingerprint=perturbed_receipt.problem_fingerprint,
        baseline_solver_id=baseline_receipt.solver_id,
        perturbed_solver_id=perturbed_receipt.solver_id,
    )
    return effect, perturbed_model, perturbed_result


def evaluate_storyline_depth(
    model: TraceGuardModel,
    baseline_result: Any,
    *,
    max_perturbations: int | None = None,
    requested_claim_scope: str = "broad",
) -> StorylineDepthReceipt:
    if requested_claim_scope not in {"bounded", "broad"}:
        raise ValueError("requested_claim_scope must be 'bounded' or 'broad'")
    fingerprint = _model_fingerprint(model)
    hypotheses = hypotheses_for_model(model)
    baseline_snapshots = hypothesis_snapshots(model, baseline_result, hypotheses)
    alternatives, alternative_gaps = _alternative_rows(hypotheses)
    causal_coverage, causal_gaps = _causal_rows(
        model,
        hypotheses,
        baseline_result,
    )
    (
        object_universe_fingerprint,
        object_coverage_counts,
        object_depth_rows,
        temporal_coverage,
        object_gaps,
    ) = _object_depth_coverage(
        model,
        hypotheses,
        requested_claim_scope=requested_claim_scope,
    )
    candidates = perturbation_candidates(model, hypotheses)
    candidate_universe_fingerprint = _candidate_universe_fingerprint(
        candidates,
        CRITICAL_PERTURBATION_THRESHOLD,
    )
    plan, untested = select_perturbation_plan(
        model,
        hypotheses,
        max_perturbations=max_perturbations,
        critical_threshold=CRITICAL_PERTURBATION_THRESHOLD,
    )
    effects: list[PerturbationEffect] = []
    for item in plan:
        effect, _, _ = run_single_perturbation(
            model,
            baseline_result,
            item,
            hypotheses,
        )
        effects.append(effect)
    unresolved = [*alternative_gaps, *causal_gaps, *object_gaps]
    raw_policy = model.metadata.get("storyline_depth_policy") or {}
    if not isinstance(raw_policy, dict):
        raw_policy = {}
    prediction_requested = bool(
        raw_policy.get("prediction_requested")
        or model.metadata.get("prediction_requested")
    )
    predictive_holdout_status = "not_requested"
    if prediction_requested:
        predictive_holdout_status = "unsupported_without_native_future_holdout"
        unresolved.append(
            {
                "gap_id": "predictive_holdout_not_supported",
                "severity": "blocking",
                "message": "TraceGuard storyline perturbations are not a future holdout predictor; route prediction through a target-owned rollout validator.",
            }
        )
    if not baseline_result.ok:
        unresolved.append(
            {
                "gap_id": "baseline_model_not_ok",
                "severity": "blocking",
                "message": "The baseline TraceGuard evaluation is non-passing; perturbation depth cannot license a broad storyline claim.",
            }
        )
    if not hypotheses:
        unresolved.append(
            {
                "gap_id": "missing_storyline_hypothesis",
                "severity": "blocking",
                "message": "No trace or explicit storyline hypothesis is available for depth analysis.",
            }
        )
    effective_count = sum(1 for effect in effects if effect.counts_toward_depth)
    if plan and effective_count == 0:
        unresolved.append(
            {
                "gap_id": "no_effective_perturbation",
                "severity": "blocking",
                "message": "Planned perturbations changed no storyline rank, confidence, support, contradiction, or gap state.",
            }
        )
    executed_ids = {effect.perturbation.perturbation_id for effect in effects}
    critical_ids = {
        item.perturbation_id
        for item in candidates
        if item.priority_score >= CRITICAL_PERTURBATION_THRESHOLD
    }
    critical_uncovered = tuple(sorted(critical_ids - executed_ids))
    if critical_uncovered:
        unresolved.append(
            {
                "gap_id": "untested_high_impact_perturbations",
                "severity": "blocking_for_broad_claim",
                "perturbation_ids": list(critical_uncovered),
                "message": "Known critical model-derived perturbations were not executed.",
            }
        )
    effect_by_id = {
        effect.perturbation.perturbation_id: effect
        for effect in effects
    }
    critical_ineffective = tuple(
        sorted(
            perturbation_id
            for perturbation_id in critical_ids & executed_ids
            if not effect_by_id[perturbation_id].counts_toward_depth
        )
    )
    if critical_ineffective:
        unresolved.append(
            {
                "gap_id": "ineffective_critical_perturbations",
                "severity": "blocking_for_broad_claim",
                "perturbation_ids": list(critical_ineffective),
                "message": "Every critical perturbation must be effective or explicitly predeclared as an informative null.",
            }
        )
    sensitivity_mismatches = tuple(
        sorted(
            effect.perturbation.expected_sensitivity_id
            for effect in effects
            if effect.perturbation.kind == "expected_sensitivity"
            and not _expected_sensitivity_matches(model, effect)
        )
    )
    if sensitivity_mismatches:
        unresolved.append(
            {
                "gap_id": "expected_sensitivity_mismatch",
                "severity": "blocking_for_broad_claim",
                "sensitivity_ids": list(sensitivity_mismatches),
                "message": "Same-engine perturbation behavior did not match its predeclared expected sensitivity.",
            }
        )
    coverage_by_kind: list[dict[str, Any]] = []
    uncovered_required_kinds: list[str] = []
    for kind in (
        "evidence_removal",
        "contradiction_injection",
        "evidence_ablation",
        "expected_sensitivity",
    ):
        kind_candidates = [item for item in candidates if item.kind == kind]
        if not kind_candidates:
            continue
        kind_critical = [
            item for item in kind_candidates if item.priority_score >= CRITICAL_PERTURBATION_THRESHOLD
        ]
        kind_executed = [item for item in kind_candidates if item.perturbation_id in executed_ids]
        kind_effective = [
            effect
            for effect in effects
            if effect.perturbation.kind == kind and effect.counts_toward_depth
        ]
        required_count = len(kind_critical) if kind_critical else 1
        covered_required = (
            sum(1 for item in kind_critical if item.perturbation_id in executed_ids)
            if kind_critical
            else (1 if kind_executed else 0)
        )
        if covered_required < required_count:
            uncovered_required_kinds.append(kind)
        coverage_by_kind.append(
            {
                "kind": kind,
                "eligible_count": len(kind_candidates),
                "critical_count": len(kind_critical),
                "selected_count": sum(1 for item in plan if item.kind == kind),
                "executed_count": len(kind_executed),
                "effective_count": len(kind_effective),
                "required_count": required_count,
                "required_coverage_ratio": covered_required / required_count,
            }
        )
    if uncovered_required_kinds:
        unresolved.append(
            {
                "gap_id": "perturbation_kind_coverage_incomplete",
                "severity": "blocking_for_broad_claim",
                "kinds": uncovered_required_kinds,
                "message": "At least one available perturbation kind has no required execution coverage.",
            }
        )
    blocking_causal = any(
        gap.get("gap_id") in {
            "qualitative_causal_insufficient",
            "qualitative_causal_contested",
            "missing_causal_mechanism",
            "missing_confounder_review",
            "mechanism_evidence_incomplete",
            "unresolved_confounder_review",
            "missing_causal_alternative",
            "missing_causal_scope",
        }
        for gap in unresolved
    )
    blocking_baseline = any(gap.get("gap_id") == "baseline_model_not_ok" for gap in unresolved)
    blocking_object_or_prediction = any(
        gap.get("gap_id") in {"critical_object_depth_incomplete", "predictive_holdout_not_supported"}
        for gap in unresolved
    )
    if blocking_causal or blocking_baseline or blocking_object_or_prediction:
        closure_status = "BLOCKED"
    elif (
        unresolved
        or not plan
        or critical_uncovered
        or critical_ineffective
        or sensitivity_mismatches
        or uncovered_required_kinds
    ):
        closure_status = "GAP"
    else:
        closure_status = "PASS"
    broad_claim_licensed = requested_claim_scope == "broad" and closure_status == "PASS"
    covered_claim_scope = (
        "broad"
        if broad_claim_licensed
        else ("bounded" if effects else "not_run")
    )
    coverage_counts = {
        "eligible_count": len(candidates),
        "critical_count": len(critical_ids),
        "selected_count": len(plan),
        "executed_count": len(effects),
        "effective_count": effective_count,
        "ineffective_count": sum(1 for effect in effects if not effect.counts_toward_depth),
        "untested_count": len(candidates) - len(executed_ids),
        "critical_uncovered_count": len(critical_uncovered),
    }
    receipt_id = f"traceguard-depth:{fingerprint[:16]}"
    return StorylineDepthReceipt(
        schema_version="researchguard.trace.storyline_depth.v2",
        receipt_id=receipt_id,
        model_fingerprint=fingerprint,
        baseline={
            "ok": baseline_result.ok,
            "objective_score": baseline_result.objective_score,
            "hypothesis_snapshots": [
                item.to_dict() for item in baseline_snapshots
            ],
            "diagnostic_count": len(baseline_result.diagnostics),
            "gap_count": len(baseline_result.gaps),
            "contradiction_count": len(baseline_result.contradictions),
        },
        hypotheses=tuple(
            {
                "hypothesis_id": hypothesis.hypothesis_id,
                "claim": hypothesis.claim,
                "role": hypothesis.role,
                "trace_ids": list(hypothesis.trace_ids),
                "event_ids": list(hypothesis.event_ids),
                "evidence_ids": list(hypothesis.evidence_ids),
                "importance": hypothesis.importance,
                "uncertainty": hypothesis.uncertainty,
                "causal": hypothesis.causal,
                "derived_from_trace": hypothesis.hypothesis_id.startswith("implicit:"),
            }
            for hypothesis in hypotheses
        ),
        alternatives=alternatives,
        causal_coverage=causal_coverage,
        object_universe_fingerprint=object_universe_fingerprint,
        object_coverage_counts=object_coverage_counts,
        object_depth_rows=object_depth_rows,
        temporal_coverage=temporal_coverage,
        native_obligation_evidence=_native_obligation_observations(
            model,
            hypotheses,
            object_depth_rows,
            plan,
            tuple(effects),
        ),
        perturbation_plan=plan,
        effects=tuple(effects),
        unresolved_gaps=tuple(unresolved),
        untested_high_impact=untested,
        candidate_universe_fingerprint=candidate_universe_fingerprint,
        critical_threshold=CRITICAL_PERTURBATION_THRESHOLD,
        coverage_counts=coverage_counts,
        coverage_by_kind=tuple(coverage_by_kind),
        critical_uncovered_ids=critical_uncovered,
        critical_ineffective_ids=critical_ineffective,
        sensitivity_mismatch_ids=sensitivity_mismatches,
        effective_perturbation_count=effective_count,
        requested_claim_scope=requested_claim_scope,
        covered_claim_scope=covered_claim_scope,
        broad_claim_licensed=broad_claim_licensed,
        predictive_holdout_status=predictive_holdout_status,
        predictive_claim_licensed=False,
        closure_status=closure_status,
        claim_boundary=(
            "This receipt reports TraceGuard model behavior only for its exact fingerprinted candidate universe, "
            "executed perturbations, and covered claim scope. "
            "It does not prove factual truth, causal identification, calibrated probability, or future real-world outcomes."
        ),
    )
