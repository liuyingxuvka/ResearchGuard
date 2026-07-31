"""Canonical registered wrapper for the ResearchGuard suite model."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
MODEL_PATH = Path(__file__).resolve().parents[1] / "researchguard_suite_model.py"


def load_suite_model():
    spec = importlib.util.spec_from_file_location(
        "registered_researchguard_suite_model",
        MODEL_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load ResearchGuard model: {MODEL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def scenarios():
    return load_suite_model().scenarios()


__all__ = ["FLOWGUARD_MODEL_MARKER", "load_suite_model", "scenarios"]
