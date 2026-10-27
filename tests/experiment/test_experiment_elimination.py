from __future__ import annotations
import json
import pytest
from researchguard.experiment import (
    ExperimentObservation,
    ExperimentSpec,
    HypothesisPrediction,
    observe_experiments,
    recommend_experiments,
)


from experiment_specs import _evergiven_spec, _observation, _spec

@pytest.mark.parametrize("iteration", [0, 1])
def test_real_observation_closes_only_with_independent_holdout(iteration: int) -> None:
    prior = observe_experiments(_spec(), ()) if iteration else None
    spec = _spec(
        iteration=iteration,
        prior_open_gap_ids=() if prior is None else prior.introduced_gap_ids,
    )
    result = observe_experiments(
        spec,
        (
            _observation("e1", "up", role="construction", suffix="a"),
            _observation("e2", "hot", role="holdout", suffix="b"),
        ),
    )
    assert result.terminal_reason == "model_closed_for_task"
    assert result.progressed is True
    assert result.resolved_gap_ids == result.persisted_gap_ids == result.introduced_gap_ids == ()
    assert result.holdout_evidence_ids == ("evidence:b",)
    assert [item.hypothesis_id for item in result.hypothesis_dispositions if item.status == "consistent"] == ["h1"]
    assert any(
        item.hypothesis_id == "h2" and item.status == "eliminated"
        for item in result.hypothesis_dispositions
    )


def test_eliminated_hypothesis_stays_eliminated_on_a_matrix_miss() -> None:
    # Packet exp-obs2 construction: two valid counterexamples followed by a miss.
    result = observe_experiments(_evergiven_spec(), (
        _observation("e_transpacific", "similar_rise", role="construction", suffix="transpacific"),
        _observation("e_reversion", "keeps_rising", role="construction", suffix="reversion"),
        _observation("e_yantian_timing", "gradual_rise_no_jump_change", role="construction", suffix="yantian")))
    dispositions = {row.hypothesis_id: row for row in result.hypothesis_dispositions}
    assert dispositions["h_suez"].status == "eliminated"
    assert dispositions["h_suez"].contradicted_experiment_ids == ("e_transpacific", "e_reversion")
    assert dispositions["h_demand"].status == dispositions["h_yantian"].status == "model_miss"
    assert result.terminal_reason == "external_input_required"
    assert result.revision_candidate is not None
    assert result.revision_candidate.disposition == "not_applied"
    assert "prediction-matrix-revision-required" in result.introduced_gap_ids
    assert result.next_experiment_ids == ()


def test_zero_survivors_is_model_miss_and_never_closes() -> None:
    result = observe_experiments(
        _spec(),
        (_observation("e1", "unknown", role="construction", suffix="a"),),
    )
    assert result.terminal_reason == "external_input_required"
    assert result.revision_candidate is not None
    assert result.revision_candidate.disposition == "not_applied"
    assert "prediction-matrix-revision-required" in result.introduced_gap_ids
    assert all(item.status == "model_miss" for item in result.hypothesis_dispositions)


@pytest.mark.parametrize("outcomes", [("cold",), ("hot", "cold"), ("cold", "hot")])
def test_every_valid_holdout_counterexample_blocks_closure(outcomes, tmp_path, capsys) -> None:
    from researchguard.experiment.cli import main

    observations = (_observation("e1", "up", role="construction", suffix="a"),) + tuple(
        _observation("e2", outcome, role="holdout", suffix=suffix)
        for outcome, suffix in zip(outcomes, ("b", "c"))
    )
    spec_path = tmp_path / "spec.json"
    observations_path = tmp_path / "observations.json"
    spec_path.write_text(json.dumps(_spec().to_dict()), encoding="utf-8")
    observations_path.write_text(json.dumps([row.to_dict() for row in observations]), encoding="utf-8")
    assert main(["observe", str(spec_path), str(observations_path)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["terminal_reason"] == "external_input_required"
    assert any(gap.startswith("holdout-conflict:") for gap in result["introduced_gap_ids"])
    assert result["holdout_evidence_ids"] == [row.evidence_id for row in observations[1:]]
    assert [row["hypothesis_id"] for row in result["hypothesis_dispositions"] if row["status"] == "consistent"] == ["h1"]


def test_recommends_all_tied_minimum_sets_deterministically() -> None:
    result = recommend_experiments(_spec())
    assert result.status == "recommended"
    assert result.selected_experiment_ids == ("e1",)
    assert result.alternative_minimal_sets == (("e2",),)


def test_reports_indistinguishable_hypothesis_pairs() -> None:
    result = recommend_experiments(
        _spec(
            hypothesis_predictions=(
                HypothesisPrediction("h1", {"e1": "same"}),
                HypothesisPrediction("h2", {"e1": "same"}),
            ),
            candidate_experiment_ids=("e1",),
            coverage_ids=("h1", "h2", "e1"),
        )
    )
    assert result.status == "indistinguishable"
    assert result.unresolved_hypothesis_pairs == (("h1", "h2"),)


