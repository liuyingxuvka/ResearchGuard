from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.build_skillguard_contracts import (
    BLUEPRINT_COMPONENTS,
    MEMBERS,
    _skillguard_source_fingerprint,
)


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_BLUEPRINT_TESTS = {
    "researchguard": {
        "test_opaque_envelope_accepts_non_json_bytes_and_can_omit_payload_transport",
        "test_composition_impact_is_exact_transitive_and_atomically_suppresses_unknown",
        "test_reverse_trace_stops_at_native_receipts_and_rejects_empty_terminal",
        "test_fresh_process_rejects_all_caller_forged_self_hashed_attestations",
        "test_caller_self_reported_passed_envelopes_are_not_native_attestation",
    },
    "logicguard": {
        "test_child_output_closes_exact_parent_input",
        "test_logic_impact_without_current_qualification_is_atomically_blocked",
        "test_reverse_trace_preserves_argument_and_source_boundary",
        "test_serialized_logic_authority_replays_without_process_registry",
        "test_simultaneous_inventory_authority_shrink_cannot_self_sign_complete",
    },
    "sourceguard": {
        "test_complete_information_blueprint_closes_every_typed_interface",
        "test_source_impact_without_current_qualification_is_atomically_blocked",
        "test_reverse_trace_and_export_round_trip_are_deterministic",
        "test_serialized_source_authority_replays_without_process_registry",
        "test_simultaneous_information_blueprint_authority_shrink_cannot_self_sign_complete",
    },
    "traceguard": {
        "test_current_blueprint_has_deterministic_complete_hierarchy",
        "test_trace_impact_without_current_qualification_is_atomically_blocked",
        "test_reverse_trace_contains_retrieval_transform_causal_and_alternative_boundaries",
        "test_serialized_trace_authority_replays_without_process_registry",
        "test_simultaneous_trace_model_universe_authority_shrink_cannot_self_sign_complete",
    },
    "experimentguard": {
        "test_complete_blueprint_is_rooted_deterministic_and_external",
        "test_impact_and_reverse_trace_follow_same_design_identities",
        "test_reverse_trace_exposes_current_child_output_parent_input_receipts",
        "test_serialized_experiment_authority_replays_without_process_registry",
        "test_simultaneous_model_universe_authority_shrink_cannot_self_sign_complete",
    },
}


def _payloads(member: str) -> tuple[dict, dict, dict]:
    base = ROOT / "skills" / member / ".skillguard"
    return tuple(
        json.loads((base / name).read_text(encoding="utf-8"))
        for name in ("contract-source.json", "compiled-contract.json", "check-manifest.json")
    )  # type: ignore[return-value]


@pytest.mark.parametrize("member", MEMBERS)
def test_compact_v2_contract_keeps_one_sequential_route(member: str) -> None:
    source, compiled, manifest = _payloads(member)
    check_ids = {f"check:{member}:{kind}" for kind in (
        "consumer-contract", "prompt-load", "native-tests", "task-model-closure"
    )}
    assert source["schema_version"] == "skillguard.contract_source.v2"
    assert compiled["schema_version"] == "skillguard.compiled_contract.v2"
    assert manifest["schema_version"] == "skillguard.check_manifest.v2"
    assert source["member_skill_ids"] == list(MEMBERS)
    assert compiled["member_skill_ids"] == list(MEMBERS)
    assert {row["check_id"] for row in source["checks"]} == check_ids
    assert {row["check_id"] for row in compiled["checks"]} == check_ids
    assert {row["check_id"] for row in manifest["checks"]} == check_ids
    assert source["checks"][0]["timeout_seconds"] == 300
    assert source["checks"][1]["timeout_seconds"] == 60
    assert source["native_route_bindings"][0]["native_route_id"] == f"route:researchguard:{member}"
    assert [row["step_id"] for row in source["step_bindings"]] == [
        f"step:researchguard:{member}:contract",
        f"step:researchguard:{member}:prompt-load",
        f"step:researchguard:{member}:tests",
        f"step:researchguard:{member}:task-model-closure",
    ]
    assert all("input_selectors" in row for row in source["checks"])
    assert manifest["contract_hash"] == compiled["contract_hash"]
    assert len(manifest["manifest_hash"]) == 64
    assert all(char in "0123456789ABCDEF" for char in manifest["manifest_hash"])


@pytest.mark.parametrize("member", MEMBERS)
def test_compact_v2_content_impact_plan_is_portable_and_copy_scoped(member: str) -> None:
    source, compiled, _manifest = _payloads(member)
    plan = compiled["content_impact_plan"]
    assert plan["schema_version"] == "skillguard.content_impact_plan.current"
    assert plan["unknown_mapping_disposition"] == "block"
    assert plan["policy_id"] == "skillguard.content_impact_policy.current"
    assert all(row["member_paths"] for row in plan["components"])
    assert all(row["install_disposition"] in {"copy", "source_only"} for row in plan["components"])
    assert source["consumer_projection"]["prohibited_path_prefixes"] == [".skillguard/"]


@pytest.mark.parametrize("member", MEMBERS)
def test_blueprint_evidence_categories_are_real_pytest_nodes(member: str) -> None:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "src"), str(ROOT / "tests"), env.get("PYTHONPATH", "")]
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *BLUEPRINT_COMPONENTS[member]["tests"], "--collect-only", "-vv"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for test_name in EXPECTED_BLUEPRINT_TESTS[member]:
        assert test_name in result.stdout


def test_current_flowguard_validation_plan_is_visible_but_not_run() -> None:
    plan = json.loads(
        (ROOT / ".skillguard" / "researchguard-suite-validation-plan.json").read_text(
            encoding="utf-8"
        )
    )
    assert plan["status"] == "current_not_run"
    assert plan["execution_disposition"] == "not_run"
    assert plan["toolchain"]["flowguard_version"] == "0.69.0"
    assert plan["toolchain"]["flowguard_status"] == "current_not_run"
    assert "maintenance-unit-validation-not-run" in plan["stale_reason_codes"]


def test_skillguard_source_fingerprint_resolves_explicit_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projection = tmp_path / "skills" / "skillguard"
    (projection / "scripts").mkdir(parents=True)
    (projection / "SKILL.md").write_text("current", encoding="utf-8")
    (projection / "scripts" / "skillguard_compile.py").write_text(
        "current", encoding="utf-8"
    )
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    fingerprint = _skillguard_source_fingerprint()
    assert fingerprint.startswith("sha256:")
    assert len(fingerprint) == len("sha256:") + 64
