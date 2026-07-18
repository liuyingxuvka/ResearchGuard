from __future__ import annotations

import ctypes
import math
import sys
import textwrap
from pathlib import Path
from typing import Any


def _enable_windows_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError, ValueError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError, ValueError):
            pass


_enable_windows_dpi_awareness()

import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

from PIL import Image, ImageDraw, ImageFilter, ImageTk

from researchguard.logic.source_library_io import export_library_package, import_library_package

from researchguard.logic_viewer.common import normalize_text
from researchguard.logic_viewer.i18n import (
    DEFAULT_LANGUAGE,
    ZH_CN,
    localized_route_label,
    localized_route_segment,
    localized_route_title,
    normalize_language,
)
from researchguard.logic_viewer.settings import (
    PERSONAL_MODE,
    load_desktop_settings,
    save_desktop_settings,
)
from researchguard.logic_viewer.software_update import (
    load_update_state,
    set_update_request,
    update_badge_clickable,
    update_badge_label,
)
from researchguard.logic_viewer.store import resolve_repo_root
from researchguard.logic_viewer.ui_data import (
    build_card_detail_payload,
    build_route_view_payload,
    build_search_payload,
    build_source_view_payload,
    navigation_card_count,
    navigation_children,
)


BG = "#ffffff"
SIDEBAR = "#fbfbfc"
SIDEBAR_ACTIVE = "#f0eeee"
TEXT = "#171717"
MUTED = "#7c7c82"
LINE = "#e6e6eb"
LINE_SOFT = "#f2f2f5"
ACCENT = "#0aa6bb"
ACCENT_DARK = "#056b80"
ACCENT_SOFT = "#ecfeff"
ACCENT_LINE = "#a5f3fc"
UI_FONT = "Segoe UI"
CJK_UI_FONT = "Microsoft YaHei UI"
ICON_FONT = "Segoe Fluent Icons"
EXPORT_PACKAGE_ICON = "\ue8da"
IMPORT_PACKAGE_ICON = "\ue8de"
DEFAULT_WINDOW_SIZE = (1440, 900)
MIN_WINDOW_SIZE = (1080, 720)
SIDEBAR_WIDTH = 344
MAIN_MARGIN_X = 36
MAIN_MAX_COLUMNS = 5
MAIN_WHEEL_SCROLL_UNITS = 3


def _runtime_asset_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", "")
    if bundle_root:
        return Path(bundle_root)
    return Path(__file__).resolve().parents[1]


ASSET_DIR = Path(__file__).resolve().parent / "assets"
APP_ICON_PATH = ASSET_DIR / "logicguard-library-icon.png"
BRAND_ICON_PATH = ASSET_DIR / "logicguard-library-icon-sidebar.png"
PROJECT_GITHUB_URL = "https://github.com/liuyingxuvka/ResearchGuard"
VOLUNTARY_SUPPORT_URL = "https://paypal.me/Yingxuliu"

LANGUAGE_DISPLAY_OPTIONS = {
    DEFAULT_LANGUAGE: "English / 英文",
    ZH_CN: "中文 / Chinese",
}

def _language_display(language: str) -> str:
    return LANGUAGE_DISPLAY_OPTIONS[normalize_language(language)]


def _language_from_display(value: str) -> str:
    for language, label in LANGUAGE_DISPLAY_OPTIONS.items():
        if value == label:
            return language
    return normalize_language(value)


def _wheel_scroll_units(delta: float, *, multiplier: int = 1) -> int:
    units = int(-1 * (delta / 120) * multiplier)
    if units == 0 and delta:
        return -1 if delta > 0 else 1
    return units


UI_TEXT = {
    DEFAULT_LANGUAGE: {
        "all_cards": "All Sources",
        "predictive_memory_cards": "Project source library",
        "cards_suffix": "sources",
        "library": "Library",
        "status": "Modeling",
        "type": "Source Type",
        "paths": "Projects",
        "trusted": "Modeled",
        "candidates": "Unmodeled",
        "deprecated": "Boundary notes",
        "models": "Presentations",
        "preferences": "Papers",
        "heuristics": "Reports",
        "facts": "Notes",
        "routes": "Projects",
        "settings": "Settings / 设置",
        "about": "About / 关于",
        "search": "Search",
        "no_cards": "No sources in this view.",
        "confidence": "importance",
        "close": "Close",
        "save": "Save / 保存",
        "cancel": "Cancel / 取消",
        "language": "Language / 语言",
        "display_language": "Language / 语言",
        "language_hint": "Choose the display language. Source model content switches when bilingual text is saved.",
        "english_canonical": "English is canonical. Chinese display requires explicit saved Chinese model text.",
        "sidebar_subtitle": "Model Library",
        "library_packages": "Library packages",
        "library_packages_hint": "Export the whole LogicGuard source library or import a portable package. Project and uncategorized exports are available from their active views.",
        "export_scope": "Export",
        "import_scope": "Import",
        "dissolve_project": "Dissolve",
        "dissolve_project_title": "Dissolve project",
        "dissolve_project_confirm": "Dissolve project '{project_id}'? Source files and source models stay in the library.",
        "dissolve_project_done": "Project dissolved",
        "export_current_project": "Export current project",
        "export_all_sources": "Export all",
        "export_uncategorized": "Export uncategorized",
        "import_package": "Import package",
        "current_project_required": "Select a project in the sidebar before exporting the current project.",
        "package_exported": "Package exported",
        "package_imported": "Package imported",
        "package_error": "Package operation failed",
        "settings_title": "Settings / 设置",
        "about_title": "About LogicGuard Library Viewer",
        "if": "If",
        "action": "Action",
        "predict": "Predict",
        "use": "Use",
        "routes_section": "Routes",
        "primary": "Primary",
        "also": "Also",
        "related": "Related",
        "source": "Source",
        "temporal_clues": "Temporal clues",
        "source_scope": "Source",
        "local_source": "Local",
        "author": "Author",
        "skill_dependencies": "Skill dependencies",
        "skill_badge": "Skill",
        "registry_status": "Registry",
        "auto_install": "Auto install",
        "eligible": "eligible",
        "not_eligible": "not eligible",
        "recommendations": "Recommendations",
        "read_only": "Read-only",
        "argument_map": "Argument map",
        "research_flow": "Research flow",
        "graph_view": "Graph view",
        "recommended_graph": "Recommended graph",
        "reset_graph": "Reset view",
        "graph_interaction_hint": "Drag to pan · mouse wheel to zoom",
        "recent_history": "Recently Added",
        "search_title": "Search",
        "update_prepared_hint": "Update will run during the next Architect pass after the UI is closed.",
        "about_body": (
            "A LogicGuard model and material library viewer.\n\n"
            "Latest version:\n{github_url}\n\n"
            "If this project is useful to you, you can support its development:\n"
            "Buy me a coffee via PayPal: {support_url}\n\n"
            "Support is voluntary and does not purchase support, warranty, priority service, "
            "commercial rights, or feature requests.\n\n"
            "Source cards and logic graphs are read from the LogicGuard source library."
        ),
    },
    ZH_CN: {
        "all_cards": "全部资料",
        "predictive_memory_cards": "项目资料库",
        "cards_suffix": "份资料",
        "library": "资料库",
        "status": "建模状态",
        "type": "资料类型",
        "paths": "项目",
        "trusted": "已建模",
        "candidates": "未建模",
        "deprecated": "含边界说明",
        "models": "PPT",
        "preferences": "论文",
        "heuristics": "报告",
        "facts": "笔记",
        "routes": "项目",
        "settings": "设置 / Settings",
        "about": "关于 / About",
        "search": "搜索",
        "no_cards": "当前视图没有资料。",
        "confidence": "重要性",
        "close": "关闭",
        "save": "保存 / Save",
        "cancel": "取消 / Cancel",
        "language": "语言 / Language",
        "display_language": "语言 / Language",
        "language_hint": "选择界面显示语言；资料模型保存了双语文本时，模型内容也会切换。",
        "english_canonical": "英文仍是默认兜底文本；已保存的双语模型可按英文或中文显示。",
        "sidebar_subtitle": "模型资料库",
        "library_packages": "资料包",
        "library_packages_hint": "导出整个 LogicGuard 资料库，或载入可迁移资料包。项目和未归类导出放在对应页面右上角。",
        "export_scope": "导出",
        "import_scope": "载入",
        "dissolve_project": "解散",
        "dissolve_project_title": "解散项目",
        "dissolve_project_confirm": "要解散项目“{project_id}”吗？资料文件和资料模型会继续保留在资料库里。",
        "dissolve_project_done": "项目已解散",
        "export_current_project": "导出当前项目",
        "export_all_sources": "导出全部",
        "export_uncategorized": "导出未归类",
        "import_package": "载入资料包",
        "current_project_required": "请先在侧边栏选择一个项目，再导出当前项目。",
        "package_exported": "资料包已导出",
        "package_imported": "资料包已载入",
        "package_error": "资料包操作失败",
        "settings_title": "设置 / Settings",
        "about_title": "关于 LogicGuard 资料库查看器",
        "if": "适用场景",
        "action": "动作/条件",
        "predict": "预测结果",
        "use": "使用方式",
        "routes_section": "路径",
        "primary": "主路径",
        "also": "也可从",
        "related": "相关卡片",
        "source": "来源",
        "temporal_clues": "时间线索",
        "source_scope": "来源",
        "local_source": "本地",
        "author": "制作人",
        "skill_dependencies": "Skill 依赖",
        "skill_badge": "技能",
        "registry_status": "登记状态",
        "auto_install": "自动安装",
        "eligible": "可用",
        "not_eligible": "不可用",
        "recommendations": "建议",
        "read_only": "只读",
        "argument_map": "论证图",
        "research_flow": "研究流程",
        "graph_view": "图谱视图",
        "recommended_graph": "推荐图",
        "reset_graph": "回正视图",
        "graph_interaction_hint": "拖拽平移 · 滚轮缩放",
        "recent_history": "最近加入",
        "search_title": "搜索",
        "update_prepared_hint": "关闭 UI 后，下次 Architect 检查会自动升级。",
        "about_body": (
            "一个用于检查 LogicGuard 模型和资料库的查看器。\n\n"
            "最新版本：\n{github_url}\n\n"
            "如果这个项目对你有帮助，可以自愿支持项目维护：\n"
            "通过 PayPal 请开发者喝杯咖啡：{support_url}\n\n"
            "自愿支持不代表购买技术支持、质保、优先服务、商业授权或功能定制。\n\n"
            "资料卡片和逻辑图都从 LogicGuard 资料库读取。"
        ),
    },
}

STATUS_FILTER_KEYS = {
    "modeled": "trusted",
    "unmodeled": "candidates",
    "risk": "deprecated",
    "recent": "recent_history",
}
TYPE_FILTER_KEYS = {
    "presentation": "models",
    "paper": "preferences",
    "report": "heuristics",
    "note": "facts",
    "web": "source",
    "source": "library",
}
SOURCE_FILTER_KEYS = {
    "local": "local_source",
}
SOURCE_SCOPE_LABELS = {
    DEFAULT_LANGUAGE: {
        "candidate": "Candidate",
        "private": "Private",
        "public": "Public",
        "trusted": "Trusted",
        "unknown": "",
    },
    ZH_CN: {
        "candidate": "候选",
        "private": "私有",
        "public": "公开",
        "trusted": "已信任",
        "unknown": "",
    },
}
SOURCE_KIND_LABELS = {
    DEFAULT_LANGUAGE: {
        "local": "Local",
        "logicguard": "LogicGuard",
    },
    ZH_CN: {
        "local": "本地",
        "logicguard": "LogicGuard",
    },
}

CARD_PALETTES = [
    {
        "name": "ion-blue",
        "fill": "#2563eb",
        "deep": "#ffffff",
        "soft": "#60a5fa",
        "line": "#bfdbfe",
        "muted": "#e0f2fe",
        "pill": "#eaf4ff",
        "pill_text": "#1d4ed8",
        "outline": "#a8c7ff",
    },
    {
        "name": "champagne-gold",
        "fill": "#d59b2e",
        "deep": "#ffffff",
        "soft": "#edc766",
        "line": "#f7e1a4",
        "muted": "#fff8e6",
        "pill": "#fff2cf",
        "pill_text": "#82520c",
        "outline": "#e8ca83",
    },
    {
        "name": "cyber-cyan",
        "fill": "#0891b2",
        "deep": "#ffffff",
        "soft": "#67e8f9",
        "line": "#a5f3fc",
        "muted": "#dcfbff",
        "pill": "#e5fbff",
        "pill_text": "#0e7490",
        "outline": "#99e7f0",
    },
    {
        "name": "copper-ember",
        "fill": "#b9683a",
        "deep": "#ffffff",
        "soft": "#d99563",
        "line": "#efc39d",
        "muted": "#fff0e4",
        "pill": "#fff0e2",
        "pill_text": "#874015",
        "outline": "#dfb28e",
    },
    {
        "name": "indigo-core",
        "fill": "#4f46e5",
        "deep": "#ffffff",
        "soft": "#818cf8",
        "line": "#c7d2fe",
        "muted": "#eef2ff",
        "pill": "#edf0ff",
        "pill_text": "#4338ca",
        "outline": "#b8c1fb",
    },
    {
        "name": "coral-signal",
        "fill": "#d8585e",
        "deep": "#ffffff",
        "soft": "#f08a86",
        "line": "#f8bbb4",
        "muted": "#fff0ef",
        "pill": "#fff0ef",
        "pill_text": "#a63237",
        "outline": "#efb0ad",
    },
    {
        "name": "cranberry-rose",
        "fill": "#bf3f66",
        "deep": "#ffffff",
        "soft": "#e27695",
        "line": "#f3b3c4",
        "muted": "#ffeaf0",
        "pill": "#ffeef3",
        "pill_text": "#942446",
        "outline": "#eab4c4",
    },
    {
        "name": "sage-green",
        "fill": "#6f9c82",
        "deep": "#ffffff",
        "soft": "#9fc2a9",
        "line": "#c9dccd",
        "muted": "#eff7f1",
        "pill": "#eef7f1",
        "pill_text": "#436c52",
        "outline": "#bfd5c5",
    },
    {
        "name": "steel-ice",
        "fill": "#64748b",
        "deep": "#ffffff",
        "soft": "#94a3b8",
        "line": "#cbd5e1",
        "muted": "#f1f5f9",
        "pill": "#edf2f7",
        "pill_text": "#475569",
        "outline": "#c8d1dc",
    },
    {
        "name": "burgundy-plum",
        "fill": "#8f3d59",
        "deep": "#ffffff",
        "soft": "#b96b83",
        "line": "#dda8b7",
        "muted": "#f8e8ee",
        "pill": "#faedf2",
        "pill_text": "#6f253f",
        "outline": "#d3a1b0",
    },
    {
        "name": "warm-plum",
        "fill": "#9b5c8f",
        "deep": "#ffffff",
        "soft": "#c389ba",
        "line": "#e3bfdc",
        "muted": "#fbecf8",
        "pill": "#f8edf6",
        "pill_text": "#713e6a",
        "outline": "#d7b4d0",
    },
    {
        "name": "amber-node",
        "fill": "#bf8416",
        "deep": "#ffffff",
        "soft": "#f3c24b",
        "line": "#f8dda0",
        "muted": "#fff8e6",
        "pill": "#fff2cf",
        "pill_text": "#7c4a03",
        "outline": "#e7c987",
    },
]


def _route_to_string(route: Any) -> str:
    if not route:
        return ""
    if isinstance(route, str):
        return route.strip("/")
    return "/".join(str(item).strip("/") for item in route if str(item).strip("/"))


def _ui_text(language: str, key: str) -> str:
    normalized = normalize_language(language)
    return UI_TEXT[normalized].get(key, key)


def _route_label(route: Any, language: str = DEFAULT_LANGUAGE, repo_root: Path | None = None) -> str:
    return localized_route_label(route, language, empty_label=_ui_text(language, "all_cards"), repo_root=repo_root)


def _route_title(route: Any, language: str = DEFAULT_LANGUAGE, repo_root: Path | None = None) -> str:
    return localized_route_title(route, language, empty_label=_ui_text(language, "all_cards"), repo_root=repo_root)


def _short_text(value: Any, limit: int = 150) -> str:
    text = normalize_text(value).strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}..."


def _short_id(value: Any, limit: int = 16) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    value = color.strip().lstrip("#")
    if len(value) != 6:
        return (255, 255, 255)
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _blend_hex(start: str, end: str, amount: float) -> str:
    ratio = max(0.0, min(1.0, amount))
    sr, sg, sb = _hex_to_rgb(start)
    er, eg, eb = _hex_to_rgb(end)
    return f"#{round(sr + (er - sr) * ratio):02x}{round(sg + (eg - sg) * ratio):02x}{round(sb + (eb - sb) * ratio):02x}"


def _palette(card: dict[str, Any] | None) -> dict[str, str]:
    if not card:
        return CARD_PALETTES[0]
    card_id = str(card.get("id") or card.get("title") or "")
    return CARD_PALETTES[sum(ord(char) for char in card_id) % len(CARD_PALETTES)]


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


def _card_type_value(card: dict[str, Any]) -> str:
    return str(card.get("type") or "model").replace("_", "-").strip().lower()


def _type_filter_label(card_type: str, language: str = DEFAULT_LANGUAGE) -> str:
    value = card_type.replace("_", "-").strip().lower()
    key = TYPE_FILTER_KEYS.get(value)
    if key:
        return _ui_text(language, key)
    return value.replace("-", " ").title() if value else _ui_text(language, "models")


def _status_label(card: dict[str, Any], language: str = DEFAULT_LANGUAGE) -> str:
    value = str(card.get("status") or "card").strip()
    if normalize_language(language) == ZH_CN:
        return {"modeled": "已建模", "unmodeled": "未建模", "risk": "含边界说明", "invalid_model": "模型有误"}.get(value.lower(), value)
    return {"risk": "Boundary notes"}.get(value.lower(), value)


def _modeling_status_label(card: dict[str, Any], language: str = DEFAULT_LANGUAGE) -> str:
    library_card = card.get("library_card") if isinstance(card.get("library_card"), dict) else {}
    value = str(library_card.get("modeling_status") or card.get("modeling_status") or card.get("status") or "").strip().lower()
    if value == "risk":
        value = "modeled"
    if normalize_language(language) == ZH_CN:
        return {"modeled": "已建模", "unmodeled": "未建模", "invalid_model": "模型有误"}.get(value, value or "未标注")
    return {"modeled": "Modeled", "unmodeled": "Unmodeled", "invalid_model": "Invalid model"}.get(value, value.replace("_", " ").title() if value else "Unmarked")


def _boundary_note_count(card: dict[str, Any]) -> int:
    library_card = card.get("library_card") if isinstance(card.get("library_card"), dict) else {}
    return int(library_card.get("risk_node_count") or 0) + int(library_card.get("risk_edge_count") or 0)


def _status_filter_label(status: str, language: str = DEFAULT_LANGUAGE) -> str:
    value = status.strip().lower()
    key = STATUS_FILTER_KEYS.get(value)
    if key:
        return _ui_text(language, key)
    return value.replace("-", " ").title() if value else _ui_text(language, "all_cards")


def _source_filter_label(source_kind: str, language: str = DEFAULT_LANGUAGE) -> str:
    value = source_kind.strip().lower()
    key = SOURCE_FILTER_KEYS.get(value)
    if key:
        return _ui_text(language, key)
    return value.replace("-", " ").title() if value else _ui_text(language, "source_scope")


def _confidence_label(card: dict[str, Any]) -> str:
    value = card.get("confidence")
    if value in (None, ""):
        return ""
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _skill_dependency_count(card: dict[str, Any]) -> int:
    value = card.get("skill_dependency_count")
    try:
        count = int(value)
    except (TypeError, ValueError):
        dependencies = card.get("skill_dependencies")
        count = len(dependencies) if isinstance(dependencies, list) else 0
    return max(0, count)


def _skill_badge_label(card: dict[str, Any], language: str = DEFAULT_LANGUAGE) -> str:
    count = _skill_dependency_count(card)
    if count <= 0:
        return ""
    if normalize_language(language) == ZH_CN:
        return f"{count} 个技能"
    return f"{count} Skill" if count == 1 else f"{count} Skills"


def _source_scope_display(scope: str, language: str = DEFAULT_LANGUAGE) -> str:
    normalized_language = normalize_language(language)
    value = str(scope or "").strip().lower()
    labels = SOURCE_SCOPE_LABELS[normalized_language]
    return labels.get(value, value.replace("-", " ").title() if value else labels["unknown"])


def _source_kind_display(kind: str, language: str = DEFAULT_LANGUAGE) -> str:
    normalized_language = normalize_language(language)
    value = str(kind or "").strip().lower()
    labels = SOURCE_KIND_LABELS[normalized_language]
    return labels.get(value, value.replace("-", " ").title() if value else labels["local"])


def _author_display_label(
    value: Any,
    language: str = DEFAULT_LANGUAGE,
    *,
    source_kind: str = "",
) -> str:
    text = str(value or "").strip()
    normalized_language = normalize_language(language)
    if not text:
        return "未注明" if normalized_language == ZH_CN else "Unknown"
    if text.lower() == "local":
        return "本机" if normalized_language == ZH_CN else "This device"
    return text


def _author_inline_label(author: str, language: str = DEFAULT_LANGUAGE) -> str:
    if normalize_language(language) == ZH_CN:
        return f"作者：{author}"
    return f"Author: {author}"


def _source_line(card: dict[str, Any], language: str = DEFAULT_LANGUAGE) -> str:
    source_info = card.get("source_info") if isinstance(card.get("source_info"), dict) else {}
    kind = str(source_info.get("kind") or "").strip().lower()
    scope = str(source_info.get("scope") or card.get("scope") or "").strip().lower()
    project_ids = [str(item) for item in card.get("project_ids", []) or [] if str(item)]
    library_card = card.get("library_card") if isinstance(card.get("library_card"), dict) else {}
    if not project_ids:
        project_ids = [str(item) for item in library_card.get("project_ids", []) or [] if str(item)]
    parts: list[str] = []

    parts.append(_source_kind_display("local", language))
    scope_label = _source_scope_display(scope, language)
    if scope_label:
        parts.append(scope_label)
    if project_ids:
        label = "项目" if normalize_language(language) == ZH_CN else "Projects"
        visible = project_ids[:2]
        suffix = f" +{len(project_ids) - 2}" if len(project_ids) > 2 else ""
        parts.append(f"{label}: {', '.join(visible)}{suffix}")
    else:
        parts.append("未归类" if normalize_language(language) == ZH_CN else "Uncategorized")

    if card.get("read_only"):
        parts.append("只读" if normalize_language(language) == ZH_CN else "read-only")
    return " · ".join(parts)


def _compact_source_line(card: dict[str, Any], language: str = DEFAULT_LANGUAGE) -> str:
    line = _source_line(card, language)
    if normalize_language(language) == ZH_CN:
        return line.replace("作者：", "")
    return line.replace("Author: ", "")


def _temporal_values(card: dict[str, Any]) -> tuple[str, str, str]:
    library_card = card.get("library_card") if isinstance(card.get("library_card"), dict) else {}
    temporal = library_card.get("temporal_context") if isinstance(library_card.get("temporal_context"), dict) else {}
    added = str(temporal.get("added_at") or library_card.get("added_at") or card.get("added_at") or "")
    source_date = str(temporal.get("source_date") or library_card.get("source_date") or library_card.get("year") or card.get("source_date") or "")
    coverage = str(temporal.get("coverage_period") or library_card.get("coverage_period") or card.get("coverage_period") or "")
    return added, source_date, coverage


def _compact_temporal_line(card: dict[str, Any], language: str = DEFAULT_LANGUAGE) -> str:
    added, source_date, coverage = _temporal_values(card)
    normalized = normalize_language(language)
    parts: list[str] = []
    if source_date:
        parts.append(source_date)
    if coverage:
        parts.append(("覆盖 " if normalized == ZH_CN else "covers ") + coverage)
    if added:
        parts.append(("加入 " if normalized == ZH_CN else "added ") + added[:10])
    return " · ".join(parts)


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


def _temporal_detail_lines(card: dict[str, Any], language: str = DEFAULT_LANGUAGE) -> list[str]:
    added, source_date, coverage = _temporal_values(card)
    normalized = normalize_language(language)
    if normalized == ZH_CN:
        return [
            f"加入资料库：{added or '未标注'}",
            f"资料时间：{source_date or '未标注'}",
            f"覆盖时期：{coverage or '未标注'}",
        ]
    return [
        f"Added to library: {added or 'unmarked'}",
        f"Source date: {source_date or 'unmarked'}",
        f"Coverage period: {coverage or 'unmarked'}",
    ]


def _fit_text_to_width(text: str, font: tkfont.Font, max_width: int) -> str:
    clean = normalize_text(text)
    if font.measure(clean) <= max_width:
        return clean
    ellipsis = "..."
    while clean and font.measure(f"{clean}{ellipsis}") > max_width:
        clean = clean[:-1].rstrip()
    return f"{clean}{ellipsis}" if clean else ellipsis


def _cover_title(card: dict[str, Any], language: str = DEFAULT_LANGUAGE) -> str:
    raw_title = normalize_text(card.get("title")).strip()
    placeholder = "卡片" if normalize_language(language) == ZH_CN else "Card"
    return raw_title or str(card.get("id") or placeholder)


def _text_lines(text: str, max_chars: int, max_lines: int) -> list[str]:
    clean = normalize_text(text)
    if not clean:
        return [""]
    if all(ord(char) <= 127 for char in clean):
        wrapped = textwrap.wrap(clean, width=max_chars, break_long_words=False, break_on_hyphens=False) or [""]
        if len(wrapped) <= max_lines:
            return wrapped
        last = wrapped[max_lines - 1]
        return [*wrapped[: max_lines - 1], f"{last[: max(0, len(last) - 3)].rstrip()}..."]
    lines: list[str] = []
    current = ""
    current_units = 0
    for char in clean:
        units = 2 if ord(char) > 127 else 1
        if char.isspace() and not current:
            continue
        if current and current_units + units > max_chars:
            lines.append(current.rstrip())
            if len(lines) >= max_lines:
                last = lines[-1]
                lines[-1] = f"{last[: max(0, len(last) - 3)].rstrip()}..."
                return lines
            current = ""
            current_units = 0
            if char.isspace():
                continue
        current += char
        current_units += units
    if current or not lines:
        lines.append(current.rstrip())
    return lines[:max_lines]


def _detail_paragraphs(value: Any, language: str = DEFAULT_LANGUAGE) -> list[str]:
    paragraphs: list[str] = []

    def append_text(item: Any) -> None:
        text = normalize_text(item).strip()
        if text:
            paragraphs.append(text)

    def append_value(item: Any) -> None:
        if item in (None, ""):
            return
        if isinstance(item, dict):
            preferred_keys = (
                "notes",
                "description",
                "expected_result",
                "guidance",
                "summary",
                "scenario",
                "action_taken",
                "observed_result",
                "previous_action",
                "previous_result",
                "revised_action",
                "revised_result",
                "operational_use",
            )
            for key in preferred_keys:
                if key in item:
                    append_value(item.get(key))
            alternatives = item.get("alternatives")
            if isinstance(alternatives, list):
                is_zh = normalize_language(language) == ZH_CN
                label = "对照路径" if is_zh else "Alternative"
                colon = "：" if is_zh else ": "
                for alternative in alternatives:
                    if isinstance(alternative, dict):
                        when = normalize_text(alternative.get("when")).strip()
                        result = normalize_text(alternative.get("result")).strip()
                        if when and result:
                            separator = f"；对应结果：" if is_zh else " -> "
                            paragraphs.append(f"{label}{colon}{when}{separator}{result}")
                        elif when or result:
                            paragraphs.append(f"{label}{colon}{when or result}")
                    else:
                        append_text(alternative)
            for key, nested in item.items():
                if key in (*preferred_keys, "alternatives"):
                    continue
                if isinstance(nested, (str, int, float, bool)):
                    append_value(nested)
            return
        if isinstance(item, list):
            for nested in item:
                append_value(nested)
            return
        append_text(item)

    append_value(value)
    return paragraphs or ["-"]


class KbDesktopApp(tk.Tk):
    def __init__(self, repo_root: str | Path, *, language: str | None = None) -> None:
        super().__init__()
        self._unit_scale = self._detect_unit_scale()
        self._font_scale = self._detect_font_scale()
        self.repo_root = resolve_repo_root(repo_root)
        self.settings = load_desktop_settings(self.repo_root)
        selected_language = language if language is not None else self.settings.get("language")
        self.language = normalize_language(selected_language)
        self.settings["language"] = self.language
        self.route = ""
        self.deck: list[dict[str, Any]] = []
        self.selected_index = -1
        self.children_by_route: dict[str, list[dict[str, Any]]] = {}
        self.expanded_routes: set[str] = {""}
        self.expanded_sidebar_sections: set[str] = set()
        self.nav_hitboxes: list[tuple[int, int, int, int, str, str]] = []
        self.footer_hitboxes: list[tuple[int, int, int, int, str]] = []
        self.card_hitboxes: list[tuple[int, int, int, int, int]] = []
        self.update_badge_hitbox: tuple[int, int, int, int] | None = None
        self.export_badge_hitbox: tuple[int, int, int, int, str, str] | None = None
        self.import_badge_hitbox: tuple[int, int, int, int, str] | None = None
        self.dissolve_project_hitbox: tuple[int, int, int, int, str] | None = None
        self._main_width = 0
        self._main_height = 0
        self._card_selected_by_user = False
        self.hovered_index = -1
        self._search_after_id: str | None = None
        self.title("LogicGuard Library Viewer")
        self.geometry(f"{self._u(DEFAULT_WINDOW_SIZE[0])}x{self._u(DEFAULT_WINDOW_SIZE[1])}")
        self.minsize(self._u(MIN_WINDOW_SIZE[0]), self._u(MIN_WINDOW_SIZE[1]))
        self.configure(bg=BG)
        self._app_icon_photo: tk.PhotoImage | None = None
        self._brand_icon_photo: tk.PhotoImage | None = None
        self._card_surface_photos: list[Any] = []
        self._card_surface_cache: dict[tuple[Any, ...], Any] = {}
        self._load_image_assets()

        self._build_layout()
        self.load_route("")
        self.after_idle(self._maximize_initial_window)
        self.after(160, self._maximize_initial_window)

    def _load_image_assets(self) -> None:
        if APP_ICON_PATH.exists():
            try:
                self._app_icon_photo = tk.PhotoImage(file=str(APP_ICON_PATH))
                self.iconphoto(True, self._app_icon_photo)
            except tk.TclError:
                self._app_icon_photo = None
        if BRAND_ICON_PATH.exists():
            try:
                icon_size = self._u(52)
                with Image.open(BRAND_ICON_PATH) as image:
                    self._brand_icon_photo = ImageTk.PhotoImage(
                        image.convert("RGBA").resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                    )
            except (OSError, tk.TclError):
                self._brand_icon_photo = None

    def _maximize_initial_window(self) -> None:
        try:
            self.state("zoomed")
        except tk.TclError:
            self.geometry(f"{self._u(1440)}x{self._u(900)}")

    def _detect_unit_scale(self) -> float:
        try:
            dpi = float(self.winfo_fpixels("1i"))
        except tk.TclError:
            dpi = 96.0
        return max(1.0, min(2.45, dpi / 120.0))

    def _detect_font_scale(self) -> float:
        try:
            dpi = float(self.winfo_fpixels("1i"))
        except tk.TclError:
            dpi = 96.0
        return max(1.0, min(2.85, dpi / 104.0))

    def _u(self, value: float) -> int:
        return int(round(value * self._unit_scale))

    def _f(self, pixels: int) -> int:
        return -int(round(pixels * self._font_scale))

    def _font(self, pixels: int, weight: str = "normal") -> tuple[str, int] | tuple[str, int, str]:
        family = CJK_UI_FONT if self.language == ZH_CN else UI_FONT
        if weight == "normal":
            return (family, self._f(pixels))
        return (family, self._f(pixels), weight)

    def _icon_font(self, pixels: int) -> tuple[str, int]:
        return (ICON_FONT, self._f(pixels))

    def _text(self, key: str) -> str:
        return _ui_text(self.language, key)

    def _local_policy_allows_skill_auto_install(self) -> bool:
        return False

    def _should_show_source_metadata(self, card: dict[str, Any] | None = None) -> bool:
        return card is not None

    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar_panel = tk.Frame(self, width=self._u(SIDEBAR_WIDTH), bg=SIDEBAR)
        self.sidebar_panel.grid(row=0, column=0, sticky="nsew")
        self.sidebar_panel.grid_propagate(False)
        self.sidebar_panel.grid_columnconfigure(0, weight=1)
        self.sidebar_panel.grid_rowconfigure(0, weight=1)

        self.sidebar = tk.Canvas(self.sidebar_panel, width=self._u(SIDEBAR_WIDTH), bg=SIDEBAR, highlightthickness=0, yscrollincrement=self._u(18))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar_scroll = tk.Scrollbar(self.sidebar_panel, orient="vertical", command=self.sidebar.yview, width=self._u(8))
        self.sidebar_scroll.grid(row=0, column=0, sticky="nse")
        self.sidebar.configure(yscrollcommand=self.sidebar_scroll.set)
        self.sidebar.bind("<Configure>", lambda _event: self._render_sidebar())
        self.sidebar.bind("<Button-1>", self._on_sidebar_click)
        self.sidebar.bind("<MouseWheel>", self._on_sidebar_mousewheel)

        self.sidebar_footer = tk.Canvas(self.sidebar_panel, width=self._u(SIDEBAR_WIDTH), height=self._u(146), bg=SIDEBAR, highlightthickness=0)
        self.sidebar_footer.grid(row=1, column=0, sticky="ew")
        self.sidebar_footer.bind("<Configure>", lambda _event: self._render_footer())
        self.sidebar_footer.bind("<Button-1>", self._on_footer_click)

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            self.sidebar,
            textvariable=self.search_var,
            relief="flat",
            bg=BG,
            fg=TEXT,
            insertbackground=TEXT,
            borderwidth=0,
            font=self._font(15),
        )
        self.search_entry.insert(0, self._text("search"))
        self.search_entry.bind("<FocusIn>", self._clear_search_placeholder)
        self.search_entry.bind("<FocusOut>", self._restore_search_placeholder)
        self.search_entry.bind("<KeyRelease>", self._schedule_search)
        self.search_entry.bind("<Return>", self._perform_search)
        self.search_window = self.sidebar.create_window(self._u(64), self._u(166), window=self.search_entry, anchor="nw", width=self._u(190), height=self._u(30))

        self.main = tk.Canvas(self, bg=BG, highlightthickness=0, yscrollincrement=self._u(22))
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main_scroll = tk.Scrollbar(self, orient="vertical", command=self.main.yview, width=self._u(8))
        self.main_scroll.grid(row=0, column=1, sticky="nse")
        self.main.configure(yscrollcommand=self.main_scroll.set)
        self.main.bind("<Configure>", self._on_main_configure)
        self.main.bind("<Button-1>", self._on_card_click)
        self.main.bind("<Motion>", self._on_card_motion)
        self.main.bind("<Leave>", self._on_card_leave)
        self.main.bind("<MouseWheel>", self._on_mousewheel)
        self.bind("<Return>", lambda _event: self.open_selected_detail())
        self.bind("<Left>", lambda _event: self._move_selection(-1))
        self.bind("<Right>", lambda _event: self._move_selection(1))

    def _round_rect(
        self,
        canvas: tk.Canvas,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        radius: int,
        *,
        fill: str,
        outline: str = "",
        width: int = 1,
        tags: str | tuple[str, ...] = "",
    ) -> None:
        r = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)
        canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=fill, tags=tags)
        canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline=fill, tags=tags)
        canvas.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, fill=fill, outline=fill, tags=tags)
        canvas.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, fill=fill, outline=fill, tags=tags)
        canvas.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, fill=fill, outline=fill, tags=tags)
        canvas.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, fill=fill, outline=fill, tags=tags)
        if not outline:
            return
        canvas.create_line(x1 + r, y1, x2 - r, y1, fill=outline, width=width, tags=tags)
        canvas.create_line(x2, y1 + r, x2, y2 - r, fill=outline, width=width, tags=tags)
        canvas.create_line(x1 + r, y2, x2 - r, y2, fill=outline, width=width, tags=tags)
        canvas.create_line(x1, y1 + r, x1, y2 - r, fill=outline, width=width, tags=tags)
        canvas.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, style="arc", outline=outline, width=width, tags=tags)
        canvas.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, style="arc", outline=outline, width=width, tags=tags)
        canvas.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, style="arc", outline=outline, width=width, tags=tags)
        canvas.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, style="arc", outline=outline, width=width, tags=tags)

    def _gradient_rect(
        self,
        canvas: tk.Canvas,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        radius: int,
        palette: dict[str, str],
        *,
        outline: str = "",
        width: int = 1,
    ) -> None:
        r = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)
        rect_w = max(1, x2 - x1)
        rect_h = max(1, y2 - y1)
        top = _blend_hex(palette.get("soft", palette["fill"]), "#ffffff", 0.06)
        mid = palette["fill"]
        bottom = _blend_hex(palette["fill"], "#000000", 0.14)
        self._round_rect(canvas, x1, y1, x2, y2, r, fill=mid)
        bands = max(24, min(96, rect_h // max(1, self._u(3))))
        for band in range(bands):
            band_y1 = y1 + round(rect_h * band / bands)
            band_y2 = y1 + round(rect_h * (band + 1) / bands) + 1
            local_mid_y = ((band_y1 + band_y2) / 2) - y1
            inset = 0
            if r > 0 and local_mid_y < r:
                dy = r - local_mid_y
                inset = round(r - math.sqrt(max(0, r * r - dy * dy)))
            elif r > 0 and local_mid_y > rect_h - r:
                dy = local_mid_y - (rect_h - r)
                inset = round(r - math.sqrt(max(0, r * r - dy * dy)))
            t = band / max(1, bands - 1)
            color = _blend_hex(top, mid, t / 0.55) if t <= 0.55 else _blend_hex(mid, bottom, (t - 0.55) / 0.45)
            canvas.create_rectangle(
                x1 + inset,
                band_y1,
                x1 + rect_w - inset,
                band_y2,
                fill=color,
                outline=color,
            )
        if outline:
            self._round_rect(canvas, x1, y1, x2, y2, r, fill="", outline=outline, width=width)

    def _draw_card_surface(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        radius: int,
        palette: dict[str, str],
        *,
        hovered: bool = False,
    ) -> None:
        scale = 2
        shadow_x = self._u(2) if not hovered else self._u(3)
        shadow_y = self._u(2) if not hovered else self._u(3)
        blur = max(1, self._u(1.4 if not hovered else 1.8))
        margin = max(self._u(4), blur + self._u(1))

        cache_key = (
            "card-surface-diagonal-v1",
            width,
            height,
            radius,
            hovered,
            palette.get("soft", ""),
            palette.get("fill", ""),
            shadow_x,
            shadow_y,
            blur,
        )
        cached_photo = self._card_surface_cache.get(cache_key)
        if cached_photo is not None:
            self._card_surface_photos.append(cached_photo)
            self.main.create_image(x - margin, y - margin, image=cached_photo, anchor="nw")
            return

        image_w = max(1, width + shadow_x + margin * 2)
        image_h = max(1, height + shadow_y + margin * 2)
        surface = Image.new("RGBA", (image_w * scale, image_h * scale), (0, 0, 0, 0))

        card_x = margin * scale
        card_y = margin * scale
        card_w = max(1, width * scale)
        card_h = max(1, height * scale)
        radius_s = max(1, radius * scale)

        shadow_layer = Image.new("RGBA", surface.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        shadow_alpha = 58 if hovered else 34
        shadow_box = [
            card_x + shadow_x * scale,
            card_y + shadow_y * scale,
            card_x + (shadow_x + width) * scale - 1,
            card_y + (shadow_y + height) * scale - 1,
        ]
        shadow_draw.rounded_rectangle(
            shadow_box,
            radius=radius_s,
            fill=(*_hex_to_rgb("#9aa1b2" if hovered else "#b8bdca"), shadow_alpha),
        )
        blurred_shadow = shadow_layer.filter(ImageFilter.GaussianBlur(blur * scale))
        surface = Image.alpha_composite(surface, blurred_shadow)

        top = _blend_hex(palette.get("soft", palette["fill"]), "#ffffff", 0.16)
        mid = palette["fill"]
        bottom = _blend_hex(palette["fill"], "#000000", 0.14)
        resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
        sample_w = min(128, card_w)
        sample_h = min(128, card_h)
        gradient_sample = Image.new("RGBA", (sample_w, sample_h), (0, 0, 0, 0))
        gradient_draw = ImageDraw.Draw(gradient_sample)
        max_x = max(1, sample_w - 1)
        max_y = max(1, sample_h - 1)
        for yy in range(sample_h):
            y_ratio = yy / max_y
            for xx in range(sample_w):
                t = ((xx / max_x) + y_ratio) / 2
                color = _blend_hex(top, mid, t / 0.55) if t <= 0.55 else _blend_hex(mid, bottom, (t - 0.55) / 0.45)
                gradient_draw.point((xx, yy), fill=(*_hex_to_rgb(color), 255))
        gradient = gradient_sample.resize((card_w, card_h), resampling)

        highlight_sample = Image.new("RGBA", (sample_w, sample_h), (0, 0, 0, 0))
        highlight_draw = ImageDraw.Draw(highlight_sample)
        max_diag = max(1, sample_w + sample_h - 2)
        for yy in range(sample_h):
            for xx in range(sample_w):
                alpha = max(0, int((1 - (xx + yy) / max_diag) * (24 if hovered else 18)))
                if alpha:
                    highlight_draw.point((xx, yy), fill=(255, 255, 255, alpha))
        highlight = highlight_sample.resize((card_w, card_h), resampling)

        texture = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        texture_draw = ImageDraw.Draw(texture)
        arc_alpha = 22 if hovered else 16
        arc_width = max(2, int(2.2 * scale))
        arc_color = (255, 255, 255, arc_alpha)
        texture_draw.arc(
            [int(card_w * 0.22), -int(card_h * 0.28), int(card_w * 1.24), int(card_h * 1.24)],
            start=205,
            end=318,
            fill=arc_color,
            width=arc_width,
        )
        texture_draw.arc(
            [int(card_w * 0.40), -int(card_h * 0.10), int(card_w * 1.36), int(card_h * 1.06)],
            start=206,
            end=312,
            fill=(255, 255, 255, max(8, arc_alpha - 6)),
            width=max(1, arc_width - 1),
        )
        texture = Image.alpha_composite(highlight, texture)
        gradient = Image.alpha_composite(gradient, texture)

        mask = Image.new("L", (card_w, card_h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, card_w - 1, card_h - 1], radius=radius_s, fill=255)
        surface.paste(gradient, (card_x, card_y), mask)
        rim = Image.new("RGBA", surface.size, (0, 0, 0, 0))
        rim_draw = ImageDraw.Draw(rim)
        rim_draw.rounded_rectangle(
            [card_x, card_y, card_x + card_w - 1, card_y + card_h - 1],
            radius=radius_s,
            outline=(255, 255, 255, 42),
            width=max(1, scale),
        )
        surface = Image.alpha_composite(surface, rim)

        surface = surface.resize((image_w, image_h), resampling)
        photo = ImageTk.PhotoImage(surface)
        self._card_surface_cache[cache_key] = photo
        self._card_surface_photos.append(photo)
        self.main.create_image(x - margin, y - margin, image=photo, anchor="nw")

    def _draw_gradient_surface(
        self,
        canvas: tk.Canvas,
        x: int,
        y: int,
        width: int,
        height: int,
        radius: int,
        palette: dict[str, str],
    ) -> None:
        scale = 2
        image_w = max(1, width)
        image_h = max(1, height)
        radius_s = max(1, radius * scale)
        cache_key = (
            "gradient-diagonal-v1",
            image_w,
            image_h,
            radius,
            palette.get("soft", ""),
            palette.get("fill", ""),
        )
        cached_photo = self._card_surface_cache.get(cache_key)
        if cached_photo is not None:
            canvas.create_image(x, y, image=cached_photo, anchor="nw")
            setattr(canvas, "_surface_photo", cached_photo)
            return

        top = _blend_hex(palette.get("soft", palette["fill"]), "#ffffff", 0.16)
        mid = palette["fill"]
        bottom = _blend_hex(palette["fill"], "#000000", 0.14)
        surface_w = image_w * scale
        surface_h = image_h * scale
        sample_w = min(160, surface_w)
        sample_h = min(160, surface_h)
        gradient_sample = Image.new("RGBA", (sample_w, sample_h), (0, 0, 0, 0))
        gradient_draw = ImageDraw.Draw(gradient_sample)
        max_x = max(1, sample_w - 1)
        max_y = max(1, sample_h - 1)
        for yy in range(sample_h):
            y_ratio = yy / max_y
            for xx in range(sample_w):
                t = ((xx / max_x) + y_ratio) / 2
                color = _blend_hex(top, mid, t / 0.55) if t <= 0.55 else _blend_hex(mid, bottom, (t - 0.55) / 0.45)
                gradient_draw.point((xx, yy), fill=(*_hex_to_rgb(color), 255))
        resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
        gradient = gradient_sample.resize((surface_w, surface_h), resampling)

        texture = Image.new("RGBA", (surface_w, surface_h), (0, 0, 0, 0))
        texture_draw = ImageDraw.Draw(texture)
        arc_width = max(2, int(2.2 * scale))
        texture_draw.arc(
            [int(surface_w * 0.30), -int(surface_h * 0.36), int(surface_w * 1.14), int(surface_h * 1.24)],
            start=204,
            end=320,
            fill=(255, 255, 255, 16),
            width=arc_width,
        )
        texture_draw.arc(
            [int(surface_w * 0.46), -int(surface_h * 0.16), int(surface_w * 1.26), int(surface_h * 1.08)],
            start=206,
            end=314,
            fill=(255, 255, 255, 10),
            width=max(1, arc_width - 1),
        )
        highlight_sample = Image.new("RGBA", (sample_w, sample_h), (0, 0, 0, 0))
        highlight_draw = ImageDraw.Draw(highlight_sample)
        max_diag = max(1, sample_w + sample_h - 2)
        for yy in range(sample_h):
            for xx in range(sample_w):
                alpha = max(0, int((1 - (xx + yy) / max_diag) * 18))
                if alpha:
                    highlight_draw.point((xx, yy), fill=(255, 255, 255, alpha))
        texture = Image.alpha_composite(highlight_sample.resize((surface_w, surface_h), resampling), texture)
        gradient = Image.alpha_composite(gradient, texture)

        mask = Image.new("L", (surface_w, surface_h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, surface_w - 1, surface_h - 1], radius=radius_s, fill=255)

        surface = Image.new("RGBA", (surface_w, surface_h), (0, 0, 0, 0))
        surface.paste(gradient, (0, 0), mask)
        rim_draw = ImageDraw.Draw(surface)
        rim_draw.rounded_rectangle(
            [0, 0, surface_w - 1, surface_h - 1],
            radius=radius_s,
            outline=(255, 255, 255, 42),
            width=max(1, scale),
        )
        surface = surface.resize((image_w, image_h), resampling)
        photo = ImageTk.PhotoImage(surface)
        self._card_surface_cache[cache_key] = photo
        canvas.create_image(x, y, image=photo, anchor="nw")
        setattr(canvas, "_surface_photo", photo)

    def _draw_sidebar_icon(self, canvas: tk.Canvas, cx: int, cy: int, kind: str, color: str, tags: str) -> None:
        u = self._u
        stroke = max(1, u(1.4))
        if kind == "search":
            canvas.create_oval(cx - u(7), cy - u(7), cx + u(5), cy + u(5), outline=color, width=stroke, tags=tags)
            canvas.create_line(cx + u(4), cy + u(4), cx + u(10), cy + u(10), fill=color, width=stroke, tags=tags)
            return
        if kind == "cards":
            canvas.create_polygon(
                cx - u(8),
                cy - u(6),
                cx + u(8),
                cy - u(6),
                cx + u(5),
                cy + u(7),
                cx - u(11),
                cy + u(7),
                outline=color,
                fill="",
                width=stroke,
                tags=tags,
            )
            return
        if kind == "trusted":
            canvas.create_oval(cx - u(8), cy - u(8), cx + u(8), cy + u(8), outline=color, width=stroke, tags=tags)
            canvas.create_line(cx - u(5), cy, cx - u(1), cy + u(4), cx + u(6), cy - u(5), fill=color, width=stroke, tags=tags)
            return
        if kind == "candidates":
            canvas.create_rectangle(cx - u(8), cy - u(8), cx + u(8), cy + u(8), outline=color, width=stroke, tags=tags)
            for offset in (-5, 0, 5):
                canvas.create_line(cx - u(8), cy + u(offset - 4), cx + u(8), cy + u(offset + 4), fill=color, width=stroke, tags=tags)
            return
        if kind == "deprecated":
            canvas.create_oval(cx - u(8), cy - u(8), cx + u(8), cy + u(8), outline=color, width=stroke, tags=tags)
            canvas.create_line(cx - u(5), cy + u(5), cx + u(5), cy - u(5), fill=color, width=stroke, tags=tags)
            return
        if kind == "status":
            for offset in (-6, 0, 6):
                canvas.create_oval(cx - u(9), cy + u(offset) - u(2), cx - u(5), cy + u(offset) + u(2), outline=color, width=stroke, tags=tags)
                canvas.create_line(cx - u(1), cy + u(offset), cx + u(9), cy + u(offset), fill=color, width=stroke, tags=tags)
            return
        if kind == "type":
            canvas.create_rectangle(cx - u(8), cy - u(8), cx + u(8), cy + u(8), outline=color, width=stroke, tags=tags)
            canvas.create_line(cx - u(4), cy - u(4), cx + u(4), cy - u(4), fill=color, width=stroke, tags=tags)
            canvas.create_line(cx, cy - u(4), cx, cy + u(6), fill=color, width=stroke, tags=tags)
            canvas.create_line(cx - u(4), cy + u(6), cx + u(4), cy + u(6), fill=color, width=stroke, tags=tags)
            return
        if kind == "model":
            canvas.create_oval(cx - u(9), cy - u(9), cx + u(9), cy + u(9), outline=color, width=stroke, tags=tags)
            canvas.create_oval(cx - u(3), cy - u(3), cx + u(3), cy + u(3), outline=color, width=stroke, tags=tags)
            canvas.create_line(cx - u(12), cy, cx - u(8), cy, fill=color, width=stroke, tags=tags)
            canvas.create_line(cx + u(8), cy, cx + u(12), cy, fill=color, width=stroke, tags=tags)
            return
        if kind == "preference":
            for offset, knob in ((-6, -3), (0, 5), (6, 0)):
                canvas.create_line(cx - u(10), cy + u(offset), cx + u(10), cy + u(offset), fill=color, width=stroke, tags=tags)
                canvas.create_oval(
                    cx + u(knob) - u(2),
                    cy + u(offset) - u(2),
                    cx + u(knob) + u(2),
                    cy + u(offset) + u(2),
                    outline=color,
                    width=stroke,
                    tags=tags,
                )
            return
        if kind == "heuristic":
            canvas.create_oval(cx - u(2), cy - u(2), cx + u(2), cy + u(2), outline=color, width=stroke, tags=tags)
            for dx, dy in ((-8, -6), (8, -6), (0, 8)):
                canvas.create_line(cx, cy, cx + u(dx), cy + u(dy), fill=color, width=stroke, tags=tags)
                canvas.create_oval(cx + u(dx) - u(2), cy + u(dy) - u(2), cx + u(dx) + u(2), cy + u(dy) + u(2), outline=color, width=stroke, tags=tags)
            return
        if kind == "fact":
            canvas.create_oval(cx - u(8), cy - u(8), cx + u(8), cy + u(8), outline=color, width=stroke, tags=tags)
            canvas.create_line(cx, cy - u(1), cx, cy + u(5), fill=color, width=stroke, tags=tags)
            canvas.create_oval(cx - u(1), cy - u(6), cx + u(1), cy - u(4), fill=color, outline=color, tags=tags)
            return
        if kind == "paths":
            nodes = ((-8, 5), (0, -5), (8, 4))
            canvas.create_line(
                cx + u(nodes[0][0]),
                cy + u(nodes[0][1]),
                cx + u(nodes[1][0]),
                cy + u(nodes[1][1]),
                cx + u(nodes[2][0]),
                cy + u(nodes[2][1]),
                fill=color,
                width=stroke,
                tags=tags,
            )
            for dx, dy in nodes:
                canvas.create_oval(cx + u(dx) - u(3), cy + u(dy) - u(3), cx + u(dx) + u(3), cy + u(dy) + u(3), outline=color, width=stroke, tags=tags)
            return
        if kind == "route":
            canvas.create_line(cx - u(7), cy, cx + u(7), cy, fill=color, width=max(stroke, u(1.6)), tags=tags)
            return
        if kind == "settings":
            canvas.create_oval(cx - u(8), cy - u(8), cx + u(8), cy + u(8), outline=color, width=stroke, tags=tags)
            canvas.create_oval(cx - u(3), cy - u(3), cx + u(3), cy + u(3), outline=color, width=stroke, tags=tags)
            for dx, dy in ((0, -11), (0, 11), (-11, 0), (11, 0), (-8, -8), (8, -8), (-8, 8), (8, 8)):
                canvas.create_line(cx + int(dx * self._unit_scale * 0.72), cy + int(dy * self._unit_scale * 0.72), cx + u(dx), cy + u(dy), fill=color, width=stroke, tags=tags)
            return
        if kind == "about":
            canvas.create_oval(cx - u(8), cy - u(8), cx + u(8), cy + u(8), outline=color, width=stroke, tags=tags)
            canvas.create_line(cx, cy - u(1), cx, cy + u(5), fill=color, width=stroke, tags=tags)
            canvas.create_oval(cx - u(1), cy - u(6), cx + u(1), cy - u(4), fill=color, outline=color, tags=tags)
            return

    def _render_sidebar(self) -> None:
        self.sidebar.delete("chrome")
        self.nav_hitboxes.clear()
        u = self._u
        width = max(int(self.sidebar.winfo_width()), u(SIDEBAR_WIDTH))
        height = max(int(self.sidebar.winfo_height()), u(560))
        self.sidebar.create_rectangle(0, 0, width, height, fill=SIDEBAR, outline=SIDEBAR, tags="chrome")
        self.sidebar.create_line(width - 1, 0, width - 1, height, fill=LINE, tags="chrome")

        if self._brand_icon_photo is not None:
            self.sidebar.create_image(u(50), u(72), image=self._brand_icon_photo, tags="chrome")
        else:
            self._round_rect(self.sidebar, u(24), u(46), u(76), u(98), u(10), fill=ACCENT, tags="chrome")
            self.sidebar.create_text(u(50), u(72), text="LG", fill=BG, font=self._font(17, "bold"), tags="chrome")
        self.sidebar.create_text(u(96), u(52), text="LogicGuard", anchor="nw", fill=TEXT, font=self._font(22, "bold"), tags="chrome")
        self.sidebar.create_text(u(96), u(83), text=self._text("sidebar_subtitle"), anchor="nw", fill=MUTED, font=self._font(12), tags="chrome")

        self._round_rect(self.sidebar, u(28), u(128), width - u(36), u(168), u(12), fill=BG, outline=LINE, tags="chrome")
        self._draw_sidebar_icon(self.sidebar, u(49), u(148), "search", MUTED, "chrome")
        self.sidebar.coords(self.search_window, u(72), u(137))
        self.sidebar.itemconfigure(self.search_window, width=max(u(140), width - u(122)), height=u(30))

        y = u(194)
        self._nav_row(u(28), y, width - u(32), self._text("all_cards"), "cards", "", active=self.route == "" and not self.searching)
        y += u(48)

        status_active = self.searching.startswith("status:")
        self._section_row(u(28), y, width - u(32), self._text("status"), "status", active=status_active)
        y += u(40)
        if "status" in self.expanded_sidebar_sections:
            for status in STATUS_FILTER_KEYS:
                self._nav_row(
                    u(42),
                    y,
                    width - u(36),
                    _status_filter_label(status, self.language),
                    "status",
                    status,
                    active=self.searching == f"status:{status}",
                )
                y += u(38)
            y += u(8)

        type_active = self.searching.startswith("type:")
        self._section_row(u(28), y, width - u(32), self._text("type"), "type", active=type_active)
        y += u(40)
        if "type" in self.expanded_sidebar_sections:
            for card_type in TYPE_FILTER_KEYS:
                self._nav_row(
                    u(42),
                    y,
                    width - u(36),
                    _type_filter_label(card_type, self.language),
                    "type",
                    card_type,
                    active=self.searching == f"type:{card_type}",
                )
                y += u(38)
            y += u(8)

        path_active = not self.searching and bool(self.route)
        self._section_row(u(28), y, width - u(32), self._text("paths"), "paths", active=path_active)
        y += u(40)
        if "paths" in self.expanded_sidebar_sections:
            for route, label, depth, active, ancestor, count, declared in self._visible_routes():
                self._route_row(u(42), y, width - u(40), route, label, depth, active, ancestor, count, declared)
                y += u(38)
        self.sidebar.configure(scrollregion=(0, 0, width, max(height, y + u(24))))
        self._render_footer()

    def _render_footer(self) -> None:
        self.sidebar_footer.delete("footer")
        self.footer_hitboxes.clear()
        u = self._u
        width = max(int(self.sidebar_footer.winfo_width()), u(SIDEBAR_WIDTH))
        height = max(int(self.sidebar_footer.winfo_height()), u(146))
        self.sidebar_footer.create_rectangle(0, 0, width, height, fill=SIDEBAR, outline=SIDEBAR, tags="footer")
        self.sidebar_footer.create_line(u(34), 0, width - u(40), 0, fill=LINE, tags="footer")
        self._footer_row(self.sidebar_footer, u(28), u(14), width - u(32), self._text("settings"), "settings")
        self._footer_row(self.sidebar_footer, u(28), u(56), width - u(32), self._text("about"), "about")

    @property
    def searching(self) -> str:
        title = getattr(self, "_searching", "")
        return title

    @searching.setter
    def searching(self, value: str) -> None:
        self._searching = value

    def _section_row(self, x1: int, y1: int, x2: int, label: str, section: str, *, active: bool) -> None:
        u = self._u
        y2 = y1 + u(36)
        expanded = section in self.expanded_sidebar_sections
        if active:
            self._round_rect(self.sidebar, x1, y1, x2, y2, u(10), fill="#f7f3f5", tags="chrome")
            self.sidebar.create_line(x1 - u(8), y1 + u(8), x1 - u(8), y2 - u(8), fill=ACCENT, width=max(1, u(2)), tags="chrome")
        icon = {"status": "status", "type": "type", "source": "cards", "paths": "paths"}.get(section, "route")
        icon_color = ACCENT if active else MUTED
        self._draw_sidebar_icon(self.sidebar, x1 + u(22), y1 + u(18), icon, icon_color, "chrome")
        self.sidebar.create_text(
            x1 + u(56),
            y1 + u(18),
            text=label,
            anchor="w",
            fill=ACCENT if active else TEXT,
            font=self._font(14),
            tags="chrome",
        )
        self.sidebar.create_text(
            x2 - u(14),
            y1 + u(18),
            text="▾" if expanded else "›",
            anchor="e",
            fill=MUTED,
            font=self._font(13, "bold"),
            tags="chrome",
        )
        self.nav_hitboxes.append((x1, y1, x2, y2, "toggle-section", section))

    def _nav_row(self, x1: int, y1: int, x2: int, label: str, action: str, value: str, *, active: bool) -> None:
        u = self._u
        y2 = y1 + u(38)
        if active:
            self._round_rect(self.sidebar, x1, y1, x2, y2, u(11), fill=SIDEBAR_ACTIVE, tags="chrome")
            self.sidebar.create_line(x1 - u(8), y1 + u(8), x1 - u(8), y2 - u(8), fill=ACCENT, width=max(1, u(2)), tags="chrome")
        icon = {"cards": "cards", "trusted": "trusted", "candidates": "candidates"}.get(action, "route")
        if action == "status":
            icon = {"trusted": "trusted", "candidate": "candidates", "deprecated": "deprecated"}.get(value, "status")
        if action == "type":
            icon = {"model": "model", "preference": "preference", "heuristic": "heuristic", "fact": "fact"}.get(value, "type")
        icon_color = ACCENT if active else MUTED
        self._draw_sidebar_icon(self.sidebar, x1 + u(22), y1 + u(19), icon, icon_color, "chrome")
        self.sidebar.create_text(
            x1 + u(56),
            y1 + u(19),
            text=label,
            anchor="w",
            fill=ACCENT if active else TEXT,
            font=self._font(14),
            tags="chrome",
        )
        self.nav_hitboxes.append((x1, y1, x2, y2, action, value))

    def _footer_row(self, canvas: tk.Canvas, x1: int, y1: int, x2: int, label: str, action: str) -> None:
        u = self._u
        y2 = y1 + u(36)
        icon = {"settings": "settings", "about": "about"}.get(action, "about")
        self._draw_sidebar_icon(canvas, x1 + u(22), y1 + u(18), icon, MUTED, "footer")
        canvas.create_text(x1 + u(54), y1 + u(18), text=label, anchor="w", fill=TEXT, font=self._font(14), tags="footer")
        self.footer_hitboxes.append((x1, y1, x2, y2, action))

    def _visible_routes(self) -> list[tuple[str, str, int, bool, bool, int, bool]]:
        rows: list[tuple[str, str, int, bool, bool, int, bool]] = []

        def walk(route: str, depth: int) -> None:
            if route not in self.expanded_routes:
                return
            for item in self.children_by_route.get(route, []):
                child_route = _route_to_string(item.get("route", []))
                active = child_route == self.route
                ancestor = bool(self.route and self.route.startswith(f"{child_route}/"))
                count = navigation_card_count(item)
                rows.append(
                    (
                        child_route,
                        localized_route_segment(item.get("segment") or child_route, self.language, repo_root=self.repo_root),
                        depth,
                        active,
                        ancestor,
                        count,
                        bool(item.get("declared", False)),
                    )
                )
                walk(child_route, depth + 1)

        walk("", 0)
        return rows

    def _route_row(
        self,
        x1: int,
        y1: int,
        x2: int,
        route: str,
        label: str,
        depth: int,
        active: bool,
        ancestor: bool,
        count: int,
        declared: bool,
    ) -> None:
        u = self._u
        y2 = y1 + u(36)
        indent = depth * u(19)
        if active:
            self._round_rect(self.sidebar, x1 - u(10), y1 - u(4), x2, y2 + u(4), u(10), fill=SIDEBAR_ACTIVE, tags="chrome")
            self.sidebar.create_line(x1 - u(16), y1 + u(5), x1 - u(16), y2 - u(5), fill=ACCENT, width=u(2), tags="chrome")
        icon_fill = ACCENT if active else MUTED
        text_fill = ACCENT if active else TEXT if ancestor or declared else MUTED
        self._draw_sidebar_icon(self.sidebar, x1 + indent + u(5), y1 + u(18), "route", icon_fill, "chrome")
        self.sidebar.create_text(
            x1 + indent + u(34),
            y1 + u(18),
            text=label,
            anchor="w",
            fill=text_fill,
            font=self._font(13),
            tags="chrome",
        )
        if count:
            pill_w = u(22) + len(str(count)) * u(8)
            self._round_rect(self.sidebar, x2 - u(42) - pill_w, y1 + u(8), x2 - u(42), y2 - u(8), u(9), fill="#f0f0f3", tags="chrome")
            self.sidebar.create_text(x2 - u(42) - pill_w / 2, y1 + u(18), text=str(count), fill=MUTED, font=self._font(10, "bold"), tags="chrome")
        if self.children_by_route.get(route):
            self.sidebar.create_text(x2 - u(6), y1 + u(18), text="›", anchor="e", fill="#b8b8bd", font=self._font(14), tags="chrome")
        self.nav_hitboxes.append((x1 - u(10), y1 - u(4), x2, y2 + u(4), "route", route))

    def _on_sidebar_click(self, event: tk.Event[Any]) -> None:
        y = int(self.sidebar.canvasy(event.y))
        for x1, y1, x2, y2, action, value in self.nav_hitboxes:
            if x1 <= event.x <= x2 and y1 <= y <= y2:
                if action == "cards":
                    self.load_route("")
                elif action == "toggle-section":
                    if value in self.expanded_sidebar_sections:
                        self.expanded_sidebar_sections.remove(value)
                    else:
                        self.expanded_sidebar_sections.add(value)
                    self._render_sidebar()
                elif action == "status":
                    self._load_status_view(value)
                elif action == "trusted":
                    self._load_status_view("trusted")
                elif action == "candidates":
                    self._load_status_view("candidate")
                elif action == "type":
                    self._load_type_view(value)
                elif action == "source":
                    self._load_source_view(value)
                elif action == "route":
                    self.load_route(value)
                return

    def _on_footer_click(self, event: tk.Event[Any]) -> None:
        for x1, y1, x2, y2, action in self.footer_hitboxes:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                if action == "settings":
                    self._open_settings_window()
                elif action == "about":
                    self._open_utility_window(
                        self._text("about_title"),
                        self._text("about_body").format(
                            github_url=PROJECT_GITHUB_URL,
                            support_url=VOLUNTARY_SUPPORT_URL,
                        ),
                    )
                return

    def _clear_search_placeholder(self, _event: tk.Event[Any]) -> None:
        if self.search_var.get() in {_ui_text(DEFAULT_LANGUAGE, "search"), _ui_text(ZH_CN, "search")}:
            self.search_var.set("")

    def _restore_search_placeholder(self, _event: tk.Event[Any]) -> None:
        if not self.search_var.get().strip():
            self.search_var.set(self._text("search"))

    def _schedule_search(self, event: tk.Event[Any]) -> None:
        if event.keysym in {
            "Alt_L",
            "Alt_R",
            "Control_L",
            "Control_R",
            "Down",
            "End",
            "Home",
            "Left",
            "Right",
            "Shift_L",
            "Shift_R",
            "Tab",
            "Up",
        }:
            return
        if self._search_after_id is not None:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(180, self._run_scheduled_search)

    def _run_scheduled_search(self) -> None:
        self._search_after_id = None
        self._perform_search()

    def _perform_search(self, _event: tk.Event[Any] | None = None, *, query: str | None = None) -> str:
        if self._search_after_id is not None:
            self.after_cancel(self._search_after_id)
            self._search_after_id = None
        query_text = (query or self.search_var.get()).strip()
        if not query_text or query_text in {_ui_text(DEFAULT_LANGUAGE, "search"), _ui_text(ZH_CN, "search")}:
            self.load_route(self.route)
            return "break"
        self.searching = query_text
        payload = build_search_payload(
            self.repo_root,
            query=query_text,
            route_hint=self.route,
            top_k=24,
            language=self.language,
        )
        self.deck = payload["results"]
        self.selected_index = -1
        self._card_selected_by_user = False
        self.hovered_index = -1
        self._route_heading = self._text("search_title")
        self._route_subtitle = query_text
        self._render_sidebar()
        self._render_main()
        return "break"

    def _load_status_view(self, status: str) -> None:
        status = status.strip().lower()
        self.route = ""
        self.searching = f"status:{status}"
        payload = build_route_view_payload(
            self.repo_root,
            route="",
            language=self.language,
        )
        if status == "recent":
            self.deck = sorted(
                payload.get("deck", []),
                key=lambda card: str(card.get("library_card", {}).get("added_at") or card.get("library_card", {}).get("updated_at") or ""),
                reverse=True,
            )
        elif status == "risk":
            self.deck = [
                card
                for card in payload.get("deck", [])
                if str(card.get("status") or "").lower() == "risk"
                or int(card.get("library_card", {}).get("risk_node_count") or 0)
                or int(card.get("library_card", {}).get("risk_edge_count") or 0)
            ]
        else:
            self.deck = [card for card in payload.get("deck", []) if str(card.get("status") or "").lower() == status]
        self.selected_index = -1
        self._card_selected_by_user = False
        self.hovered_index = -1
        self._route_heading = _status_filter_label(status, self.language)
        self._route_subtitle = f"{len(self.deck)} {self._text('cards_suffix')}"
        self._render_sidebar()
        self._render_main()

    def _load_type_view(self, card_type: str) -> None:
        card_type = card_type.strip().lower()
        self.route = ""
        self.searching = f"type:{card_type}"
        payload = build_route_view_payload(
            self.repo_root,
            route="",
            language=self.language,
        )
        self.deck = [card for card in payload.get("deck", []) if _card_type_value(card) == card_type]
        self.selected_index = -1
        self._card_selected_by_user = False
        self.hovered_index = -1
        self._route_heading = _type_filter_label(card_type, self.language)
        self._route_subtitle = f"{len(self.deck)} {self._text('cards_suffix')}"
        self._render_sidebar()
        self._render_main()

    def _load_source_view(self, source_kind: str) -> None:
        source_kind = source_kind.strip().lower()
        self.route = ""
        self.searching = f"source:{source_kind}"
        payload = build_source_view_payload(
            self.repo_root,
            source_kind,
            language=self.language,
        )
        self.deck = payload.get("deck", [])
        self.selected_index = -1
        self._card_selected_by_user = False
        self.hovered_index = -1
        self._route_heading = _source_filter_label(source_kind, self.language)
        self._route_subtitle = f"{len(self.deck)} {self._text('cards_suffix')}"
        self._render_sidebar()
        self._render_main()

    def load_route(self, route: str) -> None:
        self.searching = ""
        self.route = route
        payload = build_route_view_payload(
            self.repo_root,
            route=route,
            language=self.language,
        )
        self.children_by_route[""] = navigation_children(payload)
        if route:
            self.children_by_route.pop(route, None)
        self.expanded_routes.add("")
        self.deck = payload.get("deck", [])
        self.selected_index = -1
        self._card_selected_by_user = False
        self.hovered_index = -1
        self._route_heading = _route_title(route, self.language, self.repo_root)
        self._route_subtitle = self._text("predictive_memory_cards")
        self._render_sidebar()
        self._render_main()

    def _active_package_context(self) -> dict[str, str] | None:
        if self.searching:
            return None
        route = str(self.route or "").strip()
        if not route:
            return {
                "export_mode": "all",
                "project_id": "",
                "attach_project_id": "",
            }
        if route == "uncategorized":
            return {
                "export_mode": "uncategorized",
                "project_id": "",
                "attach_project_id": "",
            }
        if route and route not in {"recent"}:
            return {
                "export_mode": "project",
                "project_id": route,
                "attach_project_id": route,
            }
        return None

    def _export_library_package(self, mode: str, *, project_id: str = "", parent: tk.Misc | None = None) -> None:
        initial = f"logicguard-{project_id or mode}.zip"
        output = filedialog.asksaveasfilename(
            parent=parent or self,
            title=self._text("library_packages"),
            defaultextension=".zip",
            initialfile=initial,
            filetypes=[("LogicGuard package", "*.zip"), ("All files", "*.*")],
        )
        if not output:
            return
        try:
            result = export_library_package(self.repo_root, output, mode=mode, project_id=project_id)
            messagebox.showinfo(
                self._text("package_exported"),
                f"{result.package_path}\nSources: {len(result.source_ids)}\nProjects: {len(result.project_ids)}",
                parent=parent or self,
            )
        except Exception as exc:
            messagebox.showerror(self._text("package_error"), str(exc), parent=parent or self)

    def _import_library_package(
        self,
        *,
        parent: tk.Misc | None = None,
        attach_project_id: str = "",
    ) -> None:
        package = filedialog.askopenfilename(
            parent=parent or self,
            title=self._text("import_package"),
            filetypes=[("LogicGuard package", "*.zip"), ("All files", "*.*")],
        )
        if not package:
            return
        try:
            result = import_library_package(
                self.repo_root,
                package,
                include_package_projects=True,
                attach_project_id=attach_project_id,
            )
            self.load_route(self.route)
            messagebox.showinfo(
                self._text("package_imported"),
                (
                    f"Created sources: {len(result.created_sources)}\n"
                    f"Reused sources: {len(result.reused_sources)}\n"
                    f"Projects: {len(result.created_projects) + len(result.merged_projects)}\n"
                    f"Conflicts: {len(result.conflicts)}"
                ),
                parent=parent or self,
            )
        except Exception as exc:
            messagebox.showerror(self._text("package_error"), str(exc), parent=parent or self)

    def _dissolve_project(self, project_id: str) -> None:
        if not project_id:
            return
        confirmed = messagebox.askyesno(
            self._text("dissolve_project_title"),
            self._text("dissolve_project_confirm").format(project_id=project_id),
            parent=self,
        )
        if not confirmed:
            return
        try:
            from researchguard.logic import SourceLibrary

            SourceLibrary(self.repo_root).delete_project(project_id)
            self.load_route("")
            messagebox.showinfo(self._text("dissolve_project_done"), project_id, parent=self)
        except Exception as exc:
            messagebox.showerror(self._text("package_error"), str(exc), parent=self)

    def _on_main_configure(self, event: tk.Event[Any]) -> None:
        self._main_width = event.width
        self._main_height = event.height
        self._render_main()

    def _render_main(self) -> None:
        self.main.delete("all")
        self._card_surface_photos.clear()
        self.card_hitboxes.clear()
        self.update_badge_hitbox = None
        self.export_badge_hitbox = None
        self.import_badge_hitbox = None
        self.dissolve_project_hitbox = None
        u = self._u
        f = self._f
        width = max(self._main_width, int(self.main.winfo_width()), u(760))
        self.main.create_rectangle(0, 0, width, max(self._main_height, u(680)), fill=BG, outline=BG)

        layout = self._main_grid_layout(width)
        content_left = layout["left"]
        visible_columns = min(layout["columns"], max(len(self.deck), 1))
        visible_grid_width = visible_columns * layout["card_w"] + max(0, visible_columns - 1) * layout["gap"]
        grid_right = content_left + visible_grid_width
        header_right = width - u(MAIN_MARGIN_X)
        header_width = max(visible_grid_width, header_right - content_left)

        count_label = f"{len(self.deck)} {self._text('cards_suffix')}"
        count_w = max(u(92), u(34) + len(count_label) * u(8))
        update_state = load_update_state(self.repo_root)
        update_label = update_badge_label(update_state, self.language)
        update_w = max(u(76), u(34) + len(update_label) * u(8)) if update_label else 0
        package_context = self._active_package_context()
        export_label = self._text("export_scope") if package_context else ""
        import_label = self._text("import_scope") if package_context else ""
        dissolve_label = self._text("dissolve_project") if package_context and package_context.get("project_id") else ""
        export_w = max(u(82), u(44) + len(export_label) * u(9)) if package_context else 0
        import_w = max(u(82), u(44) + len(import_label) * u(9)) if package_context else 0
        dissolve_w = max(u(82), u(44) + len(dissolve_label) * u(9)) if dissolve_label else 0
        badge_gap = u(10)
        badge_widths = [count_w]
        if update_w:
            badge_widths.append(update_w)
        if export_w:
            badge_widths.append(export_w)
        if import_w:
            badge_widths.append(import_w)
        if dissolve_w:
            badge_widths.append(dissolve_w)
        header_badge_width = sum(badge_widths) + badge_gap * max(0, len(badge_widths) - 1)
        title_top = u(34)
        has_count_room = header_width >= max(u(680), header_badge_width + u(320))
        title_right = header_right - header_badge_width - u(28) if has_count_room else header_right
        title_width = max(u(260), title_right - content_left)
        title_item = self.main.create_text(
            content_left,
            title_top,
            text=getattr(self, "_route_heading", self._text("all_cards")),
            anchor="nw",
            fill=TEXT,
            width=title_width,
            font=("Segoe UI", f(21), "bold"),
        )
        title_bbox = self.main.bbox(title_item) or (content_left, title_top, title_right, title_top + u(44))

        badge_y1 = title_top + u(5) if has_count_room else title_bbox[3] + u(8)
        badge_y2 = badge_y1 + u(32)
        badge_x2 = header_right
        dissolve_rect: tuple[int, int, int, int] | None = None
        import_rect: tuple[int, int, int, int] | None = None
        export_rect: tuple[int, int, int, int] | None = None
        update_rect: tuple[int, int, int, int] | None = None
        count_rect: tuple[int, int, int, int] | None = None

        if package_context and dissolve_w:
            dissolve_rect = (badge_x2 - dissolve_w, badge_y1, badge_x2, badge_y2)
            badge_x2 = dissolve_rect[0] - badge_gap
        if package_context and import_w:
            import_rect = (badge_x2 - import_w, badge_y1, badge_x2, badge_y2)
            badge_x2 = import_rect[0] - badge_gap
        if package_context and export_w:
            export_rect = (badge_x2 - export_w, badge_y1, badge_x2, badge_y2)
            badge_x2 = export_rect[0] - badge_gap
        count_rect = (badge_x2 - count_w, badge_y1, badge_x2, badge_y2)
        badge_x2 = count_rect[0] - badge_gap
        if update_label and update_w:
            update_rect = (badge_x2 - update_w, badge_y1, badge_x2, badge_y2)

        if has_count_room:
            pass
        if update_label and update_w and update_rect:
            update_x1, update_y1, update_x2, update_y2 = update_rect
            self._draw_update_badge(
                update_x1,
                update_y1,
                update_x2,
                update_y2,
                update_label,
                update_state,
            )
        count_x1, count_y1, count_x2, count_y2 = count_rect
        self._round_rect(self.main, count_x1, count_y1, count_x2, count_y2, u(16), fill="#f7f7f9", outline=LINE_SOFT)
        self.main.create_text(
            (count_x1 + count_x2) / 2,
            (count_y1 + count_y2) / 2,
            text=count_label,
            fill=MUTED,
            font=self._font(11),
        )
        if package_context and export_rect:
            export_x1, export_y1, export_x2, export_y2 = export_rect
            self._draw_export_badge(
                export_x1,
                export_y1,
                export_x2,
                export_y2,
                export_label,
                str(package_context["export_mode"]),
                str(package_context.get("project_id") or ""),
            )
        if package_context and import_rect:
            import_x1, import_y1, import_x2, import_y2 = import_rect
            self._draw_import_badge(
                import_x1,
                import_y1,
                import_x2,
                import_y2,
                import_label,
                str(package_context.get("attach_project_id") or ""),
            )
        if package_context and dissolve_rect and dissolve_label:
            dissolve_x1, dissolve_y1, dissolve_x2, dissolve_y2 = dissolve_rect
            self._draw_dissolve_project_badge(
                dissolve_x1,
                dissolve_y1,
                dissolve_x2,
                dissolve_y2,
                dissolve_label,
                str(package_context.get("project_id") or ""),
            )

        subtitle_y = max(title_bbox[3] + u(4), count_y2 + u(6) if not has_count_room else u(68))
        subtitle_item = self.main.create_text(
            content_left + 2,
            subtitle_y,
            text=getattr(self, "_route_subtitle", self._text("predictive_memory_cards")),
            anchor="nw",
            fill=MUTED,
            width=max(u(260), header_width),
            font=("Segoe UI", f(12)),
        )
        subtitle_bbox = self.main.bbox(subtitle_item) or (content_left, subtitle_y, header_right, subtitle_y + u(24))
        header_bottom = subtitle_bbox[3] + u(24)

        if self.route:
            route_y1 = subtitle_bbox[3] + u(14)
            route_y2 = route_y1 + u(30)
            self._round_rect(
                self.main,
                content_left,
                route_y1,
                min(header_right, content_left + u(520)),
                route_y2,
                u(15),
                fill="#f6f6f8",
                outline=LINE_SOFT,
            )
            self.main.create_text(
                content_left + u(18),
                (route_y1 + route_y2) / 2,
                text=_route_label(self.route, self.language, self.repo_root),
                anchor="w",
                fill=MUTED,
                width=max(u(220), min(header_width, u(500)) - u(36)),
                font=("Segoe UI", f(12)),
            )
            header_bottom = route_y2 + u(34)

        if not self.deck:
            self.main.create_text(content_left, header_bottom, text=self._text("no_cards"), anchor="nw", fill=MUTED, font=("Segoe UI", f(13)))
            self.main.configure(scrollregion=(0, 0, width, max(self._main_height, u(680))))
            return

        card_w = layout["card_w"]
        card_h = layout["card_h"]
        gap = layout["gap"]
        columns = visible_columns
        start_x = content_left
        start_y = header_bottom

        card_rects: list[tuple[int, dict[str, Any], int, int, int, int]] = []
        for index, card in enumerate(self.deck):
            row = index // columns
            column = index % columns
            x = start_x + column * (card_w + gap)
            y = start_y + row * (card_h + gap)
            card_rects.append((index, card, x, y, card_w, card_h))

        for index, card, x, y, rect_w, rect_h in card_rects:
            if index == self.hovered_index:
                continue
            self._draw_card(index, card, x, y, rect_w, rect_h)

        for index, card, x, y, rect_w, rect_h in card_rects:
            if index != self.hovered_index:
                continue
            lift = u(8)
            self._draw_card(index, card, x - lift, y - lift, rect_w + lift * 2, rect_h + lift * 2, hovered=True)
            break

        rows = (len(self.deck) + columns - 1) // columns
        total_h = start_y + rows * (card_h + gap) + u(42)
        self.main.configure(scrollregion=(0, 0, width, max(total_h, self._main_height)))

    def _draw_update_badge(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        label: str,
        state: dict[str, Any],
    ) -> None:
        if x2 <= x1 or y2 <= y1:
            return
        u = self._u
        status = str(state.get("status") or "")
        if status == "available":
            fill, outline, text_fill = ACCENT, ACCENT, "#ffffff"
        elif status == "prepared":
            fill, outline, text_fill = ACCENT_SOFT, ACCENT_LINE, ACCENT_DARK
        elif status == "upgrading":
            fill, outline, text_fill = "#171717", "#171717", "#ffffff"
        elif status == "failed":
            fill, outline, text_fill = "#fff1e6", "#e36414", "#a54000"
        else:
            fill, outline, text_fill = BG, LINE_SOFT, MUTED
        radius = u(16)
        self._round_rect(self.main, x1, y1, x2, y2, radius, fill=fill, outline=outline)
        self.main.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=label,
            fill=text_fill,
            font=self._font(11),
        )
        if update_badge_clickable(state):
            self.update_badge_hitbox = (x1, y1, x2, y2)

    def _draw_export_badge(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        label: str,
        mode: str,
        project_id: str,
    ) -> None:
        if x2 <= x1 or y2 <= y1:
            return
        u = self._u
        self._round_rect(self.main, x1, y1, x2, y2, u(16), fill=ACCENT_SOFT, outline=ACCENT_LINE)
        icon_x = x1 + u(18)
        icon_y = (y1 + y2) / 2
        self.main.create_text(icon_x, icon_y, text=EXPORT_PACKAGE_ICON, fill=ACCENT_DARK, font=self._icon_font(16))
        self.main.create_text(
            (x1 + x2) / 2 + u(8),
            (y1 + y2) / 2,
            text=label,
            fill=ACCENT_DARK,
            font=self._font(11),
        )
        self.export_badge_hitbox = (x1, y1, x2, y2, mode, project_id)

    def _draw_import_badge(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        label: str,
        attach_project_id: str,
    ) -> None:
        if x2 <= x1 or y2 <= y1:
            return
        u = self._u
        self._round_rect(self.main, x1, y1, x2, y2, u(16), fill="#f7f7f9", outline=LINE_SOFT)
        icon_x = x1 + u(18)
        icon_y = (y1 + y2) / 2
        self.main.create_text(icon_x, icon_y, text=IMPORT_PACKAGE_ICON, fill=ACCENT_DARK, font=self._icon_font(16))
        self.main.create_text(
            (x1 + x2) / 2 + u(8),
            (y1 + y2) / 2,
            text=label,
            fill=ACCENT_DARK,
            font=self._font(11),
        )
        self.import_badge_hitbox = (x1, y1, x2, y2, attach_project_id)

    def _draw_dissolve_project_badge(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        label: str,
        project_id: str,
    ) -> None:
        if x2 <= x1 or y2 <= y1:
            return
        u = self._u
        fill = "#fff7ed"
        outline = "#fed7aa"
        text_fill = "#a54000"
        self._round_rect(self.main, x1, y1, x2, y2, u(16), fill=fill, outline=outline)
        icon_x = x1 + u(18)
        icon_y = (y1 + y2) / 2
        self.main.create_line(icon_x - u(7), icon_y, icon_x - u(2), icon_y, fill=text_fill, width=max(1, u(2)))
        self.main.create_line(icon_x + u(3), icon_y, icon_x + u(8), icon_y, fill=text_fill, width=max(1, u(2)))
        self.main.create_line(icon_x - u(1), icon_y - u(5), icon_x + u(2), icon_y + u(5), fill=text_fill, width=max(1, u(2)))
        self.main.create_text(
            (x1 + x2) / 2 + u(8),
            (y1 + y2) / 2,
            text=label,
            fill=text_fill,
            font=self._font(11),
        )
        self.dissolve_project_hitbox = (x1, y1, x2, y2, project_id)

    def _main_grid_layout(self, width: int) -> dict[str, int]:
        u = self._u
        usable_width = max(u(360), width - u(MAIN_MARGIN_X) * 2)
        if usable_width >= u(1440):
            columns = 5
        elif usable_width >= u(1040):
            columns = 4
        elif usable_width >= u(720):
            columns = 3
        elif usable_width >= u(520):
            columns = 2
        else:
            columns = 1
        columns = min(MAIN_MAX_COLUMNS, columns)
        gap = u(18) if columns > 1 else 0
        card_w = min(u(320), max(u(218), (usable_width - gap * (columns - 1)) // columns))
        card_h = int(card_w * 0.64)
        grid_width = columns * card_w + (columns - 1) * gap
        left = u(MAIN_MARGIN_X)
        return {
            "left": left,
            "columns": columns,
            "gap": gap,
            "card_w": card_w,
            "card_h": card_h,
            "grid_width": grid_width,
        }

    def _draw_card(self, index: int, card: dict[str, Any], x: int, y: int, width: int, height: int, *, hovered: bool = False) -> None:
        u = self._u
        f = self._f
        palette = _palette(card)

        self._draw_card_surface(x, y, width, height, u(15), palette, hovered=hovered)

        type_label = _card_type_label(card, self.language)
        type_w = min(width - u(138), max(u(58), u(16) + len(type_label) * u(6)))
        self._round_rect(
            self.main,
            x + u(16),
            y + u(16),
            x + u(16) + type_w,
            y + u(31),
            u(8),
            fill=_blend_hex(palette.get("soft", palette["fill"]), palette["fill"], 0.22),
        )
        self.main.create_text(
            x + u(16) + type_w / 2,
            y + u(23),
            text=type_label,
            fill=palette["muted"],
            font=("Segoe UI", f(6), "bold"),
        )
        skill_label = _skill_badge_label(card, self.language)
        if skill_label:
            skill_x1 = x + u(16) + type_w + u(7)
            skill_x2_limit = x + width - u(116)
            skill_w = min(max(u(50), u(18) + len(skill_label) * u(6)), max(0, skill_x2_limit - skill_x1))
            if skill_w >= u(42):
                self._round_rect(
                    self.main,
                    skill_x1,
                    y + u(16),
                    skill_x1 + skill_w,
                    y + u(31),
                    u(8),
                    fill=_blend_hex(palette.get("soft", palette["fill"]), "#ffffff", 0.18),
                    outline=_blend_hex(palette["muted"], palette["fill"], 0.42),
                )
                self.main.create_text(
                    skill_x1 + skill_w / 2,
                    y + u(23),
                    text=skill_label,
                    fill=palette["muted"],
                    font=("Segoe UI", f(6), "bold"),
                )
        title = _cover_title(card, self.language)
        title_step = max(u(20), min(u(26), width // 16))
        title_y = y + u(58)
        title_lines = _text_lines(title, 22, 2)
        title_icon_r = max(u(12), min(u(16), int(title_step * 0.68)))
        title_icon_cx = x + u(32)
        title_icon_cy = title_y + max(u(12), int(title_step * (0.9 if len(title_lines) > 1 else 0.52)))
        self.main.create_oval(
            title_icon_cx - title_icon_r,
            title_icon_cy - title_icon_r,
            title_icon_cx + title_icon_r,
            title_icon_cy + title_icon_r,
            outline=palette["deep"],
            width=max(2, u(3)),
        )
        title_left = x + u(54)
        for line_index, line in enumerate(title_lines):
            self.main.create_text(
                title_left,
                title_y + line_index * title_step,
                text=line,
                anchor="nw",
                fill=palette["deep"],
                width=width - u(76),
                font=self._font(13, "bold"),
            )

        footer_y = y + height - u(48)
        body = _short_text(card.get("predicted_result") or card.get("guidance"), 56)
        body_step = max(u(16), min(u(20), width // 28))
        title_block_bottom = title_y + len(title_lines) * title_step
        body_top = title_block_bottom + u(16)
        body_bottom = footer_y - u(26)
        available_body_lines = max(0, min(2, (body_bottom - body_top) // body_step))
        if available_body_lines:
            body_y = body_top
            for line_index, line in enumerate(_text_lines(body, 38, available_body_lines)):
                self.main.create_text(
                    x + u(22),
                    body_y + line_index * body_step,
                    text=line,
                    anchor="nw",
                    fill=palette["deep"],
                    width=width - u(44),
                    font=self._font(10),
                )

        status = _modeling_status_label(card, self.language)
        project_label = _detail_header_project_label(card, self.language)
        self.main.create_line(x + u(18), footer_y, x + width - u(18), footer_y, fill=palette["line"])
        pill_w = min(width - u(142), max(u(70), u(30) + len(status) * u(7)))
        self._round_rect(self.main, x + u(18), y + height - u(36), x + u(18) + pill_w, y + height - u(16), u(10), fill=palette["pill"])
        self.main.create_text(
            x + u(18) + pill_w / 2,
            y + height - u(26),
            text=status,
            fill=palette["pill_text"],
            font=("Segoe UI", f(8), "bold"),
        )
        self.main.create_text(
            x + width - u(18),
            y + height - u(26),
            text=_short_text(project_label, 18 if width >= u(310) else 12),
            anchor="e",
            fill=palette["muted"],
            font=("Segoe UI", f(8)),
        )
        self.card_hitboxes.append((x, y, x + width, y + height, index))

    def _on_mousewheel(self, event: tk.Event[Any]) -> None:
        self.main.yview_scroll(_wheel_scroll_units(event.delta, multiplier=MAIN_WHEEL_SCROLL_UNITS), "units")

    def _on_sidebar_mousewheel(self, event: tk.Event[Any]) -> None:
        self.sidebar.yview_scroll(_wheel_scroll_units(event.delta), "units")

    def _hit_card(self, event: tk.Event[Any]) -> int | None:
        x = int(self.main.canvasx(event.x))
        y = int(self.main.canvasy(event.y))
        for left, top, right, bottom, index in reversed(self.card_hitboxes):
            if left <= x <= right and top <= y <= bottom:
                return index
        return None

    def _on_card_motion(self, event: tk.Event[Any]) -> None:
        if (
            self._hit_update_badge(event)
            or self._hit_export_badge(event)
            or self._hit_import_badge(event)
            or self._hit_dissolve_project_badge(event)
        ):
            if self.main.cget("cursor") != "hand2":
                self.main.configure(cursor="hand2")
            return
        index = self._hit_card(event)
        if index != self.hovered_index:
            self.hovered_index = -1 if index is None else index
            self._render_main()
        cursor = "hand2" if index is not None else ""
        if self.main.cget("cursor") != cursor:
            self.main.configure(cursor=cursor)

    def _on_card_leave(self, _event: tk.Event[Any]) -> None:
        if self.hovered_index >= 0:
            self.hovered_index = -1
            self._render_main()
        if self.main.cget("cursor"):
            self.main.configure(cursor="")

    def _on_card_click(self, event: tk.Event[Any]) -> None:
        if self._hit_update_badge(event):
            self._toggle_update_request()
            return
        export_hit = self._hit_export_badge(event)
        if export_hit is not None:
            mode, project_id = export_hit
            self._export_library_package(mode, project_id=project_id)
            return
        attach_project_id = self._hit_import_badge(event)
        if attach_project_id is not None:
            self._import_library_package(attach_project_id=attach_project_id)
            return
        dissolve_project_id = self._hit_dissolve_project_badge(event)
        if dissolve_project_id is not None:
            self._dissolve_project(dissolve_project_id)
            return
        index = self._hit_card(event)
        if index is None:
            return
        self.selected_index = index
        self._card_selected_by_user = True
        self.hovered_index = index
        self.open_selected_detail()

    def _hit_update_badge(self, event: tk.Event[Any]) -> bool:
        if self.update_badge_hitbox is None:
            return False
        x = int(self.main.canvasx(event.x))
        y = int(self.main.canvasy(event.y))
        x1, y1, x2, y2 = self.update_badge_hitbox
        return x1 <= x <= x2 and y1 <= y <= y2

    def _hit_export_badge(self, event: tk.Event[Any]) -> tuple[str, str] | None:
        if self.export_badge_hitbox is None:
            return None
        x = int(self.main.canvasx(event.x))
        y = int(self.main.canvasy(event.y))
        x1, y1, x2, y2, mode, project_id = self.export_badge_hitbox
        if x1 <= x <= x2 and y1 <= y <= y2:
            return mode, project_id
        return None

    def _hit_import_badge(self, event: tk.Event[Any]) -> str | None:
        if self.import_badge_hitbox is None:
            return None
        x = int(self.main.canvasx(event.x))
        y = int(self.main.canvasy(event.y))
        x1, y1, x2, y2, attach_project_id = self.import_badge_hitbox
        if x1 <= x <= x2 and y1 <= y <= y2:
            return attach_project_id
        return None

    def _hit_dissolve_project_badge(self, event: tk.Event[Any]) -> str | None:
        if self.dissolve_project_hitbox is None:
            return None
        x = int(self.main.canvasx(event.x))
        y = int(self.main.canvasy(event.y))
        x1, y1, x2, y2, project_id = self.dissolve_project_hitbox
        if x1 <= x <= x2 and y1 <= y <= y2:
            return project_id
        return None

    def _toggle_update_request(self) -> None:
        state = load_update_state(self.repo_root)
        requested = str(state.get("status") or "") != "prepared"
        set_update_request(self.repo_root, requested)
        self._render_main()

    def _move_selection(self, delta: int) -> None:
        if not self.deck:
            return
        if self.selected_index < 0:
            self.selected_index = 0
        self.selected_index = (self.selected_index + delta) % len(self.deck)
        self._card_selected_by_user = True
        self.hovered_index = self.selected_index
        self._render_main()

    def open_selected_detail(self) -> None:
        if self.selected_index < 0 or self.selected_index >= len(self.deck):
            if self.deck:
                self.selected_index = 0
            else:
                return
        self._card_selected_by_user = True
        summary = self.deck[self.selected_index]
        summary_source = summary.get("source_info") if isinstance(summary.get("source_info"), dict) else None
        detail = build_card_detail_payload(
            self.repo_root,
            str(summary.get("id")),
            language=self.language,
            source_info=summary_source,
        )
        if detail is None:
            return
        self._open_detail_window({**detail, "route_reason": summary.get("route_reason")})

    def _open_detail_window(self, card: dict[str, Any]) -> None:
        u = self._u
        f = self._f
        window = tk.Toplevel(self)
        window.title(str(card.get("title") or card.get("id") or "Card"))
        window.geometry(f"{u(940)}x{u(720)}")
        window.minsize(u(760), u(560))
        window.configure(bg="#f7f7f9")
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(2, weight=1)

        header_canvas = tk.Canvas(window, height=u(222), bg="#f7f7f9", highlightthickness=0)
        header_canvas.grid(row=0, column=0, sticky="ew", padx=u(28), pady=(u(24), 0))

        def render_header(event: tk.Event[Any] | None = None) -> None:
            header_canvas.delete("all")
            canvas_width = int(event.width if event else header_canvas.winfo_width()) or u(860)
            palette = _palette(card)
            banner_h = u(210)
            drawer_y = banner_h - u(14)
            header_canvas.create_rectangle(0, drawer_y, canvas_width, u(222), fill=BG, outline=BG)
            self._draw_gradient_surface(header_canvas, 0, 0, canvas_width, banner_h, u(26), palette)
            header_canvas.create_text(
                u(32),
                u(28),
                text=_card_type_label(card, self.language),
                anchor="nw",
                fill=palette["muted"],
                font=("Segoe UI", f(12), "bold"),
            )

            title_y = u(58)
            title_icon_r = max(u(12), min(u(17), f(15)))
            title_icon_cx = u(51)
            title_icon_cy = title_y + u(25)
            header_canvas.create_oval(
                title_icon_cx - title_icon_r,
                title_icon_cy - title_icon_r,
                title_icon_cx + title_icon_r,
                title_icon_cy + title_icon_r,
                outline=palette["deep"],
                width=max(2, u(3)),
            )
            header_canvas.create_text(
                u(82),
                title_y,
                text=str(card.get("title") or card.get("id") or ""),
                anchor="nw",
                fill=palette["deep"],
                width=max(u(420), canvas_width - u(128)),
                font=("Segoe UI", f(23), "bold"),
            )
            meta = _detail_header_meta_line(card, self.language)
            pill_font = tkfont.Font(family="Segoe UI", size=f(10), weight="bold")
            max_pill_width = max(u(128), canvas_width - u(64))
            max_text_width = max(u(96), max_pill_width - u(40))
            fitted_meta = _fit_text_to_width(meta, pill_font, max_text_width)
            pill_width = min(max_pill_width, max(u(160), pill_font.measure(fitted_meta) + u(40)))
            pill_right = u(32) + pill_width
            self._round_rect(header_canvas, u(32), banner_h - u(44), pill_right, banner_h - u(18), u(13), fill=palette["pill"])
            header_canvas.create_text(
                u(52),
                banner_h - u(31),
                text=fitted_meta,
                anchor="w",
                fill=palette["pill_text"],
                font=("Segoe UI", f(10), "bold"),
            )

        header_canvas.bind("<Configure>", render_header)

        body_shell = tk.Frame(window, bg="#f7f7f9")
        body_shell.grid(row=2, column=0, sticky="nsew", padx=u(28), pady=(0, u(24)))
        body_shell.grid_columnconfigure(0, weight=1)
        body_shell.grid_rowconfigure(0, weight=1)
        graph = card.get("graph") if isinstance(card.get("graph"), dict) else {}
        if graph:
            self._insert_graph_detail(body_shell, card, graph)
            window.focus_set()
            return
        text = tk.Text(
            body_shell,
            bg=BG,
            fg=TEXT,
            relief="flat",
            wrap="word",
            padx=u(32),
            pady=u(24),
            font=("Segoe UI", f(15)),
            insertbackground=TEXT,
        )
        text.grid(row=0, column=0, sticky="nsew")
        detail_scroll = tk.Scrollbar(body_shell, orient="vertical", command=text.yview, width=u(8))
        detail_scroll.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=detail_scroll.set)
        text.tag_configure("heading", foreground=TEXT, font=("Segoe UI", f(15), "bold"), spacing1=u(10), spacing3=u(4))
        text.tag_configure("body", foreground=TEXT, font=("Segoe UI", f(15)), spacing3=u(8))
        text.tag_configure("muted", foreground=MUTED, font=("Segoe UI", f(13)))
        text.tag_configure("mono", foreground=MUTED, font=("Consolas", f(12)))

        self._insert_detail_section(text, self._text("if"), card.get("if"))
        self._insert_detail_section(text, self._text("action"), card.get("action"))
        self._insert_detail_section(text, self._text("predict"), card.get("predict"))
        self._insert_detail_section(text, self._text("use"), card.get("use"))
        text.insert("end", f"{self._text('routes_section')}\n", "heading")
        cross_routes = [_route_label(route, self.language, self.repo_root) for route in card.get("cross_index") or []]
        text.insert("end", f"{self._text('primary')}: {_route_label(card.get('domain_path'), self.language, self.repo_root)}\n")
        text.insert("end", f"{self._text('also')}: {'; '.join(cross_routes) or '-'}\n")
        text.insert("end", f"{self._text('related')}: {'; '.join(card.get('related_cards') or []) or '-'}\n\n")
        if self._should_show_source_metadata(card):
            text.insert("end", f"{self._text('source')}\n", "heading")
            source_line = _source_line(card, self.language)
            text.insert("end", f"{source_line or '-'}\n", "muted")
            text.insert("end", f"{self._text('temporal_clues')}\n", "heading")
            for line in _temporal_detail_lines(card, self.language):
                text.insert("end", f"{line}\n", "muted")
            text.insert(
                "end",
                f"{self._text('author')}: "
                f"{_author_display_label(card.get('author_label'), self.language) or '-'}\n",
                "muted",
            )
            text.insert("end", f"{card.get('path') or ''}\n\n", "mono")
        skill_dependencies = card.get("skill_dependencies") or []
        if skill_dependencies:
            text.insert("end", f"{self._text('skill_dependencies')}\n", "heading")
            for dependency in skill_dependencies:
                if not isinstance(dependency, dict):
                    continue
                skill_id = str(dependency.get("id") or "").strip()
                requirement = str(dependency.get("requirement") or "").strip()
                registry_status = str(dependency.get("registry_status") or "missing").strip()
                version = str(dependency.get("registry_version") or "").strip()
                auto_install = dependency.get("auto_install") if isinstance(dependency.get("auto_install"), dict) else {}
                eligible = bool(auto_install.get("eligible"))
                auto_label = self._text("eligible") if eligible else self._text("not_eligible")
                registry_label = registry_status if not version else f"{registry_status} {version}"
                text.insert(
                    "end",
                    f"{skill_id} · {requirement} · {self._text('registry_status')}: {registry_label} · "
                    f"{self._text('auto_install')}: {auto_label}\n",
                    "muted",
                )
            text.insert("end", "\n")
        history = card.get("recent_history") or []
        if history:
            text.insert("end", f"{self._text('recent_history')}\n", "heading")
            for event in history[:4]:
                created_at = str(event.get("created_at") or "")
                summary = normalize_text(event.get("task_summary") or event.get("rationale") or "-")
                text.insert("end", f"{created_at} · {summary}\n", "muted")
            text.insert("end", "\n")
        text.configure(state="disabled")
        window.focus_set()

    def _insert_graph_detail(self, body_shell: tk.Frame, card: dict[str, Any], graph: dict[str, Any]) -> None:
        u = self._u
        f = self._f
        body_shell.grid_columnconfigure(0, weight=4)
        body_shell.grid_columnconfigure(1, weight=1)
        body_shell.grid_rowconfigure(0, weight=1)
        graph_views = graph.get("views") if isinstance(graph.get("views"), dict) else {}
        active_view = self._recommended_graph_view_id(graph, graph_views)

        graph_shell = tk.Frame(body_shell, bg=BG)
        graph_shell.grid(row=0, column=0, sticky="nsew", padx=(0, u(16)))
        graph_shell.grid_columnconfigure(0, weight=1)
        graph_shell.grid_rowconfigure(0, weight=1)

        graph_canvas = tk.Canvas(graph_shell, bg=BG, highlightthickness=1, highlightbackground=LINE)
        graph_canvas.grid(row=0, column=0, sticky="nsew")
        reset_label = self._text("reset_graph")
        reset_font = tkfont.Font(family="Segoe UI", size=f(9), weight="bold")
        reset_w = min(max(u(94), reset_font.measure(reset_label) + u(34)), u(156))
        reset_h = u(32)
        reset_button = tk.Canvas(
            graph_canvas,
            width=reset_w,
            height=reset_h,
            bg=BG,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            takefocus=1,
        )

        def draw_reset_button(hovered: bool = False, pressed: bool = False) -> None:
            reset_button.delete("all")
            fill = "#def7fb" if pressed else "#ecfeff" if hovered else "#ffffff"
            outline = ACCENT if hovered or pressed else "#cbd5e1"
            text_fill = ACCENT_DARK if hovered or pressed else TEXT
            self._round_rect(
                reset_button,
                1,
                1,
                reset_w - 2,
                reset_h - 2,
                reset_h // 2,
                fill=fill,
                outline=outline,
                width=max(1, u(1)),
            )
            reset_button.create_text(
                reset_w // 2,
                reset_h // 2,
                text=reset_label,
                fill=text_fill,
                font=reset_font,
                anchor="center",
            )

        draw_reset_button()

        reset_button.bind("<Enter>", lambda _event: (draw_reset_button(True), "break")[1])
        reset_button.bind("<Leave>", lambda _event: (draw_reset_button(False), "break")[1])
        reset_button.bind("<ButtonPress-1>", lambda _event: (draw_reset_button(True, True), "break")[1])
        hint_label = tk.Label(
            graph_canvas,
            text=self._text("graph_interaction_hint"),
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", f(9)),
        )
        side = tk.Text(
            body_shell,
            width=30,
            bg=BG,
            fg=TEXT,
            relief="flat",
            wrap="word",
            padx=u(18),
            pady=u(16),
            font=("Segoe UI", f(12)),
            insertbackground=TEXT,
        )
        side.grid(row=0, column=1, sticky="nsew")
        side.tag_configure("heading", foreground=TEXT, font=("Segoe UI", f(13), "bold"), spacing1=u(8), spacing3=u(4))
        side.tag_configure("body", foreground=TEXT, font=("Segoe UI", f(12)), spacing3=u(8))
        side.tag_configure("muted", foreground=MUTED, font=("Segoe UI", f(11)))
        side.insert("end", f"{self._text('source')}\n", "heading")
        side.insert("end", f"{card.get('title') or card.get('id')}\n", "body")
        side.insert("end", f"{card.get('path') or ''}\n\n", "muted")
        side.insert("end", f"{self._text('status')}\n", "heading")
        side.insert("end", f"{_modeling_status_label(card, self.language)}\n", "body")
        if _boundary_note_count(card):
            boundary_note = "包含边界条件说明" if self.language == ZH_CN else "Contains boundary notes"
            side.insert("end", f"{boundary_note}\n", "muted")
        side.insert("end", f"{self._text('type')}: {_card_type_label(card, self.language)}\n", "body")
        source_card = card.get("library_card") if isinstance(card.get("library_card"), dict) else {}
        project_ids = card.get("project_ids") or source_card.get("project_ids") or []
        if project_ids:
            project_prefix = "项目" if self.language == ZH_CN else "Projects"
            side.insert("end", f"{project_prefix}: {', '.join(str(item) for item in project_ids)}\n", "muted")
        else:
            side.insert("end", "项目：未归入项目\n" if self.language == ZH_CN else "Projects: No project\n", "muted")
        side.insert("end", f"\n{self._text('temporal_clues')}\n", "heading")
        for line in _temporal_detail_lines(card, self.language):
            side.insert("end", f"{line}\n", "muted")
        side.insert("end", "\n", "muted")
        node_label = "模型节点" if self.language == ZH_CN else "Model nodes"
        side.insert("end", f"{node_label}: {source_card.get('logic_node_count', len(graph.get('nodes', [])))}\n\n", "muted")
        side.insert("end", f"{self._text('recommended_graph')}\n", "heading")
        if graph.get("modeled"):
            active_view_meta = graph_views.get(active_view, {}) if isinstance(graph_views.get(active_view), dict) else {}
            active_label = str(active_view_meta.get("label") or self._text(active_view))
            active_description = str(active_view_meta.get("description") or "")
            recommendation_reason = str(graph.get("recommendation_reason") or active_description)
            side.insert("end", f"{active_label}\n", "body")
            if recommendation_reason:
                side.insert("end", f"{recommendation_reason}\n", "muted")
        else:
            side.insert("end", "This source does not have a model yet.\n", "body")
        side.configure(state="disabled")

        graph_state: dict[str, Any] = {
            "initialized": False,
            "scale": 1.0,
            "offset_x": 0.0,
            "offset_y": 0.0,
            "drag_x": 0,
            "drag_y": 0,
            "canvas_width": 0,
            "canvas_height": 0,
            "user_adjusted": False,
        }

        def reset_graph_view() -> None:
            graph_state["initialized"] = False
            graph_state["user_adjusted"] = False
            render()

        reset_button.bind("<ButtonRelease-1>", lambda _event: (draw_reset_button(True), reset_graph_view(), "break")[2])
        reset_button.bind("<Return>", lambda _event: (reset_graph_view(), "break")[1])
        reset_button.bind("<space>", lambda _event: (reset_graph_view(), "break")[1])

        def render(event: tk.Event[Any] | None = None) -> None:
            graph_canvas.delete("all")
            canvas_width = int(event.width if event else graph_canvas.winfo_width()) or u(680)
            canvas_height = int(event.height if event else graph_canvas.winfo_height()) or u(420)
            reset_button.place(relx=1.0, x=-u(14), y=u(14), width=reset_w, height=reset_h, anchor="ne")
            hint_label.place(relx=1.0, x=-u(14), y=u(54), anchor="ne")
            if not graph_state.get("user_adjusted"):
                last_width = int(graph_state.get("canvas_width", 0))
                last_height = int(graph_state.get("canvas_height", 0))
                if abs(canvas_width - last_width) > 2 or abs(canvas_height - last_height) > 2:
                    graph_state["initialized"] = False
                graph_state["canvas_width"] = canvas_width
                graph_state["canvas_height"] = canvas_height
            self._draw_logic_graph(
                graph_canvas,
                graph,
                canvas_width,
                canvas_height,
                view_mode=active_view,
                view_state=graph_state,
            )

        def on_pan_start(event: tk.Event[Any]) -> str:
            graph_state["drag_x"] = int(event.x)
            graph_state["drag_y"] = int(event.y)
            graph_canvas.configure(cursor="fleur")
            return "break"

        def on_pan_move(event: tk.Event[Any]) -> str:
            last_x = int(graph_state.get("drag_x", event.x))
            last_y = int(graph_state.get("drag_y", event.y))
            graph_state["offset_x"] = float(graph_state.get("offset_x", 0.0)) + int(event.x) - last_x
            graph_state["offset_y"] = float(graph_state.get("offset_y", 0.0)) + int(event.y) - last_y
            graph_state["drag_x"] = int(event.x)
            graph_state["drag_y"] = int(event.y)
            graph_state["user_adjusted"] = True
            render()
            return "break"

        def on_pan_end(_event: tk.Event[Any]) -> str:
            graph_canvas.configure(cursor="")
            return "break"

        def on_zoom(event: tk.Event[Any]) -> str:
            delta = getattr(event, "delta", 0)
            steps = max(1, min(6, abs(int(delta)) // 120)) if delta else 1
            factor = 1.12 ** steps if delta > 0 else (1 / 1.12) ** steps
            if delta == 0:
                factor = 1.12 if getattr(event, "num", 0) == 4 else 1 / 1.12
            old_scale = float(graph_state.get("scale", 1.0))
            new_scale = max(0.35, min(2.8, old_scale * factor))
            if abs(new_scale - old_scale) < 0.001:
                return "break"
            offset_x = float(graph_state.get("offset_x", 0.0))
            offset_y = float(graph_state.get("offset_y", 0.0))
            logical_x = (int(event.x) - offset_x) / old_scale
            logical_y = (int(event.y) - offset_y) / old_scale
            graph_state["scale"] = new_scale
            graph_state["offset_x"] = int(event.x) - logical_x * new_scale
            graph_state["offset_y"] = int(event.y) - logical_y * new_scale
            graph_state["initialized"] = True
            graph_state["user_adjusted"] = True
            render()
            return "break"

        graph_canvas.bind("<Configure>", render)
        graph_canvas.bind("<ButtonPress-1>", on_pan_start)
        graph_canvas.bind("<B1-Motion>", on_pan_move)
        graph_canvas.bind("<ButtonRelease-1>", on_pan_end)
        graph_canvas.bind("<MouseWheel>", on_zoom)
        graph_canvas.bind("<Button-4>", on_zoom)
        graph_canvas.bind("<Button-5>", on_zoom)
        graph_canvas.bind("<Double-Button-1>", lambda _event: (reset_graph_view(), "break")[1])

    def _recommended_graph_view_id(self, graph: dict[str, Any], graph_views: dict[str, Any]) -> str:
        candidates = (
            str(graph.get("recommended_view") or ""),
            str(graph.get("preferred_view") or ""),
            str(graph.get("active_view") or ""),
            "research_flow",
            "argument_map",
        )
        for view_id in candidates:
            if view_id and isinstance(graph_views.get(view_id), dict):
                return view_id
        return "research_flow"

    def _draw_logic_graph(
        self,
        canvas: tk.Canvas,
        graph: dict[str, Any],
        width: int,
        height: int,
        *,
        view_mode: str = "argument_map",
        view_state: dict[str, Any] | None = None,
    ) -> None:
        u = self._u
        f = self._f
        canvas.create_rectangle(0, 0, width, height, fill=BG, outline=BG)
        if not graph.get("modeled"):
            canvas.create_text(
                width // 2,
                height // 2,
                text="No source model yet",
                fill=MUTED,
                font=("Segoe UI", f(16), "bold"),
            )
            return
        nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
        visible, edges = self._graph_view_data(graph, nodes, view_mode)
        if not visible:
            canvas.create_text(width // 2, height // 2, text="No graph nodes", fill=MUTED, font=("Segoe UI", f(14)))
            return
        views = graph.get("views") if isinstance(graph.get("views"), dict) else {}
        view = views.get(view_mode) if isinstance(views.get(view_mode), dict) else {}
        if view.get("diagram_kind") == "process_timeline":
            self._draw_process_timeline(canvas, visible, width, height, view_state=view_state)
            return
        sizes = {str(node.get("id") or ""): self._graph_node_size(node) for node in visible}
        natural_width, natural_height = self._graph_natural_size(visible, width, height, sizes=sizes, flow=view_mode == "research_flow")
        coords = self._layout_graph_nodes(visible, natural_width, natural_height, sizes=sizes, flow=view_mode == "research_flow")
        graph_bbox = self._graph_layout_bbox(coords, sizes)
        scale, offset_x, offset_y = self._graph_transform(view_state, graph_bbox, width, height)

        def transform_x(value: float) -> int:
            return int(round(offset_x + value * scale))

        def transform_y(value: float) -> int:
            return int(round(offset_y + value * scale))

        for edge in edges:
            source = str(edge.get("source") or "")
            target = str(edge.get("target") or "")
            if source not in coords or target not in coords:
                continue
            sx, sy = coords[source]
            target_x, target_y = coords[target]
            color = ACCENT if edge.get("type") == "research_flow" else ("#d8585e" if edge.get("markers", {}).get("risk") else "#9aa4b2")
            line_width = max(1, int(round((u(3) if edge.get("markers", {}).get("important") else u(2)) * scale)))
            canvas.create_line(
                transform_x(sx),
                transform_y(sy),
                transform_x(target_x),
                transform_y(target_y),
                fill=color,
                width=line_width,
                arrow="last",
                smooth=True,
            )
        for node in visible:
            node_id = str(node.get("id") or "")
            cx, cy = coords[node_id]
            self._draw_graph_node(canvas, node, transform_x(cx), transform_y(cy), size=sizes[node_id], scale=scale)

    def _graph_view_data(self, graph: dict[str, Any], nodes: list[dict[str, Any]], view_mode: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        views = graph.get("views") if isinstance(graph.get("views"), dict) else {}
        view = views.get(view_mode) if isinstance(views.get(view_mode), dict) else {}
        if view:
            ids = [str(item) for item in view.get("nodes", []) or []]
            by_id = {str(node.get("id") or ""): node for node in nodes}
            visible = [by_id[node_id] for node_id in ids if node_id in by_id]
            edges = [edge for edge in view.get("edges", []) or [] if isinstance(edge, dict)]
            if view_mode == "research_flow":
                return visible[:18], edges
            return self._visible_graph_nodes(visible, edges, str(graph.get("root_claim") or "")), edges
        edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
        return self._visible_graph_nodes(nodes, edges, str(graph.get("root_claim") or "")), edges

    def _draw_process_timeline(
        self,
        canvas: tk.Canvas,
        nodes: list[dict[str, Any]],
        width: int,
        height: int,
        *,
        view_state: dict[str, Any] | None = None,
    ) -> None:
        u = self._u
        sizes = {str(node.get("id") or ""): self._timeline_node_size(node) for node in nodes}
        natural_width, natural_height = self._timeline_natural_size(nodes, width, height, sizes=sizes)
        coords, spine_x = self._layout_timeline_nodes(nodes, natural_width, natural_height, sizes=sizes)
        bbox = self._graph_layout_bbox(coords, sizes)
        bbox = (min(bbox[0], spine_x - u(18)), bbox[1], bbox[2], bbox[3])
        scale, offset_x, offset_y = self._graph_transform(view_state, bbox, width, height)

        def tx(value: float) -> int:
            return int(round(offset_x + value * scale))

        def ty(value: float) -> int:
            return int(round(offset_y + value * scale))

        if len(nodes) > 1:
            first_y = coords[str(nodes[0].get("id") or "")][1]
            last_y = coords[str(nodes[-1].get("id") or "")][1]
            canvas.create_line(
                tx(spine_x),
                ty(first_y),
                tx(spine_x),
                ty(last_y),
                fill="#d1d5db",
                width=max(1, int(round(u(2) * scale))),
            )
        for node in nodes:
            node_id = str(node.get("id") or "")
            cx, cy = coords[node_id]
            node_w, _node_h = sizes[node_id]
            left = cx - node_w / 2
            color = self._graph_node_color(node)
            canvas.create_line(
                tx(spine_x),
                ty(cy),
                tx(left - u(10)),
                ty(cy),
                fill=color,
                width=max(1, int(round(u(2) * scale))),
            )
            dot = max(4, int(round(u(6) * scale)))
            canvas.create_oval(
                tx(spine_x) - dot,
                ty(cy) - dot,
                tx(spine_x) + dot,
                ty(cy) + dot,
                fill=color,
                outline="#ffffff",
                width=max(1, int(round(u(2) * scale))),
            )
        for node in nodes:
            node_id = str(node.get("id") or "")
            cx, cy = coords[node_id]
            self._draw_timeline_node(canvas, node, tx(cx), ty(cy), size=sizes[node_id], scale=scale)

    def _timeline_natural_size(
        self,
        nodes: list[dict[str, Any]],
        width: int,
        height: int,
        *,
        sizes: dict[str, tuple[int, int]],
    ) -> tuple[int, int]:
        u = self._u
        max_card_width = max((size[0] for size in sizes.values()), default=u(520))
        total_height = sum((sizes.get(str(node.get("id") or ""), (u(520), u(96)))[1] for node in nodes), u(80))
        total_height += u(30) * max(0, len(nodes) - 1)
        return max(width, max_card_width + u(260)), max(height, total_height + u(80))

    def _layout_timeline_nodes(
        self,
        nodes: list[dict[str, Any]],
        width: int,
        height: int,
        *,
        sizes: dict[str, tuple[int, int]],
    ) -> tuple[dict[str, tuple[int, int]], int]:
        u = self._u
        spine_x = u(96)
        max_card_width = max((size[0] for size in sizes.values()), default=u(520))
        card_center_x = spine_x + u(72) + max_card_width // 2
        total_height = sum((sizes.get(str(node.get("id") or ""), (u(520), u(96)))[1] for node in nodes), 0)
        total_height += u(30) * max(0, len(nodes) - 1)
        current_y = max(u(42), (height - total_height) // 2)
        coords: dict[str, tuple[int, int]] = {}
        for node in nodes:
            node_id = str(node.get("id") or "")
            node_h = sizes.get(node_id, (u(520), u(96)))[1]
            coords[node_id] = (card_center_x, current_y + node_h // 2)
            current_y += node_h + u(30)
        return coords, spine_x

    def _timeline_node_size(self, node: dict[str, Any]) -> tuple[int, int]:
        u = self._u
        node_w = u(540)
        lines = self._graph_node_lines(node, node_w - u(52))
        node_h = u(58) + len(lines) * u(17)
        return node_w, max(u(92), min(node_h, u(156)))

    def _draw_timeline_node(self, canvas: tk.Canvas, node: dict[str, Any], cx: int, cy: int, *, size: tuple[int, int], scale: float) -> None:
        u = self._u
        f = self._f
        node_w, node_h = size
        node_w = int(round(node_w * scale))
        node_h = int(round(node_h * scale))
        x1 = cx - node_w // 2
        y1 = cy - node_h // 2
        x2 = cx + node_w // 2
        y2 = cy + node_h // 2
        color = self._graph_node_color(node)
        radius = max(6, int(round(u(10) * scale)))
        self._round_rect(canvas, x1, y1, x2, y2, radius, fill="#ffffff", outline="#e5e7eb", width=max(1, int(round(u(1) * scale))))
        strip_w = max(3, int(round(u(4) * scale)))
        canvas.create_rectangle(x1, y1 + radius, x1 + strip_w, y2 - radius, fill=color, outline=color)

        def scaled_font_size(base_size: int, minimum_pixels: int) -> int:
            pixels = max(minimum_pixels, int(round(abs(base_size) * scale)))
            return -pixels if base_size < 0 else pixels

        label_font = scaled_font_size(f(10), 8)
        body_font = scaled_font_size(f(11), 8)
        pad_x = int(round(u(22) * scale))
        label_y = y1 + int(round(u(14) * scale))
        body_y = y1 + int(round(u(40) * scale))
        canvas.create_text(
            x1 + pad_x,
            label_y,
            text=self._graph_node_label(node),
            anchor="nw",
            fill=color,
            font=("Segoe UI", label_font, "bold"),
        )
        canvas.create_text(
            x1 + pad_x,
            body_y,
            text="\n".join(self._graph_node_lines(node, max(self._u(120), node_w - pad_x * 2))),
            anchor="nw",
            fill=TEXT,
            width=max(1, node_w - pad_x * 2),
            font=("Segoe UI", body_font, "normal"),
        )

    def _graph_node_label(self, node: dict[str, Any]) -> str:
        node_type = str(node.get("type") or "")
        zh = self.language == ZH_CN
        labels = {
            "Method": ("方法", "Method"),
            "Evidence": ("证据", "Evidence"),
            "Result": ("结果", "Result"),
            "Claim": ("结论", "Conclusion"),
            "Warrant": ("机制解释", "Mechanism"),
            "Limitation": ("边界 / 限制", "Boundary / limitation"),
            "Rebuttal": ("反驳", "Rebuttal"),
            "Context": ("背景", "Context"),
            "Definition": ("定义", "Definition"),
        }
        return labels.get(node_type, (node_type or "节点", node_type or "Node"))[0 if zh else 1]

    def _graph_node_color(self, node: dict[str, Any]) -> str:
        markers = node.get("markers", {}) if isinstance(node.get("markers"), dict) else {}
        node_type = str(node.get("type") or "")
        if markers.get("risk") or node_type in {"Limitation", "Rebuttal"}:
            return "#d8585e"
        if node_type == "Method":
            return "#0f766e"
        if node_type == "Evidence":
            return "#0891b2"
        if node_type == "Result":
            return "#2563eb"
        if node_type == "Warrant":
            return "#64748b"
        if node_type == "Claim" or markers.get("root"):
            return "#111827"
        return "#64748b"

    def _graph_natural_size(
        self,
        nodes: list[dict[str, Any]],
        width: int,
        height: int,
        *,
        sizes: dict[str, tuple[int, int]],
        flow: bool,
    ) -> tuple[int, int]:
        u = self._u
        if flow:
            max_per_row = max(2, min(4, width // max(u(260), 1)))
            rows = [nodes[index : index + max_per_row] for index in range(0, len(nodes), max_per_row)]
        else:
            root = [node for node in nodes if node.get("markers", {}).get("root")]
            claims = [node for node in nodes if node not in root and node.get("type") == "Claim"]
            support = [node for node in nodes if node.get("type") in {"Evidence", "Result", "Method", "Warrant"}]
            risk = [node for node in nodes if node.get("markers", {}).get("risk") and node not in support]
            other = [node for node in nodes if node not in root and node not in claims and node not in support and node not in risk]
            rows = [row for row in (root, claims, support, risk, other) if row]
        max_width = 0
        total_height = 0
        for row_index, row in enumerate(rows):
            row_width = sum(sizes.get(str(node.get("id") or ""), (u(320), u(92)))[0] for node in row)
            row_width += u(96) * max(0, len(row) - 1)
            max_width = max(max_width, row_width)
            total_height += max((sizes.get(str(node.get("id") or ""), (u(320), u(92)))[1] for node in row), default=u(92))
            if row_index:
                total_height += u(56)
        return max(width, max_width + u(160)), max(height, total_height + u(96))

    def _graph_layout_bbox(self, coords: dict[str, tuple[int, int]], sizes: dict[str, tuple[int, int]]) -> tuple[float, float, float, float]:
        if not coords:
            return (0.0, 0.0, 1.0, 1.0)
        min_x = min(coords[node_id][0] - sizes.get(node_id, (1, 1))[0] / 2 for node_id in coords)
        max_x = max(coords[node_id][0] + sizes.get(node_id, (1, 1))[0] / 2 for node_id in coords)
        min_y = min(coords[node_id][1] - sizes.get(node_id, (1, 1))[1] / 2 for node_id in coords)
        max_y = max(coords[node_id][1] + sizes.get(node_id, (1, 1))[1] / 2 for node_id in coords)
        return (min_x, min_y, max_x, max_y)

    def _graph_transform(
        self,
        view_state: dict[str, Any] | None,
        bbox: tuple[float, float, float, float],
        width: int,
        height: int,
    ) -> tuple[float, float, float]:
        if view_state is None:
            return 1.0, 0.0, 0.0
        min_x, min_y, max_x, max_y = bbox
        content_w = max(1.0, max_x - min_x)
        content_h = max(1.0, max_y - min_y)
        if not view_state.get("initialized"):
            pad = self._u(42)
            raw_fit_scale = min(max(1, width - pad * 2) / content_w, max(1, height - pad * 2) / content_h)
            fit_scale = max(0.68, min(1.15, raw_fit_scale))
            view_state["scale"] = fit_scale
            if fit_scale > raw_fit_scale + 0.001:
                if content_w * fit_scale <= max(1, width - pad * 2):
                    view_state["offset_x"] = width / 2 - ((min_x + max_x) / 2) * fit_scale
                else:
                    view_state["offset_x"] = pad - min_x * fit_scale
                view_state["offset_y"] = pad - min_y * fit_scale
            else:
                view_state["offset_x"] = width / 2 - ((min_x + max_x) / 2) * fit_scale
                view_state["offset_y"] = height / 2 - ((min_y + max_y) / 2) * fit_scale
            view_state["initialized"] = True
        return (
            float(view_state.get("scale", 1.0)),
            float(view_state.get("offset_x", 0.0)),
            float(view_state.get("offset_y", 0.0)),
        )

    def _visible_graph_nodes(self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]], root_claim: str) -> list[dict[str, Any]]:
        by_id = {str(node.get("id") or ""): node for node in nodes}
        structural = {"Document", "Section", "ArgumentBlock"}
        wanted: set[str] = set()
        if root_claim:
            wanted.add(root_claim)
        for edge in edges:
            if edge.get("target") == root_claim or edge.get("source") == root_claim:
                wanted.add(str(edge.get("source") or ""))
                wanted.add(str(edge.get("target") or ""))
        if len(wanted) < 3:
            wanted.update(str(node.get("id") or "") for node in nodes if node.get("type") not in structural)
        visible = [by_id[node_id] for node_id in wanted if node_id in by_id and by_id[node_id].get("type") not in structural]
        visible.sort(key=lambda node: self._graph_node_rank(node, root_claim))
        return visible[:24]

    def _graph_node_rank(self, node: dict[str, Any], root_claim: str) -> tuple[int, str]:
        node_id = str(node.get("id") or "")
        if node_id == root_claim:
            return (0, node_id)
        node_type = str(node.get("type") or "")
        if node_type == "Claim":
            return (1, node_id)
        if node_type in {"Evidence", "Result", "Method", "Warrant"}:
            return (2, node_id)
        if node.get("markers", {}).get("risk"):
            return (3, node_id)
        return (4, node_id)

    def _layout_graph_nodes(
        self,
        nodes: list[dict[str, Any]],
        width: int,
        height: int,
        *,
        sizes: dict[str, tuple[int, int]] | None = None,
        flow: bool = False,
    ) -> dict[str, tuple[int, int]]:
        u = self._u
        sizes = sizes or {}
        if flow:
            max_per_row = max(2, min(4, width // max(u(260), 1)))
            rows = [nodes[index : index + max_per_row] for index in range(0, len(nodes), max_per_row)]
        else:
            root = [node for node in nodes if node.get("markers", {}).get("root")]
            claims = [node for node in nodes if node not in root and node.get("type") == "Claim"]
            support = [node for node in nodes if node.get("type") in {"Evidence", "Result", "Method", "Warrant"}]
            risk = [node for node in nodes if node.get("markers", {}).get("risk") and node not in support]
            other = [node for node in nodes if node not in root and node not in claims and node not in support and node not in risk]
            rows = [row for row in (root, claims, support, risk, other) if row]
        row_heights = [max((sizes.get(str(node.get("id") or ""), (u(240), u(104)))[1] for node in row), default=u(104)) for row in rows]
        gap_y = u(42)
        total_h = sum(row_heights) + gap_y * max(0, len(rows) - 1)
        top = max(u(36), (height - total_h) // 2)
        coords: dict[str, tuple[int, int]] = {}
        current_y = top
        for row_index, row in enumerate(rows):
            row_height = row_heights[row_index]
            y = current_y + row_height // 2
            if len(row) == 1:
                xs = [width // 2]
            else:
                margin = u(132)
                usable = max(u(240), width - margin * 2)
                step = usable // max(1, len(row) - 1)
                xs = [margin + index * step for index in range(len(row))]
            for node, x in zip(row, xs):
                coords[str(node.get("id") or "")] = (x, y)
            current_y += row_height + gap_y
        return coords

    def _graph_node_size(self, node: dict[str, Any]) -> tuple[int, int]:
        u = self._u
        markers = node.get("markers", {}) if isinstance(node.get("markers"), dict) else {}
        node_w = u(380 if markers.get("root") else 340)
        lines = self._graph_node_lines(node, node_w)
        node_h = u(34) + len(lines) * u(20)
        return node_w, max(u(72), min(node_h, u(160)))

    def _graph_node_lines(self, node: dict[str, Any], node_w: int) -> list[str]:
        approx_chars = max(12, node_w // self._u(12))
        text = str(node.get("text") or node.get("id") or "")
        lines: list[str] = []
        for paragraph in text.splitlines() or [text]:
            wrapped = textwrap.wrap(paragraph, width=approx_chars, break_long_words=True, replace_whitespace=False)
            if not wrapped and paragraph:
                wrapped = [paragraph]
            lines.extend(wrapped or [""])
        max_lines = 5
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = _short_text(lines[-1], max(8, approx_chars - 1)).rstrip(".") + "..."
        return lines or [""]

    def _draw_graph_node(self, canvas: tk.Canvas, node: dict[str, Any], cx: int, cy: int, *, size: tuple[int, int], scale: float = 1.0) -> None:
        u = self._u
        f = self._f
        markers = node.get("markers", {}) if isinstance(node.get("markers"), dict) else {}
        node_w, node_h = size
        node_w = int(round(node_w * scale))
        node_h = int(round(node_h * scale))
        type_fill = "#64748b"
        if markers.get("root"):
            type_fill = "#111827"
        elif markers.get("risk"):
            type_fill = "#d8585e"
        elif markers.get("important"):
            type_fill = "#d59b2e"
        elif markers.get("evidence"):
            type_fill = "#0891b2"
        x1 = cx - node_w // 2
        y1 = cy - node_h // 2
        dot = max(4, int(round(u(6) * scale)))
        badge = self._graph_node_label(node)
        def scaled_font_size(base_size: int, minimum_pixels: int) -> int:
            pixels = max(minimum_pixels, int(round(abs(base_size) * scale)))
            return -pixels if base_size < 0 else pixels

        badge_font = scaled_font_size(f(9), 7)
        body_font = scaled_font_size(f(11), 8)
        top_pad = int(round(u(2) * scale))
        body_y = y1 + int(round(u(24) * scale))
        canvas.create_oval(x1, y1 + top_pad, x1 + dot, y1 + top_pad + dot, fill=type_fill, outline=type_fill)
        canvas.create_text(
            x1 + dot + int(round(u(8) * scale)),
            y1,
            text=badge,
            anchor="nw",
            fill=type_fill,
            font=("Segoe UI", badge_font, "bold"),
        )
        canvas.create_text(
            x1,
            body_y,
            text="\n".join(self._graph_node_lines(node, max(self._u(120), node_w))),
            anchor="nw",
            fill=TEXT,
            width=node_w,
            font=("Segoe UI", body_font, "bold" if markers.get("root") or markers.get("important") else "normal"),
        )

    def _refresh_after_language_change(self) -> None:
        if self.search_var.get() in {_ui_text(DEFAULT_LANGUAGE, "search"), _ui_text(ZH_CN, "search"), ""}:
            self.search_var.set(self._text("search"))
        current_search = self.searching
        if current_search.startswith("status:"):
            self._load_status_view(current_search.split(":", 1)[1])
            return
        if current_search.startswith("type:"):
            self._load_type_view(current_search.split(":", 1)[1])
            return
        if current_search.startswith("source:"):
            self._load_source_view(current_search.split(":", 1)[1])
            return
        if current_search:
            self._perform_search(query=current_search)
            return
        self.load_route(self.route)

    def _open_settings_window(self) -> None:
        window = tk.Toplevel(self)
        window.title(self._text("settings_title"))
        u = self._u
        f = self._f
        window_width = u(740)
        screen_height = self.winfo_screenheight()
        window_height = min(u(700), max(u(560), screen_height - u(80)))
        x = self.winfo_rootx() + max(u(80), (self.winfo_width() - window_width) // 2)
        y = self.winfo_rooty() + max(u(40), (self.winfo_height() - window_height) // 4)
        window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        window.minsize(u(640), min(u(560), window_height))
        window.transient(self)
        window.configure(bg="#f7f7f9")
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(0, weight=1)

        body_canvas = tk.Canvas(window, bg="#f7f7f9", highlightthickness=0)
        body_canvas.grid(row=0, column=0, sticky="nsew", padx=u(34), pady=(u(30), u(12)))
        body_scrollbar = ttk.Scrollbar(window, orient="vertical", command=body_canvas.yview)
        body_scrollbar.grid(row=0, column=1, sticky="ns", pady=(u(30), u(12)))
        body_canvas.configure(yscrollcommand=body_scrollbar.set)

        shell = tk.Frame(body_canvas, bg="#f7f7f9")
        shell_window = body_canvas.create_window((0, 0), window=shell, anchor="nw")
        shell.grid_columnconfigure(0, weight=1)

        def sync_settings_scroll_region(_event: tk.Event[Any] | None = None) -> None:
            body_canvas.configure(scrollregion=body_canvas.bbox("all"))

        def sync_settings_body_width(event: tk.Event[Any]) -> None:
            body_canvas.itemconfigure(shell_window, width=event.width)

        shell.bind("<Configure>", sync_settings_scroll_region)
        body_canvas.bind("<Configure>", sync_settings_body_width)

        tk.Label(
            shell,
            text=self._text("settings_title"),
            bg="#f7f7f9",
            fg=TEXT,
            anchor="w",
            font=("Segoe UI", f(22), "bold"),
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            shell,
            text=self._text("english_canonical"),
            bg="#f7f7f9",
            fg=MUTED,
            anchor="w",
            justify="left",
            wraplength=u(620),
            font=("Segoe UI", f(12)),
        ).grid(row=1, column=0, sticky="ew", pady=(u(8), u(20)))

        language_display_var = tk.StringVar(value=_language_display(self.language))
        group = tk.Frame(shell, bg=BG, highlightbackground=LINE, highlightthickness=1)
        group.grid(row=2, column=0, sticky="ew", pady=(0, u(24)))
        group.grid_columnconfigure(1, weight=1)
        tk.Label(
            group,
            text="Aa",
            bg=BG,
            fg=TEXT,
            anchor="center",
            font=self._font(18, "bold"),
        ).grid(row=0, column=0, sticky="n", padx=(u(18), u(10)), pady=(u(18), u(6)))
        tk.Label(
            group,
            text=self._text("display_language"),
            bg=BG,
            fg=TEXT,
            anchor="w",
            font=self._font(15, "bold"),
        ).grid(row=0, column=1, sticky="ew", padx=(0, u(18)), pady=(u(18), u(2)))
        tk.Label(
            group,
            text=self._text("language_hint"),
            bg=BG,
            fg=MUTED,
            anchor="w",
            justify="left",
            wraplength=u(560),
            font=self._font(11),
        ).grid(row=1, column=1, sticky="ew", padx=(0, u(18)), pady=(0, u(12)))

        window.option_add("*TCombobox*Listbox.font", self._font(13))
        window.option_add("*TCombobox*Listbox.background", BG)
        window.option_add("*TCombobox*Listbox.foreground", TEXT)
        window.option_add("*TCombobox*Listbox.selectBackground", "#ececf1")
        window.option_add("*TCombobox*Listbox.selectForeground", TEXT)
        style = ttk.Style(window)
        style.configure("LogicGuard.TCombobox", font=self._font(13), padding=(u(10), u(8), u(8), u(8)), arrowsize=u(18))

        def configure_combo_popup(combo: ttk.Combobox) -> None:
            try:
                popdown = combo.tk.call("ttk::combobox::PopdownWindow", combo)
                listbox = f"{popdown}.f.l"
                combo.tk.call(listbox, "configure", "-font", self._font(13), "-activestyle", "none")
                combo.tk.call(listbox, "configure", "-selectborderwidth", 0, "-borderwidth", u(6))
            except tk.TclError:
                return

        def bind_combo_popup(combo: ttk.Combobox) -> None:
            combo.configure(postcommand=lambda widget=combo: configure_combo_popup(widget))

        language_combo = ttk.Combobox(
            group,
            textvariable=language_display_var,
            values=list(LANGUAGE_DISPLAY_OPTIONS.values()),
            state="readonly",
            style="LogicGuard.TCombobox",
            font=self._font(13),
            height=4,
        )
        language_combo.grid(row=2, column=1, sticky="ew", padx=(0, u(18)), pady=(0, u(18)), ipady=u(4))
        bind_combo_popup(language_combo)

        actions = tk.Frame(window, bg="#f7f7f9")
        actions.grid(row=1, column=0, sticky="e", padx=u(34), pady=(0, u(24)))

        def save_settings() -> None:
            selected_language = _language_from_display(language_display_var.get())
            self.settings = {"language": selected_language, "mode": PERSONAL_MODE}
            save_desktop_settings(self.repo_root, self.settings)
            self.settings = load_desktop_settings(self.repo_root)
            self.language = selected_language
            self._refresh_after_language_change()
            window.destroy()

        tk.Button(
            actions,
            text=self._text("cancel"),
            command=window.destroy,
            relief="flat",
            bg="#ececf1",
            fg=TEXT,
            padx=u(18),
            pady=u(7),
            font=("Segoe UI", f(12)),
        ).grid(row=0, column=0, padx=(0, u(10)))
        tk.Button(
            actions,
            text=self._text("save"),
            command=save_settings,
            relief="flat",
            bg=ACCENT,
            fg=BG,
            padx=u(18),
            pady=u(7),
            font=("Segoe UI", f(12)),
        ).grid(row=0, column=1)
        window.bind("<Escape>", lambda _event: window.destroy())
        window.lift()
        window.focus_set()

    def _create_utility_window(self, title: str, message: str) -> tuple[tk.Toplevel, tk.Label]:
        window = tk.Toplevel(self)
        window.title(title)
        u = self._u
        f = self._f
        window_width = u(660)
        window_height = u(500)
        x = self.winfo_rootx() + max(u(80), (self.winfo_width() - window_width) // 2)
        y = self.winfo_rooty() + max(u(80), (self.winfo_height() - window_height) // 3)
        window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        window.minsize(u(560), u(430))
        window.transient(self)
        window.configure(bg="#f7f7f9")
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(0, weight=1)

        shell = tk.Frame(window, bg="#f7f7f9")
        shell.grid(row=0, column=0, sticky="nsew", padx=u(34), pady=u(30))
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(1, weight=1)

        title_label = tk.Label(shell, text=title, bg="#f7f7f9", fg=TEXT, anchor="w", font=("Segoe UI", f(22), "bold"))
        title_label.grid(row=0, column=0, sticky="ew")
        body = tk.Label(
            shell,
            text=message,
            bg="#f7f7f9",
            fg=TEXT,
            anchor="nw",
            justify="left",
            wraplength=u(560),
            font=("Segoe UI", f(14)),
        )
        body.grid(row=1, column=0, sticky="nsew", pady=(u(18), u(20)))
        close = tk.Button(
            shell,
            text=self._text("close"),
            command=window.destroy,
            relief="flat",
            bg=ACCENT,
            fg=BG,
            padx=u(18),
            pady=u(7),
            font=("Segoe UI", f(12), "bold"),
        )
        close.grid(row=2, column=0, sticky="e")
        window.bind("<Escape>", lambda _event: window.destroy())
        window.lift()
        window.focus_set()
        return window, body

    def _open_utility_window(self, title: str, message: str) -> None:
        self._create_utility_window(title, message)

    def _insert_detail_section(self, widget: tk.Text, label: str, value: Any) -> None:
        widget.insert("end", f"{label}\n", "heading")
        for body in _detail_paragraphs(value, self.language):
            for paragraph in textwrap.wrap(body, width=88) or ["-"]:
                widget.insert("end", f"{paragraph}\n", "body")
            widget.insert("end", "\n")
        widget.insert("end", "\n")


def run_desktop_app(repo_root: str | Path, language: str | None = None) -> None:
    app = KbDesktopApp(repo_root, language=language)
    app.mainloop()
