"""Current SkillGuard contract exports for ResearchGuard suite members."""

from __future__ import annotations

from typing import Any

import flowguard


MEMBERS = (
    "researchguard",
    "logicguard",
    "sourceguard",
    "traceguard",
    "experimentguard",
)


def build_contract_model(member: str) -> dict[str, Any]:
    if member not in MEMBERS:
        raise ValueError(f"unknown ResearchGuard suite member: {member}")

    route_id = f"route:researchguard:{member}"
    function_id = f"function:researchguard:{member}"
    contract_step = f"step:researchguard:{member}:contract"
    prompt_step = f"step:researchguard:{member}:prompt-load"
    tests_step = f"step:researchguard:{member}:tests"
    deepening_step = f"step:researchguard:{member}:task-model-closure"
    success_step = f"step:researchguard:{member}:success"
    blocked_step = f"step:researchguard:{member}:blocked"
    contract_obligation = f"obligation:researchguard:{member}:consumer-contract"
    prompt_obligation = f"obligation:researchguard:{member}:prompt-load"
    native_obligation = f"obligation:researchguard:{member}:native-tests"
    deepening_obligation = f"obligation:researchguard:{member}:task-model-closure"
    contract_invariant = f"invariant:researchguard:{member}:consumer-contract"
    prompt_invariant = f"invariant:researchguard:{member}:prompt-load"
    native_invariant = f"invariant:researchguard:{member}:native-tests"
    deepening_invariant = f"invariant:researchguard:{member}:task-model-closure"

    return {
        "schema_version": "skillguard.flowguard_model_export.v2",
        "flowguard_schema_version": str(flowguard.SCHEMA_VERSION),
        "model_id": f"researchguard.{member}.contract.current",
        "parent_model_id": "researchguard.suite.route-authority.current",
        "maintenance_unit_id": "unit:researchguard-suite",
        "member_skill_ids": list(MEMBERS),
        "claim_boundary": (
            f"This model binds only the current {member} consumer projection and "
            "member-owned native regression route inside the unified ResearchGuard "
            "maintenance unit. Installation, publication, and unrun work remain "
            "outside this model."
        ),
        "functions": [
            {
                "function_id": function_id,
                "business_intent": (
                    f"Maintain the current {member} consumer boundary without "
                    "aliases, compatibility readers, or alternate launch paths."
                ),
                "owner_id": member,
                "route_ids": [route_id],
                "signature": "Input x State -> Set(Output x State)",
            }
        ],
        "routes": [
            {
                "route_id": route_id,
                "function_id": function_id,
                "owner_id": member,
                "step_ids": [
                    contract_step,
                    prompt_step,
                    tests_step,
                    deepening_step,
                    success_step,
                    blocked_step,
                ],
                "success_terminal_step_id": success_step,
                "blocked_terminal_step_id": blocked_step,
                "handoffs": [],
            }
        ],
        "steps": [
            {
                "step_id": contract_step,
                "route_id": route_id,
                "owner_id": member,
                "action_kind": "validator",
                "prerequisite_step_ids": [],
                "terminal_kind": "",
            },
            {
                "step_id": prompt_step,
                "route_id": route_id,
                "owner_id": member,
                "action_kind": "validator",
                "prerequisite_step_ids": [contract_step],
                "terminal_kind": "",
            },
            {
                "step_id": tests_step,
                "route_id": route_id,
                "owner_id": member,
                "action_kind": "validator",
                "prerequisite_step_ids": [prompt_step],
                "terminal_kind": "",
            },
            {
                "step_id": deepening_step,
                "route_id": route_id,
                "owner_id": member,
                "action_kind": "native",
                "prerequisite_step_ids": [tests_step],
                "terminal_kind": "",
            },
            {
                "step_id": success_step,
                "route_id": route_id,
                "owner_id": member,
                "action_kind": "terminal",
                "prerequisite_step_ids": [deepening_step],
                "terminal_kind": "success",
            },
            {
                "step_id": blocked_step,
                "route_id": route_id,
                "owner_id": member,
                "action_kind": "terminal",
                "prerequisite_step_ids": [],
                "terminal_kind": "blocked",
            },
        ],
        "invariant_ids": [contract_invariant, prompt_invariant, native_invariant, deepening_invariant],
        "obligations": [
            {
                "obligation_id": contract_obligation,
                "invariant_id": contract_invariant,
                "owner_step_ids": [contract_step],
                "required": True,
                "description": "The public consumer entry and internal route inventory are exact.",
            },
            {
                "obligation_id": prompt_obligation,
                "invariant_id": prompt_invariant,
                "owner_step_ids": [prompt_step],
                "required": True,
                "description": "The selected entry and conditional reference load graph are current and contain no eager sibling path.",
            },
            {
                "obligation_id": deepening_obligation,
                "invariant_id": deepening_invariant,
                "owner_step_ids": [deepening_step],
                "required": True,
                "description": "The target-owned task-local model closure check passes with no addressable gap.",
            },
            {
                "obligation_id": native_obligation,
                "invariant_id": native_invariant,
                "owner_step_ids": [tests_step],
                "required": True,
                "description": "The member-owned current native regression suite passes.",
            },
        ],
    }
