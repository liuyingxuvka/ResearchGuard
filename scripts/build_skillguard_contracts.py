"""Build the ResearchGuard maintenance unit's five author-side contracts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEMBERS = (
    "researchguard",
    "logicguard",
    "sourceguard",
    "traceguard",
    "experimentguard",
)
UNIT_ID = "unit:researchguard-suite"
VALIDATION_PLAN_PATH = ROOT / ".skillguard" / "researchguard-suite-validation-plan.json"
UNIT_TEST_MESH_PATH = ROOT / ".skillguard" / "test-mesh.json"
UNIT_TEST_MESH_SCHEMA = "skillguard.test_mesh_manifest.current"
UNIT_TEST_MESH_ID = "researchguard-suite-owner-receipt-mesh"
UNIT_TEST_MESH_PROJECTION_ID = (
    "projection:researchguard-suite-maintenance-definition"
)
TEST_MESH_MAINTENANCE_INPUTS = (
    ".skillguard/test-mesh.json",
    "scripts/check_researchguard_test_mesh.py",
)
RESEARCHGUARD_VERSION = "0.4.10"
FLOWGUARD_VERSION = "0.68.2"
SKILLGUARD_VERSION = "0.7.2"

BLUEPRINT_COMPONENTS = {
    "researchguard": {
        "reference": "skills/researchguard/references/member-model-envelope.md",
        "runtime": [
            "src/researchguard/model_envelope.py",
            "src/researchguard/domain_dna.py",
            "src/researchguard/external_scope_authority.py",
            "src/researchguard/routing.py",
            "src/researchguard/admission.py",
            "src/researchguard/cli.py",
            "src/researchguard/suite.py",
            "src/researchguard/target_authority.py",
            "src/researchguard/experiment/owner_attestation.py",
            "src/researchguard/logic/owner_attestation.py",
            "src/researchguard/source/owner_attestation.py",
            "src/researchguard/trace/owner_attestation.py",
        ],
        "tests": [
            "tests/test_member_model_envelope.py",
            "tests/test_guard_blueprint_integration.py",
            "tests/test_external_domain_dna_real_paper.py",
            "tests/test_external_scope_authority.py",
        ],
    },
    "logicguard": {
        "reference": "skills/logicguard/references/domain-blueprint-contract.md",
        "runtime": [
            "src/researchguard/target_authority.py",
            "src/researchguard/model_envelope.py",
            "src/researchguard/logic/owner_attestation.py",
            "src/researchguard/logic/artifact_inventory.py",
            "src/researchguard/logic/blueprint.py",
            "src/researchguard/logic/model.py",
            "src/researchguard/logic/validator.py",
            "src/researchguard/logic/hierarchy.py",
            "src/researchguard/logic/structured_artifact.py",
            "src/researchguard/logic/execution_depth.py",
            "src/researchguard/logic/mesh_invalidation.py",
            "src/researchguard/logic/cli.py",
        ],
        "tests": [
            "tests/logic/test_blueprint_interfaces.py",
            "tests/logic/test_artifact_inventory.py",
        ],
    },
    "sourceguard": {
        "reference": "skills/sourceguard/references/information-blueprint.md",
        "runtime": [
            "src/researchguard/target_authority.py",
            "src/researchguard/model_envelope.py",
            "src/researchguard/source/owner_attestation.py",
            "src/researchguard/source/blueprint.py",
            "src/researchguard/source/schema.py",
            "src/researchguard/source/graph.py",
            "src/researchguard/source/depth.py",
            "src/researchguard/source/guard_contract.py",
            "src/researchguard/source/task_iteration.py",
            "src/researchguard/source/handoff.py",
            "src/researchguard/source/cli.py",
        ],
        "tests": ["tests/source/test_blueprint_graph.py"],
    },
    "traceguard": {
        "reference": "skills/traceguard/references/trace-blueprint-contract.md",
        "runtime": [
            "src/researchguard/target_authority.py",
            "src/researchguard/model_envelope.py",
            "src/researchguard/trace/owner_attestation.py",
            "src/researchguard/trace/blueprint.py",
            "src/researchguard/trace/schema.py",
            "src/researchguard/trace/inference/compiler.py",
            "src/researchguard/trace/inference/projection.py",
            "src/researchguard/trace/storyline_depth.py",
            "src/researchguard/trace/task_iteration.py",
            "src/researchguard/trace/cli.py",
        ],
        "tests": ["tests/trace/test_blueprint_hierarchy.py"],
    },
    "experimentguard": {
        "reference": "skills/experimentguard/references/experiment-model-protocol.md",
        "runtime": [
            "src/researchguard/target_authority.py",
            "src/researchguard/model_envelope.py",
            "src/researchguard/experiment/owner_attestation.py",
            "src/researchguard/experiment/blueprint.py",
            "src/researchguard/experiment/schema.py",
            "src/researchguard/experiment/engine.py",
            "src/researchguard/experiment/cli.py",
        ],
        "tests": ["tests/experiment/test_blueprint_design.py"],
    },
}

TEST_ARGS = {
    "researchguard": [
        "-m",
        "pytest",
        "tests/test_suite_routing.py",
        "tests/test_root_cli.py",
        "tests/test_skill_suite.py",
        "tests/test_install_researchguard.py",
        "tests/test_prompt_bundles.py",
        "tests/test_zero_residuals.py",
        "tests/test_external_domain_dna_real_paper.py",
        "tests/test_external_scope_authority.py",
        "-q",
    ],
    "logicguard": ["-m", "pytest", "tests/logic", "-q"],
    "sourceguard": ["-m", "pytest", "tests/source", "-q"],
    "traceguard": ["-m", "pytest", "tests/trace", "-q"],
    "experimentguard": ["-m", "pytest", "tests/experiment", "-q"],
}

ITERATION_TEST_ARGS = {
    "researchguard": ["-m", "pytest", "tests/experiment", "tests/logic", "tests/source", "tests/trace", "-q"],
    "logicguard": ["-m", "pytest", "tests/logic/test_task_iteration.py", "-q"],
    "sourceguard": ["-m", "pytest", "tests/source/test_task_iteration.py", "-q"],
    "traceguard": ["-m", "pytest", "tests/trace/test_task_iteration.py", "-q"],
    "experimentguard": ["-m", "pytest", "tests/experiment/test_recommendation.py", "-q"],
}

IMPLEMENTATION_PATHS = {
    "researchguard": [
        "skills/researchguard",
        "src/researchguard/__init__.py",
        "src/researchguard/__main__.py",
        "src/researchguard/admission.py",
        "src/researchguard/cli.py",
        "src/researchguard/domain_dna.py",
        "src/researchguard/external_scope_authority.py",
        "src/researchguard/routing.py",
        "src/researchguard/suite.py",
        "src/researchguard/logic/admission.py",
        "src/researchguard/source/admission.py",
        "src/researchguard/trace/admission.py",
        "src/researchguard/experiment/admission.py",
        ".flowguard/researchguard_suite_model.py",
        ".flowguard/researchguard_suite_model.json",
        ".flowguard/run_researchguard_suite_model.py",
        ".flowguard/researchguard_skill_contract_model.py",
        ".flowguard/researchguard_skill_contract_model_common.py",
        "scripts/build_skillguard_contracts.py",
        "scripts/compile_external_domain_dna_examples.py",
        "scripts/check_researchguard_suite.py",
        "scripts/check_zero_residuals.py",
        "scripts/install_researchguard.py",
        "tests/test_suite_routing.py",
        "tests/admission_fixtures.py",
        "tests/test_root_cli.py",
        "tests/test_skill_suite.py",
        "tests/test_install_researchguard.py",
        "tests/test_external_domain_dna_real_paper.py",
        "tests/test_external_scope_authority.py",
        "tests/external_scope_authority_fixtures.py",
        "tests/test_prompt_bundles.py",
        "tests/test_suite_model_currentness.py",
        "tests/test_zero_residuals.py",
        "tests/logic/test_task_iteration.py",
        "tests/source/test_task_iteration.py",
        "tests/trace/test_task_iteration.py",
        "tests/experiment/test_recommendation.py",
        "models/external_domain_dna",
        "pyproject.toml",
    ],
    "logicguard": [
        "skills/logicguard",
        "src/researchguard/logic",
        "src/researchguard/logic_template_packs",
        "src/researchguard/logic_viewer",
        ".flowguard/researchguard_suite_model.py",
        ".flowguard/researchguard_suite_model.json",
        ".flowguard/run_researchguard_suite_model.py",
        ".flowguard/logicguard_skill_contract_model.py",
        ".flowguard/researchguard_skill_contract_model_common.py",
        "tests/logic",
    ],
    "sourceguard": [
        "skills/sourceguard",
        "src/researchguard/source",
        ".flowguard/researchguard_suite_model.py",
        ".flowguard/researchguard_suite_model.json",
        ".flowguard/run_researchguard_suite_model.py",
        ".flowguard/sourceguard_content_anchor_oracle_model.py",
        ".flowguard/sourceguard_skill_contract_model.py",
        ".flowguard/researchguard_skill_contract_model_common.py",
        "examples/source",
        "tests/source",
    ],
    "traceguard": [
        "skills/traceguard",
        "src/researchguard/trace",
        ".flowguard/researchguard_suite_model.py",
        ".flowguard/researchguard_suite_model.json",
        ".flowguard/run_researchguard_suite_model.py",
        ".flowguard/traceguard_skill_contract_model.py",
        ".flowguard/researchguard_skill_contract_model_common.py",
        "tests/trace",
    ],
    "experimentguard": [
        "skills/experimentguard",
        "src/researchguard/experiment",
        ".flowguard/researchguard_suite_model.py",
        ".flowguard/researchguard_suite_model.json",
        ".flowguard/run_researchguard_suite_model.py",
        ".flowguard/experimentguard_skill_contract_model.py",
        ".flowguard/researchguard_skill_contract_model_common.py",
        "tests/experiment",
    ],
}

PROMPT_MANIFEST_CHECKER_PATHS = (
    "researchguard/prompt_bundle_manifest.json",
    "scripts/check_prompt_bundles.py",
)


def expected_unit_test_mesh_manifest() -> dict:
    """Return the sole current TestMesh definition for this maintenance unit."""

    return {
        "schema_version": UNIT_TEST_MESH_SCHEMA,
        "mesh_id": UNIT_TEST_MESH_ID,
        "source_model_id": "researchguard.suite.validation_composition.current",
        "profiles": [
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
        ],
        "claim_boundary": (
            "This one unit-level definition selects each ResearchGuard member's "
            "existing enforced closure. One legitimate claimed run per member is "
            "required before member-specific plan_only can freeze owners. It "
            "declares no commands, source paths, aliases, fallback, execution "
            "result, or receipt authority; full remains separately admitted."
        ),
    }


def _write_unit_test_mesh_manifest() -> None:
    UNIT_TEST_MESH_PATH.parent.mkdir(parents=True, exist_ok=True)
    UNIT_TEST_MESH_PATH.write_text(
        json.dumps(expected_unit_test_mesh_manifest(), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


def _installed_version(distribution: str, expected: str) -> str:
    actual = importlib.metadata.version(distribution)
    if actual != expected:
        raise ValueError(
            f"{distribution} toolchain mismatch: expected {expected}, found {actual}"
        )
    return actual


def _skillguard_source_fingerprint() -> str:
    spec = importlib.util.find_spec("skillguard")
    if spec is None or spec.origin is None:
        raise ValueError("installed SkillGuard source root is unavailable")
    source_root = Path(spec.origin).resolve().parent.parent
    if not (source_root / "SKILL.md").is_file() or not (
        source_root / "scripts" / "skillguard_compile.py"
    ).is_file():
        raise ValueError("installed SkillGuard source root is not an author toolchain")
    rows: dict[str, str] = {}
    for path in sorted(item for item in source_root.rglob("*") if item.is_file()):
        relative = path.relative_to(source_root)
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        rows[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    encoded = json.dumps(
        rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _unique_selectors(
    selectors: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Keep first-seen selector order while removing exact duplicate inputs."""

    unique: list[dict[str, str]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for selector in selectors:
        identity = tuple(sorted(selector.items()))
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(selector)
    return unique


def check(
    member: str,
    *,
    kind: str,
    command: str,
    args: list[str],
    selectors: list[dict[str, str]],
    depends: list[str],
    obligations: list[str],
    timeout: int,
    coverage_rationale: str | None = None,
) -> dict:
    check_id = f"check:{member}:{kind}"
    route_id = f"route:researchguard:{member}"
    return {
        "check_id": check_id,
        "maintenance_unit_id": UNIT_ID,
        "member_skill_id": member,
        "evidence_subject_id": f"subject:researchguard:{member}:{kind}",
        "semantic_check_id": f"semantic:researchguard:{member}:{kind}:current",
        "kind": "command",
        "command": command,
        "args": args,
        "cwd_token": "repository_root",
        "input_selectors": _unique_selectors(selectors),
        "expected": {"exit_code": 0},
        "timeout_seconds": timeout,
        "evidence_class": "hard",
        "evidence_domain_id": f"evidence-domain:researchguard:{member}:{kind}",
        "execution_owner_id": f"owner:researchguard:{member}:{kind}",
        "native_route_id": route_id,
        "depends_on_check_ids": depends,
        "covers_obligation_ids": list(obligations),
        "coverage_scope": "declared_obligations",
        "coverage_rationale": coverage_rationale or (
            "This check is the sole execution owner for its exact member obligation."
        ),
    }


def contract(member: str) -> dict:
    contract_check_id = f"check:{member}:consumer-contract"
    contract_obligation = f"obligation:researchguard:{member}:consumer-contract"
    prompt_check_id = f"check:{member}:prompt-load"
    prompt_obligation = f"obligation:researchguard:{member}:prompt-load"
    native_obligation = f"obligation:researchguard:{member}:native-tests"
    install_obligation = (
        "obligation:researchguard:researchguard:consumer-install-transaction"
    )
    deepening_check_id = f"check:{member}:task-model-closure"
    deepening_obligation = f"obligation:researchguard:{member}:task-model-closure"
    route_id = f"route:researchguard:{member}"
    blueprint = BLUEPRINT_COMPONENTS[member]
    blueprint_selectors = [
        {"kind": "path", "path": path}
        for path in [*blueprint["runtime"], *blueprint["tests"]]
    ]
    checks = [
        check(
            member,
            kind="consumer-contract",
            command="python",
            args=[
                "scripts/check_researchguard_suite.py",
                "--member",
                member,
                "--json",
            ],
            selectors=[
                {"kind": "path", "path": f"skills/{member}/SKILL.md"},
                {"kind": "path", "path": f"skills/{member}/agents/openai.yaml"},
                {"kind": "path", "path": "scripts/check_researchguard_suite.py"},
                {
                    "kind": "path",
                    "path": ".flowguard/researchguard_suite_model.py",
                },
                {
                    "kind": "path",
                    "path": ".flowguard/researchguard_suite_model.json",
                },
                {
                    "kind": "path",
                    "path": ".flowguard/run_researchguard_suite_model.py",
                },
                {
                    "kind": "path",
                    "path": f".flowguard/{member}_skill_contract_model.py",
                },
                {
                    "kind": "path",
                    "path": ".flowguard/researchguard_skill_contract_model_common.py",
                },
                *[
                    {"kind": "path", "path": path}
                    for path in IMPLEMENTATION_PATHS[member]
                    if path.startswith(".flowguard/")
                ],
            ],
            depends=[],
            obligations=[contract_obligation],
            timeout=60,
        ),
        check(
            member,
            kind="prompt-load",
            command="python",
            args=[
                "scripts/check_prompt_bundles.py",
                "--member",
                member,
                "--json",
            ],
            selectors=[
                {"kind": "subtree", "path": f"skills/{member}"},
                {"kind": "path", "path": blueprint["reference"]},
                *[
                    {"kind": "path", "path": path}
                    for path in PROMPT_MANIFEST_CHECKER_PATHS
                ],
            ] + (
                [
                    {"kind": "path", "path": "src/researchguard/admission.py"},
                    {"kind": "path", "path": "src/researchguard/routing.py"},
                    {"kind": "path", "path": "src/researchguard/logic/admission.py"},
                    {"kind": "path", "path": "src/researchguard/source/admission.py"},
                    {"kind": "path", "path": "src/researchguard/trace/admission.py"},
                    {"kind": "path", "path": "src/researchguard/experiment/admission.py"},
                ]
                if member == "researchguard"
                else []
            ),
            depends=[contract_check_id],
            obligations=[prompt_obligation],
            timeout=60,
        ),
        check(
            member,
            kind="native-tests",
            command="python",
            args=TEST_ARGS[member],
            selectors=[
                {
                    "kind": (
                        "subtree"
                        if (ROOT / path).is_dir()
                        else "path"
                    ),
                    "path": path,
                }
                for path in IMPLEMENTATION_PATHS[member]
                if not path.startswith(".flowguard/")
            ] + blueprint_selectors,
            depends=[prompt_check_id],
            obligations=(
                [native_obligation, install_obligation]
                if member == "researchguard"
                else [native_obligation]
            ),
            timeout=900,
            coverage_rationale=(
                "This existing member-native owner runs the complete declared member "
                "test suite once. Its exact blueprint code/test selectors cover native "
                "qualification, qualification-first impact and reverse trace, persisted "
                "fresh-process target-authority replay, and caller-forged/co-shrunk "
                "self-attestation rejection without adding duplicate execution owners. "
                + (
                    "For the ResearchGuard umbrella, this same owner also proves the "
                    "suite install transaction's total lock, package/consumer/manifest "
                    "rollback, and cleanup-unconfirmed boundary."
                    if member == "researchguard"
                    else ""
                )
            ),
        ),
        check(
            member,
            kind="task-model-closure",
            command="python",
            args=ITERATION_TEST_ARGS[member],
            selectors=[
                {
                    "kind": "path",
                    "path": path,
                }
                for path in (
                    [
                        "tests/experiment/test_recommendation.py",
                        "tests/logic/test_task_iteration.py",
                        "tests/source/test_task_iteration.py",
                        "tests/trace/test_task_iteration.py",
                    ]
                    if member == "researchguard"
                    else [f"tests/{member.replace('logicguard', 'logic').replace('sourceguard', 'source').replace('traceguard', 'trace').replace('experimentguard', 'experiment')}/test_task_iteration.py" if member != "experimentguard" else "tests/experiment/test_recommendation.py"]
                )
                if (ROOT / path).exists()
            ],
            depends=[f"check:{member}:native-tests"],
            obligations=[deepening_obligation],
            timeout=900,
        ),
    ]
    return {
        "schema_version": "skillguard.contract_source.v2",
        "skill_id": member,
        "repository_role": "skill_maintainer_source",
        "maintenance_unit_id": UNIT_ID,
        "member_skill_ids": list(MEMBERS),
        "consumer_projection": {
            "projection_id": "projection:consumer-distribution",
            "prohibited_path_prefixes": [".skillguard/"],
            "prohibited_prompt_tokens": ["SkillGuard", ".skillguard", "skillguard.py"],
            "release_manifest_path": "consumer-release.json",
        },
        "projection_consumers": [
            {
                "consumer_id": UNIT_TEST_MESH_PROJECTION_ID,
                "kind": "source_maintenance",
                "input_selectors": [
                    {"kind": "path", "path": path}
                    for path in TEST_MESH_MAINTENANCE_INPUTS
                ],
            }
        ],
        "model_id": f"researchguard.{member}.contract.current",
        "model_path": f".flowguard/{member}_skill_contract_model.py",
        "confirmed": True,
        "integration_mode": "native-integrated",
        "native_route_owner": f"owner:researchguard:{member}",
        "may_define_parallel_execution_route": False,
        "may_define_skillguard_runtime_route": False,
        "native_route_bindings": [
            {
                "binding_id": f"native:researchguard:{member}",
                "native_route_id": route_id,
                "required_before_closure": True,
                "source": f"skills/{member}/SKILL.md",
            }
        ],
        "native_check_bindings": [
            {
                "binding_id": f"native-check:researchguard:{member}:consumer-contract",
                "native_check_id": contract_check_id,
                "required": True,
                "evidence_source": "scripts/check_researchguard_suite.py",
            },
            {
                "binding_id": f"native-check:researchguard:{member}:prompt-load",
                "native_check_id": prompt_check_id,
                "required": True,
                "evidence_source": "scripts/check_prompt_bundles.py",
            },
            {
                "binding_id": f"native-check:researchguard:{member}:native-tests",
                "native_check_id": f"check:{member}:native-tests",
                "required": True,
                "evidence_source": "tests",
            },
            {
                "binding_id": f"native-check:researchguard:{member}:task-model-closure",
                "native_check_id": deepening_check_id,
                "required": True,
                "evidence_source": "tests/task-local-iteration",
            },
        ],
        "depth_profile": {
            "schema_version": "skillguard.depth_profile.v2",
            "profile_id": f"profile:researchguard:{member}:strict-model-closure",
            "target_skill_id": member,
            "integration_mode": "native-integrated",
            "native_owner_id": f"owner:researchguard:{member}",
            "native_route_ids": [route_id],
            "native_check_ids": [
                contract_check_id,
                prompt_check_id,
                f"check:{member}:native-tests",
                deepening_check_id,
            ],
            "model_deepening_check_id": deepening_check_id,
            "skillguard_adds_domain_route": False,
            "enforcement_level": "enforced",
            "required_closure_profiles": ["enforced"],
            "provider_runtime": {
                "provider_id": "skillguard-local-provider",
                "required_runtime_contract_id": "skillguard-declared-check-supervision-current",
                "required_capability_ids": [
                    "declared-check-inventory.v1",
                    "declared-check-receipt-reconciliation.v1",
                    "installation-receipt-binding.v1",
                    "installation-currentness-replay.v1",
                    "provider-runtime-enrollment.v1",
                    "single-flight-check-execution.v1",
                ],
                "required_enrollment_status": "enrolled",
                "readiness_check_ids": [
                    contract_check_id,
                    prompt_check_id,
                    f"check:{member}:native-tests",
                    deepening_check_id,
                ],
            },
            "claim_boundary": (
                "SkillGuard supervises only the exact current ResearchGuard target-owned "
                "strict model-closure checks; it does not replace their domain judgment."
            ),
        },
        "implementation_paths": list(
            dict.fromkeys(
                [
                    *IMPLEMENTATION_PATHS[member],
                    *PROMPT_MANIFEST_CHECKER_PATHS,
                    *blueprint["runtime"],
                    *blueprint["tests"],
                    blueprint["reference"],
                    *TEST_MESH_MAINTENANCE_INPUTS,
                ]
            )
        ),
        "step_bindings": [
            {
                "step_id": f"step:researchguard:{member}:contract",
                "action": {
                    "kind": "native",
                    "summary": "Validate the exact current consumer skill and route boundary.",
                },
                "check_ids": [contract_check_id],
                "output_artifact_ids": [],
            },
            {
                "step_id": f"step:researchguard:{member}:prompt-load",
                "action": {
                    "kind": "native",
                    "summary": "Validate the selected-only entry budget and conditional reference graph.",
                },
                "check_ids": [prompt_check_id],
                "output_artifact_ids": [],
            },
            {
                "step_id": f"step:researchguard:{member}:tests",
                "action": {
                    "kind": "native",
                    "summary": "Execute the member-owned current native regression suite.",
                },
                "check_ids": [f"check:{member}:native-tests"],
                "output_artifact_ids": [],
            },
            {
                "step_id": f"step:researchguard:{member}:task-model-closure",
                "action": {
                    "kind": "native",
                    "summary": "Execute the target-owned task-local model closure and gap-continuation checks.",
                },
                "check_ids": [deepening_check_id],
                "output_artifact_ids": [],
            },
        ],
        "checks": checks,
        "artifacts": [],
        "closure_profiles": [
            {
                "profile_id": "enforced",
                "required_obligation_ids": [
                    contract_obligation,
                    prompt_obligation,
                    native_obligation,
                    *([install_obligation] if member == "researchguard" else []),
                    deepening_obligation,
                ],
            }
        ],
        "judgment_rubrics": [],
        "claim_boundary": (
            f"This contract covers the current {member} consumer projection, "
            f"native route, and member-owned tests inside ResearchGuard v{RESEARCHGUARD_VERSION}. "
            "The four exact native-blueprint evidence categories are selectors of the one "
            "existing target-owned native-tests owner, so final validation does not repeat "
            "the same member suite. Distinct model obligation ids "
            "remain a later binding with the frozen FlowGuard self-DNA toolchain. "
            + (
                "The ResearchGuard native-tests owner covers installation transaction "
                "behavior without claiming an installation executed or is current. "
                if member == "researchguard"
                else ""
            )
            +
            "It does not prove source truth, unrun external work, installed currentness, "
            "publication, or future AI behavior."
        ),
    }


def validation_plan() -> dict:
    skillguard_version = _installed_version("skillguard", SKILLGUARD_VERSION)
    rows = []
    owner_ids: list[str] = []
    check_count = 0
    for member in MEMBERS:
        control = ROOT / "skills" / member / ".skillguard"
        compiled = json.loads((control / "compiled-contract.json").read_text(encoding="utf-8"))
        manifest = json.loads((control / "check-manifest.json").read_text(encoding="utf-8"))
        if tuple(compiled.get("member_skill_ids", ())) != MEMBERS:
            raise ValueError(f"{member} compiled contract is not the exact five-member unit")
        if tuple(manifest.get("member_skill_ids", ())) != MEMBERS:
            raise ValueError(f"{member} check manifest is not the exact five-member unit")
        checks = []
        for item in manifest.get("checks", ()):
            row = {
                "check_id": item["check_id"],
                "evidence_subject_id": item["evidence_subject_id"],
                "execution_owner_id": item["execution_owner_id"],
                "evidence_domain_id": item["evidence_domain_id"],
                "depends_on_check_ids": item["depends_on_check_ids"],
            }
            checks.append(row)
            owner_ids.append(row["execution_owner_id"])
        check_count += len(checks)
        rows.append(
            {
                "member_skill_id": member,
                "contract_hash": compiled["contract_hash"],
                "manifest_hash": manifest["manifest_hash"],
                "checks": checks,
            }
        )
    if len(owner_ids) != len(set(owner_ids)):
        raise ValueError("validation plan contains duplicate execution owners")
    return {
        "schema_version": "researchguard.skillguard_unit_validation_plan.v1",
        "status": "stale",
        "execution_disposition": "not_executable",
        "stale_reason_codes": [
            "flowguard-0.68.2-plan-predates-native-blueprint-contracts",
            "flowguard-toolchain-not-frozen",
            "self-dna-binding-deferred",
        ],
        "maintenance_unit_id": UNIT_ID,
        "member_skill_ids": list(MEMBERS),
        "toolchain": {
            "skillguard_version": skillguard_version,
            "skillguard_source_revision": _skillguard_source_fingerprint(),
            "flowguard_version": FLOWGUARD_VERSION,
            "flowguard_status": "stale_later_binding",
            "python_command": "python",
        },
        "private_roots": {
            "run_state_root": "work/skillguard/v0.7.2-current/run-state",
            "owner_evidence_root": "work/verification/skillguard-v0.7.2-current/owner-evidence",
        },
        "members": rows,
        "execution_owner_count": len(owner_ids),
        "check_count": check_count,
        "cross_unit_receipt_reuse": False,
        "skillguard_adds_domain_route": False,
        "claim_boundary": (
            "This file preserves the pre-blueprint FlowGuard 0.68.2 validation-plan identity "
            "as visibly stale and non-executable. Current native affected-only ownership "
            "comes from each compiled contract content-impact plan; FlowGuard self-DNA "
            "binding remains a later task after its toolchain is frozen."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-validation-plan", action="store_true")
    args = parser.parse_args(argv)
    _write_unit_test_mesh_manifest()
    for member in MEMBERS:
        control = ROOT / "skills" / member / ".skillguard"
        control.mkdir(parents=True, exist_ok=True)
        path = control / "contract-source.json"
        path.write_text(
            json.dumps(contract(member), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.write_validation_plan:
        VALIDATION_PLAN_PATH.write_text(
            json.dumps(validation_plan(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "unit": UNIT_ID,
                "members": MEMBERS,
                "test_mesh_manifest_written": True,
                "validation_plan_written": args.write_validation_plan,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
