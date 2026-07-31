"""Exact finite experiment recommendation and evidence-bound iteration."""

from __future__ import annotations

import hashlib
import json
from itertools import combinations

from .schema import (
    ExperimentIterationReceipt,
    ExperimentObservation,
    ExperimentRecommendation,
    ExperimentSpec,
    HypothesisDisposition,
    HypothesisPrediction,
    PredictionMatrixRevisionCandidate,
)


def _digest(value: object) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(body.encode('utf-8')).hexdigest()}"


def matrix_fingerprint(spec: ExperimentSpec, *, hypothesis_ids: tuple[str, ...] | None = None) -> str:
    selected = set(hypothesis_ids) if hypothesis_ids is not None else None
    return _digest(
        {
            "hypotheses": [
                {
                    "hypothesis_id": item.hypothesis_id,
                    "outcomes_by_experiment": dict(sorted(item.outcomes_by_experiment.items())),
                }
                for item in sorted(spec.hypothesis_predictions, key=lambda row: row.hypothesis_id)
                if selected is None or item.hypothesis_id in selected
            ],
            "candidate_experiment_ids": sorted(spec.candidate_experiment_ids),
            "coverage_ids": sorted(spec.coverage_ids),
        }
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
    for size in range(1, limit + 1):
        solutions = tuple(selected for selected in combinations(candidates, size) if not _unresolved(selected, pairs, predictions))
        if solutions:
            return ExperimentRecommendation("recommended", solutions[0], solutions, (), "minimum_distinguishing_set_found")
    return ExperimentRecommendation(
        "indistinguishable",
        (),
        (),
        _unresolved(candidates, pairs, predictions),
        "declared_candidates_cannot_distinguish_all_hypotheses",
    )


def observe_experiments(spec: ExperimentSpec, observations: tuple[ExperimentObservation, ...]) -> ExperimentIterationReceipt:
    """Consume external evidence; zero survivors is a model miss, never closure."""

    if len({row.evidence_id for row in observations}) != len(observations):
        raise ValueError("observation evidence_id values must be unique")
    if len({row.evidence_fingerprint for row in observations}) != len(observations):
        raise ValueError("observation evidence fingerprints must be independent")
    predictions = _prediction_map(spec)
    candidates = set(spec.candidate_experiment_ids)
    construction = tuple(row for row in observations if row.role == "construction")
    holdouts = tuple(row for row in observations if row.role == "holdout")
    gaps: set[str] = set()
    valid_construction: list[ExperimentObservation] = []
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

    dispositions: list[HypothesisDisposition] = []
    active_ids: list[str] = []
    for hypothesis_id in sorted(predictions):
        matched = tuple(row.experiment_id for row in valid_construction if predictions[hypothesis_id].get(row.experiment_id) == row.observed_outcome)
        contradicted = tuple(row.experiment_id for row in valid_construction if predictions[hypothesis_id].get(row.experiment_id) is not None and predictions[hypothesis_id].get(row.experiment_id) != row.observed_outcome)
        if unexpected:
            status = "model_miss"
        elif contradicted:
            status = "eliminated"
        elif valid_construction and len(matched) == len(valid_construction):
            status = "consistent"
            active_ids.append(hypothesis_id)
        else:
            status = "underdetermined"
            active_ids.append(hypothesis_id)
        dispositions.append(HypothesisDisposition(hypothesis_id, status, matched, contradicted))

    base_fingerprint = matrix_fingerprint(spec)
    revision_candidate = None
    if unexpected or not active_ids:
        ids = tuple(row.evidence_id for row in unexpected) or tuple(row.evidence_id for row in valid_construction)
        gaps.add("prediction-matrix-revision-required")
        revision_candidate = PredictionMatrixRevisionCandidate(
            candidate_id=f"matrix-revision:{_digest(ids)[7:27]}",
            base_matrix_fingerprint=base_fingerprint,
            unexpected_observation_ids=ids,
            required_actions=("revise_hypothesis_or_prediction_matrix", "freeze_new_matrix_before_replay"),
        )
        active_ids = []

    candidate_fingerprint = matrix_fingerprint(spec, hypothesis_ids=tuple(active_ids))
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
                prior_receipt_fingerprint=spec.prior_receipt_fingerprint,
                prior_open_gap_ids=spec.prior_open_gap_ids,
                hypothesis_predictions=tuple(row for row in spec.hypothesis_predictions if row.hypothesis_id in active_ids),
                candidate_experiment_ids=remaining_candidates,
                maximum_experiment_count=spec.maximum_experiment_count,
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
            gaps.add("declared-candidates-indistinguishable")
    elif len(active_ids) == 1:
        recommendation = ExperimentRecommendation("recommended", (), ((),), (), "one_hypothesis_consistent")
        valid_holdout = tuple(
            row
            for row in holdouts
            if row.status == "valid"
            and predictions[active_ids[0]].get(row.experiment_id) == row.observed_outcome
            and row.evidence_fingerprint not in {item.evidence_fingerprint for item in construction}
        )
        if not valid_holdout:
            gaps.add("independent-holdout-required")
    else:
        recommendation = ExperimentRecommendation("blocked_invalid_input", (), (), (), "prediction_matrix_revision_required")

    prior = set(spec.prior_open_gap_ids)
    current = set(gaps)
    resolved = tuple(sorted(prior - current))
    persisted = tuple(sorted(prior & current))
    introduced = tuple(sorted(current - prior))
    progressed = bool(resolved or introduced or (spec.iteration == 0 and observations))
    if spec.iteration >= spec.max_iterations:
        terminal = "iteration_limit"
    elif current == prior and spec.iteration > 0:
        terminal = "progress_stalled"
    elif revision_candidate or any(gap.startswith("observation-") for gap in current) or "independent-holdout-required" in current or "declared-candidates-indistinguishable" in current:
        terminal = "external_input_required"
    elif current:
        terminal = "continue_iteration"
    elif len(active_ids) == 1:
        terminal = "model_closed_for_task"
    else:
        terminal = "continue_iteration"

    holdout_ids = tuple(row.evidence_id for row in holdouts if row.status == "valid")
    receipt_material = {
        "task_id": spec.task_id,
        "iteration": spec.iteration,
        "base": base_fingerprint,
        "candidate": candidate_fingerprint,
        "observation_fingerprints": [row.evidence_fingerprint for row in observations],
        "open_gaps": sorted(current),
        "terminal": terminal,
    }
    receipt_fingerprint = _digest(receipt_material)
    return ExperimentIterationReceipt(
        task_id=spec.task_id,
        iteration=spec.iteration,
        base_matrix_fingerprint=base_fingerprint,
        candidate_matrix_fingerprint=candidate_fingerprint,
        recommendation=recommendation,
        observations=observations,
        hypothesis_dispositions=tuple(dispositions),
        input_gap_ids=spec.prior_open_gap_ids,
        resolved_gap_ids=resolved,
        persisted_gap_ids=persisted,
        introduced_gap_ids=introduced,
        open_hypothesis_pairs=recommendation.unresolved_hypothesis_pairs,
        next_experiment_ids=recommendation.selected_experiment_ids,
        native_receipt_id=f"experimentguard-iteration:{receipt_fingerprint[7:27]}",
        revision_candidate=revision_candidate,
        holdout_evidence_ids=holdout_ids,
        rollback_matrix_fingerprint=base_fingerprint,
        terminal_reason=terminal,  # type: ignore[arg-type]
        progressed=progressed,
        receipt_fingerprint=receipt_fingerprint,
    )


__all__ = ["matrix_fingerprint", "observe_experiments", "recommend_experiments"]
