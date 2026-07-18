"""Canonical ResearchGuard suite identity."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from . import MEMBER_IDS, SUITE_ID, __version__


_PACKAGE_ROOT = Path(__file__).resolve().parent
_IGNORED_PARTS = {"__pycache__"}
_IGNORED_SUFFIXES = {".pyc", ".pyo"}


def governed_file_manifest() -> tuple[tuple[str, str], ...]:
    """Return the deterministic content manifest for the installed runtime."""

    rows: list[tuple[str, str]] = []
    for path in sorted(_PACKAGE_ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(_PACKAGE_ROOT)
        if any(part in _IGNORED_PARTS for part in relative.parts):
            continue
        if path.suffix.lower() in _IGNORED_SUFFIXES:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append((relative.as_posix(), digest))
    return tuple(rows)


def suite_fingerprint() -> str:
    """Return one content-addressed identity for all native members."""

    digest = hashlib.sha256()
    digest.update(f"{SUITE_ID}\0{__version__}\0".encode("utf-8"))
    for relative, file_digest in governed_file_manifest():
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def suite_identity() -> dict[str, Any]:
    """Return the canonical machine-readable suite identity."""

    return {
        "suite_id": SUITE_ID,
        "version": __version__,
        "members": list(MEMBER_IDS),
        "distribution": "researchguard",
        "console_script": "researchguard",
        "fingerprint": suite_fingerprint(),
    }


__all__ = ["governed_file_manifest", "suite_fingerprint", "suite_identity"]

