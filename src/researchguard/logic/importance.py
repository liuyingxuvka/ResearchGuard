"""Importance and salience helpers for LogicGuard models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .model import Edge, LogicModel, Node


@dataclass(frozen=True)
class ImportanceRecord:
    subject_id: str
    subject_type: str
    text: str
    importance: float
    salience: str
    reason: str
    explicit: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.subject_id,
            "type": self.subject_type,
            "text": self.text,
            "importance": round(self.importance, 4),
            "salience": self.salience,
            "reason": self.reason,
            "explicit": self.explicit,
        }


@dataclass(frozen=True)
class ImportanceSummary:
    model_id: str
    records: tuple[ImportanceRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"model_id": self.model_id, "records": [record.to_dict() for record in self.records]}

    def to_markdown(self) -> str:
        lines = [f"# Importance Summary: {self.model_id}", ""]
        if not self.records:
            lines.append("- No model elements found.")
            return "\n".join(lines) + "\n"
        for record in self.records:
            lines.append(
                f"- {record.subject_id} ({record.subject_type}, {record.salience}, "
                f"{record.importance:.2f}): {record.text}"
            )
            lines.append(f"  - Reason: {record.reason}")
        return "\n".join(lines) + "\n"


def has_explicit_importance(model: LogicModel) -> bool:
    return any(node.importance is not None or node.salience for node in model.nodes.values()) or any(
        edge.importance is not None or edge.salience for edge in model.edges
    )


def summarize_importance(model: LogicModel, *, limit: int | None = 12) -> ImportanceSummary:
    records = [importance_for_node(model, node_id) for node_id in model.nodes]
    records.extend(importance_for_edge(model, edge) for edge in model.edges if edge.importance is not None or edge.salience)
    records = sorted(records, key=lambda record: (-record.importance, record.subject_id))
    if limit is not None:
        records = records[:limit]
    return ImportanceSummary(model.id, tuple(records))


def importance_for_node(model: LogicModel, node_id: str) -> ImportanceRecord:
    node = model.nodes[node_id]
    if node.importance is not None:
        importance = node.importance
        reason = node.importance_reason or "Declared node importance."
        explicit = True
    else:
        importance, reason = _infer_node_importance(model, node_id, node)
        explicit = False
    salience = node.salience or _infer_salience(node, importance, is_root=node_id == model.root_claim)
    return ImportanceRecord(node_id, node.type, node.text, _clamp(importance), salience, reason, explicit)


def importance_for_edge(model: LogicModel, edge: Edge) -> ImportanceRecord:
    subject_id = f"{edge.source}->{edge.target}:{edge.type}"
    text = edge.explanation or f"{edge.source} {edge.type} {edge.target}"
    if edge.importance is not None:
        importance = edge.importance
        reason = edge.importance_reason or "Declared edge importance."
        explicit = True
    else:
        importance = min(1.0, max(0.0, edge.weight))
        reason = "Inferred from edge weight because no explicit edge importance was declared."
        explicit = False
    salience = edge.salience or ("bridge" if edge.type in {"depends_on", "derives", "refines"} else "supporting")
    return ImportanceRecord(subject_id, "Edge", text, _clamp(importance), salience, reason, explicit)


def _infer_node_importance(model: LogicModel, node_id: str, node: Node) -> tuple[float, str]:
    base_by_type = {
        "Document": 0.55,
        "Section": 0.5,
        "ArgumentBlock": 0.48,
        "Claim": 0.65,
        "Premise": 0.45,
        "Evidence": 0.55,
        "Result": 0.58,
        "Warrant": 0.6,
        "Assumption": 0.58,
        "Rebuttal": 0.62,
        "Undercutter": 0.65,
        "Qualifier": 0.6,
        "Limitation": 0.7,
        "Context": 0.25,
        "Definition": 0.5,
        "Method": 0.5,
    }
    score = base_by_type.get(node.type, 0.45)
    reasons = [f"inferred from node type {node.type}"]
    if node_id == model.root_claim:
        score += 0.25
        reasons.append("root claim")
    outgoing = len(model.outgoing(node_id))
    incoming = len(model.incoming(node_id))
    if outgoing:
        score += min(0.15, outgoing * 0.04)
        reasons.append("downstream dependency")
    if incoming and node.type == "Claim":
        score += min(0.1, incoming * 0.03)
        reasons.append("supported local conclusion")
    if node.impact in {"high", "critical"}:
        score += 0.15
        reasons.append(f"{node.impact} impact")
    if node.role in {"handoff", "decision", "mainline"}:
        score += 0.12
        reasons.append(f"{node.role} role")
    return _clamp(score), ", ".join(reasons)


def _infer_salience(node: Node, importance: float, *, is_root: bool) -> str:
    if node.role:
        return node.role
    if is_root or importance >= 0.82:
        return "core"
    if node.type in {"Limitation", "Qualifier", "Rebuttal", "Undercutter", "Assumption"} and importance >= 0.55:
        return "risk"
    if node.type == "Warrant":
        return "bridge"
    if node.type in {"Evidence", "Result", "Method"}:
        return "supporting"
    if node.type == "Context" or importance < 0.35:
        return "background"
    return "supporting"


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))
