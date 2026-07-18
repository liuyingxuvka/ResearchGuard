"""Explicit compare-and-swap transaction state for ModelStore writes."""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from .identity import ModelId, ModelRevision, TransactionId
from .model_store import ModelSnapshot, TransactionStateError
from .receipts import AbortReceipt, CommitReceipt, utc_now
from .store_validation import validate_snapshot


class _TransactionBackend(Protocol):
    def _commit_transaction(
        self, transaction: "ModelTransaction", snapshot: ModelSnapshot
    ) -> CommitReceipt: ...

    def _abort_transaction(
        self, transaction: "ModelTransaction", reason: str
    ) -> AbortReceipt: ...


class ModelTransaction:
    """One explicit authoring-to-publication attempt.

    The expected revision is captured at construction, including explicit
    ``None`` for first creation.  A transaction never silently refreshes it.
    """

    def __init__(
        self,
        *,
        store: _TransactionBackend,
        model_id: ModelId | str,
        expected_revision: ModelRevision | str | None,
        idempotency_key: str,
        actor: str,
        transaction_id: TransactionId | str | None = None,
    ) -> None:
        self._store = store
        self.model_id = ModelId.parse(model_id)
        self.expected_revision = (
            ModelRevision.parse(expected_revision) if expected_revision is not None else None
        )
        # The idempotency key is a portable machine identity, not free-form text.
        TransactionId(str(idempotency_key))
        self.idempotency_key = str(idempotency_key)
        self.actor = str(actor).strip()
        if not self.actor:
            raise ValueError("transaction actor must not be empty")
        self.transaction_id = TransactionId.parse(
            transaction_id or f"txn-{uuid.uuid4().hex}"
        )
        self._snapshot: ModelSnapshot | None = None
        self._terminal_receipt: CommitReceipt | AbortReceipt | None = None
        self._state = "open"

    @property
    def state(self) -> str:
        return self._state

    @property
    def staged_snapshot(self) -> ModelSnapshot | None:
        return self._snapshot

    @property
    def terminal_receipt(self) -> CommitReceipt | AbortReceipt | None:
        return self._terminal_receipt

    def stage(self, model: Any) -> str:
        if self._state not in {"open", "staged"}:
            raise TransactionStateError(
                f"cannot stage transaction {self.transaction_id} in state {self._state}"
            )
        snapshot = ModelSnapshot.create(
            model,
            parent_revision=self.expected_revision,
            created_at=utc_now(),
            created_by=self.actor,
        )
        if snapshot.model_id != self.model_id:
            raise ValueError(
                f"transaction model {self.model_id} does not match staged model {snapshot.model_id}"
            )
        validate_snapshot(snapshot)
        self._snapshot = snapshot
        self._state = "staged"
        return snapshot.content_digest

    def commit(self) -> CommitReceipt:
        if self._state == "committed" and isinstance(self._terminal_receipt, CommitReceipt):
            return self._terminal_receipt
        if self._state != "staged" or self._snapshot is None:
            raise TransactionStateError(
                f"cannot commit transaction {self.transaction_id} in state {self._state}; "
                "stage a valid model first"
            )
        receipt = self._store._commit_transaction(self, self._snapshot)
        self._terminal_receipt = receipt
        self._state = "committed"
        return receipt

    def abort(self, reason: str) -> AbortReceipt:
        if self._state == "aborted" and isinstance(self._terminal_receipt, AbortReceipt):
            return self._terminal_receipt
        if self._state == "committed":
            raise TransactionStateError(
                f"cannot abort committed transaction {self.transaction_id}"
            )
        if not str(reason).strip():
            raise ValueError("abort requires a reason")
        receipt = self._store._abort_transaction(self, str(reason).strip())
        self._terminal_receipt = receipt
        self._state = "aborted"
        return receipt

    def __enter__(self) -> "ModelTransaction":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        if exc is not None and self._state not in {"committed", "aborted"}:
            self.abort(f"context exited with {exc_type.__name__}: {exc}")
        return False


__all__ = ["ModelTransaction"]
