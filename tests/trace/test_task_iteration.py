from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

import pytest
import yaml

import researchguard.trace.task_iteration as task_iteration_module
from researchguard.trace.cli import main
from researchguard.trace.inference.types import fingerprint
from researchguard.trace.loader import load_model
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
    model = load_model(EXAMPLE)
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
            "evidence_bindings": {
                item: f"sha256:{fingerprint(asdict(model.evidence_by_id()[item]))}"
                for item in evidence_ids
            },
            "event_bindings": {
                item: f"sha256:{fingerprint(asdict(model.event_by_id()[item]))}"
                for item in event_ids
            },
            "source_bindings": {
                item: f"sha256:{fingerprint(asdict(model.source_by_id()[item]))}"
                for item in source_ids
            },
            "future_holdout_status": "not_run",
            "future_holdout_validator_receipt": "",
        }
    )


def _comparison_file(tmp_path: Path, observation, **prediction_overrides) -> Path:
    payload = compare_prediction_observation(_prediction(**prediction_overrides), observation)
    path = tmp_path / "comparison.json"
    write_artifact(path, payload)
    return path


def test_current_prediction_requires_explicit_task_scope() -> None:
    with pytest.raises(TypeError):
        freeze_prediction(
            model_path=EXAMPLE,
            prediction_id="old-shape",
            frozen_at="2026-07-17T10:00:00+00:00",
            target_kind="storyline",
            target_id="trace_metadata_incident",
            prediction_kind="evidence_footprint",
            expected_evidence_ids=["ev_pr_fix"],
            weakens_when="missing",
        )
    assert _prediction().coverage_fingerprint


def test_loaded_prediction_rejects_implicit_or_rebound_task_scope() -> None:
    raw = _prediction().to_dict()
    raw.pop("unknowns")
    raw["snapshot_fingerprint"] = ""
    with pytest.raises(TaskIterationError, match="missing task fields"):
        task_iteration_module.PredictionSnapshot.from_dict(raw)
    raw = _prediction().to_dict()
    raw["coverage_ids"] = ["trace_metadata_incident"]
    raw["snapshot_fingerprint"] = ""
    with pytest.raises(TaskIterationError, match="coverage_fingerprint mismatch"):
        task_iteration_module.PredictionSnapshot.from_dict(raw)


def test_observation_must_follow_prediction() -> None:
    with pytest.raises(TaskIterationError, match="must be later"):
        compare_prediction_observation(
            _prediction(),
            _observation(observed_at="2026-07-17T09:59:59+00:00"),
        )


def test_stale_semantic_evidence_binding_is_rejected() -> None:
    raw = _observation().to_dict()
    raw["observation_fingerprint"] = ""
    raw["evidence_bindings"]["ev_pr_fix"] = "sha256:" + "0" * 64
    observation = EvidenceBatchObservation.from_dict(raw)
    with pytest.raises(TaskIterationError, match="evidence binding"):
        compare_prediction_observation(_prediction(), observation)


def test_current_native_depth_receipt_controls_local_match_terminal() -> None:
    comparison = compare_prediction_observation(_prediction(), _observation())
    assert comparison["native_depth_receipt_id"]
    assert comparison["native_depth_receipt"]["closure_status"] in {"PASS", "GAP"}
    assert (comparison["terminal_reason"] == "model_closed_for_task") is (
        comparison["native_depth_receipt"]["closure_status"] == "PASS"
        and not comparison["open_gap_ids"]
    )


def test_candidate_accepts_only_with_separate_holdout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(task_iteration_module, "evaluate_storyline_depth", lambda *args, **kwargs: _PassingDepth())
    construction = _observation()
    comparison = load_comparison(_comparison_file(tmp_path, construction))
    revision = decide_candidate_revision(
        comparison=comparison,
        candidate_model_path=_candidate_model(tmp_path),
        observation=construction,
        holdout_observation=_observation(holdout=True),
        required_holdout_evidence_ids=["ev_meeting_boundary"],
    )
    assert revision["disposition"] == "accepted"
    assert revision["terminal_reason"] == "model_closed_for_task"
    assert revision["native_depth_receipt_id"] == "traceguard-depth:passing"


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
    with pytest.raises(TaskIterationError, match="construction evidence binding"):
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


def test_cli_requires_strict_task_and_holdout_artifacts(tmp_path: Path) -> None:
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
        "--task-id", "trace-cli", "--purpose", "strict trace CLI", "--coverage-id",
        "trace_metadata_incident", "--iteration", "0", "--max-iterations", "4",
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
