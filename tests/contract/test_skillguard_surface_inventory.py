"""Author-side checks for the current SkillGuard v2 contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MEMBERS = ("researchguard", "logicguard", "sourceguard", "traceguard", "experimentguard")
LEGACY_FIELDS = {
    "inputs", "obligations", "routes", "steps", "functions",
    "supervision_fragment_refs", "portfolio_capability_contracts",
    "global_prompt",
}


def _load(member: str, name: str = "contract-source.json") -> dict:
    path = ROOT / "skills" / member / ".skillguard" / name
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("member", MEMBERS)
def test_compact_contract_is_current_and_closed(member: str) -> None:
    source = _load(member)
    compiled = _load(member, "compiled-contract.json")
    manifest = _load(member, "check-manifest.json")
    assert source["schema_version"] == "skillguard.contract_source.v2"
    assert compiled["schema_version"] == "skillguard.compiled_contract.v2"
    assert manifest["schema_version"] == "skillguard.check_manifest.v2"
    assert not LEGACY_FIELDS.intersection(source)
    checks = {row["check_id"]: row for row in source["checks"]}
    obligations = {
        obligation_id
        for row in source["checks"]
        for obligation_id in row["covers_obligation_ids"]
    }
    steps = {row["step_id"]: row for row in source["step_bindings"]}
    assert set(checks) == {
        f"check:{member}:consumer-contract",
        f"check:{member}:prompt-load",
        f"check:{member}:native-tests",
        f"check:{member}:task-model-closure",
    }
    assert len(obligations) == (5 if member == "researchguard" else 4)
    assert all(
        set(row["check_ids"]) <= set(checks) for row in steps.values()
    )
    assert source["member_skill_ids"] == list(MEMBERS)
    assert source["native_route_bindings"][0]["native_route_id"] == f"route:researchguard:{member}"
    assert source["depth_profile"]["native_route_ids"] == [f"route:researchguard:{member}"]
    assert set(source["depth_profile"]["native_check_ids"]) == set(checks)
    assert set(compiled["routes"][0]["step_ids"]) == {
        *steps,
        f"step:researchguard:{member}:success",
        f"step:researchguard:{member}:blocked",
    }
    assert {row["check_id"] for row in compiled["checks"]} == set(checks)
    assert {row["check_id"] for row in manifest["checks"]} == set(checks)
    assert all(row["command"] == "python" for row in manifest["checks"])


@pytest.mark.parametrize("member", MEMBERS)
def test_contract_inputs_and_projection_are_portable(member: str) -> None:
    source = _load(member)
    input_paths = {
        row["path"]
        for check in source["checks"]
        for row in check["input_selectors"]
        if row["kind"] in {"path", "subtree"}
    }
    assert f"skills/{member}/SKILL.md" in input_paths
    for raw_path in input_paths:
        path = Path(raw_path)
        assert not path.is_absolute()
        assert ".." not in path.parts
        candidate = ROOT / path
        assert candidate.exists(), raw_path
    projection = source["consumer_projection"]
    assert projection["projection_id"] == "projection:consumer-distribution"
    assert projection["prohibited_path_prefixes"] == [".skillguard/"]
    assert ".skillguard" in projection["prohibited_prompt_tokens"]


@pytest.mark.parametrize("member", MEMBERS)
def test_v2_check_manifest_has_exact_source_checks(member: str) -> None:
    source = _load(member)
    manifest = _load(member, "check-manifest.json")
    source_by_id = {row["check_id"]: row for row in source["checks"]}
    for row in manifest["checks"]:
        assert row["check_id"] in source_by_id
        assert row["command"] == "python"
        assert row["expected"] == {"exit_code": 0}
