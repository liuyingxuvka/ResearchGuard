"""Exact finite experiment-set recommendation."""

from __future__ import annotations

from itertools import combinations

from .schema import (
    ExperimentIterationReceipt,
    ExperimentObservation,
    ExperimentRecommendation,
    ExperimentSpec,
    HypothesisPrediction,
    HypothesisDisposition,
)


def _pairs(spec: ExperimentSpec) -> tuple[tuple[str, str], ...]:
    hypotheses = sorted(
        item.hypothesis_id for item in spec.hypothesis_predictions
    )
    return tuple(combinations(hypotheses, 2))


def _prediction_map(
    spec: ExperimentSpec,
) -> dict[str, dict[str, str]]:
    return {
        item.hypothesis_id: dict(item.outcomes_by_experiment)
        for item in spec.hypothesis_predictions
    }


def _unresolved(
    selected: tuple[str, ...],
    pairs: tuple[tuple[str, str], ...],
    predictions: dict[str, dict[str, str]],
) -> tuple[tuple[str, str], ...]:
    return tuple(
        pair
        for pair in pairs
        if not any(
            predictions[pair[0]].get(experiment_id)
            != predictions[pair[1]].get(experiment_id)
            and predictions[pair[0]].get(experiment_id) is not None
            and predictions[pair[1]].get(experiment_id) is not None
            for experiment_id in selected
        )
    )


def recommend_experiments(
    spec: ExperimentSpec,
) -> ExperimentRecommendation:
    """Return every minimum-cardinality distinguishing set deterministically."""

    candidates = tuple(sorted(set(spec.candidate_experiment_ids)))
    predictions = _prediction_map(spec)
    if (
        len(predictions) < 2
        or len(predictions) != len(spec.hypothesis_predictions)
        or not candidates
        or (
            spec.maximum_experiment_count is not None
            and spec.maximum_experiment_count < 1
        )
    ):
        return ExperimentRecommendation(
            status="blocked_invalid_input",
            selected_experiment_ids=(),
            alternative_minimal_sets=(),
            unresolved_hypothesis_pairs=(),
            reason_code="invalid_finite_experiment_spec",
        )

    pairs = _pairs(spec)
    limit = min(
        len(candidates),
        spec.maximum_experiment_count or len(candidates),
    )
    for size in range(1, limit + 1):
        solutions = tuple(
            selected
            for selected in combinations(candidates, size)
            if not _unresolved(selected, pairs, predictions)
        )
        if solutions:
            return ExperimentRecommendation(
                status="recommended",
                selected_experiment_ids=solutions[0],
                alternative_minimal_sets=solutions,
                unresolved_hypothesis_pairs=(),
                reason_code="minimum_distinguishing_set_found",
            )

    unresolved = _unresolved(candidates, pairs, predictions)
    return ExperimentRecommendation(
        status="indistinguishable",
        selected_experiment_ids=(),
        alternative_minimal_sets=(),
        unresolved_hypothesis_pairs=unresolved,
        reason_code="declared_candidates_cannot_distinguish_all_hypotheses",
    )


def observe_experiments(
    spec: ExperimentSpec,
    observations: tuple[ExperimentObservation, ...],
) -> ExperimentIterationReceipt:
    """Apply supplied results to the finite prediction matrix, without probabilities."""

    candidates = set(spec.candidate_experiment_ids)
    valid = [item for item in observations if item.experiment_id in candidates and item.status == "valid"]
    observed_ids = {item.experiment_id for item in valid}
    dispositions: list[HypothesisDisposition] = []
    prediction_map = _prediction_map(spec)
    for hypothesis_id in sorted(prediction_map):
        matched = tuple(
            item.experiment_id
            for item in valid
            if prediction_map[hypothesis_id].get(item.experiment_id) == item.observed_outcome
        )
        contradicted = tuple(
            item.experiment_id
            for item in valid
            if prediction_map[hypothesis_id].get(item.experiment_id) is not None
            and prediction_map[hypothesis_id].get(item.experiment_id) != item.observed_outcome
        )
        status = "weakened" if contradicted else ("supported" if matched and len(matched) == len(valid) else "undetermined")
        dispositions.append(
            HypothesisDisposition(
                hypothesis_id=hypothesis_id,
                status=status,
                matched_experiment_ids=matched,
                contradicted_experiment_ids=contradicted,
            )
        )
    active = tuple(
        HypothesisPrediction(item.hypothesis_id, dict(item.outcomes_by_experiment))
        for item in spec.hypothesis_predictions
        if next(row for row in dispositions if row.hypothesis_id == item.hypothesis_id).status != "weakened"
    )
    if len(active) <= 1:
        recommendation = ExperimentRecommendation(
            status="recommended",
            selected_experiment_ids=(),
            alternative_minimal_sets=((),),
            unresolved_hypothesis_pairs=(),
            reason_code="one_hypothesis_remains",
        )
    else:
        remaining_spec = ExperimentSpec(
            hypothesis_predictions=active,
            candidate_experiment_ids=tuple(sorted(candidates - observed_ids)),
            maximum_experiment_count=spec.maximum_experiment_count,
        )
        recommendation = recommend_experiments(remaining_spec)
    pairs = recommendation.unresolved_hypothesis_pairs
    if len(active) <= 1:
        terminal_reason = "model_closed_for_task"
    elif recommendation.status == "recommended":
        terminal_reason = "continue_iteration"
    elif recommendation.status == "indistinguishable":
        terminal_reason = "continue_iteration" if recommendation.unresolved_hypothesis_pairs else "model_closed_for_task"
    else:
        terminal_reason = "external_input_required"
    return ExperimentIterationReceipt(
        recommendation=recommendation,
        observations=tuple(valid),
        hypothesis_dispositions=tuple(dispositions),
        open_hypothesis_pairs=pairs,
        next_experiment_ids=recommendation.selected_experiment_ids,
        terminal_reason=terminal_reason,
        progressed=bool(valid),
    )


__all__ = ["observe_experiments", "recommend_experiments"]
