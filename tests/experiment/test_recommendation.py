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


def _spec(**overrides) -> ExperimentSpec:
    values = {
        "task_id": "experiment-task-1",
        "purpose": "distinguish the two declared mechanisms",
        "coverage_ids": ("h1", "h2", "e1", "e2"),
        "assumptions": (),
        "unknowns": (),
        "iteration": 0,
        "max_iterations": 4,
        "hypothesis_predictions": (
            HypothesisPrediction("h1", {"e1": "up", "e2": "hot"}),
            HypothesisPrediction("h2", {"e1": "down", "e2": "cold"}),
        ),
        "candidate_experiment_ids": ("e2", "e1"),
    }
    values.update(overrides)
    return ExperimentSpec(**values)


def _observation(
    experiment_id: str,
    outcome: str,
    *,
    role: str,
    suffix: str,
    status: str = "valid",
) -> ExperimentObservation:
    return ExperimentObservation(
        experiment_id=experiment_id,
        observed_outcome=outcome,
        evidence_id=f"evidence:{suffix}",
        evidence_fingerprint=f"sha256:{suffix * 64}"[:71],
        source_ref=f"source:{suffix}",
        observed_at="2026-07-31T12:00:00+00:00",
        role=role,
        status=status,
    )


def test_recommends_all_tied_minimum_sets_deterministically() -> None:
    result = recommend_experiments(_spec())
    assert result.status == "recommended"
    assert result.selected_experiment_ids == ("e1",)
    assert result.alternative_minimal_sets == (("e1",), ("e2",))


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


@pytest.mark.parametrize("iteration", [0, 1])
def test_real_observation_closes_only_with_independent_holdout(iteration: int) -> None:
    prior = observe_experiments(_spec(), ()) if iteration else None
    spec = _spec(
        iteration=iteration,
        prior_receipt_fingerprint=prior.receipt_fingerprint if prior else "",
        prior_open_gap_ids=() if prior is None else prior.introduced_gap_ids,
    )
    receipt = observe_experiments(
        spec,
        (
            _observation("e1", "up", role="construction", suffix="a"),
            _observation("e2", "hot", role="holdout", suffix="b"),
        ),
    )
    assert receipt.terminal_reason == "model_closed_for_task"
    assert receipt.progressed is True
    assert receipt.resolved_gap_ids == receipt.persisted_gap_ids == receipt.introduced_gap_ids == ()
    assert receipt.holdout_evidence_ids == ("evidence:b",)
    assert [item.hypothesis_id for item in receipt.hypothesis_dispositions if item.status == "consistent"] == ["h1"]
    assert any(
        item.hypothesis_id == "h2" and item.status == "eliminated"
        for item in receipt.hypothesis_dispositions
    )


@pytest.mark.parametrize("iteration, observed, terminal", [(1, False, "progress_stalled"), (4, True, "iteration_limit")])
def test_iteration_terminal_boundaries(iteration: int, observed: bool, terminal: str) -> None:
    prior = observe_experiments(_spec(), ())
    observations = (
        _observation("e1", "up", role="construction", suffix="a"),
        _observation("e2", "hot", role="holdout", suffix="b"),
    ) if observed else ()
    receipt = observe_experiments(
        _spec(iteration=iteration, prior_receipt_fingerprint=prior.receipt_fingerprint, prior_open_gap_ids=()),
        observations,
    )
    assert receipt.terminal_reason == terminal
    if not observed:
        assert receipt.progressed is False


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
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["terminal_reason"] == "external_input_required"
    assert any(gap.startswith("holdout-conflict:") for gap in receipt["introduced_gap_ids"])
    assert receipt["holdout_evidence_ids"] == [row.evidence_id for row in observations[1:]]
    assert [row["hypothesis_id"] for row in receipt["hypothesis_dispositions"] if row["status"] == "consistent"] == ["h1"]


def test_same_gap_partial_evidence_can_continue_without_claiming_historical_progress() -> None:
    values = dict(
        hypothesis_predictions=(
            HypothesisPrediction("h1", {"e1": "up", "e2": "hot"}),
            HypothesisPrediction("h2", {"e1": "up", "e2": "cold"}),
            HypothesisPrediction("h3", {"e1": "down", "e2": "cold"}),
        ),
        coverage_ids=("h1", "h2", "h3", "e1", "e2"),
    )
    prior = observe_experiments(_spec(**values), ())
    observations = (_observation("e1", "up", role="construction", suffix="a"),)
    # Replaying the same declared evidence has no provable historical newness.
    for iteration in range(1, 5):
        receipt = observe_experiments(_spec(
            **values, iteration=iteration,
            prior_receipt_fingerprint=prior.receipt_fingerprint, prior_open_gap_ids=(),
        ), observations)
        assert receipt.terminal_reason == ("iteration_limit" if iteration == 4 else "continue_iteration")
        assert receipt.progressed is False
        assert receipt.introduced_gap_ids == receipt.persisted_gap_ids == receipt.resolved_gap_ids == ()
        assert receipt.recommendation.selected_experiment_ids == ("e2",)
        assert [(row.hypothesis_id, row.status) for row in receipt.hypothesis_dispositions] == [
            ("h1", "consistent"), ("h2", "consistent"), ("h3", "eliminated")]
        prior = receipt


def test_ordinary_spec_roundtrips_through_native_cli(tmp_path, capsys) -> None:
    from researchguard.experiment.cli import _load_spec, main

    path = tmp_path / "spec.json"
    payload = _spec().to_dict()
    assert not {"design_root_id", "design_blocks", "target_universe"} & payload.keys()
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = _load_spec(path)
    assert (loaded.task_id, loaded.purpose, loaded.coverage_ids) == (
        _spec().task_id, _spec().purpose, _spec().coverage_ids)
    assert recommend_experiments(loaded) == recommend_experiments(_spec())
    assert main(["recommend", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["selected_experiment_ids"] == ["e1"]
    observations = tmp_path / "observations.json"
    observations.write_text(json.dumps([row.to_dict() for row in (
        _observation("e1", "up", role="construction", suffix="a"),
        _observation("e2", "hot", role="holdout", suffix="b"),
    )]), encoding="utf-8")
    assert main(["observe", str(path), str(observations)]) == 0
    assert json.loads(capsys.readouterr().out)["terminal_reason"] == "model_closed_for_task"
    for partial in ({"design_root_id": "root"}, {"design_blocks": []}, {"target_universe": None}):
        path.write_text(json.dumps(payload | partial), encoding="utf-8")
        with pytest.raises(ValueError):
            _load_spec(path)


def test_finite_experiment_count_limit_is_not_all_candidates_indistinguishable() -> None:
    values = {
        "hypothesis_predictions": (
            HypothesisPrediction("h1", {"e1": "0", "e2": "0"}),
            HypothesisPrediction("h2", {"e1": "1", "e2": "0"}),
            HypothesisPrediction("h3", {"e1": "0", "e2": "1"}),
        ),
        "coverage_ids": ("h1", "h2", "h3", "e1", "e2"),
    }
    limited = _spec(**values, maximum_experiment_count=1)
    recommendation = recommend_experiments(limited)
    assert recommendation.status == "indistinguishable"
    assert recommendation.reason_code == "no_distinguishing_set_within_declared_limit"
    assert recommendation.selected_experiment_ids == recommendation.alternative_minimal_sets == ()
    assert recommendation.unresolved_hypothesis_pairs == ()
    receipt = observe_experiments(limited, ())
    assert receipt.recommendation.reason_code == recommendation.reason_code
    assert receipt.introduced_gap_ids == ("experiment-count-limit-prevents-distinguishing-set",)
    assert receipt.terminal_reason == "external_input_required"
    sufficient = recommend_experiments(_spec(**values, maximum_experiment_count=2))
    assert sufficient.status == "recommended"
    assert sufficient.alternative_minimal_sets == (("e1", "e2"),)


def test_one_survivor_without_holdout_requires_external_input() -> None:
    receipt = observe_experiments(
        _spec(),
        (_observation("e1", "up", role="construction", suffix="a"),),
    )
    assert receipt.terminal_reason == "external_input_required"
    assert "independent-holdout-required" in receipt.introduced_gap_ids


def test_zero_survivors_is_model_miss_and_never_closes() -> None:
    receipt = observe_experiments(
        _spec(),
        (_observation("e1", "unknown", role="construction", suffix="a"),),
    )
    assert receipt.terminal_reason == "external_input_required"
    assert receipt.revision_candidate is not None
    assert receipt.revision_candidate.disposition == "not_applied"
    assert "prediction-matrix-revision-required" in receipt.introduced_gap_ids
    assert all(item.status == "model_miss" for item in receipt.hypothesis_dispositions)


@pytest.mark.parametrize("status", ["invalid", "not_run"])
def test_nonvalid_observation_is_explicit_gap(status: str) -> None:
    receipt = observe_experiments(
        _spec(),
        (_observation("e1", "", role="construction", suffix="a", status=status),),
    )
    assert receipt.terminal_reason == "external_input_required"
    assert f"observation-{status}:e1" in receipt.introduced_gap_ids


def test_reused_evidence_fingerprint_is_rejected() -> None:
    first = _observation("e1", "up", role="construction", suffix="a")
    second = ExperimentObservation(
        experiment_id="e2",
        observed_outcome="hot",
        evidence_id="evidence:b",
        evidence_fingerprint=first.evidence_fingerprint,
        source_ref="source:b",
        observed_at="2026-07-31T12:01:00+00:00",
        role="holdout",
    )
    with pytest.raises(ValueError, match="fingerprints must be independent"):
        observe_experiments(_spec(), (first, second))


def test_task_scope_is_mandatory() -> None:
    with pytest.raises(ValueError, match="task_id and purpose"):
        _spec(task_id="")


def test_prediction_rows_must_cover_each_candidate_identity() -> None:
    with pytest.raises(ValueError, match="candidate universe"):
        _spec(
            hypothesis_predictions=(
                HypothesisPrediction("h1", {"e1": "up"}),
                HypothesisPrediction("h2", {"e1": "down"}),
            )
        )


def test_minimal_spec_recommends_without_loop_fields(tmp_path, capsys):
    from researchguard.experiment.cli import main
    payload = {"hypothesis_predictions": [
        {"hypothesis_id": "h1", "outcomes_by_experiment": {"e1": "up", "e2": "up", "e3": "up"}},
        {"hypothesis_id": "h2", "outcomes_by_experiment": {"e1": "down", "e2": "up", "e3": "up"}},
        {"hypothesis_id": "h3", "outcomes_by_experiment": {"e1": "up", "e2": "down", "e3": "up"}}],
        "candidate_experiment_ids": ["e1", "e2", "e3"]}
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(payload))
    assert main(["recommend", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "recommended"


def test_malformed_spec_returns_a_json_error(tmp_path, capsys):
    from researchguard.experiment.cli import main
    path = tmp_path / "spec.json"
    path.write_text(json.dumps({"hypothesis_predictions": [{"hypothesis_id": "h1"}], "candidate_experiment_ids": ["e1"]}))
    assert main(["recommend", str(path)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False
    assert "outcomes_by_experiment" in result["error"]
