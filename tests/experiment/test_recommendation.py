from researchguard.experiment import (
    ExperimentObservation,
    ExperimentSpec,
    HypothesisPrediction,
    observe_experiments,
    recommend_experiments,
)


def test_recommends_all_tied_minimum_sets_deterministically() -> None:
    result = recommend_experiments(
        ExperimentSpec(
            hypothesis_predictions=(
                HypothesisPrediction("h1", {"e1": "up", "e2": "hot"}),
                HypothesisPrediction("h2", {"e1": "down", "e2": "cold"}),
            ),
            candidate_experiment_ids=("e2", "e1"),
        )
    )
    assert result.status == "recommended"
    assert result.selected_experiment_ids == ("e1",)
    assert result.alternative_minimal_sets == (("e1",), ("e2",))


def test_reports_indistinguishable_hypothesis_pairs() -> None:
    result = recommend_experiments(
        ExperimentSpec(
            hypothesis_predictions=(
                HypothesisPrediction("h1", {"e1": "same"}),
                HypothesisPrediction("h2", {"e1": "same"}),
            ),
            candidate_experiment_ids=("e1",),
        )
    )
    assert result.status == "indistinguishable"
    assert result.unresolved_hypothesis_pairs == (("h1", "h2"),)


def test_real_observation_recomputes_next_experiment_without_probabilities() -> None:
    receipt = observe_experiments(
        ExperimentSpec(
            hypothesis_predictions=(
                HypothesisPrediction("h1", {"e1": "up", "e2": "hot"}),
                HypothesisPrediction("h2", {"e1": "down", "e2": "cold"}),
            ),
            candidate_experiment_ids=("e1", "e2"),
        ),
        (ExperimentObservation("e1", "up", "evidence:e1"),),
    )
    assert receipt.terminal_reason == "model_closed_for_task"
    assert any(
        item.hypothesis_id == "h2" and item.status == "weakened"
        for item in receipt.hypothesis_dispositions
    )


def test_unexpected_observation_does_not_invent_probability() -> None:
    receipt = observe_experiments(
        ExperimentSpec(
            hypothesis_predictions=(
                HypothesisPrediction("h1", {"e1": "up"}),
                HypothesisPrediction("h2", {"e1": "down"}),
            ),
            candidate_experiment_ids=("e1",),
        ),
        (ExperimentObservation("e1", "unknown", "evidence:e1"),),
    )
    assert all(item.status == "weakened" for item in receipt.hypothesis_dispositions)
    assert receipt.terminal_reason in {
        "model_closed_for_task",
        "external_input_required",
        "continue_iteration",
    }
