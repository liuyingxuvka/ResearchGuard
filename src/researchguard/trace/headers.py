"""Portable model header checks.

Purpose: Check required portable headers on YAML/JSON TraceGuard model files.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: TraceGuard
Math boundary: Header checks are metadata gates, not PSL inference.
CLI: researchguard trace validate <model.yaml>
Boundary: Passing the header check does not validate factual content.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .schema import SchemaError


REQUIRED_HEADER_KEYS = ("purpose", "repository", "skill", "math_boundary", "cli", "boundary")


def check_model_header(model_data: dict[str, Any], path: str | Path | None = None) -> list[str]:
    metadata = model_data.get("metadata") if isinstance(model_data, dict) else None
    if not isinstance(metadata, dict):
        raise SchemaError(f"{path or 'model'} is missing metadata header")
    missing = [key for key in REQUIRED_HEADER_KEYS if not metadata.get(key)]
    if missing:
        raise SchemaError(f"{path or 'model'} missing portable header keys: {', '.join(missing)}")
    return list(REQUIRED_HEADER_KEYS)
