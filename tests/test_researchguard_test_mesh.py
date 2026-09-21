from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from scripts.build_skillguard_contracts import (
    MEMBERS,
    TEST_MESH_MAINTENANCE_INPUTS,
    UNIT_TEST_MESH_PATH,
    UNIT_TEST_MESH_PROJECTION_ID,
    expected_unit_test_mesh_manifest,
    contract,
)


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "scripts" / "check_researchguard_test_mesh.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location(
        "researchguard_test_mesh_checker_under_test", CHECKER_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unit_test_mesh_is_the_single_current_generated_definition() -> None:
    manifest = json.loads(UNIT_TEST_MESH_PATH.read_text(encoding="utf-8"))
    assert manifest == expected_unit_test_mesh_manifest()
    assert manifest["schema_version"] == "skillguard.test_mesh_manifest.current"
    assert manifest["mesh_id"] == "researchguard-suite-owner-receipt-mesh"
    assert manifest["source_model_id"] == (
        "researchguard.suite.validation_composition.current"
    )
    assert manifest["profiles"] == [
        {
            "profile_id": "focused",
            "closure_profile_id": "enforced",
            "full_admission_required": False,
        },
        {
            "profile_id": "full",
            "closure_profile_id": "enforced",
            "full_admission_required": True,
        },
    ]
    assert "fast" not in {row["profile_id"] for row in manifest["profiles"]}
    mesh_paths = sorted(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("test-mesh.json")
        if ".skillguard" in path.parts and ".git" not in path.parts
    )
    assert mesh_paths == [".skillguard/test-mesh.json"]


def test_static_test_mesh_audit_covers_five_members_and_twenty_exact_owners() -> None:
    checker = _load_checker()
    result = checker.audit(ROOT)
    assert result["status"] == "pass", result["findings"]
    assert result["maintenance_unit_id"] == "unit:researchguard-suite"
    assert result["member_count"] == 5
    assert result["check_owner_count"] == 20
    assert result["evidence_subject_count"] == 20
    assert result["evidence_domain_count"] == 20
    assert result["obligation_count"] == 21
    assert result["execution_count"] == 0
    assert result["plan_only_execution_status"] == "not_run"
    assert result["unknown_mapping_disposition"] == "block"
    assert result["member_results"] == [
        {
            "member_skill_id": member,
            "check_owner_count": 4,
            "evidence_subject_count": 4,
            "evidence_domain_count": 4,
            "closure_profile_id": "enforced",
            "obligation_count": 5 if member == "researchguard" else 4,
            "plan_only_static_eligibility": (
                "eligible_after_legitimate_claimed_run"
            ),
        }
        for member in MEMBERS
    ]
    assert not list((ROOT / "skills").glob("*/.skillguard/test-mesh.json"))
    projection = result["source_maintenance_projection"]
    assert projection["consumer_id"] == UNIT_TEST_MESH_PROJECTION_ID
    assert projection["paths"] == sorted(TEST_MESH_MAINTENANCE_INPUTS)
    assert projection["semantic_owner_selection"] == []
    assert result["generator_impact"]["direct_semantic_owner_ids"] == []
    assert result["consumer_install_transaction"] == {
        "obligation_id": (
            "obligation:researchguard:researchguard:consumer-install-transaction"
        ),
        "execution_owner_id": "owner:researchguard:researchguard:native-tests",
        "source_only_paths": [
            "scripts/install_researchguard.py",
            "tests/test_install_researchguard.py",
        ],
    }
    assert len(result["installation_boundaries"]) == 5
    assert all(
        row["release_manifest_path"] == "consumer-release.json"
        and row["installation_projection_id"] == "projection:consumer-distribution"
        for row in result["installation_boundaries"]
    )

def test_validation_plan_is_current_but_not_run_without_a_maintenance_owner() -> None:
    plan = json.loads(
        (
            ROOT
            / ".skillguard"
            / "researchguard-suite-validation-plan.json"
        ).read_text(encoding="utf-8")
    )
    assert plan["status"] == "current_not_run"
    assert plan["execution_disposition"] == "not_run"
    assert plan["toolchain"]["flowguard_status"] == "current_not_run"


@pytest.mark.parametrize(
    "member",
    ("researchguard", "logicguard", "sourceguard", "traceguard", "experimentguard"),
)
def test_member_check_input_references_are_unique(member: str) -> None:
    source = json.loads(
        (
            ROOT / "skills" / member / ".skillguard" / "contract-source.json"
        ).read_text(encoding="utf-8")
    )
    for check in source["checks"]:
        paths = [row["path"] for row in check["input_selectors"] if row.get("path")]
        assert len(paths) == len(set(paths)), check["check_id"]
        assert all("\\" not in path and not Path(path).is_absolute() for path in paths)


def test_consumer_install_transaction_reuses_the_researchguard_native_owner() -> None:
    source = json.loads(
        (ROOT / "skills" / "researchguard" / ".skillguard" / "contract-source.json")
        .read_text(encoding="utf-8")
    )
    obligation_id = "obligation:researchguard:researchguard:consumer-install-transaction"
    compiled = json.loads(
        (ROOT / "skills" / "researchguard" / ".skillguard" / "compiled-contract.json")
        .read_text(encoding="utf-8")
    )
    obligation = next(
        row for row in compiled["obligations"] if row["obligation_id"] == obligation_id
    )
    assert obligation["owner_step_ids"] == ["step:researchguard:researchguard:tests"]
    native_check = next(
        row for row in source["checks"] if row["check_id"] == "check:researchguard:native-tests"
    )
    assert native_check["covers_obligation_ids"] == [
        "obligation:researchguard:researchguard:native-tests",
        obligation_id,
    ]
    native_step = next(
        row for row in source["step_bindings"] if row["step_id"] == "step:researchguard:researchguard:tests"
    )
    assert native_step["check_ids"] == ["check:researchguard:native-tests"]
    assert obligation["obligation_id"] == obligation_id
