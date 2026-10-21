from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

import researchguard.logic.task_iteration as task_iteration_module
from researchguard.logic.loader import load_model_from_dict
from researchguard.logic.task_iteration import (
    ArgumentPrediction,
    freeze_argument_prediction,
    run_argument_iteration,
    validate_prediction_binding,
)


ROOT = Path(__file__).resolve().parents[2]


def _baseline_and_candidate():
    baseline = load_model_from_dict(
        {
            "model": {
                "id": "task-model",
                "title": "Task-local model",
                "root_claim": "C0",
                "schema_version": "researchguard.logic.model-store.v1",
            },
            "nodes": {
                "C0": {"type": "Claim", "text": "Target claim", "scope": "case", "confidence": 1.0},
                "C1": {"type": "Claim", "text": "Protected claim", "scope": "case", "confidence": 1.0},
                "C2": {"type": "Claim", "text": "Holdout claim", "scope": "case", "confidence": 1.0},
                "P0": {"type": "Premise", "text": "Target premise", "confidence": 1.0},
                "P1": {"type": "Premise", "text": "Protected premise", "confidence": 1.0},
                "P2": {"type": "Premise", "text": "Holdout premise", "confidence": 1.0},
                "A1": {"type": "Assumption", "text": "Target assumption", "confidence": 1.0},
            },
            "edges": [
                {"id": "e0", "source": "P0", "target": "C0", "type": "supports"},
                {"id": "e1", "source": "A1", "target": "C0", "type": "depends_on"},
                {"id": "e2", "source": "P1", "target": "C1", "type": "supports"},
                {"id": "e3", "source": "P2", "target": "C2", "type": "supports"},
            ],
            "acceptance": {
                "C0": {"all_of": ["P0"], "requires_not_out": ["A1"], "threshold": 0.5},
                "C1": {"all_of": ["P1"], "threshold": 0.5},
                "C2": {"all_of": ["P2"], "threshold": 0.5},
            },
            "hierarchy": {},
            "blocks": {},
        }
    )
    candidate = copy.deepcopy(baseline)
    candidate.acceptance["C0"].pop("requires_not_out")
    return baseline, candidate


def _prediction(baseline, **overrides):
    values = {
        "expected_state": "IN",
        "mode": "assumption-flip",
        "root_claim": "C0",
        "node_id": "A1",
        "protected_claim_ids": ("C1",),
        "holdout_claim_ids": ("C2",),
        "prediction_id": "prediction-task-local",
        "task_id": "argument-task-1",
        "purpose": "repair the target claim without regressing protected claims",
        "coverage_ids": ("C0", "C1", "C2"),
        "assumptions": (),
        "unknowns": (),
        "iteration": 0,
        "max_iterations": 4,
    }
    values.update(overrides)
    return freeze_argument_prediction(baseline, **values)


def _native_pass(model, prediction):
    return ()


def test_prediction_needs_only_claim_mode_and_target() -> None:
    baseline, _ = _baseline_and_candidate()
    prediction = freeze_argument_prediction(
        baseline, expected_state="IN", mode="assumption-flip", root_claim="C0", node_id="A1",
    )
    assert prediction.holdout_claim_ids == ()
    assert prediction.iteration == 0
    assert "coverage_fingerprint" not in prediction.to_dict()
    with pytest.raises(ValueError, match="missing or not a Claim"):
        _prediction(baseline, holdout_claim_ids=("P2",))
    with pytest.raises(ValueError, match="coverage nodes are missing from the model: X9"):
        _prediction(baseline, coverage_ids=("C0", "X9"))


def test_loaded_prediction_accepts_missing_optional_task_fields() -> None:
    baseline, _ = _baseline_and_candidate()
    raw = _prediction(baseline).to_dict()
    for key in ("task_id", "purpose", "coverage_ids", "assumptions", "unknowns", "holdout_claim_ids"):
        raw.pop(key)
    loaded = ArgumentPrediction.from_dict(raw)
    assert loaded.coverage_ids == ()
    assert loaded.baseline_digest == raw["baseline_digest"]


def test_stale_baseline_binding_is_rejected() -> None:
    baseline, _ = _baseline_and_candidate()
    prediction = _prediction(baseline)
    baseline.nodes["C0"].text = "Changed after freeze"
    with pytest.raises(ValueError, match="stale argument prediction"):
        validate_prediction_binding(baseline, prediction)


def test_real_native_depth_gaps_override_matching_local_prediction() -> None:
    baseline, _ = _baseline_and_candidate()
    prediction = _prediction(baseline, expected_state="OUT")
    result = run_argument_iteration(
        baseline, prediction, decision="accept"
    )
    assert result.terminal_reason != "model_closed_for_task"
    assert result.open_gap_ids


def test_candidate_acceptance_checks_protected_and_holdout_claims(monkeypatch) -> None:
    monkeypatch.setattr(task_iteration_module, "_native_depth", _native_pass)
    baseline, candidate = _baseline_and_candidate()
    result = run_argument_iteration(
        baseline,
        _prediction(baseline),
        candidate=candidate,
        decision="accept",
    )
    assert result.effective_disposition == "accepted"
    assert result.terminal_reason == "model_closed_for_task"
    assert all(item.passed for item in result.holdout_claims)
    assert "receipt_fingerprint" not in result.to_dict()


def test_holdout_regression_blocks_candidate_even_when_target_matches(monkeypatch) -> None:
    monkeypatch.setattr(task_iteration_module, "_native_depth", _native_pass)
    baseline, candidate = _baseline_and_candidate()
    candidate.nodes["P2"].confidence = 0.0
    result = run_argument_iteration(
        baseline,
        _prediction(baseline),
        candidate=candidate,
        decision="accept",
    )
    assert "independent-holdout-regression" in result.open_gap_ids
    assert result.terminal_reason != "model_closed_for_task"


def test_unchanged_gap_set_is_progress_stalled() -> None:
    baseline, _ = _baseline_and_candidate()
    first = run_argument_iteration(
        baseline, _prediction(baseline, expected_state="OUT"), decision="accept"
    )
    second_prediction = _prediction(
        baseline,
        expected_state="OUT",
        iteration=1,
        prior_open_gap_ids=first.open_gap_ids,
    )
    second = run_argument_iteration(
        baseline, second_prediction, decision="accept"
    )
    assert second.terminal_reason == "progress_stalled"
    assert second.persisted_gap_ids == first.open_gap_ids


def test_cli_freeze_and_run_leave_the_model_files_untouched(tmp_path: Path) -> None:
    baseline, candidate = _baseline_and_candidate()
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    prediction_path = tmp_path / "prediction.json"
    result_path = tmp_path / "result.json"
    baseline_path.write_text(json.dumps(baseline.to_dict()), encoding="utf-8")
    candidate_path.write_text(json.dumps(candidate.to_dict()), encoding="utf-8")
    before = (baseline_path.read_bytes(), candidate_path.read_bytes())

    def cli(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "researchguard", "logic", "argument-iteration", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    frozen = cli(
        "freeze", str(baseline_path), "--expected-state", "IN", "--mode", "assumption-flip",
        "--root", "C0", "--node", "A1", "--protect-claim", "C1", "--holdout-claim", "C2",
        "--output", str(prediction_path),
    )
    assert frozen.returncode == 0, frozen.stderr
    payload = json.loads(prediction_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "researchguard.logic.argument-prediction.v2"
    assert "coverage_fingerprint" not in payload
    ran = cli(
        "run", str(baseline_path), "--prediction", str(prediction_path),
        "--candidate", str(candidate_path), "--decision", "accept", "--output", str(result_path),
    )
    assert ran.returncode == 0, ran.stderr
    outcome = json.loads(result_path.read_text(encoding="utf-8"))
    assert outcome["schema_version"] == "researchguard.logic.argument-iteration-result.v1"
    assert outcome["effective_disposition"] in {"accepted", "continue_iteration"}
    assert (baseline_path.read_bytes(), candidate_path.read_bytes()) == before
