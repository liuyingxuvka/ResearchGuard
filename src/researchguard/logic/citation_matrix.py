"""Claim-source-paragraph matrix for source-backed writing plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .model import LogicModel, Node


IMPORTANT_SALIENCE = {"core", "risk", "bridge"}
SUPPORT_NODE_TYPES = {"Evidence", "Result", "Method"}
LIMIT_NODE_TYPES = {"Limitation", "Qualifier", "Rebuttal", "Undercutter"}


@dataclass(frozen=True)
class ClaimSourceParagraphRow:
    claim_id: str
    claim_text: str
    source_ids: tuple[str, ...] = ()
    source_roles: dict[str, str] = field(default_factory=dict)
    source_locators: dict[str, str] = field(default_factory=dict)
    paragraph_locator: str = ""
    citation_marker: str = ""
    claim_strength: str = "medium"
    limitation: str = ""
    rebuttal: str = ""
    stale_when: tuple[str, ...] = ()
    importance: float = 0.0
    generated_marker: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "source_ids": list(self.source_ids),
            "source_roles": dict(self.source_roles),
            "source_locators": dict(self.source_locators),
            "paragraph_locator": self.paragraph_locator,
            "citation_marker": self.citation_marker,
            "claim_strength": self.claim_strength,
            "limitation": self.limitation,
            "rebuttal": self.rebuttal,
            "stale_when": list(self.stale_when),
            "importance": round(self.importance, 4),
            "generated_marker": self.generated_marker,
        }


@dataclass(frozen=True)
class MatrixFinding:
    code: str
    severity: str
    claim_id: str
    explanation: str
    suggested_repair: str
    paragraph_locator: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "claim_id": self.claim_id,
            "explanation": self.explanation,
            "suggested_repair": self.suggested_repair,
            "paragraph_locator": self.paragraph_locator,
        }


@dataclass(frozen=True)
class ClaimSourceParagraphMatrix:
    model_id: str
    rows: tuple[ClaimSourceParagraphRow, ...]
    source_backed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "source_backed": self.source_backed,
            "rows": [row.to_dict() for row in self.rows],
        }

    def row_for_claim(self, claim_id: str) -> ClaimSourceParagraphRow | None:
        return next((row for row in self.rows if row.claim_id == claim_id), None)

    def to_markdown(self) -> str:
        lines = [f"# Claim-Source-Paragraph Matrix: {self.model_id}", ""]
        if not self.rows:
            lines.append("- No claim rows.")
            return "\n".join(lines) + "\n"
        for row in self.rows:
            lines.extend(
                [
                    f"## {row.claim_id}",
                    f"- Claim: {row.claim_text}",
                    f"- Paragraph: {row.paragraph_locator or 'unassigned'}",
                    f"- Sources: {', '.join(row.source_ids) or 'none'}",
                    f"- Source roles: {_format_roles(row.source_roles)}",
                    f"- Citation marker: {row.citation_marker or 'missing'}",
                    f"- Claim strength: {row.claim_strength}",
                    f"- Limitation: {row.limitation or 'none'}",
                    f"- Rebuttal: {row.rebuttal or 'none'}",
                    f"- Stale when: {'; '.join(row.stale_when) or 'not declared'}",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"


def build_claim_source_paragraph_matrix(model: LogicModel, *, source_backed: bool = True) -> ClaimSourceParagraphMatrix:
    rows: list[ClaimSourceParagraphRow] = []
    for claim_id, claim in model.nodes.items():
        if claim.type != "Claim":
            continue
        source_ids: list[str] = []
        source_roles: dict[str, str] = {}
        source_locators: dict[str, str] = {}
        _merge_source_fields(claim, source_ids, source_roles, source_locators)
        support_nodes = _incoming_nodes(model, claim_id, SUPPORT_NODE_TYPES)
        limit_nodes = _incoming_nodes(model, claim_id, LIMIT_NODE_TYPES)
        for node in support_nodes:
            _merge_source_fields(node, source_ids, source_roles, source_locators, default_role=_role_for_support_node(node))
        limitation = "; ".join(node.text for node in limit_nodes if node.type in {"Limitation", "Qualifier"} and node.text)
        rebuttal = "; ".join(node.text for node in limit_nodes if node.type in {"Rebuttal", "Undercutter"} and node.text)
        unique_sources = tuple(dict.fromkeys(source_ids))
        explicit_marker = str(claim.metadata.get("citation_marker", "") or "")
        citation_marker = explicit_marker or _citation_marker(unique_sources)
        paragraph_locator = _paragraph_locator(model, claim)
        rows.append(
            ClaimSourceParagraphRow(
                claim_id=claim_id,
                claim_text=claim.text,
                source_ids=unique_sources,
                source_roles={source_id: source_roles.get(source_id, "unknown") for source_id in unique_sources},
                source_locators={source_id: source_locators.get(source_id, "") for source_id in unique_sources},
                paragraph_locator=paragraph_locator,
                citation_marker=citation_marker,
                claim_strength=_claim_strength(claim),
                limitation=limitation or str(claim.scope or ""),
                rebuttal=rebuttal,
                stale_when=_as_tuple(claim.metadata.get("stale_when")) or ("final prose, paragraph locator, source role, or citation marker changes",),
                importance=_importance(claim),
                generated_marker=bool(citation_marker and not explicit_marker),
            )
        )
    return ClaimSourceParagraphMatrix(model.id, tuple(rows), source_backed=source_backed)


def audit_claim_source_paragraph_matrix(matrix: ClaimSourceParagraphMatrix) -> tuple[MatrixFinding, ...]:
    findings: list[MatrixFinding] = []
    by_text: dict[str, list[ClaimSourceParagraphRow]] = {}
    for row in matrix.rows:
        important = row.importance >= 0.7
        if matrix.source_backed and important and not row.source_ids:
            findings.append(
                MatrixFinding(
                    "important_claim_missing_source",
                    "warning",
                    row.claim_id,
                    "Important source-backed claim has no source id in the matrix.",
                    "Attach a source id through source-library links, evidence metadata, or claim metadata before final prose.",
                    row.paragraph_locator,
                )
            )
        if row.source_ids and any(role in {"", "unknown"} for role in row.source_roles.values()):
            findings.append(
                MatrixFinding(
                    "missing_source_role",
                    "warning",
                    row.claim_id,
                    "A source-backed claim is missing a source role.",
                    "Mark source roles such as event_fact, official_claim, independent_report, limiting, expert_analysis, background, or hypothesis.",
                    row.paragraph_locator,
                )
            )
        if row.source_ids and not row.citation_marker:
            findings.append(
                MatrixFinding(
                    "missing_citation_marker",
                    "warning",
                    row.claim_id,
                    "A source-backed claim has no inline citation marker.",
                    "Add a compact marker such as [S1] or [S2, limiting].",
                    row.paragraph_locator,
                )
            )
        if row.source_ids and row.generated_marker:
            findings.append(
                MatrixFinding(
                    "generated_citation_marker_needs_review",
                    "info",
                    row.claim_id,
                    "LogicGuard generated a citation marker from source ids; final prose should confirm the marker style.",
                    "Replace generated markers with the final citation marker if the artifact uses a different citation style.",
                    row.paragraph_locator,
                )
            )
        if not row.paragraph_locator:
            findings.append(
                MatrixFinding(
                    "missing_paragraph_locator",
                    "info",
                    row.claim_id,
                    "Claim row has no paragraph, slide, or section locator.",
                    "Attach structured artifact metadata before claiming paragraph-level citation coverage.",
                    row.paragraph_locator,
                )
            )
        by_text.setdefault(_norm(row.claim_text), []).append(row)
    for rows in by_text.values():
        locators = {row.paragraph_locator for row in rows if row.paragraph_locator}
        if len(rows) > 1 and len(locators) > 1:
            for row in rows:
                findings.append(
                    MatrixFinding(
                        "duplicate_claim_placement",
                        "warning",
                        row.claim_id,
                        "The same claim text appears in multiple paragraph locations.",
                        "Merge repeated claims, turn one into a handoff, or explain the distinct paragraph role.",
                        row.paragraph_locator,
                    )
                )
    return tuple(findings)


def render_matrix_audit(findings: Iterable[MatrixFinding]) -> str:
    findings = tuple(findings)
    lines = ["# Claim-Source-Paragraph Matrix Audit", ""]
    if not findings:
        lines.append("- No matrix findings.")
    else:
        for finding in findings:
            locator = f" ({finding.paragraph_locator})" if finding.paragraph_locator else ""
            lines.append(f"- `{finding.code}` {finding.claim_id}{locator}: {finding.explanation} Repair: {finding.suggested_repair}")
    return "\n".join(lines).rstrip() + "\n"


def _incoming_nodes(model: LogicModel, node_id: str, node_types: set[str]) -> list[Node]:
    return [model.nodes[edge.source] for edge in model.incoming(node_id) if edge.source in model.nodes and model.nodes[edge.source].type in node_types]


def _merge_source_fields(
    node: Node,
    source_ids: list[str],
    source_roles: dict[str, str],
    source_locators: dict[str, str],
    *,
    default_role: str = "unknown",
) -> None:
    ids = _as_tuple(node.metadata.get("source_ids")) or _as_tuple(node.metadata.get("source_id"))
    for source_id in ids:
        if not source_id:
            continue
        source_ids.append(source_id)
        source_roles.setdefault(source_id, str(node.metadata.get("source_role", default_role) or default_role))
        source_locators.setdefault(source_id, str(node.metadata.get("source_locator", node.metadata.get("locator", "")) or ""))


def _role_for_support_node(node: Node) -> str:
    if node.type == "Method":
        return "method"
    if node.type == "Result":
        return "result"
    return "evidence"


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value in (None, "", [], ()):
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Iterable):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)


def _paragraph_locator(model: LogicModel, claim: Node) -> str:
    if claim.metadata.get("paragraph_locator"):
        return str(claim.metadata["paragraph_locator"])
    if claim.metadata.get("locator"):
        return str(claim.metadata["locator"])
    if claim.parent and claim.parent in model.nodes:
        parent = model.nodes[claim.parent]
        return str(parent.metadata.get("locator", parent.id))
    return ""


def _claim_strength(claim: Node) -> str:
    if claim.metadata.get("claim_strength"):
        return str(claim.metadata["claim_strength"])
    if claim.confidence >= 0.8:
        return "strong"
    if claim.confidence <= 0.45:
        return "weak"
    return "medium"


def _importance(claim: Node) -> float:
    if claim.importance is not None:
        return float(claim.importance)
    if claim.salience in IMPORTANT_SALIENCE:
        return 0.8
    return 0.5


def _citation_marker(source_ids: tuple[str, ...]) -> str:
    if not source_ids:
        return ""
    return "[" + "; ".join(source_ids) + "]"


def _format_roles(roles: dict[str, str]) -> str:
    return "; ".join(f"{source}: {role}" for source, role in roles.items()) or "none"


def _norm(value: str) -> str:
    return " ".join(value.lower().split())
