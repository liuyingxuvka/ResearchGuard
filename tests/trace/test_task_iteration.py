from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest
import yaml

import researchguard.trace.task_iteration as task_iteration_module
from researchguard.trace.cli import main
from researchguard.trace.task_iteration import (
    EvidenceBatchObservation,
    TaskIterationError,
    compare_prediction_observation,
    decide_candidate_revision,
    freeze_prediction,
    load_comparison,
    write_artifact,
)


EXAMPLE = Path("examples/trace/incident_response_storyline.yaml")


class _PassingDepth:
    receipt_id = "traceguard-depth:passing"
    unresolved_gaps = ()
    critical_uncovered_ids = ()
    critical_ineffective_ids = ()
    hierarchy_fingerprint = "sha256:" + "1" * 64
    interface_fingerprint = "sha256:" + "2" * 64
    live_alternative_ids = ()
    causal_boundaries = ()
    deepest_proven_layer = "native-storyline-depth"
    first_unresolved_gap = ""

    def to_dict(self):
        return {
            "schema_version": "researchguard.trace.storyline_depth.v2",
            "receipt_id": self.receipt_id,
            "closure_status": "PASS",
            "unresolved_gaps": [],
        }


def _candidate_model(tmp_path: Path) -> Path:
    data = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    data["metadata"]["purpose"] += " Candidate task revision."
    path = tmp_path / "candidate.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _prediction(**overrides):
    values = {
        "model_path": EXAMPLE,
        "prediction_id": "prediction-1",
        "frozen_at": "2026-07-17T10:00:00+00:00",
        "target_kind": "storyline",
        "target_id": "trace_metadata_incident",
        "prediction_kind": "evidence_footprint",
        "expected_evidence_ids": ["ev_pr_fix"],
        "expected_event_ids": ["event_mitigation"],
        "expected_event_order": ["event_mitigation"],
        "weakens_when": "The mitigation evidence or event is absent.",
        "task_id": "trace-task-1",
        "purpose": "validate the mitigation storyline without overclaim",
        "coverage_ids": ["trace_metadata_incident", "ev_pr_fix", "ev_meeting_boundary"],
        "assumptions": [],
        "unknowns": [],
        "iteration": 0,
        "max_iterations": 4,
    }
    values.update(overrides)
    return freeze_prediction(**values)


def _observation(*, holdout: bool = False, observed_at: str | None = None):
    if holdout:
        evidence_ids = ("ev_meeting_boundary",)
        event_ids = ("event_boundary",)
        source_ids = ("src_meeting",)
        observation_id = "observation-holdout"
    else:
        evidence_ids = ("ev_pr_fix",)
        event_ids = ("event_mitigation",)
        source_ids = ("src_pr",)
        observation_id = "observation-construction"
    return EvidenceBatchObservation.from_dict(
        {
            "schema_version": "researchguard.trace.evidence_batch_observation.v2",
            "observation_id": observation_id,
            "observed_at": observed_at or "2026-07-17T11:00:00+00:00",
            "quality_status": "valid",
            "evidence_ids": list(evidence_ids),
            "event_ids": list(event_ids),
            "event_order": list(event_ids),
            "contradiction_ids": [],
            "source_refs": list(source_ids),
            "future_holdout_status": "not_run",
        }
    )


def _comparison_file(tmp_path: Path, observation, **prediction_overrides) -> Path:
    payload = compare_prediction_observation(_prediction(**prediction_overrides), observation)
    path = tmp_path / "comparison.json"
    write_artifact(path, payload)
    return path



# Supplied Ever Given trial/approximate transcription, not retrieved factual evidence.
TRIAL_FIXTURES = Path(__file__).parent / "fixtures"


def _new_record_case(tmp_path, *, opposition_relevance=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    baseline = tmp_path / "baseline.yaml"
    baseline.write_bytes((TRIAL_FIXTURES / "evergiven_task_iteration_baseline.yaml").read_bytes())
    raw = json.loads((TRIAL_FIXTURES / "evergiven_task_iteration_observation.json").read_text(encoding="utf-8"))
    if opposition_relevance is not None:
        next(row for row in raw["new_links"] if row["link_id"] == "l_suez_tp")["declared_relevance"] = opposition_relevance
    observation = EvidenceBatchObservation.from_dict(raw)
    data = yaml.safe_load(baseline.read_text(encoding="utf-8"))
    for observed_key, model_key in (("new_sources", "sources"), ("new_evidence", "evidence"),
                                    ("new_events", "events"), ("new_links", "hypothesis_evidence_links")):
        data[model_key] = data.get(model_key, []) + raw[observed_key]
    candidate = tmp_path / "candidate.yaml"
    candidate.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return baseline, observation, candidate


def _new_record_prediction(baseline, direction="weaken"):
    return freeze_prediction(model_path=baseline, prediction_id="trial-transpacific",
        frozen_at="2026-10-21T19:00:00Z", target_kind="hypothesis", target_id="h_suez",
        prediction_kind="evidence_footprint", expected_evidence_ids=["anc-transpacific"],
        expected_event_ids=["event_tp_rise"], expected_event_order=["event_tp_rise"],
        expected_direction=direction, coverage_ids=["h_suez", "trace_freight_2021"])


def test_prediction_needs_only_a_known_target_and_an_expectation() -> None:
    prediction = freeze_prediction(
        model_path=EXAMPLE,
        prediction_id="minimal",
        frozen_at="2026-07-17T10:00:00+00:00",
        target_kind="storyline",
        target_id="trace_metadata_incident",
        prediction_kind="evidence_footprint",
        expected_evidence_ids=["ev_pr_fix"],
        weakens_when="missing",
    )
    assert prediction.iteration == 0
    assert "snapshot_fingerprint" not in prediction.to_dict()
    with pytest.raises(TaskIterationError, match="target is missing from the model"):
        _prediction(target_id="trace_unknown")
    with pytest.raises(TaskIterationError, match="coverage ids are missing from the model: ev_unknown"):
        _prediction(coverage_ids=["ev_pr_fix", "ev_unknown"])


def test_loaded_prediction_accepts_missing_optional_task_fields() -> None:
    raw = _prediction().to_dict()
    for key in ("task_id", "purpose", "coverage_ids", "assumptions", "unknowns", "expected_direction"):
        raw.pop(key)
    loaded = task_iteration_module.PredictionSnapshot.from_dict(raw)
    assert loaded.coverage_ids == ()
    assert loaded.expected_direction == ""


def test_observation_must_follow_prediction() -> None:
    with pytest.raises(TaskIterationError, match="must be later"):
        compare_prediction_observation(
            _prediction(),
            _observation(observed_at="2026-07-17T09:59:59+00:00"),
        )


def test_observed_ids_must_exist_in_the_model() -> None:
    raw = _observation().to_dict()
    raw["evidence_ids"] = ["ev_unknown"]
    observation = EvidenceBatchObservation.from_dict(raw)
    with pytest.raises(TaskIterationError, match="observed evidence is missing from the model"):
        compare_prediction_observation(_prediction(), observation)


def test_native_depth_gaps_control_local_match_terminal() -> None:
    comparison = compare_prediction_observation(_prediction(), _observation())
    assert "native_depth_receipt" not in comparison
    assert (comparison["terminal_reason"] == "model_closed_for_task") is (
        not comparison["open_gap_ids"]
    )


def test_candidate_accepts_only_with_separate_holdout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(task_iteration_module, "evaluate_storyline_depth", lambda *args, **kwargs: _PassingDepth())
    construction = _observation()
    comparison = load_comparison(_comparison_file(tmp_path, construction))
    comparison.pop("baseline_gap_ids")  # Older comparison artifacts recompute native baseline gaps.
    revision = decide_candidate_revision(
        comparison=comparison,
        candidate_model_path=_candidate_model(tmp_path),
        observation=construction,
        holdout_observation=_observation(holdout=True),
        required_holdout_evidence_ids=["ev_meeting_boundary"],
    )
    assert revision["disposition"] == "accepted"
    assert revision["terminal_reason"] == "model_closed_for_task"
    assert "revision_fingerprint" not in revision


def test_candidate_can_be_accepted_without_a_holdout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(task_iteration_module, "evaluate_storyline_depth", lambda *args, **kwargs: _PassingDepth())
    construction = _observation()
    comparison = load_comparison(_comparison_file(tmp_path, construction))
    revision = decide_candidate_revision(
        comparison=comparison,
        candidate_model_path=_candidate_model(tmp_path),
        observation=construction,
    )
    assert revision["disposition"] == "accepted"
    assert revision["holdout_observation_id"] == ""


def test_same_evidence_cannot_be_reused_as_holdout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(task_iteration_module, "evaluate_storyline_depth", lambda *args, **kwargs: _PassingDepth())
    construction = _observation()
    comparison = load_comparison(_comparison_file(tmp_path, construction))
    with pytest.raises(TaskIterationError, match="holdout observation must be independent"):
        decide_candidate_revision(
            comparison=comparison,
            candidate_model_path=_candidate_model(tmp_path),
            observation=construction,
            holdout_observation=construction,
            required_holdout_evidence_ids=["ev_pr_fix"],
        )


@pytest.mark.parametrize("field, identifier, changed_field, value", [
    ("sources", "src-wci-transpacific", "title", "Rewritten observed source"),
    ("evidence", "anc-transpacific", "raw_text", "Rewritten observed evidence"),
    ("events", "event_tp_rise", "action", "Rewritten observed event"),
    ("hypothesis_evidence_links", "l_suez_tp", "polarity", "support"),
])
def test_candidate_cannot_rewrite_construction_evidence_binding(tmp_path, field, identifier, changed_field, value) -> None:
    baseline, observation, candidate = _new_record_case(tmp_path)
    comparison = compare_prediction_observation(_new_record_prediction(baseline), observation)
    data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
    id_field = {"sources": "source_id", "evidence": "evidence_id", "events": "event_id",
                "hypothesis_evidence_links": "link_id"}[field]
    next(row for row in data[field] if row[id_field] == identifier)[changed_field] = value
    candidate.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    with pytest.raises(TaskIterationError, match=identifier):
        decide_candidate_revision(comparison=comparison, candidate_model_path=candidate,
                                  observation=observation,
                                  addressed_mismatch_ids=[row["mismatch_id"] for row in comparison["mismatches"]])


def test_explicit_rollback_retains_baseline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(task_iteration_module, "evaluate_storyline_depth", lambda *args, **kwargs: _PassingDepth())
    construction = _observation()
    comparison = load_comparison(_comparison_file(tmp_path, construction))
    revision = decide_candidate_revision(
        comparison=comparison,
        candidate_model_path=_candidate_model(tmp_path),
        observation=construction,
        holdout_observation=_observation(holdout=True),
        required_holdout_evidence_ids=["ev_meeting_boundary"],
        force_rollback=True,
    )
    assert revision["disposition"] == "rolled_back"
    assert revision["effective_model_sha256"] == revision["baseline_model_sha256"]


def test_cli_runs_the_loop_with_optional_task_fields(tmp_path: Path) -> None:
    prediction_path = tmp_path / "prediction.json"
    construction_path = tmp_path / "construction.json"
    holdout_path = tmp_path / "holdout.json"
    comparison_path = tmp_path / "comparison.json"
    revision_path = tmp_path / "revision.json"
    construction_path.write_text(json.dumps(_observation().to_dict()), encoding="utf-8")
    holdout_path.write_text(json.dumps(_observation(holdout=True).to_dict()), encoding="utf-8")
    candidate = _candidate_model(tmp_path)
    assert main([
        "iterate", "freeze", "--model", str(EXAMPLE), "--prediction-id", "prediction-cli",
        "--frozen-at", "2026-07-17T10:00:00+00:00", "--target-kind", "storyline",
        "--target-id", "trace_metadata_incident", "--expected-evidence", "ev_pr_fix",
        "--expected-event", "event_mitigation", "--expected-direction", "unchanged",
        "--output", str(prediction_path),
    ]) == 0
    assert main([
        "iterate", "compare", "--prediction", str(prediction_path), "--observation",
        str(construction_path), "--output", str(comparison_path),
    ]) == 0
    assert main([
        "iterate", "decide", "--comparison", str(comparison_path), "--observation",
        str(construction_path), "--holdout-observation", str(holdout_path), "--candidate",
        str(candidate), "--required-holdout-evidence", "ev_meeting_boundary", "--output",
        str(revision_path),
    ]) == 0
    assert json.loads(comparison_path.read_text(encoding="utf-8"))["observed_direction"] == "unchanged"
    payload = json.loads(revision_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "researchguard.trace.candidate_storyline_revision.v2"


def test_mismatch_ids_never_enter_gap_transitions(tmp_path: Path) -> None:
    prediction = _prediction(expected_evidence_ids=["ev_meeting_boundary"])
    observation = _observation()
    comparison = compare_prediction_observation(prediction, observation)
    assert any(item["mismatch_type"] == "expected_evidence_missing" for item in comparison["mismatches"])
    assert comparison["progressed"] is False
    assert not comparison["introduced_gap_ids"]
    revision = decide_candidate_revision(comparison=comparison, candidate_model_path=_candidate_model(tmp_path),
                                         observation=observation)
    assert revision["unaddressed_mismatch_ids"]
    assert any("unaddressed mismatch" in reason for reason in revision["rejection_reasons"])
    assert revision["disposition"] != "accepted"
    assert revision["input_gap_ids"] == comparison["baseline_gap_ids"]
    assert revision["persisted_gap_ids"] == comparison["baseline_gap_ids"]
    assert not revision["introduced_gap_ids"]
    assert revision["progressed"] is False
    for payload in (comparison, revision):
        assert not any(item.startswith("mismatch-") for item in payload["gap_transitions"])
        assert not set(payload["persisted_gap_ids"]) & set(payload["introduced_gap_ids"])



def test_freeze_accepts_evidence_not_yet_in_the_model(tmp_path) -> None:
    baseline, observation, _ = _new_record_case(tmp_path)
    data = yaml.safe_load(baseline.read_text(encoding="utf-8"))
    assert "anc-transpacific" not in {row["evidence_id"] for row in data["evidence"]}
    assert "event_tp_rise" not in {row["event_id"] for row in data["events"]}
    prediction = _new_record_prediction(baseline)
    assert prediction.expected_evidence_ids == ("anc-transpacific",)
    assert prediction.expected_event_ids == ("event_tp_rise",)
    assert prediction.expected_direction == "weaken" and prediction.weakens_when == ""
    assert observation.event_ids == () and observation.event_order == ("event_tp_rise",)


def test_compare_computes_the_direction(tmp_path) -> None:
    baseline, observation, candidate = _new_record_case(tmp_path)
    before = baseline.read_bytes(), candidate.read_bytes(), observation.to_dict()
    result = compare_prediction_observation(_new_record_prediction(baseline), observation)
    assert result["support_after"] < result["support_before"] - .01
    assert result["observed_direction"] == "weaken"
    types = {row["mismatch_type"] for row in result["mismatches"]}
    assert not types & {"direction_mismatch", "expected_evidence_missing", "expected_event_missing", "event_order_mismatch"}
    assert result["factual_future_prediction_licensed"] is False
    assert (baseline.read_bytes(), candidate.read_bytes(), observation.to_dict()) == before


def test_wrong_direction_is_a_mismatch(tmp_path) -> None:
    baseline, observation, _ = _new_record_case(tmp_path)
    result = compare_prediction_observation(_new_record_prediction(baseline, "strengthen"), observation)
    assert result["observed_direction"] == "weaken"
    assert result["support_after"] < result["support_before"] - .01
    assert any(row["mismatch_type"] == "direction_mismatch" for row in result["mismatches"])


def test_depth_gaps_are_not_mismatches(tmp_path) -> None:
    baseline, observation, _ = _new_record_case(tmp_path)
    result = compare_prediction_observation(_new_record_prediction(baseline), observation)
    assert result["open_depth_gap_ids"]
    assert not any(row["mismatch_type"] == "native_depth_gap" for row in result["mismatches"])
    assert set(result["open_depth_gap_ids"]) <= set(result["open_gap_ids"])
    assert not any(identifier.startswith("mismatch-") for identifier in result["gap_transitions"])
    assert result["terminal_reason"] != "model_closed_for_task"


def test_revision_can_be_accepted_while_alternatives_stay_live(tmp_path, monkeypatch) -> None:
    actual_evaluations = []
    phase = ["exact supplied trial"]
    native_evaluate = task_iteration_module.evaluate_model

    def record_native_evaluation(model, *args, **kwargs):
        result = native_evaluate(model, *args, **kwargs)
        actual_evaluations.append({"phase": phase[0], "hypotheses": [
            {"id": row.hypothesis_id, "support": row.support, "rank": row.rank, "live": row.live}
            for row in result.inference_receipt.hypothesis_projections]})
        return result

    monkeypatch.setattr(task_iteration_module, "evaluate_model", record_native_evaluation)
    baseline, observation, candidate = _new_record_case(tmp_path / "exact")
    before = baseline.read_bytes(), candidate.read_bytes(), observation.to_dict()
    comparison = compare_prediction_observation(_new_record_prediction(baseline), observation)
    revision = decide_candidate_revision(comparison=comparison, candidate_model_path=candidate,
        observation=observation, addressed_mismatch_ids=[row["mismatch_id"] for row in comparison["mismatches"]])
    assert revision["candidate_evaluation_ok"] and revision["disposition"] == "accepted"
    assert revision["open_gap_ids"] and revision["terminal_reason"] == "continue_iteration"
    assert revision["effective_model_sha256"] == revision["candidate_model_sha256"]
    assert revision["effective_model_sha256"] != revision["baseline_model_sha256"]
    assert revision["factual_future_prediction_licensed"] is False
    assert (baseline.read_bytes(), candidate.read_bytes(), observation.to_dict()) == before

    # Explicit trial variant: only the new opposition link's relevance is .8
    # instead of .9, keeping a real nonleader live under the unchanged .12 margin.
    phase[0] = "trial opposition relevance .8"
    baseline, observation, candidate = _new_record_case(tmp_path / "live", opposition_relevance=.8)
    before = baseline.read_bytes(), candidate.read_bytes(), observation.to_dict()
    comparison = compare_prediction_observation(_new_record_prediction(baseline), observation)
    live_revision = decide_candidate_revision(comparison=comparison, candidate_model_path=candidate,
        observation=observation, addressed_mismatch_ids=[row["mismatch_id"] for row in comparison["mismatches"]])
    assert live_revision["candidate_evaluation_ok"] and live_revision["disposition"] == "accepted"
    assert "h_suez" in live_revision["live_alternative_ids"]
    assert live_revision["open_gap_ids"] and live_revision["terminal_reason"] == "continue_iteration"
    assert live_revision["effective_model_sha256"] == live_revision["candidate_model_sha256"]
    assert (baseline.read_bytes(), candidate.read_bytes(), observation.to_dict()) == before
    print(json.dumps({"native_hypothesis_evaluations": actual_evaluations,
                      "exact_live_alternative_ids": revision["live_alternative_ids"],
                      "trial_variant_live_alternative_ids": live_revision["live_alternative_ids"]}))


@pytest.mark.parametrize("field", ["new_sources", "new_evidence", "new_events", "new_links"])
def test_observation_rejects_duplicate_new_record_ids(tmp_path, field) -> None:
    baseline, observation, _ = _new_record_case(tmp_path)
    raw = observation.to_dict()
    raw[field] = [*raw[field], raw[field][0]]
    identifier = raw[field][0][{"new_sources": "source_id", "new_evidence": "evidence_id",
                               "new_events": "event_id", "new_links": "link_id"}[field]]
    with pytest.raises(TaskIterationError, match=identifier):
        duplicated = EvidenceBatchObservation.from_dict(raw)
        compare_prediction_observation(_new_record_prediction(baseline), duplicated)


def test_observed_new_evidence_cannot_reuse_a_baseline_id(tmp_path) -> None:
    baseline, observation, _ = _new_record_case(tmp_path)
    identifier = yaml.safe_load(baseline.read_text(encoding="utf-8"))["evidence"][0]["evidence_id"]
    raw = observation.to_dict()
    raw["new_evidence"][0]["evidence_id"] = identifier
    raw["evidence_ids"] = [identifier]
    for event in raw["new_events"]:
        event["evidence_ids"] = [identifier]
    for link in raw["new_links"]:
        link["evidence_id"] = identifier
    with pytest.raises(TaskIterationError, match=identifier):
        colliding = EvidenceBatchObservation.from_dict(raw)
        compare_prediction_observation(_new_record_prediction(baseline), colliding)


@pytest.mark.parametrize("quality", ["invalid", "access_gap"])
def test_invalid_observation_cannot_be_accepted_even_when_mismatches_are_addressed(tmp_path, quality) -> None:
    observation = replace(_observation(), quality_status=quality)
    comparison = compare_prediction_observation(_prediction(), observation)
    assert any(row["mismatch_type"] == "observation_invalid" for row in comparison["mismatches"])
    revision = decide_candidate_revision(comparison=comparison, candidate_model_path=_candidate_model(tmp_path),
        observation=observation, addressed_mismatch_ids=[row["mismatch_id"] for row in comparison["mismatches"]])
    assert revision["disposition"] != "accepted"
    assert any("valid" in reason for reason in revision["rejection_reasons"])


def test_distinct_holdout_observation_cannot_reuse_new_construction_evidence(tmp_path) -> None:
    baseline, observation, candidate = _new_record_case(tmp_path)
    observation = replace(observation, evidence_ids=())
    assert not observation.evidence_ids and observation.new_evidence
    comparison = compare_prediction_observation(_new_record_prediction(baseline), observation)
    holdout = replace(observation, observation_id="distinct-holdout", evidence_ids=("anc-transpacific",),
                      event_ids=("event_tp_rise",), new_sources=(), new_evidence=(), new_events=(), new_links=())
    with pytest.raises(TaskIterationError, match="disjoint"):
        decide_candidate_revision(comparison=comparison, candidate_model_path=candidate, observation=observation,
                                  holdout_observation=holdout, required_holdout_evidence_ids=["anc-transpacific"])


def test_loaded_prediction_refuses_a_changed_baseline(tmp_path) -> None:
    baseline, observation, _ = _new_record_case(tmp_path)
    prediction = _new_record_prediction(baseline)
    baseline.write_bytes(baseline.read_bytes() + b"\n# edited after freeze\n")
    with pytest.raises(TaskIterationError, match="stale"):
        task_iteration_module.PredictionSnapshot.from_dict(prediction.to_dict())
    with pytest.raises(TaskIterationError, match="stale"):
        compare_prediction_observation(prediction, observation)


def test_lifecycle_artifact_write_never_overwrites_an_existing_file(tmp_path) -> None:
    path = tmp_path / "existing.json"
    path.write_bytes(b"existing immutable-style artifact\n")
    with pytest.raises(TaskIterationError, match="refusing to overwrite"):
        write_artifact(path, {"changed": True})
    assert path.read_bytes() == b"existing immutable-style artifact\n"


def test_new_event_order_still_detects_a_missing_expected_order(tmp_path) -> None:
    baseline, observation, _ = _new_record_case(tmp_path)
    observation = replace(observation, event_order=())
    comparison = compare_prediction_observation(_new_record_prediction(baseline), observation)
    assert any(row["mismatch_type"] == "event_order_mismatch" for row in comparison["mismatches"])
