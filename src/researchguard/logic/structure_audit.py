"""Structure-flow diagnostics for naturally structured artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Mapping

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


def audit_structure(model: LogicModel, selection_request: Mapping[str, Any] | Any | None = None) -> StructureAuditReport:
    blocks = [block for block in ordered_artifact_blocks(model) if block.node_type in {"Section", "ArgumentBlock"}]
    findings: list[StructureFinding] = []
    if selection_request is None:
        findings.append(
            StructureFinding(
                "coverage_gap",
                "error",
                (),
                "No current selection request was supplied, so cross-unit contribution flow cannot be audited.",
                "Provide the current selection request; a model-only artifact scan is local diagnostics, not a complete synthesis audit.",
                {"scope": "local_only"},
            )
        )
    else:
        findings.extend(_audit_unit_contributions(model, selection_request))
    findings.extend(_missing_handoffs(model, blocks))
    findings.extend(_late_limitations(model, blocks))
    findings.extend(_overloaded_blocks(model, blocks))
    findings.extend(_orphan_blocks(model, blocks))
    findings.extend(_duplicate_claims(model, blocks))
    findings.extend(_temporal_context_findings(model, blocks))
    return StructureAuditReport(model.id, tuple(_dedupe(findings)))


def _audit_unit_contributions(model: LogicModel, request: Mapping[str, Any] | Any) -> list[StructureFinding]:
    """Check the cross-block contribution declared by the A03 unit request.

    A local support edge only proves local support. It does not prove that a
    unit advances the selected artifact argument or is consumed downstream.
    """
    raw_units = request.get("units", ()) if isinstance(request, Mapping) else getattr(request, "units", ())
    if isinstance(raw_units, Mapping) or not isinstance(raw_units, (list, tuple)) or not raw_units:
        return [StructureFinding("coverage_gap", "error", (),
            "No structured argument units were supplied for cross-block contribution audit.",
            "Provide the current selection request with complete unit, parent, and downstream bindings.", {})]
    units = [dict(item) if isinstance(item, Mapping) else item.to_dict() for item in raw_units]
    by_id: dict[str, dict[str, Any]] = {}
    findings: list[StructureFinding] = []
    for index, unit in enumerate(units):
        unit_id = str(unit.get("unit_id", "") or "")
        if not unit_id:
            findings.append(StructureFinding(
                "coverage_gap", "error", (f"unit[{index}]",),
                "A structured argument unit has no stable identifier.",
                "Supply a unique unit_id for every unit.", {},
            ))
            continue
        if unit_id in by_id:
            findings.append(StructureFinding(
                "duplicate_unit", "error", (unit_id,),
                "The current composition contains more than one unit with the same identifier.",
                "Assign each unit a unique identifier before auditing contribution flow.", {},
            ))
            continue
        by_id[unit_id] = unit

    raw_order = request.get("body_unit_order", ()) if isinstance(request, Mapping) else getattr(request, "body_unit_order", ())
    body_order = tuple(str(value) for value in raw_order if str(value)) if isinstance(raw_order, (list, tuple)) else ()
    if not body_order:
        # An order is required for a complete cross-unit audit.  The supplied
        # list is used only to make diagnostics deterministic; it is never a
        # success substitute for the explicit order validated by synthesis.
        body_order = tuple(
            str(unit.get("unit_id", ""))
            for unit in units
            if str(unit.get("unit_id", "")) and str(unit.get("placement", "")) == "body"
        )
        findings.append(StructureFinding(
            "coverage_gap", "error", (),
            "The composition does not provide an explicit body_unit_order.",
            "Provide the current reader-selected body order so sibling and downstream obligations can be checked.",
            {"derived_order_for_diagnostics": list(body_order)},
        ))
    order_index = {unit_id: index for index, unit_id in enumerate(body_order)}
    body_ids = {unit_id for unit_id, unit in by_id.items() if str(unit.get("placement", "")) == "body"}
    unknown_order_ids = sorted(set(body_order).difference(by_id))
    if unknown_order_ids:
        findings.append(StructureFinding(
            "coverage_gap", "error", tuple(unknown_order_ids),
            "The body order references units that are absent from the current composition.",
            "Use each admitted body unit exactly once in body_unit_order.",
            {"unknown_unit_ids": unknown_order_ids},
        ))
    if set(body_order) != body_ids:
        findings.append(StructureFinding(
            "coverage_gap", "error", tuple(sorted(body_ids)),
            "The explicit body order does not cover exactly the body units in the composition.",
            "Reconcile body_unit_order with unit placement before reviewing contribution flow.",
            {"body_unit_ids": sorted(body_ids), "body_unit_order": list(body_order)},
        ))

    root_claim = model.root_claim
    consumers: dict[str, list[str]] = {unit_id: [] for unit_id in by_id}
    for unit in by_id.values():
        unit_id = str(unit.get("unit_id", ""))
        for predecessor in unit.get("predecessor_unit_ids", ()) if isinstance(unit.get("predecessor_unit_ids", ()), (list, tuple)) else ():
            if str(predecessor) in consumers:
                consumers[str(predecessor)].append(unit_id)
    # Only native model relationships prove that one unit contributes to or
    # consumes another.  Caller-provided strings such as ``contributes_to``
    # and ``parent_unit_ids`` are intentionally ignored.
    def _claims(unit: Mapping[str, Any]) -> set[str]:
        values = unit.get("claim_ids", ())
        return {str(value) for value in values} if isinstance(values, (list, tuple, set)) else set()

    def _related(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
        left_claims, right_claims = _claims(left), _claims(right)
        if not left_claims or not right_claims:
            return False
        forward = {"supports", "depends_on", "refines", "derives", "aggregates", "explains", "contextualizes", "qualifies", "attacks", "undercuts", "contradicts"}
        reverse_dependency = {"depends_on", "refines", "derives", "aggregates", "explains", "contextualizes"}
        for edge in model.edges:
            if edge.source in left_claims and edge.target in right_claims and edge.type in forward:
                return True
            if edge.source in right_claims and edge.target in left_claims and edge.type in reverse_dependency:
                return True
        return False

    for unit in by_id.values():
        unit_id = str(unit.get("unit_id", ""))
        claim_ids = _claims(unit)
        parent_id = str(unit.get("parent_unit_id", "") or "")
        if parent_id and parent_id not in by_id:
            findings.append(StructureFinding("missing_parent_contribution", "error", (unit_id,),
                "The unit names a parent unit that is absent from the current composition.",
                "Bind the unit to an existing parent unit or explicitly make it a root unit.", {"parent_unit_id": parent_id}))
        if parent_id in by_id:
            parent_claims = _claims(by_id[parent_id])
            if not _related(unit, by_id[parent_id]):
                findings.append(StructureFinding("missing_parent_contribution", "error", (parent_id, unit_id),
                    "The unit has local claims but no declared or modeled contribution to its parent unit.",
                    "Add a real native relation between a child claim and a parent claim; a caller string cannot substitute for that relation.",
                    {"parent_unit_id": parent_id, "claim_ids": sorted(claim_ids), "parent_claim_ids": sorted(parent_claims)}))
        placement = str(unit.get("placement", "") or "")

        if root_claim and root_claim in claim_ids and (placement != "body" or str(unit.get("progression_relation", "")) != "concludes"):
            findings.append(StructureFinding("unrecovered_conclusion_obligation", "error", (unit_id,),
                "The model root conclusion is not recovered by a concluding body unit.",
                "Place the root claim in a body unit with progression_relation=concludes.", {"root_claim": root_claim, "placement": placement}))

    # Siblings are checked per parent.  The first unit in each parent group is
    # allowed to have no predecessor; every subsequent body sibling needs an
    # earlier sibling and a native relation proving why it follows.
    sibling_groups: dict[str, list[dict[str, Any]]] = {}
    for unit in by_id.values():
        if str(unit.get("placement", "")) != "body":
            continue
        parent_id = str(unit.get("parent_unit_id", "") or "<root>")
        sibling_groups.setdefault(parent_id, []).append(unit)
    for parent_id, siblings in sibling_groups.items():
        siblings.sort(key=lambda row: (order_index.get(str(row.get("unit_id", "")), 10**9), str(row.get("unit_id", ""))))
        for position, unit in enumerate(siblings):
            if position == 0:
                continue
            unit_id = str(unit.get("unit_id", ""))
            predecessors = {str(value) for value in unit.get("predecessor_unit_ids", ())} if isinstance(unit.get("predecessor_unit_ids", ()), (list, tuple, set)) else set()
            earlier_siblings = {str(row.get("unit_id", "")) for row in siblings[:position]}
            valid_predecessors = predecessors.intersection(earlier_siblings)
            if not valid_predecessors or not any(_related(by_id[pred], unit) for pred in valid_predecessors):
                findings.append(StructureFinding("missing_sibling_progression", "error", (parent_id, unit_id),
                    "A body sibling has no earlier sibling with a native relation explaining its position.",
                    "Declare an earlier sibling predecessor and connect the corresponding claims with a valid model relation.",
                    {"parent_unit_id": parent_id, "earlier_sibling_ids": sorted(earlier_siblings), "predecessor_unit_ids": sorted(predecessors)}))

    # A body unit must have a visible later consumer unless it is the explicit
    # conclusion.  Merely naming a predecessor does not establish consumption.
    for unit_id, unit in by_id.items():
        if str(unit.get("placement", "")) != "body":
            continue
        claim_ids = _claims(unit)
        is_conclusion = str(unit.get("progression_relation", "")) == "concludes" and (not root_claim or root_claim in claim_ids)
        if is_conclusion:
            continue
        later_consumers = []
        for candidate_id, candidate in by_id.items():
            if candidate_id == unit_id or str(candidate.get("placement", "")) != "body":
                continue
            if order_index.get(candidate_id, 10**9) <= order_index.get(unit_id, -1):
                continue
            predecessors = candidate.get("predecessor_unit_ids", ())
            if isinstance(predecessors, (list, tuple, set)) and unit_id in {str(value) for value in predecessors} and _related(unit, candidate):
                later_consumers.append(candidate_id)
        if not later_consumers:
            findings.append(StructureFinding("missing_downstream_consumer", "error", (unit_id,),
                "A body unit is not consumed by a later body unit through a native model relation and is not the concluding unit.",
                "Bind it to a later visible consumer with predecessor_unit_ids and a valid cross-unit claim relation.",
                {"unit_id": unit_id, "progression_relation": unit.get("progression_relation", "")}))

    if root_claim and not any(root_claim in _claims(unit) and str(unit.get("placement", "")) == "body" and str(unit.get("progression_relation", "")) == "concludes" for unit in by_id.values()):
        findings.append(StructureFinding("unrecovered_conclusion_obligation", "error", (),
            "The selected unit request does not contain the model root conclusion.",
            "Add the root claim to the concluding unit or provide a native disposition for the conclusion obligation.", {"root_claim": root_claim}))

    # A child obligation is also an ancestor obligation.  Keep this explicit
    # in the report so a grandchild gap cannot be mistaken for a local repair:
    # every real parent on the path remains non-closed until the descendant is
    # repaired.  This is deliberately derived from the validated parent graph
    # and never from caller strings such as ``parent_unit_ids``.
    blocking_units = {
        affected
        for finding in findings
        if finding.severity in {"error", "critical"}
        for affected in finding.affected_blocks
        if affected in by_id
    }
    ancestors: dict[str, tuple[str, ...]] = {}
    for unit_id in by_id:
        path: list[str] = []
        cursor = str(by_id[unit_id].get("parent_unit_id", "") or "")
        seen: set[str] = set()
        while cursor in by_id and cursor not in seen:
            path.append(cursor)
            seen.add(cursor)
            cursor = str(by_id[cursor].get("parent_unit_id", "") or "")
        ancestors[unit_id] = tuple(path)
    propagated: set[tuple[str, str]] = set()
    for blocked in sorted(blocking_units):
        for ancestor in ancestors.get(blocked, ()):
            key = (ancestor, blocked)
            if key in propagated:
                continue
            propagated.add(key)
            findings.append(StructureFinding(
                "ancestor_nonclosure",
                "error",
                (ancestor, blocked),
                "A descendant unit has an unresolved contribution obligation, so each real ancestor remains non-closed.",
                "Repair the descendant's native contribution and re-run the complete parent-to-root audit.",
                {"ancestor_unit_id": ancestor, "blocked_descendant_unit_id": blocked},
            ))
    return findings


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
