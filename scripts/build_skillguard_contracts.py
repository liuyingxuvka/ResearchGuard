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
RESEARCHGUARD_VERSION = "0.4.1"
FLOWGUARD_VERSION = "0.68.2"
SKILLGUARD_VERSION = "0.7.2"

TEST_ARGS = {
    "researchguard": [
        "-m",
        "pytest",
        "tests/test_suite_routing.py",
        "tests/test_root_cli.py",
        "tests/test_skill_suite.py",
        "tests/test_install_researchguard.py",
        "tests/test_zero_residuals.py",
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
        "scripts/check_researchguard_suite.py",
        "scripts/check_zero_residuals.py",
        "scripts/install_researchguard.py",
        "tests/test_suite_routing.py",
        "tests/admission_fixtures.py",
        "tests/test_root_cli.py",
        "tests/test_skill_suite.py",
        "tests/test_install_researchguard.py",
        "tests/test_suite_model_currentness.py",
        "tests/test_zero_residuals.py",
        "tests/logic/test_task_iteration.py",
        "tests/source/test_task_iteration.py",
        "tests/trace/test_task_iteration.py",
        "tests/experiment/test_recommendation.py",
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

PROMPT_GOVERNANCE_PATHS = (
    "researchguard/prompt_bundle_manifest.json",
    "scripts/check_prompt_bundles.py",
    "tests/test_prompt_bundles.py",
)
for _member_paths in IMPLEMENTATION_PATHS.values():
    _member_paths.extend(path for path in PROMPT_GOVERNANCE_PATHS if path not in _member_paths)


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


def check(
    member: str,
    *,
    kind: str,
    command: str,
    args: list[str],
    selectors: list[dict[str, str]],
    depends: list[str],
    obligation: str,
    timeout: int,
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
        "input_selectors": selectors,
        "expected": {"exit_code": 0},
        "timeout_seconds": timeout,
        "evidence_class": "hard",
        "evidence_domain_id": f"evidence-domain:researchguard:{member}:{kind}",
        "execution_owner_id": f"owner:researchguard:{member}:{kind}",
        "native_route_id": route_id,
        "depends_on_check_ids": depends,
        "covers_obligation_ids": [obligation],
        "coverage_scope": "declared_obligations",
        "coverage_rationale": (
            "This check is the sole execution owner for its exact member obligation."
        ),
    }


def contract(member: str) -> dict:
    contract_check_id = f"check:{member}:consumer-contract"
    contract_obligation = f"obligation:researchguard:{member}:consumer-contract"
    prompt_check_id = f"check:{member}:prompt-load"
    prompt_obligation = f"obligation:researchguard:{member}:prompt-load"
    native_obligation = f"obligation:researchguard:{member}:native-tests"
    deepening_check_id = f"check:{member}:task-model-closure"
    deepening_obligation = f"obligation:researchguard:{member}:task-model-closure"
    route_id = f"route:researchguard:{member}"
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
            ],
            depends=[],
            obligation=contract_obligation,
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
                {"kind": "path", "path": "researchguard/prompt_bundle_manifest.json"},
                {"kind": "path", "path": "scripts/check_prompt_bundles.py"},
                {"kind": "path", "path": "tests/test_prompt_bundles.py"},
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
            obligation=prompt_obligation,
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
            ],
            depends=[prompt_check_id],
            obligation=native_obligation,
            timeout=900,
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
            obligation=deepening_obligation,
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
        "implementation_paths": IMPLEMENTATION_PATHS[member],
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
                    deepening_obligation,
                ],
            }
        ],
        "judgment_rubrics": [],
        "claim_boundary": (
            f"This contract covers the current {member} consumer projection, "
            f"native route, and member-owned tests inside ResearchGuard v{RESEARCHGUARD_VERSION}. "
            "It does not prove source truth, unrun external work, installation, "
            "publication, or future AI behavior."
        ),
    }


def validation_plan() -> dict:
    skillguard_version = _installed_version("skillguard", SKILLGUARD_VERSION)
    flowguard_version = _installed_version("flowguard", FLOWGUARD_VERSION)
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
        "status": "frozen",
        "maintenance_unit_id": UNIT_ID,
        "member_skill_ids": list(MEMBERS),
        "toolchain": {
            "skillguard_version": skillguard_version,
            "skillguard_source_revision": _skillguard_source_fingerprint(),
            "flowguard_version": flowguard_version,
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
            "This freezes the exact same-unit owner inventory for the current local "
            "maintenance change. It does not itself execute a check, activate a "
            "consumer installation, publish a release, or retire predecessor repositories."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-validation-plan", action="store_true")
    args = parser.parse_args(argv)
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
                "validation_plan_written": args.write_validation_plan,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
