"""Deterministic bounded subgraph materialization over one exact ModelMesh view."""

from __future__ import annotations

import copy
from collections import deque
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .identity import EdgeId, QualifiedModelRef, QualifiedNodeRef
from .model_mesh import (
    CrossModelEdge,
    MeshMembership,
    qualified_model_key,
    qualified_node_key,
)
from .model_store import canonical_digest, canonical_json_bytes
from .schema import EDGE_TYPES


class MeshMaterializationError(RuntimeError):
    """A materialization request or exact graph reference is invalid."""


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


@dataclass(frozen=True)
class MeshMaterializationRequest:
    roots: tuple[QualifiedNodeRef, ...]
    direction: str = "both"
    allowed_edge_kinds: tuple[str, ...] = ()
    model_filter: tuple[QualifiedModelRef, ...] = ()
    hop_limit: int = 8
    node_limit: int = 10_000
    edge_limit: int = 20_000
    model_limit: int = 100
    byte_limit: int = 64 * 1024 * 1024
    profile: str = "bounded"

    def __post_init__(self) -> None:
        roots = tuple(sorted(set(self.roots), key=qualified_node_key))
        if not roots:
            raise MeshMaterializationError("materialization requires at least one root")
        object.__setattr__(self, "roots", roots)
        if self.direction not in {"incoming", "outgoing", "both"}:
            raise MeshMaterializationError("direction must be incoming, outgoing, or both")
        kinds = tuple(sorted(set(self.allowed_edge_kinds)))
        unknown = sorted(set(kinds).difference(EDGE_TYPES))
        if unknown:
            raise MeshMaterializationError(f"unknown edge kinds: {unknown}")
        object.__setattr__(self, "allowed_edge_kinds", kinds)
        object.__setattr__(
            self,
            "model_filter",
            tuple(sorted(set(self.model_filter), key=qualified_model_key)),
        )
        for name in ("node_limit", "edge_limit", "model_limit", "byte_limit"):
            if int(getattr(self, name)) <= 0:
                raise MeshMaterializationError(f"{name} must be positive")
        if self.hop_limit < 0:
            raise MeshMaterializationError("hop_limit must be non-negative")
        if self.profile not in {"broad", "bounded"}:
            raise MeshMaterializationError("profile must be broad or bounded")
        if self.profile == "broad" and (self.allowed_edge_kinds or self.model_filter):
            raise MeshMaterializationError(
                "broad materialization cannot hide relations with edge/model filters"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "roots": [item.to_dict() for item in self.roots],
            "direction": self.direction,
            "allowed_edge_kinds": list(self.allowed_edge_kinds),
            "model_filter": [item.to_dict() for item in self.model_filter],
            "hop_limit": self.hop_limit,
            "node_limit": self.node_limit,
            "edge_limit": self.edge_limit,
            "model_limit": self.model_limit,
            "byte_limit": self.byte_limit,
            "profile": self.profile,
        }


@dataclass(frozen=True)
class MaterializedNode:
    ref: QualifiedNodeRef
    payload: Mapping[str, Any]
    block_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", _freeze(dict(self.payload)))
        object.__setattr__(self, "block_ids", tuple(sorted(set(self.block_ids))))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref.to_dict(),
            "payload": _thaw(self.payload),
            "block_ids": list(self.block_ids),
        }


@dataclass(frozen=True, order=True)
class QualifiedLocalEdge:
    model_ref: QualifiedModelRef
    id: EdgeId
    source: QualifiedNodeRef
    target: QualifiedNodeRef
    type: str
    weight: float
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_ref": self.model_ref.to_dict(),
            "id": str(self.id),
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
            "type": self.type,
            "weight": self.weight,
            "explanation": self.explanation,
        }


@dataclass(frozen=True, order=True)
class FrontierEntry:
    source: QualifiedNodeRef
    target: QualifiedNodeRef
    relation_id: str
    relation_type: str
    reason: str
    next_hop: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
            "relation_id": self.relation_id,
            "relation_type": self.relation_type,
            "reason": self.reason,
            "next_hop": self.next_hop,
        }


@dataclass(frozen=True, order=True)
class ExcludedRelation:
    source: QualifiedNodeRef
    target: QualifiedNodeRef
    relation_id: str
    relation_type: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
            "relation_id": self.relation_id,
            "relation_type": self.relation_type,
            "reason": self.reason,
        }


@dataclass(frozen=True, order=True)
class UnresolvedReference:
    ref: QualifiedNodeRef
    relation_id: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref.to_dict(),
            "relation_id": self.relation_id,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class MeshBudgetUsage:
    nodes: int
    edges: int
    models: int
    bytes: int
    node_limit: int
    edge_limit: int
    model_limit: int
    byte_limit: int

    def to_dict(self) -> dict[str, int]:
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "models": self.models,
            "bytes": self.bytes,
            "node_limit": self.node_limit,
            "edge_limit": self.edge_limit,
            "model_limit": self.model_limit,
            "byte_limit": self.byte_limit,
        }


@dataclass(frozen=True)
class MaterializedMesh:
    mesh_id: Any
    mesh_revision: Any
    mesh_content_digest: str
    request: MeshMaterializationRequest
    model_pins: tuple[QualifiedModelRef, ...]
    nodes: tuple[MaterializedNode, ...]
    local_edges: tuple[QualifiedLocalEdge, ...]
    cross_edges: tuple[CrossModelEdge, ...]
    memberships: tuple[MeshMembership, ...]
    frontier: tuple[FrontierEntry, ...]
    excluded_relations: tuple[ExcludedRelation, ...]
    unresolved_references: tuple[UnresolvedReference, ...]
    budgets: MeshBudgetUsage
    truncation_reasons: tuple[str, ...]
    complete: bool
    authoritative_universe_fingerprint: str
    model_read_count: int

    @property
    def materialization_fingerprint(self) -> str:
        return canonical_digest(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "mesh_id": str(self.mesh_id),
            "mesh_revision": str(self.mesh_revision),
            "mesh_content_digest": self.mesh_content_digest,
            "request": self.request.to_dict(),
            "model_pins": [item.to_dict() for item in self.model_pins],
            "nodes": [item.to_dict() for item in self.nodes],
            "local_edges": [item.to_dict() for item in self.local_edges],
            "cross_edges": [item.to_dict() for item in self.cross_edges],
            "memberships": [item.to_dict() for item in self.memberships],
            "frontier": [item.to_dict() for item in self.frontier],
            "excluded_relations": [item.to_dict() for item in self.excluded_relations],
            "unresolved_references": [item.to_dict() for item in self.unresolved_references],
            "budgets": self.budgets.to_dict(),
            "truncation_reasons": list(self.truncation_reasons),
            "complete": self.complete,
            "authoritative_universe_fingerprint": self.authoritative_universe_fingerprint,
            "model_read_count": self.model_read_count,
        }
        if include_fingerprint:
            payload["materialization_fingerprint"] = self.materialization_fingerprint
        return payload


@dataclass(frozen=True)
class _TraversalRelation:
    source: QualifiedNodeRef
    target: QualifiedNodeRef
    relation_id: str
    relation_type: str
    local_edge: QualifiedLocalEdge | None = None
    cross_edge: CrossModelEdge | None = None


def _local_relations(view, ref: QualifiedNodeRef, direction: str) -> tuple[_TraversalRelation, ...]:
    model_ref = QualifiedModelRef(ref.model_id, ref.revision)
    snapshot = view.model_snapshot(model_ref)
    found: list[_TraversalRelation] = []
    for raw in snapshot.model_payload.get("edges") or ():
        source = QualifiedNodeRef(ref.model_id, ref.revision, raw["source"])
        target = QualifiedNodeRef(ref.model_id, ref.revision, raw["target"])
        edge = QualifiedLocalEdge(
            model_ref=model_ref,
            id=EdgeId.parse(raw["id"]),
            source=source,
            target=target,
            type=str(raw["type"]),
            weight=float(raw.get("weight", 1.0)),
            explanation=str(raw.get("explanation", "")),
        )
        if direction in {"outgoing", "both"} and source == ref:
            found.append(
                _TraversalRelation(source, target, str(edge.id), edge.type, local_edge=edge)
            )
        if direction in {"incoming", "both"} and target == ref:
            found.append(
                _TraversalRelation(target, source, str(edge.id), edge.type, local_edge=edge)
            )
    return tuple(found)


def _cross_relations(view, ref: QualifiedNodeRef, direction: str) -> tuple[_TraversalRelation, ...]:
    found: list[_TraversalRelation] = []
    if direction in {"outgoing", "both"}:
        for edge in view.outgoing_cross_edges(ref):
            found.append(
                _TraversalRelation(ref, edge.target, str(edge.id), edge.type, cross_edge=edge)
            )
    if direction in {"incoming", "both"}:
        for edge in view.incoming_cross_edges(ref):
            found.append(
                _TraversalRelation(ref, edge.source, str(edge.id), edge.type, cross_edge=edge)
            )
    return tuple(found)


def _blocks_for(snapshot, node_id: str) -> tuple[str, ...]:
    result = []
    for block_id, raw in (snapshot.model_payload.get("blocks") or {}).items():
        if node_id in tuple(raw.get("member_nodes") or ()):
            result.append(str(block_id))
    return tuple(sorted(result))


def materialize_mesh(view, request: MeshMaterializationRequest) -> MaterializedMesh:
    """Materialize only the declared deterministic universe from ``view``."""

    registered = {item.model_ref for item in view.snapshot.registry}
    allowed_models = set(request.model_filter) if request.model_filter else registered
    if any(QualifiedModelRef(root.model_id, root.revision) not in registered for root in request.roots):
        raise MeshMaterializationError("one or more roots are not registered in this mesh")
    if any(QualifiedModelRef(root.model_id, root.revision) not in allowed_models for root in request.roots):
        raise MeshMaterializationError("one or more roots are excluded by model_filter")

    start_reads = view.model_read_count
    nodes: dict[QualifiedNodeRef, MaterializedNode] = {}
    node_hops: dict[QualifiedNodeRef, int] = {}
    local_edges: dict[tuple[QualifiedModelRef, EdgeId], QualifiedLocalEdge] = {}
    cross_edges: dict[EdgeId, CrossModelEdge] = {}
    memberships: dict[str, MeshMembership] = {}
    frontier: list[FrontierEntry] = []
    excluded: list[ExcludedRelation] = []
    unresolved: list[UnresolvedReference] = []
    truncation: set[str] = set()
    selected_models: set[QualifiedModelRef] = set()
    used_bytes = 0
    queue: deque[QualifiedNodeRef] = deque()

    def add_node(ref: QualifiedNodeRef, hop: int, relation_id: str) -> bool:
        nonlocal used_bytes
        if ref in nodes:
            if hop < node_hops[ref]:
                node_hops[ref] = hop
                queue.append(ref)
            return True
        model_ref = QualifiedModelRef(ref.model_id, ref.revision)
        if model_ref not in allowed_models:
            return False
        if len(nodes) >= request.node_limit:
            truncation.add("node_limit")
            return False
        if model_ref not in selected_models and len(selected_models) >= request.model_limit:
            truncation.add("model_limit")
            return False
        try:
            payload = view.node(ref)
            snapshot = view.model_snapshot(model_ref)
        except Exception as exc:
            unresolved.append(UnresolvedReference(ref, relation_id, str(exc)))
            truncation.add("unresolved_reference")
            return False
        candidate = MaterializedNode(ref, payload, _blocks_for(snapshot, str(ref.node_id)))
        node_memberships = view.memberships_for_node(ref)
        byte_cost = len(canonical_json_bytes(candidate.to_dict())) + sum(
            len(canonical_json_bytes(item.to_dict())) for item in node_memberships
        )
        if used_bytes + byte_cost > request.byte_limit:
            truncation.add("byte_limit")
            return False
        nodes[ref] = candidate
        node_hops[ref] = hop
        selected_models.add(model_ref)
        used_bytes += byte_cost
        for membership in node_memberships:
            memberships[membership.membership_key] = membership
        queue.append(ref)
        return True

    for root in request.roots:
        if not add_node(root, 0, "root"):
            raise MeshMaterializationError(
                f"root cannot fit declared materialization budgets: {root}"
            )

    processed_hop: dict[QualifiedNodeRef, int] = {}
    while queue:
        ref = queue.popleft()
        hop = node_hops[ref]
        if processed_hop.get(ref, 10**9) <= hop:
            continue
        processed_hop[ref] = hop
        relations = (*_local_relations(view, ref, request.direction), *_cross_relations(view, ref, request.direction))
        relations = tuple(
            sorted(
                relations,
                key=lambda item: (
                    qualified_node_key(item.target),
                    item.relation_type,
                    item.relation_id,
                ),
            )
        )
        for relation in relations:
            if request.allowed_edge_kinds and relation.relation_type not in request.allowed_edge_kinds:
                excluded.append(
                    ExcludedRelation(
                        relation.source,
                        relation.target,
                        relation.relation_id,
                        relation.relation_type,
                        "edge_kind_filter",
                    )
                )
                continue
            target_model = QualifiedModelRef(
                relation.target.model_id, relation.target.revision
            )
            if target_model not in allowed_models:
                excluded.append(
                    ExcludedRelation(
                        relation.source,
                        relation.target,
                        relation.relation_id,
                        relation.relation_type,
                        "model_filter",
                    )
                )
                continue
            if hop >= request.hop_limit and relation.target not in nodes:
                truncation.add("hop_limit")
                frontier.append(
                    FrontierEntry(
                        relation.source,
                        relation.target,
                        relation.relation_id,
                        relation.relation_type,
                        "hop_limit",
                        hop + 1,
                    )
                )
                continue
            edge_key = (
                (relation.local_edge.model_ref, relation.local_edge.id)
                if relation.local_edge is not None
                else relation.cross_edge.id
            )
            already_selected = (
                edge_key in local_edges
                if relation.local_edge is not None
                else edge_key in cross_edges
            )
            if not already_selected and len(local_edges) + len(cross_edges) >= request.edge_limit:
                truncation.add("edge_limit")
                frontier.append(
                    FrontierEntry(
                        relation.source,
                        relation.target,
                        relation.relation_id,
                        relation.relation_type,
                        "edge_limit",
                        hop + 1,
                    )
                )
                continue
            if not add_node(relation.target, hop + 1, relation.relation_id):
                reason = next(
                    (
                        item
                        for item in ("node_limit", "model_limit", "byte_limit", "unresolved_reference")
                        if item in truncation
                    ),
                    "excluded",
                )
                frontier.append(
                    FrontierEntry(
                        relation.source,
                        relation.target,
                        relation.relation_id,
                        relation.relation_type,
                        reason,
                        hop + 1,
                    )
                )
                continue
            if not already_selected:
                edge_payload = (
                    relation.local_edge.to_dict()
                    if relation.local_edge is not None
                    else relation.cross_edge.to_dict()
                )
                edge_bytes = len(canonical_json_bytes(edge_payload))
                if used_bytes + edge_bytes > request.byte_limit:
                    truncation.add("byte_limit")
                    frontier.append(
                        FrontierEntry(
                            relation.source,
                            relation.target,
                            relation.relation_id,
                            relation.relation_type,
                            "byte_limit",
                            hop + 1,
                        )
                    )
                    continue
                used_bytes += edge_bytes
                if relation.local_edge is not None:
                    local_edges[edge_key] = relation.local_edge
                else:
                    cross_edges[edge_key] = relation.cross_edge

    node_values = tuple(sorted(nodes.values(), key=lambda item: qualified_node_key(item.ref)))
    local_values = tuple(
        sorted(
            local_edges.values(),
            key=lambda item: (qualified_model_key(item.model_ref), str(item.id)),
        )
    )
    cross_values = tuple(sorted(cross_edges.values(), key=lambda item: str(item.id)))
    membership_values = tuple(
        sorted(memberships.values(), key=lambda item: item.membership_key)
    )
    frontier_values = tuple(sorted(set(frontier)))
    excluded_values = tuple(sorted(set(excluded)))
    unresolved_values = tuple(sorted(set(unresolved)))
    model_pins = tuple(sorted(selected_models, key=qualified_model_key))
    complete = not truncation and not unresolved_values
    universe_payload = {
        "mesh_id": str(view.snapshot.mesh_id),
        "mesh_revision": str(view.snapshot.revision),
        "mesh_content_digest": view.snapshot.content_digest,
        "request": request.to_dict(),
        "model_pins": [item.to_dict() for item in model_pins],
        "nodes": [item.to_dict() for item in node_values],
        "local_edges": [item.to_dict() for item in local_values],
        "cross_edges": [item.to_dict() for item in cross_values],
        "memberships": [item.to_dict() for item in membership_values],
        "frontier": [item.to_dict() for item in frontier_values],
        "excluded_relations": [item.to_dict() for item in excluded_values],
        "unresolved_references": [item.to_dict() for item in unresolved_values],
    }
    return MaterializedMesh(
        mesh_id=view.snapshot.mesh_id,
        mesh_revision=view.snapshot.revision,
        mesh_content_digest=view.snapshot.content_digest,
        request=request,
        model_pins=model_pins,
        nodes=node_values,
        local_edges=local_values,
        cross_edges=cross_values,
        memberships=membership_values,
        frontier=frontier_values,
        excluded_relations=excluded_values,
        unresolved_references=unresolved_values,
        budgets=MeshBudgetUsage(
            nodes=len(node_values),
            edges=len(local_values) + len(cross_values),
            models=len(model_pins),
            bytes=used_bytes,
            node_limit=request.node_limit,
            edge_limit=request.edge_limit,
            model_limit=request.model_limit,
            byte_limit=request.byte_limit,
        ),
        truncation_reasons=tuple(sorted(truncation)),
        complete=complete,
        authoritative_universe_fingerprint=canonical_digest(universe_payload),
        model_read_count=view.model_read_count - start_reads,
    )


__all__ = [
    "ExcludedRelation",
    "FrontierEntry",
    "MaterializedMesh",
    "MaterializedNode",
    "MeshBudgetUsage",
    "MeshMaterializationError",
    "MeshMaterializationRequest",
    "QualifiedLocalEdge",
    "UnresolvedReference",
    "materialize_mesh",
]
