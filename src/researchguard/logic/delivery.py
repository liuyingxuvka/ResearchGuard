"""Delivery adaptation for synthesized LogicGuard plans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .synthesis import SynthesisItem, SynthesisPlan


@dataclass(frozen=True)
class DeliverySuggestion:
    profile: str
    item_id: str
    suggested_text: str
    trace: str
    treatment: str = ""
    placement: str = "body"
    unit_id: str = ""
    claim_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "item_id": self.item_id,
            "suggested_text": self.suggested_text,
            "trace": self.trace,
            "treatment": self.treatment,
            "placement": self.placement,
            "unit_id": self.unit_id,
            "claim_ids": list(self.claim_ids),
        }


@dataclass(frozen=True)
class DeliveryGuidance:
    model_id: str
    profile: str
    suggestions: tuple[DeliverySuggestion, ...]
    appendix_suggestions: tuple[DeliverySuggestion, ...] = ()
    note_suggestions: tuple[DeliverySuggestion, ...] = ()
    status: str = "research_handoff_ready"
    open_gaps: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "researchguard.logic.delivery-guidance.v1",
            "model_id": self.model_id,
            "profile": self.profile,
            "suggestions": [suggestion.to_dict() for suggestion in self.suggestions],
            "note_suggestions": [suggestion.to_dict() for suggestion in self.note_suggestions],
            "appendix_suggestions": [suggestion.to_dict() for suggestion in self.appendix_suggestions],
            "status": self.status,
            "open_gaps": list(self.open_gaps),
        }

    def to_markdown(self) -> str:
        lines = [f"# Delivery Guidance: {self.profile}", "", f"- Status: {self.status}", ""]
        if self.open_gaps:
            lines.append("## Open Gaps")
            lines.extend(f"- {gap}" for gap in self.open_gaps)
            lines.append("")
        for heading, suggestions in (
            ("Body", self.suggestions),
            ("Notes", self.note_suggestions),
            ("Appendix", self.appendix_suggestions),
        ):
            lines.extend([f"## {heading}", ""])
            if not suggestions:
                lines.append("- None.")
                lines.append("")
                continue
            for suggestion in suggestions:
                lines.append(f"- {suggestion.suggested_text}")
                lines.append(f"  - Trace: {suggestion.trace}")
            lines.append("")
        return "\n".join(lines) + "\n"


def adapt_delivery(plan: SynthesisPlan, *, profile: str | None = None) -> DeliveryGuidance:
    active_profile = profile or plan.profile
    contract_gaps = _delivery_contract_gaps(plan)
    if plan.status != "research_handoff_ready":
        # A blocked synthesis is diagnostic input for repair orchestration. It
        # must never be silently downgraded to usable writer material.
        gaps = tuple(dict.fromkeys((*plan.open_gaps, *contract_gaps)))
        return DeliveryGuidance(
            plan.model_id,
            active_profile,
            (),
            (),
            (),
            plan.status,
            gaps,
        )
    if contract_gaps:
        return DeliveryGuidance(
            plan.model_id,
            active_profile,
            (),
            (),
            (),
            "blocked_delivery_contract",
            tuple(dict.fromkeys(contract_gaps)),
        )

    item_by_id = {item.node_id: item for item in (*plan.selected_items, *plan.omitted_items)}
    by_id = {unit.unit_id: unit for unit in plan.units}
    ordered_body = tuple(by_id[unit_id] for unit_id in plan.body_unit_order)
    ordered_non_body = tuple(
        unit for unit in plan.units if unit.placement in {"note", "appendix"}
    )
    suggestions = tuple(
        _unit_suggestion(active_profile, unit, item_by_id, plan, placement="body")
        for unit in ordered_body
    )
    notes = tuple(
        _unit_suggestion(active_profile, unit, item_by_id, plan, placement="note")
        for unit in ordered_non_body
        if unit.placement == "note"
    )
    appendix = tuple(
        _unit_suggestion(active_profile, unit, item_by_id, plan, placement="appendix")
        for unit in ordered_non_body
        if unit.placement == "appendix"
    )
    return DeliveryGuidance(
        plan.model_id,
        active_profile,
        suggestions,
        appendix,
        notes,
        plan.status,
        tuple(plan.open_gaps),
    )


def _delivery_contract_gaps(plan: SynthesisPlan) -> list[str]:
    """Validate the delivery-facing unit index before producing any text."""

    gaps: list[str] = []
    units = list(plan.units)
    by_id: dict[str, Any] = {}
    for index, unit in enumerate(units):
        unit_id = str(getattr(unit, "unit_id", "") or "")
        if not unit_id:
            gaps.append(f"delivery:missing_unit_id:{index}")
            continue
        if unit_id in by_id:
            gaps.append(f"delivery:duplicate_unit_id:{unit_id}")
            continue
        by_id[unit_id] = unit
    raw_order = plan.body_unit_order
    order = tuple(str(value) for value in raw_order)
    seen: set[str] = set()
    for unit_id in order:
        if unit_id in seen:
            gaps.append(f"delivery:duplicate_body_unit_order:{unit_id}")
        seen.add(unit_id)
        if unit_id not in by_id:
            gaps.append(f"delivery:unknown_body_unit:{unit_id}")
    body_ids = {unit_id for unit_id, unit in by_id.items() if unit.placement == "body"}
    if set(order) != body_ids:
        gaps.append(
            "delivery:body_unit_order_mismatch:"
            f"expected={','.join(sorted(body_ids))}:actual={','.join(order)}"
        )
    for unit in units:
        if unit.placement not in {"body", "note", "appendix", "omit"}:
            gaps.append(f"delivery:invalid_placement:{unit.unit_id}:{unit.placement}")
    return gaps


def _unit_suggestion(
    profile: str,
    unit: Any,
    item_by_id: dict[str, SynthesisItem],
    plan: SynthesisPlan,
    *,
    placement: str,
) -> DeliverySuggestion:
    """Render every claim in one unit while keeping diagnostics in ``trace``."""

    ids: list[str] = []
    ids.extend(str(value) for value in unit.claim_ids)
    ids.extend(str(value) for value in unit.argument_closure if str(value) not in ids)
    # Source branches are candidates rather than LogicModel nodes.  Their
    # unit-specific placement is recorded by synthesis and therefore must be
    # joined here without using the aggregate placement as a substitute.
    for disposition in plan.candidate_dispositions:
        if disposition.unit_placements.get(unit.unit_id) == placement:
            ids.append(disposition.candidate_id)
    items: list[SynthesisItem] = []
    seen: set[str] = set()
    for item_id in ids:
        item = item_by_id.get(item_id)
        if item is None or item.node_id in seen:
            continue
        seen.add(item.node_id)
        items.append(item)
    claim_id_set = {str(value) for value in unit.claim_ids}
    claims = [item for item in items if item.node_id in claim_id_set]
    support = [item for item in items if item.node_id not in claim_id_set]
    if not claims:
        text = str(unit.unit_job)
        item_ids = ()
        treatment = "normal"
    else:
        rendered = [
            _with_material_temporal_context(_profile_text(profile, item), item, profile)
            for item in claims
        ]
        if support:
            rendered.extend(
                _with_material_temporal_context(_profile_text(profile, item), item, profile)
                for item in support
            )
        text = _join_fragments(rendered)
        item_ids = tuple(item.node_id for item in items)
        treatment = "deep" if unit.editorial_prominence == "lead" else "normal"
    trace = (
        f"unit={unit.unit_id}; placement={placement}; claim_ids={','.join(str(value) for value in unit.claim_ids)}; "
        f"item_ids={','.join(item_ids)}; prominence={unit.editorial_prominence}"
    )
    return DeliverySuggestion(
        profile,
        unit.unit_id,
        text,
        trace,
        treatment,
        placement,
        unit.unit_id,
        tuple(str(value) for value in unit.claim_ids),
    )


def _join_fragments(fragments: list[str]) -> str:
    return " ".join(fragment.strip() for fragment in fragments if fragment and fragment.strip())


def _profile_text(profile: str, item: SynthesisItem) -> str:
    if profile == "presentation":
        return _presentation_text(item)
    if profile == "paper":
        return _paper_text(item)
    if profile == "report":
        return _report_text(item)
    return item.text


def _suggestion(profile: str, item: SynthesisItem) -> DeliverySuggestion:
    if profile == "presentation":
        text = _presentation_text(item)
    elif profile == "paper":
        text = _paper_text(item)
    elif profile == "report":
        text = _report_text(item)
    else:
        text = item.text
    text = _with_material_temporal_context(text, item, profile)
    treatment = item.treatment or "normal"
    return DeliverySuggestion(
        profile,
        item.node_id,
        text,
        f"{item.node_id} ({item.node_type}, {item.salience}, treatment={treatment})",
        treatment,
    )


def _presentation_text(item: SynthesisItem) -> str:
    if item.treatment == "appendix":
        return f"Appendix: {item.text}"
    if item.treatment == "brief":
        return f"Context: {item.text}"
    if item.salience == "risk" or item.node_type in {"Limitation", "Qualifier"}:
        return f"Boundary: {item.text}"
    if item.salience == "bridge" or item.node_type == "Warrant":
        return f"This supports the next step because {item.text}"
    if item.treatment == "deep":
        return f"Main point: {item.text}"
    return item.text


def _paper_text(item: SynthesisItem) -> str:
    if item.treatment == "appendix":
        return f"Appendix material: {item.text}"
    if item.treatment == "brief":
        return f"As context, {item.text}"
    if item.salience == "risk" or item.node_type in {"Limitation", "Qualifier"}:
        return f"This claim should be interpreted within the following boundary: {item.text}"
    if item.salience == "bridge" or item.node_type == "Warrant":
        return f"The inference depends on the following warrant: {item.text}"
    if item.treatment == "deep":
        return f"Develop this claim with explicit support and scope: {item.text}"
    return item.text


def _report_text(item: SynthesisItem) -> str:
    if item.treatment == "appendix":
        return f"Appendix note: {item.text}"
    if item.treatment == "brief":
        return f"Brief context: {item.text}"
    if item.salience == "risk" or item.node_type in {"Limitation", "Qualifier"}:
        return f"Risk boundary: {item.text}"
    if item.node_type in {"Evidence", "Result"}:
        return f"Evidence: {item.text}"
    if item.treatment == "deep":
        return f"Priority finding: {item.text}"
    return item.text


def _with_material_temporal_context(text: str, item: SynthesisItem, profile: str) -> str:
    if not _temporal_context_is_material(item):
        return text
    caveat = item.temporal_caveat or _temporal_context_text(item)
    if not caveat:
        return text
    if profile == "presentation":
        return f"{text} Time boundary: {caveat}"
    if profile == "paper":
        return f"{text} This should be interpreted with the following temporal boundary: {caveat}"
    if profile == "report":
        return f"{text} Time context: {caveat}"
    return f"{text} ({caveat})"


def _temporal_context_is_material(item: SynthesisItem) -> bool:
    if not (item.temporal_role or item.temporal_caveat):
        return False
    if item.treatment in {"deep", "normal"}:
        return True
    if item.salience in {"core", "risk", "bridge"}:
        return True
    return item.node_type in {"SourceBranch", "Limitation", "Qualifier", "Rebuttal", "Undercutter"}


def _temporal_context_text(item: SynthesisItem) -> str:
    parts: list[str] = []
    if item.source_date:
        parts.append(f"source date {item.source_date}")
    if item.coverage_period:
        parts.append(f"coverage {item.coverage_period}")
    if item.temporal_role == "unknown_time":
        parts.append("source time unmarked")
    return "; ".join(parts)
