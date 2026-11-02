"""Text of a card's detail header: type, modelling status, dates and projects.

These helpers read only the card payload. They live apart from desktop_app so that their
tests run on a Python without tkinter or Pillow.
"""
from __future__ import annotations

from typing import Any

from researchguard.logic_viewer.i18n import DEFAULT_LANGUAGE, ZH_CN, normalize_language


def _card_type_label(card: dict[str, Any], language: str = DEFAULT_LANGUAGE) -> str:
    value = str(card.get("type") or "model").replace("_", " ").strip()
    if normalize_language(language) == ZH_CN:
        return {
            "presentation": "PPT",
            "paper": "论文",
            "report": "报告",
            "note": "笔记",
            "web": "网页",
            "source": "资料",
        }.get(value.lower(), value)
    return value.upper() if value else "MODEL"


def _modeling_status_label(card: dict[str, Any], language: str = DEFAULT_LANGUAGE) -> str:
    library_card = card.get("library_card") if isinstance(card.get("library_card"), dict) else {}
    value = str(library_card.get("modeling_status") or card.get("modeling_status") or card.get("status") or "").strip().lower()
    if value == "risk":
        value = "modeled"
    if normalize_language(language) == ZH_CN:
        return {"modeled": "已建模", "unmodeled": "未建模", "invalid_model": "模型有误"}.get(value, value or "未标注")
    return {"modeled": "Modeled", "unmodeled": "Unmodeled", "invalid_model": "Invalid model"}.get(value, value.replace("_", " ").title() if value else "Unmarked")


def _temporal_values(card: dict[str, Any]) -> tuple[str, str, str]:
    library_card = card.get("library_card") if isinstance(card.get("library_card"), dict) else {}
    temporal = library_card.get("temporal_context") if isinstance(library_card.get("temporal_context"), dict) else {}
    added = str(temporal.get("added_at") or library_card.get("added_at") or card.get("added_at") or "")
    source_date = str(temporal.get("source_date") or library_card.get("source_date") or library_card.get("year") or card.get("source_date") or "")
    coverage = str(temporal.get("coverage_period") or library_card.get("coverage_period") or card.get("coverage_period") or "")
    return added, source_date, coverage


def _detail_header_meta_line(card: dict[str, Any], language: str = DEFAULT_LANGUAGE) -> str:
    """Return only user-facing source summary metadata for the detail hero."""
    normalized = normalize_language(language)
    parts: list[str] = []
    card_type = _card_type_label(card, language)
    if card_type:
        parts.append(card_type)

    status = _modeling_status_label(card, language)
    if status:
        parts.append(status)

    added, _source_date, _coverage = _temporal_values(card)
    if added:
        parts.append(("加入 " if normalized == ZH_CN else "added ") + added[:10])

    project_label = _detail_header_project_label(card, language)
    if project_label:
        parts.append(project_label)
    return " · ".join(parts)


def _detail_header_project_label(card: dict[str, Any], language: str = DEFAULT_LANGUAGE) -> str:
    library_card = card.get("library_card") if isinstance(card.get("library_card"), dict) else {}
    project_ids = [str(item) for item in card.get("project_ids", []) or [] if str(item)]
    if not project_ids:
        project_ids = [str(item) for item in library_card.get("project_ids", []) or [] if str(item)]
    normalized = normalize_language(language)
    if not project_ids:
        return "未归入项目" if normalized == ZH_CN else "No project"
    if len(project_ids) == 1:
        label = project_ids[0]
        return f"项目：{label}" if normalized == ZH_CN else f"Project: {label}"
    return f"{len(project_ids)} 个项目" if normalized == ZH_CN else f"{len(project_ids)} projects"
