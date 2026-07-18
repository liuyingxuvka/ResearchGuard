"""Data adapter for the copied LogicGuard source-library viewer shell."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from researchguard.logic.library_viewer import build_library_view_payload, build_source_graph_payload
from researchguard.logic.localization import localized_field

from .common import normalize_text
from .i18n import DEFAULT_LANGUAGE, ZH_CN, localized_route_label, normalize_language


def build_route_view_payload(
    repo_root: Path,
    route: str = "",
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, Any]:
    payload = build_library_view_payload(repo_root)
    normalized_language = normalize_language(language)
    route = str(route or "").strip("/")
    cards = [_summarize_card(card, normalized_language) for card in payload["cards"]]
    deck = _filter_by_route(cards, route)
    return {
        "route": [route] if route else [],
        "route_label": localized_route_label(route, normalized_language, empty_label=_text(normalized_language, "all_sources")),
        "taxonomy": {"children": _navigation(payload, normalized_language), "coverage": {}},
        "navigation_children": _navigation(payload, normalized_language),
        "cards": {"primary": deck, "cross": []},
        "deck": deck,
    }


def build_card_detail_payload(
    repo_root: Path,
    entry_id: str,
    language: str = DEFAULT_LANGUAGE,
    source_info: dict[str, Any] | None = None,
    local_policy_allows_skill_auto_install: bool = False,
) -> dict[str, Any] | None:
    payload = build_library_view_payload(repo_root)
    normalized_language = normalize_language(language)
    for card in payload["cards"]:
        if card["source_id"] != entry_id:
            continue
        summary = _summarize_card(card, normalized_language)
        graph = build_source_graph_payload(repo_root, entry_id, language=normalized_language)
        return {
            **summary,
            "graph": graph,
            "if": {"notes": _text(normalized_language, "source_metadata")},
            "action": {"description": _metadata_sentence(card, normalized_language)},
            "predict": {"expected_result": _graph_sentence(graph, normalized_language)},
            "use": {"guidance": _text(normalized_language, "read_only_guidance")},
            "source": card,
            "updated_at": card.get("updated_at", ""),
            "raw": {"card": card, "graph": graph},
            "skill_dependencies": [],
            "recent_history": [],
        }
    return None


def build_search_payload(
    repo_root: Path,
    query: str,
    route_hint: str = "",
    top_k: int = 12,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, Any]:
    payload = build_library_view_payload(repo_root)
    normalized_language = normalize_language(language)
    tokens = [token for token in normalize_text(query).lower().split() if token]
    results = []
    for card in payload["cards"]:
        haystack = " ".join(
            str(card.get(key, ""))
            for key in ("source_id", "title", "source_type", "project_label", "year", "source_date", "coverage_period", "added_at", "path")
        ).lower()
        if tokens and not all(token in haystack for token in tokens):
            continue
        results.append(_summarize_card(card, normalized_language, route_reason="search"))
    return {"query": query, "route_hint": route_hint, "results": results[:top_k]}


def build_source_view_payload(
    repo_root: Path,
    source_kind: str,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, Any]:
    payload = build_library_view_payload(repo_root)
    normalized_language = normalize_language(language)
    deck = [
        _summarize_card(card, normalized_language, route_reason="source")
        for card in payload["cards"]
        if card.get("source_type") == source_kind
    ]
    return {"source_kind": source_kind, "deck": deck}


def build_overview_payload(repo_root: Path) -> dict[str, Any]:
    payload = build_library_view_payload(repo_root)
    return {
        "entry_count": payload["summary"]["source_count"],
        "status_counts": {
            "modeled": payload["summary"]["modeled_source_count"],
            "unmodeled": payload["summary"]["unmodeled_source_count"],
        },
        "scope_counts": {},
        "type_counts": _type_counts(payload["cards"]),
        "recent_event_count": 0,
        "latest_events": [],
        "taxonomy_gap_count": 0,
        "taxonomy_gaps": [],
    }


def navigation_children(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("navigation_children"), list):
        return payload["navigation_children"]
    taxonomy = payload.get("taxonomy", {}) if isinstance(payload.get("taxonomy"), dict) else {}
    return taxonomy.get("children", []) if isinstance(taxonomy.get("children"), list) else []


def navigation_card_count(item: dict[str, Any]) -> int:
    return int(item.get("observed_subtree_count") or item.get("primary_subtree_count") or item.get("source_count") or 0)


def _summarize_card(card: dict[str, Any], language: str, *, route_reason: str = "primary") -> dict[str, Any]:
    project_route = card["project_ids"][0] if card.get("project_ids") else "uncategorized"
    title = localized_field(card.get("i18n", {}), "title", language, str(card.get("model_title") or card.get("title") or card.get("source_id")))
    risk_count = int(card.get("risk_node_count") or 0) + int(card.get("risk_edge_count") or 0)
    return {
        "id": card["source_id"],
        "title": title,
        "type": card.get("source_type") or "source",
        "scope": "library",
        "status": "risk" if risk_count else card.get("modeling_status", "unmodeled"),
        "confidence": _confidence(card),
        "domain_path": [project_route],
        "domain_label": localized_route_label(project_route, language),
        "cross_index": [project_id for project_id in card.get("project_ids", [])[1:]],
        "project_ids": list(card.get("project_ids", [])),
        "project_count": int(card.get("project_count") or 0),
        "project_label": card.get("project_label") or "",
        "project_summary": card.get("project_summary") or "",
        "related_cards": [],
        "tags": [card.get("source_type", "source"), card.get("modeling_status", "unmodeled")],
        "trigger_keywords": [],
        "skill_dependency_count": 0,
        "predicted_result": _card_preview(card, language),
        "guidance": _card_guidance(card, language),
        "path": card.get("path") or "",
        "source_info": {
            "kind": "logicguard",
            "scope": "library",
            "source_id": card["source_id"],
            "path": card.get("path") or "",
        },
        "source_label": _text(language, "logicguard_library"),
        "author_label": card.get("project_label") or "",
        "read_only": True,
        "route_reason": route_reason,
        "match_route": [project_route],
        "library_card": card,
    }


def _filter_by_route(cards: list[dict[str, Any]], route: str) -> list[dict[str, Any]]:
    if not route:
        return cards
    if route == "recent":
        return sorted(cards, key=lambda card: str(card.get("library_card", {}).get("added_at") or ""), reverse=True)
    if route == "uncategorized":
        return [card for card in cards if not card.get("library_card", {}).get("project_ids")]
    return [card for card in cards if route in card.get("library_card", {}).get("project_ids", [])]


def _navigation(payload: dict[str, Any], language: str) -> list[dict[str, Any]]:
    children = [
        {
            "segment": "uncategorized",
            "route": ["uncategorized"],
            "label": _text(language, "uncategorized"),
            "primary_subtree_count": sum(1 for card in payload["cards"] if not card.get("project_ids")),
            "observed_subtree_count": sum(1 for card in payload["cards"] if not card.get("project_ids")),
            "declared": True,
        },
    ]
    for project in payload["projects"]:
        children.append(
            {
                "segment": project["project_id"],
                "route": [project["project_id"]],
                "label": project["project_id"],
                "primary_subtree_count": project["source_count"],
                "observed_subtree_count": project["source_count"],
                "declared": True,
            }
        )
    return children


def _type_counts(cards: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for card in cards:
        source_type = str(card.get("source_type") or "source")
        counts[source_type] = counts.get(source_type, 0) + 1
    return counts


def _confidence(card: dict[str, Any]) -> float | None:
    if card.get("modeling_status") != "modeled":
        return None
    logic_nodes = max(1, int(card.get("logic_node_count") or 0))
    important = int(card.get("important_node_count") or 0)
    return round(min(0.99, max(0.35, important / logic_nodes + 0.35)), 2)


def _card_preview(card: dict[str, Any], language: str) -> str:
    nodes = int(card.get("logic_node_count") or 0)
    if card.get("modeling_status") != "modeled":
        return "等待建模" if language == ZH_CN else "Waiting for modeling"
    if language == ZH_CN:
        return f"已保存浅模型 · {nodes} 个模型节点"
    return f"Shallow model saved · {nodes} model nodes"


def _card_guidance(card: dict[str, Any], language: str) -> str:
    project_text = card.get("project_summary") or card.get("project_label")
    if language == ZH_CN:
        status = "已建模" if card.get("modeling_status") == "modeled" else "未建模"
        return f"{project_text or '未归入项目'} · {status}"
    status = "Modeled" if card.get("modeling_status") == "modeled" else "Unmodeled"
    return f"{project_text or 'No project'} · {status}"


def _metadata_sentence(card: dict[str, Any], language: str) -> str:
    temporal = _temporal_sentence(card, language)
    if language == ZH_CN:
        return f"资料类型：{card.get('source_type')}；项目：{card.get('project_label')}；{temporal}；路径：{card.get('path') or '-'}。"
    return f"Type: {card.get('source_type')}; projects: {card.get('project_label')}; {temporal}; path: {card.get('path') or '-'}."


def _temporal_sentence(card: dict[str, Any], language: str) -> str:
    source_date = card.get("source_date") or card.get("year") or ""
    coverage = card.get("coverage_period") or ""
    added = card.get("added_at") or ""
    if language == ZH_CN:
        return f"加入资料库：{added or '未标注'}；资料时间：{source_date or '未标注'}；覆盖时期：{coverage or '未标注'}"
    return f"added: {added or 'unmarked'}; source date: {source_date or 'unmarked'}; coverage: {coverage or 'unmarked'}"


def _graph_sentence(graph: dict[str, Any], language: str) -> str:
    if not graph.get("modeled"):
        return _text(language, "unmodeled_graph")
    if language == ZH_CN:
        return f"逻辑图包含 {len(graph.get('nodes', []))} 个节点和 {len(graph.get('edges', []))} 条关系。"
    return f"The logic graph contains {len(graph.get('nodes', []))} nodes and {len(graph.get('edges', []))} relations."


def _text(language: str, key: str) -> str:
    labels = {
        DEFAULT_LANGUAGE: {
            "all_sources": "All Sources",
            "recent": "Recently Added",
            "uncategorized": "Uncategorized",
            "logicguard_library": "LogicGuard Library",
            "source_metadata": "Source metadata",
            "temporal_clues": "Temporal clues",
            "read_only_guidance": "This viewer is read-only. Use LogicGuard CLI commands to edit or deepen the model.",
            "unmodeled_graph": "This source does not have a source model yet.",
        },
        ZH_CN: {
            "all_sources": "全部资料",
            "recent": "最近加入",
            "uncategorized": "未归入项目",
            "logicguard_library": "LogicGuard 资料库",
            "source_metadata": "资料信息",
            "temporal_clues": "时间线索",
            "read_only_guidance": "这个查看器只读。需要编辑或深化模型时，请使用 LogicGuard 命令。",
            "unmodeled_graph": "这份资料还没有资料模型。",
        },
    }
    return labels[normalize_language(language)].get(key, key)
