from __future__ import annotations

import json
import socket

import pytest

from researchguard.logic.file_model_store import FileModelStore, TestInjectedStoreFault
from researchguard.logic.model_store import RecoveryRequiredError
from researchguard.logic.provenance import content_hash_for
from researchguard.logic.schema import JOURNAL_SCHEMA, SCHEMA_VERSION


def model_payload(text: str = "Conclusion") -> dict:
    return {
        "model": {
            "id": "model-alpha",
            "title": "Alpha",
            "root_claim": "claim-root",
            "schema_version": SCHEMA_VERSION,
        },
        "nodes": {
            "claim-root": {"type": "Claim", "text": text},
            "evidence-one": {
                "type": "Evidence",
                "text": "Observed",
                "provenance": [
                    {
                        "origin_kind": "test_result",
                        "source_id": "test-suite-alpha",
                        "content_hash": content_hash_for("observed"),
                    }
                ],
            },
        },
        "edges": [
            {
                "id": "edge-evidence-root",
                "source": "evidence-one",
                "target": "claim-root",
                "type": "supports",
            }
        ],
        "acceptance": {},
        "hierarchy": {},
        "blocks": {
            "block-alpha": {
                "id": "block-alpha",
                "title": "Alpha",
                "root_claim": "claim-root",
                "member_nodes": ["claim-root", "evidence-one"],
                "input_nodes": ["evidence-one"],
                "output_claims": ["claim-root"],
            }
        },
    }


class CrashAt:
    def __init__(self, point: str) -> None:
        self.point = point

    def __call__(self, point: str) -> None:
        if point == self.point:
            raise TestInjectedStoreFault(point)


def stage_with_fault(root, point: str, *, expected=None, text: str = "Conclusion"):
    store = FileModelStore(root, _test_fault_hook=CrashAt(point))
    transaction = store.begin("model-alpha", expected, f"fault-{point}", "test-actor")
    transaction.stage(model_payload(text))
    with pytest.raises(TestInjectedStoreFault, match=point):
        transaction.commit()
    return transaction


def test_crash_after_lock_creates_no_authority_or_recovery_work(tmp_path) -> None:
    root = tmp_path / "store"
    stage_with_fault(root, "after_lock")
    clean = FileModelStore(root)
    assert clean.head("model-alpha") is None
    assert clean.recover() == ()


@pytest.mark.parametrize("point", ["after_journal", "after_revision", "after_receipt"])
def test_crash_before_manifest_keeps_prior_head_and_recovery_aborts_orphan(
    tmp_path, point: str
) -> None:
    root = tmp_path / "store"
    base_store = FileModelStore(root)
    base_tx = base_store.begin("model-alpha", None, "base", "test-actor")
    base_tx.stage(model_payload("Base"))
    base = base_tx.commit()

    crashed = stage_with_fault(root, point, expected=base.revision, text="Candidate")
    clean = FileModelStore(root)
    assert clean.head("model-alpha") == base.revision
    assert crashed.staged_snapshot.revision not in clean.list_revisions("model-alpha")

    recoveries = clean.recover()
    assert len(recoveries) == 1
    assert recoveries[0].action == "abort_orphan"
    assert recoveries[0].revision == crashed.staged_snapshot.revision
    assert clean.head("model-alpha") == base.revision
    journals = [json.loads(path.read_text(encoding="utf-8")) for path in (root / "journals").glob("*.json")]
    candidate = next(item for item in journals if item["transaction_id"] == str(crashed.transaction_id))
    assert candidate["status"] == "aborted"


def test_crash_after_manifest_is_finalized_without_changing_new_head(tmp_path) -> None:
    root = tmp_path / "store"
    crashed = stage_with_fault(root, "after_manifest")
    clean = FileModelStore(root)
    assert clean.head("model-alpha") == crashed.staged_snapshot.revision
    assert clean.get("model-alpha").revision == crashed.staged_snapshot.revision

    recoveries = clean.recover()
    assert len(recoveries) == 1
    assert recoveries[0].action == "finalize_committed_journal"
    assert clean.head("model-alpha") == crashed.staged_snapshot.revision


def test_crash_after_terminal_journal_needs_no_recovery_and_retry_is_stable(tmp_path) -> None:
    root = tmp_path / "store"
    crashed = stage_with_fault(root, "after_terminal_journal")
    clean = FileModelStore(root)
    assert clean.head("model-alpha") == crashed.staged_snapshot.revision
    assert clean.recover() == ()

    retry = clean.begin("model-alpha", None, "fault-after_terminal_journal", "test-actor")
    retry.stage(model_payload())
    receipt = retry.commit()
    assert receipt.revision == crashed.staged_snapshot.revision
    assert len(clean.list_revisions("model-alpha")) == 1


def test_prepared_journal_blocks_same_idempotency_until_recovery(tmp_path) -> None:
    root = tmp_path / "store"
    stage_with_fault(root, "after_journal")
    clean = FileModelStore(root)
    retry = clean.begin("model-alpha", None, "fault-after_journal", "test-actor")
    retry.stage(model_payload())
    with pytest.raises(RecoveryRequiredError, match="incomplete journal"):
        retry.commit()
    clean.recover()
    receipt = retry.commit()
    assert clean.head("model-alpha") == receipt.revision


def test_explicit_recovery_removes_only_non_live_stale_lock_and_receipts_it(tmp_path) -> None:
    root = tmp_path / "store"
    store = FileModelStore(root)
    lock_path = root / "locks" / "writer.lock"
    lock_path.write_text(
        json.dumps(
            {
                "artifact_schema": JOURNAL_SCHEMA,
                "store_schema_version": SCHEMA_VERSION,
                "lock_type": "writer",
                "pid": 0,
                "host": socket.gethostname(),
                "transaction_id": "txn-dead-owner",
                "created_at": "2026-07-14T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    transaction = store.begin("model-alpha", None, "blocked-by-stale", "test-actor")
    transaction.stage(model_payload())
    with pytest.raises(RecoveryRequiredError, match="explicit recover"):
        transaction.commit()

    receipts = store.recover()
    assert len(receipts) == 1
    assert receipts[0].action == "remove_stale_lock"
    assert not lock_path.exists()
    assert list((root / "receipts" / "recovery").glob("*.json"))
