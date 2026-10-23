"""Deterministic public projections from one verified inference solution."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from ..schema import TraceGuardModel
from .policy import InferencePolicy
from .types import (
    CompiledProblem,
    FactorContribution,
    HypothesisProjection,
    InferenceSolution,
    TraceProjection,
)


def _factor_ids(
    contributions: Iterable[FactorContribution],
    object_id: str,
    direction: str,
    *,
    limit: int = 5,
) -> tuple[str, ...]:
    rows = [
        item
        for item in contributions
        if object_id in item.affected_object_ids and item.direction == direction
    ]
    rows.sort(key=lambda item: (-item.loss, item.factor_id))
    return tuple(item.factor_id for item in rows[:limit])


def _binding_constraint_ids(
    problem: CompiledProblem,
    solution: InferenceSolution,
    object_id: str,
    tolerance: float,
) -> tuple[str, ...]:
    result: list[str] = []
    for constraint in problem.hard_constraints:
        if object_id not in constraint.affected_object_ids:
            continue
        value = constraint.expression.value(solution.atom_values)
        binding = (
            constraint.lower is not None
            and abs(value - float(constraint.lower)) <= tolerance
        ) or (
            constraint.upper is not None
            and abs(value - float(constraint.upper)) <= tolerance
        )
        if binding:
            result.append(constraint.constraint_id)
    return tuple(sorted(result))


def _status(
    support: float,
    evidence_types: set[str],
    has_blocking_diagnostic: bool,
    has_contradiction: bool,
    policy: InferencePolicy,
) -> str:
    if has_contradiction:
        return "contradicted"
    if has_blocking_diagnostic and evidence_types != {"source_only"}:
        return "insufficient"
    if evidence_types == {"source_only"}:
        return "source_only"
    if support >= policy.validated_threshold:
        return "validated"
    if support >= policy.candidate_threshold:
        return "candidate"
    if support >= policy.weak_signal_threshold:
        return "weak_signal"
    return "insufficient"


def _trace_boundary(status: str, stage: str) -> tuple[str, str, str]:
    if status == "validated":
        safe = (
            "The trace has current structural support for a validated storyline "
            "within the listed evidence boundary."
        )
    elif status == "candidate":
        safe = (
            f"The trace supports a candidate storyline around {stage}; it does "
            "not support confirmed wording without stronger evidence."
            if stage != "unknown"
            else "The trace supports a candidate storyline, not confirmed wording."
        )
    elif status == "weak_signal":
        safe = "The trace is a weak signal suitable for monitoring, not validation."
    elif status == "contradicted":
        safe = "The trace contains a blocking contradiction and is not a clean storyline."
    elif status == "source_only":
        safe = "This is source-only material and is not a trace or storyline."
    else:
        safe = "The trace is insufficient for a storyline claim."
    unsafe = (
        "confirmed, proven, causally established, or operational when unsupported"
        if status != "validated"
        else "factual certainty or proof beyond the declared evidence"
    )
    boundary = (
        "Support is the MAP solution of the declared constrained HL-MRF. "
        "It is structural support, not calibrated probability or factual proof."
    )
    return boundary, safe, unsafe


def project_traces(
    model: TraceGuardModel,
    problem: CompiledProblem,
    solution: InferenceSolution,
    contributions: tuple[FactorContribution, ...],
    policy: InferencePolicy,
) -> tuple[TraceProjection, ...]:
    diagnostics = tuple(problem.metadata.get("diagnostics", ()))
    contradictions = tuple(problem.metadata.get("contradictions", ()))
    evidence_types = problem.metadata.get("trace_evidence_types", {})
    evidence_ids = problem.metadata.get("trace_evidence_ids", {})
    stages = problem.metadata.get("trace_stages", {})
    rows: list[TraceProjection] = []
    for trace in model.traces:
        support = float(solution.atom_values[f"trace_support:{trace.trace_id}"])
        trace_types = set(evidence_types.get(trace.trace_id, []))
        has_blocking = any(
            item.blocking and trace.trace_id in item.affected_object_ids
            for item in diagnostics
        )
        has_contradiction = any(
            trace.trace_id in item.affected_object_ids
            or any(
                event_id in item.affected_object_ids for event_id in trace.event_ids
            )
            for item in contradictions
        )
        status = _status(
            support,
            trace_types,
            has_blocking,
            has_contradiction,
            policy,
        )
        stage = str(stages.get(trace.trace_id, trace.current_stage))
        boundary, safe, unsafe = _trace_boundary(status, stage)
        rows.append(
            TraceProjection(
                trace_id=trace.trace_id,
                support=support,
                validation_status=status,
                current_stage=stage,
                evidence_ids=tuple(evidence_ids.get(trace.trace_id, [])),
                top_support_factor_ids=_factor_ids(
                    contributions, trace.trace_id, "support"
                ),
                top_opposition_factor_ids=_factor_ids(
                    contributions, trace.trace_id, "oppose"
                ),
                binding_constraint_ids=_binding_constraint_ids(
                    problem,
                    solution,
                    trace.trace_id,
                    policy.binding_constraint_tolerance,
                ),
                claim_boundary=boundary,
                safe_wording=safe,
                unsafe_wording_avoided=unsafe,
            )
        )
    return tuple(rows)


def project_hypotheses(
    model: TraceGuardModel,
    problem: CompiledProblem,
    solution: InferenceSolution,
    contributions: tuple[FactorContribution, ...],
    policy: InferencePolicy,
) -> tuple[HypothesisProjection, ...]:
    support_by_id = {
        item.hypothesis_id: float(
            solution.atom_values[f"hypothesis_support:{item.hypothesis_id}"]
        )
        for item in model.storyline_hypotheses
    }
    order = sorted(support_by_id, key=lambda item: (-support_by_id[item], item))
    rank_by_id = {hypothesis_id: index + 1 for index, hypothesis_id in enumerate(order)}
    best = max(support_by_id.values(), default=0.0)
    causal_atoms = dict(problem.metadata.get("causal_atoms", {}))
    rows: list[HypothesisProjection] = []
    for hypothesis in model.storyline_hypotheses:
        support = support_by_id[hypothesis.hypothesis_id]
        causal_atom = causal_atoms.get(hypothesis.hypothesis_id)
        causal_support = (
            None if causal_atom is None else float(solution.atom_values[causal_atom])
        )
        if causal_support is None:
            causal_status = "not_requested"
        elif causal_support >= policy.causal_supported_threshold:
            causal_status = "supported"
        elif causal_support >= policy.causal_contested_threshold:
            causal_status = "contested"
        else:
            causal_status = "insufficient"
        rows.append(
            HypothesisProjection(
                hypothesis_id=hypothesis.hypothesis_id,
                support=support,
                rank=rank_by_id[hypothesis.hypothesis_id],
                live=(best - support) <= policy.alternative_live_margin,
                causal_support=causal_support,
                causal_status=causal_status,
                top_support_factor_ids=_factor_ids(
                    contributions, hypothesis.hypothesis_id, "support"
                ),
                top_opposition_factor_ids=_factor_ids(
                    contributions, hypothesis.hypothesis_id, "oppose"
                ),
                claim_boundary=(
                    "Qualitative causal support is licensed only inside declared "
                    "evidence, chronology, mechanism, alternatives, confounders, "
                    "and scope. It is not do-operator identification, ATE, or CATE."
                    if causal_support is not None
                    else "This is a competing-storyline support projection, not a causal claim."
                ),
            )
        )
    return tuple(sorted(rows, key=lambda item: (item.rank, item.hypothesis_id)))
