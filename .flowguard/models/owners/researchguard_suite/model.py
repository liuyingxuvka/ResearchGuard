"""Canonical registered wrapper for the ResearchGuard suite model."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
MODEL_ID = "researchguard_suite"
CHILD_MODEL_IDS = (
    "authoritative_model_system",
    "compositional_verification_kernel",
    "hierarchical_model_mesh",
    "model_test_code_alignment",
    "logic_synthesis",
    "logic_selection_contract",
    "argument_support_closure",
    "discourse_structure",
    "trace_domain_export",
)
CHILD_MODEL_PATHS = {
    model_id: f".flowguard/models/owners/{model_id}/model.py"
    for model_id in CHILD_MODEL_IDS
}
SEMANTIC_PARENT_BY_CHILD = {
    "logic_synthesis": "semantic-parent:researchguard_suite",
    "logic_selection_contract": "semantic-parent:logic_synthesis",
    "argument_support_closure": "semantic-parent:logic_synthesis",
    "discourse_structure": "semantic-parent:logic_synthesis",
    "trace_domain_export": "semantic-parent:researchguard_suite",
}
SEMANTIC_RELATION_EDGES = (
    ("researchguard_suite", "logic_synthesis"),
    ("logic_synthesis", "logic_selection_contract"),
    ("logic_synthesis", "argument_support_closure"),
    ("logic_synthesis", "discourse_structure"),
    ("researchguard_suite", "trace_domain_export"),
)
CHILD_FAILURE_PROPAGATION = "child_failure_blocks_parent"
ROOT_SUPPORTING_MODEL_IDS = (
    "authoritative_model_system",
    "compositional_verification_kernel",
    "hierarchical_model_mesh",
    "model_test_code_alignment",
)
ROOT_STRUCTURAL_PARENT_ID = "semantic-parent:software-root"
PROTECTED_FAILURE_IDS = (
    "researchguard:ambiguous-or-recursive-route",
    "researchguard:unproven-member-admission",
    "researchguard:alternate-success-after-member-failure",
    "researchguard:stale-suite-identity",
    "researchguard:premature-member-model-closure",
    "researchguard:experiment-execution-overclaim",
)
KNOWN_GOOD_CASE_ID = "native-runner:researchguard-suite:declared-route-scenarios"
KNOWN_BAD_CASE_IDS = (
    "scenario:rg03-or-rg06",
    "scenario:rg03-rg10-rg11",
    "scenario:rg04",
    "native:researchguard-suite:currentness-mismatch",
    "native:member-task-iteration:strict-closure",
    "native:experimentguard:recommendation-boundary",
)
FLOWGUARD_ROOT = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = FLOWGUARD_ROOT.parent
MODEL_PATH = FLOWGUARD_ROOT / "models" / "researchguard_suite_model.py"
SOFTWARE_DNA_PATH = REPOSITORY_ROOT / "models" / "software_dna" / "researchguard.json"


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


def run_model() -> None:
    if len(CHILD_MODEL_IDS) != 9 or len(set(CHILD_MODEL_IDS)) != 9:
        raise AssertionError("ResearchGuard suite child model inventory must contain nine unique owners")
    if set(CHILD_MODEL_PATHS) != set(CHILD_MODEL_IDS):
        raise AssertionError("ResearchGuard suite child path inventory drifted")
    if len(PROTECTED_FAILURE_IDS) != len(KNOWN_BAD_CASE_IDS):
        raise AssertionError("ResearchGuard suite protected-case inventory drifted")
    expected_edges = {child for _, child in SEMANTIC_RELATION_EDGES}
    if expected_edges != set(SEMANTIC_PARENT_BY_CHILD):
        raise AssertionError("ResearchGuard suite semantic child hierarchy drifted")


def software_dna_report():
    """Read the native software-DNA contract without creating a projection."""

    sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
    from researchguard.software_dna import check_software_dna_contract

    return check_software_dna_contract(REPOSITORY_ROOT)


__all__ = ["FLOWGUARD_MODEL_MARKER", "SOFTWARE_DNA_PATH", "load_suite_model", "scenarios", "software_dna_report"]
