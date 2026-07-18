"""Read-only payloads for the LogicGuard project library viewer."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .importance import importance_for_edge, importance_for_node
from .loader import ModelLoadError, load_model
from .localization import DEFAULT_LANGUAGE, ZH_CN, localized_field, normalize_language
from .model import Edge, LogicModel, Node
from .source_library import ProjectBranch, SourceLibrary, SourceRecord


IMPORTANT_THRESHOLD = 0.75
RISK_NODE_TYPES = {"Assumption", "Rebuttal", "Undercutter", "Qualifier", "Limitation"}
RISK_EDGE_TYPES = {"attacks", "undercuts", "contradicts", "qualifies"}
SUPPORT_NODE_TYPES = {"Evidence", "Result", "Method"}


def build_library_view_payload(root: str | Path) -> dict[str, Any]:
    """Return one read-only snapshot for the source-library viewer."""
    library = SourceLibrary(root)
    sources = library.list_sources()
    projects = library.list_projects()
    cards = build_source_cards(root, sources=sources, projects=projects)
    return {
        "library": {
            "root": str(Path(root)),
            "version": "1",
            "read_only": True,
        },
        "summary": _summary(cards, projects),
        "projects": [_project_payload(project, cards) for project in projects],
        "sources": [source.to_dict() for source in sources],
        "cards": cards,
        "groups": _groups(cards, projects),
    }


def build_source_cards(
    root: str | Path,
    *,
    sources: Iterable[SourceRecord] | None = None,
    projects: Iterable[ProjectBranch] | None = None,
) -> list[dict[str, Any]]:
    library = SourceLibrary(root)
    source_records = list(sources if sources is not None else library.list_sources())
    project_records = list(projects if projects is not None else library.list_projects())
    project_membership = _project_membership(project_records)
    cards = [
        _source_card(library, source, project_membership.get(source.source_id, ()))
        for source in source_records
    ]
    return sorted(cards, key=lambda card: (card.get("title") or card["source_id"]).lower())


def build_source_graph_payload(root: str | Path, source_id: str, *, language: str = DEFAULT_LANGUAGE) -> dict[str, Any]:
    library = SourceLibrary(root)
    source = _source_by_id(library.list_sources(), source_id)
    model_path = library.source_model_path(source_id)
    source_payload = source.to_dict() if source else {"source_id": source_id}
    normalized_language = normalize_language(language)
    if not model_path.exists():
        return {
            "source": source_payload,
            "modeled": False,
            "status": "unmodeled",
            "language": normalized_language,
            "nodes": [],
            "edges": [],
            "views": {},
            "recommended_view": "",
            "recommended_diagram_kind": "",
            "recommendation_reason": "",
            "hierarchy": {},
            "root_claim": "",
            "markers": {},
        }
    try:
        model = load_model(model_path)
    except ModelLoadError as exc:
        return {
            "source": source_payload,
            "modeled": False,
            "status": "invalid_model",
            "language": normalized_language,
            "error": str(exc),
            "nodes": [],
            "edges": [],
            "views": {},
            "recommended_view": "",
            "recommended_diagram_kind": "",
            "recommendation_reason": "",
            "hierarchy": {},
            "root_claim": "",
            "markers": {},
        }
    nodes = [_graph_node(model, node_id, node, language=normalized_language) for node_id, node in sorted(model.nodes.items())]
    edges = [_graph_edge(model, edge, language=normalized_language) for edge in model.edges]
    views = _graph_views(nodes, edges, model.root_claim or "", language=normalized_language)
    recommended_view = _preferred_graph_view(nodes, edges, views)
    recommended_diagram_kind = str(views.get(recommended_view, {}).get("diagram_kind") or "")
    recommendation_reason = _view_recommendation_reason(recommended_view, normalized_language)
    model_i18n = model.metadata.get("i18n", {}) if isinstance(model.metadata.get("i18n", {}), dict) else {}
    model_title = localized_field(model_i18n, "title", normalized_language, model.title)
    return {
        "source": source_payload,
        "modeled": True,
        "status": "modeled",
        "language": normalized_language,
        "model": {
            "id": model.id,
            "title": model_title,
            "canonical_title": model.title,
            "root_claim": model.root_claim or "",
            "i18n": model_i18n,
        },
        "nodes": nodes,
        "edges": edges,
        "views": views,
        "recommended_view": recommended_view,
        "recommended_diagram_kind": recommended_diagram_kind,
        "recommendation_reason": recommendation_reason,
        "preferred_view": recommended_view,
        "active_view": recommended_view,
        "hierarchy": model.hierarchy,
        "root_claim": model.root_claim or "",
        "markers": {
            "important_node_ids": [node["id"] for node in nodes if node["markers"].get("important")],
            "risk_node_ids": [node["id"] for node in nodes if node["markers"].get("risk")],
            "important_edge_ids": [edge["id"] for edge in edges if edge["markers"].get("important")],
            "risk_edge_ids": [edge["id"] for edge in edges if edge["markers"].get("risk")],
        },
    }


def _source_card(library: SourceLibrary, source: SourceRecord, project_ids: tuple[str, ...]) -> dict[str, Any]:
    model = _load_source_model_if_present(library, source.source_id)
    source_file = library.root / source.source_path if source.source_path else None
    model_path = library.source_model_path(source.source_id)
    counts = _model_counts(model)
    source_type = _source_type(source)
    modeled = model is not None and counts["logic_node_count"] > 0
    risk_count = counts["risk_node_count"] + counts["risk_edge_count"]
    return {
        "source_id": source.source_id,
        "id": source.source_id,
        "title": source.title or source.source_id,
        "model_title": model.title if model else "",
        "i18n": dict(model.metadata.get("i18n", {})) if model and isinstance(model.metadata.get("i18n", {}), dict) else {},
        "authors": list(source.authors),
        "year": source.year,
        "source_date": source.source_date or source.year,
        "coverage_period": source.coverage_period,
        "doi": source.doi,
        "url": source.url,
        "source_type": source_type,
        "type": source_type,
        "project_ids": list(project_ids),
        "project_count": len(project_ids),
        "project_label": ", ".join(project_ids) if project_ids else "Uncategorized",
        "project_summary": _project_summary(project_ids),
        "added_at": _mtime_iso(source_file),
        "updated_at": _mtime_iso(model_path if model_path.exists() else source_file),
        "temporal_context": {
            "added_at": _mtime_iso(source_file),
            "source_date": source.source_date or source.year,
            "coverage_period": source.coverage_period,
        },
        "modeling_status": "modeled" if modeled else "unmodeled",
        "status": "risk" if risk_count else ("modeled" if modeled else "unmodeled"),
        "node_count": counts["node_count"],
        "logic_node_count": counts["logic_node_count"],
        "edge_count": counts["edge_count"],
        "important_node_count": counts["important_node_count"],
        "risk_node_count": counts["risk_node_count"],
        "risk_edge_count": counts["risk_edge_count"],
        "source_path": source.source_path,
        "original_path": source.original_path,
        "path": source.source_path or source.original_path,
        "read_only": True,
    }


def _model_counts(model: LogicModel | None) -> dict[str, int]:
    if model is None:
        return {
            "node_count": 0,
            "logic_node_count": 0,
            "edge_count": 0,
            "important_node_count": 0,
            "risk_node_count": 0,
            "risk_edge_count": 0,
        }
    important_nodes = 0
    risk_nodes = 0
    for node_id, node in model.nodes.items():
        record = importance_for_node(model, node_id)
        if record.importance >= IMPORTANT_THRESHOLD:
            important_nodes += 1
        if _node_is_risk(node, record.salience):
            risk_nodes += 1
    risk_edges = 0
    for edge in model.edges:
        if edge.type in RISK_EDGE_TYPES:
            risk_edges += 1
    return {
        "node_count": len(model.nodes),
        "logic_node_count": sum(1 for node in model.nodes.values() if node.type not in {"Document", "Section", "ArgumentBlock"}),
        "edge_count": len(model.edges),
        "important_node_count": important_nodes,
        "risk_node_count": risk_nodes,
        "risk_edge_count": risk_edges,
    }


def _graph_node(model: LogicModel, node_id: str, node: Node, *, language: str = DEFAULT_LANGUAGE) -> dict[str, Any]:
    record = importance_for_node(model, node_id)
    i18n = node.metadata.get("i18n", {}) if isinstance(node.metadata.get("i18n", {}), dict) else {}
    text = localized_field(i18n, "text", language, node.text)
    scope = localized_field(i18n, "scope", language, node.scope or "")
    markers = {
        "root": node_id == model.root_claim,
        "important": record.importance >= IMPORTANT_THRESHOLD,
        "risk": _node_is_risk(node, record.salience),
        "evidence": node.type in SUPPORT_NODE_TYPES,
        "claim": node.type == "Claim",
    }
    return {
        "id": node_id,
        "type": node.type,
        "text": text,
        "canonical_text": node.text,
        "scope": scope,
        "canonical_scope": node.scope or "",
        "parent": node.parent or "",
        "children": list(node.children),
        "importance": record.importance,
        "salience": record.salience,
        "importance_reason": record.reason,
        "explicit_importance": record.explicit,
        "markers": markers,
        "metadata": dict(node.metadata),
    }


def _graph_edge(model: LogicModel, edge: Edge, *, language: str = DEFAULT_LANGUAGE) -> dict[str, Any]:
    record = importance_for_edge(model, edge)
    edge_id = f"{edge.source}->{edge.target}:{edge.type}"
    i18n = edge.metadata.get("i18n", {}) if isinstance(edge.metadata.get("i18n", {}), dict) else {}
    explanation = localized_field(i18n, "explanation", language, edge.explanation)
    return {
        "id": edge_id,
        "source": edge.source,
        "target": edge.target,
        "type": edge.type,
        "weight": edge.weight,
        "explanation": explanation,
        "canonical_explanation": edge.explanation,
        "importance": record.importance,
        "salience": record.salience,
        "importance_reason": record.reason,
        "markers": {
            "important": record.importance >= IMPORTANT_THRESHOLD,
            "risk": edge.type in RISK_EDGE_TYPES,
        },
        "metadata": dict(edge.metadata),
    }


def _graph_views(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], root_claim: str, *, language: str) -> dict[str, Any]:
    argument_nodes = [
        str(node.get("id") or "")
        for node in nodes
        if str(node.get("type") or "") not in {"Document", "Section", "ArgumentBlock"}
    ]
    argument_edges = [
        edge
        for edge in edges
        if str(edge.get("source") or "") in argument_nodes and str(edge.get("target") or "") in argument_nodes
    ]
    flow_nodes = _research_flow_node_ids(nodes, root_claim)
    preferred = _preferred_graph_view(nodes, argument_edges, {})
    process_model = _has_research_process_shape(nodes)
    argument_distinct = _has_distinct_argument_shape(argument_edges, argument_nodes)
    return {
        "argument_map": {
            "id": "argument_map",
            "label": _view_label("argument_map", language),
            "description": _view_description("argument_map", language),
            "diagram_kind": "argument_support",
            "visible": preferred == "argument_map" or (argument_distinct and not process_model),
            "nodes": argument_nodes,
            "edges": argument_edges,
        },
        "research_flow": {
            "id": "research_flow",
            "label": _view_label("research_flow", language),
            "description": _view_description("research_flow", language),
            "diagram_kind": "process_timeline",
            "visible": preferred == "research_flow" or process_model,
            "nodes": flow_nodes,
            "edges": _research_flow_edges(flow_nodes, language=language),
        },
    }


def _preferred_graph_view(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], views: dict[str, Any]) -> str:
    if _has_research_process_shape(nodes):
        return "research_flow"
    argument_nodes = [str(node.get("id") or "") for node in nodes if str(node.get("type") or "") not in {"Document", "Section", "ArgumentBlock"}]
    if _has_distinct_argument_shape(edges, argument_nodes):
        return "argument_map"
    if isinstance(views.get("research_flow"), dict) and views["research_flow"].get("nodes"):
        return "research_flow"
    return "argument_map"


def _has_research_process_shape(nodes: list[dict[str, Any]]) -> bool:
    node_types = {str(node.get("type") or "") for node in nodes}
    return bool({"Method", "Evidence", "Result"} & node_types) and bool({"Claim", "Limitation", "Warrant"} & node_types)


def _has_distinct_argument_shape(edges: list[dict[str, Any]], node_ids: list[str]) -> bool:
    node_set = set(node_ids)
    logical_edges = [
        edge
        for edge in edges
        if str(edge.get("source") or "") in node_set
        and str(edge.get("target") or "") in node_set
        and str(edge.get("type") or "") not in {"research_flow", "contextualizes"}
    ]
    edge_types = {str(edge.get("type") or "") for edge in logical_edges}
    return len(logical_edges) >= 2 and len(edge_types) >= 1


def _research_flow_node_ids(nodes: list[dict[str, Any]], root_claim: str) -> list[str]:
    priority = {
        "Context": 0,
        "Definition": 1,
        "Method": 2,
        "Evidence": 3,
        "Result": 4,
        "Warrant": 5,
        "Claim": 6,
        "Limitation": 7,
        "Rebuttal": 8,
    }
    candidates = [
        node
        for node in nodes
        if str(node.get("type") or "") not in {"Document", "Section", "ArgumentBlock"}
    ]
    candidates.sort(key=lambda node: (priority.get(str(node.get("type") or ""), 50), 0 if node.get("id") == root_claim else 1, str(node.get("id") or "")))
    return [str(node.get("id") or "") for node in candidates]


def _research_flow_edges(node_ids: list[str], *, language: str) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for index, (source, target) in enumerate(zip(node_ids, node_ids[1:]), start=1):
        edge_id = f"flow:{source}->{target}"
        edges.append(
            {
                "id": edge_id,
                "source": source,
                "target": target,
                "type": "research_flow",
                "weight": 1.0,
                "explanation": _view_label("research_flow", language),
                "importance": 0.5,
                "salience": "view",
                "importance_reason": "Derived display-only research-flow edge.",
                "markers": {"important": False, "risk": False, "derived": True},
                "metadata": {"derived_view": "research_flow", "order": index},
            }
        )
    return edges


def _view_label(view_id: str, language: str) -> str:
    if normalize_language(language) == ZH_CN:
        return {"argument_map": "论证图", "research_flow": "研究流程"}.get(view_id, view_id)
    return {"argument_map": "Argument map", "research_flow": "Research flow"}.get(view_id, view_id)


def _view_description(view_id: str, language: str) -> str:
    if normalize_language(language) == ZH_CN:
        return {
            "argument_map": "显示支持、限定、反驳等论证关系。",
            "research_flow": "按论文阅读顺序显示方法、证据/结果、结论和边界。",
        }.get(view_id, "")
    return {
        "argument_map": "Shows support, qualification, and rebuttal relations.",
        "research_flow": "Shows a reading order from methods through evidence/results to conclusion and boundaries.",
    }.get(view_id, "")


def _view_recommendation_reason(view_id: str, language: str) -> str:
    if normalize_language(language) == ZH_CN:
        return {
            "argument_map": "推荐此图，因为当前资料的核心是说明结论如何被证据、warrant、限定和反驳关系支撑。",
            "research_flow": "推荐此图，因为当前资料包含方法、证据/结果、结论和边界，按研究阅读顺序更清楚。",
        }.get(view_id, "")
    return {
        "argument_map": "Recommended because this source is clearest as claim support: evidence, warrants, qualifications, and rebuttal relations.",
        "research_flow": "Recommended because this source contains method, evidence/result, conclusion, and boundary material that reads clearest as a research sequence.",
    }.get(view_id, "")


def _load_source_model_if_present(library: SourceLibrary, source_id: str) -> LogicModel | None:
    path = library.source_model_path(source_id)
    if not path.exists():
        return None
    try:
        return load_model(path)
    except ModelLoadError:
        return None


def _project_membership(projects: Iterable[ProjectBranch]) -> dict[str, tuple[str, ...]]:
    membership: dict[str, list[str]] = {}
    for project in projects:
        for source_id in project.selected_sources:
            membership.setdefault(source_id, []).append(project.project_id)
    return {source_id: tuple(sorted(project_ids)) for source_id, project_ids in membership.items()}


def _project_payload(project: ProjectBranch, cards: list[dict[str, Any]]) -> dict[str, Any]:
    source_ids = set(project.selected_sources)
    project_cards = [card for card in cards if card["source_id"] in source_ids]
    return {
        "project_id": project.project_id,
        "id": project.project_id,
        "topic": project.topic,
        "selected_sources": list(project.selected_sources),
        "source_count": len(project_cards),
        "modeled_source_count": sum(1 for card in project_cards if card["modeling_status"] == "modeled"),
        "risk_source_count": sum(1 for card in project_cards if card["risk_node_count"] or card["risk_edge_count"]),
        "important_node_count": sum(int(card["important_node_count"]) for card in project_cards),
    }


def _project_summary(project_ids: tuple[str, ...]) -> str:
    if not project_ids:
        return "Uncategorized"
    if len(project_ids) <= 2:
        return ", ".join(project_ids)
    return f"{project_ids[0]}, {project_ids[1]} +{len(project_ids) - 2}"


def _groups(cards: list[dict[str, Any]], projects: list[ProjectBranch]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = [
        {"id": "all", "label": "All Sources", "kind": "all", "source_count": len(cards)},
        {
            "id": "recent",
            "label": "Recently Added",
            "kind": "recent",
            "source_count": len(cards),
        },
        {
            "id": "uncategorized",
            "label": "Uncategorized",
            "kind": "project",
            "source_count": sum(1 for card in cards if not card["project_ids"]),
        },
    ]
    groups.extend(
        {
            "id": project.project_id,
            "label": project.project_id,
            "kind": "project",
            "source_count": sum(1 for card in cards if project.project_id in card["project_ids"]),
        }
        for project in projects
    )
    return groups


def _summary(cards: list[dict[str, Any]], projects: list[ProjectBranch]) -> dict[str, int]:
    return {
        "source_count": len(cards),
        "project_count": len(projects),
        "modeled_source_count": sum(1 for card in cards if card["modeling_status"] == "modeled"),
        "unmodeled_source_count": sum(1 for card in cards if card["modeling_status"] != "modeled"),
        "important_node_count": sum(int(card["important_node_count"]) for card in cards),
        "risk_node_count": sum(int(card["risk_node_count"]) for card in cards),
        "risk_edge_count": sum(int(card["risk_edge_count"]) for card in cards),
    }


def _source_by_id(sources: Iterable[SourceRecord], source_id: str) -> SourceRecord | None:
    for source in sources:
        if source.source_id == source_id:
            return source
    return None


def _source_type(source: SourceRecord) -> str:
    path_text = source.source_path or source.original_path or source.url or source.title
    suffix = Path(path_text).suffix.lower()
    if suffix in {".ppt", ".pptx"}:
        return "presentation"
    if suffix in {".pdf"}:
        return "paper"
    if suffix in {".doc", ".docx", ".md", ".rst"}:
        return "report"
    if suffix in {".html", ".htm"} or source.url:
        return "web"
    if suffix in {".txt", ".yaml", ".yml", ".json"}:
        return "note"
    return "source"


def _node_is_risk(node: Node, salience: str) -> bool:
    return node.type in RISK_NODE_TYPES or salience == "risk"


def _mtime_iso(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    value = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")
