"""Structured artifact helpers built on LogicGuard hierarchy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .hierarchy import build_children_index, hierarchy_roots
from .importance import importance_for_node
from .model import LogicModel


STRUCTURAL_NODE_TYPES = {"Document", "Section", "ArgumentBlock"}


@dataclass(frozen=True)
class ArtifactBlock:
    block_id: str
    node_type: str
    title: str
    artifact_kind: str
    locator: str
    order_index: float
    role: str
    child_nodes: tuple[str, ...]
    claims: tuple[str, ...]
    evidence: tuple[str, ...]
    limitations: tuple[str, ...]
    importance: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_id": self.block_id,
            "node_type": self.node_type,
            "title": self.title,
            "artifact_kind": self.artifact_kind,
            "locator": self.locator,
            "order_index": self.order_index,
            "role": self.role,
            "child_nodes": list(self.child_nodes),
            "claims": list(self.claims),
            "evidence": list(self.evidence),
            "limitations": list(self.limitations),
            "importance": round(self.importance, 4),
        }


@dataclass(frozen=True)
class ArtifactMap:
    model_id: str
    artifact_kind: str
    blocks: tuple[ArtifactBlock, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "artifact_kind": self.artifact_kind,
            "blocks": [block.to_dict() for block in self.blocks],
        }


def build_artifact_map(model: LogicModel) -> ArtifactMap:
    artifact_kind = str(model.metadata.get("artifact_kind", "structured-artifact"))
    blocks = tuple(ordered_artifact_blocks(model, artifact_kind=artifact_kind))
    return ArtifactMap(model.id, artifact_kind, blocks)


def ordered_artifact_blocks(model: LogicModel, *, artifact_kind: str | None = None) -> list[ArtifactBlock]:
    children = build_children_index(model)
    blocks: list[ArtifactBlock] = []
    for node_id, node in model.nodes.items():
        if node.type not in STRUCTURAL_NODE_TYPES:
            continue
        child_nodes = tuple(children.get(node_id, ()))
        local_nodes = tuple(child for child in child_nodes if child in model.nodes)
        claims = tuple(child for child in local_nodes if model.nodes[child].type == "Claim")
        evidence = tuple(child for child in local_nodes if model.nodes[child].type in {"Evidence", "Result", "Method"})
        limitations = tuple(child for child in local_nodes if model.nodes[child].type in {"Limitation", "Qualifier"})
        block_kind = str(node.metadata.get("artifact_kind", artifact_kind or model.metadata.get("artifact_kind", "")) or "")
        locator = str(node.metadata.get("locator", ""))
        role = node.role or str(node.metadata.get("role", ""))
        order_index = _order_index(node_id, node.metadata.get("order_index"))
        importance = importance_for_node(model, node_id).importance
        blocks.append(
            ArtifactBlock(
                block_id=node_id,
                node_type=node.type,
                title=node.text,
                artifact_kind=block_kind or "structured-artifact",
                locator=locator,
                order_index=order_index,
                role=role,
                child_nodes=local_nodes,
                claims=claims,
                evidence=evidence,
                limitations=limitations,
                importance=importance,
            )
        )
    rank = _hierarchy_rank(model)
    return sorted(blocks, key=lambda block: (rank.get(block.block_id, 999999.0), block.order_index, block.block_id))


def node_block_index(model: LogicModel) -> dict[str, str]:
    result: dict[str, str] = {}
    for block in ordered_artifact_blocks(model):
        for child in block.child_nodes:
            result[child] = block.block_id
    return result


def _order_index(node_id: str, value: object) -> float:
    if value not in (None, ""):
        try:
            return float(value)
        except (TypeError, ValueError):
            pass
    digits = "".join(ch for ch in node_id if ch.isdigit())
    if digits:
        return float(digits)
    return 999999.0


def _hierarchy_rank(model: LogicModel) -> dict[str, float]:
    children = build_children_index(model)
    rank: dict[str, float] = {}
    counter = 0

    def visit(node_id: str) -> None:
        nonlocal counter
        if node_id in rank:
            return
        rank[node_id] = float(counter)
        counter += 1
        child_ids = sorted(
            children.get(node_id, []),
            key=lambda child_id: (
                _order_index(child_id, model.nodes[child_id].metadata.get("order_index") if child_id in model.nodes else None),
                child_id,
            ),
        )
        for child_id in child_ids:
            visit(child_id)

    for root in hierarchy_roots(model):
        visit(root)
    return rank
