"""Structural validation for LogicGuard models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .identity import BlockId, EdgeId, ModelId, NodeId
from .model import LogicModel
from .provenance import ProvenanceError, validate_evidence_provenance
from .schema import ACCEPTANCE_KEYS, EDGE_TYPES, NODE_TYPES, SCHEMA_VERSION, STATES, STATE_UNDECIDED


_EXECUTABLE_BLOCK_NODE_KEYS = {
    "root_claim",
    "member_nodes",
    "input_nodes",
    "internal_nodes",
    "output_claims",
    "local_assumptions",
    "local_rebuttals",
    "acceptance_conditions",
}
_TRANSIENT_NODE_KEYS = {"forced_state", "evaluated_state", "evaluation_state", "runtime_state"}


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings}

    def format_text(self) -> str:
        lines = [f"validation: {'OK' if self.ok else 'FAILED'}"]
        lines.extend(f"ERROR: {item}" for item in self.errors)
        lines.extend(f"WARNING: {item}" for item in self.warnings)
        return "\n".join(lines)


def validate_model(model: LogicModel, *, durable: bool = False) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    if not model.nodes:
        errors.append("model must define at least one node")
    if model.root_claim and model.root_claim not in model.nodes:
        errors.append(f"root_claim {model.root_claim!r} is not a defined node")
    if durable and model.schema_version != SCHEMA_VERSION:
        errors.append(
            f"model schema {model.schema_version!r} is not current {SCHEMA_VERSION!r}; "
            "use the explicit import-to-current boundary"
        )
    if durable:
        _check_portable_id("model", model.id, ModelId, errors)

    for node_id, node in model.nodes.items():
        if node.type not in NODE_TYPES:
            errors.append(f"node {node_id!r} has unsupported type {node.type!r}")
        if node.state not in STATES:
            errors.append(f"node {node_id!r} has unsupported state {node.state!r}")
        if not 0.0 <= node.confidence <= 1.0:
            errors.append(f"node {node_id!r} confidence must be between 0 and 1")
        if node.importance is not None and not 0.0 <= node.importance <= 1.0:
            errors.append(f"node {node_id!r} importance must be between 0 and 1")
        if durable:
            _check_portable_id("node", node_id, NodeId, errors)
            if node.id != node_id:
                errors.append(f"node registry key {node_id!r} disagrees with node.id {node.id!r}")
            if node.state != STATE_UNDECIDED:
                errors.append(
                    f"node {node_id!r} persists evaluated state {node.state!r}; "
                    "durable evaluated state belongs in an EvaluationOverlay"
                )
            transient = sorted(_TRANSIENT_NODE_KEYS.intersection(node.metadata))
            if transient:
                errors.append(f"node {node_id!r} contains transient simulation fields {transient!r}")
            if node.type == "Evidence":
                try:
                    validate_evidence_provenance(node_id, node.provenance)
                except ProvenanceError as exc:
                    errors.append(str(exc))

    for index, edge in enumerate(model.edges):
        if edge.source not in model.nodes:
            errors.append(f"edge {index} source {edge.source!r} is not a defined node")
        if edge.target not in model.nodes:
            errors.append(f"edge {index} target {edge.target!r} is not a defined node")
        if edge.type not in EDGE_TYPES:
            errors.append(f"edge {index} has unsupported type {edge.type!r}")
        if not 0.0 <= edge.weight <= 1.0:
            errors.append(f"edge {index} weight must be between 0 and 1")
        if edge.importance is not None and not 0.0 <= edge.importance <= 1.0:
            errors.append(f"edge {index} importance must be between 0 and 1")
        if durable:
            if not edge.id:
                errors.append(f"edge {index} has no stable id")
            else:
                _check_portable_id("edge", edge.id, EdgeId, errors)

    edge_ids = [edge.id for edge in model.edges if edge.id]
    if len(edge_ids) != len(set(edge_ids)):
        errors.append("edge ids must be unique within a model revision")

    for target, condition in model.acceptance.items():
        if target not in model.nodes:
            errors.append(f"acceptance target {target!r} is not a defined node")
        if not isinstance(condition, dict):
            errors.append(f"acceptance target {target!r} must map to a dictionary")
            continue
        for key in condition:
            if key not in ACCEPTANCE_KEYS:
                warnings.append(f"acceptance target {target!r} uses unknown key {key!r}")
        for key in ("all_of", "any_of", "none_of", "requires", "requires_not_out", "unless"):
            refs = _as_list(condition.get(key))
            for ref in refs:
                if ref not in model.nodes:
                    errors.append(f"acceptance {target!r}.{key} references unknown node {ref!r}")
        if "at_least_k" in condition:
            at_least = condition["at_least_k"]
            refs = []
            if isinstance(at_least, dict):
                refs = _as_list(at_least.get("nodes"))
                k = at_least.get("k")
            elif isinstance(at_least, (list, tuple)) and len(at_least) == 2:
                k, refs = at_least[0], _as_list(at_least[1])
            else:
                errors.append(f"acceptance {target!r}.at_least_k must be {{k, nodes}} or [k, nodes]")
                k = None
            if k is not None and int(k) < 1:
                errors.append(f"acceptance {target!r}.at_least_k k must be positive")
            for ref in refs:
                if ref not in model.nodes:
                    errors.append(f"acceptance {target!r}.at_least_k references unknown node {ref!r}")

    known_hierarchy_ids = set(model.nodes) | set(model.hierarchy)
    seen_children: dict[str, str] = {}
    for parent, children in model.hierarchy.items():
        if parent not in known_hierarchy_ids:
            warnings.append(f"hierarchy parent {parent!r} is virtual and has no node definition")
        for child in children:
            if child not in known_hierarchy_ids:
                errors.append(f"hierarchy child {child!r} is neither a node nor a hierarchy container")
            if child in seen_children and seen_children[child] != parent:
                warnings.append(f"hierarchy child {child!r} appears under multiple parents")
            seen_children[child] = parent

    hierarchy_cycle = _find_cycle({str(key): list(value) for key, value in model.hierarchy.items()})
    if hierarchy_cycle:
        errors.append(f"hierarchy contains a cycle: {' -> '.join(hierarchy_cycle)}")

    block_graph: dict[str, list[str]] = {block_id: list(block.child_blocks) for block_id, block in model.blocks.items()}
    for block_id, block in model.blocks.items():
        if block.id != block_id:
            errors.append(f"block registry key {block_id!r} disagrees with block.id {block.id!r}")
        if durable:
            _check_portable_id("block", block_id, BlockId, errors)
        if len(block.member_nodes) != len(set(block.member_nodes)):
            errors.append(f"block {block_id!r}.member_nodes contains duplicates")
        members = set(block.member_node_ids())
        for field_name, refs in {
            "input_nodes": block.input_nodes,
            "internal_nodes": block.internal_nodes,
            "output_claims": block.output_claims,
            "local_assumptions": block.local_assumptions,
            "local_rebuttals": block.local_rebuttals,
        }.items():
            for ref in refs:
                if ref not in model.nodes:
                    errors.append(f"block {block_id!r}.{field_name} references unknown node {ref!r}")
                elif ref not in members:
                    errors.append(f"block {block_id!r}.{field_name} reference {ref!r} is not a member")

        for ref in members:
            if ref not in model.nodes:
                errors.append(f"block {block_id!r}.member_nodes references unknown node {ref!r}")
        if block.root_claim is None:
            if durable:
                errors.append(f"block {block_id!r} must declare one root_claim")
        elif block.root_claim not in model.nodes:
            errors.append(f"block {block_id!r}.root_claim references unknown node {block.root_claim!r}")
        else:
            if block.root_claim not in members:
                errors.append(f"block {block_id!r}.root_claim must be a member node")
            if model.nodes[block.root_claim].type != "Claim":
                errors.append(f"block {block_id!r}.root_claim must reference a Claim")
        for output_claim in block.output_claims:
            if output_claim in model.nodes and model.nodes[output_claim].type != "Claim":
                errors.append(f"block {block_id!r}.output_claims item {output_claim!r} is not a Claim")
        for field_name, classifications in {
            "input_classifications": block.input_classifications,
            "output_classifications": block.output_classifications,
        }.items():
            for ref in classifications:
                if ref not in members:
                    errors.append(f"block {block_id!r}.{field_name} references non-member {ref!r}")

        if block.parent:
            if block.parent not in model.blocks and block.parent not in model.nodes and block.parent not in model.hierarchy:
                errors.append(f"block {block_id!r}.parent references unknown block {block.parent!r}")
            elif block.parent in model.blocks:
                block_graph.setdefault(block.parent, []).append(block_id)
        for child_id in block.child_blocks:
            if child_id not in model.blocks:
                errors.append(f"block {block_id!r}.child_blocks references unknown block {child_id!r}")

        structural = model.nodes.get(block_id)
        if structural is not None:
            if structural.type != "ArgumentBlock":
                errors.append(
                    f"canonical block {block_id!r} collides with non-ArgumentBlock node type {structural.type!r}"
                )
            if block.title and structural.text and block.title != structural.text:
                message = f"block {block_id!r} title disagrees with its structural-node projection"
                (errors if durable else warnings).append(message)
            if block.parent and structural.parent and block.parent != structural.parent:
                message = f"block {block_id!r} parent disagrees with its structural-node projection"
                (errors if durable else warnings).append(message)
            dual_fields = sorted(_EXECUTABLE_BLOCK_NODE_KEYS.intersection(structural.metadata))
            if dual_fields:
                errors.append(
                    f"ArgumentBlock node {block_id!r} defines executable fields outside the canonical registry: {dual_fields!r}"
                )

    block_cycle = _find_cycle(block_graph)
    if block_cycle:
        errors.append(f"argument-block hierarchy contains a cycle: {' -> '.join(block_cycle)}")

    return ValidationResult(ok=not errors, errors=errors, warnings=warnings)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _check_portable_id(kind: str, value: str, identity_type: Any, errors: list[str]) -> None:
    try:
        identity_type.parse(value)
    except ValueError as exc:
        errors.append(f"{kind} id {value!r} is not portable: {exc}")


def _find_cycle(graph: dict[str, list[str]]) -> list[str]:
    """Return one cycle from a directed graph using an explicit DFS stack."""

    nodes = set(graph)
    for children in graph.values():
        nodes.update(children)
    color: dict[str, int] = {}
    for root in sorted(nodes):
        if color.get(root, 0):
            continue
        path = [root]
        positions = {root: 0}
        color[root] = 1
        stack: list[tuple[str, int]] = [(root, 0)]
        while stack:
            node_id, index = stack[-1]
            children = graph.get(node_id, ())
            if index >= len(children):
                stack.pop()
                color[node_id] = 2
                positions.pop(node_id, None)
                path.pop()
                continue
            child_id = children[index]
            stack[-1] = (node_id, index + 1)
            child_color = color.get(child_id, 0)
            if child_color == 0:
                color[child_id] = 1
                positions[child_id] = len(path)
                path.append(child_id)
                stack.append((child_id, 0))
            elif child_color == 1:
                start = positions[child_id]
                return path[start:] + [child_id]
    return []
