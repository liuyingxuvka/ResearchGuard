from __future__ import annotations

import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from researchguard.trace.purpose_contract import (
    GuardPurposeContractError,
    bind_task_guard_purpose,
    load_model_mapping,
    load_task_guard_contract,
    prove_task_guard_contract,
    require_current_guard_purpose_binding,
)


ROOT = Path(__file__).resolve().parents[2]
PRIMARY_SKILL = ROOT / "skills" / "traceguard"
GUARD_MODEL_ROOT = ROOT / "src" / "researchguard" / "trace" / "guard_model"
TASK_CONTRACT = ROOT / "examples" / "trace" / "project_radar_task_purpose.json"
TASK_CANDIDATE = ROOT / "examples" / "trace" / "project_radar_hydrogen_trace.yaml"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _copy_task_bundle(tmp_path: Path) -> tuple[Path, Path, Path]:
    target = tmp_path / "target"
    examples = target / "examples"
    guard_model = target / "guard-model"
    examples.mkdir(parents=True)
    guard_model.mkdir()
    shutil.copy2(GUARD_MODEL_ROOT / "contract.json", guard_model / "contract.json")
    for name in (
        "project_radar_task_purpose.json",
        "project_radar_hydrogen_trace.yaml",
        "invalid_source_example.yaml",
        "operation_before_tender_contradiction.yaml",
    ):
        shutil.copy2(ROOT / "examples" / "trace" / name, examples / name)

    contract_path = examples / "project_radar_task_purpose.json"
    candidate_path = examples / "project_radar_hydrogen_trace.yaml"
    candidate = load_model_mapping(candidate_path)
    candidate["metadata"].pop("guard_purpose_contract", None)
    candidate = bind_task_guard_purpose(
        candidate,
        contract_path=contract_path,
        candidate_path=candidate_path,
    )
    candidate_path.write_text(
        yaml.safe_dump(candidate, sort_keys=False),
        encoding="utf-8",
    )
    return target, contract_path, candidate_path


def _assert_contract_error(code: str, function, *args, **kwargs) -> None:
    with pytest.raises(GuardPurposeContractError) as raised:
        function(*args, **kwargs)
    assert raised.value.code == code


def test_repository_guard_model_is_family_baseline_not_production_authority() -> None:
    root = GUARD_MODEL_ROOT
    contract = _json(root / "contract.json")
    oracles = _json(root / "oracles.json")
    good_artifact = _json(root / "known-good.json")
    bad_artifact = _json(root / "known-bad.json")
    good = good_artifact["cases"]
    bad = bad_artifact["cases"]

    assert contract["schema_version"] == "researchguard.trace.guard_family_baseline.v1"
    assert contract["contract_kind"] == "family_baseline"
    assert contract["authority_scope"] == "family_capability_regression"
    assert contract["production_authority"] is False
    assert "candidate_binding_contract" not in contract
    assert all(
        artifact["contract_kind"] == "family_baseline"
        and artifact["authority_scope"] == "family_capability_regression"
        and artifact["production_authority"] is False
        for artifact in (oracles, good_artifact, bad_artifact)
    )

    failure_ids = contract["external_universe"]["failure_class_ids"]
    assert contract["enforcement"] == "enforced"
    assert len(failure_ids) == len(set(failure_ids))
    assert len(good) == 1
    assert len(bad) == len(failure_ids)
    assert {row["failure_class_id"] for row in bad} == set(failure_ids)
    assert all(
        sum(row["failure_class_id"] == failure_id for row in bad) == 1
        for failure_id in failure_ids
    )
    expected_oracles = {"oracle:traceguard:known-good"} | {
        row["native_oracle_id"] for row in contract["failure_classes"]
    }
    assert {row["oracle_id"] for row in oracles["oracles"]} == expected_oracles


def test_task_model_purpose_proves_one_or_multiple_selected_failures(
    tmp_path: Path,
) -> None:
    target, contract_path, _ = _copy_task_bundle(tmp_path)

    multiple = prove_task_guard_contract(
        contract_path,
        family_catalog_path=target / "guard-model" / "contract.json",
    )
    assert multiple["status"] == "passed"
    assert multiple["selected_failure_ids"] == [
        "missing-event-evidence",
        "hidden-temporal-contradiction",
    ]
    assert multiple["known_good_count"] == 1
    assert multiple["known_bad_count"] == 2
    assert all(row["passed"] for row in multiple["observations"])

    one_failure_path = contract_path.with_name("single_failure_task_purpose.json")
    one_failure = _json(contract_path)
    one_failure["contract_id"] = "researchguard.trace.test.single-failure-purpose.v1"
    one_failure["purpose"] = "Prevent this model from accepting unusable event evidence."
    one_failure["selected_failure_ids"] = ["missing-event-evidence"]
    one_failure["known_bad_cases"] = [one_failure["known_bad_cases"][0]]
    _write_json(one_failure_path, one_failure)
    receipt = prove_task_guard_contract(
        one_failure_path,
        family_catalog_path=target / "guard-model" / "contract.json",
    )
    assert receipt["status"] == "passed"
    assert receipt["selected_failure_ids"] == ["missing-event-evidence"]
    assert receipt["known_bad_count"] == 1


def test_task_model_purpose_rejects_missing_or_empty_contract(tmp_path: Path) -> None:
    _assert_contract_error(
        "traceguard_task_purpose_contract_missing",
        load_task_guard_contract,
        tmp_path / "missing.json",
    )

    target, contract_path, _ = _copy_task_bundle(tmp_path)
    contract = _json(contract_path)
    contract["selected_failure_ids"] = []
    contract["known_bad_cases"] = []
    _write_json(contract_path, contract)
    _assert_contract_error(
        "traceguard_task_purpose_failure_universe_empty_or_duplicate",
        prove_task_guard_contract,
        contract_path,
        family_catalog_path=target / "guard-model" / "contract.json",
    )


def test_task_model_purpose_rejects_unknown_or_mismatched_native_oracle(
    tmp_path: Path,
) -> None:
    target, contract_path, _ = _copy_task_bundle(tmp_path)
    contract = _json(contract_path)
    contract["selected_failure_ids"].append("unknown-task-failure")
    _write_json(contract_path, contract)
    _assert_contract_error(
        "traceguard_task_purpose_native_oracle_unknown",
        prove_task_guard_contract,
        contract_path,
        family_catalog_path=target / "guard-model" / "contract.json",
    )

    contract = _json(TASK_CONTRACT)
    contract["known_bad_cases"][0]["native_oracle_id"] = (
        "oracle:traceguard:not-the-family-oracle"
    )
    _write_json(contract_path, contract)
    _assert_contract_error(
        "traceguard_task_purpose_bad_case_invalid",
        prove_task_guard_contract,
        contract_path,
        family_catalog_path=target / "guard-model" / "contract.json",
    )


def test_task_model_purpose_rejects_incomplete_or_duplicate_bad_cases(
    tmp_path: Path,
) -> None:
    target, contract_path, _ = _copy_task_bundle(tmp_path)
    contract = _json(contract_path)
    contract["known_bad_cases"].pop()
    _write_json(contract_path, contract)
    _assert_contract_error(
        "traceguard_task_purpose_bad_case_cardinality_invalid",
        prove_task_guard_contract,
        contract_path,
        family_catalog_path=target / "guard-model" / "contract.json",
    )

    contract = _json(TASK_CONTRACT)
    contract["known_bad_cases"].append(deepcopy(contract["known_bad_cases"][0]))
    _write_json(contract_path, contract)
    _assert_contract_error(
        "traceguard_task_purpose_bad_case_cardinality_invalid",
        prove_task_guard_contract,
        contract_path,
        family_catalog_path=target / "guard-model" / "contract.json",
    )


def test_task_model_purpose_rejects_stale_case_hash(tmp_path: Path) -> None:
    target, contract_path, _ = _copy_task_bundle(tmp_path)
    contract = _json(contract_path)
    contract["known_bad_cases"][0]["model_sha256"] = "0" * 64
    _write_json(contract_path, contract)
    _assert_contract_error(
        "traceguard_task_purpose_case_stale",
        prove_task_guard_contract,
        contract_path,
        family_catalog_path=target / "guard-model" / "contract.json",
    )


def test_candidate_binding_rejects_missing_binding_and_candidate_tamper(
    tmp_path: Path,
) -> None:
    _, _, candidate_path = _copy_task_bundle(tmp_path)
    candidate = load_model_mapping(candidate_path)
    current = require_current_guard_purpose_binding(
        candidate,
        candidate_path=candidate_path,
    )
    assert current["schema_version"] == "researchguard.trace.guard_purpose_binding.v3"
    assert current["contract_ref"].startswith(".researchguard-purpose/")
    bundled_contract = candidate_path.parent / current["contract_ref"]
    assert bundled_contract.is_file()
    assert (bundled_contract.parent / "project_radar_hydrogen_trace.yaml").is_file()
    assert current["selected_failure_ids"] == [
        "missing-event-evidence",
        "hidden-temporal-contradiction",
    ]

    missing = deepcopy(candidate)
    missing["metadata"].pop("guard_purpose_contract")
    _assert_contract_error(
        "traceguard_guard_purpose_binding_missing",
        require_current_guard_purpose_binding,
        missing,
        candidate_path=candidate_path,
    )

    tampered = deepcopy(candidate)
    tampered["traces"][0]["claim"] += " Tampered after purpose proof."
    _assert_contract_error(
        "traceguard_guard_purpose_binding_stale_or_mismatched",
        require_current_guard_purpose_binding,
        tampered,
        candidate_path=candidate_path,
    )

    retired = deepcopy(candidate)
    retired["metadata"]["guard_purpose_contract"]["schema_version"] = (
        "researchguard.trace.guard_purpose_binding.v2"
    )
    _assert_contract_error(
        "traceguard_guard_purpose_binding_stale_or_mismatched",
        require_current_guard_purpose_binding,
        retired,
        candidate_path=candidate_path,
    )
