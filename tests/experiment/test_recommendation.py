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
        source_ref=f"source:{suffix}",
        observed_at="2026-07-31T12:00:00+00:00",
        role=role,
        status=status,
    )


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


@pytest.mark.parametrize("iteration", [0, 1])
def test_real_observation_closes_only_with_independent_holdout(iteration: int) -> None:
    prior = observe_experiments(_spec(), ()) if iteration else None
    spec = _spec(
        iteration=iteration,
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
        _spec(iteration=iteration, prior_open_gap_ids=()),
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
            **values, iteration=iteration, prior_open_gap_ids=(),
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
    assert sufficient.selected_experiment_ids == ("e1", "e2")
    assert sufficient.alternative_minimal_sets == ()


def test_one_survivor_closes_without_a_holdout() -> None:
    result = observe_experiments(
        _spec(),
        (_observation("e1", "up", role="construction", suffix="a"),),
    )
    assert result.terminal_reason == "model_closed_for_task"
    assert result.holdout_evidence_ids == ()
    assert result.recommendation.alternative_minimal_sets == ()
    assert "receipt_fingerprint" not in result.to_dict()


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


def test_reused_evidence_id_is_rejected() -> None:
    first = _observation("e1", "up", role="construction", suffix="a")
    second = ExperimentObservation(
        experiment_id="e2",
        observed_outcome="hot",
        evidence_id=first.evidence_id,
        source_ref="source:b",
        observed_at="2026-07-31T12:01:00+00:00",
        role="holdout",
    )
    with pytest.raises(ValueError, match="evidence_id values must be unique"):
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


def _cost_spec(**overrides) -> ExperimentSpec:
    """A costly single experiment competes with two cheap complementary ones."""
    values = {
        "hypothesis_predictions": (
            HypothesisPrediction("h1", {"all": "a", "left": "0", "right": "0"}),
            HypothesisPrediction("h2", {"all": "b", "left": "1", "right": "0"}),
            HypothesisPrediction("h3", {"all": "c", "left": "0", "right": "1"}),
        ),
        "candidate_experiment_ids": ("right", "all", "left"),
        "coverage_ids": ("h1", "h2", "h3", "all", "left", "right"),
    }
    values.update(overrides)
    return _spec(**values)


def _evergiven_spec(**overrides) -> ExperimentSpec:
    """Declared trial matrix from the packet, not independently verified facts."""
    values = {
        "hypothesis_predictions": (
            HypothesisPrediction("h_suez", {
                "e_transpacific": "ae_rise_much_larger", "e_reversion": "reverts_by_may",
                "e_yantian_timing": "no_jump"}),
            HypothesisPrediction("h_demand", {
                "e_transpacific": "similar_rise", "e_reversion": "keeps_rising",
                "e_yantian_timing": "no_jump"}),
            HypothesisPrediction("h_yantian", {
                "e_transpacific": "similar_rise", "e_reversion": "keeps_rising",
                "e_yantian_timing": "jump_in_june"}),
        ),
        "candidate_experiment_ids": ("e_transpacific", "e_reversion", "e_yantian_timing"),
        "coverage_ids": ("h_suez", "h_demand", "h_yantian", "e_transpacific", "e_reversion", "e_yantian_timing"),
    }
    values.update(overrides)
    return _spec(**values)


def test_cost_picks_the_cheaper_distinguishing_set() -> None:
    costs = {"all": 9, "left": 1, "right": 1}
    assert recommend_experiments(_cost_spec()).selected_experiment_ids == ("all",)
    assert recommend_experiments(_cost_spec(cost_by_experiment=None)).selected_experiment_ids == ("all",)
    result = recommend_experiments(_cost_spec(cost_by_experiment=costs))
    assert result.selected_experiment_ids == ("left", "right")
    assert result.alternative_minimal_sets == ()
    # Every pair distinguishes; naive float sums all overflow and lose cost order.
    finite_large = recommend_experiments(_spec(
        hypothesis_predictions=(
            HypothesisPrediction("h1", {"a": "0", "b": "0", "z": "0"}),
            HypothesisPrediction("h2", {"a": "1", "b": "0", "z": "1"}),
            HypothesisPrediction("h3", {"a": "0", "b": "1", "z": "1"})),
        candidate_experiment_ids=("a", "b", "z"),
        coverage_ids=("h1", "h2", "h3", "a", "b", "z"),
        cost_by_experiment={"a": 1.6e308, "b": 1.5e308, "z": 1.4e308}))
    assert finite_large.selected_experiment_ids == ("b", "z")
    bounded = recommend_experiments(_cost_spec(cost_by_experiment=costs, maximum_experiment_count=1))
    assert bounded.selected_experiment_ids == ("all",)
    packet = recommend_experiments(_evergiven_spec(cost_by_experiment={
        "e_transpacific": 1, "e_reversion": 5, "e_yantian_timing": 1}))
    assert packet.selected_experiment_ids == ("e_transpacific", "e_yantian_timing")


@pytest.mark.parametrize("costs, expected", [
    ({}, ("all",)),
    ({"all": 4, "left": 0}, ("left", "right")),
    ({"all": 2, "left": 1, "right": 1}, ("all",)),
    ({"all": 5, "left": 0, "right": 0}, ("left", "right")),
])
def test_cost_presence_defaults_zero_and_count_tiebreak(costs, expected) -> None:
    spec = _cost_spec(cost_by_experiment=costs)
    assert spec.to_dict()["cost_by_experiment"] == costs
    result = recommend_experiments(spec)
    assert result.selected_experiment_ids == expected
    assert result.alternative_minimal_sets == ()
    assert "cost_by_experiment" not in _cost_spec().to_dict()


def test_cost_alternatives_are_other_equal_cost_and_count_sets() -> None:
    tied = recommend_experiments(_spec(cost_by_experiment={"e1": 0, "e2": 0}))
    assert tied.selected_experiment_ids == ("e1",)
    assert tied.alternative_minimal_sets == (("e2",),)
    costly = recommend_experiments(_spec(cost_by_experiment={"e1": 0, "e2": 1}))
    assert costly.selected_experiment_ids == ("e1",)
    assert costly.alternative_minimal_sets == ()


@pytest.mark.parametrize("costs", [
    {"e1": -1}, {"e1": True}, {"e1": float("nan")},
    {"e1": float("inf")}, {"e1": float("-inf")}, {"e1": "1"},
    {"e1": None}, {"outside": 1}, [], "costs",
])
def test_invalid_native_costs_are_rejected(costs) -> None:
    with pytest.raises(ValueError, match="cost"):
        _spec(cost_by_experiment=costs)


@pytest.mark.parametrize("costs", [None, [], 1, "costs"])
def test_explicit_json_costs_require_a_mapping(costs, tmp_path, capsys) -> None:
    from researchguard.experiment.cli import main

    payload = _spec().to_dict()
    payload["cost_by_experiment"] = costs
    path = tmp_path / "invalid-cost.json"
    path.write_text(json.dumps(payload))
    assert main(["recommend", str(path)]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False
    assert "cost" in report["error"]


def test_cost_candidate_limit_does_not_limit_legacy_cardinality() -> None:
    def many(count, **overrides):
        ids = tuple(f"e{i:02d}" for i in range(count))
        return _spec(
            candidate_experiment_ids=ids,
            hypothesis_predictions=(
                HypothesisPrediction("h1", dict.fromkeys(ids, "up")),
                HypothesisPrediction("h2", dict.fromkeys(ids, "down"))),
            **overrides)

    assert recommend_experiments(many(16, cost_by_experiment={})).selected_experiment_ids == ("e00",)
    with pytest.raises(ValueError, match="16"):
        many(17, cost_by_experiment={})
    assert recommend_experiments(many(17)).selected_experiment_ids == ("e00",)


@pytest.mark.parametrize("costs, expected", [({}, ("a",)), ({"observed": 0, "a": 9, "z": 0}, ("z",))])
def test_remaining_recommendation_preserves_cost_mode_and_projects_known_ids(costs, expected) -> None:
    spec = _spec(
        cost_by_experiment=costs,
        candidate_experiment_ids=("z", "observed", "a"),
        coverage_ids=("h1", "h2", "h3", "observed", "a", "z"),
        hypothesis_predictions=(
            HypothesisPrediction("h1", {"observed": "keep", "a": "up", "z": "up"}),
            HypothesisPrediction("h2", {"observed": "keep", "a": "down", "z": "down"}),
            HypothesisPrediction("h3", {"observed": "discard", "a": "up", "z": "up"})))
    result = observe_experiments(spec, (_observation("observed", "keep", role="construction", suffix="observed"),))
    assert result.terminal_reason == "continue_iteration"
    assert result.next_experiment_ids == expected
    assert [(row.hypothesis_id, row.status) for row in result.hypothesis_dispositions] == [
        ("h1", "consistent"), ("h2", "consistent"), ("h3", "eliminated")]


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


@pytest.mark.parametrize("status", ["invalid", "not_run"])
def test_invalid_counterexamples_do_not_eliminate_on_a_matrix_miss(status) -> None:
    result = observe_experiments(_spec(), (
        _observation("e1", "up", role="construction", suffix="invalid", status=status),
        _observation("e2", "unknown", role="construction", suffix="miss")))
    assert all(row.status == "model_miss" for row in result.hypothesis_dispositions)
    assert f"observation-{status}:e1" in result.introduced_gap_ids
    assert result.terminal_reason != "model_closed_for_task"


def test_old_port_fields_are_ignored(tmp_path, capsys) -> None:
    from researchguard.experiment.cli import _load_observations, _load_spec, main

    clean_spec = _spec()
    payload = clean_spec.to_dict()
    for row in payload["hypothesis_predictions"]:
        row.update(observation_port_by_experiment={"e1": "legacy-in"}, outcome_port_by_experiment={"e1": "legacy-out"})
    path = tmp_path / "legacy-spec.json"
    path.write_text(json.dumps(payload))
    loaded = _load_spec(path)
    assert loaded == clean_spec
    assert all(not {"observation_port_by_experiment", "outcome_port_by_experiment"} & row.keys()
               for row in loaded.to_dict()["hypothesis_predictions"])
    assert main(["recommend", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["selected_experiment_ids"] == ["e1"]
    clean = (_observation("e1", "up", role="construction", suffix="construction"),)
    observations = [dict(row.to_dict(), observation_port_id="legacy-in", outcome_port_id="legacy-out") for row in clean]
    observed_path = tmp_path / "legacy-observations.json"
    observed_path.write_text(json.dumps(observations))
    assert _load_observations(observed_path) == clean
    assert main(["observe", str(path), str(observed_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["terminal_reason"] == "model_closed_for_task"
    assert all(not {"observation_port_id", "outcome_port_id"} & row.keys() for row in result["observations"])
