"""Audit the current five-member SkillGuard v3 contract mesh.

This is a read-only structural audit.  It checks the generated v3 contracts,
their four-step validation routes, portable consumer projections, and the
single unit-level test-mesh definition.  It does not run a member check or
claim a receipt.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_UNIT_ID = "unit:researchguard-suite"
EXPECTED_MEMBERS = (
    "researchguard",
    "logicguard",
    "sourceguard",
    "traceguard",
    "experimentguard",
)
CHECK_KINDS = ("consumer-contract", "prompt-load", "native-tests", "task-model-closure")
INSTALL_OBLIGATION_ID = "obligation:researchguard:consumer-install-transaction"
TEST_MESH_MAINTENANCE_INPUTS = (".skillguard/test-mesh.json", "scripts/check_researchguard_test_mesh.py")
UNIT_TEST_MESH_PROJECTION_ID = "projection:researchguard-suite-maintenance-definition"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path}")
    return value


def _record(findings: list[dict[str, str]], condition: bool, code: str, detail: str) -> None:
    if not condition:
        findings.append({"code": code, "detail": detail})


def _check_member(root: Path, member: str, findings: list[dict[str, str]]) -> dict[str, Any]:
    control = root / "skills" / member / ".skillguard"
    source = _load_json(control / "contract-source.json")
    compiled = _load_json(control / "compiled-contract.json")
    manifest = _load_json(control / "check-manifest.json")
    _record(findings, source.get("schema_version") == "skillguard.skill_contract.v3", "source_schema_invalid", member)
    _record(findings, compiled.get("schema_version") == "skillguard.compiled_contract.v3", "compiled_schema_invalid", member)
    _record(findings, manifest.get("schema_version") == "skillguard.check_manifest.v3", "manifest_schema_invalid", member)
    for label, payload in (("source", source), ("compiled", compiled), ("manifest", manifest)):
        _record(findings, payload.get("skill_id") == member, "member_skill_identity_mismatch", f"{member}:{label}")
        if "maintenance_unit_id" in payload:
            _record(findings, payload.get("maintenance_unit_id") == EXPECTED_UNIT_ID, "maintenance_unit_identity_mismatch", f"{member}:{label}")
        if "member_skill_ids" in payload:
            _record(findings, payload.get("member_skill_ids") == [member], "member_inventory_invalid", f"{member}:{label}")

    expected_checks = {f"check:{member}:{kind}" for kind in CHECK_KINDS}
    source_checks = {str(row.get("check_id")) for row in source.get("checks", []) if isinstance(row, dict)}
    compiled_checks = {str(row.get("check_id")) for row in compiled.get("checks", []) if isinstance(row, dict)}
    manifest_checks = {str(row.get("check_id")) for row in manifest.get("checks", []) if isinstance(row, dict)}
    _record(findings, source_checks == compiled_checks == manifest_checks == expected_checks, "check_inventory_projection_mismatch", member)

    input_ids = {str(row.get("id")) for row in source.get("inputs", []) if isinstance(row, dict)}
    input_paths = {str(row.get("path")) for row in source.get("inputs", []) if isinstance(row, dict)}
    _record(findings, len(input_ids) == len(source.get("inputs", [])), "duplicate_input_ids", member)
    _record(findings, all(set(row.get("input_ids", [])) <= input_ids for row in source.get("checks", []) if isinstance(row, dict)), "check_input_reference_invalid", member)
    _record(findings, all("\\" not in path and not Path(path).is_absolute() for path in input_paths), "nonportable_input_path", member)
    _record(findings, all((root / "skills" / member / path).is_file() for path in input_paths), "missing_contract_input", member)

    steps = source.get("steps", [])
    route = source.get("routes", [{}])[0] if source.get("routes") else {}
    ordered_steps = list(route.get("step_ids", [])) if isinstance(route, dict) else []
    step_by_id = {str(row.get("step_id")): row for row in steps if isinstance(row, dict)}
    _record(findings, len(source.get("routes", [])) == 1 and ordered_steps == [f"step:{member}:{kind}" for kind in CHECK_KINDS], "route_shape_invalid", member)
    expected_requires = [[], [ordered_steps[0]] if ordered_steps else [], [ordered_steps[1]] if len(ordered_steps) > 1 else [], [ordered_steps[2]] if len(ordered_steps) > 2 else []]
    _record(findings, [step_by_id.get(step_id, {}).get("requires", []) for step_id in ordered_steps] == expected_requires, "step_dependency_chain_invalid", member)
    obligations = {str(row.get("obligation_id")) for row in source.get("obligations", []) if isinstance(row, dict)}
    expected_obligations = {f"obligation:{member}:{kind}" for kind in CHECK_KINDS}
    if member == "researchguard":
        expected_obligations.add(INSTALL_OBLIGATION_ID)
    _record(findings, obligations == expected_obligations, "obligation_inventory_invalid", member)
    _record(findings, manifest.get("contract_hash") == compiled.get("contract_hash"), "manifest_contract_hash_mismatch", member)
    plan = compiled.get("content_impact_plan", {})
    _record(findings, plan.get("schema_version") == "skillguard.content_impact_plan.v3", "content_impact_plan_schema_invalid", member)
    inventory_paths = {str(row.get("path")) for row in plan.get("inventory", []) if isinstance(row, dict)}
    _record(findings, inventory_paths <= input_paths, "content_inventory_outside_inputs", member)
    _record(findings, all(row.get("install_disposition") == "copy" for row in plan.get("inventory", []) if isinstance(row, dict)), "content_inventory_install_disposition_invalid", member)
    projection_paths = set(source.get("consumer_projection", {}).get("file_paths", []))
    _record(findings, projection_paths == inventory_paths, "consumer_projection_inventory_mismatch", member)

    return {
        "member_skill_id": member,
        "check_owner_count": len(expected_checks),
        "evidence_subject_count": len(expected_checks),
        "evidence_domain_count": len(expected_checks),
        "closure_profile_id": "enforced",
        "plan_only_static_eligibility": "eligible_after_legitimate_claimed_run",
        "obligation_count": len(obligations),
    }


def audit(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    findings: list[dict[str, str]] = []
    mesh_path = root / ".skillguard" / "test-mesh.json"
    mesh = _load_json(mesh_path)
    _record(findings, mesh.get("schema_version") == "skillguard.test_mesh_manifest.current", "unit_test_mesh_schema_invalid", "")
    _record(findings, mesh.get("mesh_id") == "researchguard-suite-owner-receipt-mesh", "unit_test_mesh_identity_invalid", "")
    all_mesh_paths = sorted(path.relative_to(root).as_posix() for path in root.rglob("test-mesh.json") if ".skillguard" in path.parts and ".git" not in path.parts)
    _record(findings, all_mesh_paths == [".skillguard/test-mesh.json"], "unit_test_mesh_authority_not_unique", ",".join(all_mesh_paths))
    member_results = [_check_member(root, member, findings) for member in EXPECTED_MEMBERS]
    status = "pass" if not findings else "blocked"
    for row in member_results:
        row["plan_only_static_eligibility"] = "eligible_after_legitimate_claimed_run" if status == "pass" else "blocked"
    return {
        "schema_version": "researchguard.skillguard_test_mesh_static_audit.v2",
        "status": status,
        "findings": findings,
        "maintenance_unit_id": EXPECTED_UNIT_ID,
        "mesh_id": mesh.get("mesh_id", ""),
        "member_count": len(EXPECTED_MEMBERS),
        "check_owner_count": sum(row["check_owner_count"] for row in member_results),
        "evidence_subject_count": sum(row["evidence_subject_count"] for row in member_results),
        "evidence_domain_count": sum(row["evidence_domain_count"] for row in member_results),
        "obligation_count": sum(row["obligation_count"] for row in member_results),
        "execution_count": 0,
        "plan_only_execution_status": "not_run",
        "unknown_mapping_disposition": "block",
        "member_results": member_results,
        "source_maintenance_projection": {
            "consumer_id": UNIT_TEST_MESH_PROJECTION_ID,
            "paths": sorted(TEST_MESH_MAINTENANCE_INPUTS),
            "semantic_owner_selection": [],
            "required_next_action_on_change": "regenerate and compile all five member contracts; after one legitimate current claimed run for each member, freeze five member-specific plan_only plans",
        },
        "generator_impact": {
            "direct_semantic_owner_ids": [],
            "disposition": "v3 member contracts are generated artifacts; this read-only audit does not create a second execution owner",
        },
        "consumer_install_transaction": {
            "obligation_id": INSTALL_OBLIGATION_ID,
            "execution_owner_id": "member-native-check:researchguard",
            "source_only_paths": ["scripts/install_researchguard.py", "tests/test_install_researchguard.py"],
        },
        "installation_boundaries": [
            {"member_skill_id": member, "release_manifest_path": "consumer-release.json", "installation_projection_id": "projection:consumer-distribution"}
            for member in EXPECTED_MEMBERS
        ],
    }


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
