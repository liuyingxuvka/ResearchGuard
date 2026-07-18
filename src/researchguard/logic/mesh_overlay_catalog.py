"""Independent CAS-versioned overlay dependency authority for ModelMesh."""

from __future__ import annotations

import copy
import hashlib
import uuid
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Protocol

from .identity import (
    MeshEvaluationId,
    MeshId,
    MeshRevision,
    MeshTransactionId,
    OverlayCatalogRevision,
)
from .mesh_overlay import MeshEvaluationOverlay, OverlayDependencyBinding
from .mesh_receipts import MeshAbortReceipt, OverlayCatalogCommitReceipt
from .model_mesh import MeshShardRef, MeshShardSetRef, OverlayCatalogPin
from .model_store import canonical_digest, canonical_json_bytes
from .receipts import utc_now
from .schema import (
    MESH_OVERLAY_CATALOG_SNAPSHOT_SCHEMA,
    MESH_OVERLAY_DEPENDENCY_SHARD_SCHEMA,
    MESH_SCHEMA_VERSION,
)


CATALOG_DEPENDENCY_FORWARD_SHARD = "overlay-dependency-forward"
CATALOG_DEPENDENCY_REVERSE_SHARD = "overlay-dependency-reverse"
CATALOG_DEPENDENCY_SHARD_KINDS = (
    CATALOG_DEPENDENCY_FORWARD_SHARD,
    CATALOG_DEPENDENCY_REVERSE_SHARD,
)


class OverlayCatalogError(RuntimeError):
    """Catalog authority is incomplete, non-current, or inconsistent."""


class OverlayCatalogTransactionStateError(OverlayCatalogError):
    """A catalog transaction was used outside its legal state."""


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
        raise OverlayCatalogError(f"required catalog field is missing: {key}")
    return raw[key]


def derive_overlay_catalog_revision(
    *,
    mesh_id: MeshId,
    mesh_revision: MeshRevision,
    parent_revision: OverlayCatalogRevision | None,
    content_digest: str,
) -> OverlayCatalogRevision:
    digest = hashlib.sha256(
        canonical_json_bytes(
            {
                "mesh_schema_version": MESH_SCHEMA_VERSION,
                "mesh_id": str(mesh_id),
                "mesh_revision": str(mesh_revision),
                "parent_catalog_revision": (
                    str(parent_revision) if parent_revision else None
                ),
                "content_digest": content_digest,
            }
        )
    ).hexdigest()
    return OverlayCatalogRevision(f"catalog-rev-{digest}")


@dataclass(frozen=True, order=True)
class OverlayCatalogEntry:
    overlay_id: MeshEvaluationId
    overlay_digest: str
    dependency_binding_digest: str
    profile: str
    authority: str
    registered_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "overlay_id", MeshEvaluationId.parse(self.overlay_id))
        if not self.overlay_digest.startswith("sha256:"):
            raise OverlayCatalogError("overlay_digest must use sha256")
        if not self.dependency_binding_digest.startswith("sha256:"):
            raise OverlayCatalogError("dependency_binding_digest must use sha256")
        if self.profile not in {"broad", "bounded"}:
            raise OverlayCatalogError("catalog entry profile must be broad or bounded")
        if self.authority != "production":
            raise OverlayCatalogError("production catalog cannot register simulation authority")
        if not self.registered_at:
            raise OverlayCatalogError("catalog entry requires registered_at")

    @classmethod
    def from_overlay(
        cls, overlay: MeshEvaluationOverlay, *, registered_at: str
    ) -> "OverlayCatalogEntry":
        if overlay.authority != "production":
            raise OverlayCatalogError("simulation overlay cannot enter production catalog")
        return cls(
            overlay_id=overlay.evaluation_id,
            overlay_digest=overlay.fingerprint,
            dependency_binding_digest=overlay.dependency_binding.digest,
            profile=overlay.profile,
            authority=overlay.authority,
            registered_at=registered_at,
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "overlay_id": str(self.overlay_id),
            "overlay_digest": self.overlay_digest,
            "dependency_binding_digest": self.dependency_binding_digest,
            "profile": self.profile,
            "authority": self.authority,
            "registered_at": self.registered_at,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "OverlayCatalogEntry":
        return cls(
            overlay_id=MeshEvaluationId.parse(_require(raw, "overlay_id")),
            overlay_digest=str(_require(raw, "overlay_digest")),
            dependency_binding_digest=str(_require(raw, "dependency_binding_digest")),
            profile=str(_require(raw, "profile")),
            authority=str(_require(raw, "authority")),
            registered_at=str(_require(raw, "registered_at")),
        )


@dataclass(frozen=True)
class OverlayDependencyShard:
    mesh_id: MeshId
    mesh_revision: MeshRevision
    content_basis_digest: str
    kind: str
    partition: str
    records: tuple[Mapping[str, Any], ...]
    digest: str
    artifact_schema: str = MESH_OVERLAY_DEPENDENCY_SHARD_SCHEMA
    mesh_schema_version: str = MESH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "mesh_id", MeshId.parse(self.mesh_id))
        object.__setattr__(self, "mesh_revision", MeshRevision.parse(self.mesh_revision))
        if self.artifact_schema != MESH_OVERLAY_DEPENDENCY_SHARD_SCHEMA:
            raise OverlayCatalogError("unsupported overlay dependency shard schema")
        if self.mesh_schema_version != MESH_SCHEMA_VERSION:
            raise OverlayCatalogError("unsupported mesh schema version")
        if self.kind not in CATALOG_DEPENDENCY_SHARD_KINDS:
            raise OverlayCatalogError(f"unsupported catalog shard kind: {self.kind!r}")
        if self.partition != "all":
            raise OverlayCatalogError("current catalog shard partition must be explicit 'all'")
        records = tuple(
            MappingProxyType(dict(item))
            for item in sorted(
                (dict(record) for record in self.records), key=canonical_json_bytes
            )
        )
        object.__setattr__(self, "records", records)
        expected = canonical_digest(self.fingerprint_payload())
        if self.digest != expected:
            raise OverlayCatalogError(
                f"catalog shard digest mismatch for {self.kind}: {self.digest} != {expected}"
            )

    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "mesh_schema_version": self.mesh_schema_version,
            "mesh_id": str(self.mesh_id),
            "mesh_revision": str(self.mesh_revision),
            "content_basis_digest": self.content_basis_digest,
            "kind": self.kind,
            "partition": self.partition,
            "records": [dict(item) for item in self.records],
        }

    @classmethod
    def create(
        cls,
        *,
        mesh_id: MeshId,
        mesh_revision: MeshRevision,
        content_basis_digest: str,
        kind: str,
        records: Iterable[Mapping[str, Any]],
    ) -> "OverlayDependencyShard":
        payload = {
            "artifact_schema": MESH_OVERLAY_DEPENDENCY_SHARD_SCHEMA,
            "mesh_schema_version": MESH_SCHEMA_VERSION,
            "mesh_id": str(mesh_id),
            "mesh_revision": str(mesh_revision),
            "content_basis_digest": content_basis_digest,
            "kind": kind,
            "partition": "all",
            "records": sorted((dict(item) for item in records), key=canonical_json_bytes),
        }
        return cls(
            mesh_id=mesh_id,
            mesh_revision=mesh_revision,
            content_basis_digest=content_basis_digest,
            kind=kind,
            partition="all",
            records=tuple(payload["records"]),
            digest=canonical_digest(payload),
        )

    @property
    def ref(self) -> MeshShardRef:
        return MeshShardRef(
            kind=self.kind,
            partition=self.partition,
            digest=self.digest,
            record_count=len(self.records),
            byte_count=len(canonical_json_bytes(self.to_dict())),
        )

    def to_dict(self) -> dict[str, Any]:
        return {**self.fingerprint_payload(), "digest": self.digest}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "OverlayDependencyShard":
        return cls(
            artifact_schema=str(_require(raw, "artifact_schema")),
            mesh_schema_version=str(_require(raw, "mesh_schema_version")),
            mesh_id=MeshId.parse(_require(raw, "mesh_id")),
            mesh_revision=MeshRevision.parse(_require(raw, "mesh_revision")),
            content_basis_digest=str(_require(raw, "content_basis_digest")),
            kind=str(_require(raw, "kind")),
            partition=str(_require(raw, "partition")),
            records=tuple(_require(raw, "records")),
            digest=str(_require(raw, "digest")),
        )


@dataclass(frozen=True)
class OverlayDependencyShardBundle:
    content_basis_digest: str
    shards: tuple[OverlayDependencyShard, ...]

    def __post_init__(self) -> None:
        shards = tuple(sorted(self.shards, key=lambda item: item.kind))
        if tuple(item.kind for item in shards) != tuple(
            sorted(CATALOG_DEPENDENCY_SHARD_KINDS)
        ):
            raise OverlayCatalogError("catalog bundle requires both exact dependency shards")
        if any(item.content_basis_digest != self.content_basis_digest for item in shards):
            raise OverlayCatalogError("catalog shard content basis mismatch")
        object.__setattr__(self, "shards", shards)

    @property
    def shard_sets(self) -> tuple[MeshShardSetRef, ...]:
        return tuple(
            MeshShardSetRef(
                kind=shard.kind,
                partition_scheme="single-explicit-v1",
                partitions=(shard.ref,),
            )
            for shard in self.shards
        )

    def by_kind(self, kind: str) -> OverlayDependencyShard:
        for shard in self.shards:
            if shard.kind == kind:
                return shard
        raise OverlayCatalogError(f"required catalog shard is missing: {kind}")


def _catalog_basis(
    entries: Iterable[OverlayCatalogEntry],
    bindings: Iterable[OverlayDependencyBinding],
) -> str:
    return canonical_digest(
        {
            "entries": [
                item.to_dict() for item in sorted(entries, key=lambda value: str(value.overlay_id))
            ],
            "dependency_bindings": [
                item.to_dict()
                for item in sorted(bindings, key=lambda value: value.digest)
            ],
        }
    )


def compile_overlay_dependency_shards(
    *,
    mesh_id: MeshId,
    mesh_revision: MeshRevision,
    entries: Iterable[OverlayCatalogEntry],
    bindings: Iterable[OverlayDependencyBinding],
) -> OverlayDependencyShardBundle:
    entries = tuple(sorted(entries, key=lambda item: str(item.overlay_id)))
    bindings = tuple(sorted(bindings, key=lambda item: item.digest))
    binding_by_digest = {item.digest: item for item in bindings}
    if len(binding_by_digest) != len(bindings):
        raise OverlayCatalogError("duplicate dependency binding digest")
    forward: list[dict[str, Any]] = []
    reverse: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in entries:
        binding = binding_by_digest.get(entry.dependency_binding_digest)
        if binding is None:
            raise OverlayCatalogError(
                f"catalog entry {entry.overlay_id} has no dependency binding"
            )
        forward.append(
            {
                "overlay_id": str(entry.overlay_id),
                "dependency_binding_digest": binding.digest,
                "dependency_keys": [item.to_dict() for item in binding.dependency_keys],
            }
        )
        for key in binding.dependency_keys:
            aggregate = reverse.setdefault(
                (key.kind, key.identity_digest),
                {
                    "kind": key.kind,
                    "identity_digest": key.identity_digest,
                    "dependency_key": key.to_dict(),
                    "overlay_ids": [],
                },
            )
            aggregate["overlay_ids"].append(str(entry.overlay_id))
    for item in reverse.values():
        item["overlay_ids"] = sorted(set(item["overlay_ids"]))
    basis = _catalog_basis(entries, bindings)
    shards = (
        OverlayDependencyShard.create(
            mesh_id=mesh_id,
            mesh_revision=mesh_revision,
            content_basis_digest=basis,
            kind=CATALOG_DEPENDENCY_FORWARD_SHARD,
            records=forward,
        ),
        OverlayDependencyShard.create(
            mesh_id=mesh_id,
            mesh_revision=mesh_revision,
            content_basis_digest=basis,
            kind=CATALOG_DEPENDENCY_REVERSE_SHARD,
            records=reverse.values(),
        ),
    )
    return OverlayDependencyShardBundle(content_basis_digest=basis, shards=shards)


@dataclass(frozen=True)
class OverlayCatalogSnapshot:
    mesh_id: MeshId
    mesh_revision: MeshRevision
    revision: OverlayCatalogRevision
    parent_revision: OverlayCatalogRevision | None
    content_digest: str
    entries: tuple[OverlayCatalogEntry, ...]
    dependency_bindings: tuple[OverlayDependencyBinding, ...]
    dependency_shard_sets: tuple[MeshShardSetRef, ...]
    invalidation_receipt_id: str | None
    invalidation_receipt_digest: str | None
    created_at: str
    created_by: str
    artifact_schema: str = MESH_OVERLAY_CATALOG_SNAPSHOT_SCHEMA
    mesh_schema_version: str = MESH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "mesh_id", MeshId.parse(self.mesh_id))
        object.__setattr__(self, "mesh_revision", MeshRevision.parse(self.mesh_revision))
        object.__setattr__(self, "revision", OverlayCatalogRevision.parse(self.revision))
        if self.parent_revision is not None:
            object.__setattr__(
                self, "parent_revision", OverlayCatalogRevision.parse(self.parent_revision)
            )
        if self.artifact_schema != MESH_OVERLAY_CATALOG_SNAPSHOT_SCHEMA:
            raise OverlayCatalogError("unsupported overlay catalog snapshot schema")
        if self.mesh_schema_version != MESH_SCHEMA_VERSION:
            raise OverlayCatalogError("unsupported mesh schema version")
        entries = tuple(sorted(self.entries, key=lambda item: str(item.overlay_id)))
        if len({item.overlay_id for item in entries}) != len(entries):
            raise OverlayCatalogError("duplicate overlay ID in catalog")
        bindings = tuple(sorted(self.dependency_bindings, key=lambda item: item.digest))
        if len({item.digest for item in bindings}) != len(bindings):
            raise OverlayCatalogError("duplicate dependency binding in catalog")
        if any(
            item.mesh_id != self.mesh_id or item.mesh_revision != self.mesh_revision
            for item in bindings
        ):
            raise OverlayCatalogError("catalog dependency binding pins another mesh revision")
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "dependency_bindings", bindings)
        object.__setattr__(
            self,
            "dependency_shard_sets",
            tuple(sorted(self.dependency_shard_sets, key=lambda item: item.kind)),
        )
        if bool(self.invalidation_receipt_id) != bool(self.invalidation_receipt_digest):
            raise OverlayCatalogError("catalog invalidation receipt ID and digest must be paired")
        if self.invalidation_receipt_digest and not self.invalidation_receipt_digest.startswith(
            "sha256:"
        ):
            raise OverlayCatalogError("catalog invalidation receipt digest must use sha256")
        if not self.created_at or not self.created_by:
            raise OverlayCatalogError("catalog snapshot requires creation identity")
        expected_content = canonical_digest(self.semantic_dict())
        if self.content_digest != expected_content:
            raise OverlayCatalogError(
                f"catalog content digest mismatch: {self.content_digest} != {expected_content}"
            )
        expected_revision = derive_overlay_catalog_revision(
            mesh_id=self.mesh_id,
            mesh_revision=self.mesh_revision,
            parent_revision=self.parent_revision,
            content_digest=self.content_digest,
        )
        if self.revision != expected_revision:
            raise OverlayCatalogError(
                f"catalog revision mismatch: {self.revision} != {expected_revision}"
            )

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "mesh_schema_version": self.mesh_schema_version,
            "mesh_id": str(self.mesh_id),
            "mesh_revision": str(self.mesh_revision),
            "entries": [item.to_dict() for item in self.entries],
            "dependency_bindings": [item.to_dict() for item in self.dependency_bindings],
            "dependency_shard_sets": [item.to_dict() for item in self.dependency_shard_sets],
            "invalidation_receipt_id": self.invalidation_receipt_id,
            "invalidation_receipt_digest": self.invalidation_receipt_digest,
        }

    @classmethod
    def create(
        cls,
        *,
        mesh_id: MeshId,
        mesh_revision: MeshRevision,
        parent_revision: OverlayCatalogRevision | None,
        entries: Iterable[OverlayCatalogEntry],
        dependency_bindings: Iterable[OverlayDependencyBinding],
        dependency_shard_sets: Iterable[MeshShardSetRef],
        invalidation_receipt_id: str | None,
        invalidation_receipt_digest: str | None,
        created_at: str,
        created_by: str,
    ) -> "OverlayCatalogSnapshot":
        semantic = {
            "mesh_schema_version": MESH_SCHEMA_VERSION,
            "mesh_id": str(mesh_id),
            "mesh_revision": str(mesh_revision),
            "entries": [
                item.to_dict()
                for item in sorted(entries, key=lambda value: str(value.overlay_id))
            ],
            "dependency_bindings": [
                item.to_dict()
                for item in sorted(dependency_bindings, key=lambda value: value.digest)
            ],
            "dependency_shard_sets": [
                item.to_dict()
                for item in sorted(dependency_shard_sets, key=lambda value: value.kind)
            ],
            "invalidation_receipt_id": invalidation_receipt_id,
            "invalidation_receipt_digest": invalidation_receipt_digest,
        }
        content_digest = canonical_digest(semantic)
        revision = derive_overlay_catalog_revision(
            mesh_id=mesh_id,
            mesh_revision=mesh_revision,
            parent_revision=parent_revision,
            content_digest=content_digest,
        )
        return cls(
            mesh_id=mesh_id,
            mesh_revision=mesh_revision,
            revision=revision,
            parent_revision=parent_revision,
            content_digest=content_digest,
            entries=tuple(entries),
            dependency_bindings=tuple(dependency_bindings),
            dependency_shard_sets=tuple(dependency_shard_sets),
            invalidation_receipt_id=invalidation_receipt_id,
            invalidation_receipt_digest=invalidation_receipt_digest,
            created_at=created_at,
            created_by=created_by,
        )

    @property
    def pin(self) -> OverlayCatalogPin:
        return OverlayCatalogPin(
            mesh_id=self.mesh_id,
            mesh_revision=self.mesh_revision,
            catalog_revision=self.revision,
            catalog_content_digest=self.content_digest,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "mesh_schema_version": self.mesh_schema_version,
            "mesh_id": str(self.mesh_id),
            "mesh_revision": str(self.mesh_revision),
            "revision": str(self.revision),
            "parent_revision": str(self.parent_revision) if self.parent_revision else None,
            "content_digest": self.content_digest,
            "entries": [item.to_dict() for item in self.entries],
            "dependency_bindings": [item.to_dict() for item in self.dependency_bindings],
            "dependency_shard_sets": [item.to_dict() for item in self.dependency_shard_sets],
            "invalidation_receipt_id": self.invalidation_receipt_id,
            "invalidation_receipt_digest": self.invalidation_receipt_digest,
            "created_at": self.created_at,
            "created_by": self.created_by,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "OverlayCatalogSnapshot":
        parent = _require(raw, "parent_revision")
        return cls(
            artifact_schema=str(_require(raw, "artifact_schema")),
            mesh_schema_version=str(_require(raw, "mesh_schema_version")),
            mesh_id=MeshId.parse(_require(raw, "mesh_id")),
            mesh_revision=MeshRevision.parse(_require(raw, "mesh_revision")),
            revision=OverlayCatalogRevision.parse(_require(raw, "revision")),
            parent_revision=OverlayCatalogRevision.parse(parent) if parent else None,
            content_digest=str(_require(raw, "content_digest")),
            entries=tuple(
                OverlayCatalogEntry.from_dict(item) for item in _require(raw, "entries")
            ),
            dependency_bindings=tuple(
                OverlayDependencyBinding.from_dict(item)
                for item in _require(raw, "dependency_bindings")
            ),
            dependency_shard_sets=tuple(
                MeshShardSetRef.from_dict(item)
                for item in _require(raw, "dependency_shard_sets")
            ),
            invalidation_receipt_id=_require(raw, "invalidation_receipt_id"),
            invalidation_receipt_digest=_require(raw, "invalidation_receipt_digest"),
            created_at=str(_require(raw, "created_at")),
            created_by=str(_require(raw, "created_by")),
        )

    def binding_for(self, entry: OverlayCatalogEntry) -> OverlayDependencyBinding:
        for binding in self.dependency_bindings:
            if binding.digest == entry.dependency_binding_digest:
                return binding
        raise OverlayCatalogError(f"binding missing for overlay {entry.overlay_id}")

    def dependents(self, dependency_digests: Iterable[str]) -> tuple[MeshEvaluationId, ...]:
        requested = set(dependency_digests)
        found = {
            entry.overlay_id
            for entry in self.entries
            if any(
                key.identity_digest in requested
                for key in self.binding_for(entry).dependency_keys
            )
        }
        return tuple(sorted(found, key=str))


def create_catalog_snapshot(
    *,
    mesh_id: MeshId,
    mesh_revision: MeshRevision,
    parent_revision: OverlayCatalogRevision | None,
    entries: Iterable[OverlayCatalogEntry],
    dependency_bindings: Iterable[OverlayDependencyBinding],
    invalidation_receipt_id: str | None,
    invalidation_receipt_digest: str | None,
    created_at: str,
    created_by: str,
) -> tuple[OverlayCatalogSnapshot, OverlayDependencyShardBundle]:
    entries = tuple(entries)
    bindings = tuple(dependency_bindings)
    bundle = compile_overlay_dependency_shards(
        mesh_id=mesh_id,
        mesh_revision=mesh_revision,
        entries=entries,
        bindings=bindings,
    )
    snapshot = OverlayCatalogSnapshot.create(
        mesh_id=mesh_id,
        mesh_revision=mesh_revision,
        parent_revision=parent_revision,
        entries=entries,
        dependency_bindings=bindings,
        dependency_shard_sets=bundle.shard_sets,
        invalidation_receipt_id=invalidation_receipt_id,
        invalidation_receipt_digest=invalidation_receipt_digest,
        created_at=created_at,
        created_by=created_by,
    )
    return snapshot, bundle


class _CatalogTransactionBackend(Protocol):
    def _commit_catalog_transaction(
        self,
        transaction: "OverlayCatalogTransaction",
        overlay: MeshEvaluationOverlay,
    ) -> OverlayCatalogCommitReceipt: ...

    def _abort_catalog_transaction(
        self, transaction: "OverlayCatalogTransaction", reason: str
    ) -> MeshAbortReceipt: ...


class OverlayCatalogTransaction:
    """One exact catalog CAS attempt; it never refreshes a floating head."""

    def __init__(
        self,
        *,
        store: _CatalogTransactionBackend,
        mesh_id: MeshId | str,
        mesh_revision: MeshRevision | str,
        expected_catalog_revision: OverlayCatalogRevision | str,
        idempotency_key: str,
        actor: str,
        transaction_id: MeshTransactionId | str | None = None,
    ) -> None:
        self._store = store
        self.mesh_id = MeshId.parse(mesh_id)
        self.mesh_revision = MeshRevision.parse(mesh_revision)
        self.expected_catalog_revision = OverlayCatalogRevision.parse(
            expected_catalog_revision
        )
        MeshTransactionId(str(idempotency_key))
        self.idempotency_key = str(idempotency_key)
        self.actor = str(actor).strip()
        if not self.actor:
            raise ValueError("catalog transaction actor must not be empty")
        self.transaction_id = MeshTransactionId.parse(
            transaction_id or f"mesh-catalog-tx-{uuid.uuid4().hex}"
        )
        self._overlay: MeshEvaluationOverlay | None = None
        self._terminal_receipt: OverlayCatalogCommitReceipt | MeshAbortReceipt | None = None
        self._state = "open"

    @property
    def state(self) -> str:
        return self._state

    @property
    def staged_overlay(self) -> MeshEvaluationOverlay | None:
        return self._overlay

    def stage(self, overlay: MeshEvaluationOverlay) -> str:
        if self._state not in {"open", "staged"}:
            raise OverlayCatalogTransactionStateError(
                f"cannot stage catalog transaction in state {self._state}"
            )
        if overlay.authority != "production":
            raise OverlayCatalogError("simulation overlay cannot enter production catalog")
        if overlay.mesh_id != self.mesh_id or overlay.mesh_revision != self.mesh_revision:
            raise OverlayCatalogError("overlay does not bind catalog mesh revision")
        self._overlay = overlay
        self._state = "staged"
        return overlay.fingerprint

    def commit(self) -> OverlayCatalogCommitReceipt:
        if self._state == "committed" and isinstance(
            self._terminal_receipt, OverlayCatalogCommitReceipt
        ):
            return self._terminal_receipt
        if self._state != "staged" or self._overlay is None:
            raise OverlayCatalogTransactionStateError(
                f"cannot commit catalog transaction in state {self._state}"
            )
        receipt = self._store._commit_catalog_transaction(self, self._overlay)
        self._terminal_receipt = receipt
        self._state = "committed"
        return receipt

    def abort(self, reason: str) -> MeshAbortReceipt:
        if self._state == "aborted" and isinstance(self._terminal_receipt, MeshAbortReceipt):
            return self._terminal_receipt
        if self._state == "committed":
            raise OverlayCatalogTransactionStateError("cannot abort committed catalog transaction")
        if not str(reason).strip():
            raise ValueError("catalog abort requires a reason")
        receipt = self._store._abort_catalog_transaction(self, str(reason).strip())
        self._terminal_receipt = receipt
        self._state = "aborted"
        return receipt


__all__ = [
    "CATALOG_DEPENDENCY_FORWARD_SHARD",
    "CATALOG_DEPENDENCY_REVERSE_SHARD",
    "CATALOG_DEPENDENCY_SHARD_KINDS",
    "OverlayCatalogEntry",
    "OverlayCatalogError",
    "OverlayCatalogSnapshot",
    "OverlayCatalogTransaction",
    "OverlayCatalogTransactionStateError",
    "OverlayDependencyShard",
    "OverlayDependencyShardBundle",
    "compile_overlay_dependency_shards",
    "create_catalog_snapshot",
    "derive_overlay_catalog_revision",
]
