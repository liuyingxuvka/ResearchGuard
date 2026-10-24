"""Exact finite experiment recommendation and evidence-bound iteration."""

from __future__ import annotations

from ..iteration import baseline_identity, gap_lineage, select_terminal

from fractions import Fraction
from itertools import combinations

from .schema import (
    ExperimentIterationResult,
    ExperimentObservation,
    ExperimentRecommendation,
    ExperimentSpec,
    HypothesisDisposition,
    HypothesisPrediction,
    PredictionMatrixRevisionCandidate,
)




def _pairs(spec: ExperimentSpec) -> tuple[tuple[str, str], ...]:
    return tuple(combinations(sorted(item.hypothesis_id for item in spec.hypothesis_predictions), 2))


def _prediction_map(spec: ExperimentSpec) -> dict[str, dict[str, str]]:
    return {item.hypothesis_id: dict(item.outcomes_by_experiment) for item in spec.hypothesis_predictions}


def _unresolved(selected, pairs, predictions):
    return tuple(
        pair
        for pair in pairs
        if not any(
            predictions[pair[0]].get(experiment_id) is not None
            and predictions[pair[1]].get(experiment_id) is not None
            and predictions[pair[0]][experiment_id] != predictions[pair[1]][experiment_id]
            for experiment_id in selected
        )
    )


def recommend_experiments(spec: ExperimentSpec) -> ExperimentRecommendation:
    candidates = tuple(sorted(spec.candidate_experiment_ids))
    predictions = _prediction_map(spec)
    if spec.maximum_experiment_count is not None and spec.maximum_experiment_count < 1:
        return ExperimentRecommendation("blocked_invalid_input", (), (), (), "invalid_finite_experiment_spec")
    pairs = _pairs(spec)
    limit = min(len(candidates), spec.maximum_experiment_count or len(candidates))
    costs = (None if spec.cost_by_experiment is None else
             {item: Fraction(spec.cost_by_experiment.get(item, 1)) for item in candidates})
    cost_solutions = []
    for size in range(1, limit + 1):
        solutions = tuple(selected for selected in combinations(candidates, size) if not _unresolved(selected, pairs, predictions))
        if solutions:
            if spec.cost_by_experiment is None:
                return ExperimentRecommendation("recommended", solutions[0], solutions[1:], (), "minimum_distinguishing_set_found")
            cost_solutions.extend(
                (sum(costs[item] for item in selected), size, selected)
                for selected in solutions
            )
    if cost_solutions:
        cost_solutions.sort()
        cost, count, selected = cost_solutions[0]
        alternatives = tuple(row[2] for row in cost_solutions[1:] if row[:2] == (cost, count))
        return ExperimentRecommendation("recommended", selected, alternatives, (), "minimum_cost_distinguishing_set_found")
    unresolved = _unresolved(candidates, pairs, predictions)
    return ExperimentRecommendation(
        "indistinguishable",
        (),
        (),
        unresolved,
        "declared_candidates_cannot_distinguish_all_hypotheses"
        if unresolved else "no_distinguishing_set_within_declared_limit",
    )


def observe_experiments(spec: ExperimentSpec, observations: tuple[ExperimentObservation, ...]) -> ExperimentIterationResult:
    """Consume external evidence; zero survivors is a model miss, never closure."""

    if len({row.evidence_id for row in observations}) != len(observations):
        raise ValueError("observation evidence_id values must be unique")
    predictions = _prediction_map(spec)
    candidates = set(spec.candidate_experiment_ids)
    gaps: set[str] = set()
    valid_construction: list[ExperimentObservation] = []
    valid_holdouts: list[ExperimentObservation] = []
    unexpected: list[ExperimentObservation] = []
    for row in observations:
        if row.experiment_id not in candidates:
            gaps.add(f"observation-outside-candidate-universe:{row.experiment_id}")
            continue
        if row.status != "valid":
            gaps.add(f"observation-{row.status}:{row.experiment_id}")
            continue
        if not any(mapping.get(row.experiment_id) == row.observed_outcome for mapping in predictions.values()):
            gaps.add(f"prediction-matrix-miss:{row.experiment_id}")
            unexpected.append(row)
            continue
        if row.role == "construction":
            valid_construction.append(row)
        else:
            valid_holdouts.append(row)

    dispositions: list[HypothesisDisposition] = []
    active_ids: list[str] = []
    for hypothesis_id in sorted(predictions):
        matched = tuple(row.experiment_id for row in valid_construction if predictions[hypothesis_id].get(row.experiment_id) == row.observed_outcome)
        contradicted = tuple(row.experiment_id for row in valid_construction if predictions[hypothesis_id].get(row.experiment_id) is not None and predictions[hypothesis_id].get(row.experiment_id) != row.observed_outcome)
        if contradicted:
            status = "eliminated"
        elif unexpected:
            status = "model_miss"
        elif valid_construction and len(matched) == len(valid_construction):
            status = "consistent"
            active_ids.append(hypothesis_id)
        else:
            status = "underdetermined"
            active_ids.append(hypothesis_id)
        dispositions.append(HypothesisDisposition(hypothesis_id, status, matched, contradicted))

    revision_candidate = None
    if unexpected or not active_ids:
        ids = tuple(row.evidence_id for row in unexpected) or tuple(row.evidence_id for row in valid_construction)
        gaps.add("prediction-matrix-revision-required")
        revision_candidate = PredictionMatrixRevisionCandidate(
            candidate_id=f"matrix-revision:{baseline_identity(ids)[7:27]}",
            unexpected_observation_ids=ids,
            required_actions=("revise_hypothesis_or_prediction_matrix", "freeze_new_matrix_before_replay"),
        )
        active_ids = []

    observed_ids = {row.experiment_id for row in valid_construction}
    if len(active_ids) > 1:
        remaining_candidates = tuple(sorted(candidates - observed_ids))
        if remaining_candidates:
            remaining = ExperimentSpec(
                task_id=spec.task_id,
                purpose=spec.purpose,
                coverage_ids=spec.coverage_ids,
                assumptions=spec.assumptions,
                unknowns=spec.unknowns,
                iteration=spec.iteration,
                max_iterations=spec.max_iterations,
                prior_open_gap_ids=spec.prior_open_gap_ids,
                hypothesis_predictions=tuple(row for row in spec.hypothesis_predictions if row.hypothesis_id in active_ids),
                candidate_experiment_ids=remaining_candidates,
                maximum_experiment_count=spec.maximum_experiment_count,
                cost_by_experiment=(
                    None if spec.cost_by_experiment is None else
                    {key: value for key, value in spec.cost_by_experiment.items() if key in remaining_candidates}
                ),
            )
            recommendation = recommend_experiments(remaining)
        else:
            recommendation = ExperimentRecommendation(
                "indistinguishable",
                (),
                (),
                tuple(combinations(sorted(active_ids), 2)),
                "declared_candidates_exhausted",
            )
        if recommendation.status == "indistinguishable":
            gaps.add(
                "experiment-count-limit-prevents-distinguishing-set"
                if recommendation.reason_code == "no_distinguishing_set_within_declared_limit"
                else "declared-candidates-indistinguishable"
            )
    elif len(active_ids) == 1:
        recommendation = ExperimentRecommendation("recommended", (), (), (), "one_hypothesis_consistent")
        for row in valid_holdouts:
            if predictions[active_ids[0]][row.experiment_id] != row.observed_outcome:
                gaps.add(f"holdout-conflict:{row.evidence_id}")
    else:
        recommendation = ExperimentRecommendation("blocked_invalid_input", (), (), (), "prediction_matrix_revision_required")

    prior = set(spec.prior_open_gap_ids)
    current = set(gaps)
    resolved, persisted, introduced, _ = gap_lineage(prior, current)
    progressed = bool(resolved or introduced or (spec.iteration == 0 and observations))
    closed = not current and len(active_ids) == 1
    if closed:
        progressed = True
    continuation = not current and len(active_ids) > 1 and valid_construction and recommendation.selected_experiment_ids
    terminal = select_terminal(closed=closed, iteration=spec.iteration, max_iterations=spec.max_iterations,
        stalled=not continuation and current == prior and spec.iteration > 0,
        external=bool(revision_candidate or any(gap.startswith(("observation-", "holdout-conflict:")) for gap in current) or "declared-candidates-indistinguishable" in current or "experiment-count-limit-prevents-distinguishing-set" in current))

    holdout_ids = tuple(row.evidence_id for row in valid_holdouts)
    first_unresolved_gap = sorted(current)[0] if current else ""
    return ExperimentIterationResult(
        baseline_identity=baseline_identity(spec.to_dict()),
        task_id=spec.task_id,
        iteration=spec.iteration,
        recommendation=recommendation,
        observations=observations,
        hypothesis_dispositions=tuple(dispositions),
        input_gap_ids=spec.prior_open_gap_ids,
        resolved_gap_ids=resolved,
        persisted_gap_ids=persisted,
        introduced_gap_ids=introduced,
        open_hypothesis_pairs=recommendation.unresolved_hypothesis_pairs,
        next_experiment_ids=recommendation.selected_experiment_ids,
        revision_candidate=revision_candidate,
        holdout_evidence_ids=holdout_ids,
        terminal_reason=terminal,  # type: ignore[arg-type]
        progressed=progressed,
        affected_obligation_ids=tuple(sorted(spec.coverage_ids)),
        first_unresolved_gap=first_unresolved_gap,
    )


__all__ = ["observe_experiments", "recommend_experiments"]
