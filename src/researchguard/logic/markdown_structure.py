"""Conservative Markdown-like structured artifact intake."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .loader import load_model_from_dict
from .model import LogicModel


LOGIC_LABELS = {
    "claim": "Claim",
    "evidence": "Evidence",
    "warrant": "Warrant",
    "method": "Method",
    "result": "Result",
    "limitation": "Limitation",
    "limitations": "Limitation",
    "rebuttal": "Rebuttal",
    "rebuttals": "Rebuttal",
}

NODE_PREFIXES = {
    "Claim": "C",
    "Evidence": "E",
    "Warrant": "W",
    "Method": "M",
    "Result": "RSLT",
    "Limitation": "L",
    "Rebuttal": "R",
}


def markdown_to_model(
    text: str,
    *,
    model_id: str = "markdown_artifact",
    title: str = "",
    artifact_kind: str = "paper",
) -> LogicModel:
    return load_model_from_dict(
        markdown_to_model_dict(text, model_id=model_id, title=title, artifact_kind=artifact_kind)
    )


def markdown_to_model_dict(
    text: str,
    *,
    model_id: str = "markdown_artifact",
    title: str = "",
    artifact_kind: str = "paper",
) -> dict[str, Any]:
    lines = text.splitlines()
    document_title = title or _first_heading(lines, level=1) or "Markdown artifact"
    raw: dict[str, Any] = {
        "model": {
            "id": model_id,
            "title": document_title,
            "root_claim": None,
            "artifact_kind": artifact_kind,
            "source_format": "markdown",
        },
        "nodes": {
            "D0": {
                "type": "Document",
                "text": document_title,
                "artifact_kind": artifact_kind,
                "order_index": 0,
            }
        },
        "edges": [],
        "acceptance": {},
        "hierarchy": {"D0": []},
    }
    counters: defaultdict[str, int] = defaultdict(int)
    current_section = ""
    current_block = ""
    block_nodes: defaultdict[str, list[str]] = defaultdict(list)

    def next_id(node_type: str) -> str:
        counters[node_type] += 1
        return f"{NODE_PREFIXES.get(node_type, node_type[:1].upper())}{counters[node_type]}"

    def add_section(heading: str) -> str:
        nonlocal current_section, current_block
        node_id = f"S{len([node for node in raw['nodes'] if node.startswith('S')]) + 1}"
        raw["nodes"][node_id] = {
            "type": "Section",
            "text": heading,
            "artifact_kind": artifact_kind,
            "locator": heading,
            "order_index": len(raw["hierarchy"]["D0"]) + 1,
        }
        raw["hierarchy"]["D0"].append(node_id)
        raw["hierarchy"][node_id] = []
        current_section = node_id
        current_block = ""
        return node_id

    def ensure_section() -> str:
        return current_section or add_section("Main")

    def add_block(heading: str) -> str:
        nonlocal current_block
        section_id = ensure_section()
        node_id = f"B{len([node for node in raw['nodes'] if node.startswith('B')]) + 1}"
        raw["nodes"][node_id] = {
            "type": "ArgumentBlock",
            "text": heading,
            "artifact_kind": artifact_kind,
            "locator": heading,
            "order_index": len(raw["hierarchy"][section_id]) + 1,
        }
        raw["hierarchy"][section_id].append(node_id)
        raw["hierarchy"][node_id] = []
        current_block = node_id
        return node_id

    def ensure_block() -> str:
        return current_block or add_block("Argument block")

    heading_pattern = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
    field_pattern = re.compile(r"^\s*(?:[-*]\s*)?([A-Za-z][A-Za-z ]{1,30})\s*[:：-]\s*(.+?)\s*$")
    for line in lines:
        heading = heading_pattern.match(line)
        if heading:
            level = len(heading.group(1))
            heading_text = heading.group(2).strip()
            if level == 1:
                raw["nodes"]["D0"]["text"] = title or heading_text
                raw["model"]["title"] = title or heading_text
            elif level == 2:
                add_section(heading_text)
            else:
                add_block(heading_text)
            continue

        field = field_pattern.match(line)
        if not field:
            continue
        node_type = LOGIC_LABELS.get(field.group(1).strip().lower())
        if not node_type:
            continue
        block_id = ensure_block()
        node_id = next_id(node_type)
        raw["nodes"][node_id] = {
            "type": node_type,
            "text": field.group(2).strip(),
            "parent": block_id,
        }
        raw["hierarchy"][block_id].append(node_id)
        block_nodes[block_id].append(node_id)
        if node_type == "Claim" and raw["model"]["root_claim"] is None:
            raw["model"]["root_claim"] = node_id

    raw["edges"] = _standard_edges(raw, block_nodes)
    if raw["model"]["root_claim"]:
        raw["acceptance"] = _standard_acceptance(raw, block_nodes)
    return raw


def _standard_edges(raw: dict[str, Any], block_nodes: dict[str, list[str]]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    nodes = raw["nodes"]
    for node_ids in block_nodes.values():
        claims = [node_id for node_id in node_ids if nodes[node_id]["type"] == "Claim"]
        if not claims:
            continue
        target = claims[0]
        for node_id in node_ids:
            if node_id == target:
                continue
            node_type = nodes[node_id]["type"]
            edge_type = ""
            if node_type in {"Evidence", "Warrant", "Method", "Result"}:
                edge_type = "supports"
            elif node_type == "Limitation":
                edge_type = "qualifies"
            elif node_type == "Rebuttal":
                edge_type = "attacks"
            if edge_type:
                edges.append({"source": node_id, "target": target, "type": edge_type, "weight": 1.0})
    return edges


def _standard_acceptance(raw: dict[str, Any], block_nodes: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
    acceptance: dict[str, dict[str, Any]] = {}
    nodes = raw["nodes"]
    for node_ids in block_nodes.values():
        claims = [node_id for node_id in node_ids if nodes[node_id]["type"] == "Claim"]
        if not claims:
            continue
        target = claims[0]
        supports = [
            node_id
            for node_id in node_ids
            if nodes[node_id]["type"] in {"Evidence", "Warrant", "Method", "Result"}
        ]
        if supports:
            acceptance[target] = {"all_of": supports, "threshold": 0.6}
    return acceptance


def _first_heading(lines: list[str], *, level: int) -> str:
    prefix = "#" * level
    pattern = re.compile(rf"^{re.escape(prefix)}\s+(.+?)\s*$")
    for line in lines:
        match = pattern.match(line)
        if match:
            return match.group(1).strip()
    return ""
