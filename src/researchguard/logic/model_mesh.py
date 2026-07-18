"""Pure product-runtime ModelMesh domain objects.

The mesh owns graph composition only.  P0 ``ModelSnapshot`` objects remain the
sole authority for node payloads, ArgumentBlocks, and local edges.
"""

from __future__ import annotations

import copy
import hashlib
import math
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Protocol

from .identity import (
    BlockId,
    EdgeId,
    MeshId,
    MeshRevision,
    ModelId,
    ModelRevision,
    NodeId,
    OverlayCatalogRevision,
    QualifiedModelRef,
    QualifiedNodeRef,
)
from .model_store import canonical_digest, canonical_json_bytes
from .provenance import OriginKind, ProvenanceRecord, coerce_provenance
from .schema import (
    EDGE_TYPES,
    MESH_INDEX_SHARD_SCHEMA,
    MESH_SCHEMA_VERSION,
    MESH_SNAPSHOT_SCHEMA,
)


class ModelMeshError(RuntimeError):
    """Base error for product-runtime mesh authority."""


class MeshSchemaError(ModelMeshError):
    """A durable mesh artifact is not the one current schema."""


class MeshValidationError(ModelMeshError):
    """A proposed mesh definition violates graph authority rules."""


class MeshIntegrityError(ModelMeshError):
    """A digest-bound mesh artifact is absent, corrupt, or inconsistent."""


class MeshNotFoundError(ModelMeshError):
    """The exact requested logical mesh does not exist."""


class MeshRevisionNotFoundError(ModelMeshError):
    """The exact requested mesh revision is not manifest-authorized."""


_ROLE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")
_FORBIDDEN_MEMBERSHIP_FIELDS = frozenset(
    {
        "acceptance",
        "blocks",
        "confidence",
        "member_nodes",
        "node_payload",
        "provenance_override",
        "root_claim",
        "state",
        "text",
        "type",
    }
)


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


def _require(raw: Mapping[str, Any], field_name: str) -> Any:
    if field_name not in raw:
        raise MeshIntegrityError(f"required field is missing: {field_name}")
    return raw[field_name]


def qualified_model_key(ref: QualifiedModelRef) -> tuple[str, str]:
    return (str(ref.model_id), str(ref.revision))


def qualified_node_key(ref: QualifiedNodeRef) -> tuple[str, str, str]:
    return (str(ref.model_id), str(ref.revision), str(ref.node_id))


@dataclass(frozen=True, order=True)
class OverlayCatalogPin:
    """Exact dependency-catalog authority consumed by a mesh transition."""

    mesh_id: MeshId
    mesh_revision: MeshRevision
    catalog_revision: OverlayCatalogRevision
    catalog_content_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "mesh_id", MeshId.parse(self.mesh_id))
        object.__setattr__(self, "mesh_revision", MeshRevision.parse(self.mesh_revision))
        object.__setattr__(
            self,
            "catalog_revision",
            OverlayCatalogRevision.parse(self.catalog_revision),
        )
        if not str(self.catalog_content_digest).startswith("sha256:"):
            raise MeshValidationError("catalog_content_digest must be a sha256 digest")

    def to_dict(self) -> dict[str, str]:
        return {
            "mesh_id": str(self.mesh_id),
            "mesh_revision": str(self.mesh_revision),
            "catalog_revision": str(self.catalog_revision),
            "catalog_content_digest": self.catalog_content_digest,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "OverlayCatalogPin":
        return cls(
            mesh_id=MeshId.parse(_require(raw, "mesh_id")),
            mesh_revision=MeshRevision.parse(_require(raw, "mesh_revision")),
            catalog_revision=OverlayCatalogRevision.parse(
                _require(raw, "catalog_revision")
            ),
            catalog_content_digest=str(_require(raw, "catalog_content_digest")),
        )


@dataclass(frozen=True, order=True)
class ModelRegistryEntry:
    model_ref: QualifiedModelRef
    content_digest: str
    snapshot_artifact_schema: str
    store_schema_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.model_ref, QualifiedModelRef):
            object.__setattr__(self, "model_ref", QualifiedModelRef.from_dict(self.model_ref))
        if not str(self.content_digest).startswith("sha256:"):
            raise MeshValidationError("registry content_digest must be a sha256 digest")
        if not self.snapshot_artifact_schema or not self.store_schema_version:
            raise MeshValidationError("registry entry requires exact P0 schema bindings")

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_ref": self.model_ref.to_dict(),
            "content_digest": self.content_digest,
            "snapshot_artifact_schema": self.snapshot_artifact_schema,
            "store_schema_version": self.store_schema_version,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ModelRegistryEntry":
        return cls(
            model_ref=QualifiedModelRef.from_dict(_require(raw, "model_ref")),
            content_digest=str(_require(raw, "content_digest")),
            snapshot_artifact_schema=str(_require(raw, "snapshot_artifact_schema")),
            store_schema_version=str(_require(raw, "store_schema_version")),
        )


@dataclass(frozen=True)
class MeshMembership:
    owner: QualifiedNodeRef
    logical_model: QualifiedModelRef
    roles: tuple[str, ...] = ()
    role_metadata: Mapping[str, Any] = field(default_factory=dict)
    provenance: tuple[ProvenanceRecord, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.owner, QualifiedNodeRef):
            object.__setattr__(self, "owner", QualifiedNodeRef.from_dict(self.owner))
        if not isinstance(self.logical_model, QualifiedModelRef):
            object.__setattr__(
                self, "logical_model", QualifiedModelRef.from_dict(self.logical_model)
            )
        roles = tuple(sorted({str(role) for role in self.roles}))
        if any(not _ROLE_PATTERN.fullmatch(role) for role in roles):
            raise MeshValidationError("membership role is not a portable identity")
        object.__setattr__(self, "roles", roles)
        metadata = dict(self.role_metadata or {})
        forbidden = sorted(_FORBIDDEN_MEMBERSHIP_FIELDS.intersection(metadata))
        if forbidden:
            raise MeshValidationError(
                "membership cannot redefine P0 node/block authority: " + ", ".join(forbidden)
            )
        object.__setattr__(self, "role_metadata", _freeze(metadata))
        records = coerce_provenance(self.provenance)
        if not records:
            raise MeshValidationError("membership requires provenance")
        object.__setattr__(self, "provenance", records)

    @property
    def membership_key(self) -> str:
        return canonical_digest(
            {"owner": self.owner.to_dict(), "logical_model": self.logical_model.to_dict()}
        )

    @property
    def content_digest(self) -> str:
        return canonical_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner": self.owner.to_dict(),
            "logical_model": self.logical_model.to_dict(),
            "roles": list(self.roles),
            "role_metadata": _thaw(self.role_metadata),
            "provenance": [record.to_dict() for record in self.provenance],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MeshMembership":
        return cls(
            owner=QualifiedNodeRef.from_dict(_require(raw, "owner")),
            logical_model=QualifiedModelRef.from_dict(_require(raw, "logical_model")),
            roles=tuple(_require(raw, "roles")),
            role_metadata=dict(_require(raw, "role_metadata")),
            provenance=tuple(
                ProvenanceRecord.from_dict(item) for item in _require(raw, "provenance")
            ),
        )


@dataclass(frozen=True)
class CrossModelEdge:
    id: EdgeId
    source: QualifiedNodeRef
    target: QualifiedNodeRef
    type: str
    weight: float = 1.0
    explanation: str = ""
    source_block_id: BlockId | None = None
    target_block_id: BlockId | None = None
    source_role: str | None = None
    target_role: str | None = None
    provenance: tuple[ProvenanceRecord, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", EdgeId.parse(self.id))
        if not isinstance(self.source, QualifiedNodeRef):
            object.__setattr__(self, "source", QualifiedNodeRef.from_dict(self.source))
        if not isinstance(self.target, QualifiedNodeRef):
            object.__setattr__(self, "target", QualifiedNodeRef.from_dict(self.target))
        if self.type not in EDGE_TYPES:
            raise MeshValidationError(f"unsupported cross-model edge type: {self.type!r}")
        weight = float(self.weight)
        if not math.isfinite(weight) or weight < 0:
            raise MeshValidationError("cross-model edge weight must be finite and non-negative")
        object.__setattr__(self, "weight", weight)
        if self.source_block_id is not None:
            object.__setattr__(self, "source_block_id", BlockId.parse(self.source_block_id))
        if self.target_block_id is not None:
            object.__setattr__(self, "target_block_id", BlockId.parse(self.target_block_id))
        for name in ("source_role", "target_role"):
            value = getattr(self, name)
            if value is not None and not _ROLE_PATTERN.fullmatch(str(value)):
                raise MeshValidationError(f"{name} is not a portable identity")
        records = coerce_provenance(self.provenance)
        if not records or not any(record.origin_kind != OriginKind.AI_GENERATED for record in records):
            raise MeshValidationError(
                "canonical cross-model edge requires non-AI-only provenance"
            )
        object.__setattr__(self, "provenance", records)
        object.__setattr__(self, "metadata", _freeze(dict(self.metadata or {})))

    @property
    def relation_key(self) -> str:
        return canonical_digest(
            {
                "source": self.source.to_dict(),
                "target": self.target.to_dict(),
                "type": self.type,
                "source_block_id": str(self.source_block_id) if self.source_block_id else None,
                "target_block_id": str(self.target_block_id) if self.target_block_id else None,
                "source_role": self.source_role,
                "target_role": self.target_role,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "id": str(self.id),
                "source": self.source.to_dict(),
                "target": self.target.to_dict(),
                "type": self.type,
                "weight": self.weight,
                "explanation": self.explanation,
                "source_block_id": str(self.source_block_id) if self.source_block_id else None,
                "target_block_id": str(self.target_block_id) if self.target_block_id else None,
                "source_role": self.source_role,
                "target_role": self.target_role,
                "provenance": [record.to_dict() for record in self.provenance],
                "metadata": _thaw(self.metadata),
            }.items()
            if value not in (None, "", {}, [])
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "CrossModelEdge":
        return cls(
            id=EdgeId.parse(_require(raw, "id")),
            source=QualifiedNodeRef.from_dict(_require(raw, "source")),
            target=QualifiedNodeRef.from_dict(_require(raw, "target")),
            type=str(_require(raw, "type")),
            weight=float(raw.get("weight", 1.0)),
            explanation=str(raw.get("explanation", "")),
            source_block_id=(BlockId.parse(raw["source_block_id"]) if raw.get("source_block_id") else None),
            target_block_id=(BlockId.parse(raw["target_block_id"]) if raw.get("target_block_id") else None),
            source_role=raw.get("source_role"),
            target_role=raw.get("target_role"),
            provenance=tuple(
                ProvenanceRecord.from_dict(item) for item in _require(raw, "provenance")
            ),
            metadata=dict(raw.get("metadata") or {}),
        )


@dataclass(frozen=True, order=True)
class MeshShardRef:
    kind: str
    partition: str
    digest: str
    record_count: int
    byte_count: int

    def __post_init__(self) -> None:
        if not self.kind or not self.partition:
            raise MeshValidationError("shard reference requires kind and partition")
        if not str(self.digest).startswith("sha256:"):
            raise MeshValidationError("shard digest must be a sha256 digest")
        if self.record_count < 0 or self.byte_count < 0:
            raise MeshValidationError("shard counts must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "partition": self.partition,
            "digest": self.digest,
            "record_count": self.record_count,
            "byte_count": self.byte_count,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MeshShardRef":
        return cls(
            kind=str(_require(raw, "kind")),
            partition=str(_require(raw, "partition")),
            digest=str(_require(raw, "digest")),
            record_count=int(_require(raw, "record_count")),
            byte_count=int(_require(raw, "byte_count")),
        )


@dataclass(frozen=True, order=True)
class MeshShardSetRef:
    kind: str
    partition_scheme: str
    partitions: tuple[MeshShardRef, ...]

    def __post_init__(self) -> None:
        if not self.kind or not self.partition_scheme:
            raise MeshValidationError("shard set requires kind and partition_scheme")
        partitions = tuple(sorted(self.partitions, key=lambda item: item.partition))
        if not partitions:
            raise MeshValidationError("shard set requires an explicit partition, including empty")
        if any(item.kind != self.kind for item in partitions):
            raise MeshValidationError("shard set contains a different shard kind")
        if len({item.partition for item in partitions}) != len(partitions):
            raise MeshValidationError("duplicate shard partition")
        object.__setattr__(self, "partitions", partitions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "partition_scheme": self.partition_scheme,
            "partitions": [item.to_dict() for item in self.partitions],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MeshShardSetRef":
        return cls(
            kind=str(_require(raw, "kind")),
            partition_scheme=str(_require(raw, "partition_scheme")),
            partitions=tuple(MeshShardRef.from_dict(item) for item in _require(raw, "partitions")),
        )


@dataclass(frozen=True)
class ModelMeshDefinition:
    mesh_id: MeshId
    registry: tuple[ModelRegistryEntry, ...]
    memberships: tuple[MeshMembership, ...] = ()
    cross_model_edges: tuple[CrossModelEdge, ...] = ()
    invalidation_baseline: OverlayCatalogPin | None = None
    provenance: tuple[ProvenanceRecord, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "mesh_id", MeshId.parse(self.mesh_id))
        registry = tuple(sorted(self.registry, key=lambda item: qualified_model_key(item.model_ref)))
        if not registry:
            raise MeshValidationError("mesh requires at least one registered model revision")
        model_ids = [str(item.model_ref.model_id) for item in registry]
        if len(set(model_ids)) != len(model_ids):
            raise MeshValidationError("one mesh cannot register two revisions of the same model_id")
        object.__setattr__(self, "registry", registry)
        memberships = tuple(
            sorted(
                self.memberships,
                key=lambda item: (qualified_node_key(item.owner), qualified_model_key(item.logical_model)),
            )
        )
        if len({item.membership_key for item in memberships}) != len(memberships):
            raise MeshValidationError("duplicate membership relation")
        object.__setattr__(self, "memberships", memberships)
        edges = tuple(sorted(self.cross_model_edges, key=lambda item: str(item.id)))
        if len({str(item.id) for item in edges}) != len(edges):
            raise MeshValidationError("duplicate cross-model edge id")
        if len({item.relation_key for item in edges}) != len(edges):
            raise MeshValidationError("duplicate cross-model relation under different edge IDs")
        object.__setattr__(self, "cross_model_edges", edges)
        baseline = self.invalidation_baseline
        if baseline is not None and not isinstance(baseline, OverlayCatalogPin):
            baseline = OverlayCatalogPin.from_dict(baseline)
            object.__setattr__(self, "invalidation_baseline", baseline)
        if baseline is not None and baseline.mesh_id != self.mesh_id:
            raise MeshValidationError("invalidation baseline belongs to another mesh")
        object.__setattr__(self, "provenance", coerce_provenance(self.provenance))
        object.__setattr__(self, "metadata", _freeze(dict(self.metadata or {})))

    @property
    def registry_digest(self) -> str:
        return canonical_digest([item.to_dict() for item in self.registry])

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "mesh_schema_version": MESH_SCHEMA_VERSION,
            "mesh_id": str(self.mesh_id),
            "registry": [item.to_dict() for item in self.registry],
            "memberships": [item.to_dict() for item in self.memberships],
            "cross_model_edges": [item.to_dict() for item in self.cross_model_edges],
            "invalidation_baseline": (
                self.invalidation_baseline.to_dict() if self.invalidation_baseline else None
            ),
            "provenance": [record.to_dict() for record in self.provenance],
            "metadata": _thaw(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.canonical_dict()

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ModelMeshDefinition":
        schema = str(_require(raw, "mesh_schema_version"))
        if schema != MESH_SCHEMA_VERSION:
            raise MeshSchemaError(
                f"mesh schema {schema!r} is unsupported; expected {MESH_SCHEMA_VERSION!r}"
            )
        return cls(
            mesh_id=MeshId.parse(_require(raw, "mesh_id")),
            registry=tuple(ModelRegistryEntry.from_dict(item) for item in _require(raw, "registry")),
            memberships=tuple(MeshMembership.from_dict(item) for item in _require(raw, "memberships")),
            cross_model_edges=tuple(
                CrossModelEdge.from_dict(item) for item in _require(raw, "cross_model_edges")
            ),
            invalidation_baseline=(
                OverlayCatalogPin.from_dict(raw["invalidation_baseline"])
                if raw.get("invalidation_baseline")
                else None
            ),
            provenance=tuple(
                ProvenanceRecord.from_dict(item) for item in _require(raw, "provenance")
            ),
            metadata=dict(_require(raw, "metadata")),
        )


def derive_mesh_revision(
    *, mesh_id: MeshId, parent_revision: MeshRevision | None, content_digest: str
) -> MeshRevision:
    payload = {
        "mesh_schema_version": MESH_SCHEMA_VERSION,
        "mesh_id": str(mesh_id),
        "parent_revision": str(parent_revision) if parent_revision else None,
        "content_digest": content_digest,
    }
    return MeshRevision(f"mesh-rev-{hashlib.sha256(canonical_json_bytes(payload)).hexdigest()}")


@dataclass(frozen=True)
class ModelMeshSnapshot:
    mesh_id: MeshId
    revision: MeshRevision
    parent_revision: MeshRevision | None
    content_digest: str
    registry_digest: str
    registry: tuple[ModelRegistryEntry, ...]
    memberships: tuple[MeshMembership, ...]
    cross_model_edges: tuple[CrossModelEdge, ...]
    shard_sets: tuple[MeshShardSetRef, ...]
    invalidation_baseline: OverlayCatalogPin | None
    provenance: tuple[ProvenanceRecord, ...]
    metadata: Mapping[str, Any]
    created_at: str
    created_by: str
    artifact_schema: str = MESH_SNAPSHOT_SCHEMA
    mesh_schema_version: str = MESH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "mesh_id", MeshId.parse(self.mesh_id))
        object.__setattr__(self, "revision", MeshRevision.parse(self.revision))
        if self.parent_revision is not None:
            object.__setattr__(
                self, "parent_revision", MeshRevision.parse(self.parent_revision)
            )
        if self.artifact_schema != MESH_SNAPSHOT_SCHEMA:
            raise MeshSchemaError(
                f"snapshot schema {self.artifact_schema!r} is unsupported; expected {MESH_SNAPSHOT_SCHEMA!r}"
            )
        if self.mesh_schema_version != MESH_SCHEMA_VERSION:
            raise MeshSchemaError(
                f"mesh schema {self.mesh_schema_version!r} is unsupported; expected {MESH_SCHEMA_VERSION!r}"
            )
        object.__setattr__(
            self,
            "registry",
            tuple(sorted(self.registry, key=lambda item: qualified_model_key(item.model_ref))),
        )
        object.__setattr__(
            self,
            "memberships",
            tuple(
                sorted(
                    self.memberships,
                    key=lambda item: (
                        qualified_node_key(item.owner),
                        qualified_model_key(item.logical_model),
                    ),
                )
            ),
        )
        object.__setattr__(
            self, "cross_model_edges", tuple(sorted(self.cross_model_edges, key=lambda item: str(item.id)))
        )
        object.__setattr__(self, "shard_sets", tuple(sorted(self.shard_sets, key=lambda item: item.kind)))
        object.__setattr__(self, "provenance", coerce_provenance(self.provenance))
        object.__setattr__(self, "metadata", _freeze(dict(self.metadata or {})))
        if not self.created_at or not self.created_by:
            raise MeshValidationError("mesh snapshot requires created_at and created_by")
        expected_registry_digest = canonical_digest([item.to_dict() for item in self.registry])
        if self.registry_digest != expected_registry_digest:
            raise MeshIntegrityError(
                f"registry digest mismatch: found {self.registry_digest}, expected {expected_registry_digest}"
            )
        expected_content = canonical_digest(self.semantic_dict())
        if self.content_digest != expected_content:
            raise MeshIntegrityError(
                f"mesh content digest mismatch: found {self.content_digest}, expected {expected_content}"
            )
        expected_revision = derive_mesh_revision(
            mesh_id=self.mesh_id,
            parent_revision=self.parent_revision,
            content_digest=self.content_digest,
        )
        if self.revision != expected_revision:
            raise MeshIntegrityError(
                f"mesh revision mismatch: found {self.revision}, expected {expected_revision}"
            )

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "mesh_schema_version": self.mesh_schema_version,
            "mesh_id": str(self.mesh_id),
            "registry": [item.to_dict() for item in self.registry],
            "memberships": [item.to_dict() for item in self.memberships],
            "cross_model_edges": [item.to_dict() for item in self.cross_model_edges],
            "shard_sets": [item.to_dict() for item in self.shard_sets],
            "invalidation_baseline": (
                self.invalidation_baseline.to_dict() if self.invalidation_baseline else None
            ),
            "provenance": [record.to_dict() for record in self.provenance],
            "metadata": _thaw(self.metadata),
        }

    @classmethod
    def create(
        cls,
        definition: ModelMeshDefinition,
        *,
        parent_revision: MeshRevision | None,
        shard_sets: Iterable[MeshShardSetRef],
        created_at: str,
        created_by: str,
    ) -> "ModelMeshSnapshot":
        semantic = {
            **definition.canonical_dict(),
            "shard_sets": [
                item.to_dict() for item in sorted(shard_sets, key=lambda value: value.kind)
            ],
        }
        digest = canonical_digest(semantic)
        parent = MeshRevision.parse(parent_revision) if parent_revision is not None else None
        revision = derive_mesh_revision(
            mesh_id=definition.mesh_id,
            parent_revision=parent,
            content_digest=digest,
        )
        return cls(
            mesh_id=definition.mesh_id,
            revision=revision,
            parent_revision=parent,
            content_digest=digest,
            registry_digest=definition.registry_digest,
            registry=definition.registry,
            memberships=definition.memberships,
            cross_model_edges=definition.cross_model_edges,
            shard_sets=tuple(shard_sets),
            invalidation_baseline=definition.invalidation_baseline,
            provenance=definition.provenance,
            metadata=definition.metadata,
            created_at=created_at,
            created_by=created_by,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "mesh_schema_version": self.mesh_schema_version,
            "mesh_id": str(self.mesh_id),
            "revision": str(self.revision),
            "parent_revision": str(self.parent_revision) if self.parent_revision else None,
            "content_digest": self.content_digest,
            "registry_digest": self.registry_digest,
            "registry": [item.to_dict() for item in self.registry],
            "memberships": [item.to_dict() for item in self.memberships],
            "cross_model_edges": [item.to_dict() for item in self.cross_model_edges],
            "shard_sets": [item.to_dict() for item in self.shard_sets],
            "invalidation_baseline": (
                self.invalidation_baseline.to_dict() if self.invalidation_baseline else None
            ),
            "provenance": [record.to_dict() for record in self.provenance],
            "metadata": _thaw(self.metadata),
            "created_at": self.created_at,
            "created_by": self.created_by,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ModelMeshSnapshot":
        return cls(
            artifact_schema=str(_require(raw, "artifact_schema")),
            mesh_schema_version=str(_require(raw, "mesh_schema_version")),
            mesh_id=MeshId.parse(_require(raw, "mesh_id")),
            revision=MeshRevision.parse(_require(raw, "revision")),
            parent_revision=(
                MeshRevision.parse(raw["parent_revision"])
                if raw.get("parent_revision")
                else None
            ),
            content_digest=str(_require(raw, "content_digest")),
            registry_digest=str(_require(raw, "registry_digest")),
            registry=tuple(ModelRegistryEntry.from_dict(item) for item in _require(raw, "registry")),
            memberships=tuple(MeshMembership.from_dict(item) for item in _require(raw, "memberships")),
            cross_model_edges=tuple(
                CrossModelEdge.from_dict(item) for item in _require(raw, "cross_model_edges")
            ),
            shard_sets=tuple(MeshShardSetRef.from_dict(item) for item in _require(raw, "shard_sets")),
            invalidation_baseline=(
                OverlayCatalogPin.from_dict(raw["invalidation_baseline"])
                if raw.get("invalidation_baseline")
                else None
            ),
            provenance=tuple(
                ProvenanceRecord.from_dict(item) for item in _require(raw, "provenance")
            ),
            metadata=dict(_require(raw, "metadata")),
            created_at=str(_require(raw, "created_at")),
            created_by=str(_require(raw, "created_by")),
        )


class SnapshotStore(Protocol):
    def get(self, model_id: ModelId | str, revision: ModelRevision | str | None = None) -> Any: ...

    def head(self, model_id: ModelId | str) -> ModelRevision | None: ...


@dataclass(frozen=True, order=True)
class ModelHeadDrift:
    registered: QualifiedModelRef
    current_head: ModelRevision

    def to_dict(self) -> dict[str, Any]:
        return {
            "registered": self.registered.to_dict(),
            "current_head": str(self.current_head),
        }


def validate_definition_against_store(
    definition: ModelMeshDefinition,
    model_store: SnapshotStore,
) -> dict[QualifiedModelRef, Any]:
    """Validate exact P0 pins and all qualified node/edge references."""

    snapshots: dict[QualifiedModelRef, Any] = {}
    registry_refs = {entry.model_ref for entry in definition.registry}
    for entry in definition.registry:
        snapshot = model_store.get(entry.model_ref.model_id, entry.model_ref.revision)
        if snapshot.revision != entry.model_ref.revision:
            raise MeshIntegrityError(f"model store returned wrong revision for {entry.model_ref}")
        if snapshot.content_digest != entry.content_digest:
            raise MeshIntegrityError(
                f"registered digest mismatch for {entry.model_ref}: "
                f"{entry.content_digest} != {snapshot.content_digest}"
            )
        if snapshot.artifact_schema != entry.snapshot_artifact_schema:
            raise MeshIntegrityError(f"registered snapshot schema mismatch for {entry.model_ref}")
        if snapshot.store_schema_version != entry.store_schema_version:
            raise MeshIntegrityError(f"registered store schema mismatch for {entry.model_ref}")
        snapshots[entry.model_ref] = snapshot

    def require_node(ref: QualifiedNodeRef) -> None:
        model_ref = QualifiedModelRef(ref.model_id, ref.revision)
        if model_ref not in registry_refs:
            raise MeshValidationError(f"qualified node endpoint is not registered: {ref}")
        nodes = snapshots[model_ref].model_payload.get("nodes")
        if not isinstance(nodes, Mapping) or str(ref.node_id) not in nodes:
            raise MeshValidationError(f"qualified node endpoint does not exist: {ref}")

    for membership in definition.memberships:
        require_node(membership.owner)
        if membership.logical_model not in registry_refs:
            raise MeshValidationError(
                f"membership logical model is not registered: {membership.logical_model}"
            )
    for edge in definition.cross_model_edges:
        require_node(edge.source)
        require_node(edge.target)
        if edge.source.model_id == edge.target.model_id:
            raise MeshValidationError(
                f"edge {edge.id} is within one physical model and must remain a P0 local edge"
            )
    return snapshots


def detect_model_head_drift(
    snapshot: ModelMeshSnapshot, model_store: SnapshotStore
) -> tuple[ModelHeadDrift, ...]:
    drift: list[ModelHeadDrift] = []
    for entry in snapshot.registry:
        head = model_store.head(entry.model_ref.model_id)
        if head is not None and head != entry.model_ref.revision:
            drift.append(ModelHeadDrift(entry.model_ref, head))
    return tuple(sorted(drift, key=lambda item: qualified_model_key(item.registered)))


__all__ = [
    "CrossModelEdge",
    "MeshIntegrityError",
    "MeshNotFoundError",
    "MeshRevisionNotFoundError",
    "MeshSchemaError",
    "MeshShardRef",
    "MeshShardSetRef",
    "MeshValidationError",
    "ModelHeadDrift",
    "ModelMeshDefinition",
    "ModelMeshError",
    "ModelMeshSnapshot",
    "ModelRegistryEntry",
    "MeshMembership",
    "OverlayCatalogPin",
    "derive_mesh_revision",
    "detect_model_head_drift",
    "qualified_model_key",
    "qualified_node_key",
    "validate_definition_against_store",
]
