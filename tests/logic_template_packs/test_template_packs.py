from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil
from typing import Any

import pytest

import researchguard.logic_template_packs.builder as builder_module
from researchguard.logic_template_packs import (
    CatalogValidationError,
    REQUIRED_FAMILIES,
    TemplateRequest,
    build_template_instance,
    default_catalog_root,
    load_catalog,
    select_template_pack,
)
from researchguard.logic_template_packs.canonical import canonical_sha256
from researchguard.logic_template_packs.catalog import catalog_digest_payload
from researchguard.logic_template_packs.native_validators import (
    ALLOWED_BINDINGS,
    callable_fingerprint,
    resolve_callable,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
CATALOG_ROOT = default_catalog_root()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


FIXTURE_MANIFEST = _read_json(FIXTURE_ROOT / "manifest.json")
FIXTURE_ENTRIES = tuple(FIXTURE_MANIFEST["cases"])


def _request(payload: dict[str, Any]) -> TemplateRequest:
    return TemplateRequest.create(
        purpose=payload["purpose"],
        capabilities=payload["capabilities"],
        context_tags=payload["context_tags"],
        allow_base=payload["allow_base"],
        parameters=payload["parameters"],
    )


def _finding_codes(items) -> list[str]:
    return [item.code for item in items]


def _assert_request_case(case: dict[str, Any], catalog=None):
    catalog = catalog or load_catalog()
    selection = select_template_pack(catalog, _request(case["request"]))
    expected = case["expected"]
    assert selection.decision == expected["decision"]
    assert list(selection.candidate_ids) == expected["candidate_ids"]
    assert list(selection.selected_profile_ids) == expected["selected_profile_ids"]
    assert _finding_codes(selection.findings) == expected["finding_codes"]

    result = build_template_instance(catalog, selection)
    assert result.status == expected["build_status"]
    if result.status == "valid":
        assert result.instance is not None
        instance = result.instance
        assert not instance.findings
        assert len(instance.fields) == len(instance.field_owners)
        assert set(dict(instance.field_owners).values()) == set(
            selection.selected_profile_ids
        )
        expected_validator_ids = {
            "logicguard-template-pack:structure",
            *(
                binding.validator_id
                for profile_id in selection.selected_profile_ids
                for binding in catalog.profile(profile_id).native_binding.validators
            ),
        }
        assert {
            observation.validator_id
            for observation in instance.validator_observations
        } == expected_validator_ids
        assert all(
            observation.status == "pass"
            for observation in instance.validator_observations
        )
    else:
        assert result.instance is None
    return selection, result


def _apply_operation(document: dict[str, Any], operation: dict[str, Any]) -> None:
    path = operation["path"]
    assert path
    owner: dict[str, Any] = document
    for segment in path[:-1]:
        child = owner[segment]
        assert isinstance(child, dict)
        owner = child
    if operation["op"] == "set":
        owner[path[-1]] = operation["value"]
    elif operation["op"] == "remove":
        del owner[path[-1]]
    else:
        raise AssertionError(f"unsupported fixture mutation: {operation['op']}")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _mutated_catalog(tmp_path: Path, case: dict[str, Any]) -> Path:
    root = tmp_path / case["case_id"]
    shutil.copytree(CATALOG_ROOT, root)
    target = root.joinpath(*case["target"].split("/"))
    document = _read_json(target)
    for operation in case["operations"]:
        _apply_operation(document, operation)
    _write_json(target, document)

    manifest_path = root / "manifest.json"
    manifest = document if target == manifest_path else _read_json(manifest_path)
    if case["recompute_profile_digest"]:
        assert case["target"].startswith("profiles/")
        profile_digest = canonical_sha256(document)
        matching_entries = [
            entry
            for entry in manifest["profiles"]
            if entry["path"] == case["target"]
        ]
        assert len(matching_entries) == 1
        matching_entries[0]["sha256"] = profile_digest
    if case["recompute_catalog_digest"]:
        manifest["catalog_digest"] = canonical_sha256(
            catalog_digest_payload(manifest)
        )
    if manifest is not document or case["recompute_catalog_digest"]:
        _write_json(manifest_path, manifest)
    return root


def test_fixture_inventory_is_exact_sorted_and_unique() -> None:
    assert FIXTURE_MANIFEST["schema"] == "researchguard.logic.template-pack-fixtures.v1"
    case_ids = [entry["case_id"] for entry in FIXTURE_ENTRIES]
    paths = [entry["path"] for entry in FIXTURE_ENTRIES]
    assert case_ids == sorted(case_ids)
    assert len(case_ids) == len(set(case_ids))
    assert len(paths) == len(set(paths))
    assert all(set(entry) == {"case_id", "kind", "path"} for entry in FIXTURE_ENTRIES)
    actual_paths = {
        path.relative_to(FIXTURE_ROOT).as_posix()
        for path in (FIXTURE_ROOT / "cases").glob("*.json")
    }
    assert set(paths) == actual_paths
    for entry in FIXTURE_ENTRIES:
        case = _read_json(FIXTURE_ROOT / entry["path"])
        assert case["case_id"] == entry["case_id"]
        assert case["kind"] == entry["kind"]


@pytest.mark.parametrize(
    "entry",
    FIXTURE_ENTRIES,
    ids=[entry["case_id"] for entry in FIXTURE_ENTRIES],
)
def test_every_governed_fixture_reaches_exact_terminal(
    entry: dict[str, Any], tmp_path: Path
) -> None:
    case = _read_json(FIXTURE_ROOT / entry["path"])
    if case["kind"] == "request":
        _assert_request_case(case)
        return

    root = _mutated_catalog(tmp_path, case)
    if case["kind"] == "catalog_mutation":
        with pytest.raises(CatalogValidationError) as caught:
            load_catalog(root)
        assert _finding_codes(caught.value.findings) == case["expected"]["finding_codes"]
        return

    assert case["kind"] == "catalog_request_mutation"
    _assert_request_case(case, load_catalog(root))


def test_catalog_identity_inventory_and_native_bindings_are_deterministic() -> None:
    first = load_catalog()
    second = load_catalog()
    assert first.to_dict() == second.to_dict()
    assert first.catalog_digest == second.catalog_digest
    assert first.required_families == REQUIRED_FAMILIES
    assert [profile.profile_id for profile in first.profiles] == sorted(
        profile.profile_id for profile in first.profiles
    )
    assert len(first.profiles) == len(REQUIRED_FAMILIES) + 1
    for profile in first.profiles:
        allowed = ALLOWED_BINDINGS[profile.family]
        binding = profile.native_binding
        assert binding.route_id == allowed["route_id"]
        assert binding.owner_callable == allowed["owner_callable"]
        assert binding.owner_fingerprint == callable_fingerprint(
            resolve_callable(binding.owner_callable)
        )
        assert {item.validator_id for item in binding.validators} == set(
            allowed["validators"]
        )
        for validator in binding.validators:
            assert validator.callable_ref == allowed["validators"][validator.validator_id]
            assert validator.callable_fingerprint == callable_fingerprint(
                resolve_callable(validator.callable_ref)
            )


def test_request_order_and_duplicate_equivalence_preserve_selection_identity() -> None:
    catalog = load_catalog()
    first = TemplateRequest.create(
        purpose="preserve and deepen",
        capabilities=["source-library", "deepening", "source-library"],
        context_tags=["review", "source-backed", "review"],
        parameters={"b": [2, 1], "a": {"z": 1, "y": 2}},
    )
    second = TemplateRequest.create(
        purpose="preserve and deepen",
        capabilities=["deepening", "source-library"],
        context_tags=["source-backed", "review"],
        parameters={"a": {"y": 2, "z": 1}, "b": [2, 1]},
    )
    assert first == second
    first_selection = select_template_pack(catalog, first)
    second_selection = select_template_pack(catalog, second)
    assert first_selection.to_dict() == second_selection.to_dict()


@pytest.mark.parametrize(
    "overrides",
    (
        {"purpose": 7},
        {"capabilities": ["argument", 7]},
        {"context_tags": [""]},
        {"parameters": {7: "not a portable key"}},
        {"parameters": {"a": 1, " a ": 2}},
    ),
)
def test_request_rejects_silent_type_coercion_and_duplicate_normalized_keys(
    overrides: dict[str, Any],
) -> None:
    arguments: dict[str, Any] = {
        "purpose": "bounded request",
        "capabilities": ["argument"],
        "context_tags": ["review"],
        "parameters": {"root_claim": "claim"},
    }
    arguments.update(overrides)
    with pytest.raises(ValueError):
        TemplateRequest.create(**arguments)


def test_reciprocal_and_cyclic_dominance_fail_closed_before_composition() -> None:
    catalog = load_catalog()
    reciprocal_relations = {
        "researchguard.logic.deepening": ("researchguard.logic.source-library",),
        "researchguard.logic.source-library": ("researchguard.logic.deepening",),
    }
    reciprocal_catalog = replace(
        catalog,
        profiles=tuple(
            replace(profile, strictly_dominates=reciprocal_relations[profile.profile_id])
            if profile.profile_id in reciprocal_relations
            else profile
            for profile in catalog.profiles
        ),
    )
    reciprocal = select_template_pack(
        reciprocal_catalog,
        TemplateRequest.create(
            purpose="reciprocal dominance must not compose",
            capabilities=["source-library", "deepening"],
        ),
    )
    assert reciprocal.decision == "ambiguous"
    assert _finding_codes(reciprocal.findings) == ["multiple_complete_dominators"]

    cycle_relations = {
        "researchguard.logic.argument": ("researchguard.logic.purpose",),
        "researchguard.logic.purpose": ("researchguard.logic.synthesis",),
        "researchguard.logic.synthesis": ("researchguard.logic.argument",),
    }
    cycle_catalog = replace(
        catalog,
        profiles=tuple(
            replace(profile, strictly_dominates=cycle_relations[profile.profile_id])
            if profile.profile_id in cycle_relations
            else profile
            for profile in catalog.profiles
        ),
    )
    cycle = select_template_pack(
        cycle_catalog,
        TemplateRequest.create(
            purpose="cyclic dominance must fail closed",
            capabilities=["argument", "purpose", "synthesis"],
        ),
    )
    assert cycle.decision == "ambiguous"
    assert _finding_codes(cycle.findings) == ["dominance_cycle"]


def test_incomplete_dominance_fails_closed() -> None:
    catalog = load_catalog()
    partial_catalog = replace(
        catalog,
        profiles=tuple(
            replace(profile, strictly_dominates=("researchguard.logic.purpose",))
            if profile.profile_id == "researchguard.logic.argument"
            else profile
            for profile in catalog.profiles
        ),
    )
    selection = select_template_pack(
        partial_catalog,
        TemplateRequest.create(
            purpose="partial dominance must fail closed",
            capabilities=["argument", "purpose", "synthesis"],
        ),
    )
    assert selection.decision == "ambiguous"
    assert _finding_codes(selection.findings) == ["incomplete_dominance"]


def test_instance_identity_field_ledger_and_boundaries_are_complete() -> None:
    case = _read_json(
        FIXTURE_ROOT / "cases" / "good-compose-source-deepening.json"
    )
    catalog = load_catalog()
    selection, first_result = _assert_request_case(case, catalog)
    second_result = build_template_instance(catalog, selection)
    assert first_result.to_dict() == second_result.to_dict()
    instance = first_result.instance
    assert instance is not None
    assert instance.instance_fingerprint == second_result.instance.instance_fingerprint
    assert dict(instance.profile_claim_boundaries) == {
        profile_id: catalog.profile(profile_id).claim_boundary
        for profile_id in selection.selected_profile_ids
    }
    assert "does not prove factual truth" in instance.effective_claim_boundary
    assert "skill installation" in instance.effective_claim_boundary
    assert "future AI behavior" in instance.effective_claim_boundary
    fields = dict(instance.fields)
    owners = dict(instance.field_owners)
    assert set(fields) == set(owners)
    assert all(owner in selection.selected_profile_ids for owner in owners.values())

    changed_request_payload = dict(case["request"])
    changed_parameters = dict(changed_request_payload["parameters"])
    changed_parameters["source_registry"] = ["source-001", "source-003"]
    changed_request_payload["parameters"] = changed_parameters
    changed_selection = select_template_pack(catalog, _request(changed_request_payload))
    changed_result = build_template_instance(catalog, changed_selection)
    assert changed_selection.selected_profile_ids == selection.selected_profile_ids
    assert changed_result.instance is not None
    assert changed_result.instance.instance_fingerprint != instance.instance_fingerprint


def test_builder_blocks_stale_selection_catalog_identity() -> None:
    catalog = load_catalog()
    selection = select_template_pack(
        catalog,
        TemplateRequest.create(
            purpose="one argument",
            capabilities=["argument"],
            parameters={"root_claim": "claim", "acceptance": ["bounded"]},
        ),
    )
    stale_selection = replace(selection, catalog_digest="0" * 64)
    result = build_template_instance(catalog, stale_selection)
    assert result.status == "blocked"
    assert result.instance is None
    assert _finding_codes(result.findings) == ["selection_catalog_mismatch"]


def test_builder_blocks_missing_parameter_and_failed_native_validation() -> None:
    catalog = load_catalog()
    selection = select_template_pack(
        catalog,
        TemplateRequest.create(
            purpose="argument missing acceptance",
            capabilities=["argument"],
            parameters={"root_claim": "claim"},
        ),
    )
    result = build_template_instance(catalog, selection)
    assert result.status == "blocked"
    assert result.instance is not None
    codes = set(_finding_codes(result.findings))
    assert "request_parameter_missing" in codes
    assert "declared_field_not_materialized" in codes
    assert "missing_or_empty:argument.acceptance" in codes
    assert any(
        observation.status == "failed"
        for observation in result.instance.validator_observations
    )


def test_builder_blocks_stale_native_validator_observation(monkeypatch) -> None:
    catalog = load_catalog()
    selection = select_template_pack(
        catalog,
        TemplateRequest.create(
            purpose="one argument",
            capabilities=["argument"],
            parameters={"root_claim": "claim", "acceptance": ["bounded"]},
        ),
    )

    def replacement_validator(_fields):
        return ()

    monkeypatch.setattr(
        builder_module,
        "resolve_callable",
        lambda _callable_ref: replacement_validator,
    )
    result = build_template_instance(catalog, selection)
    assert result.status == "blocked"
    assert result.instance is not None
    assert "stale_native_validator_binding" in _finding_codes(result.findings)
    assert any(
        observation.status == "failed"
        and observation.finding_codes == ("stale_native_validator_binding",)
        for observation in result.instance.validator_observations
    )


def test_catalog_rejects_undeclared_profile_without_fallback(tmp_path: Path) -> None:
    root = tmp_path / "undeclared-profile"
    shutil.copytree(CATALOG_ROOT, root)
    shutil.copy2(root / "profiles" / "argument.json", root / "profiles" / "shadow.json")
    with pytest.raises(CatalogValidationError) as caught:
        load_catalog(root)
    assert _finding_codes(caught.value.findings) == ["profile_inventory_mismatch"]
