from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from researchguard.logic.file_model_store import FileModelStore
from researchguard.logic.loader import load_model_from_dict
from researchguard.logic.task_iteration import (
    ArgumentPrediction,
    freeze_argument_prediction,
    rollback_argument_revision,
    run_argument_iteration,
    validate_prediction_binding,
)


ROOT = Path(__file__).resolve().parents[2]


class _ConflictTransaction:
    def __init__(self, store, transaction) -> None:
        self._store = store
        self._transaction = transaction

    @property
    def staged_snapshot(self):
        return self._transaction.staged_snapshot

    def stage(self, model):
        return self._transaction.stage(model)

    def commit(self):
        competing = super(_ConflictStore, self._store).begin(
            self._transaction.model_id,
            self._transaction.expected_revision,
            "competing-candidate",
            "competing-writer",
        )
        competing.stage(self._transaction.staged_snapshot.authoring_payload())
        competing.commit()
        return self._transaction.commit()

    def abort(self, reason):
        return self._transaction.abort(reason)


class _ConflictStore(FileModelStore):
    def begin(self, model_id, expected_revision, idempotency_key, actor):
        transaction = super().begin(
            model_id, expected_revision, idempotency_key, actor
        )
        if expected_revision is not None and idempotency_key != "competing-candidate":
            return _ConflictTransaction(self, transaction)
        return transaction
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
                "C0": {
                    "type": "Claim",
                    "text": "Target claim",
                    "scope": "tested case",
                    "confidence": 1.0,
                },
                "C1": {
                    "type": "Claim",
                    "text": "Protected claim",
                    "scope": "tested case",
                    "confidence": 1.0,
                },
                "P0": {"type": "Premise", "text": "Target premise", "confidence": 1.0},
                "P1": {"type": "Premise", "text": "Protected premise", "confidence": 1.0},
                "A1": {"type": "Assumption", "text": "Target assumption", "confidence": 1.0},
            },
            "edges": [
                {
                    "id": "edge-p0-c0",
                    "source": "P0",
                    "target": "C0",
                    "type": "supports",
                },
                {
                    "id": "edge-a1-c0",
                    "source": "A1",
                    "target": "C0",
                    "type": "depends_on",
                },
                {
                    "id": "edge-p1-c1",
                    "source": "P1",
                    "target": "C1",
                    "type": "supports",
                },
            ],
            "acceptance": {
                "C0": {
                    "all_of": ["P0"],
                    "requires_not_out": ["A1"],
                    "threshold": 0.5,
                },
                "C1": {"all_of": ["P1"], "threshold": 0.5},
            },
            "hierarchy": {},
            "blocks": {},
        }
    )
    candidate = copy.deepcopy(baseline)
    candidate.acceptance["C0"].pop("requires_not_out")
    return baseline, candidate


def _prediction(baseline, *, protected=("C1",)):
    return freeze_argument_prediction(
        baseline,
        expected_state="IN",
        mode="assumption-flip",
        root_claim="C0",
        node_id="A1",
        protected_claim_ids=protected,
        prediction_id="prediction-task-local",
    )


def test_freeze_binds_prediction_without_simulation_output() -> None:
    baseline, _ = _baseline_and_candidate()
    prediction = _prediction(baseline)

    assert prediction.model_id == baseline.id
    assert prediction.baseline_digest.startswith("sha256:")
    assert prediction.expected_state == "IN"
    assert prediction.protected_claim_ids == ("C1",)
    assert "observed_state" not in prediction.to_dict()


def test_stale_baseline_binding_is_rejected() -> None:
    baseline, _ = _baseline_and_candidate()
    prediction = _prediction(baseline)
    baseline.nodes["C0"].text = "Changed after prediction freeze."

    with pytest.raises(ValueError, match="stale argument prediction"):
        validate_prediction_binding(baseline, prediction)


def test_matching_baseline_needs_no_revision(tmp_path: Path) -> None:
    baseline, _ = _baseline_and_candidate()
    prediction = freeze_argument_prediction(
        baseline,
        expected_state="OUT",
        mode="assumption-flip",
        root_claim="C0",
        node_id="A1",
        prediction_id="prediction-no-revision",
    )
    store = FileModelStore(tmp_path / "store")

    receipt = run_argument_iteration(store, baseline, prediction, decision="accept")

    assert receipt.baseline_comparison.matches
    assert receipt.effective_disposition == "no_revision_needed"
    assert len(store.list_revisions(baseline.id)) == 1


def test_candidate_is_accepted_as_immutable_child_and_can_be_rolled_back(
    tmp_path: Path,
) -> None:
    baseline, candidate = _baseline_and_candidate()
    prediction = _prediction(baseline)
    store = FileModelStore(tmp_path / "store")

    receipt = run_argument_iteration(
        store,
        baseline,
        prediction,
        candidate=candidate,
        decision="accept",
        idempotency_key="candidate-accept",
    )

    assert not receipt.baseline_comparison.matches
    assert receipt.candidate_comparison is not None
    assert receipt.candidate_comparison.matches
    assert all(item.passed for item in receipt.protected_claims)
    assert receipt.effective_disposition == "accepted"
    assert len(store.list_revisions(baseline.id)) == 2
    accepted_head = store.head(baseline.id)
    assert str(accepted_head) == receipt.candidate_revision

    rollback = rollback_argument_revision(
        store,
        model_id=baseline.id,
        source_revision=receipt.baseline_revision,
        idempotency_key="candidate-rollback",
    )

    assert rollback.prior_head_revision == str(accepted_head)
    assert rollback.compensating_revision != receipt.baseline_revision
    assert store.get(baseline.id).content_digest == prediction.baseline_digest
    assert len(store.list_revisions(baseline.id)) == 3


def test_explicit_reject_preserves_baseline_head(tmp_path: Path) -> None:
    baseline, candidate = _baseline_and_candidate()
    prediction = _prediction(baseline)
    store = FileModelStore(tmp_path / "store")

    receipt = run_argument_iteration(
        store,
        baseline,
        prediction,
        candidate=candidate,
        decision="reject",
        idempotency_key="candidate-reject",
    )

    assert receipt.effective_disposition == "rejected"
    assert store.head(baseline.id) == store.list_revisions(baseline.id)[0]
    assert len(store.list_revisions(baseline.id)) == 1


def test_protected_claim_change_blocks_requested_accept(tmp_path: Path) -> None:
    baseline, candidate = _baseline_and_candidate()
    candidate.nodes["P1"].confidence = 0.0
    prediction = _prediction(baseline, protected=("C1",))
    store = FileModelStore(tmp_path / "store")

    receipt = run_argument_iteration(
        store,
        baseline,
        prediction,
        candidate=candidate,
        decision="accept",
        idempotency_key="candidate-protected-fail",
    )

    assert receipt.candidate_comparison is not None
    assert receipt.candidate_comparison.matches
    assert receipt.protected_claims[0].status == "fail"
    assert receipt.effective_disposition == "rejected"
    assert len(store.list_revisions(baseline.id)) == 1


def test_concurrent_head_change_is_reported_without_candidate_commit(
    tmp_path: Path,
) -> None:
    baseline, candidate = _baseline_and_candidate()
    prediction = _prediction(baseline)
    store = _ConflictStore(tmp_path / "store")

    receipt = run_argument_iteration(
        store,
        baseline,
        prediction,
        candidate=candidate,
        decision="accept",
        idempotency_key="candidate-conflict",
    )

    assert receipt.effective_disposition == "conflict"
    assert receipt.store_receipt is not None
    assert receipt.store_receipt["conflict_kind"] == "compare_and_swap"
    assert len(store.list_revisions(baseline.id)) == 2


def test_cli_freeze_run_and_rollback(tmp_path: Path) -> None:
    baseline, candidate = _baseline_and_candidate()
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    baseline_path.write_text(json.dumps(baseline.to_dict()), encoding="utf-8")
    candidate_path.write_text(json.dumps(candidate.to_dict()), encoding="utf-8")
    prediction_path = tmp_path / "prediction.json"
    run_receipt_path = tmp_path / "run-receipt.json"
    rollback_receipt_path = tmp_path / "rollback-receipt.json"
    store_root = tmp_path / "store"

    frozen = subprocess.run(
        [
            sys.executable,
            "-m",
            "researchguard", "logic",
            "argument-iteration",
            "freeze",
            str(baseline_path),
            "--expected-state",
            "IN",
            "--mode",
            "assumption-flip",
            "--root",
            "C0",
            "--node",
            "A1",
            "--protect-claim",
            "C1",
            "--prediction-id",
            "prediction-cli",
            "--output",
            str(prediction_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert frozen.returncode == 0, frozen.stderr or frozen.stdout
    prediction = ArgumentPrediction.from_dict(
        json.loads(prediction_path.read_text(encoding="utf-8"))
    )
    assert prediction.expected_state == "IN"

    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "researchguard", "logic",
            "argument-iteration",
            "run",
            str(baseline_path),
            "--prediction",
            str(prediction_path),
            "--candidate",
            str(candidate_path),
            "--store-root",
            str(store_root),
            "--decision",
            "accept",
            "--idempotency-key",
            "candidate-cli",
            "--output",
            str(run_receipt_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr or run.stdout
    run_receipt = json.loads(run_receipt_path.read_text(encoding="utf-8"))
    assert run_receipt["effective_disposition"] == "accepted"

    rollback = subprocess.run(
        [
            sys.executable,
            "-m",
            "researchguard", "logic",
            "argument-iteration",
            "rollback",
            "--store-root",
            str(store_root),
            "--model-id",
            baseline.id,
            "--source-revision",
            run_receipt["baseline_revision"],
            "--idempotency-key",
            "rollback-cli",
            "--output",
            str(rollback_receipt_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert rollback.returncode == 0, rollback.stderr or rollback.stdout
    assert json.loads(rollback_receipt_path.read_text(encoding="utf-8"))[
        "schema_version"
    ] == "researchguard.logic.argument-rollback-receipt.v1"
