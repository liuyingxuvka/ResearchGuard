"""Structure-flow diagnostics for naturally structured artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from .importance import importance_for_node
from .model import LogicModel
from .structured_artifact import ArtifactBlock, node_block_index, ordered_artifact_blocks


@dataclass(frozen=True)
class StructureFinding:
    code: str
    severity: str
    affected_blocks: tuple[str, ...]
    explanation: str
    suggested_repair: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "affected_blocks": list(self.affected_blocks),
            "explanation": self.explanation,
            "suggested_repair": self.suggested_repair,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class StructureAuditReport:
    model_id: str
    findings: tuple[StructureFinding, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"model_id": self.model_id, "findings": [finding.to_dict() for finding in self.findings]}

    def to_markdown(self) -> str:
        lines = [f"# Structure Audit: {self.model_id}", ""]
        if not self.findings:
            lines.append("- No structure-flow issues identified.")
            return "\n".join(lines) + "\n"
        for finding in self.findings:
            blocks = ", ".join(finding.affected_blocks)
            lines.append(f"- {finding.code} ({finding.severity}, {blocks}): {finding.explanation}")
            lines.append(f"  - Repair: {finding.suggested_repair}")
        return "\n".join(lines) + "\n"


def audit_structure(model: LogicModel) -> StructureAuditReport:
    blocks = [block for block in ordered_artifact_blocks(model) if block.node_type in {"Section", "ArgumentBlock"}]
    findings: list[StructureFinding] = []
    findings.extend(_missing_handoffs(model, blocks))
    findings.extend(_late_limitations(model, blocks))
    findings.extend(_overloaded_blocks(model, blocks))
    findings.extend(_orphan_blocks(model, blocks))
    findings.extend(_duplicate_claims(model, blocks))
    findings.extend(_temporal_context_findings(model, blocks))
    return StructureAuditReport(model.id, tuple(_dedupe(findings)))


def _missing_handoffs(model: LogicModel, blocks: list[ArtifactBlock]) -> list[StructureFinding]:
    findings: list[StructureFinding] = []
    argument_blocks = [block for block in blocks if block.node_type == "ArgumentBlock"]
    for previous, current in zip(argument_blocks, argument_blocks[1:]):
        if _has_cross_block_edge(model, previous, current) or _has_handoff_role(current):
            continue
        findings.append(
            StructureFinding(
                "missing_handoff",
                "warning",
                (previous.block_id, current.block_id),
                "Consecutive artifact blocks have no declared transition, dependency, or handoff role.",
                "Add a concise handoff, dependency edge, or bridge block explaining why the next block follows.",
                {"previous_locator": previous.locator, "current_locator": current.locator},
            )
        )
    return findings


def _late_limitations(model: LogicModel, blocks: list[ArtifactBlock]) -> list[StructureFinding]:
    block_by_node = node_block_index(model)
    order_by_block = {block.block_id: block.order_index for block in blocks}
    findings: list[StructureFinding] = []
    for edge in model.edges:
        if edge.type != "qualifies":
            continue
        source = model.nodes.get(edge.source)
        target = model.nodes.get(edge.target)
        if not source or not target or source.type not in {"Limitation", "Qualifier"}:
            continue
        source_block = block_by_node.get(edge.source)
        target_block = block_by_node.get(edge.target)
        if not source_block or not target_block:
            continue
        source_order = order_by_block.get(source_block, 0)
        target_order = order_by_block.get(target_block, 0)
        if source_order > target_order and importance_for_node(model, edge.source).importance >= 0.65:
            findings.append(
                StructureFinding(
                    "late_limitation",
                    "error",
                    (target_block, source_block),
                    "A high-importance limitation appears after the conclusion it qualifies.",
                    "Move the limitation earlier or add a visible qualifier before the dependent conclusion.",
                    {"limitation": edge.source, "qualified_node": edge.target},
                )
            )
    return findings


def _overloaded_blocks(model: LogicModel, blocks: list[ArtifactBlock]) -> list[StructureFinding]:
    findings: list[StructureFinding] = []
    for block in blocks:
        important_claims = [
            claim_id
            for claim_id in block.claims
            if importance_for_node(model, claim_id).importance >= 0.75
        ]
        if len(important_claims) > 1:
            findings.append(
                StructureFinding(
                    "overloaded_block",
                    "warning",
                    (block.block_id,),
                    "One artifact block carries multiple high-importance claims.",
                    "Split the block or make one claim the visible main point and demote the rest.",
                    {"claims": important_claims},
                )
            )
    return findings


def _orphan_blocks(model: LogicModel, blocks: list[ArtifactBlock]) -> list[StructureFinding]:
    findings: list[StructureFinding] = []
    for block in blocks:
        if block.node_type != "ArgumentBlock" or not block.child_nodes:
            continue
        connected = any(
            edge.source in block.child_nodes or edge.target in block.child_nodes
            for edge in model.edges
        )
        if not connected and block.importance >= 0.45:
            findings.append(
                StructureFinding(
                    "orphan_block",
                    "info",
                    (block.block_id,),
                    "Artifact block has local content but no declared logical relationship to nearby material.",
                    "Add support, dependency, contextualization, or handoff edges to attach it to the story.",
                    {"locator": block.locator},
                )
            )
    return findings


def _duplicate_claims(model: LogicModel, blocks: list[ArtifactBlock]) -> list[StructureFinding]:
    by_text: dict[str, list[tuple[str, str]]] = {}
    for block in blocks:
        for claim_id in block.claims:
            key = _normalize(model.nodes[claim_id].text)
            if key:
                by_text.setdefault(key, []).append((block.block_id, claim_id))
    findings: list[StructureFinding] = []
    for claims in by_text.values():
        if len(claims) < 2:
            continue
        blocks_tuple = tuple(block_id for block_id, _ in claims)
        findings.append(
            StructureFinding(
                "duplicate_claim",
                "warning",
                blocks_tuple,
                "The same claim appears in multiple artifact blocks.",
                "Merge the repeated claim, turn one occurrence into a handoff, or clarify the distinct role of each block.",
                {"claims": [claim_id for _, claim_id in claims]},
            )
        )
    return findings


def _temporal_context_findings(model: LogicModel, blocks: list[ArtifactBlock]) -> list[StructureFinding]:
    block_by_node = node_block_index(model)
    findings: list[StructureFinding] = []
    for node_id, node in model.nodes.items():
        if node.type in {"Document", "Section", "ArgumentBlock"}:
            continue
        record = importance_for_node(model, node_id)
        metadata = node.metadata
        source_date = str(metadata.get("source_date", ""))
        coverage_period = str(metadata.get("coverage_period", ""))
        source_id = str(metadata.get("source_id", ""))
        block_id = block_by_node.get(node_id, node.parent or "")
        affected = (block_id,) if block_id else ()
        if metadata.get("current_state") and record.importance >= 0.65 and source_id and not (source_date or coverage_period):
            findings.append(
                StructureFinding(
                    "undated_current_state_source",
                    "warning",
                    affected,
                    "A current-state claim depends on source-linked material without source date or covered-period metadata.",
                    "Add source temporal metadata or qualify the current-state claim near the relevant paragraph or slide.",
                    {"node": node_id, "source_id": source_id},
                )
            )
        source_year = _leading_year(source_date)
        coverage_end = _coverage_end_year(coverage_period)
        if source_year is not None and coverage_end is not None and source_year > coverage_end and record.importance >= 0.6:
            findings.append(
                StructureFinding(
                    "source_date_after_coverage",
                    "info",
                    affected,
                    "A source date is later than the covered period; publication timing should not be treated as factual coverage.",
                    "Keep the covered period visible when using this source for a time-sensitive conclusion.",
                    {"node": node_id, "source_date": source_date, "coverage_period": coverage_period},
                )
            )
    return findings


def _has_cross_block_edge(model: LogicModel, previous: ArtifactBlock, current: ArtifactBlock) -> bool:
    previous_nodes = set(previous.child_nodes) | {previous.block_id}
    current_nodes = set(current.child_nodes) | {current.block_id}
    for edge in model.edges:
        if edge.source in previous_nodes and edge.target in current_nodes:
            return True
        if edge.source in current_nodes and edge.target in previous_nodes and edge.type in {"depends_on", "contextualizes", "derives", "refines"}:
            return True
    return False


def _has_handoff_role(block: ArtifactBlock) -> bool:
    return block.role in {"handoff", "bridge", "transition"}


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _leading_year(value: str) -> int | None:
    match = re.search(r"(?:19|20)\d{2}", value or "")
    return int(match.group(0)) if match else None


def _coverage_end_year(value: str) -> int | None:
    matches = re.findall(r"(?:19|20)\d{2}", value or "")
    return int(matches[-1]) if matches else None


def _dedupe(findings: list[StructureFinding]) -> list[StructureFinding]:
    seen: set[tuple[str, tuple[str, ...], str]] = set()
    result: list[StructureFinding] = []
    for finding in findings:
        key = (finding.code, finding.affected_blocks, finding.explanation)
        if key in seen:
            continue
        seen.add(key)
        result.append(finding)
    return result
