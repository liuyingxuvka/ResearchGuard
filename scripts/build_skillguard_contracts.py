"""Build the one ResearchGuard maintenance unit's four author-side contracts."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEMBERS = ("researchguard", "logicguard", "sourceguard", "traceguard")
UNIT_ID = "unit:researchguard-suite"

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
}

IMPLEMENTATION_PATHS = {
    "researchguard": [
        "skills/researchguard",
        "src/researchguard/__init__.py",
        "src/researchguard/__main__.py",
        "src/researchguard/cli.py",
        "src/researchguard/routing.py",
        "src/researchguard/suite.py",
        ".flowguard/researchguard_skill_contract_model.py",
        ".flowguard/researchguard_skill_contract_model_common.py",
        "scripts/check_researchguard_suite.py",
        "scripts/check_zero_residuals.py",
        "scripts/install_researchguard.py",
        "tests/test_suite_routing.py",
        "tests/test_root_cli.py",
        "tests/test_skill_suite.py",
        "tests/test_install_researchguard.py",
        "tests/test_zero_residuals.py",
    ],
    "logicguard": [
        "skills/logicguard",
        "src/researchguard/logic",
        "src/researchguard/logic_template_packs",
        "src/researchguard/logic_viewer",
        ".flowguard/logicguard_skill_contract_model.py",
        ".flowguard/researchguard_skill_contract_model_common.py",
        "tests/logic",
    ],
    "sourceguard": [
        "skills/sourceguard",
        "src/researchguard/source",
        ".flowguard/sourceguard_skill_contract_model.py",
        ".flowguard/researchguard_skill_contract_model_common.py",
        "examples/source",
        "tests/source",
    ],
    "traceguard": [
        "skills/traceguard",
        "src/researchguard/trace",
        ".flowguard/traceguard_skill_contract_model.py",
        ".flowguard/researchguard_skill_contract_model_common.py",
        "tests/trace",
    ],
}


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
    native_obligation = f"obligation:researchguard:{member}:native-tests"
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
            depends=[contract_check_id],
            obligation=native_obligation,
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
                "binding_id": f"native-check:researchguard:{member}:native-tests",
                "native_check_id": f"check:{member}:native-tests",
                "required": True,
                "evidence_source": "tests",
            },
        ],
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
                "step_id": f"step:researchguard:{member}:tests",
                "action": {
                    "kind": "native",
                    "summary": "Execute the member-owned current native regression suite.",
                },
                "check_ids": [f"check:{member}:native-tests"],
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
                    native_obligation,
                ],
            }
        ],
        "judgment_rubrics": [],
        "claim_boundary": (
            f"This contract covers the current {member} consumer projection, "
            "native route, and member-owned tests inside ResearchGuard v0.1.2. "
            "It does not prove source truth, unrun external work, installation, "
            "publication, or future AI behavior."
        ),
    }


def main() -> int:
    for member in MEMBERS:
        control = ROOT / "skills" / member / ".skillguard"
        control.mkdir(parents=True, exist_ok=True)
        path = control / "contract-source.json"
        path.write_text(
            json.dumps(contract(member), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({"unit": UNIT_ID, "members": MEMBERS}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
