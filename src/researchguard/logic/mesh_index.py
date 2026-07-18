"""Deterministic immutable index shards for product-runtime ModelMesh."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .identity import EdgeId, QualifiedModelRef, QualifiedNodeRef
from .model_mesh import (
    CrossModelEdge,
    MeshIntegrityError,
    MeshMembership,
    MeshShardRef,
    MeshShardSetRef,
    ModelMeshDefinition,
    ModelMeshSnapshot,
    qualified_model_key,
    qualified_node_key,
)
from .model_store import canonical_digest, canonical_json_bytes
from .provenance import ProvenanceRecord
from .schema import MESH_INDEX_SHARD_SCHEMA, MESH_SCHEMA_VERSION


REGISTRY_SHARD = "registry"
MEMBERSHIP_FORWARD_SHARD = "membership-forward"
MEMBERSHIP_REVERSE_SHARD = "membership-reverse"
CROSS_ADJACENCY_OUT_SHARD = "cross-adjacency-out"
CROSS_ADJACENCY_IN_SHARD = "cross-adjacency-in"
MODEL_DEPENDENCY_SHARD = "model-dependency"
EVIDENCE_BY_NODE_SHARD = "evidence-contribution-by-node"
EVIDENCE_BY_KEY_SHARD = "evidence-contribution-by-key"

MESH_SHARD_KINDS = (
    REGISTRY_SHARD,
    MEMBERSHIP_FORWARD_SHARD,
    MEMBERSHIP_REVERSE_SHARD,
    CROSS_ADJACENCY_OUT_SHARD,
    CROSS_ADJACENCY_IN_SHARD,
    MODEL_DEPENDENCY_SHARD,
    EVIDENCE_BY_NODE_SHARD,
    EVIDENCE_BY_KEY_SHARD,
)


def _required(raw: Mapping[str, Any], key: str) -> Any:
    if key not in raw:
        raise MeshIntegrityError(f"required shard field is missing: {key}")
    return raw[key]


@dataclass(frozen=True)
class MeshIndexShard:
    mesh_id: str
    content_basis_digest: str
    kind: str
    partition: str
    records: tuple[Mapping[str, Any], ...]
    digest: str
    artifact_schema: str = MESH_INDEX_SHARD_SCHEMA
    mesh_schema_version: str = MESH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.artifact_schema != MESH_INDEX_SHARD_SCHEMA:
            raise MeshIntegrityError(
                f"index shard schema {self.artifact_schema!r} is unsupported; "
                f"expected {MESH_INDEX_SHARD_SCHEMA!r}"
            )
        if self.mesh_schema_version != MESH_SCHEMA_VERSION:
            raise MeshIntegrityError(
                f"mesh schema {self.mesh_schema_version!r} is unsupported; "
                f"expected {MESH_SCHEMA_VERSION!r}"
            )
        if self.kind not in MESH_SHARD_KINDS:
            raise MeshIntegrityError(f"unknown mesh shard kind: {self.kind!r}")
        if self.partition != "all":
            raise MeshIntegrityError("P1 current shard partition must be explicit 'all'")
        normalized = tuple(
            MappingProxyType(dict(item))
            for item in sorted(
                (dict(record) for record in self.records),
                key=lambda record: canonical_json_bytes(record),
            )
        )
        object.__setattr__(self, "records", normalized)
        expected = canonical_digest(self.fingerprint_payload())
        if self.digest != expected:
            raise MeshIntegrityError(
                f"mesh index shard digest mismatch for {self.kind}: "
                f"found {self.digest}, expected {expected}"
            )

    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "mesh_schema_version": self.mesh_schema_version,
            "mesh_id": self.mesh_id,
            "content_basis_digest": self.content_basis_digest,
            "kind": self.kind,
            "partition": self.partition,
            "records": [dict(item) for item in self.records],
        }

    @classmethod
    def create(
        cls,
        *,
        mesh_id: str,
        content_basis_digest: str,
        kind: str,
        records: Iterable[Mapping[str, Any]],
    ) -> "MeshIndexShard":
        payload = {
            "artifact_schema": MESH_INDEX_SHARD_SCHEMA,
            "mesh_schema_version": MESH_SCHEMA_VERSION,
            "mesh_id": mesh_id,
            "content_basis_digest": content_basis_digest,
            "kind": kind,
            "partition": "all",
            "records": sorted(
                (dict(item) for item in records), key=lambda item: canonical_json_bytes(item)
            ),
        }
        return cls(
            mesh_id=mesh_id,
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
    def from_dict(cls, raw: Mapping[str, Any]) -> "MeshIndexShard":
        return cls(
            artifact_schema=str(_required(raw, "artifact_schema")),
            mesh_schema_version=str(_required(raw, "mesh_schema_version")),
            mesh_id=str(_required(raw, "mesh_id")),
            content_basis_digest=str(_required(raw, "content_basis_digest")),
            kind=str(_required(raw, "kind")),
            partition=str(_required(raw, "partition")),
            records=tuple(_required(raw, "records")),
            digest=str(_required(raw, "digest")),
        )


@dataclass(frozen=True)
class MeshIndexBundle:
    content_basis_digest: str
    shards: tuple[MeshIndexShard, ...]

    def __post_init__(self) -> None:
        shards = tuple(sorted(self.shards, key=lambda item: item.kind))
        kinds = tuple(item.kind for item in shards)
        if kinds != tuple(sorted(MESH_SHARD_KINDS)):
            missing = sorted(set(MESH_SHARD_KINDS).difference(kinds))
            extra = sorted(set(kinds).difference(MESH_SHARD_KINDS))
            raise MeshIntegrityError(
                f"mesh index bundle must contain every exact shard kind; missing={missing}, extra={extra}"
            )
        if any(item.content_basis_digest != self.content_basis_digest for item in shards):
            raise MeshIntegrityError("mesh shard content basis mismatch")
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

    def by_kind(self, kind: str) -> MeshIndexShard:
        for shard in self.shards:
            if shard.kind == kind:
                return shard
        raise MeshIntegrityError(f"required mesh shard is missing: {kind}")

    def validate_snapshot_binding(self, snapshot: ModelMeshSnapshot) -> None:
        expected = {
            item.kind: item.partitions[0]
            for item in snapshot.shard_sets
            if len(item.partitions) == 1
        }
        if set(expected) != set(MESH_SHARD_KINDS):
            raise MeshIntegrityError("snapshot does not bind every current mesh shard kind")
        for shard in self.shards:
            ref = expected[shard.kind]
            if ref.digest != shard.digest:
                raise MeshIntegrityError(f"snapshot shard digest mismatch: {shard.kind}")
            if ref.record_count != len(shard.records):
                raise MeshIntegrityError(f"snapshot shard count mismatch: {shard.kind}")


def _evidence_records(
    model_snapshots: Mapping[QualifiedModelRef, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_node: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for model_ref, snapshot in sorted(
        (model_snapshots or {}).items(), key=lambda item: qualified_model_key(item[0])
    ):
        nodes = snapshot.model_payload.get("nodes") or {}
        if not isinstance(nodes, Mapping):
            continue
        for node_id in sorted(nodes):
            node = nodes[node_id]
            if not isinstance(node, Mapping) or node.get("type") != "Evidence":
                continue
            node_ref = QualifiedNodeRef(model_ref.model_id, model_ref.revision, node_id)
            for raw_record in node.get("provenance") or ():
                record = (
                    raw_record
                    if isinstance(raw_record, ProvenanceRecord)
                    else ProvenanceRecord.from_dict(raw_record)
                )
                if not record.is_evidentiary:
                    continue
                identity = record.normalized_source_identity
                group = record.independence_group or ""
                contribution_key = canonical_digest(
                    {
                        "source_identity": identity,
                        "content_hash": record.content_hash,
                        "independence_group": group,
                    }
                )
                item = {
                    "node_ref": node_ref.to_dict(),
                    "contribution_key": contribution_key,
                    "source_identity": identity,
                    "content_hash": record.content_hash,
                    "independence_group": group,
                    "provenance": record.to_dict(),
                }
                by_node.append(item)
                aggregate_key = (identity, record.content_hash, group)
                aggregate = by_key.setdefault(
                    aggregate_key,
                    {
                        "contribution_key": contribution_key,
                        "source_identity": identity,
                        "content_hash": record.content_hash,
                        "independence_group": group,
                        "node_refs": [],
                    },
                )
                aggregate["node_refs"].append(node_ref.to_dict())
    for aggregate in by_key.values():
        aggregate["node_refs"] = sorted(
            aggregate["node_refs"], key=lambda item: canonical_json_bytes(item)
        )
    return by_node, list(by_key.values())


def compile_mesh_indexes(
    definition: ModelMeshDefinition,
    *,
    model_snapshots: Mapping[QualifiedModelRef, Any] | None = None,
) -> MeshIndexBundle:
    """Compile every current deterministic mesh shard, including explicit empties."""

    basis = canonical_digest(definition.canonical_dict())
    records: dict[str, list[dict[str, Any]]] = {kind: [] for kind in MESH_SHARD_KINDS}
    records[REGISTRY_SHARD] = [entry.to_dict() for entry in definition.registry]
    for membership in definition.memberships:
        item = {
            "membership_key": membership.membership_key,
            "owner": membership.owner.to_dict(),
            "logical_model": membership.logical_model.to_dict(),
            "content_digest": membership.content_digest,
        }
        records[MEMBERSHIP_FORWARD_SHARD].append(item)
        records[MEMBERSHIP_REVERSE_SHARD].append(
            {
                "logical_model": membership.logical_model.to_dict(),
                "owner": membership.owner.to_dict(),
                "membership_key": membership.membership_key,
            }
        )
    dependency_pairs: set[tuple[QualifiedModelRef, QualifiedModelRef, str]] = set()
    for membership in definition.memberships:
        owner_model = QualifiedModelRef(membership.owner.model_id, membership.owner.revision)
        if owner_model != membership.logical_model:
            dependency_pairs.add((owner_model, membership.logical_model, "membership"))
    for edge in definition.cross_model_edges:
        out_item = {
            "node_ref": edge.source.to_dict(),
            "edge_id": str(edge.id),
            "target": edge.target.to_dict(),
            "type": edge.type,
        }
        in_item = {
            "node_ref": edge.target.to_dict(),
            "edge_id": str(edge.id),
            "source": edge.source.to_dict(),
            "type": edge.type,
        }
        records[CROSS_ADJACENCY_OUT_SHARD].append(out_item)
        records[CROSS_ADJACENCY_IN_SHARD].append(in_item)
        dependency_pairs.add(
            (
                QualifiedModelRef(edge.source.model_id, edge.source.revision),
                QualifiedModelRef(edge.target.model_id, edge.target.revision),
                "cross_edge",
            )
        )
    records[MODEL_DEPENDENCY_SHARD] = [
        {"source": source.to_dict(), "target": target.to_dict(), "kind": kind}
        for source, target, kind in sorted(
            dependency_pairs,
            key=lambda item: (qualified_model_key(item[0]), qualified_model_key(item[1]), item[2]),
        )
    ]
    by_node, by_key = _evidence_records(model_snapshots)
    records[EVIDENCE_BY_NODE_SHARD] = by_node
    records[EVIDENCE_BY_KEY_SHARD] = by_key
    shards = tuple(
        MeshIndexShard.create(
            mesh_id=str(definition.mesh_id),
            content_basis_digest=basis,
            kind=kind,
            records=records[kind],
        )
        for kind in MESH_SHARD_KINDS
    )
    return MeshIndexBundle(content_basis_digest=basis, shards=shards)


class MeshIndexView:
    """Digest-verified in-memory query view over exact current shards."""

    def __init__(self, snapshot: ModelMeshSnapshot, bundle: MeshIndexBundle) -> None:
        bundle.validate_snapshot_binding(snapshot)
        self.snapshot = snapshot
        self.bundle = bundle
        self._membership_by_owner: dict[QualifiedNodeRef, list[str]] = {}
        self._members_by_model: dict[QualifiedModelRef, list[QualifiedNodeRef]] = {}
        self._out_edges: dict[QualifiedNodeRef, list[EdgeId]] = {}
        self._in_edges: dict[QualifiedNodeRef, list[EdgeId]] = {}
        self._dependency: dict[QualifiedModelRef, set[QualifiedModelRef]] = {}
        for raw in bundle.by_kind(MEMBERSHIP_FORWARD_SHARD).records:
            owner = QualifiedNodeRef.from_dict(raw["owner"])
            self._membership_by_owner.setdefault(owner, []).append(str(raw["membership_key"]))
        for raw in bundle.by_kind(MEMBERSHIP_REVERSE_SHARD).records:
            model = QualifiedModelRef.from_dict(raw["logical_model"])
            owner = QualifiedNodeRef.from_dict(raw["owner"])
            self._members_by_model.setdefault(model, []).append(owner)
        for raw in bundle.by_kind(CROSS_ADJACENCY_OUT_SHARD).records:
            ref = QualifiedNodeRef.from_dict(raw["node_ref"])
            self._out_edges.setdefault(ref, []).append(EdgeId.parse(raw["edge_id"]))
        for raw in bundle.by_kind(CROSS_ADJACENCY_IN_SHARD).records:
            ref = QualifiedNodeRef.from_dict(raw["node_ref"])
            self._in_edges.setdefault(ref, []).append(EdgeId.parse(raw["edge_id"]))
        for raw in bundle.by_kind(MODEL_DEPENDENCY_SHARD).records:
            source = QualifiedModelRef.from_dict(raw["source"])
            target = QualifiedModelRef.from_dict(raw["target"])
            self._dependency.setdefault(source, set()).add(target)

    def membership_keys_for_node(self, ref: QualifiedNodeRef) -> tuple[str, ...]:
        return tuple(sorted(self._membership_by_owner.get(ref, ())))

    def members_of_model(self, ref: QualifiedModelRef) -> tuple[QualifiedNodeRef, ...]:
        return tuple(sorted(self._members_by_model.get(ref, ()), key=qualified_node_key))

    def outgoing_edge_ids(self, ref: QualifiedNodeRef) -> tuple[EdgeId, ...]:
        return tuple(sorted(self._out_edges.get(ref, ()), key=str))

    def incoming_edge_ids(self, ref: QualifiedNodeRef) -> tuple[EdgeId, ...]:
        return tuple(sorted(self._in_edges.get(ref, ()), key=str))

    def model_dependencies(self, ref: QualifiedModelRef) -> tuple[QualifiedModelRef, ...]:
        return tuple(sorted(self._dependency.get(ref, ()), key=qualified_model_key))


__all__ = [
    "CROSS_ADJACENCY_IN_SHARD",
    "CROSS_ADJACENCY_OUT_SHARD",
    "EVIDENCE_BY_KEY_SHARD",
    "EVIDENCE_BY_NODE_SHARD",
    "MEMBERSHIP_FORWARD_SHARD",
    "MEMBERSHIP_REVERSE_SHARD",
    "MESH_SHARD_KINDS",
    "MODEL_DEPENDENCY_SHARD",
    "REGISTRY_SHARD",
    "MeshIndexBundle",
    "MeshIndexShard",
    "MeshIndexView",
    "compile_mesh_indexes",
]
