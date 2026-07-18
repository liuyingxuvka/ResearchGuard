"""Temporal-order and stage factors for the unified objective."""

from __future__ import annotations

from itertools import combinations

from ...diagnostics import Contradiction, Gap
from ...schema import TraceGuardModel
from ...stage_model import stage_for_event, stronger_stage, valid_stage_transition
from ...temporal import allen_relation
from ..policy import InferencePolicy
from ..types import HardConstraint, HingeFactor, LinearExpression, ObservedAtom


def build_temporal_stage_factors(
    model: TraceGuardModel,
    policy: InferencePolicy,
) -> dict[str, object]:
    events = model.event_by_id()
    observed: list[ObservedAtom] = []
    factors: list[HingeFactor] = []
    constraints: list[HardConstraint] = []
    gaps: list[Gap] = []
    contradictions: list[Contradiction] = []
    trace_stages: dict[str, str] = {}

    for trace in model.traces:
        trace_events = [events[event_id] for event_id in trace.event_ids]
        trace_atom_id = f"trace_support:{trace.trace_id}"
        stage = trace.current_stage if trace.current_stage != "unknown" else "unknown"
        for event in trace_events:
            stage = stronger_stage(
                stage,
                stage_for_event(event.event_type, event.stage_hint),
            )
            if event.time_interval is None or event.time_interval.precision == "unknown":
                gaps.append(
                    Gap(
                        "missing_date",
                        "warning",
                        f"Event {event.event_id} has missing or unknown time.",
                        trace.trace_id,
                        "Find dated evidence or keep temporal order uncertain.",
                    )
                )
        trace_stages[trace.trace_id] = stage

        dated_events = [
            event for event in trace_events if event.time_interval is not None
        ]
        pair_scores: list[float] = []
        for left, right in combinations(dated_events, 2):
            relation = allen_relation(left.time_interval, right.time_interval)
            left_stage = stage_for_event(left.event_type, left.stage_hint)
            right_stage = stage_for_event(right.event_type, right.stage_hint)
            pair_contradictions: list[tuple[str, str]] = []
            if relation in {"before", "meets"} and not valid_stage_transition(
                left_stage, right_stage
            ):
                pair_contradictions.append(
                    (
                        "stage_reversal",
                        f"Stage reversal: {left_stage} occurs before {right_stage}.",
                    )
                )
            elif relation in {"after", "met_by"} and not valid_stage_transition(
                right_stage, left_stage
            ):
                pair_contradictions.append(
                    (
                        "temporal_contradiction",
                        f"Temporal contradiction: later-stage {left_stage} is dated "
                        f"before {right_stage}.",
                    )
                )
            if (
                left_stage == "operation"
                and right_stage in {"tendering", "awarded", "funded"}
                and relation in {"before", "meets"}
            ) or (
                right_stage == "operation"
                and left_stage in {"tendering", "awarded", "funded"}
                and relation in {"after", "met_by"}
            ):
                pair_contradictions.append(
                    (
                        "operation_before_tender",
                        "Operation evidence predates tender or funding evidence.",
                    )
                )
            if pair_contradictions:
                for contradiction_code, message in pair_contradictions:
                    contradictions.append(
                        Contradiction(
                            contradiction_code,
                            "error",
                            message,
                            (left.event_id, right.event_id),
                            True,
                        )
                    )
                pair_scores.append(0.0)
            elif relation == "unknown":
                pair_scores.append(0.5)
            else:
                pair_scores.append(1.0)

        temporal_score = (
            sum(pair_scores) / len(pair_scores)
            if pair_scores
            else (0.5 if trace_events else 0.0)
        )
        temporal_id = f"temporal_consistency:{trace.trace_id}"
        observed.append(
            ObservedAtom(
                atom_id=temporal_id,
                value=temporal_score,
                kind="temporal_consistency",
                object_id=trace.trace_id,
                evidence_ids=tuple(
                    evidence_id
                    for event in trace_events
                    for evidence_id in event.evidence_ids
                ),
            )
        )
        factors.append(
            HingeFactor(
                factor_id=f"temporal-support:{trace.trace_id}",
                family="temporal_stage",
                description="A coherent temporal and stage order supports the trace.",
                expression=LinearExpression(
                    ((temporal_id, 0.7), (trace_atom_id, -1.0))
                ),
                weight=policy.temporal_weight,
                affected_object_ids=(trace.trace_id,),
                direction="support",
            )
        )
        if pair_scores and min(pair_scores) == 0.0:
            constraints.append(
                HardConstraint(
                    constraint_id=f"temporal-contradiction-cap:{trace.trace_id}",
                    description="A blocking temporal contradiction caps trace support.",
                    expression=LinearExpression(((trace_atom_id, 1.0),)),
                    upper=max(0.0, policy.weak_signal_threshold - 0.01),
                    affected_object_ids=(trace.trace_id,),
                )
            )

    return {
        "observed_atoms": observed,
        "latent_atoms": [],
        "factors": factors,
        "hard_constraints": constraints,
        "diagnostics": [],
        "gaps": gaps,
        "contradictions": contradictions,
        "metadata": {"trace_stages": trace_stages},
    }
