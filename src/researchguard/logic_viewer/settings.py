"""No-mutation settings shim for the copied desktop UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

PERSONAL_MODE = "personal"


def load_desktop_settings(repo_root: str | Path) -> dict[str, Any]:
    return {"language": "en", "mode": PERSONAL_MODE}


def save_desktop_settings(repo_root: str | Path, settings: dict[str, Any]) -> None:
    return None
