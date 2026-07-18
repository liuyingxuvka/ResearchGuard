"""LogicGuard Project Library Viewer UI."""

from __future__ import annotations

__all__ = ["run_desktop_app"]


def run_desktop_app(repo_root: str, language: str | None = None) -> None:
    from .desktop_app import run_desktop_app as _run

    _run(repo_root, language=language)
