"""Path resolution for the LogicGuard viewer."""

from __future__ import annotations

from pathlib import Path


def resolve_repo_root(value: str | Path = "auto") -> Path:
    text = str(value or "auto")
    if text == "auto":
        cwd = Path.cwd()
        default_library = cwd / ".logicguard-library"
        return default_library if default_library.exists() else cwd
    return Path(text).expanduser().resolve()
