"""Author-side checks for the current compact SkillGuard v3 contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MEMBERS = ("researchguard", "logicguard", "sourceguard", "traceguard", "experimentguard")
LEGACY_FIELDS = {
    "model_path", "functions", "supervision_fragment_refs",
    "portfolio_capability_contracts", "global_prompt", "depth_profile",
    "step_bindings", "native_check_bindings",
}


def _load(member: str, name: str = "contract-source.json") -> dict:
    path = ROOT / "skills" / member / ".skillguard" / name
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("member", MEMBERS)
def test_compact_contract_is_current_and_closed(member: str) -> None:
    source = _load(member)
    compiled = _load(member, "compiled-contract.json")
    manifest = _load(member, "check-manifest.json")
    assert source["schema_version"] == "skillguard.skill_contract.v3"
    assert compiled["schema_version"] == "skillguard.compiled_contract.v3"
    assert manifest["schema_version"] == "skillguard.check_manifest.v3"
    assert not LEGACY_FIELDS.intersection(source)
    checks = {row["check_id"]: row for row in source["checks"]}
    obligations = {row["obligation_id"]: row for row in source["obligations"]}
    steps = {row["step_id"]: row for row in source["steps"]}
    assert set(checks) == {
        f"check:{member}:consumer-contract",
        f"check:{member}:prompt-load",
        f"check:{member}:native-tests",
        f"check:{member}:task-model-closure",
    }
    assert len(obligations) == (5 if member == "researchguard" else 4)
    assert all(set(row["check_ids"]) <= set(checks) for row in obligations.values())
    assert all(
        set(row["check_ids"]) <= set(checks)
        and set(row["requires"]) <= set(steps)
        for row in steps.values()
    )
    route = source["routes"][0]
    assert route["route_id"] == f"route:{member}:current-validation"
    assert route["when"] == [{"fact": "operation", "equals": "validate"}]
    assert set(route["step_ids"]) == set(steps)
    assert set(route["obligation_ids"]) == set(obligations)
    assert {row["check_id"] for row in compiled["checks"]} == set(checks)
    assert {row["check_id"] for row in manifest["checks"]} == set(checks)


@pytest.mark.parametrize("member", MEMBERS)
def test_contract_inputs_and_projection_are_portable(member: str) -> None:
    source = _load(member)
    root = ROOT / "skills" / member
    input_paths = {row["path"] for row in source["inputs"]}
    assert ".skillguard/checks/run_researchguard_check.py" in input_paths
    for row in source["inputs"]:
        path = Path(row["path"])
        assert not path.is_absolute()
        assert ".." not in path.parts
        assert (root / path).is_file(), row["path"]
    projection = source["consumer_projection"]
    assert projection["projection_id"] == "projection:consumer-distribution"
    assert all(not path.startswith(".skillguard/") for path in projection["file_paths"])
    assert set(projection["file_paths"]) <= input_paths


@pytest.mark.parametrize("member", MEMBERS)
def test_v3_check_manifest_has_exact_source_checks(member: str) -> None:
    source = _load(member)
    manifest = _load(member, "check-manifest.json")
    source_by_id = {row["check_id"]: row for row in source["checks"]}
    for row in manifest["checks"]:
        assert row["check_id"] in source_by_id
        assert row["command"] == "{{python}}"
        assert row["expected"] == {"exit_code": 0}
