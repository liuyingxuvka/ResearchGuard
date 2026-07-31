"""Exact finite experiment-set recommendation."""

from __future__ import annotations

from itertools import combinations

from .schema import ExperimentRecommendation, ExperimentSpec


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


__all__ = ["recommend_experiments"]
