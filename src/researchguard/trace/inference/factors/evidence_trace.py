"""Evidence, lineage, and trace-support factors."""

from __future__ import annotations

from collections import defaultdict

from ...diagnostics import Diagnostic, Gap
from ...schema import EvidenceItem, SourceRecord, TraceGuardModel, clamp01
from ..policy import InferencePolicy
from ..types import (
    HardConstraint,
    HingeFactor,
    LatentAtom,
    LinearExpression,
    ObservedAtom,
)


WEAK_EVIDENCE_TYPES = {"patent", "hiring", "source_only", "news", "keyword_hit"}
LOCATION_REQUIRED_TRACE_TYPES = {
    "project",
    "project_signal",
    "technology_signal",
    "deployment",
    "infrastructure",
    "asset_trace",
    "geospatial_trace",
}


def source_quality(source: SourceRecord) -> float:
    if source.source_status == "invalid_or_empty":
        return 0.0
    if source.source_status == "need_auth_or_permission":
        return 0.15
    bonus = (
        0.1
        if source.source_type
        in {"funding", "procurement", "government_database", "company_page"}
        else 0.0
    )
    return clamp01(source.source_reliability + bonus)


def evidence_quality(
    evidence: EvidenceItem,
    source: SourceRecord,
    policy: InferencePolicy,
) -> float:
    if evidence.usable_as_trace_evidence is False:
        return 0.0
    extraction = (
        source_quality(source)
        + evidence.extraction_confidence
        + evidence.evidence_specificity
    ) / 3.0
    type_strength = policy.evidence_type_strength.get(
        evidence.evidence_type,
        policy.evidence_type_strength["unknown"],
    )
    return clamp01(extraction * (0.55 + 0.45 * type_strength))


def _combined_independent_support(values: list[float]) -> float:
    """Combine independent lanes while each lineage contributes at most once."""

    residual = 1.0
    for value in sorted(values, reverse=True):
        residual *= 1.0 - 0.72 * clamp01(value)
    return clamp01(1.0 - residual)


def build_evidence_trace_factors(
    model: TraceGuardModel,
    policy: InferencePolicy,
) -> dict[str, object]:
    sources = model.source_by_id()
    evidence = model.evidence_by_id()
    events = model.event_by_id()
    observed: list[ObservedAtom] = []
    latent: list[LatentAtom] = []
    factors: list[HingeFactor] = []
    constraints: list[HardConstraint] = []
    diagnostics: list[Diagnostic] = []
    gaps: list[Gap] = []
    metadata: dict[str, object] = {
        "trace_evidence_ids": {},
        "trace_evidence_types": {},
        "trace_lineage_groups": {},
    }

    evidence_quality_by_id: dict[str, float] = {}
    for item in model.evidence:
        quality = evidence_quality(item, sources[item.source_id], policy)
        evidence_quality_by_id[item.evidence_id] = quality
        source = sources[item.source_id]
        observed.append(
            ObservedAtom(
                atom_id=f"evidence_quality:{item.evidence_id}",
                value=quality,
                kind="evidence_quality",
                object_id=item.evidence_id,
                evidence_ids=(item.evidence_id,),
                lineage_ids=(source.lineage_id,),
                metadata={
                    "independence_group": source.independence_group,
                    "source_id": source.source_id,
                    "evidence_type": item.evidence_type,
                },
            )
        )

    for trace in model.traces:
        trace_atom_id = f"trace_support:{trace.trace_id}"
        latent.append(
            LatentAtom(
                atom_id=trace_atom_id,
                kind="trace_support",
                object_id=trace.trace_id,
            )
        )
        factors.append(
            HingeFactor(
                factor_id=f"trace-sparsity:{trace.trace_id}",
                family="sparsity",
                description="Unsupported trace support should remain low.",
                expression=LinearExpression(((trace_atom_id, 1.0),)),
                weight=policy.sparsity_weight,
                power=2,
                affected_object_ids=(trace.trace_id,),
                direction="oppose",
            )
        )

        trace_events = [events[event_id] for event_id in trace.event_ids]
        trace_evidence_ids = sorted(
            {
                evidence_id
                for event in trace_events
                for evidence_id in event.evidence_ids
            }
        )
        trace_evidence = [evidence[evidence_id] for evidence_id in trace_evidence_ids]
        evidence_types = sorted({item.evidence_type for item in trace_evidence})
        metadata["trace_evidence_ids"][trace.trace_id] = trace_evidence_ids
        metadata["trace_evidence_types"][trace.trace_id] = evidence_types

        ungrounded_events = [
            event for event in trace_events if not event.evidence_ids
        ]
        for event in ungrounded_events:
            diagnostics.append(
                Diagnostic(
                    "no_evidence_no_event",
                    "error",
                    "Event has no evidence_id support.",
                    (trace.trace_id, event.event_id),
                    True,
                    "Add evidence_ids or remove the event.",
                    "hard_gate",
                )
            )
        if ungrounded_events:
            constraints.append(
                HardConstraint(
                    constraint_id=f"ungrounded-event-blocks-trace:{trace.trace_id}",
                    description="Every trace event must be source-backed.",
                    expression=LinearExpression(((trace_atom_id, 1.0),)),
                    upper=0.0,
                    affected_object_ids=(
                        trace.trace_id,
                        *(event.event_id for event in ungrounded_events),
                    ),
                )
            )

        groups: dict[str, list[EvidenceItem]] = defaultdict(list)
        for item in trace_evidence:
            groups[sources[item.source_id].independence_group].append(item)
        group_values = [
            max(evidence_quality_by_id[item.evidence_id] for item in items)
            for _, items in sorted(groups.items())
        ]
        combined = _combined_independent_support(group_values)
        combined_id = f"trace_evidence_support:{trace.trace_id}"
        observed.append(
            ObservedAtom(
                atom_id=combined_id,
                value=combined,
                kind="trace_evidence_support",
                object_id=trace.trace_id,
                evidence_ids=tuple(trace_evidence_ids),
                lineage_ids=tuple(sorted(groups)),
                metadata={
                    "independence_group_count": len(groups),
                    "lineage_deduplicated": True,
                },
            )
        )
        metadata["trace_lineage_groups"][trace.trace_id] = sorted(groups)
        factors.append(
            HingeFactor(
                factor_id=f"evidence-supports-trace:{trace.trace_id}",
                family="evidence_trace",
                description="Lineage-deduplicated evidence supports trace truth.",
                expression=LinearExpression(
                    ((combined_id, 1.0), (trace_atom_id, -1.0))
                ),
                weight=policy.evidence_support_weight,
                power=2,
                affected_object_ids=(trace.trace_id,),
                evidence_ids=tuple(trace_evidence_ids),
                direction="support",
            )
        )

        if len(groups) >= 2:
            multi_id = f"independent_sources:{trace.trace_id}"
            observed.append(
                ObservedAtom(
                    atom_id=multi_id,
                    value=min(1.0, len(groups) / 3.0),
                    kind="independent_source_coverage",
                    object_id=trace.trace_id,
                    evidence_ids=tuple(trace_evidence_ids),
                    lineage_ids=tuple(sorted(groups)),
                )
            )
            factors.append(
                HingeFactor(
                    factor_id=f"independent-support:{trace.trace_id}",
                    family="source_independence",
                    description="Independent source lanes reinforce trace support.",
                    expression=LinearExpression(
                        ((multi_id, 0.65), (trace_atom_id, -1.0))
                    ),
                    weight=policy.independent_source_weight,
                    affected_object_ids=(trace.trace_id,),
                    evidence_ids=tuple(trace_evidence_ids),
                    direction="support",
                )
            )

        if not trace_events or not trace_evidence:
            constraints.append(
                HardConstraint(
                    constraint_id=f"no-evidence-no-trace:{trace.trace_id}",
                    description="A trace without source-backed events has zero support.",
                    expression=LinearExpression(((trace_atom_id, 1.0),)),
                    upper=0.0,
                    affected_object_ids=(trace.trace_id,),
                )
            )
            diagnostics.append(
                Diagnostic(
                    "no_evidence_no_trace",
                    "error",
                    "Trace has no source-backed events.",
                    (trace.trace_id,),
                    True,
                    "Attach evidence-backed events.",
                    "hard_gate",
                )
            )

        invalid = [
            item
            for item in trace_evidence
            if sources[item.source_id].source_status == "invalid_or_empty"
        ]
        if invalid:
            constraints.append(
                HardConstraint(
                    constraint_id=f"invalid-source-blocks-trace:{trace.trace_id}",
                    description="Invalid sources cannot support a trace.",
                    expression=LinearExpression(((trace_atom_id, 1.0),)),
                    upper=0.0,
                    affected_object_ids=(trace.trace_id,),
                    evidence_ids=tuple(item.evidence_id for item in invalid),
                )
            )
            diagnostics.append(
                Diagnostic(
                    "invalid_source_not_validation_evidence",
                    "error",
                    "invalid_or_empty source cannot support validation evidence.",
                    tuple(item.evidence_id for item in invalid),
                    True,
                    "Remove invalid evidence from trace evaluation.",
                    "hard_gate",
                )
            )

        if trace_evidence and set(evidence_types) <= {"source_only"}:
            constraints.append(
                HardConstraint(
                    constraint_id=f"source-only-boundary:{trace.trace_id}",
                    description="A source registry entry is not a trace.",
                    expression=LinearExpression(((trace_atom_id, 1.0),)),
                    upper=max(0.0, policy.weak_signal_threshold - 0.01),
                    affected_object_ids=(trace.trace_id,),
                    evidence_ids=tuple(trace_evidence_ids),
                )
            )
            diagnostics.append(
                Diagnostic(
                    "source_entry_is_not_trace",
                    "error",
                    "Source registry rows cannot directly become traces or storylines.",
                    tuple(trace_evidence_ids),
                    True,
                    "Extract evidence and events before trace inference.",
                    "hard_gate",
                )
            )
        elif trace_evidence and set(evidence_types) <= WEAK_EVIDENCE_TYPES:
            constraints.append(
                HardConstraint(
                    constraint_id=f"weak-only-cap:{trace.trace_id}",
                    description="Weak-only evidence cannot validate a trace.",
                    expression=LinearExpression(((trace_atom_id, 1.0),)),
                    upper=max(
                        policy.weak_signal_threshold,
                        policy.candidate_threshold - 0.01,
                    ),
                    affected_object_ids=(trace.trace_id,),
                    evidence_ids=tuple(trace_evidence_ids),
                )
            )

        if any(
            sources[item.source_id].source_status == "need_auth_or_permission"
            for item in trace_evidence
        ):
            gaps.append(
                Gap(
                    "access_gap",
                    "warning",
                    "need_auth_or_permission source is an access gap, not checked evidence.",
                    trace.trace_id,
                    "Obtain permission or use another source.",
                )
            )

        if trace.trace_type in LOCATION_REQUIRED_TRACE_TYPES:
            for event in trace_events:
                if not event.location_ids:
                    gaps.append(
                        Gap(
                            "missing_location",
                            "warning",
                            f"Event {event.event_id} has no location.",
                            trace.trace_id,
                            "Find a source with a relevant location role.",
                        )
                    )
                for location_id in event.location_ids:
                    location = model.location_by_id().get(location_id)
                    if location is not None and location.location_role == "unknown":
                        diagnostics.append(
                            Diagnostic(
                                "location_role_required",
                                "warning",
                                "Location role is unknown and cannot be promoted to a site role.",
                                (trace.trace_id, location_id),
                                False,
                                "Declare the location role or keep the boundary unknown.",
                                "hard_gate",
                            )
                        )

    return {
        "observed_atoms": observed,
        "latent_atoms": latent,
        "factors": factors,
        "hard_constraints": constraints,
        "diagnostics": diagnostics,
        "gaps": gaps,
        "contradictions": [],
        "metadata": metadata,
    }
