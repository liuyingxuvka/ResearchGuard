"""YAML and JSON loading for LogicGuard models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from .model import ArgumentBlock, Edge, LogicModel, Node
from .schema import SCHEMA_VERSION
from .validator import validate_model


class ModelLoadError(ValueError):
    """Raised when a LogicGuard model cannot be loaded."""


def load_model(path: str | Path, *, validate: bool = True) -> LogicModel:
    model_path = Path(path)
    if not model_path.exists():
        raise ModelLoadError(f"Model file not found: {model_path}")
    text = model_path.read_text(encoding="utf-8")
    if model_path.suffix.lower() == ".json":
        raw = json.loads(text)
    elif model_path.suffix.lower() in {".yaml", ".yml"}:
        raw = yaml.safe_load(text)
    else:
        raise ModelLoadError("LogicGuard models must be .yaml, .yml, or .json files")
    model = load_model_from_dict(raw, validate=validate)
    model.metadata.setdefault("source_path", str(model_path))
    return model


def load_model_from_dict(raw: Mapping[str, Any], *, validate: bool = True) -> LogicModel:
    if not isinstance(raw, Mapping):
        raise ModelLoadError("Model root must be a mapping")
    model_info = dict(raw.get("model") or {})
    model_id = str(model_info.pop("id", "logicguard_model"))
    title = str(model_info.pop("title", model_id))
    root_claim = model_info.pop("root_claim", None)
    schema_version = str(model_info.pop("schema_version", SCHEMA_VERSION))

    nodes_raw = raw.get("nodes") or {}
    if not isinstance(nodes_raw, Mapping):
        raise ModelLoadError("'nodes' must be a mapping")
    nodes: dict[str, Node] = {}
    for node_id, node_raw in nodes_raw.items():
        if not isinstance(node_raw, Mapping):
            raise ModelLoadError(f"Node {node_id} must be a mapping")
        node_data = dict(node_raw)
        node_type = str(node_data.pop("type", "Claim"))
        metadata = {
            key: value
            for key, value in node_data.items()
            if key
            not in {
                "text",
                "level",
                "scope",
                "state",
                "confidence",
                "active",
                "impact",
                "importance",
                "salience",
                "role",
                "importance_reason",
                "parent",
                "children",
                "provenance",
            }
        }
        node = Node(
            id=str(node_id),
            type=node_type,
            text=str(node_data.get("text", "")),
            level=str(node_data.get("level", "")),
            scope=_string_or_none(node_data.get("scope")),
            state=str(node_data.get("state", "UNDECIDED")),
            confidence=_float_or_default(node_data.get("confidence"), 0.5),
            active=bool(node_data.get("active", False)),
            impact=_string_or_none(node_data.get("impact")),
            importance=_optional_float(node_data.get("importance")),
            salience=_string_or_none(node_data.get("salience")),
            role=_string_or_none(node_data.get("role")),
            importance_reason=_string_or_none(node_data.get("importance_reason")),
            parent=_string_or_none(node_data.get("parent")),
            children=[str(item) for item in node_data.get("children", []) or []],
            metadata=metadata,
            provenance=list(node_data.get("provenance", []) or []),
        )
        nodes[node.id] = node

    edges: list[Edge] = []
    for edge_index, edge_raw in enumerate(raw.get("edges") or []):
        if not isinstance(edge_raw, Mapping):
            raise ModelLoadError("Each edge must be a mapping")
        edge_data = dict(edge_raw)
        metadata = {
            key: value
            for key, value in edge_data.items()
            if key not in {"id", "source", "target", "type", "weight", "explanation", "importance", "salience", "importance_reason"}
        }
        edges.append(
            Edge(
                source=str(edge_data.get("source", "")),
                target=str(edge_data.get("target", "")),
                type=str(edge_data.get("type", "")),
                weight=_float_or_default(edge_data.get("weight"), 1.0),
                explanation=str(edge_data.get("explanation", "")),
                importance=_optional_float(edge_data.get("importance")),
                salience=_string_or_none(edge_data.get("salience")),
                importance_reason=_string_or_none(edge_data.get("importance_reason")),
                metadata=metadata,
                id=str(edge_data.get("id") or f"edge-{edge_index:06d}"),
            )
        )

    hierarchy_raw = raw.get("hierarchy") or {}
    hierarchy = {
        str(parent): [str(child) for child in (children or [])]
        for parent, children in dict(hierarchy_raw).items()
    }
    for parent, children in hierarchy.items():
        for child_id in children:
            if child_id in nodes:
                nodes[child_id].parent = parent
        if parent in nodes:
            nodes[parent].children = list(children)

    blocks = _parse_blocks(raw.get("blocks") or {})

    model = LogicModel(
        id=model_id,
        title=title,
        root_claim=_string_or_none(root_claim),
        nodes=nodes,
        edges=edges,
        acceptance={str(key): dict(value or {}) for key, value in dict(raw.get("acceptance") or {}).items()},
        hierarchy=hierarchy,
        blocks=blocks,
        metadata=dict(model_info),
        schema_version=schema_version,
    )
    if validate:
        validation = validate_model(model)
        if not validation.ok:
            messages = "; ".join(validation.errors)
            raise ModelLoadError(f"Invalid LogicGuard model: {messages}")
    return model


def _parse_blocks(raw_blocks: Mapping[str, Any]) -> dict[str, ArgumentBlock]:
    blocks: dict[str, ArgumentBlock] = {}
    for block_id, block_raw in dict(raw_blocks).items():
        if not isinstance(block_raw, Mapping):
            raise ModelLoadError(f"ArgumentBlock {block_id} must be a mapping")
        data = dict(block_raw)
        output_claims = [str(item) for item in data.get("output_claims", data.get("outputs", [])) or []]
        input_nodes = [str(item) for item in data.get("input_nodes", data.get("inputs", [])) or []]
        internal_nodes = [str(item) for item in data.get("internal_nodes", data.get("internal", [])) or []]
        local_assumptions = [str(item) for item in data.get("local_assumptions", []) or []]
        local_rebuttals = [str(item) for item in data.get("local_rebuttals", []) or []]
        root_claim = _string_or_none(data.get("root_claim"))
        if root_claim is None and output_claims:
            root_claim = output_claims[0]
        known_fields = {
            "id",
            "title",
            "level",
            "parent",
            "input_nodes",
            "inputs",
            "internal_nodes",
            "internal",
            "output_claims",
            "outputs",
            "local_assumptions",
            "local_rebuttals",
            "acceptance_conditions",
            "acceptance",
            "diagnostics",
            "child_blocks",
            "root_claim",
            "member_nodes",
            "input_classifications",
            "output_classifications",
            "provenance",
        }
        blocks[str(block_id)] = ArgumentBlock(
            id=str(block_id),
            title=str(data.get("title", block_id)),
            level=str(data.get("level", "")),
            parent=_string_or_none(data.get("parent")),
            input_nodes=input_nodes,
            internal_nodes=internal_nodes,
            output_claims=output_claims,
            local_assumptions=local_assumptions,
            local_rebuttals=local_rebuttals,
            acceptance_conditions=dict(data.get("acceptance_conditions", data.get("acceptance", {})) or {}),
            diagnostics=[str(item) for item in data.get("diagnostics", []) or []],
            child_blocks=[str(item) for item in data.get("child_blocks", []) or []],
            root_claim=root_claim,
            member_nodes=[str(item) for item in data.get("member_nodes", []) or []],
            input_classifications={str(key): str(value) for key, value in dict(data.get("input_classifications", {}) or {}).items()},
            output_classifications={str(key): str(value) for key, value in dict(data.get("output_classifications", {}) or {}).items()},
            metadata={key: value for key, value in data.items() if key not in known_fields},
            provenance=list(data.get("provenance", []) or []),
        )
    return blocks


def _float_or_default(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ModelLoadError(f"numeric field must be a number, got {value!r}")


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
