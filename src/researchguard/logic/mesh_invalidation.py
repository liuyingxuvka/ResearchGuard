"""Exact dependency delta and affected-only invalidation for ModelMesh overlays."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .mesh_index import EVIDENCE_BY_KEY_SHARD, MeshIndexBundle
from .mesh_overlay import MeshDependencyKey
from .mesh_overlay_catalog import OverlayCatalogSnapshot
from .mesh_receipts import MeshInvalidationReceipt
from .model_mesh import ModelMeshSnapshot
from .model_store import canonical_digest


@dataclass(frozen=True)
class MeshDependencyDelta:
    removed_or_changed: tuple[MeshDependencyKey, ...]
    added_or_changed: tuple[MeshDependencyKey, ...]
    unchanged_digests: tuple[str, ...]

    @property
    def affected_parent_digests(self) -> tuple[str, ...]:
        return tuple(item.identity_digest for item in self.removed_or_changed)

    def to_dict(self) -> dict:
        return {
            "removed_or_changed": [item.to_dict() for item in self.removed_or_changed],
            "added_or_changed": [item.to_dict() for item in self.added_or_changed],
            "unchanged_digests": list(self.unchanged_digests),
        }


def mesh_authority_dependency_keys(
    snapshot: ModelMeshSnapshot, indexes: MeshIndexBundle
) -> tuple[MeshDependencyKey, ...]:
    """Project every mesh-owned authority that may license an overlay.

    P0 node payload changes are covered by the exact ``model_pin`` key.  Node,
    scope, evaluator, simulator, and profile keys remain overlay-owned inputs.
    """

    keys: list[MeshDependencyKey] = []
    for entry in snapshot.registry:
        keys.append(
            MeshDependencyKey.create(
                "model_pin",
                {
                    "model_ref": entry.model_ref.to_dict(),
                    "content_digest": entry.content_digest,
                },
            )
        )
    for membership in snapshot.memberships:
        keys.append(
            MeshDependencyKey.create(
                "membership",
                {
                    "membership_key": membership.membership_key,
                    "content_digest": membership.content_digest,
                },
            )
        )
    for edge in snapshot.cross_model_edges:
        keys.append(
            MeshDependencyKey.create(
                "edge",
                {
                    "edge_id": str(edge.id),
                    "relation_key": edge.relation_key,
                    "content_digest": canonical_digest(edge.to_dict()),
                },
            )
        )
    for raw in indexes.by_kind(EVIDENCE_BY_KEY_SHARD).records:
        keys.append(
            MeshDependencyKey.create(
                "evidence_identity",
                {
                    "contribution_key": raw["contribution_key"],
                    "source_identity": raw["source_identity"],
                    "content_hash": raw["content_hash"],
                },
            )
        )
        if raw.get("independence_group"):
            keys.append(
                MeshDependencyKey.create(
                    "independence_group",
                    {
                        "independence_group": raw["independence_group"],
                        "contribution_key": raw["contribution_key"],
                    },
                )
            )
    return tuple(
        sorted(
            {item.identity_digest: item for item in keys}.values(),
            key=lambda item: (item.kind, item.identity_digest),
        )
    )


def diff_mesh_dependencies(
    parent_snapshot: ModelMeshSnapshot,
    parent_indexes: MeshIndexBundle,
    child_snapshot: ModelMeshSnapshot,
    child_indexes: MeshIndexBundle,
) -> MeshDependencyDelta:
    parent = {
        item.identity_digest: item
        for item in mesh_authority_dependency_keys(parent_snapshot, parent_indexes)
    }
    child = {
        item.identity_digest: item
        for item in mesh_authority_dependency_keys(child_snapshot, child_indexes)
    }
    unchanged = tuple(sorted(set(parent).intersection(child)))
    removed = tuple(
        sorted(
            (parent[key] for key in set(parent).difference(child)),
            key=lambda item: (item.kind, item.identity_digest),
        )
    )
    added = tuple(
        sorted(
            (child[key] for key in set(child).difference(parent)),
            key=lambda item: (item.kind, item.identity_digest),
        )
    )
    return MeshDependencyDelta(
        removed_or_changed=removed,
        added_or_changed=added,
        unchanged_digests=unchanged,
    )


def compute_overlay_invalidation(
    *,
    parent_snapshot: ModelMeshSnapshot,
    parent_indexes: MeshIndexBundle,
    child_snapshot: ModelMeshSnapshot,
    child_indexes: MeshIndexBundle,
    catalog_snapshot: OverlayCatalogSnapshot,
    tool_fingerprint: str,
    created_at: str | None = None,
) -> MeshInvalidationReceipt:
    if (
        catalog_snapshot.mesh_id != parent_snapshot.mesh_id
        or catalog_snapshot.mesh_revision != parent_snapshot.revision
    ):
        raise ValueError("invalidation catalog does not bind parent mesh revision")
    if child_snapshot.parent_revision != parent_snapshot.revision:
        raise ValueError("child mesh does not directly descend from parent mesh")
    delta = diff_mesh_dependencies(
        parent_snapshot, parent_indexes, child_snapshot, child_indexes
    )
    changed_digests = set(delta.affected_parent_digests)
    affected = []
    unaffected = []
    for entry in catalog_snapshot.entries:
        binding = catalog_snapshot.binding_for(entry)
        matches = tuple(
            key
            for key in binding.dependency_keys
            if key.identity_digest in changed_digests
        )
        if matches:
            affected.append(
                {
                    "overlay_id": str(entry.overlay_id),
                    "reason_codes": sorted({f"changed:{item.kind}" for item in matches}),
                    "matched_dependency_keys": [item.to_dict() for item in matches],
                }
            )
        else:
            unaffected.append(
                {
                    "overlay_id": str(entry.overlay_id),
                    "explanation": "no declared dependency key changed",
                }
            )
    values = dict(
        mesh_id=parent_snapshot.mesh_id,
        parent_mesh_revision=parent_snapshot.revision,
        child_mesh_revision=child_snapshot.revision,
        catalog_baseline=catalog_snapshot.pin,
        catalog_snapshot_digest=catalog_snapshot.content_digest,
        changed_dependencies=(
            {
                "direction": "removed_or_changed",
                **item.to_dict(),
            }
            for item in delta.removed_or_changed
        ),
        affected_overlays=affected,
        unaffected_overlays=unaffected,
        tool_fingerprint=tool_fingerprint,
    )
    if created_at is not None:
        values["created_at"] = created_at
    return MeshInvalidationReceipt.create(**values)


__all__ = [
    "MeshDependencyDelta",
    "compute_overlay_invalidation",
    "diff_mesh_dependencies",
    "mesh_authority_dependency_keys",
]
