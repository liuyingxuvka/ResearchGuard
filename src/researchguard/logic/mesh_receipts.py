"""Immutable current-schema receipts for product-runtime ModelMesh."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .identity import (
    MeshEvaluationId,
    MeshId,
    MeshReceiptId,
    MeshRevision,
    MeshTransactionId,
    OverlayCatalogRevision,
    QualifiedModelRef,
)
from .model_mesh import OverlayCatalogPin, qualified_model_key
from .model_store import canonical_digest
from .receipts import utc_now
from .schema import (
    MESH_INVALIDATION_RECEIPT_SCHEMA,
    MESH_RECEIPT_SCHEMA,
    MESH_SCALE_RECEIPT_SCHEMA,
    MESH_SCHEMA_VERSION,
    MESH_SIMULATION_RECEIPT_SCHEMA,
)


MESH_RECEIPT_CLAIM_BOUNDARY = (
    "This receipt proves only the declared durable ModelMesh operation and exact "
    "bindings. It does not establish factual truth, downstream cutover, or release readiness."
)


class MeshReceiptError(ValueError):
    """A receipt is incomplete, non-current, or content-tampered."""


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return copy.deepcopy(value)


def _require(raw: Mapping[str, Any], key: str) -> Any:
    if key not in raw:
        raise MeshReceiptError(f"required receipt field is missing: {key}")
    return raw[key]


def _receipt_id(kind: str, payload: Mapping[str, Any]) -> MeshReceiptId:
    digest = canonical_digest({"kind": kind, "payload": dict(payload)}).split(":", 1)[1]
    return MeshReceiptId(f"mesh-receipt-{kind}-{digest}")


def _check_schema(artifact_schema: str, expected: str, mesh_schema_version: str) -> None:
    if artifact_schema != expected:
        raise MeshReceiptError(
            f"receipt schema {artifact_schema!r} is unsupported; expected {expected!r}"
        )
    if mesh_schema_version != MESH_SCHEMA_VERSION:
        raise MeshReceiptError(
            f"mesh schema {mesh_schema_version!r} is unsupported; expected {MESH_SCHEMA_VERSION!r}"
        )


def _check_fixed(actual: str, expected: str, field_name: str) -> None:
    if actual != expected:
        raise MeshReceiptError(
            f"receipt {field_name} {actual!r} is unsupported; expected {expected!r}"
        )


@dataclass(frozen=True)
class MeshCommitReceipt:
    receipt_id: MeshReceiptId
    transaction_id: MeshTransactionId
    mesh_id: MeshId
    revision: MeshRevision
    parent_revision: MeshRevision | None
    content_digest: str
    registry_digest: str
    shard_digests: tuple[tuple[str, str], ...]
    model_pins: tuple[QualifiedModelRef, ...]
    parent_catalog_baseline: OverlayCatalogPin | None
    child_catalog_pin: OverlayCatalogPin
    invalidation_receipt_id: MeshReceiptId | None
    idempotency_key: str
    actor: str
    committed_at: str
    package_version: str
    tool_fingerprint: str
    claim_boundary: str = MESH_RECEIPT_CLAIM_BOUNDARY
    status: str = "committed"
    artifact_schema: str = MESH_RECEIPT_SCHEMA
    mesh_schema_version: str = MESH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _check_schema(self.artifact_schema, MESH_RECEIPT_SCHEMA, self.mesh_schema_version)
        _check_fixed(self.status, "committed", "status")
        object.__setattr__(self, "receipt_id", MeshReceiptId.parse(self.receipt_id))
        object.__setattr__(self, "transaction_id", MeshTransactionId.parse(self.transaction_id))
        object.__setattr__(self, "mesh_id", MeshId.parse(self.mesh_id))
        object.__setattr__(self, "revision", MeshRevision.parse(self.revision))
        if self.parent_revision is not None:
            object.__setattr__(self, "parent_revision", MeshRevision.parse(self.parent_revision))
        shard_digests = tuple(sorted((str(k), str(v)) for k, v in self.shard_digests))
        if len({key for key, _digest in shard_digests}) != len(shard_digests):
            raise MeshReceiptError("commit receipt contains duplicate shard kinds")
        if any(not digest.startswith("sha256:") for _key, digest in shard_digests):
            raise MeshReceiptError("commit receipt shard digests must use sha256")
        object.__setattr__(self, "shard_digests", shard_digests)
        model_pins = tuple(self.model_pins)
        if len(set(model_pins)) != len(model_pins):
            raise MeshReceiptError("commit receipt contains duplicate model pins")
        object.__setattr__(self, "model_pins", tuple(sorted(model_pins, key=qualified_model_key)))
        if self.parent_revision is None:
            if self.parent_catalog_baseline is not None or self.invalidation_receipt_id is not None:
                raise MeshReceiptError("first mesh commit cannot name parent invalidation authority")
        else:
            if self.parent_catalog_baseline is None or self.invalidation_receipt_id is None:
                raise MeshReceiptError(
                    "non-first mesh commit requires exact parent catalog and invalidation receipt"
                )
            if (
                self.parent_catalog_baseline.mesh_id != self.mesh_id
                or self.parent_catalog_baseline.mesh_revision != self.parent_revision
            ):
                raise MeshReceiptError("parent catalog baseline does not bind parent mesh revision")
        if self.child_catalog_pin.mesh_id != self.mesh_id or self.child_catalog_pin.mesh_revision != self.revision:
            raise MeshReceiptError("child catalog pin does not bind committed mesh revision")
        expected = _receipt_id("commit", self.payload())
        if self.receipt_id != expected:
            raise MeshReceiptError(f"commit receipt ID mismatch: {self.receipt_id} != {expected}")

    def payload(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "mesh_schema_version": self.mesh_schema_version,
            "status": self.status,
            "transaction_id": str(self.transaction_id),
            "mesh_id": str(self.mesh_id),
            "revision": str(self.revision),
            "parent_revision": str(self.parent_revision) if self.parent_revision else None,
            "content_digest": self.content_digest,
            "registry_digest": self.registry_digest,
            "shard_digests": {key: value for key, value in self.shard_digests},
            "model_pins": [item.to_dict() for item in self.model_pins],
            "parent_catalog_baseline": self.parent_catalog_baseline.to_dict() if self.parent_catalog_baseline else None,
            "child_catalog_pin": self.child_catalog_pin.to_dict(),
            "invalidation_receipt_id": str(self.invalidation_receipt_id) if self.invalidation_receipt_id else None,
            "idempotency_key": self.idempotency_key,
            "actor": self.actor,
            "committed_at": self.committed_at,
            "package_version": self.package_version,
            "tool_fingerprint": self.tool_fingerprint,
            "claim_boundary": self.claim_boundary,
        }

    @classmethod
    def create(cls, **values: Any) -> "MeshCommitReceipt":
        committed_at = values.pop("committed_at", None) or utc_now()
        shard_digests = tuple(
            sorted((str(key), str(digest)) for key, digest in values["shard_digests"])
        )
        model_pins = tuple(
            sorted(
                {QualifiedModelRef(item.model_id, item.revision) for item in values["model_pins"]},
                key=qualified_model_key,
            )
        )
        parent_revision = values.get("parent_revision")
        parent_catalog_baseline = values.get("parent_catalog_baseline")
        invalidation_receipt_id = values.get("invalidation_receipt_id")
        claim_boundary = values.get("claim_boundary", MESH_RECEIPT_CLAIM_BOUNDARY)
        payload = {
            "artifact_schema": MESH_RECEIPT_SCHEMA,
            "mesh_schema_version": MESH_SCHEMA_VERSION,
            "status": "committed",
            "transaction_id": str(values["transaction_id"]),
            "mesh_id": str(values["mesh_id"]),
            "revision": str(values["revision"]),
            "parent_revision": str(parent_revision) if parent_revision else None,
            "content_digest": values["content_digest"],
            "registry_digest": values["registry_digest"],
            "shard_digests": dict(shard_digests),
            "model_pins": [item.to_dict() for item in model_pins],
            "parent_catalog_baseline": (
                parent_catalog_baseline.to_dict() if parent_catalog_baseline else None
            ),
            "child_catalog_pin": values["child_catalog_pin"].to_dict(),
            "invalidation_receipt_id": (
                str(invalidation_receipt_id) if invalidation_receipt_id else None
            ),
            "idempotency_key": values["idempotency_key"],
            "actor": values["actor"],
            "committed_at": committed_at,
            "package_version": values["package_version"],
            "tool_fingerprint": values["tool_fingerprint"],
            "claim_boundary": claim_boundary,
        }
        return cls(
            receipt_id=_receipt_id("commit", payload),
            transaction_id=values["transaction_id"],
            mesh_id=values["mesh_id"],
            revision=values["revision"],
            parent_revision=parent_revision,
            content_digest=values["content_digest"],
            registry_digest=values["registry_digest"],
            shard_digests=shard_digests,
            model_pins=model_pins,
            parent_catalog_baseline=parent_catalog_baseline,
            child_catalog_pin=values["child_catalog_pin"],
            invalidation_receipt_id=invalidation_receipt_id,
            idempotency_key=values["idempotency_key"],
            actor=values["actor"],
            committed_at=committed_at,
            package_version=values["package_version"],
            tool_fingerprint=values["tool_fingerprint"],
            claim_boundary=claim_boundary,
        )

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_id": str(self.receipt_id)}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MeshCommitReceipt":
        parent_revision = _require(raw, "parent_revision")
        parent_catalog = _require(raw, "parent_catalog_baseline")
        invalidation_receipt_id = _require(raw, "invalidation_receipt_id")
        shard_digests = _require(raw, "shard_digests")
        if not isinstance(shard_digests, Mapping):
            raise MeshReceiptError("commit receipt shard_digests must be an object")
        return cls(
            receipt_id=MeshReceiptId.parse(_require(raw, "receipt_id")),
            transaction_id=MeshTransactionId.parse(_require(raw, "transaction_id")),
            mesh_id=MeshId.parse(_require(raw, "mesh_id")),
            revision=MeshRevision.parse(_require(raw, "revision")),
            parent_revision=MeshRevision.parse(parent_revision) if parent_revision else None,
            content_digest=str(_require(raw, "content_digest")),
            registry_digest=str(_require(raw, "registry_digest")),
            shard_digests=tuple((str(key), str(value)) for key, value in shard_digests.items()),
            model_pins=tuple(
                QualifiedModelRef.from_dict(item) for item in _require(raw, "model_pins")
            ),
            parent_catalog_baseline=(
                OverlayCatalogPin.from_dict(parent_catalog) if parent_catalog else None
            ),
            child_catalog_pin=OverlayCatalogPin.from_dict(_require(raw, "child_catalog_pin")),
            invalidation_receipt_id=(
                MeshReceiptId.parse(invalidation_receipt_id)
                if invalidation_receipt_id
                else None
            ),
            idempotency_key=str(_require(raw, "idempotency_key")),
            actor=str(_require(raw, "actor")),
            committed_at=str(_require(raw, "committed_at")),
            package_version=str(_require(raw, "package_version")),
            tool_fingerprint=str(_require(raw, "tool_fingerprint")),
            claim_boundary=str(_require(raw, "claim_boundary")),
            status=str(_require(raw, "status")),
            artifact_schema=str(_require(raw, "artifact_schema")),
            mesh_schema_version=str(_require(raw, "mesh_schema_version")),
        )


@dataclass(frozen=True)
class MeshAbortReceipt:
    receipt_id: MeshReceiptId
    transaction_id: MeshTransactionId
    mesh_id: MeshId
    actor: str
    reason: str
    staged_content_digest: str | None
    created_at: str
    claim_boundary: str = MESH_RECEIPT_CLAIM_BOUNDARY
    status: str = "aborted"
    artifact_schema: str = MESH_RECEIPT_SCHEMA
    mesh_schema_version: str = MESH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _check_schema(self.artifact_schema, MESH_RECEIPT_SCHEMA, self.mesh_schema_version)
        _check_fixed(self.status, "aborted", "status")
        object.__setattr__(self, "receipt_id", MeshReceiptId.parse(self.receipt_id))
        object.__setattr__(self, "transaction_id", MeshTransactionId.parse(self.transaction_id))
        object.__setattr__(self, "mesh_id", MeshId.parse(self.mesh_id))
        expected = _receipt_id("abort", self.payload())
        if self.receipt_id != expected:
            raise MeshReceiptError("abort receipt ID mismatch")

    def payload(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "mesh_schema_version": self.mesh_schema_version,
            "status": self.status,
            "transaction_id": str(self.transaction_id),
            "mesh_id": str(self.mesh_id),
            "actor": self.actor,
            "reason": self.reason,
            "staged_content_digest": self.staged_content_digest,
            "created_at": self.created_at,
            "claim_boundary": self.claim_boundary,
        }

    @classmethod
    def create(cls, **values: Any) -> "MeshAbortReceipt":
        payload = {
            "artifact_schema": MESH_RECEIPT_SCHEMA,
            "mesh_schema_version": MESH_SCHEMA_VERSION,
            "status": "aborted",
            "transaction_id": str(values["transaction_id"]),
            "mesh_id": str(values["mesh_id"]),
            "actor": values["actor"],
            "reason": values["reason"],
            "staged_content_digest": values.get("staged_content_digest"),
            "created_at": values.get("created_at") or utc_now(),
            "claim_boundary": values.get("claim_boundary", MESH_RECEIPT_CLAIM_BOUNDARY),
        }
        return cls(receipt_id=_receipt_id("abort", payload), **{k: v for k, v in payload.items() if k not in {"artifact_schema", "mesh_schema_version", "status"}})

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_id": str(self.receipt_id)}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MeshAbortReceipt":
        return cls(
            receipt_id=MeshReceiptId.parse(_require(raw, "receipt_id")),
            transaction_id=MeshTransactionId.parse(_require(raw, "transaction_id")),
            mesh_id=MeshId.parse(_require(raw, "mesh_id")),
            actor=str(_require(raw, "actor")),
            reason=str(_require(raw, "reason")),
            staged_content_digest=_require(raw, "staged_content_digest"),
            created_at=str(_require(raw, "created_at")),
            claim_boundary=str(_require(raw, "claim_boundary")),
            status=str(_require(raw, "status")),
            artifact_schema=str(_require(raw, "artifact_schema")),
            mesh_schema_version=str(_require(raw, "mesh_schema_version")),
        )


@dataclass(frozen=True)
class MeshConflictReceipt:
    receipt_id: MeshReceiptId
    transaction_id: MeshTransactionId
    mesh_id: MeshId
    conflict_kind: str
    expected_revision: MeshRevision | None
    actual_revision: MeshRevision | None
    expected_catalog_revision: OverlayCatalogRevision | None
    actual_catalog_revision: OverlayCatalogRevision | None
    reason: str
    created_at: str
    claim_boundary: str = MESH_RECEIPT_CLAIM_BOUNDARY
    status: str = "conflict"
    artifact_schema: str = MESH_RECEIPT_SCHEMA
    mesh_schema_version: str = MESH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _check_schema(self.artifact_schema, MESH_RECEIPT_SCHEMA, self.mesh_schema_version)
        _check_fixed(self.status, "conflict", "status")
        object.__setattr__(self, "receipt_id", MeshReceiptId.parse(self.receipt_id))
        object.__setattr__(self, "transaction_id", MeshTransactionId.parse(self.transaction_id))
        object.__setattr__(self, "mesh_id", MeshId.parse(self.mesh_id))
        for name, kind in (
            ("expected_revision", MeshRevision),
            ("actual_revision", MeshRevision),
            ("expected_catalog_revision", OverlayCatalogRevision),
            ("actual_catalog_revision", OverlayCatalogRevision),
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, kind.parse(value))
        if self.receipt_id != _receipt_id("conflict", self.payload()):
            raise MeshReceiptError("conflict receipt ID mismatch")

    def payload(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "mesh_schema_version": self.mesh_schema_version,
            "status": self.status,
            "transaction_id": str(self.transaction_id),
            "mesh_id": str(self.mesh_id),
            "conflict_kind": self.conflict_kind,
            "expected_revision": str(self.expected_revision) if self.expected_revision else None,
            "actual_revision": str(self.actual_revision) if self.actual_revision else None,
            "expected_catalog_revision": str(self.expected_catalog_revision) if self.expected_catalog_revision else None,
            "actual_catalog_revision": str(self.actual_catalog_revision) if self.actual_catalog_revision else None,
            "reason": self.reason,
            "created_at": self.created_at,
            "claim_boundary": self.claim_boundary,
        }

    @classmethod
    def create(cls, **values: Any) -> "MeshConflictReceipt":
        created_at = values.pop("created_at", None) or utc_now()
        claim_boundary = values.get("claim_boundary", MESH_RECEIPT_CLAIM_BOUNDARY)
        payload = {
            "artifact_schema": MESH_RECEIPT_SCHEMA,
            "mesh_schema_version": MESH_SCHEMA_VERSION,
            "status": "conflict",
            "transaction_id": str(values["transaction_id"]),
            "mesh_id": str(values["mesh_id"]),
            "conflict_kind": values["conflict_kind"],
            "expected_revision": (
                str(values["expected_revision"]) if values.get("expected_revision") else None
            ),
            "actual_revision": (
                str(values["actual_revision"]) if values.get("actual_revision") else None
            ),
            "expected_catalog_revision": (
                str(values["expected_catalog_revision"])
                if values.get("expected_catalog_revision")
                else None
            ),
            "actual_catalog_revision": (
                str(values["actual_catalog_revision"])
                if values.get("actual_catalog_revision")
                else None
            ),
            "reason": values["reason"],
            "created_at": created_at,
            "claim_boundary": claim_boundary,
        }
        return cls(
            receipt_id=_receipt_id("conflict", payload),
            transaction_id=values["transaction_id"],
            mesh_id=values["mesh_id"],
            conflict_kind=values["conflict_kind"],
            expected_revision=values.get("expected_revision"),
            actual_revision=values.get("actual_revision"),
            expected_catalog_revision=values.get("expected_catalog_revision"),
            actual_catalog_revision=values.get("actual_catalog_revision"),
            reason=values["reason"],
            created_at=created_at,
            claim_boundary=claim_boundary,
        )

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_id": str(self.receipt_id)}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MeshConflictReceipt":
        expected_revision = _require(raw, "expected_revision")
        actual_revision = _require(raw, "actual_revision")
        expected_catalog = _require(raw, "expected_catalog_revision")
        actual_catalog = _require(raw, "actual_catalog_revision")
        return cls(
            receipt_id=MeshReceiptId.parse(_require(raw, "receipt_id")),
            transaction_id=MeshTransactionId.parse(_require(raw, "transaction_id")),
            mesh_id=MeshId.parse(_require(raw, "mesh_id")),
            conflict_kind=str(_require(raw, "conflict_kind")),
            expected_revision=MeshRevision.parse(expected_revision) if expected_revision else None,
            actual_revision=MeshRevision.parse(actual_revision) if actual_revision else None,
            expected_catalog_revision=(
                OverlayCatalogRevision.parse(expected_catalog) if expected_catalog else None
            ),
            actual_catalog_revision=(
                OverlayCatalogRevision.parse(actual_catalog) if actual_catalog else None
            ),
            reason=str(_require(raw, "reason")),
            created_at=str(_require(raw, "created_at")),
            claim_boundary=str(_require(raw, "claim_boundary")),
            status=str(_require(raw, "status")),
            artifact_schema=str(_require(raw, "artifact_schema")),
            mesh_schema_version=str(_require(raw, "mesh_schema_version")),
        )


@dataclass(frozen=True)
class MeshRecoveryReceipt:
    receipt_id: MeshReceiptId
    action: str
    mesh_id: MeshId
    transaction_id: MeshTransactionId | None
    revision: MeshRevision | None
    reason: str
    created_at: str
    claim_boundary: str = MESH_RECEIPT_CLAIM_BOUNDARY
    status: str = "recovered"
    artifact_schema: str = MESH_RECEIPT_SCHEMA
    mesh_schema_version: str = MESH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _check_schema(self.artifact_schema, MESH_RECEIPT_SCHEMA, self.mesh_schema_version)
        _check_fixed(self.status, "recovered", "status")
        object.__setattr__(self, "receipt_id", MeshReceiptId.parse(self.receipt_id))
        object.__setattr__(self, "mesh_id", MeshId.parse(self.mesh_id))
        if self.transaction_id is not None:
            object.__setattr__(self, "transaction_id", MeshTransactionId.parse(self.transaction_id))
        if self.revision is not None:
            object.__setattr__(self, "revision", MeshRevision.parse(self.revision))
        if self.receipt_id != _receipt_id("recovery", self.payload()):
            raise MeshReceiptError("recovery receipt ID mismatch")

    def payload(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "mesh_schema_version": self.mesh_schema_version,
            "status": self.status,
            "action": self.action,
            "mesh_id": str(self.mesh_id),
            "transaction_id": str(self.transaction_id) if self.transaction_id else None,
            "revision": str(self.revision) if self.revision else None,
            "reason": self.reason,
            "created_at": self.created_at,
            "claim_boundary": self.claim_boundary,
        }

    @classmethod
    def create(cls, **values: Any) -> "MeshRecoveryReceipt":
        created_at = values.pop("created_at", None) or utc_now()
        payload = {
            "artifact_schema": MESH_RECEIPT_SCHEMA,
            "mesh_schema_version": MESH_SCHEMA_VERSION,
            "status": "recovered",
            "action": values["action"],
            "mesh_id": str(values["mesh_id"]),
            "transaction_id": str(values.get("transaction_id")) if values.get("transaction_id") else None,
            "revision": str(values.get("revision")) if values.get("revision") else None,
            "reason": values["reason"],
            "created_at": created_at,
            "claim_boundary": values.get("claim_boundary", MESH_RECEIPT_CLAIM_BOUNDARY),
        }
        return cls(receipt_id=_receipt_id("recovery", payload), created_at=created_at, **values)

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_id": str(self.receipt_id)}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MeshRecoveryReceipt":
        transaction_id = _require(raw, "transaction_id")
        revision = _require(raw, "revision")
        return cls(
            receipt_id=MeshReceiptId.parse(_require(raw, "receipt_id")),
            action=str(_require(raw, "action")),
            mesh_id=MeshId.parse(_require(raw, "mesh_id")),
            transaction_id=(MeshTransactionId.parse(transaction_id) if transaction_id else None),
            revision=MeshRevision.parse(revision) if revision else None,
            reason=str(_require(raw, "reason")),
            created_at=str(_require(raw, "created_at")),
            claim_boundary=str(_require(raw, "claim_boundary")),
            status=str(_require(raw, "status")),
            artifact_schema=str(_require(raw, "artifact_schema")),
            mesh_schema_version=str(_require(raw, "mesh_schema_version")),
        )


@dataclass(frozen=True)
class MeshIndexRepairReceipt:
    receipt_id: MeshReceiptId
    mesh_id: MeshId
    mesh_revision: MeshRevision
    before_shard_digests: tuple[tuple[str, str], ...]
    after_shard_digests: tuple[tuple[str, str], ...]
    actor: str
    created_at: str
    claim_boundary: str = MESH_RECEIPT_CLAIM_BOUNDARY
    status: str = "repaired"
    artifact_schema: str = MESH_RECEIPT_SCHEMA
    mesh_schema_version: str = MESH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _check_schema(self.artifact_schema, MESH_RECEIPT_SCHEMA, self.mesh_schema_version)
        _check_fixed(self.status, "repaired", "status")
        object.__setattr__(self, "receipt_id", MeshReceiptId.parse(self.receipt_id))
        object.__setattr__(self, "mesh_id", MeshId.parse(self.mesh_id))
        object.__setattr__(self, "mesh_revision", MeshRevision.parse(self.mesh_revision))
        object.__setattr__(self, "before_shard_digests", tuple(sorted(self.before_shard_digests)))
        object.__setattr__(self, "after_shard_digests", tuple(sorted(self.after_shard_digests)))
        if self.receipt_id != _receipt_id("index-repair", self.payload()):
            raise MeshReceiptError("index repair receipt ID mismatch")

    def payload(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "mesh_schema_version": self.mesh_schema_version,
            "status": self.status,
            "mesh_id": str(self.mesh_id),
            "mesh_revision": str(self.mesh_revision),
            "before_shard_digests": dict(self.before_shard_digests),
            "after_shard_digests": dict(self.after_shard_digests),
            "actor": self.actor,
            "created_at": self.created_at,
            "claim_boundary": self.claim_boundary,
        }

    @classmethod
    def create(cls, **values: Any) -> "MeshIndexRepairReceipt":
        created_at = values.pop("created_at", None) or utc_now()
        payload = {
            "artifact_schema": MESH_RECEIPT_SCHEMA,
            "mesh_schema_version": MESH_SCHEMA_VERSION,
            "status": "repaired",
            "mesh_id": str(values["mesh_id"]),
            "mesh_revision": str(values["mesh_revision"]),
            "before_shard_digests": dict(values["before_shard_digests"]),
            "after_shard_digests": dict(values["after_shard_digests"]),
            "actor": values["actor"],
            "created_at": created_at,
            "claim_boundary": values.get("claim_boundary", MESH_RECEIPT_CLAIM_BOUNDARY),
        }
        return cls(receipt_id=_receipt_id("index-repair", payload), created_at=created_at, **values)

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_id": str(self.receipt_id)}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MeshIndexRepairReceipt":
        before = _require(raw, "before_shard_digests")
        after = _require(raw, "after_shard_digests")
        if not isinstance(before, Mapping) or not isinstance(after, Mapping):
            raise MeshReceiptError("index repair shard digests must be objects")
        return cls(
            receipt_id=MeshReceiptId.parse(_require(raw, "receipt_id")),
            mesh_id=MeshId.parse(_require(raw, "mesh_id")),
            mesh_revision=MeshRevision.parse(_require(raw, "mesh_revision")),
            before_shard_digests=tuple((str(key), str(value)) for key, value in before.items()),
            after_shard_digests=tuple((str(key), str(value)) for key, value in after.items()),
            actor=str(_require(raw, "actor")),
            created_at=str(_require(raw, "created_at")),
            claim_boundary=str(_require(raw, "claim_boundary")),
            status=str(_require(raw, "status")),
            artifact_schema=str(_require(raw, "artifact_schema")),
            mesh_schema_version=str(_require(raw, "mesh_schema_version")),
        )


@dataclass(frozen=True)
class MeshInvalidationReceipt:
    receipt_id: MeshReceiptId
    mesh_id: MeshId
    parent_mesh_revision: MeshRevision
    child_mesh_revision: MeshRevision
    catalog_baseline: OverlayCatalogPin
    catalog_snapshot_digest: str
    changed_dependencies: tuple[Mapping[str, Any], ...]
    affected_overlays: tuple[Mapping[str, Any], ...]
    unaffected_overlays: tuple[Mapping[str, Any], ...]
    created_at: str
    tool_fingerprint: str
    claim_boundary: str = MESH_RECEIPT_CLAIM_BOUNDARY
    status: str = "computed"
    artifact_schema: str = MESH_INVALIDATION_RECEIPT_SCHEMA
    mesh_schema_version: str = MESH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _check_schema(self.artifact_schema, MESH_INVALIDATION_RECEIPT_SCHEMA, self.mesh_schema_version)
        _check_fixed(self.status, "computed", "status")
        object.__setattr__(self, "receipt_id", MeshReceiptId.parse(self.receipt_id))
        object.__setattr__(self, "mesh_id", MeshId.parse(self.mesh_id))
        object.__setattr__(self, "parent_mesh_revision", MeshRevision.parse(self.parent_mesh_revision))
        object.__setattr__(self, "child_mesh_revision", MeshRevision.parse(self.child_mesh_revision))
        object.__setattr__(self, "changed_dependencies", tuple(_freeze(dict(item)) for item in self.changed_dependencies))
        object.__setattr__(self, "affected_overlays", tuple(_freeze(dict(item)) for item in self.affected_overlays))
        object.__setattr__(self, "unaffected_overlays", tuple(_freeze(dict(item)) for item in self.unaffected_overlays))
        if (
            self.catalog_baseline.mesh_id != self.mesh_id
            or self.catalog_baseline.mesh_revision != self.parent_mesh_revision
        ):
            raise MeshReceiptError("invalidation catalog baseline does not bind parent mesh")
        affected_ids = tuple(str(item.get("overlay_id", "")) for item in self.affected_overlays)
        unaffected_ids = tuple(str(item.get("overlay_id", "")) for item in self.unaffected_overlays)
        if any(not item for item in (*affected_ids, *unaffected_ids)):
            raise MeshReceiptError("invalidation overlay entries require overlay_id")
        if len(set(affected_ids)) != len(affected_ids) or len(set(unaffected_ids)) != len(unaffected_ids):
            raise MeshReceiptError("invalidation receipt contains duplicate overlay entries")
        if set(affected_ids).intersection(unaffected_ids):
            raise MeshReceiptError("one overlay cannot be both affected and unaffected")
        if self.receipt_id != _receipt_id("invalidation", self.payload()):
            raise MeshReceiptError("invalidation receipt ID mismatch")

    @property
    def invalidated_overlay_ids(self) -> tuple[MeshEvaluationId, ...]:
        return tuple(
            sorted(
                (MeshEvaluationId.parse(item["overlay_id"]) for item in self.affected_overlays),
                key=str,
            )
        )

    def payload(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "mesh_schema_version": self.mesh_schema_version,
            "status": self.status,
            "mesh_id": str(self.mesh_id),
            "parent_mesh_revision": str(self.parent_mesh_revision),
            "child_mesh_revision": str(self.child_mesh_revision),
            "catalog_baseline": self.catalog_baseline.to_dict(),
            "catalog_snapshot_digest": self.catalog_snapshot_digest,
            "changed_dependencies": [_thaw(item) for item in self.changed_dependencies],
            "affected_overlays": [_thaw(item) for item in self.affected_overlays],
            "unaffected_overlays": [_thaw(item) for item in self.unaffected_overlays],
            "created_at": self.created_at,
            "tool_fingerprint": self.tool_fingerprint,
            "claim_boundary": self.claim_boundary,
        }

    @classmethod
    def create(cls, **values: Any) -> "MeshInvalidationReceipt":
        created_at = values.pop("created_at", None) or utc_now()
        changed_dependencies = tuple(dict(item) for item in values["changed_dependencies"])
        affected_overlays = tuple(dict(item) for item in values["affected_overlays"])
        unaffected_overlays = tuple(dict(item) for item in values["unaffected_overlays"])
        payload = {
            "artifact_schema": MESH_INVALIDATION_RECEIPT_SCHEMA,
            "mesh_schema_version": MESH_SCHEMA_VERSION,
            "status": "computed",
            "mesh_id": str(values["mesh_id"]),
            "parent_mesh_revision": str(values["parent_mesh_revision"]),
            "child_mesh_revision": str(values["child_mesh_revision"]),
            "catalog_baseline": values["catalog_baseline"].to_dict(),
            "catalog_snapshot_digest": values["catalog_snapshot_digest"],
            "changed_dependencies": [dict(item) for item in changed_dependencies],
            "affected_overlays": [dict(item) for item in affected_overlays],
            "unaffected_overlays": [dict(item) for item in unaffected_overlays],
            "created_at": created_at,
            "tool_fingerprint": values["tool_fingerprint"],
            "claim_boundary": values.get("claim_boundary", MESH_RECEIPT_CLAIM_BOUNDARY),
        }
        return cls(
            receipt_id=_receipt_id("invalidation", payload),
            mesh_id=values["mesh_id"],
            parent_mesh_revision=values["parent_mesh_revision"],
            child_mesh_revision=values["child_mesh_revision"],
            catalog_baseline=values["catalog_baseline"],
            catalog_snapshot_digest=values["catalog_snapshot_digest"],
            changed_dependencies=changed_dependencies,
            affected_overlays=affected_overlays,
            unaffected_overlays=unaffected_overlays,
            created_at=created_at,
            tool_fingerprint=values["tool_fingerprint"],
            claim_boundary=values.get("claim_boundary", MESH_RECEIPT_CLAIM_BOUNDARY),
        )

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_id": str(self.receipt_id)}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MeshInvalidationReceipt":
        return cls(
            receipt_id=MeshReceiptId.parse(_require(raw, "receipt_id")),
            mesh_id=MeshId.parse(_require(raw, "mesh_id")),
            parent_mesh_revision=MeshRevision.parse(_require(raw, "parent_mesh_revision")),
            child_mesh_revision=MeshRevision.parse(_require(raw, "child_mesh_revision")),
            catalog_baseline=OverlayCatalogPin.from_dict(_require(raw, "catalog_baseline")),
            catalog_snapshot_digest=str(_require(raw, "catalog_snapshot_digest")),
            changed_dependencies=tuple(_require(raw, "changed_dependencies")),
            affected_overlays=tuple(_require(raw, "affected_overlays")),
            unaffected_overlays=tuple(_require(raw, "unaffected_overlays")),
            created_at=str(_require(raw, "created_at")),
            tool_fingerprint=str(_require(raw, "tool_fingerprint")),
            claim_boundary=str(_require(raw, "claim_boundary")),
            status=str(_require(raw, "status")),
            artifact_schema=str(_require(raw, "artifact_schema")),
            mesh_schema_version=str(_require(raw, "mesh_schema_version")),
        )


@dataclass(frozen=True)
class OverlayCatalogCommitReceipt:
    receipt_id: MeshReceiptId
    transaction_id: MeshTransactionId
    mesh_id: MeshId
    mesh_revision: MeshRevision
    catalog_revision: OverlayCatalogRevision
    parent_catalog_revision: OverlayCatalogRevision | None
    content_digest: str
    dependency_shard_digests: tuple[tuple[str, str], ...]
    overlay_ids: tuple[MeshEvaluationId, ...]
    idempotency_key: str
    actor: str
    committed_at: str
    claim_boundary: str = MESH_RECEIPT_CLAIM_BOUNDARY
    status: str = "committed"
    artifact_schema: str = MESH_RECEIPT_SCHEMA
    mesh_schema_version: str = MESH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _check_schema(self.artifact_schema, MESH_RECEIPT_SCHEMA, self.mesh_schema_version)
        _check_fixed(self.status, "committed", "status")
        object.__setattr__(self, "receipt_id", MeshReceiptId.parse(self.receipt_id))
        object.__setattr__(self, "transaction_id", MeshTransactionId.parse(self.transaction_id))
        object.__setattr__(self, "mesh_id", MeshId.parse(self.mesh_id))
        object.__setattr__(self, "mesh_revision", MeshRevision.parse(self.mesh_revision))
        object.__setattr__(self, "catalog_revision", OverlayCatalogRevision.parse(self.catalog_revision))
        if self.parent_catalog_revision is not None:
            object.__setattr__(self, "parent_catalog_revision", OverlayCatalogRevision.parse(self.parent_catalog_revision))
        object.__setattr__(self, "dependency_shard_digests", tuple(sorted(self.dependency_shard_digests)))
        object.__setattr__(self, "overlay_ids", tuple(sorted(set(self.overlay_ids), key=str)))
        if self.receipt_id != _receipt_id("catalog-commit", self.payload()):
            raise MeshReceiptError("catalog commit receipt ID mismatch")

    def payload(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "mesh_schema_version": self.mesh_schema_version,
            "status": self.status,
            "transaction_id": str(self.transaction_id),
            "mesh_id": str(self.mesh_id),
            "mesh_revision": str(self.mesh_revision),
            "catalog_revision": str(self.catalog_revision),
            "parent_catalog_revision": str(self.parent_catalog_revision) if self.parent_catalog_revision else None,
            "content_digest": self.content_digest,
            "dependency_shard_digests": dict(self.dependency_shard_digests),
            "overlay_ids": [str(item) for item in self.overlay_ids],
            "idempotency_key": self.idempotency_key,
            "actor": self.actor,
            "committed_at": self.committed_at,
            "claim_boundary": self.claim_boundary,
        }

    @classmethod
    def create(cls, **values: Any) -> "OverlayCatalogCommitReceipt":
        committed_at = values.pop("committed_at", None) or utc_now()
        payload = {
            "artifact_schema": MESH_RECEIPT_SCHEMA,
            "mesh_schema_version": MESH_SCHEMA_VERSION,
            "status": "committed",
            "transaction_id": str(values["transaction_id"]),
            "mesh_id": str(values["mesh_id"]),
            "mesh_revision": str(values["mesh_revision"]),
            "catalog_revision": str(values["catalog_revision"]),
            "parent_catalog_revision": str(values.get("parent_catalog_revision")) if values.get("parent_catalog_revision") else None,
            "content_digest": values["content_digest"],
            "dependency_shard_digests": dict(values["dependency_shard_digests"]),
            "overlay_ids": [str(item) for item in sorted(values["overlay_ids"], key=str)],
            "idempotency_key": values["idempotency_key"],
            "actor": values["actor"],
            "committed_at": committed_at,
            "claim_boundary": values.get("claim_boundary", MESH_RECEIPT_CLAIM_BOUNDARY),
        }
        return cls(receipt_id=_receipt_id("catalog-commit", payload), committed_at=committed_at, **values)

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_id": str(self.receipt_id)}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "OverlayCatalogCommitReceipt":
        parent = _require(raw, "parent_catalog_revision")
        shard_digests = _require(raw, "dependency_shard_digests")
        if not isinstance(shard_digests, Mapping):
            raise MeshReceiptError("catalog dependency_shard_digests must be an object")
        return cls(
            receipt_id=MeshReceiptId.parse(_require(raw, "receipt_id")),
            transaction_id=MeshTransactionId.parse(_require(raw, "transaction_id")),
            mesh_id=MeshId.parse(_require(raw, "mesh_id")),
            mesh_revision=MeshRevision.parse(_require(raw, "mesh_revision")),
            catalog_revision=OverlayCatalogRevision.parse(_require(raw, "catalog_revision")),
            parent_catalog_revision=(
                OverlayCatalogRevision.parse(parent) if parent else None
            ),
            content_digest=str(_require(raw, "content_digest")),
            dependency_shard_digests=tuple(
                (str(key), str(value)) for key, value in shard_digests.items()
            ),
            overlay_ids=tuple(
                MeshEvaluationId.parse(item) for item in _require(raw, "overlay_ids")
            ),
            idempotency_key=str(_require(raw, "idempotency_key")),
            actor=str(_require(raw, "actor")),
            committed_at=str(_require(raw, "committed_at")),
            claim_boundary=str(_require(raw, "claim_boundary")),
            status=str(_require(raw, "status")),
            artifact_schema=str(_require(raw, "artifact_schema")),
            mesh_schema_version=str(_require(raw, "mesh_schema_version")),
        )


@dataclass(frozen=True)
class MeshSimulationReceipt:
    receipt_id: MeshReceiptId
    mesh_id: MeshId
    base_mesh_revision: MeshRevision
    delta_digest: str
    affected_universe_fingerprint: str
    result_fingerprint: str
    tool_fingerprint: str
    limitations: tuple[str, ...]
    created_at: str
    authority: str = "simulation-only"
    claim_boundary: str = MESH_RECEIPT_CLAIM_BOUNDARY
    artifact_schema: str = MESH_SIMULATION_RECEIPT_SCHEMA
    mesh_schema_version: str = MESH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _check_schema(self.artifact_schema, MESH_SIMULATION_RECEIPT_SCHEMA, self.mesh_schema_version)
        object.__setattr__(self, "receipt_id", MeshReceiptId.parse(self.receipt_id))
        object.__setattr__(self, "mesh_id", MeshId.parse(self.mesh_id))
        object.__setattr__(self, "base_mesh_revision", MeshRevision.parse(self.base_mesh_revision))
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        if self.authority != "simulation-only":
            raise MeshReceiptError("simulation receipt cannot be production authority")
        if self.receipt_id != _receipt_id("simulation", self.payload()):
            raise MeshReceiptError("simulation receipt ID mismatch")

    def payload(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "mesh_schema_version": self.mesh_schema_version,
            "authority": self.authority,
            "mesh_id": str(self.mesh_id),
            "base_mesh_revision": str(self.base_mesh_revision),
            "delta_digest": self.delta_digest,
            "affected_universe_fingerprint": self.affected_universe_fingerprint,
            "result_fingerprint": self.result_fingerprint,
            "tool_fingerprint": self.tool_fingerprint,
            "limitations": list(self.limitations),
            "created_at": self.created_at,
            "claim_boundary": self.claim_boundary,
        }

    @classmethod
    def create(cls, **values: Any) -> "MeshSimulationReceipt":
        created_at = values.pop("created_at", None) or utc_now()
        payload = {
            "artifact_schema": MESH_SIMULATION_RECEIPT_SCHEMA,
            "mesh_schema_version": MESH_SCHEMA_VERSION,
            "authority": "simulation-only",
            "mesh_id": str(values["mesh_id"]),
            "base_mesh_revision": str(values["base_mesh_revision"]),
            "delta_digest": values["delta_digest"],
            "affected_universe_fingerprint": values["affected_universe_fingerprint"],
            "result_fingerprint": values["result_fingerprint"],
            "tool_fingerprint": values["tool_fingerprint"],
            "limitations": sorted(set(values.get("limitations", ()))),
            "created_at": created_at,
            "claim_boundary": values.get("claim_boundary", MESH_RECEIPT_CLAIM_BOUNDARY),
        }
        return cls(receipt_id=_receipt_id("simulation", payload), created_at=created_at, **values)

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_id": str(self.receipt_id)}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MeshSimulationReceipt":
        return cls(
            receipt_id=MeshReceiptId.parse(_require(raw, "receipt_id")),
            mesh_id=MeshId.parse(_require(raw, "mesh_id")),
            base_mesh_revision=MeshRevision.parse(_require(raw, "base_mesh_revision")),
            delta_digest=str(_require(raw, "delta_digest")),
            affected_universe_fingerprint=str(
                _require(raw, "affected_universe_fingerprint")
            ),
            result_fingerprint=str(_require(raw, "result_fingerprint")),
            tool_fingerprint=str(_require(raw, "tool_fingerprint")),
            limitations=tuple(_require(raw, "limitations")),
            created_at=str(_require(raw, "created_at")),
            authority=str(_require(raw, "authority")),
            claim_boundary=str(_require(raw, "claim_boundary")),
            artifact_schema=str(_require(raw, "artifact_schema")),
            mesh_schema_version=str(_require(raw, "mesh_schema_version")),
        )


@dataclass(frozen=True)
class MeshScaleReceipt:
    receipt_id: MeshReceiptId
    environment: Mapping[str, Any]
    fixture: Mapping[str, Any]
    io_counts: Mapping[str, Any]
    timing: Mapping[str, Any]
    memory: Mapping[str, Any]
    thresholds: tuple[Mapping[str, Any], ...]
    overall_passed: bool
    created_at: str
    claim_boundary: str
    artifact_schema: str = MESH_SCALE_RECEIPT_SCHEMA
    mesh_schema_version: str = MESH_SCHEMA_VERSION

    REQUIRED_SECTIONS = ("environment", "fixture", "io_counts", "timing", "memory")

    def __post_init__(self) -> None:
        _check_schema(self.artifact_schema, MESH_SCALE_RECEIPT_SCHEMA, self.mesh_schema_version)
        object.__setattr__(self, "receipt_id", MeshReceiptId.parse(self.receipt_id))
        for name in self.REQUIRED_SECTIONS:
            value = dict(getattr(self, name) or {})
            if not value:
                raise MeshReceiptError(f"scale receipt section is empty: {name}")
            object.__setattr__(self, name, _freeze(value))
        object.__setattr__(self, "thresholds", tuple(_freeze(dict(item)) for item in self.thresholds))
        if not self.thresholds or any("passed" not in item for item in self.thresholds):
            raise MeshReceiptError("scale receipt requires explicit threshold outcomes")
        computed = all(bool(item["passed"]) for item in self.thresholds)
        if self.overall_passed != computed:
            raise MeshReceiptError("scale overall_passed disagrees with thresholds")
        if self.receipt_id != _receipt_id("scale", self.payload()):
            raise MeshReceiptError("scale receipt ID mismatch")

    def payload(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "mesh_schema_version": self.mesh_schema_version,
            "environment": _thaw(self.environment),
            "fixture": _thaw(self.fixture),
            "io_counts": _thaw(self.io_counts),
            "timing": _thaw(self.timing),
            "memory": _thaw(self.memory),
            "thresholds": [_thaw(item) for item in self.thresholds],
            "overall_passed": self.overall_passed,
            "created_at": self.created_at,
            "claim_boundary": self.claim_boundary,
        }

    @classmethod
    def create(cls, **values: Any) -> "MeshScaleReceipt":
        created_at = values.pop("created_at", None) or utc_now()
        payload = {
            "artifact_schema": MESH_SCALE_RECEIPT_SCHEMA,
            "mesh_schema_version": MESH_SCHEMA_VERSION,
            "environment": dict(values["environment"]),
            "fixture": dict(values["fixture"]),
            "io_counts": dict(values["io_counts"]),
            "timing": dict(values["timing"]),
            "memory": dict(values["memory"]),
            "thresholds": [dict(item) for item in values["thresholds"]],
            "overall_passed": bool(values["overall_passed"]),
            "created_at": created_at,
            "claim_boundary": values["claim_boundary"],
        }
        return cls(receipt_id=_receipt_id("scale", payload), created_at=created_at, **values)

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_id": str(self.receipt_id)}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MeshScaleReceipt":
        return cls(
            receipt_id=MeshReceiptId.parse(_require(raw, "receipt_id")),
            environment=dict(_require(raw, "environment")),
            fixture=dict(_require(raw, "fixture")),
            io_counts=dict(_require(raw, "io_counts")),
            timing=dict(_require(raw, "timing")),
            memory=dict(_require(raw, "memory")),
            thresholds=tuple(_require(raw, "thresholds")),
            overall_passed=bool(_require(raw, "overall_passed")),
            created_at=str(_require(raw, "created_at")),
            claim_boundary=str(_require(raw, "claim_boundary")),
            artifact_schema=str(_require(raw, "artifact_schema")),
            mesh_schema_version=str(_require(raw, "mesh_schema_version")),
        )


__all__ = [
    "MESH_RECEIPT_CLAIM_BOUNDARY",
    "MeshAbortReceipt",
    "MeshCommitReceipt",
    "MeshConflictReceipt",
    "MeshIndexRepairReceipt",
    "MeshInvalidationReceipt",
    "MeshReceiptError",
    "MeshRecoveryReceipt",
    "MeshScaleReceipt",
    "MeshSimulationReceipt",
    "OverlayCatalogCommitReceipt",
]
