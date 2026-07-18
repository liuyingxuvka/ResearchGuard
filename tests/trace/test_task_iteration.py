from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

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


def _candidate_model(tmp_path: Path) -> Path:
    data = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    data["metadata"]["purpose"] = (
        str(data["metadata"]["purpose"]) + " Candidate task revision."
    )
    candidate = tmp_path / "candidate.yaml"
    candidate.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    return candidate


def _prediction():
    return freeze_prediction(
        model_path=EXAMPLE,
        prediction_id="prediction-1",
        frozen_at="2026-07-17T10:00:00+00:00",
        target_kind="storyline",
        target_id="trace_metadata_incident",
        prediction_kind="evidence_footprint",
        expected_evidence_ids=["ev_pr_fix"],
        expected_event_ids=["event_mitigation"],
        expected_event_order=["event_mitigation"],
        weakens_when="The mitigation evidence or event is absent.",
    )


def _observation(*, include_holdout: bool = True, observed_at: str | None = None):
    evidence = ["ev_pr_fix"]
    if include_holdout:
        evidence.append("ev_meeting_boundary")
    return EvidenceBatchObservation.from_dict(
        {
            "schema_version": "researchguard.trace.evidence_batch_observation.v1",
            "observation_id": "observation-1",
            "observed_at": observed_at or "2026-07-17T11:00:00+00:00",
            "quality_status": "valid",
            "evidence_ids": evidence,
            "event_ids": ["event_mitigation"],
            "event_order": ["event_mitigation"],
            "contradiction_ids": [],
            "source_refs": ["source:pr", "source:meeting"],
            "future_holdout_status": "not_run",
            "future_holdout_validator_receipt": "",
        }
    )


def _comparison_file(tmp_path: Path, observation: EvidenceBatchObservation) -> Path:
    payload = compare_prediction_observation(_prediction(), observation)
    path = tmp_path / "comparison.json"
    write_artifact(path, payload)
    return path


def test_freeze_requires_an_expectation() -> None:
    with pytest.raises(TaskIterationError, match="requires expected"):
        freeze_prediction(
            model_path=EXAMPLE,
            prediction_id="prediction-empty",
            frozen_at="2026-07-17T10:00:00+00:00",
            target_kind="storyline",
            target_id="trace_metadata_incident",
            prediction_kind="evidence_footprint",
            weakens_when="Nothing was declared.",
        )


def test_observation_must_follow_prediction() -> None:
    with pytest.raises(TaskIterationError, match="must be later"):
        compare_prediction_observation(
            _prediction(),
            _observation(observed_at="2026-07-17T09:59:59+00:00"),
        )


def test_comparison_records_missing_expected_evidence_and_order() -> None:
    observation = EvidenceBatchObservation.from_dict(
        {
            "schema_version": "researchguard.trace.evidence_batch_observation.v1",
            "observation_id": "observation-mismatch",
            "observed_at": "2026-07-17T11:00:00+00:00",
            "quality_status": "valid",
            "evidence_ids": [],
            "event_ids": ["event_mitigation", "event_boundary"],
            "event_order": ["event_boundary", "event_mitigation"],
            "contradiction_ids": ["contradiction-1"],
            "source_refs": ["source:later-batch"],
            "future_holdout_status": "not_run",
            "future_holdout_validator_receipt": "",
        }
    )
    payload = compare_prediction_observation(_prediction(), observation)
    kinds = {item["mismatch_type"] for item in payload["mismatches"]}
    assert "expected_evidence_missing" in kinds
    assert "unexpected_contradiction" in kinds
    assert payload["factual_future_prediction_licensed"] is False


def test_future_event_requires_separate_holdout_validator() -> None:
    prediction = freeze_prediction(
        model_path=EXAMPLE,
        prediction_id="prediction-future",
        frozen_at="2026-07-17T10:00:00+00:00",
        target_kind="storyline",
        target_id="trace_metadata_incident",
        prediction_kind="future_event",
        expected_event_ids=["event_mitigation"],
        weakens_when="The future event is absent.",
    )
    payload = compare_prediction_observation(prediction, _observation())
    assert "future_holdout_validator_missing" in {
        item["mismatch_type"] for item in payload["mismatches"]
    }
    assert payload["factual_future_prediction_licensed"] is False


def test_candidate_accepts_only_with_current_holdout(tmp_path: Path) -> None:
    observation = _observation()
    comparison = load_comparison(_comparison_file(tmp_path, observation))
    revision = decide_candidate_revision(
        comparison=comparison,
        candidate_model_path=_candidate_model(tmp_path),
        observation=observation,
        required_holdout_evidence_ids=["ev_meeting_boundary"],
    )
    assert revision["disposition"] == "accepted"
    assert (
        revision["effective_model_sha256"]
        == revision["candidate_model_sha256"]
    )
    assert revision["candidate_inference_receipt_id"].startswith(
        "traceguard-inference-"
    )
    assert revision["factual_future_prediction_licensed"] is False


def test_candidate_rejects_and_retains_baseline_when_holdout_missing(
    tmp_path: Path,
) -> None:
    observation = _observation(include_holdout=False)
    comparison = load_comparison(_comparison_file(tmp_path, observation))
    revision = decide_candidate_revision(
        comparison=comparison,
        candidate_model_path=_candidate_model(tmp_path),
        observation=observation,
        required_holdout_evidence_ids=["ev_meeting_boundary"],
    )
    assert revision["disposition"] == "rejected"
    assert revision["missing_holdout_evidence_ids"] == ["ev_meeting_boundary"]
    assert (
        revision["effective_model_sha256"]
        == revision["baseline_model_sha256"]
    )


def test_explicit_rollback_retains_baseline(tmp_path: Path) -> None:
    observation = _observation()
    comparison = load_comparison(_comparison_file(tmp_path, observation))
    revision = decide_candidate_revision(
        comparison=comparison,
        candidate_model_path=_candidate_model(tmp_path),
        observation=observation,
        required_holdout_evidence_ids=["ev_meeting_boundary"],
        force_rollback=True,
    )
    assert revision["disposition"] == "rolled_back"
    assert (
        revision["effective_model_sha256"]
        == revision["baseline_model_sha256"]
    )


def test_candidate_cannot_reuse_baseline_path(tmp_path: Path) -> None:
    observation = _observation()
    comparison = load_comparison(_comparison_file(tmp_path, observation))
    with pytest.raises(TaskIterationError, match="path must differ"):
        decide_candidate_revision(
            comparison=comparison,
            candidate_model_path=EXAMPLE,
            observation=observation,
            required_holdout_evidence_ids=["ev_meeting_boundary"],
        )


def test_candidate_decision_rejects_tampered_comparison(tmp_path: Path) -> None:
    observation = _observation()
    comparison = load_comparison(_comparison_file(tmp_path, observation))
    comparison["baseline_model_sha256"] = "0" * 64

    with pytest.raises(TaskIterationError, match="fingerprint mismatch"):
        decide_candidate_revision(
            comparison=comparison,
            candidate_model_path=_candidate_model(tmp_path),
            observation=observation,
            required_holdout_evidence_ids=["ev_meeting_boundary"],
        )


def test_candidate_decision_requires_compared_observation(tmp_path: Path) -> None:
    observation = _observation()
    comparison = load_comparison(_comparison_file(tmp_path, observation))
    different_observation = EvidenceBatchObservation.from_dict(
        {
            **observation.to_dict(),
            "observation_id": "observation-different",
            "observation_fingerprint": "",
        }
    )

    with pytest.raises(TaskIterationError, match="does not match"):
        decide_candidate_revision(
            comparison=comparison,
            candidate_model_path=_candidate_model(tmp_path),
            observation=different_observation,
            required_holdout_evidence_ids=["ev_meeting_boundary"],
        )


def test_lifecycle_artifacts_are_not_overwritten(tmp_path: Path) -> None:
    target = tmp_path / "prediction.json"
    write_artifact(target, _prediction().to_dict())
    with pytest.raises(TaskIterationError, match="refusing to overwrite"):
        write_artifact(target, _prediction().to_dict())


def test_cli_runs_freeze_compare_and_decide(tmp_path: Path) -> None:
    prediction_path = tmp_path / "prediction.json"
    comparison_path = tmp_path / "comparison.json"
    revision_path = tmp_path / "revision.json"
    observation_path = tmp_path / "observation.json"
    observation_path.write_text(
        json.dumps(_observation().to_dict(), indent=2),
        encoding="utf-8",
    )
    candidate_path = _candidate_model(tmp_path)

    assert (
        main(
            [
                "iterate",
                "freeze",
                "--model",
                str(EXAMPLE),
                "--prediction-id",
                "prediction-cli",
                "--frozen-at",
                "2026-07-17T10:00:00+00:00",
                "--target-kind",
                "storyline",
                "--target-id",
                "trace_metadata_incident",
                "--expected-evidence",
                "ev_pr_fix",
                "--expected-event",
                "event_mitigation",
                "--weakens-when",
                "The expected mitigation is absent.",
                "--output",
                str(prediction_path),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "iterate",
                "compare",
                "--prediction",
                str(prediction_path),
                "--observation",
                str(observation_path),
                "--output",
                str(comparison_path),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "iterate",
                "decide",
                "--comparison",
                str(comparison_path),
                "--observation",
                str(observation_path),
                "--candidate",
                str(candidate_path),
                "--required-holdout-evidence",
                "ev_meeting_boundary",
                "--output",
                str(revision_path),
            ]
        )
        == 0
    )
    assert json.loads(revision_path.read_text(encoding="utf-8"))["disposition"] == "accepted"
