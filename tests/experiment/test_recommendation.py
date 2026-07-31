from researchguard.experiment import (
    ExperimentSpec,
    HypothesisPrediction,
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
