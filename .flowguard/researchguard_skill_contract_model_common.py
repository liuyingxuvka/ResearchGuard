"""Current SkillGuard contract exports for ResearchGuard suite members."""

from __future__ import annotations

from typing import Any

import flowguard


MEMBERS = ("researchguard", "logicguard", "sourceguard", "traceguard")


def build_contract_model(member: str) -> dict[str, Any]:
    if member not in MEMBERS:
        raise ValueError(f"unknown ResearchGuard suite member: {member}")

    route_id = f"route:researchguard:{member}"
    function_id = f"function:researchguard:{member}"
    contract_step = f"step:researchguard:{member}:contract"
    tests_step = f"step:researchguard:{member}:tests"
    success_step = f"step:researchguard:{member}:success"
    blocked_step = f"step:researchguard:{member}:blocked"
    contract_obligation = f"obligation:researchguard:{member}:consumer-contract"
    native_obligation = f"obligation:researchguard:{member}:native-tests"
    contract_invariant = f"invariant:researchguard:{member}:consumer-contract"
    native_invariant = f"invariant:researchguard:{member}:native-tests"

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
                    tests_step,
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
                "step_id": tests_step,
                "route_id": route_id,
                "owner_id": member,
                "action_kind": "validator",
                "prerequisite_step_ids": [contract_step],
                "terminal_kind": "",
            },
            {
                "step_id": success_step,
                "route_id": route_id,
                "owner_id": member,
                "action_kind": "terminal",
                "prerequisite_step_ids": [tests_step],
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
        "invariant_ids": [contract_invariant, native_invariant],
        "obligations": [
            {
                "obligation_id": contract_obligation,
                "invariant_id": contract_invariant,
                "owner_step_ids": [contract_step],
                "required": True,
                "description": "The public consumer entry and internal route inventory are exact.",
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
