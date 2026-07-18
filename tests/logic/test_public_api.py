from __future__ import annotations

import tomllib
import re
from pathlib import Path

import researchguard.logic


ROOT = Path(__file__).resolve().parents[2]


def test_public_version_matches_pyproject() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert researchguard.logic.__version__ == pyproject["project"]["version"]


def test_public_version_matches_readme_and_changelog() -> None:
    version = researchguard.logic.__version__
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"**Current version:** `v{version}`" in readme
    assert f"**当前版本：** `v{version}`" in readme
    assert re.search(rf"^## v{re.escape(version)} - ", changelog, re.MULTILINE)


def test_source_library_api_is_exported() -> None:
    exported = set(researchguard.logic.__all__)
    assert "SourceLibrary" in exported
    assert "SourceRecord" in exported
    assert "NodeLink" in exported
    assert "DeepeningBranch" in exported
    assert "BranchAuditReport" in exported
    assert "IntakeMaterial" in exported
    assert "IntakeResult" in exported
    assert "intake_materials" in exported
    assert "create_argument_model" in exported


def test_structured_artifact_api_is_exported() -> None:
    exported = set(researchguard.logic.__all__)
    assert "GapItem" in exported
    assert "GapLedger" in exported
    assert "build_gap_ledger" in exported
    assert "search_combination_counterexamples" in exported
    assert "summarize_importance" in exported
    assert "build_artifact_map" in exported
    assert "audit_structure" in exported
    assert "synthesize_artifact_plan" in exported
    assert "adapt_delivery" in exported
    assert "markdown_to_model" in exported
    assert "markdown_to_model_dict" in exported
    assert "ClaimSourceParagraphMatrix" in exported
    assert "ClaimSourceParagraphRow" in exported
    assert "MatrixFinding" in exported
    assert "build_claim_source_paragraph_matrix" in exported
    assert "audit_claim_source_paragraph_matrix" in exported


def test_model_store_overlay_and_native_depth_api_is_exported() -> None:
    exported = set(researchguard.logic.__all__)
    assert {
        "SCHEMA_VERSION",
        "ModelId",
        "ModelRevision",
        "NodeId",
        "EdgeId",
        "BlockId",
        "QualifiedNodeRef",
        "ProvenanceRecord",
        "ModelSnapshot",
        "ModelStore",
        "ModelTransaction",
        "FileModelStore",
        "EvaluationOverlay",
        "evaluate_snapshot",
        "LogicDepthReceipt",
        "build_logic_depth_receipt",
    } <= exported
