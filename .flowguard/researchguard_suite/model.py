"""Canonical registered wrapper for the ResearchGuard suite model."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
MODEL_PATH = Path(__file__).resolve().parents[1] / "researchguard_suite_model.py"
SOFTWARE_DNA_PATH = Path(__file__).resolve().parents[2] / "models" / "software_dna" / "researchguard.json"


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


def software_dna_report():
    """Read the native software-DNA contract without creating a projection."""

    sys.path.insert(0, str(MODEL_PATH.parents[1] / "src"))
    from researchguard.software_dna import check_software_dna_contract

    return check_software_dna_contract(SOFTWARE_DNA_PATH.parents[2])


__all__ = ["FLOWGUARD_MODEL_MARKER", "SOFTWARE_DNA_PATH", "load_suite_model", "scenarios", "software_dna_report"]
