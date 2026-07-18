"""Display labels for the LogicGuard viewer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

DEFAULT_LANGUAGE = "en"
ZH_CN = "zh-CN"
SUPPORTED_LANGUAGES = (DEFAULT_LANGUAGE, ZH_CN)

_SEGMENT_LABELS = {
    DEFAULT_LANGUAGE: {
        "recent": "Recently Added",
        "uncategorized": "Uncategorized",
    },
    ZH_CN: {
        "recent": "最近加入",
        "uncategorized": "未归入项目",
    },
}


def normalize_language(value: Any) -> str:
    text = str(value or "").strip()
    if text not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"unsupported language {text!r}; expected one of {SUPPORTED_LANGUAGES}"
        )
    return text


def localized_route_segment(segment: Any, language: str = DEFAULT_LANGUAGE, repo_root: Path | None = None) -> str:
    normalized = normalize_language(language)
    text = str(segment or "").strip()
    return _SEGMENT_LABELS[normalized].get(text, text)


def localized_route_label(
    route: Any,
    language: str = DEFAULT_LANGUAGE,
    *,
    empty_label: str = "All Sources",
    repo_root: Path | None = None,
) -> str:
    parts = _route_parts(route)
    if not parts:
        return empty_label
    return " / ".join(localized_route_segment(part, language, repo_root=repo_root) for part in parts)


def localized_route_title(
    route: Any,
    language: str = DEFAULT_LANGUAGE,
    *,
    empty_label: str = "All Sources",
    repo_root: Path | None = None,
) -> str:
    return localized_route_label(route, language, empty_label=empty_label, repo_root=repo_root)


def _route_parts(route: Any) -> list[str]:
    if route is None:
        return []
    if isinstance(route, str):
        return [part for part in route.strip("/").split("/") if part]
    return [str(part).strip("/") for part in route if str(part).strip("/")]
