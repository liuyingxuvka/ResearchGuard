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
    assert result["generator_impact"]["direct_semantic_owner_ids"] == [
        "owner:researchguard:researchguard:native-tests"
    ]
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
        and row["installation_projection_id"] == "projection:installation"
        for row in result["installation_boundaries"]
    )

def test_legacy_validation_plan_remains_stale_and_non_executable() -> None:
    plan = json.loads(
        (
            ROOT
            / ".skillguard"
            / "researchguard-suite-validation-plan.json"
        ).read_text(encoding="utf-8")
    )
    assert plan["status"] == "stale"
    assert plan["execution_disposition"] == "not_executable"
    assert plan["toolchain"]["flowguard_status"] == "stale_later_binding"


@pytest.mark.parametrize(
    "member",
    ("researchguard", "logicguard", "sourceguard", "traceguard", "experimentguard"),
)
def test_member_check_input_selectors_are_exactly_unique(member: str) -> None:
    source = json.loads(
        (
            ROOT / "skills" / member / ".skillguard" / "contract-source.json"
        ).read_text(encoding="utf-8")
    )
    for check in source["checks"]:
        identities = [
            json.dumps(selector, ensure_ascii=False, sort_keys=True)
            for selector in check["input_selectors"]
        ]
        assert len(identities) == len(set(identities)), check["check_id"]


def test_consumer_install_transaction_reuses_the_researchguard_native_owner() -> None:
    payload = contract("researchguard")
    checks = {row["check_id"]: row for row in payload["checks"]}
    native = checks["check:researchguard:native-tests"]
    obligation_id = (
        "obligation:researchguard:researchguard:consumer-install-transaction"
    )
    assert native["execution_owner_id"] == (
        "owner:researchguard:researchguard:native-tests"
    )
    assert native["covers_obligation_ids"] == [
        "obligation:researchguard:researchguard:native-tests",
        obligation_id,
    ]
    assert obligation_id in payload["closure_profiles"][0]["required_obligation_ids"]

    model_path = ROOT / ".flowguard/researchguard_skill_contract_model_common.py"
    spec = importlib.util.spec_from_file_location(
        "researchguard_contract_model_common_under_test", model_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    model = module.build_contract_model("researchguard")
    obligation = next(
        row for row in model["obligations"] if row["obligation_id"] == obligation_id
    )
    assert obligation["owner_step_ids"] == [
        "step:researchguard:researchguard:tests"
    ]
