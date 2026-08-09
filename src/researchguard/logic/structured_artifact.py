"""Structured artifact helpers built on LogicGuard hierarchy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .hierarchy import build_children_index, hierarchy_roots
from .importance import importance_for_node
from .model import LogicModel
from .artifact_inventory import ArtifactInventory


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
    inventory_fingerprint: str = ""
    missing_inventory_unit_ids: tuple[str, ...] = ()
    parse_gap_unit_ids: tuple[str, ...] = ()
    realization_binding_ids: tuple[str, ...] = ()
    unrealized_argument_block_ids: tuple[str, ...] = ()
    missing_interface_receipt_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "artifact_kind": self.artifact_kind,
            "blocks": [block.to_dict() for block in self.blocks],
            "inventory_fingerprint": self.inventory_fingerprint,
            "missing_inventory_unit_ids": list(self.missing_inventory_unit_ids),
            "parse_gap_unit_ids": list(self.parse_gap_unit_ids),
            "realization_binding_ids": list(self.realization_binding_ids),
            "unrealized_argument_block_ids": list(self.unrealized_argument_block_ids),
            "missing_interface_receipt_ids": list(self.missing_interface_receipt_ids),
        }


def build_artifact_map(
    model: LogicModel,
    *,
    inventory: ArtifactInventory | None = None,
    realizations: Iterable[object] = (),
) -> ArtifactMap:
    artifact_kind = str(model.metadata.get("artifact_kind", "structured-artifact"))
    blocks = tuple(ordered_artifact_blocks(model, artifact_kind=artifact_kind))
    bindings = tuple(realizations)
    bound_unit_ids = {
        str(getattr(item, "artifact_unit_id", ""))
        for item in bindings
        if str(getattr(item, "artifact_unit_id", ""))
    }
    bound_block_ids = {
        str(getattr(item, "argument_block_id", ""))
        for item in bindings
        if str(getattr(item, "argument_block_id", ""))
    }
    missing = (
        tuple(sorted(item.unit_id for item in inventory.units if item.unit_id not in bound_unit_ids))
        if inventory
        else ()
    )
    parse_gaps = tuple(sorted(item.unit_id for item in inventory.units if item.parse_disposition == "unparsed")) if inventory else ()
    receipt_resource_ids = (
        {
            resource.resource_id
            for unit in inventory.units
            for resource in unit.resources
            if resource.role == "receipt"
            and resource.required
            and resource.disposition == "bound"
        }
        if inventory
        else set()
    )
    required_receipt_ids = {
        item.parent_receipt_id
        for item in model.block_interfaces
        if item.consumer_status == "consumed"
    }
    provided_receipt_ids = {
        str(resource_id)
        for item in bindings
        for resource_id in getattr(item, "resource_ids", ())
        if str(resource_id) in receipt_resource_ids
        and str(resource_id) in required_receipt_ids
    }
    return ArtifactMap(
        model.id,
        artifact_kind,
        blocks,
        inventory.fingerprint if inventory else "",
        missing,
        parse_gaps,
        tuple(
            sorted(
                f"realization:{getattr(item, 'artifact_unit_id', '')}->{getattr(item, 'argument_block_id', '')}"
                for item in bindings
            )
        ),
        tuple(sorted(set(model.blocks) - bound_block_ids)) if inventory else (),
        tuple(sorted(required_receipt_ids - provided_receipt_ids)),
    )


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
