from __future__ import annotations

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
    with pytest.raises(TaskIterationError, match="expected evidence or event ids are missing from the model: ev_typo"):
        _prediction(expected_evidence_ids=["ev_typo"])


def test_loaded_prediction_accepts_missing_optional_task_fields() -> None:
    raw = _prediction().to_dict()
    for key in ("task_id", "purpose", "coverage_ids", "assumptions", "unknowns"):
        raw.pop(key)
    loaded = task_iteration_module.PredictionSnapshot.from_dict(raw)
    assert loaded.coverage_ids == ()


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


def test_candidate_cannot_rewrite_construction_evidence_binding(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(task_iteration_module, "evaluate_storyline_depth", lambda *args, **kwargs: _PassingDepth())
    construction = _observation()
    comparison = load_comparison(_comparison_file(tmp_path, construction))
    data = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    next(
        item for item in data["evidence"] if item["evidence_id"] == "ev_pr_fix"
    )["raw_text"] = "Candidate rewrote the construction evidence."
    candidate = tmp_path / "candidate-rebound.yaml"
    candidate.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    with pytest.raises(TaskIterationError, match="construction evidence changed in candidate"):
        decide_candidate_revision(
            comparison=comparison,
            candidate_model_path=candidate,
            observation=construction,
            holdout_observation=_observation(holdout=True),
            required_holdout_evidence_ids=["ev_meeting_boundary"],
        )


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
        "--expected-event", "event_mitigation", "--weakens-when", "missing",
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
