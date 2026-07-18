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

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "item_id": self.item_id,
            "suggested_text": self.suggested_text,
            "trace": self.trace,
            "treatment": self.treatment,
        }


@dataclass(frozen=True)
class DeliveryGuidance:
    model_id: str
    profile: str
    suggestions: tuple[DeliverySuggestion, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "profile": self.profile,
            "suggestions": [suggestion.to_dict() for suggestion in self.suggestions],
        }

    def to_markdown(self) -> str:
        lines = [f"# Delivery Guidance: {self.profile}", ""]
        if not self.suggestions:
            lines.append("- No delivery suggestions.")
            return "\n".join(lines) + "\n"
        for suggestion in self.suggestions:
            lines.append(f"- {suggestion.suggested_text}")
            lines.append(f"  - Trace: {suggestion.trace}")
        return "\n".join(lines) + "\n"


def adapt_delivery(plan: SynthesisPlan, *, profile: str | None = None) -> DeliveryGuidance:
    active_profile = profile or plan.profile
    suggestions = tuple(_suggestion(active_profile, item) for item in plan.selected_items)
    return DeliveryGuidance(plan.model_id, active_profile, suggestions)


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
