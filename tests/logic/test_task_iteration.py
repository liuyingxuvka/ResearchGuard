from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

import researchguard.logic.task_iteration as task_iteration_module
from researchguard.logic.file_model_store import FileModelStore
from researchguard.logic.loader import load_model_from_dict
from researchguard.logic.execution_depth import model_fingerprint
from researchguard.logic.task_iteration import (
    ArgumentPrediction,
    freeze_argument_prediction,
    rollback_argument_revision,
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
    digest = model_fingerprint(model)
    return {
        "receipt_version": "researchguard.logic.depth.v3",
        "model_fingerprint": digest,
        "status": "pass",
        "unresolved_gaps": [],
    }, ()


def test_current_prediction_requires_task_coverage_and_holdout() -> None:
    baseline, _ = _baseline_and_candidate()
    with pytest.raises(TypeError):
        freeze_argument_prediction(
            baseline,
            expected_state="IN",
            mode="assumption-flip",
            root_claim="C0",
            node_id="A1",
        )
    prediction = _prediction(baseline)
    assert prediction.coverage_fingerprint.startswith("sha256:")
    assert prediction.holdout_claim_ids == ("C2",)


def test_loaded_prediction_rejects_implicit_or_rebound_task_scope() -> None:
    baseline, _ = _baseline_and_candidate()
    raw = _prediction(baseline).to_dict()
    raw.pop("assumptions")
    with pytest.raises(ValueError, match="missing task fields"):
        ArgumentPrediction.from_dict(raw)
    raw = _prediction(baseline).to_dict()
    raw["coverage_ids"] = ["C0"]
    with pytest.raises(ValueError, match="does not bind"):
        ArgumentPrediction.from_dict(raw)


def test_stale_baseline_binding_is_rejected() -> None:
    baseline, _ = _baseline_and_candidate()
    prediction = _prediction(baseline)
    baseline.nodes["C0"].text = "Changed after freeze"
    with pytest.raises(ValueError, match="stale argument prediction"):
        validate_prediction_binding(baseline, prediction)


def test_real_native_depth_gaps_override_matching_local_prediction(tmp_path: Path) -> None:
    baseline, _ = _baseline_and_candidate()
    prediction = _prediction(baseline, expected_state="OUT")
    receipt = run_argument_iteration(
        FileModelStore(tmp_path / "store"), baseline, prediction, decision="accept"
    )
    assert receipt.terminal_reason != "model_closed_for_task"
    assert receipt.native_depth_receipt_id
    assert receipt.open_gap_ids


def test_candidate_acceptance_binds_native_receipt_and_independent_holdout(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(task_iteration_module, "_native_depth", _native_pass)
    baseline, candidate = _baseline_and_candidate()
    receipt = run_argument_iteration(
        FileModelStore(tmp_path / "store"),
        baseline,
        _prediction(baseline),
        candidate=candidate,
        decision="accept",
    )
    assert receipt.effective_disposition == "accepted"
    assert receipt.terminal_reason == "model_closed_for_task"
    assert all(item.passed for item in receipt.holdout_claims)
    assert receipt.receipt_fingerprint.startswith("sha256:")


def test_holdout_regression_blocks_candidate_even_when_target_matches(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(task_iteration_module, "_native_depth", _native_pass)
    baseline, candidate = _baseline_and_candidate()
    candidate.nodes["P2"].confidence = 0.0
    receipt = run_argument_iteration(
        FileModelStore(tmp_path / "store"),
        baseline,
        _prediction(baseline),
        candidate=candidate,
        decision="accept",
    )
    assert "independent-holdout-regression" in receipt.open_gap_ids
    assert receipt.terminal_reason != "model_closed_for_task"


def test_unchanged_gap_set_is_progress_stalled(tmp_path: Path) -> None:
    baseline, _ = _baseline_and_candidate()
    first = run_argument_iteration(
        FileModelStore(tmp_path / "first"), baseline, _prediction(baseline, expected_state="OUT"), decision="accept"
    )
    second_prediction = _prediction(
        baseline,
        expected_state="OUT",
        iteration=1,
        prior_receipt_fingerprint=first.receipt_fingerprint,
        prior_open_gap_ids=first.open_gap_ids,
    )
    second = run_argument_iteration(
        FileModelStore(tmp_path / "second"), baseline, second_prediction, decision="accept"
    )
    assert second.terminal_reason == "progress_stalled"
    assert second.persisted_gap_ids == first.open_gap_ids


def test_accepted_revision_can_be_rolled_back(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(task_iteration_module, "_native_depth", _native_pass)
    baseline, candidate = _baseline_and_candidate()
    store = FileModelStore(tmp_path / "store")
    accepted = run_argument_iteration(
        store, baseline, _prediction(baseline), candidate=candidate, decision="accept"
    )
    rollback = rollback_argument_revision(
        store,
        model_id=baseline.id,
        source_revision=accepted.baseline_revision,
    )
    assert rollback.compensating_revision != accepted.baseline_revision
    assert store.get(baseline.id).content_digest == _prediction(baseline).baseline_digest


def test_cli_freeze_emits_only_current_strict_prediction(tmp_path: Path) -> None:
    baseline, _ = _baseline_and_candidate()
    baseline_path = tmp_path / "baseline.json"
    output = tmp_path / "prediction.json"
    baseline_path.write_text(json.dumps(baseline.to_dict()), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable, "-m", "researchguard", "logic", "argument-iteration", "freeze",
            str(baseline_path), "--expected-state", "IN", "--mode", "assumption-flip",
            "--root", "C0", "--node", "A1", "--protect-claim", "C1",
            "--holdout-claim", "C2", "--task-id", "argument-task-cli",
            "--purpose", "exercise strict CLI", "--coverage-id", "C0",
            "--coverage-id", "C1", "--coverage-id", "C2", "--iteration", "0",
            "--max-iterations", "4", "--prediction-id", "prediction-cli",
            "--output", str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "researchguard.logic.argument-prediction.v2"
    assert "prior_gap_fingerprints" not in payload
