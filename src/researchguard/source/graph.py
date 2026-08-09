"""
Purpose: Build and inspect lightweight SourceGuard evidence-frontier graph neighborhoods.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: SourceGuard
Math boundary: Expected utility ranks search value, not factual truth or calibrated probability.
CLI: researchguard source frontier <model.yaml>
Boundary: Source candidates and evidence anchors require downstream TraceGuard/LogicGuard review before final claims.
"""

from __future__ import annotations

from typing import Any

from .schema import BeliefState, GRAPH_RELATION_ENDPOINTS, GraphEdge, SchemaError


EDGE_TYPES = set(GRAPH_RELATION_ENDPOINTS)


def build_adjacency(edges: list[GraphEdge]) -> dict[str, list[str]]:
    """Build an undirected neighborhood without fabricating reverse model edges."""

    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        if not isinstance(edge, GraphEdge):
            raise SchemaError("raw graph edges are not a current SourceGuard authority")
        adjacency.setdefault(edge.source_id, []).append(edge.target_id)
        adjacency.setdefault(edge.target_id, []).append(edge.source_id)
    for node_id in adjacency:
        adjacency[node_id] = sorted(set(adjacency[node_id]))
    return adjacency


def neighbors(node_id: str, edges: list[GraphEdge]) -> list[str]:
    adjacency = build_adjacency(edges)
    return list(adjacency.get(node_id, []))


def connected_component(node_id: str, edges: list[GraphEdge]) -> list[str]:
    adjacency = build_adjacency(edges)
    seen: set[str] = set()
    stack = [node_id]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(neighbor for neighbor in adjacency.get(current, []) if neighbor not in seen)
    return sorted(seen)


def _edges(belief_state: BeliefState) -> list[GraphEdge]:
    if any(not isinstance(edge, GraphEdge) for edge in belief_state.graph_edges):
        raise SchemaError("raw graph edges are not a current SourceGuard authority")
    return list(belief_state.graph_edges)


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
