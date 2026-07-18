"""Strict execution-depth validation for LogicGuard internal routes."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


PACKAGE_SCHEMA = "researchguard.logic.route-execution-package.v1"
RECEIPT_SCHEMA = "researchguard.logic.route-execution-receipt.v1"


@dataclass(frozen=True)
class RoutePolicy:
    route_id: str
    required_obligation_ids: tuple[str, ...]
    per_unit_role_ids: tuple[str, ...]


ROUTE_POLICIES = {
    "artifact-synthesis": RoutePolicy(
        "artifact-synthesis",
        (
            "target_story_goal",
            "complete_target_unit_inventory",
            "important_claim_support",
            "source_and_gap_reconciliation",
            "synthesis_blueprints",
            "delivery_boundary",
            "postwrite_freshness",
        ),
        (
            "parent_goal",
            "unit_job",
            "support_path",
            "downstream_consumer",
            "final_treatment",
        ),
    ),
    "model-deepening": RoutePolicy(
        "model-deepening",
        (
            "important_node_inventory",
            "under_modeling_diagnostics",
            "recursive_expansions",
            "role_completion",
            "perturbation_coverage",
            "stopping_and_budget_boundary",
            "next_route_handoff",
        ),
        (
            "under_modeling_diagnostic",
            "selected_action",
            "role_completion",
            "perturbation",
            "stopping_boundary",
        ),
    ),
    "project-library-viewer": RoutePolicy(
        "project-library-viewer",
        (
            "selected_library_identity",
            "selected_project_or_source_scope",
            "headless_check",
            "active_view_or_package_operation",
            "safe_io_result",
            "visible_graph_boundary",
            "side_effect_closure",
        ),
        (
            "object_identity",
            "visible_graph",
            "operation_outcome",
            "side_effect_boundary",
        ),
    ),
    "source-library": RoutePolicy(
        "source-library",
        (
            "selected_source_inventory",
            "preservation_and_deduplication",
            "content_model_depth",
            "claim_source_links",
            "temporal_metadata",
            "important_path_disposition",
            "intake_closure",
        ),
        (
            "preservation",
            "content_model",
            "source_role",
            "link_or_disposition",
            "temporal_context",
        ),
    ),
    "structured-artifact": RoutePolicy(
        "structured-artifact",
        (
            "complete_artifact_unit_inventory",
            "structural_contributions",
            "claim_source_roles",
            "opposition_and_alternatives",
            "handoff_and_downstream_use",
            "limitations",
            "licensed_scope",
        ),
        (
            "parent_goal",
            "structural_contribution",
            "support_path",
            "opposition_or_disposition",
            "downstream_consumer",
            "limitation",
        ),
    ),
}


def canonical_sha256(value: Any) -> str:
    body = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _ids(value: Any, field: str, errors: list[str]) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        errors.append(f"{field}:nonempty-string-array-required")
        return ()
    normalized = tuple(item.strip() for item in value)
    if len(set(normalized)) != len(normalized):
        errors.append(f"{field}:duplicate-id")
    return normalized


def evaluate_route_execution_package(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if payload.get("schema_version") != PACKAGE_SCHEMA:
        errors.append("schema_version:current-schema-required")
    route_id = str(payload.get("route_id", "")).strip()
    policy = ROUTE_POLICIES.get(route_id)
    if policy is None:
        errors.append("route_id:unknown-internal-route")
    run_id = str(payload.get("run_id", "")).strip()
    if not run_id:
        errors.append("run_id:required")
    claim_boundary = str(payload.get("claim_boundary", "")).strip()
    if not claim_boundary:
        errors.append("claim_boundary:required")
    blockers = payload.get("blockers")
    if not isinstance(blockers, list):
        errors.append("blockers:array-required")
        blockers = []
    elif blockers:
        errors.append("blockers:unresolved")

    obligations = payload.get("obligation_results")
    obligation_map: dict[str, Mapping[str, Any]] = {}
    if not isinstance(obligations, list):
        errors.append("obligation_results:array-required")
    else:
        for index, row in enumerate(obligations):
            if not isinstance(row, Mapping):
                errors.append(f"obligation_results[{index}]:object-required")
                continue
            obligation_id = str(row.get("obligation_id", "")).strip()
            if not obligation_id or obligation_id in obligation_map:
                errors.append(f"obligation_results[{index}]:unique-id-required")
                continue
            obligation_map[obligation_id] = row
            if row.get("status") != "pass":
                errors.append(f"obligation_results[{index}]:terminal-pass-required")
            evidence_ref = str(row.get("evidence_ref", "")).strip()
            evidence_sha256 = str(row.get("evidence_sha256", "")).lower()
            if not evidence_ref or len(evidence_sha256) != 64:
                errors.append(f"obligation_results[{index}]:bound-evidence-required")
    if policy is not None and set(obligation_map) != set(
        policy.required_obligation_ids
    ):
        errors.append("obligation_results:exact-current-inventory-required")

    universe = payload.get("unit_universe")
    if not isinstance(universe, Mapping):
        errors.append("unit_universe:object-required")
        eligible: set[str] = set()
    else:
        declared = set(_ids(universe.get("declared_unit_ids"), "declared_unit_ids", errors))
        required = set(_ids(universe.get("required_unit_ids"), "required_unit_ids", errors))
        important = set(_ids(universe.get("important_unit_ids"), "important_unit_ids", errors))
        evaluated = set(_ids(universe.get("evaluated_unit_ids"), "evaluated_unit_ids", errors))
        excluded = set(_ids(universe.get("excluded_unit_ids", []), "excluded_unit_ids", errors))
        eligible = declared - excluded
        if not declared:
            errors.append("unit_universe:empty")
        if not required.issubset(declared) or not important.issubset(declared):
            errors.append("unit_universe:required-or-important-outside-declared")
        if evaluated != eligible:
            errors.append("unit_universe:eligible-units-not-fully-evaluated")

    units = payload.get("unit_results")
    unit_map: dict[str, Mapping[str, Any]] = {}
    if not isinstance(units, list):
        errors.append("unit_results:array-required")
    else:
        for index, row in enumerate(units):
            if not isinstance(row, Mapping):
                errors.append(f"unit_results[{index}]:object-required")
                continue
            unit_id = str(row.get("unit_id", "")).strip()
            if not unit_id or unit_id in unit_map:
                errors.append(f"unit_results[{index}]:unique-id-required")
                continue
            unit_map[unit_id] = row
            role_rows = row.get("role_results")
            if not isinstance(role_rows, list):
                errors.append(f"unit_results[{index}]:role-results-required")
                continue
            roles = {
                str(role.get("role_id", "")).strip()
                for role in role_rows
                if isinstance(role, Mapping)
                and role.get("status") == "pass"
                and str(role.get("evidence_ref", "")).strip()
                and len(str(role.get("evidence_sha256", ""))) == 64
            }
            if policy is not None and roles != set(policy.per_unit_role_ids):
                errors.append(f"unit_results[{index}]:exact-route-roles-required")
    if set(unit_map) != eligible:
        errors.append("unit_results:exact-eligible-unit-inventory-required")

    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "status": "pass" if not errors else "blocked",
        "route_id": route_id,
        "run_id": run_id,
        "input_fingerprint": canonical_sha256(payload),
        "required_obligation_ids": (
            list(policy.required_obligation_ids) if policy else []
        ),
        "covered_obligation_ids": sorted(obligation_map),
        "evaluated_unit_ids": sorted(unit_map),
        "errors": errors,
        "blockers": list(blockers),
        "claim_boundary": claim_boundary,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate one current LogicGuard internal-route execution package."
    )
    parser.add_argument("package", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    payload = json.loads(args.package.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("route execution package must be a JSON object")
    receipt = evaluate_route_execution_package(payload)
    rendered = json.dumps(
        receipt,
        ensure_ascii=False,
        indent=2 if args.pretty else None,
        sort_keys=True,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if receipt["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
