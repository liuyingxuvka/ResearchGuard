"""Single compile-solve-explain-project orchestration authority."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

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


@dataclass(frozen=True)
class _DomainFields:
    """One validated domain projection reused by all TraceEvaluation fields."""

    proposition: str
    mechanism_refs: tuple[str, ...]
    assumption_refs: tuple[str, ...]
    object_scope: tuple[str, ...]
    alternatives: tuple[str, ...]
    boundaries: tuple[str, ...]
    native_causal_license: str
    gaps: tuple[str, ...]
    candidate_propositions: tuple[str, ...]
    context: dict[str, object]


def _stable_strings(value: Any, *, gap_prefix: str, gaps: list[str]) -> tuple[str, ...]:
    """Accept typed string collections without iterating a scalar as characters."""

    if value in (None, ""):
        return ()
    if isinstance(value, str):
        gaps.append(f"{gap_prefix}:metadata_scalar_not_collection")
        return ()
    if not isinstance(value, (list, tuple, set)):
        gaps.append(f"{gap_prefix}:metadata_invalid_collection")
        return ()
    values: list[str] = []
    iterable = sorted(value, key=lambda item: str(item)) if isinstance(value, set) else value
    for item in iterable:
        if not isinstance(item, str):
            gaps.append(f"{gap_prefix}:non_string_ref")
            continue
        text = item.strip()
        if text and text not in values:
            values.append(text)
    return tuple(values)


def _metadata_assumption_ids(metadata: Mapping[str, Any]) -> set[str]:
    """Collect explicitly typed assumption declarations, if the model has them."""

    ids: set[str] = set()
    for key in ("assumptions", "domain_assumptions", "assumption_refs"):
        value = metadata.get(key)
        if isinstance(value, Mapping):
            for name, row in value.items():
                if isinstance(row, Mapping):
                    candidate = row.get("assumption_id", row.get("id", name))
                else:
                    candidate = name
                if isinstance(candidate, str) and candidate.strip():
                    ids.add(candidate.strip())
        elif isinstance(value, (list, tuple, set)):
            for row in value:
                if isinstance(row, Mapping):
                    candidate = row.get("assumption_id", row.get("id", ""))
                else:
                    candidate = row
                if isinstance(candidate, str) and candidate.strip():
                    ids.add(candidate.strip())
    return ids


def _metadata_domain_boundaries(metadata: Mapping[str, Any], trace_id: str, gaps: list[str]) -> list[str]:
    value = metadata.get("boundary", "")
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if value in (None, ""):
        return []
    if isinstance(value, Mapping):
        selected = value.get(trace_id, value.get("default", ""))
        if isinstance(selected, str):
            return [selected.strip()] if selected.strip() else []
        values = _stable_strings(selected, gap_prefix="domain_boundary", gaps=gaps)
        return list(values)
    values = _stable_strings(value, gap_prefix="domain_boundary", gaps=gaps)
    return list(values)


def _domain_fields(model: TraceGuardModel, trace) -> _DomainFields:
    """Project and validate source-declared domain objects without inventing a warrant."""

    linked = [item for item in model.storyline_hypotheses if trace.trace_id in item.trace_ids]
    linked_by_id = {item.hypothesis_id: item for item in linked}
    hypothesis_ids = set(linked_by_id)
    all_hypotheses = {item.hypothesis_id: item for item in model.storyline_hypotheses}
    domain_gaps: list[str] = []
    candidate_propositions: list[str] = []

    explicit_selection = ""
    selection_map = model.metadata.get("trace_hypothesis_selection", {})
    if isinstance(selection_map, Mapping):
        selected = selection_map.get(trace.trace_id, "")
        if isinstance(selected, str):
            explicit_selection = selected.strip()
        elif selected not in (None, ""):
            domain_gaps.append("invalid_trace_hypothesis_selection")
    elif selection_map not in (None, ""):
        domain_gaps.append("invalid_trace_hypothesis_selection_metadata")

    proposition = str(trace.claim or "").strip()
    if proposition:
        candidate_propositions.append(proposition)
    linked_claims: list[str] = []
    for item in linked:
        claim = str(item.claim or "").strip()
        if claim and claim not in linked_claims:
            linked_claims.append(claim)
    candidate_propositions.extend(value for value in linked_claims if value not in candidate_propositions)
    if explicit_selection:
        selected_hypothesis = linked_by_id.get(explicit_selection)
        if selected_hypothesis is None:
            domain_gaps.append(f"unknown_trace_hypothesis_selection:{explicit_selection}")
            proposition = ""
        else:
            proposition = str(selected_hypothesis.claim or "").strip()
    elif not proposition:
        if len(linked_claims) == 1:
            proposition = linked_claims[0]
        elif len(linked_claims) > 1:
            # Never take linked[0] as a hidden winner.
            domain_gaps.append("ambiguous_domain_proposition")
            proposition = ""
    if not proposition:
        domain_gaps.append("missing_domain_proposition")

    mechanism_by_id = {item.mechanism_id: item for item in model.causal_mechanisms}
    declared_mechanisms: list[str] = []
    for item in linked:
        raw_refs = item.mechanism_ids
        if isinstance(raw_refs, str):
            domain_gaps.append("domain_mechanism:metadata_scalar_not_collection")
        elif isinstance(raw_refs, (list, tuple, set)):
            declared_mechanisms.extend(raw_refs)
        elif raw_refs not in (None, ""):
            domain_gaps.append("domain_mechanism:metadata_invalid_collection")
    for item in model.causal_candidates:
        if item.hypothesis_id in hypothesis_ids:
            raw_refs = item.mechanism_ids
            if isinstance(raw_refs, str):
                domain_gaps.append("domain_mechanism:metadata_scalar_not_collection")
            elif isinstance(raw_refs, (list, tuple, set)):
                declared_mechanisms.extend(raw_refs)
            elif raw_refs not in (None, ""):
                domain_gaps.append("domain_mechanism:metadata_invalid_collection")
    mechanism_refs: list[str] = []
    for ref in _stable_strings(declared_mechanisms, gap_prefix="domain_mechanism", gaps=domain_gaps):
        mechanism = mechanism_by_id.get(ref)
        if mechanism is None:
            domain_gaps.append(f"unknown_domain_mechanism:{ref}")
            continue
        if hypothesis_ids and mechanism.hypothesis_id not in hypothesis_ids:
            domain_gaps.append(f"foreign_domain_mechanism:{ref}")
            continue
        if ref not in mechanism_refs:
            mechanism_refs.append(ref)
    if not mechanism_refs:
        domain_gaps.append("missing_domain_mechanism")

    raw_assumptions = model.metadata.get("trace_assumption_refs", {})
    assumptions: tuple[str, ...] = ()
    if raw_assumptions in (None, ""):
        assumptions = ()
    elif not isinstance(raw_assumptions, Mapping):
        domain_gaps.append("invalid_domain_assumption_metadata")
    else:
        assumptions = _stable_strings(
            raw_assumptions.get(trace.trace_id, ()),
            gap_prefix="domain_assumption",
            gaps=domain_gaps,
        )
    declared_assumptions = _metadata_assumption_ids(model.metadata)
    valid_assumptions: list[str] = []
    for ref in assumptions:
        if ref not in declared_assumptions:
            domain_gaps.append(f"unknown_domain_assumption:{ref}")
            continue
        valid_assumptions.append(ref)

    entity_ids = {item.mention_id for item in model.entities}
    location_ids = {item.location_id for item in model.locations}
    scope: list[str] = []
    for ref in _stable_strings(trace.entity_ids, gap_prefix="domain_scope", gaps=domain_gaps):
        if ref not in entity_ids:
            domain_gaps.append(f"unknown_domain_entity:{ref}")
            continue
        if ref not in scope:
            scope.append(ref)
    for ref in _stable_strings(trace.location_ids, gap_prefix="domain_scope", gaps=domain_gaps):
        if ref not in location_ids:
            domain_gaps.append(f"unknown_domain_location:{ref}")
            continue
        if ref not in scope:
            scope.append(ref)

    alternatives_raw: list[str] = []
    for item in linked:
        raw_refs = item.alternative_to
        if isinstance(raw_refs, str):
            domain_gaps.append("domain_alternative:metadata_scalar_not_collection")
        elif isinstance(raw_refs, (list, tuple, set)):
            alternatives_raw.extend(raw_refs)
        elif raw_refs not in (None, ""):
            domain_gaps.append("domain_alternative:metadata_invalid_collection")
    for item in model.causal_candidates:
        if item.hypothesis_id in hypothesis_ids:
            raw_refs = item.alternative_hypothesis_ids
            if isinstance(raw_refs, str):
                domain_gaps.append("domain_alternative:metadata_scalar_not_collection")
            elif isinstance(raw_refs, (list, tuple, set)):
                alternatives_raw.extend(raw_refs)
            elif raw_refs not in (None, ""):
                domain_gaps.append("domain_alternative:metadata_invalid_collection")
    alternatives: list[str] = []
    for ref in _stable_strings(alternatives_raw, gap_prefix="domain_alternative", gaps=domain_gaps):
        if ref not in all_hypotheses:
            domain_gaps.append(f"unknown_domain_alternative:{ref}")
            continue
        if ref not in alternatives:
            alternatives.append(ref)

    boundaries = _metadata_domain_boundaries(model.metadata, trace.trace_id, domain_gaps)
    confounders = {item.confounder_id: item for item in model.confounder_reviews}
    candidate_rows = [item for item in model.causal_candidates if item.hypothesis_id in hypothesis_ids]
    causal_hypothesis = any(item.causal and not item.bounded_non_causal for item in linked)
    licensed_candidate = False
    for candidate in candidate_rows:
        candidate_mechanisms = (
            tuple(candidate.mechanism_ids)
            if isinstance(candidate.mechanism_ids, (list, tuple, set))
            else ()
        )
        candidate_causes = (
            tuple(candidate.cause_event_ids)
            if isinstance(candidate.cause_event_ids, (list, tuple, set))
            else ()
        )
        candidate_effects = (
            tuple(candidate.effect_event_ids)
            if isinstance(candidate.effect_event_ids, (list, tuple, set))
            else ()
        )
        candidate_confounders = (
            tuple(candidate.confounder_ids)
            if isinstance(candidate.confounder_ids, (list, tuple, set))
            else ()
        )
        candidate_refs = [ref for ref in candidate_mechanisms if ref in mechanism_refs]
        if not candidate_refs or not candidate_causes or not candidate_effects:
            continue
        unknown_confounders = [ref for ref in candidate_confounders if ref not in confounders]
        domain_gaps.extend(f"unknown_domain_confounder:{ref}" for ref in unknown_confounders)
        reviews = [confounders.get(ref) for ref in candidate_confounders]
        unresolved_reviews = [
            (ref, getattr(review, "status", "missing"))
            for ref, review in zip(candidate_confounders, reviews)
            if review is None or review.status not in {"addressed", "partially_addressed", "not_applicable"}
        ]
        domain_gaps.extend(
            f"unresolved_domain_confounder:{ref}:{status}"
            for ref, status in unresolved_reviews
        )
        if unresolved_reviews:
            continue
        licensed_candidate = True
        break
    if causal_hypothesis and licensed_candidate and not any(
        gap.startswith(("unknown_domain_mechanism:", "foreign_domain_mechanism:", "unknown_domain_alternative:", "unknown_domain_confounder:", "unresolved_domain_confounder:"))
        for gap in domain_gaps
    ):
        native_causal_license = "causal_assertion_licensed"
    elif causal_hypothesis:
        native_causal_license = "not_licensed"
    else:
        native_causal_license = "bounded_non_causal"

    unique_gaps = tuple(dict.fromkeys(domain_gaps))
    context = {
        "validation_status": "",
        "current_stage": trace.current_stage,
        "safe_wording": "",
        "unsafe_wording_avoided": "",
        "tool_boundary": "TraceGuard solver state and generic audit language do not constitute a domain proposition or warrant.",
        "domain_gaps": list(unique_gaps),
        "domain_boundaries": list(boundaries),
        "native_causal_license": native_causal_license,
        "domain_candidate_propositions": list(dict.fromkeys(candidate_propositions)),
    }
    return _DomainFields(
        proposition,
        tuple(mechanism_refs),
        tuple(valid_assumptions),
        tuple(scope),
        tuple(alternatives),
        tuple(dict.fromkeys(value for value in boundaries if value)),
        native_causal_license,
        unique_gaps,
        tuple(dict.fromkeys(candidate_propositions)),
        context,
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
        "model_fingerprint": str(problem.metadata.get("model_fingerprint", "")),
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
        "model_fingerprint": receipt.model_fingerprint,
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
        model_fingerprint=str(receipt_payload["model_fingerprint"]),
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
    # Domain projection is deliberately computed once per trace.  Reusing the
    # same validated object prevents field-by-field recomputation from
    # selecting different hypotheses or emitting duplicate gaps.
    domain_by_trace = {
        trace_id: _domain_fields(model, trace)
        for trace_id, trace in trace_by_id.items()
    }
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
            domain_proposition=domain_by_trace[projection.trace_id].proposition,
            domain_mechanism_refs=domain_by_trace[projection.trace_id].mechanism_refs,
            domain_assumption_refs=domain_by_trace[projection.trace_id].assumption_refs,
            object_scope=domain_by_trace[projection.trace_id].object_scope,
            material_alternatives=domain_by_trace[projection.trace_id].alternatives,
            domain_boundaries=domain_by_trace[projection.trace_id].boundaries,
            native_causal_license=domain_by_trace[projection.trace_id].native_causal_license,
            domain_gaps=domain_by_trace[projection.trace_id].gaps,
            domain_candidate_propositions=domain_by_trace[projection.trace_id].candidate_propositions,
            audit_context={
                **domain_by_trace[projection.trace_id].context,
                "validation_status": projection.validation_status,
                "safe_wording": projection.safe_wording,
                "unsafe_wording_avoided": projection.unsafe_wording_avoided,
            },
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
