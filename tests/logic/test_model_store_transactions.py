from __future__ import annotations

import json
import os
import socket
import threading

import pytest

from researchguard.logic.file_model_store import FileModelStore
from researchguard.logic.identity import ModelId
from researchguard.logic.model_store import (
    IdempotencyConflictError,
    TransactionConflictError,
    WriterLockHeldError,
)
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


def commit(
    store: FileModelStore,
    payload: dict,
    *,
    expected=None,
    key: str = "commit-alpha",
):
    transaction = store.begin("model-alpha", expected, key, "test-actor")
    transaction.stage(payload)
    return transaction.commit()


def test_first_commit_publishes_one_authorized_immutable_revision(tmp_path) -> None:
    store = FileModelStore(tmp_path / "store")
    receipt = commit(store, model_payload())

    assert store.head("model-alpha") == receipt.revision
    assert store.list_models() == (ModelId("model-alpha"),)
    assert store.list_revisions("model-alpha") == (receipt.revision,)

    first_read = store.get("model-alpha")
    detached = first_read.to_model()
    detached.nodes["claim-root"].text = "caller mutation"
    second_read = store.get("model-alpha")
    assert second_read.to_model().nodes["claim-root"].text == "Conclusion"


def test_identical_idempotent_retry_is_resolved_before_advanced_head_cas(tmp_path) -> None:
    store = FileModelStore(tmp_path / "store")
    first = commit(store, model_payload(), expected=None, key="same-operation")

    retry_transaction = store.begin(
        "model-alpha", None, "same-operation", "test-actor"
    )
    retry_transaction.stage(model_payload())
    retry = retry_transaction.commit()

    assert retry == first
    assert store.list_revisions("model-alpha") == (first.revision,)


def test_stale_writer_loses_without_visible_revision(tmp_path) -> None:
    store = FileModelStore(tmp_path / "store")
    base = commit(store, model_payload(), key="base")
    first_writer = store.begin("model-alpha", base.revision, "writer-one", "actor-one")
    second_writer = store.begin("model-alpha", base.revision, "writer-two", "actor-two")
    first_writer.stage(model_payload("First wins"))
    second_writer.stage(model_payload("Second loses"))

    winner = first_writer.commit()
    with pytest.raises(TransactionConflictError) as caught:
        second_writer.commit()

    assert caught.value.expected == base.revision
    assert caught.value.actual == winner.revision
    assert caught.value.receipt.conflict_kind == "compare_and_swap"
    assert list((tmp_path / "store" / "receipts" / "conflicts").glob("*.json"))
    assert store.head("model-alpha") == winner.revision
    assert len(store.list_revisions("model-alpha")) == 2
    assert all(
        snapshot != second_writer.staged_snapshot.revision
        for snapshot in store.list_revisions("model-alpha")
    )


def test_idempotency_key_cannot_be_rebound_to_different_content(tmp_path) -> None:
    store = FileModelStore(tmp_path / "store")
    first = commit(store, model_payload(), key="stable-key")
    conflicting = store.begin("model-alpha", None, "stable-key", "test-actor")
    conflicting.stage(model_payload("Different content"))

    with pytest.raises(IdempotencyConflictError, match="different model content") as caught:
        conflicting.commit()
    assert caught.value.receipt.conflict_kind == "idempotency"
    assert store.head("model-alpha") == first.revision
    assert store.list_revisions("model-alpha") == (first.revision,)


def test_explicit_abort_writes_terminal_receipt_without_head(tmp_path) -> None:
    store = FileModelStore(tmp_path / "store")
    transaction = store.begin("model-alpha", None, "aborted-key", "test-actor")
    digest = transaction.stage(model_payload())
    receipt = transaction.abort("operator cancelled")

    assert receipt.status == "aborted"
    assert receipt.staged_content_digest == digest
    assert store.head("model-alpha") is None


def test_live_writer_lock_is_never_stolen(tmp_path) -> None:
    root = tmp_path / "store"
    store = FileModelStore(root)
    lock_path = root / "locks" / "writer.lock"
    lock_path.write_text(
        json.dumps(
            {
                "artifact_schema": JOURNAL_SCHEMA,
                "store_schema_version": SCHEMA_VERSION,
                "lock_type": "writer",
                "pid": os.getpid(),
                "host": socket.gethostname(),
                "transaction_id": "txn-live-owner",
                "created_at": "2026-07-14T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    transaction = store.begin("model-alpha", None, "blocked-key", "test-actor")
    transaction.stage(model_payload())

    with pytest.raises(WriterLockHeldError, match="live writer lock"):
        transaction.commit()
    with pytest.raises(WriterLockHeldError, match="refused live writer lock"):
        store.recover()
    assert lock_path.exists()


def test_concurrent_writers_publish_exactly_one_revision_and_loser_stales(tmp_path) -> None:
    store = FileModelStore(tmp_path / "store")
    base = commit(store, model_payload("Base"), key="base-concurrent")
    transactions = {
        "one": store.begin("model-alpha", base.revision, "concurrent-one", "actor-one"),
        "two": store.begin("model-alpha", base.revision, "concurrent-two", "actor-two"),
    }
    transactions["one"].stage(model_payload("Candidate one"))
    transactions["two"].stage(model_payload("Candidate two"))
    barrier = threading.Barrier(2)
    outcomes: dict[str, object] = {}

    def publish(name: str) -> None:
        barrier.wait()
        try:
            outcomes[name] = transactions[name].commit()
        except (WriterLockHeldError, TransactionConflictError) as exc:
            outcomes[name] = exc

    workers = [threading.Thread(target=publish, args=(name,)) for name in transactions]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
    assert all(not worker.is_alive() for worker in workers)

    winners = [name for name, outcome in outcomes.items() if hasattr(outcome, "revision")]
    assert len(winners) == 1
    loser = next(name for name in transactions if name not in winners)
    if isinstance(outcomes[loser], WriterLockHeldError):
        with pytest.raises(TransactionConflictError):
            transactions[loser].commit()
    else:
        assert isinstance(outcomes[loser], TransactionConflictError)
    assert len(store.list_revisions("model-alpha")) == 2
