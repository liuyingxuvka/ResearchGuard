"""Single compile-solve-explain-project orchestration authority."""

from __future__ import annotations

from dataclasses import replace

from .compiler import compile_model
from .explain import explain_solution
from .osqp_backend import solve_problem
from .policy import DEFAULT_POLICY, InferencePolicy
from .projection import project_hypotheses, project_traces
from .types import InferenceReceipt, fingerprint
from ..entity_resolution import EntityScore
from ..results import EvaluationResult, RuleResult, TraceEvaluation
from ..schema import TraceGuardModel
from ..schema import StorylineHypothesis


CLAIM_BOUNDARY = (
    "TraceGuard solves one declared constrained HL-MRF/MAP model. Its outputs "
    "are structural support and bounded qualitative causal licenses, not "
    "calibrated probability, factual proof, do-operator identification, ATE, "
    "or CATE."
)


def _receipt_payload(
    *,
    problem,
    solution,
    contributions,
    trace_projections,
    hypothesis_projections,
    policy: InferencePolicy,
) -> dict[str, object]:
    return {
        "problem_fingerprint": problem.problem_fingerprint,
        "solution_fingerprint": solution.solution_fingerprint,
        "atom_values_fingerprint": fingerprint(solution.atom_values),
        "factor_catalog_fingerprint": fingerprint(
            [item.to_dict() for item in problem.factors]
        ),
        "hard_constraint_catalog_fingerprint": fingerprint(
            [item.to_dict() for item in problem.hard_constraints]
        ),
        "provenance_fingerprint": fingerprint(
            [
                {
                    "atom_id": item.atom_id,
                    "evidence_ids": item.evidence_ids,
                    "lineage_ids": item.lineage_ids,
                    "metadata": item.metadata,
                }
                for item in problem.observed_atoms
            ]
        ),
        "schema_id": problem.schema_id,
        "policy_id": problem.policy_id,
        "factor_set_id": problem.factor_set_id,
        "solver_id": problem.solver_id,
        "solver_configuration_fingerprint": policy.solver_configuration_fingerprint,
        "solver_backend": solution.backend,
        "solver_backend_version": solution.backend_version,
        "solver_status": solution.status,
        "primal_residual": solution.primal_residual,
        "dual_residual": solution.dual_residual,
        "maximum_constraint_violation": solution.maximum_constraint_violation,
        "iterations": solution.iterations,
        "objective": solution.objective,
        "hard_constraint_ids": [
            item.constraint_id for item in problem.hard_constraints
        ],
        "contribution_fingerprint": fingerprint(
            [item.to_dict() for item in contributions]
        ),
        "trace_projections": [item.to_dict() for item in trace_projections],
        "hypothesis_projections": [
            item.to_dict() for item in hypothesis_projections
        ],
    }


def verify_inference_receipt(receipt: InferenceReceipt) -> None:
    """Fail when a projection or receipt identity is detached from its evidence."""

    contribution_ids = [item.factor_id for item in receipt.contributions]
    if len(contribution_ids) != len(set(contribution_ids)):
        raise ValueError("inference receipt has duplicate factor contributions")
    contribution_set = set(contribution_ids)
    constraint_set = set(receipt.hard_constraint_ids)
    for projection in (
        *receipt.trace_projections,
        *receipt.hypothesis_projections,
    ):
        if not set(projection.top_support_factor_ids) <= contribution_set:
            raise ValueError("projection references detached supporting factors")
        if not set(projection.top_opposition_factor_ids) <= contribution_set:
            raise ValueError("projection references detached opposing factors")
        binding_ids = getattr(projection, "binding_constraint_ids", ())
        if not set(binding_ids) <= constraint_set:
            raise ValueError("projection references detached hard constraints")
    identity_payload = {
        "problem_fingerprint": receipt.problem_fingerprint,
        "solution_fingerprint": receipt.solution_fingerprint,
        "atom_values_fingerprint": receipt.atom_values_fingerprint,
        "factor_catalog_fingerprint": receipt.factor_catalog_fingerprint,
        "hard_constraint_catalog_fingerprint": (
            receipt.hard_constraint_catalog_fingerprint
        ),
        "provenance_fingerprint": receipt.provenance_fingerprint,
        "schema_id": receipt.schema_id,
        "policy_id": receipt.policy_id,
        "factor_set_id": receipt.factor_set_id,
        "solver_id": receipt.solver_id,
        "solver_configuration_fingerprint": (
            receipt.solver_configuration_fingerprint
        ),
        "solver_backend": receipt.solver_backend,
        "solver_backend_version": receipt.solver_backend_version,
        "solver_status": receipt.solver_status,
        "primal_residual": receipt.primal_residual,
        "dual_residual": receipt.dual_residual,
        "maximum_constraint_violation": receipt.maximum_constraint_violation,
        "iterations": receipt.iterations,
        "objective": receipt.objective,
        "hard_constraint_ids": list(receipt.hard_constraint_ids),
        "contribution_fingerprint": fingerprint(
            [item.to_dict() for item in receipt.contributions]
        ),
        "trace_projections": [
            item.to_dict() for item in receipt.trace_projections
        ],
        "hypothesis_projections": [
            item.to_dict() for item in receipt.hypothesis_projections
        ],
    }
    expected_id = f"traceguard-inference-{fingerprint(identity_payload)[:24]}"
    if receipt.receipt_id != expected_id:
        raise ValueError("inference receipt content fingerprint mismatch")


def _entity_scores(model: TraceGuardModel, problem, solution) -> tuple[EntityScore, ...]:
    rows: list[EntityScore] = []
    for item in problem.metadata.get("entity_pairs", []):
        score = float(solution.atom_values[item["atom_id"]])
        blockers = tuple(item["blockers"])
        if score >= 0.86 and not blockers:
            relation = "same_as"
        elif score >= 0.55:
            relation = "possible_same_as"
        elif blockers:
            relation = "different"
        else:
            relation = "unknown"
        rows.append(
            EntityScore(
                left_id=str(item["left_id"]),
                right_id=str(item["right_id"]),
                relation=relation,
                score=score,
                reasons=tuple(item["reasons"]),
                blockers=blockers,
            )
        )
    return tuple(rows)


def _rule_results_for_trace(
    trace_id: str,
    contributions,
) -> tuple[RuleResult, ...]:
    rows: list[RuleResult] = []
    for item in contributions:
        if trace_id not in item.affected_object_ids:
            continue
        rows.append(
            RuleResult(
                rule_id=item.factor_id,
                family=item.family,
                description=item.explanation,
                weight=1.0,
                violation=item.violation,
                loss=item.loss,
                affected_object_ids=item.affected_object_ids,
                why_it_matters=(
                    "This factor is part of the one canonical inference objective."
                ),
                repair_hint="Inspect the factor evidence and binding constraints.",
                blocking=False,
                affects_validation_status=item.loss > 0,
            )
        )
    return tuple(sorted(rows, key=lambda item: item.rule_id))


def infer_model(
    model: TraceGuardModel,
    *,
    policy: InferencePolicy = DEFAULT_POLICY,
) -> EvaluationResult:
    """TraceGuardModel x Policy -> EvaluationResult."""

    inference_model = model
    if not model.storyline_hypotheses:
        inference_model = replace(
            model,
            storyline_hypotheses=tuple(
                StorylineHypothesis(
                    hypothesis_id=f"implicit:{trace.trace_id}",
                    claim=trace.claim or trace.title,
                    role="primary" if index == 0 else "alternative",
                    trace_ids=[trace.trace_id],
                    event_ids=list(trace.event_ids),
                    importance=trace.importance,
                    uncertainty=0.5,
                    causal=False,
                    bounded_non_causal=True,
                )
                for index, trace in enumerate(model.traces)
            ),
        )
    problem = compile_model(inference_model, policy)
    solution = solve_problem(problem, policy)
    contributions = explain_solution(problem, solution, policy)
    trace_projections = project_traces(
        inference_model,
        problem,
        solution,
        contributions,
        policy,
    )
    hypothesis_projections = project_hypotheses(
        inference_model,
        problem,
        solution,
        contributions,
        policy,
    )
    entity_scores = _entity_scores(model, problem, solution)
    diagnostics = tuple(problem.metadata.get("diagnostics", ()))
    gaps = tuple(problem.metadata.get("gaps", ()))
    contradictions = tuple(problem.metadata.get("contradictions", ()))
    receipt_payload = _receipt_payload(
        problem=problem,
        solution=solution,
        contributions=contributions,
        trace_projections=trace_projections,
        hypothesis_projections=hypothesis_projections,
        policy=policy,
    )
    receipt = InferenceReceipt(
        receipt_id=f"traceguard-inference-{fingerprint(receipt_payload)[:24]}",
        problem_fingerprint=problem.problem_fingerprint,
        solution_fingerprint=solution.solution_fingerprint,
        atom_values_fingerprint=str(receipt_payload["atom_values_fingerprint"]),
        factor_catalog_fingerprint=str(
            receipt_payload["factor_catalog_fingerprint"]
        ),
        hard_constraint_catalog_fingerprint=str(
            receipt_payload["hard_constraint_catalog_fingerprint"]
        ),
        provenance_fingerprint=str(receipt_payload["provenance_fingerprint"]),
        schema_id=problem.schema_id,
        policy_id=problem.policy_id,
        factor_set_id=problem.factor_set_id,
        solver_id=problem.solver_id,
        solver_configuration_fingerprint=policy.solver_configuration_fingerprint,
        solver_backend=solution.backend,
        solver_backend_version=solution.backend_version,
        solver_status=solution.status,
        primal_residual=solution.primal_residual,
        dual_residual=solution.dual_residual,
        maximum_constraint_violation=solution.maximum_constraint_violation,
        iterations=solution.iterations,
        objective=solution.objective,
        hard_constraint_ids=tuple(
            item.constraint_id for item in problem.hard_constraints
        ),
        contributions=contributions,
        trace_projections=trace_projections,
        hypothesis_projections=hypothesis_projections,
        diagnostics=diagnostics,
        gaps=gaps,
        contradictions=contradictions,
        claim_boundary=CLAIM_BOUNDARY,
    )
    verify_inference_receipt(receipt)
    trace_by_id = {item.trace_id: item for item in model.traces}
    trace_results = tuple(
        TraceEvaluation(
            trace_id=projection.trace_id,
            title=trace_by_id[projection.trace_id].title,
            trace_type=trace_by_id[projection.trace_id].trace_type,
            validation_status=projection.validation_status,
            support=projection.support,
            current_stage=projection.current_stage,
            evidence_ids=projection.evidence_ids,
            rule_results=_rule_results_for_trace(
                projection.trace_id,
                contributions,
            ),
            diagnostics=tuple(
                item
                for item in diagnostics
                if projection.trace_id in item.affected_object_ids
                or any(
                    event_id in item.affected_object_ids
                    for event_id in trace_by_id[projection.trace_id].event_ids
                )
            ),
            gaps=tuple(
                item for item in gaps if item.trace_id == projection.trace_id
            ),
            contradictions=tuple(
                item
                for item in contradictions
                if projection.trace_id in item.affected_object_ids
                or any(
                    event_id in item.affected_object_ids
                    for event_id in trace_by_id[projection.trace_id].event_ids
                )
            ),
            claim_boundary=projection.claim_boundary,
            safe_wording=projection.safe_wording,
            unsafe_wording_avoided=projection.unsafe_wording_avoided,
            structure_unit_id=trace_by_id[projection.trace_id].structure_unit_id or "",
            source_unit_id=trace_by_id[projection.trace_id].source_unit_id or "",
            destination_unit_id=trace_by_id[
                projection.trace_id
            ].destination_unit_id
            or "",
            trace_layer=trace_by_id[projection.trace_id].trace_layer or "",
            weakest_link=trace_by_id[projection.trace_id].weakest_link or "",
            conclusion_transfer_status=trace_by_id[
                projection.trace_id
            ].conclusion_transfer_status
            or "",
            downstream_consumer=trace_by_id[
                projection.trace_id
            ].downstream_consumer
            or "",
        )
        for projection in trace_projections
    )
    ok = not any(item.blocking for item in diagnostics) and not contradictions
    return EvaluationResult(
        ok=ok,
        objective_score=round(solution.objective, 6),
        traces=trace_results,
        entity_scores=entity_scores,
        diagnostics=diagnostics,
        gaps=gaps,
        contradictions=contradictions,
        inference_receipt=receipt,
    )
