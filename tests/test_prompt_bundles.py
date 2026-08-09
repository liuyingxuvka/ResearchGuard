from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

from scripts.build_skillguard_contracts import contract


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_prompt_bundles.py"
SPEC = importlib.util.spec_from_file_location("researchguard_prompt_bundles", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

BLUEPRINT_BOUNDARIES = {
    "researchguard": (
        "route:member-model-envelope",
        "skills/researchguard/references/member-model-envelope.md",
        "composition-transport",
    ),
    "logicguard": (
        "route:domain-blueprint",
        "skills/logicguard/references/domain-blueprint-contract.md",
        "member-domain-dna",
    ),
    "sourceguard": (
        "route:information-blueprint",
        "skills/sourceguard/references/information-blueprint.md",
        "member-domain-dna",
    ),
    "traceguard": (
        "route:trace-blueprint",
        "skills/traceguard/references/trace-blueprint-contract.md",
        "member-domain-dna",
    ),
    "experimentguard": (
        "route:experiment-blueprint",
        "skills/experimentguard/references/experiment-model-protocol.md",
        "member-domain-dna",
    ),
}


def manifest() -> dict:
    return json.loads((ROOT / "researchguard" / "prompt_bundle_manifest.json").read_text(encoding="utf-8"))


def test_current_prompt_bundles_and_index_pass() -> None:
    result = MODULE.check_prompt_bundles()
    assert result["status"] == "pass", result["failures"]
    assert {row["skill_id"] for row in result["bundles"]} == {
        "researchguard", "logicguard", "sourceguard", "traceguard", "experimentguard"
    }
    assert all(row["headroom_bytes"] > 0 for row in result["bundles"])


def test_entry_budget_without_headroom_fails() -> None:
    payload = manifest()
    row = next(row for row in payload["bundles"] if row["skill_id"] == "logicguard")
    row["max_entry_bytes"] = 1
    result = MODULE.check_prompt_bundles(payload)
    assert {row["code"] for row in result["failures"]} >= {
        "entry-budget-exceeded", "entry-headroom-insufficient"
    }


def test_missing_or_untriggered_reference_edge_fails() -> None:
    payload = manifest()
    bad = deepcopy(payload["reference_edges"][0])
    bad["trigger_id"] = "trigger:not-declared"
    payload["reference_edges"].append(bad)
    result = MODULE.check_prompt_bundles(payload)
    assert "reference-edge-undeclared" in {row["code"] for row in result["failures"]}


def test_generated_member_index_is_exact() -> None:
    index = ROOT / "skills" / "researchguard" / "references" / "member-admission-index.md"
    assert index.read_text(encoding="utf-8") == MODULE.render_member_admission_index()


def test_manifest_forbids_eager_sibling_skill_paths() -> None:
    payload = manifest()
    prohibited = set(payload["prohibited_eager_member_paths"])
    umbrella = (ROOT / "skills" / "researchguard" / "SKILL.md").read_text(encoding="utf-8")
    assert prohibited.isdisjoint(path for path in prohibited if path in umbrella)


def test_blueprint_references_are_conditionally_reachable_without_eager_detail() -> None:
    payload = manifest()
    expected = {
        (skill_id, trigger_id): reference
        for skill_id, (trigger_id, reference, _role) in BLUEPRINT_BOUNDARIES.items()
    }
    actual = {
        (row["skill_id"], row["trigger_id"]): row["reference"]
        for row in payload["reference_edges"]
    }
    assert {key: actual[key] for key in expected} == expected
    for reference in expected.values():
        assert (ROOT / reference).is_file()

    boundary_rows = {
        row["skill_id"]: (row["trigger_id"], row["reference"], row["role"])
        for row in payload["conditional_blueprint_boundaries"]
    }
    assert boundary_rows == BLUEPRINT_BOUNDARIES
    bundles = {row["skill_id"]: row for row in payload["bundles"]}
    for skill_id, (_trigger_id, reference, role) in BLUEPRINT_BOUNDARIES.items():
        entry_text = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in bundles[skill_id]["entry_files"]
        )
        reference_text = (ROOT / reference).read_text(encoding="utf-8")
        for term in (
            "member-domain DNA",
            "ResearchGuard repository software-DNA root",
            "FlowGuard-owned",
        ):
            assert term in entry_text
            assert term in reference_text
        assert ("composition transport" in reference_text) is (
            role == "composition-transport"
        )
        assert not any(
            term in entry_text
            for term in payload["prohibited_eager_self_dna_terms"]
        )

    detailed_contract_terms = {
        "producer_native_receipt_fingerprint",
        "required_procedure_step_ids",
        "observation_receipt_fingerprint",
        "consumer-payload-fingerprint-mismatch",
    }
    entry_text = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for bundle in payload["bundles"]
        for path in bundle["entry_files"]
        if path.endswith(("SKILL.md", "openai.yaml"))
    )
    assert not any(term in entry_text for term in detailed_contract_terms)


def test_blueprint_boundary_manifest_mismatch_and_eager_detail_fail() -> None:
    payload = manifest()
    payload["conditional_blueprint_boundaries"][0]["reference"] = (
        "skills/researchguard/references/member-admission-index.md"
    )
    result = MODULE.check_prompt_bundles(payload)
    assert "blueprint-boundary-edge-missing" in {
        row["code"] for row in result["failures"]
    }

    payload = manifest()
    payload["prohibited_eager_self_dna_terms"].append("member-domain DNA")
    result = MODULE.check_prompt_bundles(payload)
    assert "blueprint-self-dna-detail-eager" in {
        row["code"] for row in result["failures"]
    }


def test_reported_prompt_byte_totals_equal_exact_entry_files() -> None:
    payload = manifest()
    result = MODULE.check_prompt_bundles(payload)
    by_skill = {row["skill_id"]: row for row in result["bundles"]}
    for bundle in payload["bundles"]:
        expected_bytes = sum(len((ROOT / path).read_bytes()) for path in bundle["entry_files"])
        assert by_skill[bundle["skill_id"]]["entry_bytes"] == expected_bytes


def test_prompt_governance_has_one_declared_execution_path() -> None:
    manifest_checker_paths = {
        "researchguard/prompt_bundle_manifest.json",
        "scripts/check_prompt_bundles.py",
    }
    prompt_test_path = "tests/test_prompt_bundles.py"
    for member in (
        "researchguard",
        "logicguard",
        "sourceguard",
        "traceguard",
        "experimentguard",
    ):
        payload = contract(member)
        stored_payload = json.loads(
            (
                ROOT
                / "skills"
                / member
                / ".skillguard"
                / "contract-source.json"
            ).read_text(encoding="utf-8")
        )
        checks = {row["check_id"]: row for row in payload["checks"]}
        stored_checks = {
            row["check_id"]: row for row in stored_payload["checks"]
        }
        prompt = checks[f"check:{member}:prompt-load"]
        native = checks[f"check:{member}:native-tests"]
        stored_prompt = stored_checks[f"check:{member}:prompt-load"]
        stored_native = stored_checks[f"check:{member}:native-tests"]
        implementation_paths = payload["implementation_paths"]
        stored_implementation_paths = stored_payload["implementation_paths"]
        assert stored_prompt["input_selectors"] == prompt["input_selectors"]
        assert stored_native["args"] == native["args"]
        governed_source_paths = manifest_checker_paths | {
            prompt_test_path,
            "tests/test_skill_suite.py",
            BLUEPRINT_BOUNDARIES[member][1],
        }
        assert {
            path
            for path in stored_implementation_paths
            if path in governed_source_paths
        } == {
            path for path in implementation_paths if path in governed_source_paths
        }
        assert all(
            implementation_paths.count(path) == 1
            for path in manifest_checker_paths
        )
        prompt_paths = {
            row["path"]
            for row in prompt["input_selectors"]
            if row["kind"] == "path"
        }
        assert manifest_checker_paths <= prompt_paths
        assert prompt_test_path not in prompt_paths
        assert {
            check_id
            for check_id, check in checks.items()
            if manifest_checker_paths.intersection(
                row["path"]
                for row in check["input_selectors"]
                if row["kind"] == "path"
            )
        } == {f"check:{member}:prompt-load"}
        assert (prompt_test_path in native["args"]) is (member == "researchguard")
        assert {
            check_id
            for check_id, check in checks.items()
            if prompt_test_path
            in {
                row["path"]
                for row in check["input_selectors"]
                if row["kind"] == "path"
            }
        } == (
            {f"check:{member}:native-tests"}
            if member == "researchguard"
            else set()
        )
        assert (prompt_test_path in implementation_paths) is (
            member == "researchguard"
        )

    suite_checker = (ROOT / "scripts/check_researchguard_suite.py").read_text(
        encoding="utf-8"
    )
    assert "check_prompt_bundles.py" not in suite_checker
