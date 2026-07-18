"""Localization helpers for persisted LogicGuard display text."""

from __future__ import annotations

from typing import Any, Mapping


DEFAULT_LANGUAGE = "en"
ZH_CN = "zh-CN"
SUPPORTED_LANGUAGES = (DEFAULT_LANGUAGE, ZH_CN)


def normalize_language(value: Any) -> str:
    text = str(value or "").strip()
    if text not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"unsupported language {text!r}; expected one of {SUPPORTED_LANGUAGES}"
        )
    return text


def normalize_i18n(raw: Any) -> dict[str, dict[str, str]]:
    """Validate the one current language-first i18n mapping."""

    if not isinstance(raw, Mapping):
        return {}
    data: dict[str, dict[str, str]] = {}
    for language, values in raw.items():
        normalized = normalize_language(language)
        if not isinstance(values, Mapping):
            raise ValueError(f"i18n[{language!r}] must be a field mapping")
        for field, value in values.items():
            text = str(value or "").strip()
            if text:
                data.setdefault(normalized, {})[str(field)] = text
    return data


def localized_field(
    i18n: Any,
    field: str,
    language: str = DEFAULT_LANGUAGE,
    canonical_english: str = "",
) -> str:
    data = normalize_i18n(i18n)
    normalized = normalize_language(language)
    text = data.get(normalized, {}).get(field, "")
    if text:
        return text
    if normalized == DEFAULT_LANGUAGE:
        return str(canonical_english or "")
    if not str(canonical_english or ""):
        return ""
    raise KeyError(
        f"missing exact localized field {field!r} for language {normalized!r}"
    )


def field_i18n(i18n: Any, field: str, *, text_key: str = "text", scope_key: str = "scope") -> dict[str, dict[str, str]]:
    data = normalize_i18n(i18n)
    result: dict[str, dict[str, str]] = {}
    for language, values in data.items():
        entry: dict[str, str] = {}
        text = values.get(field, "")
        if text:
            entry[text_key] = text
        scope = values.get(scope_key, "")
        if scope:
            entry["scope"] = scope
        if entry:
            result[language] = entry
    return result
