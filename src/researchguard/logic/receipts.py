"""Immutable receipts for ModelStore publication and recovery decisions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping

from .identity import ModelId, ModelRevision, ReceiptId, TransactionId
from .schema import RECEIPT_SCHEMA, SCHEMA_VERSION


STRUCTURAL_CLAIM_BOUNDARY = (
    "This receipt proves declared store and structural operations only; "
    "it does not establish factual truth."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_default(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "value"):
        return value.value
    raise TypeError(f"value of type {type(value).__name__} is not JSON serializable")


def canonical_receipt_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=_json_default,
    ).encode("utf-8")


def _receipt_id(kind: str, payload: Mapping[str, Any]) -> ReceiptId:
    digest = hashlib.sha256(canonical_receipt_bytes(payload)).hexdigest()
    return ReceiptId(f"receipt-{kind}-{digest}")


def _assert_receipt_id(actual: ReceiptId, kind: str, payload: Mapping[str, Any]) -> None:
    expected = _receipt_id(kind, payload)
    if actual != expected:
        raise ValueError(f"{kind} receipt_id {actual} does not match content {expected}")


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


@dataclass(frozen=True)
class CommitReceipt:
    receipt_id: ReceiptId
    transaction_id: TransactionId
    model_id: ModelId
    revision: ModelRevision
    parent_revision: ModelRevision | None
    content_digest: str
    idempotency_key: str
    actor: str
    committed_at: str
    artifact_schema: str = RECEIPT_SCHEMA
    store_schema_version: str = SCHEMA_VERSION
    artifact_type: str = "commit"
    status: str = "committed"
    claim_boundary: str = STRUCTURAL_CLAIM_BOUNDARY

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", ReceiptId.parse(self.receipt_id))
        object.__setattr__(self, "transaction_id", TransactionId.parse(self.transaction_id))
        object.__setattr__(self, "model_id", ModelId.parse(self.model_id))
        object.__setattr__(self, "revision", ModelRevision.parse(self.revision))
        if self.parent_revision is not None:
            object.__setattr__(
                self, "parent_revision", ModelRevision.parse(self.parent_revision)
            )
        _validate_common_receipt(self.artifact_schema, self.store_schema_version)
        if self.status != "committed" or self.artifact_type != "commit":
            raise ValueError("CommitReceipt must have committed/commit status and type")
        _assert_receipt_id(
            self.receipt_id,
            "commit",
            {
                "transaction_id": str(self.transaction_id),
                "model_id": str(self.model_id),
                "revision": str(self.revision),
                "parent_revision": str(self.parent_revision) if self.parent_revision else None,
                "content_digest": self.content_digest,
                "idempotency_key": self.idempotency_key,
                "actor": self.actor,
                "committed_at": self.committed_at,
            },
        )

    @classmethod
    def create(
        cls,
        *,
        transaction_id: TransactionId,
        model_id: ModelId,
        revision: ModelRevision,
        parent_revision: ModelRevision | None,
        content_digest: str,
        idempotency_key: str,
        actor: str,
        committed_at: str | None = None,
    ) -> "CommitReceipt":
        timestamp = committed_at or utc_now()
        payload = {
            "transaction_id": str(transaction_id),
            "model_id": str(model_id),
            "revision": str(revision),
            "parent_revision": str(parent_revision) if parent_revision else None,
            "content_digest": content_digest,
            "idempotency_key": idempotency_key,
            "actor": actor,
            "committed_at": timestamp,
        }
        return cls(receipt_id=_receipt_id("commit", payload), **payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "store_schema_version": self.store_schema_version,
            "artifact_type": self.artifact_type,
            "status": self.status,
            "receipt_id": str(self.receipt_id),
            "transaction_id": str(self.transaction_id),
            "model_id": str(self.model_id),
            "revision": str(self.revision),
            "parent_revision": str(self.parent_revision) if self.parent_revision else None,
            "content_digest": self.content_digest,
            "idempotency_key": self.idempotency_key,
            "actor": self.actor,
            "committed_at": self.committed_at,
            "claim_boundary": self.claim_boundary,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "CommitReceipt":
        return cls(
            artifact_schema=str(raw.get("artifact_schema", "")),
            store_schema_version=str(raw.get("store_schema_version", "")),
            artifact_type=str(raw.get("artifact_type", "")),
            status=str(raw.get("status", "")),
            receipt_id=ReceiptId.parse(raw.get("receipt_id", "")),
            transaction_id=TransactionId.parse(raw.get("transaction_id", "")),
            model_id=ModelId.parse(raw.get("model_id", "")),
            revision=ModelRevision.parse(raw.get("revision", "")),
            parent_revision=(
                ModelRevision.parse(raw["parent_revision"])
                if raw.get("parent_revision")
                else None
            ),
            content_digest=str(raw.get("content_digest", "")),
            idempotency_key=str(raw.get("idempotency_key", "")),
            actor=str(raw.get("actor", "")),
            committed_at=str(raw.get("committed_at", "")),
            claim_boundary=str(raw.get("claim_boundary", STRUCTURAL_CLAIM_BOUNDARY)),
        )


@dataclass(frozen=True)
class AbortReceipt:
    receipt_id: ReceiptId
    transaction_id: TransactionId
    model_id: ModelId
    actor: str
    reason: str
    aborted_at: str
    staged_content_digest: str | None = None
    artifact_schema: str = RECEIPT_SCHEMA
    store_schema_version: str = SCHEMA_VERSION
    artifact_type: str = "abort"
    status: str = "aborted"
    claim_boundary: str = STRUCTURAL_CLAIM_BOUNDARY

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", ReceiptId.parse(self.receipt_id))
        object.__setattr__(self, "transaction_id", TransactionId.parse(self.transaction_id))
        object.__setattr__(self, "model_id", ModelId.parse(self.model_id))
        _validate_common_receipt(self.artifact_schema, self.store_schema_version)
        if not self.reason:
            raise ValueError("abort receipt requires a reason")
        _assert_receipt_id(
            self.receipt_id,
            "abort",
            {
                "transaction_id": str(self.transaction_id),
                "model_id": str(self.model_id),
                "actor": self.actor,
                "reason": self.reason,
                "aborted_at": self.aborted_at,
                "staged_content_digest": self.staged_content_digest,
            },
        )

    @classmethod
    def create(
        cls,
        *,
        transaction_id: TransactionId,
        model_id: ModelId,
        actor: str,
        reason: str,
        staged_content_digest: str | None,
    ) -> "AbortReceipt":
        timestamp = utc_now()
        payload = {
            "transaction_id": str(transaction_id),
            "model_id": str(model_id),
            "actor": actor,
            "reason": reason,
            "aborted_at": timestamp,
            "staged_content_digest": staged_content_digest,
        }
        return cls(receipt_id=_receipt_id("abort", payload), **payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "store_schema_version": self.store_schema_version,
            "artifact_type": self.artifact_type,
            "status": self.status,
            "receipt_id": str(self.receipt_id),
            "transaction_id": str(self.transaction_id),
            "model_id": str(self.model_id),
            "actor": self.actor,
            "reason": self.reason,
            "aborted_at": self.aborted_at,
            "staged_content_digest": self.staged_content_digest,
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class ConflictReceipt:
    """In-memory immutable evidence for a rejected CAS or idempotency attempt."""

    receipt_id: ReceiptId
    transaction_id: TransactionId
    model_id: ModelId
    conflict_kind: str
    expected_revision: ModelRevision | None
    actual_revision: ModelRevision | None
    reason: str
    observed_at: str
    details: Mapping[str, Any] = field(default_factory=dict)
    artifact_schema: str = RECEIPT_SCHEMA
    store_schema_version: str = SCHEMA_VERSION
    artifact_type: str = "conflict"
    status: str = "rejected"
    claim_boundary: str = STRUCTURAL_CLAIM_BOUNDARY

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", ReceiptId.parse(self.receipt_id))
        object.__setattr__(self, "transaction_id", TransactionId.parse(self.transaction_id))
        object.__setattr__(self, "model_id", ModelId.parse(self.model_id))
        if self.expected_revision is not None:
            object.__setattr__(
                self, "expected_revision", ModelRevision.parse(self.expected_revision)
            )
        if self.actual_revision is not None:
            object.__setattr__(self, "actual_revision", ModelRevision.parse(self.actual_revision))
        object.__setattr__(self, "details", _freeze_mapping(self.details))
        _validate_common_receipt(self.artifact_schema, self.store_schema_version)
        _assert_receipt_id(
            self.receipt_id,
            "conflict",
            {
                "transaction_id": str(self.transaction_id),
                "model_id": str(self.model_id),
                "conflict_kind": self.conflict_kind,
                "expected_revision": (
                    str(self.expected_revision) if self.expected_revision else None
                ),
                "actual_revision": str(self.actual_revision) if self.actual_revision else None,
                "reason": self.reason,
                "observed_at": self.observed_at,
                "details": dict(self.details),
            },
        )

    @classmethod
    def create(
        cls,
        *,
        transaction_id: TransactionId,
        model_id: ModelId,
        conflict_kind: str,
        expected_revision: ModelRevision | None,
        actual_revision: ModelRevision | None,
        reason: str,
        details: Mapping[str, Any] | None = None,
    ) -> "ConflictReceipt":
        timestamp = utc_now()
        payload = {
            "transaction_id": str(transaction_id),
            "model_id": str(model_id),
            "conflict_kind": conflict_kind,
            "expected_revision": str(expected_revision) if expected_revision else None,
            "actual_revision": str(actual_revision) if actual_revision else None,
            "reason": reason,
            "observed_at": timestamp,
            "details": dict(details or {}),
        }
        return cls(receipt_id=_receipt_id("conflict", payload), **payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "store_schema_version": self.store_schema_version,
            "artifact_type": self.artifact_type,
            "status": self.status,
            "receipt_id": str(self.receipt_id),
            "transaction_id": str(self.transaction_id),
            "model_id": str(self.model_id),
            "conflict_kind": self.conflict_kind,
            "expected_revision": str(self.expected_revision) if self.expected_revision else None,
            "actual_revision": str(self.actual_revision) if self.actual_revision else None,
            "reason": self.reason,
            "observed_at": self.observed_at,
            "details": dict(self.details),
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class RecoveryReceipt:
    receipt_id: ReceiptId
    transaction_id: TransactionId
    action: str
    reason: str
    recovered_at: str
    model_id: ModelId | None = None
    revision: ModelRevision | None = None
    journal_status_before: str = ""
    journal_status_after: str = ""
    evidence: Mapping[str, Any] = field(default_factory=dict)
    artifact_schema: str = RECEIPT_SCHEMA
    store_schema_version: str = SCHEMA_VERSION
    artifact_type: str = "recovery"
    status: str = "recovered"
    claim_boundary: str = STRUCTURAL_CLAIM_BOUNDARY

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", ReceiptId.parse(self.receipt_id))
        object.__setattr__(self, "transaction_id", TransactionId.parse(self.transaction_id))
        if self.model_id is not None:
            object.__setattr__(self, "model_id", ModelId.parse(self.model_id))
        if self.revision is not None:
            object.__setattr__(self, "revision", ModelRevision.parse(self.revision))
        object.__setattr__(self, "evidence", _freeze_mapping(self.evidence))
        _validate_common_receipt(self.artifact_schema, self.store_schema_version)
        _assert_receipt_id(
            self.receipt_id,
            "recovery",
            {
                "transaction_id": str(self.transaction_id),
                "action": self.action,
                "reason": self.reason,
                "recovered_at": self.recovered_at,
                "model_id": str(self.model_id) if self.model_id else None,
                "revision": str(self.revision) if self.revision else None,
                "journal_status_before": self.journal_status_before,
                "journal_status_after": self.journal_status_after,
                "evidence": dict(self.evidence),
            },
        )

    @classmethod
    def create(
        cls,
        *,
        transaction_id: TransactionId,
        action: str,
        reason: str,
        model_id: ModelId | None = None,
        revision: ModelRevision | None = None,
        journal_status_before: str = "",
        journal_status_after: str = "",
        evidence: Mapping[str, Any] | None = None,
    ) -> "RecoveryReceipt":
        timestamp = utc_now()
        payload = {
            "transaction_id": str(transaction_id),
            "action": action,
            "reason": reason,
            "recovered_at": timestamp,
            "model_id": str(model_id) if model_id else None,
            "revision": str(revision) if revision else None,
            "journal_status_before": journal_status_before,
            "journal_status_after": journal_status_after,
            "evidence": dict(evidence or {}),
        }
        return cls(receipt_id=_receipt_id("recovery", payload), **payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "store_schema_version": self.store_schema_version,
            "artifact_type": self.artifact_type,
            "status": self.status,
            "receipt_id": str(self.receipt_id),
            "transaction_id": str(self.transaction_id),
            "model_id": str(self.model_id) if self.model_id else None,
            "revision": str(self.revision) if self.revision else None,
            "action": self.action,
            "reason": self.reason,
            "recovered_at": self.recovered_at,
            "journal_status_before": self.journal_status_before,
            "journal_status_after": self.journal_status_after,
            "evidence": dict(self.evidence),
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class LifecycleReceipt:
    """Receipt for an explicit tombstone manifest mutation."""

    receipt_id: ReceiptId
    transaction_id: TransactionId
    action: str
    subject_model_id: ModelId
    actor: str
    reason: str
    recorded_at: str
    artifact_schema: str = RECEIPT_SCHEMA
    store_schema_version: str = SCHEMA_VERSION
    artifact_type: str = "lifecycle"
    status: str = "committed"
    claim_boundary: str = STRUCTURAL_CLAIM_BOUNDARY

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", ReceiptId.parse(self.receipt_id))
        object.__setattr__(self, "transaction_id", TransactionId.parse(self.transaction_id))
        object.__setattr__(self, "subject_model_id", ModelId.parse(self.subject_model_id))
        _validate_common_receipt(self.artifact_schema, self.store_schema_version)
        if self.action != "tombstone":
            raise ValueError("lifecycle action must be tombstone")
        if not self.reason:
            raise ValueError("lifecycle receipt requires a reason")
        _assert_receipt_id(
            self.receipt_id,
            "lifecycle",
            {
                "transaction_id": str(self.transaction_id),
                "action": self.action,
                "subject_model_id": str(self.subject_model_id),
                "actor": self.actor,
                "reason": self.reason,
                "recorded_at": self.recorded_at,
            },
        )

    @classmethod
    def create(
        cls,
        *,
        transaction_id: TransactionId,
        action: str,
        subject_model_id: ModelId,
        actor: str,
        reason: str,
    ) -> "LifecycleReceipt":
        timestamp = utc_now()
        payload = {
            "transaction_id": str(transaction_id),
            "action": action,
            "subject_model_id": str(subject_model_id),
            "actor": actor,
            "reason": reason,
            "recorded_at": timestamp,
        }
        return cls(receipt_id=_receipt_id("lifecycle", payload), **payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "store_schema_version": self.store_schema_version,
            "artifact_type": self.artifact_type,
            "status": self.status,
            "receipt_id": str(self.receipt_id),
            "transaction_id": str(self.transaction_id),
            "action": self.action,
            "subject_model_id": str(self.subject_model_id),
            "actor": self.actor,
            "reason": self.reason,
            "recorded_at": self.recorded_at,
            "claim_boundary": self.claim_boundary,
        }


def _validate_common_receipt(artifact_schema: str, store_schema_version: str) -> None:
    if artifact_schema != RECEIPT_SCHEMA:
        raise ValueError(
            f"unsupported receipt schema {artifact_schema!r}; expected {RECEIPT_SCHEMA!r}"
        )
    if store_schema_version != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported store schema {store_schema_version!r}; expected {SCHEMA_VERSION!r}"
        )


def receipt_from_dict(
    raw: Mapping[str, Any],
) -> CommitReceipt | AbortReceipt | ConflictReceipt | RecoveryReceipt | LifecycleReceipt:
    artifact_type = raw.get("artifact_type")
    if artifact_type == "commit":
        return CommitReceipt.from_dict(raw)
    if artifact_type == "abort":
        return AbortReceipt(
            artifact_schema=str(raw.get("artifact_schema", "")),
            store_schema_version=str(raw.get("store_schema_version", "")),
            artifact_type="abort",
            status=str(raw.get("status", "")),
            receipt_id=ReceiptId.parse(raw.get("receipt_id", "")),
            transaction_id=TransactionId.parse(raw.get("transaction_id", "")),
            model_id=ModelId.parse(raw.get("model_id", "")),
            actor=str(raw.get("actor", "")),
            reason=str(raw.get("reason", "")),
            aborted_at=str(raw.get("aborted_at", "")),
            staged_content_digest=raw.get("staged_content_digest"),
            claim_boundary=str(raw.get("claim_boundary", STRUCTURAL_CLAIM_BOUNDARY)),
        )
    if artifact_type == "conflict":
        return ConflictReceipt(
            artifact_schema=str(raw.get("artifact_schema", "")),
            store_schema_version=str(raw.get("store_schema_version", "")),
            artifact_type="conflict",
            status=str(raw.get("status", "")),
            receipt_id=ReceiptId.parse(raw.get("receipt_id", "")),
            transaction_id=TransactionId.parse(raw.get("transaction_id", "")),
            model_id=ModelId.parse(raw.get("model_id", "")),
            conflict_kind=str(raw.get("conflict_kind", "")),
            expected_revision=(
                ModelRevision.parse(raw["expected_revision"])
                if raw.get("expected_revision")
                else None
            ),
            actual_revision=(
                ModelRevision.parse(raw["actual_revision"])
                if raw.get("actual_revision")
                else None
            ),
            reason=str(raw.get("reason", "")),
            observed_at=str(raw.get("observed_at", "")),
            details=dict(raw.get("details") or {}),
            claim_boundary=str(raw.get("claim_boundary", STRUCTURAL_CLAIM_BOUNDARY)),
        )
    if artifact_type == "recovery":
        return RecoveryReceipt(
            artifact_schema=str(raw.get("artifact_schema", "")),
            store_schema_version=str(raw.get("store_schema_version", "")),
            artifact_type="recovery",
            status=str(raw.get("status", "")),
            receipt_id=ReceiptId.parse(raw.get("receipt_id", "")),
            transaction_id=TransactionId.parse(raw.get("transaction_id", "")),
            model_id=ModelId.parse(raw["model_id"]) if raw.get("model_id") else None,
            revision=ModelRevision.parse(raw["revision"]) if raw.get("revision") else None,
            action=str(raw.get("action", "")),
            reason=str(raw.get("reason", "")),
            recovered_at=str(raw.get("recovered_at", "")),
            journal_status_before=str(raw.get("journal_status_before", "")),
            journal_status_after=str(raw.get("journal_status_after", "")),
            evidence=dict(raw.get("evidence") or {}),
            claim_boundary=str(raw.get("claim_boundary", STRUCTURAL_CLAIM_BOUNDARY)),
        )
    if artifact_type == "lifecycle":
        if "target_model_id" in raw:
            raise ValueError(
                "lifecycle target_model_id is retired; migrate the receipt before use"
            )
        return LifecycleReceipt(
            artifact_schema=str(raw.get("artifact_schema", "")),
            store_schema_version=str(raw.get("store_schema_version", "")),
            artifact_type="lifecycle",
            status=str(raw.get("status", "")),
            receipt_id=ReceiptId.parse(raw.get("receipt_id", "")),
            transaction_id=TransactionId.parse(raw.get("transaction_id", "")),
            action=str(raw.get("action", "")),
            subject_model_id=ModelId.parse(raw.get("subject_model_id", "")),
            actor=str(raw.get("actor", "")),
            reason=str(raw.get("reason", "")),
            recorded_at=str(raw.get("recorded_at", "")),
            claim_boundary=str(raw.get("claim_boundary", STRUCTURAL_CLAIM_BOUNDARY)),
        )
    raise ValueError(f"unsupported receipt artifact_type: {artifact_type!r}")


__all__ = [
    "AbortReceipt",
    "CommitReceipt",
    "ConflictReceipt",
    "LifecycleReceipt",
    "RecoveryReceipt",
    "STRUCTURAL_CLAIM_BOUNDARY",
    "canonical_receipt_bytes",
    "receipt_from_dict",
    "utc_now",
]
