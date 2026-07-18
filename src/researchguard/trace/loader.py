"""Load TraceGuard YAML/JSON model files.

Purpose: Load local model files for executable TraceGuard checks.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: TraceGuard
Math boundary: Loading and schema validation only; no factual validation.
CLI: researchguard trace validate <model.yaml>
Boundary: Local file loader does not fetch websites, call LLMs, or query databases.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .headers import check_model_header
from .schema import SchemaError, TraceGuardModel
from .validation import validate_references


def read_model_data(path: str | Path) -> dict[str, Any]:
    model_path = Path(path)
    text = model_path.read_text(encoding="utf-8")
    if model_path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise SchemaError(f"{model_path} did not load as a mapping")
    return data


def load_model(path: str | Path, *, require_header: bool = True) -> TraceGuardModel:
    data = read_model_data(path)
    if require_header:
        check_model_header(data, path)
    model = TraceGuardModel.from_dict(data)
    validate_references(model)
    return model


def dump_yaml(data: Any) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=False)
