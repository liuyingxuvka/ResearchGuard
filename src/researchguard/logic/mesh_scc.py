"""Iterative model-level SCC analysis for product-runtime ModelMesh."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .identity import QualifiedModelRef
from .model_mesh import qualified_model_key
from .model_store import canonical_digest


@dataclass(frozen=True)
class ModelDependencyGraph:
    nodes: tuple[QualifiedModelRef, ...]
    edges: tuple[tuple[QualifiedModelRef, QualifiedModelRef], ...]

    def __post_init__(self) -> None:
        nodes = tuple(sorted(set(self.nodes), key=qualified_model_key))
        node_set = set(nodes)
        edges = tuple(
            sorted(
                {
                    (source, target)
                    for source, target in self.edges
                    if source in node_set and target in node_set
                },
                key=lambda item: (qualified_model_key(item[0]), qualified_model_key(item[1])),
            )
        )
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "edges", edges)

    def to_dict(self) -> dict:
        return {
            "nodes": [item.to_dict() for item in self.nodes],
            "edges": [
                {"source": source.to_dict(), "target": target.to_dict()}
                for source, target in self.edges
            ],
        }


@dataclass(frozen=True)
class ModelScc:
    scc_id: str
    members: tuple[QualifiedModelRef, ...]
    incoming_scc_ids: tuple[str, ...]
    outgoing_scc_ids: tuple[str, ...]
    cyclic: bool
    grounded_contribution_keys: tuple[str, ...]
    status: str
    diagnostics: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "scc_id": self.scc_id,
            "members": [item.to_dict() for item in self.members],
            "incoming_scc_ids": list(self.incoming_scc_ids),
            "outgoing_scc_ids": list(self.outgoing_scc_ids),
            "cyclic": self.cyclic,
            "grounded_contribution_keys": list(self.grounded_contribution_keys),
            "status": self.status,
            "diagnostics": list(self.diagnostics),
        }


@dataclass(frozen=True)
class ModelSccAnalysis:
    graph: ModelDependencyGraph
    sccs: tuple[ModelScc, ...]
    condensation_order: tuple[str, ...]

    def scc_for(self, model_ref: QualifiedModelRef) -> ModelScc:
        for scc in self.sccs:
            if model_ref in scc.members:
                return scc
        raise KeyError(model_ref)

    def to_dict(self) -> dict:
        return {
            "graph": self.graph.to_dict(),
            "sccs": [item.to_dict() for item in self.sccs],
            "condensation_order": list(self.condensation_order),
        }


def build_model_dependency_graph(view_or_materialization) -> ModelDependencyGraph:
    if hasattr(view_or_materialization, "snapshot"):
        snapshot = view_or_materialization.snapshot
        model_refs = tuple(item.model_ref for item in snapshot.registry)
        cross_edges = snapshot.cross_model_edges
        memberships = snapshot.memberships
    else:
        materialized = view_or_materialization
        model_refs = tuple(materialized.model_pins)
        cross_edges = materialized.cross_edges
        memberships = materialized.memberships
    selected = set(model_refs)
    edges: set[tuple[QualifiedModelRef, QualifiedModelRef]] = set()
    for edge in cross_edges:
        source = QualifiedModelRef(edge.source.model_id, edge.source.revision)
        target = QualifiedModelRef(edge.target.model_id, edge.target.revision)
        if source in selected and target in selected:
            edges.add((source, target))
    for membership in memberships:
        source = QualifiedModelRef(membership.owner.model_id, membership.owner.revision)
        target = membership.logical_model
        if source != target and source in selected and target in selected:
            edges.add((source, target))
    return ModelDependencyGraph(tuple(model_refs), tuple(edges))


def compute_model_sccs(
    graph: ModelDependencyGraph,
    *,
    grounded_contributions: Mapping[QualifiedModelRef, Iterable[str]] | None = None,
) -> ModelSccAnalysis:
    """Compute SCCs and condensation order without Python recursion."""

    adjacency = {node: [] for node in graph.nodes}
    reverse = {node: [] for node in graph.nodes}
    for source, target in graph.edges:
        adjacency[source].append(target)
        reverse[target].append(source)
    for values in (*adjacency.values(), *reverse.values()):
        values.sort(key=qualified_model_key)

    visited: set[QualifiedModelRef] = set()
    finish: list[QualifiedModelRef] = []
    for root in graph.nodes:
        if root in visited:
            continue
        visited.add(root)
        stack: list[tuple[QualifiedModelRef, int]] = [(root, 0)]
        while stack:
            node, index = stack[-1]
            neighbors = adjacency[node]
            if index < len(neighbors):
                target = neighbors[index]
                stack[-1] = (node, index + 1)
                if target not in visited:
                    visited.add(target)
                    stack.append((target, 0))
                continue
            stack.pop()
            finish.append(node)

    assigned: set[QualifiedModelRef] = set()
    components: list[tuple[QualifiedModelRef, ...]] = []
    for root in reversed(finish):
        if root in assigned:
            continue
        assigned.add(root)
        members: list[QualifiedModelRef] = []
        stack = [root]
        while stack:
            node = stack.pop()
            members.append(node)
            for target in reversed(reverse[node]):
                if target not in assigned:
                    assigned.add(target)
                    stack.append(target)
        components.append(tuple(sorted(members, key=qualified_model_key)))

    component_ids = {
        members: f"model-scc-{canonical_digest([item.to_dict() for item in members]).split(':', 1)[1]}"
        for members in components
    }
    owner = {
        member: component_ids[members]
        for members in components
        for member in members
    }
    incoming: dict[str, set[str]] = {value: set() for value in component_ids.values()}
    outgoing: dict[str, set[str]] = {value: set() for value in component_ids.values()}
    for source, target in graph.edges:
        source_scc = owner[source]
        target_scc = owner[target]
        if source_scc != target_scc:
            outgoing[source_scc].add(target_scc)
            incoming[target_scc].add(source_scc)

    grounded = grounded_contributions or {}
    sccs: list[ModelScc] = []
    for members in components:
        scc_id = component_ids[members]
        self_loop = any(source == target and source in members for source, target in graph.edges)
        cyclic = len(members) > 1 or self_loop
        contribution_keys = tuple(
            sorted(
                {
                    key
                    for member in members
                    for key in grounded.get(member, ())
                }
            )
        )
        diagnostics = []
        status = "acyclic"
        if cyclic and contribution_keys:
            status = "grounded-cycle"
        elif cyclic:
            status = "ungrounded-cycle"
            diagnostics.append("support cycle has no grounded admissible contribution")
        sccs.append(
            ModelScc(
                scc_id=scc_id,
                members=members,
                incoming_scc_ids=tuple(sorted(incoming[scc_id])),
                outgoing_scc_ids=tuple(sorted(outgoing[scc_id])),
                cyclic=cyclic,
                grounded_contribution_keys=contribution_keys,
                status=status,
                diagnostics=tuple(diagnostics),
            )
        )
    sccs.sort(key=lambda item: item.scc_id)

    indegree = {scc.scc_id: len(scc.incoming_scc_ids) for scc in sccs}
    ready = sorted(item for item, degree in indegree.items() if degree == 0)
    order: list[str] = []
    while ready:
        scc_id = ready.pop(0)
        order.append(scc_id)
        for target in sorted(outgoing[scc_id]):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
                ready.sort()
    if len(order) != len(sccs):
        raise RuntimeError("condensation graph unexpectedly contains a cycle")
    return ModelSccAnalysis(graph=graph, sccs=tuple(sccs), condensation_order=tuple(order))


__all__ = [
    "ModelDependencyGraph",
    "ModelScc",
    "ModelSccAnalysis",
    "build_model_dependency_graph",
    "compute_model_sccs",
]
