from __future__ import annotations

from researchguard.logic.route_execution_depth import (
    PACKAGE_SCHEMA,
    ROUTE_POLICIES,
    evaluate_route_execution_package,
)


def _package(route_id: str) -> dict:
    policy = ROUTE_POLICIES[route_id]
    return {
        "schema_version": PACKAGE_SCHEMA,
        "route_id": route_id,
        "run_id": "run:current-route-depth",
        "claim_boundary": "Only this current internal-route execution is covered.",
        "blockers": [],
        "obligation_results": [
            {
                "obligation_id": obligation_id,
                "status": "pass",
                "evidence_ref": f"evidence/{obligation_id}.json",
                "evidence_sha256": "a" * 64,
            }
            for obligation_id in policy.required_obligation_ids
        ],
        "unit_universe": {
            "declared_unit_ids": ["unit:1"],
            "required_unit_ids": ["unit:1"],
            "important_unit_ids": ["unit:1"],
            "excluded_unit_ids": [],
            "evaluated_unit_ids": ["unit:1"],
        },
        "unit_results": [
            {
                "unit_id": "unit:1",
                "role_results": [
                    {
                        "role_id": role_id,
                        "status": "pass",
                        "evidence_ref": f"evidence/{role_id}.json",
                        "evidence_sha256": "b" * 64,
                    }
                    for role_id in policy.per_unit_role_ids
                ],
            }
        ],
    }


def test_every_internal_route_has_one_strict_passing_shape() -> None:
    for route_id in ROUTE_POLICIES:
        receipt = evaluate_route_execution_package(_package(route_id))
        assert receipt["status"] == "pass", receipt


def test_unknown_route_does_not_redirect_to_another_owner() -> None:
    package = _package("source-library")
    package["route_id"] = "retired-or-foreign-route"
    receipt = evaluate_route_execution_package(package)
    assert receipt["status"] == "blocked"
    assert "route_id:unknown-internal-route" in receipt["errors"]
