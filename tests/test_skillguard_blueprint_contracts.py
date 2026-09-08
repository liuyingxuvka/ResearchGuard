from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.build_skillguard_contracts import (
    BLUEPRINT_COMPONENTS,
    IMPLEMENTATION_PATHS,
    MEMBERS,
    contract,
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


def _check_index(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        str(item["check_id"]): item
        for item in payload["checks"]  # type: ignore[index]
    }


def _component_for_path(plan: dict[str, object], path: str) -> dict[str, object]:
    matches = [
        item
        for item in plan["components"]  # type: ignore[index]
        if path in item["member_paths"]
    ]
    assert len(matches) == 1, (path, matches)
    return matches[0]


@pytest.mark.parametrize(
    "member",
    ("researchguard", "logicguard", "sourceguard", "traceguard", "experimentguard"),
)
def test_contract_keeps_one_native_owner_with_exact_blueprint_components(member: str) -> None:
    payload = contract(member)
    checks = _check_index(payload)
    expected_ids = {
        f"check:{member}:consumer-contract",
        f"check:{member}:prompt-load",
        f"check:{member}:native-tests",
        f"check:{member}:task-model-closure",
    }
    assert set(checks) == expected_ids
    assert checks[f"check:{member}:prompt-load"]["depends_on_check_ids"] == [
        f"check:{member}:consumer-contract"
    ]
    assert {
        row["execution_owner_id"] for row in checks.values()
    } == {
        f"owner:researchguard:{member}:consumer-contract",
        f"owner:researchguard:{member}:prompt-load",
        f"owner:researchguard:{member}:native-tests",
        f"owner:researchguard:{member}:task-model-closure",
    }

    native = checks[f"check:{member}:native-tests"]
    assert native["execution_owner_id"] == f"owner:researchguard:{member}:native-tests"
    install_obligation = (
        "obligation:researchguard:researchguard:consumer-install-transaction"
    )
    expected_native_obligations = [
        f"obligation:researchguard:{member}:native-tests",
        *([install_obligation] if member == "researchguard" else []),
    ]
    assert native["covers_obligation_ids"] == expected_native_obligations
    assert {
        row["execution_owner_id"]
        for row in checks.values()
        if install_obligation in row["covers_obligation_ids"]
    } == (
        {"owner:researchguard:researchguard:native-tests"}
        if member == "researchguard"
        else set()
    )
    rationale = str(native["coverage_rationale"])
    for phrase in (
        "native qualification",
        "impact and reverse trace",
        "fresh-process target-authority replay",
        "self-attestation rejection",
        "without adding duplicate execution owners",
    ):
        assert phrase in rationale

    selectors = {
        (str(item["kind"]), str(item["path"]))
        for item in native["input_selectors"]
    }
    blueprint = BLUEPRINT_COMPONENTS[member]
    for path in [*blueprint["runtime"], *blueprint["tests"]]:
        assert ("path", path) in selectors
    assert not any(path.startswith(".flowguard/") for _kind, path in selectors)

    implementation_paths = set(payload["implementation_paths"])
    assert blueprint["reference"] in implementation_paths
    assert set(blueprint["runtime"]).issubset(implementation_paths)
    assert set(blueprint["tests"]).issubset(implementation_paths)
    assert any(path.startswith(".flowguard/") for path in IMPLEMENTATION_PATHS[member])

    depth_ids = set(payload["depth_profile"]["native_check_ids"])
    readiness_ids = set(
        payload["depth_profile"]["provider_runtime"]["readiness_check_ids"]
    )
    assert depth_ids == expected_ids
    assert readiness_ids == expected_ids


@pytest.mark.parametrize(
    "member",
    ("researchguard", "logicguard", "sourceguard", "traceguard", "experimentguard"),
)
def test_compiled_component_map_is_member_exact_and_never_run_all(member: str) -> None:
    compiled = json.loads(
        (ROOT / "skills" / member / ".skillguard" / "compiled-contract.json").read_text(
            encoding="utf-8"
        )
    )
    plan = compiled["content_impact_plan"]
    assert plan["unknown_mapping_disposition"] == "block"
    assert plan["all_owner_component_ids"] == []
    assert all(not values for values in plan["health"].values())
    assert len(compiled["checks"]) == 4

    native_owner = f"owner:researchguard:{member}:native-tests"
    foreign_owner_prefixes = {
        f"owner:researchguard:{other}:" for other in MEMBERS if other != member
    }
    blueprint = BLUEPRINT_COMPONENTS[member]
    for path in [*blueprint["runtime"], *blueprint["tests"]]:
        component = _component_for_path(plan, path)
        consumers = set(component["consumer_ids"])
        assert native_owner in consumers
        assert not any(
            any(consumer.startswith(prefix) for prefix in foreign_owner_prefixes)
            for consumer in consumers
        )

    for component in plan["components"]:
        if any(path.startswith(".flowguard/") for path in component["member_paths"]):
            assert native_owner not in component["consumer_ids"]

    reference_component = _component_for_path(plan, blueprint["reference"])
    assert f"owner:researchguard:{member}:prompt-load" in reference_component[
        "consumer_ids"
    ]


@pytest.mark.parametrize(
    "member",
    ("researchguard", "logicguard", "sourceguard", "traceguard", "experimentguard"),
)
def test_blueprint_evidence_categories_are_real_pytest_nodes(member: str) -> None:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "src"), str(ROOT / "tests"), env.get("PYTHONPATH", "")]
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *BLUEPRINT_COMPONENTS[member]["tests"],
            "--collect-only",
            "-vv",
        ],
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
