"""Artifact story synthesis from LogicGuard models."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import re
from typing import Any, Iterable, Mapping

from .citation_matrix import ClaimSourceParagraphMatrix, build_claim_source_paragraph_matrix
from .importance import ImportanceRecord, summarize_importance
from .model import LogicModel


@dataclass(frozen=True)
class SynthesisItem:
    node_id: str
    node_type: str
    salience: str
    importance: float
    text: str
    reason: str
    treatment: str = ""
    source_id: str = ""
    source_ids: tuple[str, ...] = ()
    source_roles: dict[str, str] = field(default_factory=dict)
    paragraph_locator: str = ""
    citation_marker: str = ""
    claim_strength: str = ""
    limitation: str = ""
    branch_id: str = ""
    anchor_node_id: str = ""
    anchor_block_id: str = ""
    branch_role: str = ""
    source_date: str = ""
    coverage_period: str = ""
    temporal_role: str = ""
    temporal_caveat: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "salience": self.salience,
            "importance": round(self.importance, 4),
            "text": self.text,
            "reason": self.reason,
            "treatment": self.treatment,
            "source_id": self.source_id,
            "source_ids": list(self.source_ids),
            "source_roles": dict(self.source_roles),
            "paragraph_locator": self.paragraph_locator,
            "citation_marker": self.citation_marker,
            "claim_strength": self.claim_strength,
            "limitation": self.limitation,
            "branch_id": self.branch_id,
            "anchor_node_id": self.anchor_node_id,
            "anchor_block_id": self.anchor_block_id,
            "branch_role": self.branch_role,
            "source_date": self.source_date,
            "coverage_period": self.coverage_period,
            "temporal_role": self.temporal_role,
            "temporal_caveat": self.temporal_caveat,
        }
        return {key: value for key, value in data.items() if value not in ("", [], (), None)}


@dataclass(frozen=True)
class SynthesisPlan:
    model_id: str
    target_goal: str
    profile: str
    selected_items: tuple[SynthesisItem, ...]
    omitted_items: tuple[SynthesisItem, ...] = ()
    missing_additions: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "target_goal": self.target_goal,
            "profile": self.profile,
            "selected_items": [item.to_dict() for item in self.selected_items],
            "omitted_items": [item.to_dict() for item in self.omitted_items],
            "missing_additions": list(self.missing_additions),
            "notes": list(self.notes),
        }

    def to_markdown(self) -> str:
        lines = [f"# Synthesis Plan: {self.target_goal}", "", f"- Profile: {self.profile}", ""]
        lines.append("## Selected Story Items")
        if not self.selected_items:
            lines.append("- No selected items.")
        for index, item in enumerate(self.selected_items, start=1):
            treatment = f", treatment={item.treatment}" if item.treatment else ""
            temporal = f", time={item.temporal_role}" if item.temporal_role else ""
            lines.append(f"{index}. {item.node_id} ({item.node_type}, {item.salience}, {item.importance:.2f}{treatment}{temporal}): {item.text}")
            lines.append(f"   - Reason: {item.reason}")
            if item.temporal_caveat:
                lines.append(f"   - Temporal context: {item.temporal_caveat}")
            if item.source_ids or item.citation_marker or item.paragraph_locator:
                lines.append(f"   - Citation plan: {item.citation_marker or 'missing marker'} at {item.paragraph_locator or 'unassigned paragraph'}")
                if item.source_roles:
                    roles = "; ".join(f"{source}: {role}" for source, role in item.source_roles.items())
                    lines.append(f"   - Source roles: {roles}")
        lines.append("")
        lines.append("## Missing Additions")
        lines.extend(f"- {item}" for item in self.missing_additions) if self.missing_additions else lines.append("- None identified.")
        if self.omitted_items:
            lines.append("")
            lines.append("## Omitted Lower-Priority Items")
            for item in self.omitted_items:
                treatment = f", treatment={item.treatment}" if item.treatment else ""
                lines.append(f"- {item.node_id} ({item.salience}, {item.importance:.2f}{treatment}): {item.text}")
        return "\n".join(lines) + "\n"


def synthesize_artifact_plan(
    model: LogicModel,
    *,
    target_goal: str,
    profile: str = "presentation",
    max_items: int = 8,
    source_branches: Iterable[Any] = (),
) -> SynthesisPlan:
    if not target_goal:
        raise ValueError("target_goal is required for artifact synthesis")
    records = [
        record
        for record in summarize_importance(model, limit=None).records
        if record.subject_type not in {"Document", "Section", "ArgumentBlock", "Edge"} and record.text
    ]
    branch_items = [_item_from_branch(branch) for branch in source_branches]
    citation_matrix = build_claim_source_paragraph_matrix(model)
    candidates = [*_branch_goal_matches(branch_items, target_goal), *(_item_from_record(record, model, citation_matrix) for record in records)]
    candidates = _with_temporal_roles(candidates)
    candidates = sorted(candidates, key=lambda item: (-item.importance, item.node_id))
    selected = tuple(candidates[:max_items])
    omitted = tuple(_omitted_item(item) for item in candidates[max_items : max_items + 10])
    selected_records = records[:max_items]
    missing = tuple(_missing_additions(selected_records))
    notes = (
        "Synthesis selects from declared model nodes; missing additions are requests for new support, not invented evidence.",
        "Source branches are reusable provenance chunks; verify their anchors and branch audits before final drafting.",
        "Temporal context organizes source chronology but does not override importance/treatment selection or prove newer material is truer.",
        "Run argument and structure diagnostics after drafting from this plan.",
    )
    return SynthesisPlan(model.id, target_goal, profile, selected, omitted, missing, notes)


def _item_from_record(record: ImportanceRecord, model: LogicModel, citation_matrix: ClaimSourceParagraphMatrix) -> SynthesisItem:
    metadata: Mapping[str, Any] = {}
    if record.subject_id in model.nodes:
        metadata = model.nodes[record.subject_id].metadata
    citation_row = citation_matrix.row_for_claim(record.subject_id)
    source_ids = citation_row.source_ids if citation_row else ()
    return SynthesisItem(
        node_id=record.subject_id,
        node_type=record.subject_type,
        salience=record.salience,
        importance=record.importance,
        text=record.text,
        reason=record.reason,
        treatment=_treatment_for(record.subject_type, record.salience, record.importance),
        source_id=str(metadata.get("source_id", "") or (source_ids[0] if source_ids else "")),
        source_ids=source_ids,
        source_roles=citation_row.source_roles if citation_row else {},
        paragraph_locator=citation_row.paragraph_locator if citation_row else "",
        citation_marker=citation_row.citation_marker if citation_row else "",
        claim_strength=citation_row.claim_strength if citation_row else "",
        limitation=citation_row.limitation if citation_row else "",
        source_date=str(metadata.get("source_date", "")),
        coverage_period=str(metadata.get("coverage_period", "")),
    )


def _item_from_branch(branch: Any) -> SynthesisItem:
    data = branch if isinstance(branch, Mapping) else _object_public_data(branch)
    branch_id = str(data.get("branch_id", ""))
    source_id = str(data.get("source_id", ""))
    topic_focus = str(data.get("topic_focus", ""))
    branch_role = str(data.get("branch_role", ""))
    source_date = str(data.get("source_date", ""))
    coverage_period = str(data.get("coverage_period", ""))
    note = str(data.get("note", ""))
    locator = str(data.get("locator", ""))
    text_parts = [part for part in (topic_focus, branch_role, note, locator) if part]
    importance = data.get("importance")
    try:
        numeric_importance = 0.55 if importance in (None, "") else float(importance)
    except (TypeError, ValueError):
        numeric_importance = 0.55
    salience = str(data.get("salience", "")) or _salience_for_branch_role(branch_role, numeric_importance)
    anchor_node_id = str(data.get("anchor_node_id", ""))
    anchor_block_id = str(data.get("anchor_block_id", ""))
    reason = "Reusable source-library deepening branch"
    if anchor_node_id or anchor_block_id:
        reason += f" anchored to {anchor_node_id or anchor_block_id}"
    return SynthesisItem(
        node_id=branch_id or f"{source_id}:{topic_focus}",
        node_type="SourceBranch",
        salience=salience,
        importance=min(1.0, max(0.0, numeric_importance)),
        text=" | ".join(text_parts) or branch_id or source_id,
        reason=reason + ".",
        treatment=_treatment_for("SourceBranch", salience, numeric_importance),
        source_id=source_id,
        branch_id=branch_id,
        anchor_node_id=anchor_node_id,
        anchor_block_id=anchor_block_id,
        branch_role=branch_role,
        source_date=source_date,
        coverage_period=coverage_period,
    )


def _branch_goal_matches(items: list[SynthesisItem], target_goal: str) -> list[SynthesisItem]:
    tokens = {token for token in target_goal.lower().replace("-", " ").split() if len(token) > 2}
    if not tokens:
        return items
    matched: list[SynthesisItem] = []
    unmatched: list[SynthesisItem] = []
    for item in items:
        haystack = f"{item.text} {item.branch_role} {item.salience}".lower()
        if any(token in haystack for token in tokens):
            matched.append(item)
        else:
            unmatched.append(item)
    return [*matched, *unmatched]


def _object_public_data(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        result = value.to_dict()
        return dict(result) if isinstance(result, Mapping) else {}
    return {
        key: getattr(value, key)
        for key in (
            "branch_id",
            "source_id",
            "topic_focus",
            "branch_role",
            "note",
            "locator",
            "importance",
            "salience",
            "anchor_node_id",
            "anchor_block_id",
            "source_date",
            "coverage_period",
        )
        if hasattr(value, key)
    }


def _with_temporal_roles(items: list[SynthesisItem]) -> list[SynthesisItem]:
    dated_years = [_leading_year(item.source_date) for item in items if item.source_date]
    dated_years = [year for year in dated_years if year is not None]
    min_year = min(dated_years) if dated_years else None
    max_year = max(dated_years) if dated_years else None
    return [_with_temporal_role(item, min_year=min_year, max_year=max_year) for item in items]


def _with_temporal_role(item: SynthesisItem, *, min_year: int | None, max_year: int | None) -> SynthesisItem:
    role = ""
    caveat = ""
    source_year = _leading_year(item.source_date)
    coverage_end = _coverage_end_year(item.coverage_period)
    if item.source_date and min_year is not None and max_year is not None and min_year != max_year and source_year is not None:
        if source_year == min_year:
            role = "historical"
        elif source_year == max_year:
            role = "recent"
        else:
            role = "source_dated"
    elif item.source_date:
        role = "source_dated"
    elif item.coverage_period:
        role = "covered_period"
    elif item.source_id:
        role = "unknown_time"
    if item.coverage_period and role != "unknown_time":
        caveat = f"Coverage period: {item.coverage_period}."
    if source_year is not None and coverage_end is not None and source_year > coverage_end:
        caveat = f"Published/source date {item.source_date} is later than covered period {item.coverage_period}; do not treat publication date as coverage."
        role = "covered_period"
    elif role == "unknown_time":
        caveat = "Source time is unmarked; avoid treating it as current-state evidence without confirmation."
    return replace(item, temporal_role=role, temporal_caveat=caveat)


def _leading_year(value: str) -> int | None:
    match = re.search(r"(?:19|20)\d{2}", value or "")
    return int(match.group(0)) if match else None


def _coverage_end_year(value: str) -> int | None:
    matches = re.findall(r"(?:19|20)\d{2}", value or "")
    return int(matches[-1]) if matches else None


def _salience_for_branch_role(branch_role: str, importance: float) -> str:
    role = branch_role.lower()
    if any(token in role for token in ("limit", "risk", "scope", "rebut", "attack")):
        return "risk"
    if any(token in role for token in ("mechanism", "warrant", "bridge", "explain")):
        return "bridge"
    if importance >= 0.8:
        return "core"
    return "supporting"


def _treatment_for(node_type: str, salience: str, importance: float) -> str:
    salience_key = salience.lower()
    if salience_key == "optional" or importance < 0.35:
        return "omit"
    if salience_key == "background" or importance < 0.5:
        return "brief"
    if importance >= 0.85 or salience_key in {"core", "risk"}:
        return "deep"
    if salience_key == "bridge" and importance >= 0.7:
        return "deep"
    if node_type in {"Limitation", "Qualifier", "Rebuttal", "Undercutter"} and importance >= 0.65:
        return "deep"
    if importance >= 0.6:
        return "normal"
    return "brief"


def _omitted_item(item: SynthesisItem) -> SynthesisItem:
    if item.treatment == "omit":
        return item
    if item.importance >= 0.6 or item.salience.lower() in {"core", "risk", "bridge"}:
        return replace(item, treatment="appendix")
    return replace(item, treatment="omit")


def _missing_additions(records: list[ImportanceRecord]) -> list[str]:
    node_types = {record.subject_type for record in records}
    saliences = {record.salience for record in records}
    missing: list[str] = []
    if "Claim" in node_types and "Warrant" not in node_types:
        missing.append("Add or select a bridge/warrant explaining why the evidence supports the main claim.")
    if "Claim" in node_types and not ({"Evidence", "Result"} & node_types):
        missing.append("Add or select concrete evidence for the main claim.")
    if "Claim" in node_types and "risk" not in saliences and "Limitation" not in node_types:
        missing.append("Add or select the most important limitation so the final claim is not overextended.")
    return missing
