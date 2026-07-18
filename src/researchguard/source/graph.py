"""
Purpose: Build and inspect lightweight SourceGuard evidence-frontier graph neighborhoods.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: SourceGuard
Math boundary: Expected utility ranks search value, not factual truth or calibrated probability.
CLI: researchguard source frontier <model.yaml>
Boundary: Source candidates and evidence anchors require downstream TraceGuard/LogicGuard review before final claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .schema import BeliefState, SchemaError


EDGE_TYPES = {
    "mentions",
    "supports",
    "limits",
    "rebuts",
    "cites",
    "cited_by",
    "same_entity_as",
    "same_location_as",
    "before",
    "after",
    "candidate_for",
    "opens_gap",
    "closes_gap",
    "generated_action",
    "observation_from",
    "promoted_to_traceguard",
    "promoted_to_logicguard",
}


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    edge_type: str
    notes: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GraphEdge":
        source = str(data.get("source", ""))
        target = str(data.get("target", ""))
        edge_type = str(data.get("edge_type", ""))
        if not source or not target:
            raise SchemaError("graph edge requires source and target")
        if edge_type not in EDGE_TYPES:
            raise SchemaError(f"invalid graph edge type {edge_type!r}")
        return cls(source=source, target=target, edge_type=edge_type, notes=str(data.get("notes", "")))


def build_adjacency(edges: list[GraphEdge]) -> dict[str, list[GraphEdge]]:
    adjacency: dict[str, list[GraphEdge]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source, []).append(edge)
        adjacency.setdefault(edge.target, []).append(GraphEdge(edge.target, edge.source, edge.edge_type, edge.notes))
    return adjacency


def neighbors(node_id: str, edges: list[GraphEdge]) -> list[str]:
    adjacency = build_adjacency(edges)
    return sorted({edge.target for edge in adjacency.get(node_id, [])})


def connected_component(node_id: str, edges: list[GraphEdge]) -> list[str]:
    adjacency = build_adjacency(edges)
    seen: set[str] = set()
    stack = [node_id]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(edge.target for edge in adjacency.get(current, []) if edge.target not in seen)
    return sorted(seen)


def _edges(belief_state: BeliefState) -> list[GraphEdge]:
    return [GraphEdge.from_dict(edge) for edge in belief_state.graph_edges]


def lead_neighborhood(lead_id: str, belief_state: BeliefState) -> dict[str, Any]:
    edges = _edges(belief_state)
    lead = belief_state.lead_by_id().get(lead_id)
    return {
        "lead_id": lead_id,
        "lead": lead,
        "neighbors": neighbors(lead_id, edges),
        "component": connected_component(lead_id, edges),
        "gaps": [gap for gap in belief_state.gaps if gap.lead_id == lead_id],
        "actions": [action for action in belief_state.actions if action.target_lead_id == lead_id],
    }


def source_neighborhood(source_id: str, belief_state: BeliefState) -> dict[str, Any]:
    edges = _edges(belief_state)
    return {
        "source_id": source_id,
        "source": belief_state.source_by_id().get(source_id),
        "neighbors": neighbors(source_id, edges),
        "component": connected_component(source_id, edges),
        "anchors": [anchor for anchor in belief_state.anchors if anchor.source_id == source_id],
    }
