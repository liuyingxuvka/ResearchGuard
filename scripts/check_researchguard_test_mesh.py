"""Read-only static audit for the ResearchGuard SkillGuard TestMesh definition.

The checker proves that one unit-level current-format manifest selects the
existing five-member, twenty-owner topology without creating another semantic
owner.  It never claims a run, executes ``plan_only``, launches an owner,
aggregates receipts, or publishes validation evidence.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "scripts" / "build_skillguard_contracts.py"
EXPECTED_UNIT_ID = "unit:researchguard-suite"
EXPECTED_MEMBERS = (
    "researchguard",
    "logicguard",
    "sourceguard",
    "traceguard",
    "experimentguard",
)
CHECK_KINDS = (
    "consumer-contract",
    "prompt-load",
    "native-tests",
    "task-model-closure",
)
DEPENDENCY_KINDS = {
    "consumer-contract": (),
    "prompt-load": ("consumer-contract",),
    "native-tests": ("prompt-load",),
    "task-model-closure": ("native-tests",),
}
EXPECTED_OWNER_COUNT = 20
EXPECTED_OBLIGATION_COUNT = 21
INSTALL_OBLIGATION_ID = (
    "obligation:researchguard:researchguard:consumer-install-transaction"
)
INSTALL_TRANSACTION_PATHS = {
    "scripts/install_researchguard.py",
    "tests/test_install_researchguard.py",
}
PROMPT_MANIFEST_CHECKER_PATHS = {
    "researchguard/prompt_bundle_manifest.json",
    "scripts/check_prompt_bundles.py",
}
PROMPT_TEST_PATH = "tests/test_prompt_bundles.py"
EXPECTED_HEALTH_FIELDS = {
    "ambiguous_role_paths",
    "dependency_parse_errors",
    "duplicate_owner_ids",
    "invalid_dependency_edges",
    "owner_cycles",
    "unmapped_paths",
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path.relative_to(ROOT).as_posix()}")
    return value


def _load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "researchguard_contract_generator_for_test_mesh", GENERATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise ValueError("generator_import_spec_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record(
    findings: list[dict[str, str]], condition: bool, code: str, detail: str
) -> None:
    if not condition:
        findings.append({"code": code, "detail": detail})


def _rows_by_id(
    rows: object,
    key: str,
    findings: list[dict[str, str]],
    scope: str,
) -> dict[str, Mapping[str, Any]]:
    if not isinstance(rows, list):
        findings.append({"code": f"{scope}_rows_invalid", "detail": key})
        return {}
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            findings.append({"code": f"{scope}_row_invalid", "detail": key})
            continue
        row_id = str(row.get(key, ""))
        if not row_id or row_id in indexed:
            findings.append(
                {"code": f"{scope}_id_missing_or_duplicate", "detail": row_id}
            )
            continue
        indexed[row_id] = row
    return indexed


def _selector_paths(row: Mapping[str, Any]) -> set[str]:
    selectors = row.get("input_selectors", [])
    if not isinstance(selectors, list):
        return set()
    return {
        str(selector.get("path", ""))
        for selector in selectors
        if isinstance(selector, Mapping)
        and selector.get("kind") == "path"
        and selector.get("path")
    }


def _selectors_are_unique(row: Mapping[str, Any]) -> bool:
    selectors = row.get("input_selectors", [])
    if not isinstance(selectors, list):
        return False
    identities: list[str] = []
    for selector in selectors:
        if not isinstance(selector, Mapping):
            return False
        identities.append(
            json.dumps(dict(selector), ensure_ascii=False, sort_keys=True)
        )
    return len(identities) == len(set(identities))


def _selector_covers_path(selector: Mapping[str, Any], path: str) -> bool:
    kind = selector.get("kind")
    selected = str(selector.get("path", "")).rstrip("/")
    if kind == "path":
        return selected == path
    if kind == "subtree":
        return selected in {"", "."} or path == selected or path.startswith(
            selected + "/"
        )
    return False


def _row_selects_any_path(row: Mapping[str, Any], paths: set[str]) -> bool:
    selectors = row.get("input_selectors", [])
    return isinstance(selectors, list) and any(
        isinstance(selector, Mapping)
        and any(_selector_covers_path(selector, path) for path in paths)
        for selector in selectors
    )


def _component_paths(
    plan: Mapping[str, Any], findings: list[dict[str, str]], member: str
) -> tuple[dict[str, Mapping[str, Any]], dict[str, str]]:
    components = _rows_by_id(
        plan.get("components"), "component_id", findings, f"{member}:components"
    )
    path_to_component: dict[str, str] = {}
    for component_id, component in components.items():
        member_paths = component.get("member_paths", [])
        if not isinstance(member_paths, list):
            findings.append(
                {
                    "code": "component_member_paths_invalid",
                    "detail": f"{member}:{component_id}",
                }
            )
            continue
        for value in member_paths:
            path = str(value)
            if path in path_to_component:
                findings.append(
                    {
                        "code": "component_path_duplicated",
                        "detail": f"{member}:{path}",
                    }
                )
            path_to_component[path] = component_id
    return components, path_to_component


def _closure_check_ids(
    compiled: Mapping[str, Any], findings: list[dict[str, str]], member: str
) -> set[str]:
    profiles = _rows_by_id(
        compiled.get("closure_profiles"),
        "profile_id",
        findings,
        f"{member}:closure_profiles",
    )
    profile = profiles.get("enforced")
    if profile is None:
        findings.append({"code": "enforced_closure_missing", "detail": member})
        return set()
    obligations = _rows_by_id(
        compiled.get("obligations"),
        "obligation_id",
        findings,
        f"{member}:obligations",
    )
    required_obligations = profile.get("required_obligation_ids", [])
    if not isinstance(required_obligations, list) or not required_obligations:
        findings.append({"code": "enforced_obligations_invalid", "detail": member})
        return set()
    required_checks: set[str] = set()
    for obligation_value in required_obligations:
        obligation_id = str(obligation_value)
        obligation = obligations.get(obligation_id)
        if obligation is None:
            findings.append(
                {
                    "code": "closure_obligation_unknown",
                    "detail": f"{member}:{obligation_id}",
                }
            )
            continue
        check_ids = obligation.get("required_check_ids", [])
        if not isinstance(check_ids, list) or not check_ids:
            findings.append(
                {
                    "code": "closure_obligation_check_empty",
                    "detail": f"{member}:{obligation_id}",
                }
            )
            continue
        required_checks.update(str(value) for value in check_ids)
    return required_checks


def _check_dependency_order(
    owners: Mapping[str, Mapping[str, Any]],
    findings: list[dict[str, str]],
    member: str,
) -> None:
    pending = set(owners)
    completed: set[str] = set()
    while pending:
        ready = sorted(
            owner_id
            for owner_id in pending
            if set(
                str(value)
                for value in owners[owner_id].get("depends_on_owner_ids", [])
            )
            <= completed
        )
        if not ready:
            findings.append(
                {
                    "code": "owner_dependency_cycle_or_foreign_dependency",
                    "detail": f"{member}:{','.join(sorted(pending))}",
                }
            )
            return
        pending.difference_update(ready)
        completed.update(ready)


def audit(repository_root: Path = ROOT) -> dict[str, Any]:
    global ROOT, GENERATOR_PATH
    ROOT = repository_root.resolve()
    GENERATOR_PATH = ROOT / "scripts" / "build_skillguard_contracts.py"
    findings: list[dict[str, str]] = []
    generator = _load_generator()
    expected_manifest = generator.expected_unit_test_mesh_manifest()
    manifest_path = ROOT / ".skillguard" / "test-mesh.json"
    manifest = _load_json(manifest_path)
    _record(
        findings,
        manifest == expected_manifest,
        "unit_test_mesh_generator_parity_failed",
        ".skillguard/test-mesh.json",
    )
    _record(
        findings,
        set(manifest) == {
            "schema_version",
            "mesh_id",
            "source_model_id",
            "profiles",
            "claim_boundary",
        }
        and manifest.get("schema_version") == "skillguard.test_mesh_manifest.current",
        "unit_test_mesh_schema_shape_invalid",
        ".skillguard/test-mesh.json",
    )
    profiles = _rows_by_id(
        manifest.get("profiles"), "profile_id", findings, "test_mesh_profiles"
    )
    _record(
        findings,
        set(profiles) == {"focused", "full"}
        and profiles.get("focused", {}).get("closure_profile_id") == "enforced"
        and profiles.get("focused", {}).get("full_admission_required") is False
        and profiles.get("full", {}).get("closure_profile_id") == "enforced"
        and profiles.get("full", {}).get("full_admission_required") is True,
        "unit_test_mesh_profiles_invalid",
        ",".join(sorted(profiles)),
    )
    all_mesh_paths = sorted(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("test-mesh.json")
        if ".skillguard" in path.parts and ".git" not in path.parts
    )
    _record(
        findings,
        all_mesh_paths == [".skillguard/test-mesh.json"],
        "unit_test_mesh_authority_not_unique",
        ",".join(all_mesh_paths),
    )

    expected_members = tuple(generator.MEMBERS)
    _record(
        findings,
        expected_members == EXPECTED_MEMBERS,
        "generator_member_inventory_drifted",
        ",".join(expected_members),
    )
    maintenance_paths = set(generator.TEST_MESH_MAINTENANCE_INPUTS)
    maintenance_projection_id = generator.UNIT_TEST_MESH_PROJECTION_ID
    _record(
        findings,
        maintenance_paths
        == {
            ".skillguard/test-mesh.json",
            "scripts/check_researchguard_test_mesh.py",
        },
        "test_mesh_maintenance_input_inventory_drifted",
        ",".join(sorted(maintenance_paths)),
    )

    all_check_ids: set[str] = set()
    all_owner_ids: set[str] = set()
    all_subject_ids: set[str] = set()
    all_domain_ids: set[str] = set()
    direct_generator_owner_ids: set[str] = set()
    all_obligation_ids: set[str] = set()
    installation_boundaries: list[dict[str, Any]] = []
    member_results: list[dict[str, Any]] = []
    suite_checker_text = (ROOT / "scripts" / "check_researchguard_suite.py").read_text(
        encoding="utf-8"
    )
    _record(
        findings,
        "check_prompt_bundles.py" not in suite_checker_text,
        "consumer_contract_executes_prompt_checker",
        "scripts/check_researchguard_suite.py",
    )

    for member in expected_members:
        control_root = ROOT / "skills" / member / ".skillguard"
        source = _load_json(control_root / "contract-source.json")
        compiled = _load_json(control_root / "compiled-contract.json")
        check_manifest = _load_json(control_root / "check-manifest.json")

        for label, value in (
            ("source", source),
            ("compiled", compiled),
            ("check_manifest", check_manifest),
        ):
            _record(
                findings,
                value.get("skill_id") == member,
                "member_skill_identity_mismatch",
                f"{member}:{label}",
            )
            _record(
                findings,
                value.get("maintenance_unit_id") == EXPECTED_UNIT_ID,
                "maintenance_unit_identity_mismatch",
                f"{member}:{label}",
            )
            _record(
                findings,
                tuple(value.get("member_skill_ids", ())) == expected_members,
                "maintenance_member_inventory_mismatch",
                f"{member}:{label}",
            )

        _record(
            findings,
            check_manifest.get("contract_hash") == compiled.get("contract_hash"),
            "manifest_contract_hash_mismatch",
            member,
        )
        _record(
            findings,
            check_manifest.get("check_declarations_hash")
            == compiled.get("check_declarations_hash"),
            "manifest_check_hash_mismatch",
            member,
        )
        source_checks = _rows_by_id(
            source.get("checks"), "check_id", findings, f"{member}:source_checks"
        )
        compiled_checks = _rows_by_id(
            compiled.get("checks"), "check_id", findings, f"{member}:compiled_checks"
        )
        manifest_checks = _rows_by_id(
            check_manifest.get("checks"),
            "check_id",
            findings,
            f"{member}:manifest_checks",
        )
        expected_check_ids = {f"check:{member}:{kind}" for kind in CHECK_KINDS}
        _record(
            findings,
            set(source_checks)
            == set(compiled_checks)
            == set(manifest_checks)
            == expected_check_ids,
            "check_inventory_projection_mismatch",
            member,
        )

        for kind in CHECK_KINDS:
            check_id = f"check:{member}:{kind}"
            source_check = source_checks.get(check_id, {})
            compiled_check = compiled_checks.get(check_id, {})
            manifest_check = manifest_checks.get(check_id, {})
            _record(
                findings,
                manifest_check == compiled_check,
                "compiled_manifest_check_projection_mismatch",
                f"{member}:{check_id}",
            )
            expected_identities = {
                "maintenance_unit_id": EXPECTED_UNIT_ID,
                "member_skill_id": member,
                "evidence_subject_id": f"subject:researchguard:{member}:{kind}",
                "execution_owner_id": f"owner:researchguard:{member}:{kind}",
                "semantic_check_id": f"semantic:researchguard:{member}:{kind}:current",
                "evidence_domain_id": f"evidence-domain:researchguard:{member}:{kind}",
            }
            for field, expected in expected_identities.items():
                _record(
                    findings,
                    source_check.get(field)
                    == compiled_check.get(field)
                    == expected,
                    "source_compiled_check_identity_mismatch",
                    f"{member}:{check_id}:{field}",
                )
            expected_dependencies = [
                f"check:{member}:{dependency}"
                for dependency in DEPENDENCY_KINDS[kind]
            ]
            _record(
                findings,
                source_check.get("depends_on_check_ids")
                == compiled_check.get("depends_on_check_ids")
                == expected_dependencies,
                "check_dependency_projection_invalid",
                f"{member}:{check_id}",
            )
            _record(
                findings,
                _selectors_are_unique(source_check)
                and _selectors_are_unique(compiled_check),
                "duplicate_check_input_selector",
                f"{member}:{check_id}",
            )
            expected_coverage = [
                f"obligation:researchguard:{member}:{kind}"
            ]
            if member == "researchguard" and kind == "native-tests":
                expected_coverage.append(INSTALL_OBLIGATION_ID)
            _record(
                findings,
                source_check.get("covers_obligation_ids")
                == compiled_check.get("covers_obligation_ids")
                == expected_coverage,
                "check_obligation_coverage_invalid",
                f"{member}:{check_id}",
            )

        prompt_check = source_checks.get(f"check:{member}:prompt-load", {})
        native_check = source_checks.get(f"check:{member}:native-tests", {})
        _record(
            findings,
            PROMPT_MANIFEST_CHECKER_PATHS <= _selector_paths(prompt_check)
            and not _row_selects_any_path(prompt_check, {PROMPT_TEST_PATH})
            and all(
                not _row_selects_any_path(check, PROMPT_MANIFEST_CHECKER_PATHS)
                for check_id, check in source_checks.items()
                if check_id != f"check:{member}:prompt-load"
            ),
            "prompt_manifest_checker_owner_not_unique",
            member,
        )
        native_args = native_check.get("args", [])
        _record(
            findings,
            isinstance(native_args, list)
            and ((PROMPT_TEST_PATH in native_args) == (member == "researchguard"))
            and (
                _row_selects_any_path(native_check, {PROMPT_TEST_PATH})
                == (member == "researchguard")
            )
            and all(
                not _row_selects_any_path(check, {PROMPT_TEST_PATH})
                for check_id, check in source_checks.items()
                if check_id != "check:researchguard:native-tests"
            ),
            "prompt_test_execution_owner_invalid",
            member,
        )
        selected_install_checks = {
            check_id
            for check_id, check in source_checks.items()
            if _row_selects_any_path(check, INSTALL_TRANSACTION_PATHS)
        }
        expected_install_checks = (
            {"check:researchguard:native-tests"}
            if member == "researchguard"
            else set()
        )
        _record(
            findings,
            selected_install_checks == expected_install_checks,
            "consumer_install_transaction_owner_invalid",
            f"{member}:{','.join(sorted(selected_install_checks))}",
        )

        _record(
            findings,
            _closure_check_ids(compiled, findings, member) == expected_check_ids,
            "enforced_closure_not_check_complete",
            member,
        )
        obligations = _rows_by_id(
            compiled.get("obligations"),
            "obligation_id",
            findings,
            f"{member}:obligations",
        )
        expected_obligation_ids = {
            f"obligation:researchguard:{member}:{kind}" for kind in CHECK_KINDS
        }
        if member == "researchguard":
            expected_obligation_ids.add(INSTALL_OBLIGATION_ID)
        _record(
            findings,
            set(obligations) == expected_obligation_ids
            and (
                (INSTALL_OBLIGATION_ID in obligations)
                == (member == "researchguard")
            ),
            "member_obligation_inventory_invalid",
            member,
        )
        all_obligation_ids.update(obligations)

        plan = compiled.get("content_impact_plan")
        if not isinstance(plan, Mapping):
            findings.append({"code": "content_impact_plan_missing", "detail": member})
            continue
        _record(
            findings,
            plan.get("schema_version") == "skillguard.content_impact_plan.current",
            "content_impact_plan_schema_invalid",
            member,
        )
        _record(
            findings,
            plan.get("unknown_mapping_disposition") == "block",
            "unknown_mapping_not_blocked",
            member,
        )
        health = plan.get("health")
        _record(
            findings,
            isinstance(health, Mapping)
            and set(health) == EXPECTED_HEALTH_FIELDS
            and all(isinstance(health[key], list) and not health[key] for key in health),
            "content_impact_plan_unhealthy",
            member,
        )
        _record(
            findings,
            plan.get("all_owner_component_ids") == [],
            "all_owner_component_present",
            member,
        )
        _record(
            findings,
            check_manifest.get("content_impact_plan") == plan,
            "manifest_content_impact_plan_mismatch",
            member,
        )

        owners = _rows_by_id(
            plan.get("owners"), "execution_owner_id", findings, f"{member}:owners"
        )
        projections = _rows_by_id(
            plan.get("check_projections"),
            "check_id",
            findings,
            f"{member}:check_projections",
        )
        _record(
            findings,
            len(owners) == 4 and set(projections) == expected_check_ids,
            "member_owner_or_projection_count_drifted",
            f"{member}:owners={len(owners)};projections={len(projections)}",
        )
        for check_id, check in compiled_checks.items():
            owner_id = str(check.get("execution_owner_id", ""))
            owner = owners.get(owner_id, {})
            expected_owner_dependencies = [
                str(compiled_checks[dependency].get("execution_owner_id", ""))
                for dependency in check.get("depends_on_check_ids", [])
                if dependency in compiled_checks
            ]
            _record(
                findings,
                owner.get("check_ids") == [check_id]
                and owner.get("depends_on_owner_ids") == expected_owner_dependencies,
                "owner_dependency_or_cardinality_invalid",
                f"{member}:{owner_id}",
            )
            projection = projections.get(check_id, {})
            for field in (
                "semantic_check_id",
                "evidence_domain_id",
                "execution_owner_id",
                "projection_declaration_hash",
            ):
                _record(
                    findings,
                    projection.get(field) == check.get(field),
                    "check_projection_identity_mismatch",
                    f"{member}:{check_id}:{field}",
                )
        _check_dependency_order(owners, findings, member)

        source_projections = _rows_by_id(
            source.get("projection_consumers"),
            "consumer_id",
            findings,
            f"{member}:source_projection_consumers",
        )
        source_maintenance = source_projections.get(maintenance_projection_id)
        _record(
            findings,
            source_maintenance is not None
            and source_maintenance.get("kind") == "source_maintenance"
            and _selector_paths(source_maintenance) == maintenance_paths,
            "source_maintenance_projection_invalid",
            member,
        )
        _record(
            findings,
            maintenance_paths <= set(source.get("implementation_paths", [])),
            "maintenance_implementation_paths_missing",
            member,
        )

        components, path_to_component = _component_paths(plan, findings, member)
        installation_rows = [
            row
            for row in plan.get("projection_consumers", [])
            if isinstance(row, Mapping)
            and row.get("consumer_id") == "projection:installation"
        ]
        installation = installation_rows[0] if len(installation_rows) == 1 else {}
        installation_component_ids = {
            str(value) for value in installation.get("input_component_ids", [])
        }
        copy_component_ids = {
            component_id
            for component_id, component in components.items()
            if component.get("install_disposition") == "copy"
        }
        source_only_component_ids = {
            component_id
            for component_id, component in components.items()
            if component.get("install_disposition") == "source_only"
        }
        consumer_projection = compiled.get("consumer_projection", {})
        source_consumer_projection = source.get("consumer_projection", {})
        manifest_consumer_projection = check_manifest.get("consumer_projection", {})
        _record(
            findings,
            len(installation_rows) == 1
            and installation.get("kind") == "installation"
            and installation_component_ids == copy_component_ids
            and not (installation_component_ids & source_only_component_ids)
            and all(
                isinstance(value, Mapping)
                and value.get("projection_id")
                == "projection:consumer-distribution"
                and value.get("release_manifest_path") == "consumer-release.json"
                for value in (
                    source_consumer_projection,
                    consumer_projection,
                    manifest_consumer_projection,
                )
            )
            and all(
                "consumer-release.json" not in component.get("member_paths", [])
                for component in components.values()
            ),
            "consumer_release_installation_projection_invalid",
            member,
        )
        for path in sorted(INSTALL_TRANSACTION_PATHS):
            component_id = path_to_component.get(path, "")
            component = components.get(component_id, {})
            expected_present = member == "researchguard"
            _record(
                findings,
                (bool(component_id) == expected_present)
                and (
                    not expected_present
                    or (
                        component.get("install_disposition") == "source_only"
                        and set(component.get("consumer_ids", []))
                        == {"owner:researchguard:researchguard:native-tests"}
                        and component_id not in installation_component_ids
                    )
                ),
                "consumer_install_component_boundary_invalid",
                f"{member}:{path}",
            )
        installation_boundaries.append(
            {
                "member_skill_id": member,
                "release_manifest_path": "consumer-release.json",
                "installation_projection_id": "projection:installation",
                "copy_component_count": len(copy_component_ids),
                "source_only_component_count": len(source_only_component_ids),
            }
        )
        maintenance_component_ids = {
            path_to_component.get(path, "") for path in maintenance_paths
        }
        _record(
            findings,
            "" not in maintenance_component_ids
            and len(maintenance_component_ids) == len(maintenance_paths),
            "maintenance_component_missing_or_merged",
            member,
        )
        compiled_projections = _rows_by_id(
            plan.get("projection_consumers"),
            "consumer_id",
            findings,
            f"{member}:compiled_projection_consumers",
        )
        compiled_maintenance = compiled_projections.get(maintenance_projection_id)
        _record(
            findings,
            compiled_maintenance is not None
            and compiled_maintenance.get("kind") == "source_maintenance"
            and set(compiled_maintenance.get("input_component_ids", []))
            == maintenance_component_ids,
            "compiled_maintenance_projection_invalid",
            member,
        )
        expected_roles = {
            ".skillguard/test-mesh.json": "contract_schema",
            "scripts/check_researchguard_test_mesh.py": "runtime_source",
        }
        for path, role in expected_roles.items():
            component = components.get(path_to_component.get(path, ""), {})
            _record(
                findings,
                component.get("role") == role
                and component.get("install_disposition") == "source_only"
                and set(component.get("consumer_ids", []))
                == {maintenance_projection_id},
                "maintenance_component_role_or_owner_invalid",
                f"{member}:{path}",
            )
        _record(
            findings,
            all(
                not _row_selects_any_path(owner, maintenance_paths)
                for owner in owners.values()
            ),
            "maintenance_path_wrongly_selects_semantic_owner",
            member,
        )

        generator_path = "scripts/build_skillguard_contracts.py"
        generator_component_id = path_to_component.get(generator_path, "")
        generator_component = components.get(generator_component_id, {})
        generator_owner_ids = {
            str(value)
            for value in generator_component.get("consumer_ids", [])
            if str(value).startswith("owner:")
        }
        expected_generator_owners = (
            {"owner:researchguard:researchguard:native-tests"}
            if member == "researchguard"
            else set()
        )
        _record(
            findings,
            generator_owner_ids == expected_generator_owners
            and ((not generator_component_id) == (member != "researchguard")),
            "generator_semantic_impact_hidden_or_expanded",
            f"{member}:{','.join(sorted(generator_owner_ids))}",
        )
        direct_generator_owner_ids.update(generator_owner_ids)

        duplicate_checks = all_check_ids & set(compiled_checks)
        duplicate_owners = all_owner_ids & set(owners)
        subject_ids = {
            str(check.get("evidence_subject_id", ""))
            for check in compiled_checks.values()
        }
        domain_ids = {
            str(check.get("evidence_domain_id", ""))
            for check in compiled_checks.values()
        }
        _record(
            findings,
            not duplicate_checks and not duplicate_owners,
            "cross_member_check_or_owner_duplicate",
            f"{member}:{','.join(sorted(duplicate_checks | duplicate_owners))}",
        )
        _record(
            findings,
            "" not in subject_ids
            and "" not in domain_ids
            and not (all_subject_ids & subject_ids)
            and not (all_domain_ids & domain_ids),
            "cross_member_subject_or_domain_duplicate",
            member,
        )
        all_check_ids.update(compiled_checks)
        all_owner_ids.update(owners)
        all_subject_ids.update(subject_ids)
        all_domain_ids.update(domain_ids)
        member_results.append(
            {
                "member_skill_id": member,
                "check_owner_count": len(owners),
                "evidence_subject_count": len(subject_ids),
                "evidence_domain_count": len(domain_ids),
                "closure_profile_id": "enforced",
                "plan_only_static_eligibility": "pending",
            }
        )

    _record(
        findings,
        len(all_check_ids)
        == len(all_owner_ids)
        == len(all_subject_ids)
        == len(all_domain_ids)
        == EXPECTED_OWNER_COUNT,
        "unit_identity_total_drifted",
        (
            f"checks={len(all_check_ids)};owners={len(all_owner_ids)};"
            f"subjects={len(all_subject_ids)};domains={len(all_domain_ids)}"
        ),
    )
    _record(
        findings,
        len(all_obligation_ids) == EXPECTED_OBLIGATION_COUNT,
        "unit_obligation_total_drifted",
        str(len(all_obligation_ids)),
    )
    _record(
        findings,
        direct_generator_owner_ids
        == {"owner:researchguard:researchguard:native-tests"},
        "generator_original_impact_missing",
        ",".join(sorted(direct_generator_owner_ids)),
    )

    status = "pass" if not findings else "blocked"
    for row in member_results:
        row["plan_only_static_eligibility"] = (
            "eligible_after_legitimate_claimed_run"
            if status == "pass"
            else "blocked"
        )
    return {
        "schema_version": "researchguard.skillguard_test_mesh_static_audit.v1",
        "status": status,
        "maintenance_unit_id": EXPECTED_UNIT_ID,
        "mesh_id": manifest.get("mesh_id", ""),
        "member_count": len(expected_members),
        "check_owner_count": len(all_owner_ids),
        "evidence_subject_count": len(all_subject_ids),
        "evidence_domain_count": len(all_domain_ids),
        "obligation_count": len(all_obligation_ids),
        "execution_count": 0,
        "plan_only_execution_status": "not_run",
        "member_results": member_results,
        "source_maintenance_projection": {
            "consumer_id": maintenance_projection_id,
            "paths": sorted(maintenance_paths),
            "semantic_owner_selection": [],
            "required_next_action_on_change": (
                "regenerate and compile all five member contracts; after one "
                "legitimate current claimed run for each member, freeze five "
                "member-specific plan_only plans"
            ),
        },
        "generator_impact": {
            "direct_semantic_owner_ids": sorted(direct_generator_owner_ids),
            "disposition": (
                "preserve the existing researchguard native-tests impact; never "
                "hide it behind the source-maintenance projection"
            ),
        },
        "consumer_install_transaction": {
            "obligation_id": INSTALL_OBLIGATION_ID,
            "execution_owner_id": "owner:researchguard:researchguard:native-tests",
            "source_only_paths": sorted(INSTALL_TRANSACTION_PATHS),
        },
        "prompt_governance": {
            "manifest_checker_owner_kind": "prompt-load",
            "manifest_checker_paths": sorted(PROMPT_MANIFEST_CHECKER_PATHS),
            "test_execution_owner_id": "owner:researchguard:researchguard:native-tests",
            "test_path": PROMPT_TEST_PATH,
        },
        "installation_boundaries": installation_boundaries,
        "unknown_mapping_disposition": "block",
        "findings": findings,
        "claim_boundary": (
            "A pass proves only current-format static eligibility for five future "
            "member-specific plan_only freezes covering the existing twenty owners. "
            "No run was claimed, no plan_only was executed, no owner process was "
            "launched, and no execution or aggregation receipt was created."
        ),
    }


def main() -> int:
    result = audit(ROOT)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
