"""Durable-boundary validation for current ModelStore snapshots."""

from __future__ import annotations

import copy
import hashlib
from collections import defaultdict
from typing import Any, Iterable, Mapping

from .identity import BlockId, EdgeId, ModelId, NodeId
from .model_store import ModelSnapshot, canonical_json_bytes
from .provenance import (
    ProvenanceError,
    ProvenanceRecord,
    coerce_provenance,
    normalize_duplicate_independence,
    validate_evidence_provenance,
)
from .schema import SCHEMA_VERSION


class DurableValidationError(ValueError):
    """One or more declared durable model invariants failed."""

    def __init__(self, errors: Iterable[str]) -> None:
        self.errors = tuple(str(error) for error in errors)
        super().__init__("; ".join(self.errors))


def _record_list(value: Any) -> list[Mapping[str, Any]]:
    if value in (None, ""):
        return []
    if not isinstance(value, (list, tuple)):
        raise ProvenanceError("provenance must be a list")
    return list(value)


def _identity_error(errors: list[str], kind: str, value: Any, identity_type: Any) -> None:
    try:
        identity_type.parse(value)
    except ValueError as exc:
        errors.append(f"invalid {kind} {value!r}: {exc}")


def validate_model_payload(payload: Mapping[str, Any]) -> None:
    errors: list[str] = []
    model_info = payload.get("model")
    if not isinstance(model_info, Mapping):
        raise DurableValidationError(["canonical model payload requires model mapping"])
    model_id = model_info.get("id")
    _identity_error(errors, "model_id", model_id, ModelId)
    schema = model_info.get("schema_version")
    if schema != SCHEMA_VERSION:
        errors.append(
            f"model schema {schema!r} is unsupported; expected {SCHEMA_VERSION!r}; "
            "use the explicit direct-to-current import boundary"
        )

    nodes = payload.get("nodes")
    if not isinstance(nodes, Mapping):
        errors.append("nodes must be a mapping")
        nodes = {}
    for node_id, node in nodes.items():
        _identity_error(errors, "node_id", node_id, NodeId)
        if not isinstance(node, Mapping):
            errors.append(f"node {node_id!r} must be a mapping")
            continue
        embedded_id = node.get("id")
        if embedded_id not in (None, "", node_id):
            errors.append(
                f"node {node_id!r} embedded id {embedded_id!r} conflicts with registry key"
            )
        if "state" in node:
            errors.append(
                f"node {node_id!r} persists evaluated state in canonical content; use an evaluation overlay"
            )

    edges = payload.get("edges") or []
    if not isinstance(edges, (list, tuple)):
        errors.append("edges must be a list")
        edges = []
    edge_ids: set[str] = set()
    for index, edge in enumerate(edges):
        if not isinstance(edge, Mapping):
            errors.append(f"edge #{index} must be a mapping")
            continue
        edge_id = edge.get("id")
        if not edge_id:
            errors.append(f"edge #{index} requires a stable id")
        else:
            _identity_error(errors, "edge_id", edge_id, EdgeId)
            if str(edge_id) in edge_ids:
                errors.append(f"duplicate edge id {edge_id!r}")
            edge_ids.add(str(edge_id))
        if edge.get("source") not in nodes:
            errors.append(f"edge {edge_id or index!r} source is not a local node")
        if edge.get("target") not in nodes:
            errors.append(f"edge {edge_id or index!r} target is not a local node")

    blocks = payload.get("blocks") or {}
    if not isinstance(blocks, Mapping):
        errors.append("blocks must be a mapping")
        blocks = {}
    for block_id, block in blocks.items():
        _identity_error(errors, "block_id", block_id, BlockId)
        if not isinstance(block, Mapping):
            errors.append(f"block {block_id!r} must be a mapping")
            continue
        if block.get("id") not in (None, "", block_id):
            errors.append(f"block {block_id!r} embedded id conflicts with registry key")
        root_claim = block.get("root_claim")
        members_raw = block.get("member_nodes")
        if not root_claim:
            errors.append(f"block {block_id!r} requires one root_claim")
        if not isinstance(members_raw, (list, tuple)) or not members_raw:
            errors.append(f"block {block_id!r} requires an explicit member_nodes set")
            members: list[str] = []
        else:
            members = [str(item) for item in members_raw]
            if len(members) != len(set(members)):
                errors.append(f"block {block_id!r} member_nodes contains duplicates")
        for member in members:
            if member not in nodes:
                errors.append(f"block {block_id!r} references absent local member {member!r}")
        if root_claim and root_claim not in members:
            errors.append(f"block {block_id!r} root_claim must be a member")
        if root_claim in nodes and nodes[root_claim].get("type") != "Claim":
            errors.append(f"block {block_id!r} root_claim {root_claim!r} is not a Claim")
        for output in block.get("output_claims") or []:
            if output not in members:
                errors.append(f"block {block_id!r} output {output!r} is not a member")
            if output in nodes and nodes[output].get("type") != "Claim":
                errors.append(f"block {block_id!r} output {output!r} is not a Claim")
        for field in (
            "input_nodes",
            "internal_nodes",
            "local_assumptions",
            "local_rebuttals",
        ):
            for node_id in block.get(field) or []:
                if node_id not in members:
                    errors.append(
                        f"block {block_id!r} {field} reference {node_id!r} is not a member"
                    )

        structural_node = nodes.get(block_id)
        if isinstance(structural_node, Mapping) and structural_node.get("type") == "ArgumentBlock":
            node_title = structural_node.get("text") or structural_node.get("title") or ""
            block_title = block.get("title") or ""
            if node_title and block_title and node_title != block_title:
                errors.append(
                    f"block {block_id!r} structural title conflicts with canonical block title"
                )
            if (structural_node.get("parent") or None) != (block.get("parent") or None):
                errors.append(
                    f"block {block_id!r} structural parent conflicts with canonical block parent"
                )
            executable_fields = {
                "root_claim",
                "member_nodes",
                "input_nodes",
                "output_claims",
                "acceptance_conditions",
            }
            conflicts = executable_fields.intersection(structural_node)
            if conflicts:
                errors.append(
                    f"block {block_id!r} structural node defines executable fields: "
                    f"{', '.join(sorted(conflicts))}"
                )

    _validate_block_hierarchy(blocks, errors)
    _validate_hierarchy(payload.get("hierarchy") or {}, nodes, errors)
    _validate_provenance(nodes, edges, blocks, errors)

    if errors:
        raise DurableValidationError(errors)


def _validate_block_hierarchy(blocks: Mapping[str, Any], errors: list[str]) -> None:
    parents: dict[str, str] = {}
    for block_id, block in blocks.items():
        if not isinstance(block, Mapping):
            continue
        parent = block.get("parent")
        if parent:
            if parent not in blocks:
                errors.append(f"block {block_id!r} parent {parent!r} is absent")
            else:
                parents[str(block_id)] = str(parent)
        for child in block.get("child_blocks") or []:
            if child not in blocks:
                errors.append(f"block {block_id!r} child {child!r} is absent")
            elif isinstance(blocks[child], Mapping):
                child_parent = blocks[child].get("parent")
                if child_parent not in (None, "", block_id):
                    errors.append(
                        f"block {block_id!r} child {child!r} disagrees on parent {child_parent!r}"
                    )
    for start in parents:
        seen: set[str] = set()
        current: str | None = start
        while current in parents:
            if current in seen:
                errors.append(f"block hierarchy contains a cycle through {current!r}")
                break
            seen.add(current)
            current = parents.get(current)


def _validate_hierarchy(
    hierarchy: Any, nodes: Mapping[str, Any], errors: list[str]
) -> None:
    if not isinstance(hierarchy, Mapping):
        errors.append("hierarchy must be a mapping")
        return
    parents: dict[str, str] = {}
    for parent, children in hierarchy.items():
        if parent not in nodes:
            errors.append(f"hierarchy parent {parent!r} is absent")
        for child in children or []:
            if child not in nodes:
                errors.append(f"hierarchy child {child!r} is absent")
            previous = parents.setdefault(str(child), str(parent))
            if previous != parent:
                errors.append(f"hierarchy child {child!r} has multiple parents")
    for node_id, node in nodes.items():
        if not isinstance(node, Mapping):
            continue
        declared_parent = node.get("parent")
        if declared_parent:
            if declared_parent not in nodes:
                errors.append(f"node {node_id!r} parent {declared_parent!r} is absent")
            hierarchy_parent = parents.get(str(node_id))
            if hierarchy_parent and hierarchy_parent != declared_parent:
                errors.append(
                    f"node {node_id!r} parent {declared_parent!r} conflicts with "
                    f"hierarchy parent {hierarchy_parent!r}"
                )
            parents.setdefault(str(node_id), str(declared_parent))
        for child in node.get("children") or []:
            if child not in nodes:
                errors.append(f"node {node_id!r} child {child!r} is absent")
                continue
            hierarchy_parent = parents.get(str(child))
            if hierarchy_parent and hierarchy_parent != node_id:
                errors.append(
                    f"node {node_id!r} child {child!r} conflicts with "
                    f"hierarchy parent {hierarchy_parent!r}"
                )
            parents.setdefault(str(child), str(node_id))
    for start in parents:
        seen: set[str] = set()
        current: str | None = start
        while current in parents:
            if current in seen:
                errors.append(f"node hierarchy contains a cycle through {current!r}")
                break
            seen.add(current)
            current = parents.get(current)


def _validate_provenance(
    nodes: Mapping[str, Any],
    edges: Iterable[Any],
    blocks: Mapping[str, Any],
    errors: list[str],
) -> None:
    duplicate_groups: dict[tuple[str, str], list[tuple[str, ProvenanceRecord]]] = defaultdict(list)
    for node_id, node in nodes.items():
        if not isinstance(node, Mapping):
            continue
        try:
            records = coerce_provenance(_record_list(node.get("provenance")))
            if node.get("type") == "Evidence":
                records = validate_evidence_provenance(str(node_id), records)
        except ProvenanceError as exc:
            errors.append(str(exc))
            continue
        for record in records:
            duplicate_groups[record.source_content_key()].append((f"node:{node_id}", record))
    for edge in edges:
        if not isinstance(edge, Mapping):
            continue
        try:
            records = coerce_provenance(_record_list(edge.get("provenance")))
        except ProvenanceError as exc:
            errors.append(f"edge {edge.get('id')!r}: {exc}")
            continue
        for record in records:
            duplicate_groups[record.source_content_key()].append((f"edge:{edge.get('id')}", record))
    for block_id, block in blocks.items():
        if not isinstance(block, Mapping):
            continue
        try:
            records = coerce_provenance(_record_list(block.get("provenance")))
        except ProvenanceError as exc:
            errors.append(f"block {block_id!r}: {exc}")
            continue
        for record in records:
            duplicate_groups[record.source_content_key()].append((f"block:{block_id}", record))

    for key, located_records in duplicate_groups.items():
        groups = {record.independence_group for _, record in located_records}
        if len(groups) <= 1:
            continue
        canonical_group = next(
            (
                record.independence_group
                for _, record in located_records
                if not record.reviewed_separation
            ),
            located_records[0][1].independence_group,
        )
        unreviewed_differences = [
            location
            for location, record in located_records
            if record.independence_group != canonical_group and not record.reviewed_separation
        ]
        if unreviewed_differences:
            errors.append(
                f"duplicate source/content {key!r} declares multiple independence groups "
                f"without reviewed separation at {', '.join(unreviewed_differences)}"
            )


def validate_snapshot(snapshot: ModelSnapshot) -> None:
    validate_model_payload(snapshot.authoring_payload())
    model_info = snapshot.model_payload.get("model")
    if not isinstance(model_info, Mapping) or model_info.get("id") != str(snapshot.model_id):
        raise DurableValidationError(
            ["snapshot model_id conflicts with canonical model payload model.id"]
        )


def normalize_explicit_import_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Rewrite one direct authoring payload to the sole current durable shape.

    This function is an explicit import boundary, not a normal-runtime reader.
    It produces current content in memory and leaves no legacy authority behind.
    It cannot invent evidentiary provenance, so evidence without sources remains
    invalid at commit time.
    """

    payload = copy.deepcopy(dict(raw))
    model_info = payload.setdefault("model", {})
    if not isinstance(model_info, dict):
        raise DurableValidationError(["import payload model must be a mapping"])
    existing_schema = model_info.get("schema_version")
    if existing_schema not in (None, "", SCHEMA_VERSION):
        raise DurableValidationError(
            [
                f"explicit import cannot guess unsupported schema {existing_schema!r}; "
                "a version-owned direct migration is required"
            ]
        )
    model_info["schema_version"] = SCHEMA_VERSION

    nodes = payload.setdefault("nodes", {})
    edges = payload.setdefault("edges", [])
    for index, edge in enumerate(edges):
        if isinstance(edge, dict) and not edge.get("id"):
            edge_binding = {
                "source": edge.get("source"),
                "target": edge.get("target"),
                "type": edge.get("type"),
                "ordinal": index,
            }
            digest = hashlib.sha256(canonical_json_bytes(edge_binding)).hexdigest()
            edge["id"] = f"edge-{digest}"

    blocks = payload.setdefault("blocks", {})
    if isinstance(blocks, dict):
        for block_id, block in blocks.items():
            if not isinstance(block, dict):
                continue
            block.setdefault("id", str(block_id))
            if not block.get("root_claim"):
                outputs = block.get("output_claims") or block.get("outputs") or []
                block["root_claim"] = outputs[0] if outputs else model_info.get("root_claim")
            members: list[str] = []
            for field in (
                "member_nodes",
                "input_nodes",
                "inputs",
                "internal_nodes",
                "internal",
                "output_claims",
                "outputs",
                "local_assumptions",
                "local_rebuttals",
            ):
                members.extend(str(item) for item in (block.get(field) or []))
            if block.get("root_claim"):
                members.append(str(block["root_claim"]))
            block["member_nodes"] = list(dict.fromkeys(members))

    # Normalize duplicate provenance within each artifact list. Cross-artifact
    # duplicates already derive the same default group from the same key.
    for collection in (nodes, blocks):
        if isinstance(collection, Mapping):
            for item in collection.values():
                if isinstance(item, dict) and item.get("provenance"):
                    item["provenance"] = [
                        record.to_dict()
                        for record in normalize_duplicate_independence(item["provenance"])
                    ]
    for edge in edges:
        if isinstance(edge, dict) and edge.get("provenance"):
            edge["provenance"] = [
                record.to_dict()
                for record in normalize_duplicate_independence(edge["provenance"])
            ]
    return payload


__all__ = [
    "DurableValidationError",
    "normalize_explicit_import_payload",
    "validate_model_payload",
    "validate_snapshot",
]
