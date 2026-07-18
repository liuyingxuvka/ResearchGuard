"""Versioned immutable snapshots and the LogicGuard ModelStore protocol."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Protocol, runtime_checkable

from .identity import (
    EvaluationId,
    ModelId,
    ModelRevision,
    ReceiptId,
)
from .provenance import ProvenanceRecord, coerce_provenance
from .schema import MODEL_SNAPSHOT_SCHEMA, SCHEMA_VERSION


class ModelStoreError(RuntimeError):
    """Base class for durable store failures."""


class StoreSchemaError(ModelStoreError):
    """A durable artifact does not declare the sole current schema."""


class ModelNotFoundError(ModelStoreError):
    pass


class RevisionNotFoundError(ModelStoreError):
    pass


class EvaluationNotFoundError(ModelStoreError):
    pass


class TransactionStateError(ModelStoreError):
    pass


class TransactionConflictError(ModelStoreError):
    def __init__(
        self,
        *,
        model_id: ModelId,
        expected: ModelRevision | None,
        actual: ModelRevision | None,
        message: str | None = None,
        receipt: Any | None = None,
    ) -> None:
        self.model_id = model_id
        self.expected = expected
        self.actual = actual
        self.receipt = receipt
        super().__init__(
            message
            or (
                f"compare-and-swap conflict for {model_id}: "
                f"expected {expected or '<creation>'}, actual {actual or '<none>'}"
            )
        )


class IdempotencyConflictError(ModelStoreError):
    def __init__(self, message: str, *, receipt: Any | None = None) -> None:
        self.receipt = receipt
        super().__init__(message)


class WriterLockHeldError(ModelStoreError):
    pass


class RecoveryRequiredError(ModelStoreError):
    pass


class StoreCorruptionError(ModelStoreError):
    pass


class TombstonedModelError(ModelStoreError):
    def __init__(self, model_id: ModelId, *, reason: str, receipt_id: ReceiptId) -> None:
        self.model_id = model_id
        self.reason = reason
        self.receipt_id = receipt_id
        super().__init__(
            f"model {model_id} is tombstoned: {reason} (receipt {receipt_id}); "
            "request an exact historical revision to read retained evidence"
        )


def _json_value(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return _json_value(value.to_dict())
    if hasattr(value, "value") and isinstance(getattr(value, "value"), str):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_value(item) for item in value]
    return value


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize one semantic value deterministically for hashing and disk I/O."""

    return json.dumps(
        _json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return f"sha256:{hashlib.sha256(canonical_json_bytes(value)).hexdigest()}"


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


def canonical_model_payload(model: Any) -> dict[str, Any]:
    """Return canonical model content without transient evaluation state.

    ``LogicModel.canonical_dict`` is the primary authority.  Mapping support is
    intentionally narrow and useful for explicit import/test boundaries.
    """

    if hasattr(model, "canonical_dict"):
        raw = model.canonical_dict()
    elif isinstance(model, Mapping):
        # Explicit mapping inputs are normalized through the current authoring
        # model so omitted defaults and registry-key IDs cannot change merely
        # because a committed snapshot was loaded and re-frozen.
        from .loader import load_model_from_dict

        raw = load_model_from_dict(copy.deepcopy(dict(model)), validate=False).canonical_dict()
    elif hasattr(model, "to_dict"):
        raw = model.to_dict()
    else:
        raise TypeError("model must provide canonical_dict()/to_dict() or be a mapping")
    payload = _json_value(raw)
    if not isinstance(payload, dict):
        raise TypeError("canonical model payload must be a mapping")

    # Mapping inputs cannot carry evaluated truth into the durable graph.
    nodes = payload.get("nodes")
    if isinstance(nodes, Mapping):
        for node in nodes.values():
            if isinstance(node, dict):
                node.pop("state", None)
                node.pop("evaluated_state", None)
                node.pop("evaluation_state", None)
                node.pop("runtime_state", None)
                node.pop("forced_state", None)
    model_info = payload.get("model")
    if isinstance(model_info, dict):
        model_info.pop("source_path", None)
        # Snapshot bindings belong to a detached read projection, never to the
        # next revision's semantic content (which would self-fingerprint).
        model_info.pop("model_revision_id", None)
        model_info.pop("model_content_digest", None)
        for key in list(model_info):
            if str(key).startswith("_"):
                model_info.pop(key, None)
    provenance_locations: list[tuple[dict[str, Any], tuple[ProvenanceRecord, ...]]] = []
    for collection_name in ("nodes", "blocks"):
        collection = payload.get(collection_name)
        if isinstance(collection, Mapping):
            for item_id in sorted(collection):
                item = collection[item_id]
                if isinstance(item, dict) and item.get("provenance"):
                    provenance_locations.append(
                        (item, coerce_provenance(item["provenance"]))
                    )
    edges = payload.get("edges")
    if isinstance(edges, list):
        for edge in edges:
            if isinstance(edge, dict) and edge.get("provenance"):
                provenance_locations.append(
                    (edge, coerce_provenance(edge["provenance"]))
                )

    canonical_independence: dict[tuple[str, str], str] = {}
    for _, records in provenance_locations:
        for record in records:
            if not record.reviewed_separation:
                canonical_independence.setdefault(
                    record.source_content_key(), record.independence_group or ""
                )
    for _, records in provenance_locations:
        for record in records:
            canonical_independence.setdefault(
                record.source_content_key(), record.independence_group or ""
            )
    for container, records in provenance_locations:
        normalized_records: list[dict[str, Any]] = []
        for record in records:
            canonical_group = canonical_independence[record.source_content_key()]
            raw_record = record.to_dict()
            if record.independence_group != canonical_group and not record.reviewed_separation:
                raw_record["independence_group"] = canonical_group
            normalized_records.append(raw_record)
        container["provenance"] = normalized_records
    # Canonical JSON round-trip removes mapping subclasses and protects callers.
    return json.loads(canonical_json_bytes(payload).decode("utf-8"))


def derive_revision(
    *,
    model_id: ModelId,
    parent_revision: ModelRevision | None,
    content_digest: str,
) -> ModelRevision:
    binding = {
        "store_schema_version": SCHEMA_VERSION,
        "model_id": str(model_id),
        "parent_revision": str(parent_revision) if parent_revision else None,
        "content_digest": content_digest,
    }
    digest = hashlib.sha256(canonical_json_bytes(binding)).hexdigest()
    return ModelRevision(f"rev-{digest}")


@dataclass(frozen=True)
class ModelSnapshot:
    """Immutable envelope around one normalized authoring model revision."""

    model_id: ModelId
    revision: ModelRevision
    parent_revision: ModelRevision | None
    content_digest: str
    created_at: str
    created_by: str
    model_payload: Mapping[str, Any]
    provenance: tuple[ProvenanceRecord, ...] = ()
    artifact_schema: str = MODEL_SNAPSHOT_SCHEMA
    store_schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", ModelId.parse(self.model_id))
        object.__setattr__(self, "revision", ModelRevision.parse(self.revision))
        if self.parent_revision is not None:
            object.__setattr__(
                self, "parent_revision", ModelRevision.parse(self.parent_revision)
            )
        object.__setattr__(self, "provenance", coerce_provenance(self.provenance))
        object.__setattr__(self, "model_payload", _freeze(_thaw(self.model_payload)))
        if not self.created_at:
            raise ValueError("snapshot created_at must not be empty")
        if not self.created_by:
            raise ValueError("snapshot created_by must not be empty")
        if self.artifact_schema != MODEL_SNAPSHOT_SCHEMA:
            raise StoreSchemaError(
                f"snapshot schema {self.artifact_schema!r} is unsupported; "
                f"expected {MODEL_SNAPSHOT_SCHEMA!r}; use explicit import/upgrade"
            )
        if self.store_schema_version != SCHEMA_VERSION:
            raise StoreSchemaError(
                f"store schema {self.store_schema_version!r} is unsupported; "
                f"expected {SCHEMA_VERSION!r}; use explicit import/upgrade"
            )
        expected_digest = canonical_digest(self.model_payload)
        if self.content_digest != expected_digest:
            raise StoreCorruptionError(
                f"snapshot digest mismatch: found {self.content_digest}, expected {expected_digest}"
            )
        expected_revision = derive_revision(
            model_id=self.model_id,
            parent_revision=self.parent_revision,
            content_digest=self.content_digest,
        )
        if self.revision != expected_revision:
            raise StoreCorruptionError(
                f"snapshot revision mismatch: found {self.revision}, expected {expected_revision}"
            )

    @classmethod
    def create(
        cls,
        model: Any,
        *,
        parent_revision: ModelRevision | None,
        created_at: str,
        created_by: str,
        provenance: Iterable[ProvenanceRecord | Mapping[str, Any]] = (),
    ) -> "ModelSnapshot":
        payload = canonical_model_payload(model)
        model_info = payload.get("model")
        if not isinstance(model_info, Mapping) or not model_info.get("id"):
            raise ValueError("canonical model requires model.id")
        model_id = ModelId.parse(model_info["id"])
        parent = ModelRevision.parse(parent_revision) if parent_revision is not None else None
        digest = canonical_digest(payload)
        revision = derive_revision(
            model_id=model_id,
            parent_revision=parent,
            content_digest=digest,
        )
        return cls(
            model_id=model_id,
            revision=revision,
            parent_revision=parent,
            content_digest=digest,
            created_at=created_at,
            created_by=created_by,
            model_payload=payload,
            provenance=tuple(coerce_provenance(provenance)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "store_schema_version": self.store_schema_version,
            "model_id": str(self.model_id),
            "revision": str(self.revision),
            "parent_revision": str(self.parent_revision) if self.parent_revision else None,
            "content_digest": self.content_digest,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "provenance": [record.to_dict() for record in self.provenance],
            "model_payload": _thaw(self.model_payload),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ModelSnapshot":
        return cls(
            artifact_schema=str(raw.get("artifact_schema", "")),
            store_schema_version=str(raw.get("store_schema_version", "")),
            model_id=ModelId.parse(raw.get("model_id", "")),
            revision=ModelRevision.parse(raw.get("revision", "")),
            parent_revision=(
                ModelRevision.parse(raw["parent_revision"])
                if raw.get("parent_revision")
                else None
            ),
            content_digest=str(raw.get("content_digest", "")),
            created_at=str(raw.get("created_at", "")),
            created_by=str(raw.get("created_by", "")),
            provenance=tuple(
                ProvenanceRecord.from_dict(item)
                for item in (raw.get("provenance") or [])
            ),
            model_payload=dict(raw.get("model_payload") or {}),
        )

    def authoring_payload(self) -> dict[str, Any]:
        """Return a detached mutable authoring payload."""

        return _thaw(self.model_payload)

    @property
    def model(self) -> Any:
        """A fresh detached authoring projection for ergonomic read access."""

        return self.to_model()

    def to_model(self) -> Any:
        """Return a fresh transient ``LogicModel`` detached from store authority."""

        from .loader import load_model_from_dict

        model = load_model_from_dict(self.authoring_payload(), validate=False)
        model.metadata["model_revision_id"] = str(self.revision)
        model.metadata["model_content_digest"] = self.content_digest
        return model


@runtime_checkable
class ModelTransactionProtocol(Protocol):
    def stage(self, model: Any) -> str: ...

    def commit(self) -> Any: ...

    def abort(self, reason: str) -> Any: ...


@runtime_checkable
class ModelStore(Protocol):
    def head(self, model_id: ModelId | str) -> ModelRevision | None: ...

    def get(
        self, model_id: ModelId | str, revision: ModelRevision | str | None = None
    ) -> ModelSnapshot: ...

    def list_models(self) -> tuple[ModelId, ...]: ...

    def list_revisions(self, model_id: ModelId | str) -> tuple[ModelRevision, ...]: ...

    def begin(
        self,
        model_id: ModelId | str,
        expected_revision: ModelRevision | str | None,
        idempotency_key: str,
        actor: str,
    ) -> ModelTransactionProtocol: ...

    def put_evaluation(self, overlay: Any, expected_model_digest: str) -> Any: ...

    def get_evaluation(
        self,
        model_id: ModelId | str,
        revision: ModelRevision | str,
        evaluation_id: EvaluationId | str,
    ) -> Any: ...

    def recover(self) -> tuple[Any, ...]: ...


__all__ = [
    "IdempotencyConflictError",
    "EvaluationNotFoundError",
    "ModelNotFoundError",
    "ModelSnapshot",
    "ModelStore",
    "ModelStoreError",
    "ModelTransactionProtocol",
    "RecoveryRequiredError",
    "RevisionNotFoundError",
    "StoreCorruptionError",
    "StoreSchemaError",
    "TombstonedModelError",
    "TransactionConflictError",
    "TransactionStateError",
    "WriterLockHeldError",
    "canonical_digest",
    "canonical_json_bytes",
    "canonical_model_payload",
    "derive_revision",
]
