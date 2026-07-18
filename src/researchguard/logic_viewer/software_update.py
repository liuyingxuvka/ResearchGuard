"""Software-update shim for the copied desktop UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from researchguard.logic import __version__


def startup_block_message(repo_root: str | Path, language: str | None = None) -> str:
    return ""


def load_update_state(repo_root: str | Path) -> dict[str, Any]:
    return {
        "status": "current",
        "available": False,
        "version": __version__,
        "label": f"v{__version__}",
        "clickable": False,
    }


def set_update_request(repo_root: str | Path, requested: bool = True) -> None:
    return None


def update_badge_clickable(state: dict[str, Any]) -> bool:
    return False


def update_badge_label(state: dict[str, Any], language: str | None = None) -> str:
    return str(state.get("label") or state.get("version") or "")
