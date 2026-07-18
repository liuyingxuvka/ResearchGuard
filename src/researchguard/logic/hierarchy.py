"""Hierarchy helpers for containment plus argument graph models."""

from __future__ import annotations

from collections import defaultdict, deque

from .model import LogicModel


def build_parent_index(model: LogicModel) -> dict[str, str]:
    parents: dict[str, str] = {}
    for parent, children in model.hierarchy.items():
        for child in children:
            parents[child] = parent
    for node_id, node in model.nodes.items():
        if node.parent:
            parents[node_id] = node.parent
    return parents


def build_children_index(model: LogicModel) -> dict[str, list[str]]:
    children: dict[str, list[str]] = defaultdict(list)
    for parent, child_ids in model.hierarchy.items():
        children[parent].extend(child_ids)
    for node_id, node in model.nodes.items():
        if node.parent and node_id not in children[node.parent]:
            children[node.parent].append(node_id)
        if node.children:
            for child in node.children:
                if child not in children[node_id]:
                    children[node_id].append(child)
    return dict(children)


def descendants(model: LogicModel, parent_id: str) -> list[str]:
    children = build_children_index(model)
    result: list[str] = []
    seen = {parent_id}
    queue = deque(children.get(parent_id, []))
    while queue:
        child = queue.popleft()
        if child in seen:
            continue
        seen.add(child)
        result.append(child)
        queue.extend(children.get(child, []))
    return result


def hierarchy_roots(model: LogicModel) -> list[str]:
    children = {child for values in model.hierarchy.values() for child in values}
    roots = [parent for parent in model.hierarchy if parent not in children]
    if roots:
        return roots
    if model.root_claim:
        return [model.root_claim]
    return list(model.nodes)[:1]


def aggregate_child_states(states: list[str]) -> str:
    if not states:
        return "UNDECIDED"
    if all(state == "IN" for state in states):
        return "IN"
    if any(state == "OUT" for state in states):
        return "OUT"
    return "UNDECIDED"
