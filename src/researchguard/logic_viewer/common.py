"""Small UI helpers for the copied LogicGuard viewer shell."""

from __future__ import annotations

from typing import Any


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, dict):
        return " ".join(f"{key}: {normalize_text(item)}" for key, item in value.items() if item not in (None, "", [], {}))
    if isinstance(value, (list, tuple, set)):
        return "; ".join(normalize_text(item) for item in value if item not in (None, "", [], {}))
    return str(value)
