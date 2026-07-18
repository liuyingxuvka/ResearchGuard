"""Prove TraceGuard family capability and an explicit task-model purpose.

``guard-model`` is a family regression baseline and native-oracle catalog.  It
is deliberately not a production purpose declaration.  A real model instance
is proved separately from its target-local task contract.
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Callable
from unittest.mock import patch

import yaml


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _native_api(skill_root: Path):
    runtime = skill_root / "runtime"
    if not (runtime / "traceguard" / "storyline_depth.py").is_file():
        runtime = skill_root / "skills" / "traceguard" / "runtime"
    if not (runtime / "traceguard" / "storyline_depth.py").is_file():
        raise RuntimeError("bundled TraceGuard runtime is missing")
    sys.path.insert(0, str(runtime))
    from researchguard.trace.evaluator import evaluate_model
    from researchguard.trace.loader import load_model
    from researchguard.trace.purpose_contract import (
        canonical_guard_contract_fingerprint,
        prove_task_guard_contract,
    )
    from researchguard.trace.schema import TraceGuardModel
    from researchguard.trace.storyline_depth import evaluate_storyline_depth
    from researchguard.trace.validation import validate_references

    return (
        evaluate_model,
        evaluate_storyline_depth,
        load_model,
        TraceGuardModel,
        validate_references,
        canonical_guard_contract_fingerprint,
        prove_task_guard_contract,
    )


def _run_scenarios(skill_root: Path) -> dict[str, bool]:
    (
        evaluate_model,
        evaluate_storyline_depth,
        load_model,
        TraceGuardModel,
        validate_references,
        _,
        _,
    ) = _native_api(skill_root)
    example_path = skill_root / "examples" / "project_radar_hydrogen_trace.yaml"
    negative_path = skill_root / "examples" / "operation_before_tender_contradiction.yaml"
    base = yaml.safe_load(example_path.read_text(encoding="utf-8"))

    def model(data: dict):
        value = TraceGuardModel.from_dict(data)
        validate_references(value)
        return value

    def receipt(data: dict):
        return evaluate_model(model(data)).storyline_depth

    def known_good() -> bool:
        value = evaluate_model(load_model(example_path)).storyline_depth
        return bool(
            value
            and value.closure_status == "PASS"
            and value.broad_claim_licensed
            and not value.critical_uncovered_ids
            and not value.critical_ineffective_ids
            and not value.sensitivity_mismatch_ids
            and not value.predictive_claim_licensed
        )

    def missing_event_evidence() -> bool:
        data = deepcopy(base)
        data["events"][0]["evidence_ids"] = []
        value = receipt(data)
        return value.closure_status == "BLOCKED" and not value.broad_claim_licensed

    def caller_output_authority() -> bool:
        from researchguard.trace.schema import SchemaError

        data = deepcopy(base)
        data["traces"][0]["validation_status"] = "validated"
        try:
            model(data)
        except SchemaError:
            return True
        return False

    def duplicate_lineage_overcount() -> bool:
        baseline = evaluate_model(
            model(deepcopy(base)),
            include_storyline_depth=False,
        ).traces[0].support
        data = deepcopy(base)
        source = deepcopy(data["sources"][0])
        original_source_id = source["source_id"]
        source["source_id"] = "guard_duplicate_source"
        source["derived_from_source_ids"] = [original_source_id]
        data["sources"].append(source)
        evidence = deepcopy(data["evidence"][0])
        original_evidence_id = evidence["evidence_id"]
        evidence["evidence_id"] = "guard_duplicate_evidence"
        evidence["source_id"] = source["source_id"]
        data["evidence"].append(evidence)
        for event in data["events"]:
            if original_evidence_id in event["evidence_ids"]:
                event["evidence_ids"].append(evidence["evidence_id"])
                break
        duplicated = evaluate_model(
            model(data),
            include_storyline_depth=False,
        ).traces[0].support
        return abs(baseline - duplicated) <= 1e-8

    def hard_gate_compensation() -> bool:
        data = deepcopy(base)
        data["sources"][0]["source_status"] = "invalid_or_empty"
        data["sources"][0]["source_reliability"] = 1.0
        for evidence in data["evidence"]:
            evidence["extraction_confidence"] = 1.0
            evidence["evidence_specificity"] = 1.0
        result = evaluate_model(model(data), include_storyline_depth=False)
        return bool(
            result.traces[0].support <= 1e-8
            and result.traces[0].validation_status != "validated"
            and any(
                item.diagnostic_id == "invalid_source_not_validation_evidence"
                for item in result.diagnostics
            )
        )

    def solver_fallback() -> bool:
        from researchguard.trace.inference.types import SolverError

        with patch(
            "researchguard.trace.inference.osqp_backend.osqp.OSQP",
            side_effect=RuntimeError("guard-forced-backend-failure"),
        ):
            try:
                evaluate_model(model(deepcopy(base)), include_storyline_depth=False)
            except SolverError:
                return True
        return False

    def detached_explanation() -> bool:
        from researchguard.trace.inference.engine import verify_inference_receipt

        inference_receipt = evaluate_model(
            model(deepcopy(base)),
            include_storyline_depth=False,
        ).inference_receipt
        projection = replace(
            inference_receipt.trace_projections[0],
            top_support_factor_ids=("detached-factor",),
        )
        detached = replace(
            inference_receipt,
            trace_projections=(
                projection,
                *inference_receipt.trace_projections[1:],
            ),
        )
        try:
            verify_inference_receipt(detached)
        except ValueError:
            return True
        return False

    def perturbation_without_reinference() -> bool:
        value = receipt(deepcopy(base))
        return bool(
            value.effects
            and all(
                effect.baseline_inference_receipt_id
                and effect.perturbed_inference_receipt_id
                and effect.baseline_inference_receipt_id
                != effect.perturbed_inference_receipt_id
                and effect.baseline_problem_fingerprint
                != effect.perturbed_problem_fingerprint
                and effect.baseline_solver_id == effect.perturbed_solver_id
                for effect in value.effects
            )
        )

    def hidden_temporal_contradiction() -> bool:
        value = evaluate_model(load_model(negative_path)).storyline_depth
        return value.closure_status == "BLOCKED" and "baseline_model_not_ok" in {
            row["gap_id"] for row in value.unresolved_gaps
        }

    def chronology_promoted_to_causality() -> bool:
        data = deepcopy(base)
        data["storyline_hypotheses"][0].update(
            {"causal": True, "bounded_non_causal": False, "mechanism_ids": [], "confounder_ids": []}
        )
        data["causal_mechanisms"] = []
        data["confounder_reviews"] = []
        data["causal_scopes"] = []
        data["causal_candidates"] = [
            {
                "causal_id": "causal_guard_incomplete",
                "hypothesis_id": "h_implementation",
                "cause_event_ids": ["event_funding"],
                "effect_event_ids": ["event_tender"],
                "mechanism_ids": [],
                "confounder_ids": [],
                "alternative_hypothesis_ids": ["h_public_signal_only"],
                "scope_id": None,
            }
        ]
        value = receipt(data)
        gaps = {row["gap_id"] for row in value.unresolved_gaps}
        return value.closure_status == "BLOCKED" and {
            "missing_causal_mechanism",
            "missing_confounder_review",
        } <= gaps

    def untested_critical_perturbation() -> bool:
        current = model(deepcopy(base))
        baseline = evaluate_model(current, include_storyline_depth=False)
        value = evaluate_storyline_depth(current, baseline, max_perturbations=1)
        return bool(
            value.closure_status == "GAP"
            and value.critical_uncovered_ids
            and not value.broad_claim_licensed
        )

    def shallow_trace_temporal_depth() -> bool:
        data = deepcopy(base)
        data["traces"][0]["event_ids"] = ["event_funding"]
        data["storyline_hypotheses"] = []
        data["hypothesis_evidence_links"] = []
        data["hypothesis_relations"] = []
        data["causal_mechanisms"] = []
        data["confounder_reviews"] = []
        data["causal_scopes"] = []
        data["causal_candidates"] = []
        data["evidence_ablations"] = []
        data["scenario_perturbations"] = []
        data["expected_sensitivities"] = []
        value = receipt(data)
        return value.closure_status == "BLOCKED" and any(
            row["object_type"] == "trace"
            and "trace_event_count_below_native_floor" in row["findings"]
            for row in value.object_depth_rows
        )

    def unresolved_causal_confounder() -> bool:
        data = deepcopy(base)
        data["storyline_hypotheses"][0].update(
            {
                "causal": True,
                "bounded_non_causal": False,
                "mechanism_ids": ["m_guard"],
                "confounder_ids": ["c_guard"],
            }
        )
        data["causal_mechanisms"] = [
            {
                "mechanism_id": "m_guard",
                "hypothesis_id": data["storyline_hypotheses"][0]["hypothesis_id"],
                "description": "Funding enables tender activity.",
                "evidence_ids": ["ev_funding"],
                "declared_relevance": 1.0,
            }
        ]
        data["confounder_reviews"] = [
            {
                "confounder_id": "c_guard",
                "hypothesis_id": data["storyline_hypotheses"][0]["hypothesis_id"],
                "description": "Concurrent policy activity may explain timing.",
                "status": "unresolved",
                "evidence_ids": ["ev_company"],
            }
        ]
        data["causal_scopes"] = [
            {
                "scope_id": "scope_guard",
                "description": "The declared project and evidence period.",
                "time_window": "declared evidence period",
                "boundary_conditions": ["No transfer outside this project."],
            }
        ]
        data["causal_candidates"] = [
            {
                "causal_id": "causal_guard_unresolved",
                "hypothesis_id": "h_implementation",
                "cause_event_ids": ["event_funding"],
                "effect_event_ids": ["event_tender"],
                "mechanism_ids": ["m_guard"],
                "confounder_ids": ["c_guard"],
                "alternative_hypothesis_ids": ["h_public_signal_only"],
                "scope_id": "scope_guard",
            }
        ]
        value = receipt(data)
        return value.closure_status == "BLOCKED" and "unresolved_confounder_review" in {
            row["gap_id"] for row in value.unresolved_gaps
        }

    def expected_sensitivity_mismatch() -> bool:
        data = deepcopy(base)
        data["expected_sensitivities"][0]["expected_direction"] = "increase"
        value = receipt(data)
        return bool(value.sensitivity_mismatch_ids and not value.broad_claim_licensed)

    def internal_perturbation_promoted_to_prediction() -> bool:
        data = deepcopy(base)
        data["metadata"]["storyline_depth_policy"] = {"prediction_requested": True}
        value = receipt(data)
        return bool(
            value.closure_status == "BLOCKED"
            and value.predictive_holdout_status == "unsupported_without_native_future_holdout"
            and not value.predictive_claim_licensed
        )

    def bounded_scope_promoted_to_broad() -> bool:
        current = model(deepcopy(base))
        baseline = evaluate_model(current, include_storyline_depth=False)
        value = evaluate_storyline_depth(current, baseline, requested_claim_scope="bounded")
        return value.closure_status == "PASS" and not value.broad_claim_licensed

    scenarios: dict[str, Callable[[], bool]] = {
        "known_good": known_good,
        "missing_event_evidence": missing_event_evidence,
        "caller_output_authority": caller_output_authority,
        "duplicate_lineage_overcount": duplicate_lineage_overcount,
        "hard_gate_compensation": hard_gate_compensation,
        "solver_fallback": solver_fallback,
        "detached_explanation": detached_explanation,
        "perturbation_without_reinference": perturbation_without_reinference,
        "hidden_temporal_contradiction": hidden_temporal_contradiction,
        "chronology_promoted_to_causality": chronology_promoted_to_causality,
        "untested_critical_perturbation": untested_critical_perturbation,
        "shallow_trace_temporal_depth": shallow_trace_temporal_depth,
        "unresolved_causal_confounder": unresolved_causal_confounder,
        "expected_sensitivity_mismatch": expected_sensitivity_mismatch,
        "internal_perturbation_promoted_to_prediction": internal_perturbation_promoted_to_prediction,
        "bounded_scope_promoted_to_broad": bounded_scope_promoted_to_broad,
    }
    return {name: bool(run()) for name, run in scenarios.items()}


def prove_all(skill_root: Path, task_contract: Path | None = None) -> dict:
    contract = _load_json(skill_root / "guard-model" / "contract.json")
    oracles = _load_json(skill_root / "guard-model" / "oracles.json")
    known_good = _load_json(skill_root / "guard-model" / "known-good.json")
    known_bad = _load_json(skill_root / "guard-model" / "known-bad.json")
    (
        _,
        _,
        _,
        _,
        _,
        canonical_guard_contract_fingerprint,
        prove_task_guard_contract,
    ) = _native_api(skill_root)
    failure_ids = contract["external_universe"]["failure_class_ids"]
    bad_rows = known_bad["cases"]
    native_contract = contract.get("native_execution_contract", {})
    universe_ids = [
        row.get("universe_id")
        for row in native_contract.get("universe_policies", [])
        if isinstance(row, dict)
    ]
    calibration_rows = native_contract.get("calibration_checks", [])
    bad_by_failure = {failure_id: [] for failure_id in failure_ids}
    for row in bad_rows:
        if row.get("failure_class_id") in bad_by_failure:
            bad_by_failure[row["failure_class_id"]].append(row)
    shape_ok = (
        contract.get("schema_version") == "researchguard.trace.guard_family_baseline.v1"
        and contract.get("contract_kind") == "family_baseline"
        and contract.get("authority_scope") == "family_capability_regression"
        and contract.get("production_authority") is False
        and "candidate_binding_contract" not in contract
        and all(
            artifact.get("contract_kind") == "family_baseline"
            and artifact.get("authority_scope")
            == "family_capability_regression"
            and artifact.get("production_authority") is False
            for artifact in (oracles, known_good, known_bad)
        )
        and contract.get("enforcement") == "enforced"
        and contract.get("native_owner_id") == "researchguard.trace.inference"
        and contract.get("fixed_route_id") == "researchguard.trace.inference"
        and len(known_good["cases"]) == 1
        and set(bad_by_failure) == set(failure_ids)
        and all(len(rows) == 1 for rows in bad_by_failure.values())
        and native_contract.get("production_check_id") == "check:traceguard-native-depth"
        and native_contract.get("evidence_domain") == "scheduled_production"
        and set(universe_ids)
        == {
            "universe:traceguard-inference-receipts",
            "universe:traceguard-storyline-objects",
            "universe:traceguard-perturbations",
            "universe:traceguard-trace-events",
        }
        and len(universe_ids) == len(set(universe_ids)) == 4
        and {
            (row.get("case_kind"), row.get("expected_status"))
            for row in calibration_rows
            if isinstance(row, dict)
        }
        == {
            ("positive", "EXECUTION_DEPTH_PASS"),
            ("shallow", "SHALLOW_BLOCKED"),
        }
        and {row["oracle_id"] for row in oracles["oracles"]}
        == {"oracle:traceguard:known-good"} | {row["native_oracle_id"] for row in contract["failure_classes"]}
    )
    scenario_results = _run_scenarios(skill_root)
    case_results = []
    for row in known_good["cases"] + bad_rows:
        passed = scenario_results.get(row["scenario"], False)
        case_results.append({"case_id": row["case_id"], "passed": passed})
    family_passed = shape_ok and all(row["passed"] for row in case_results)
    task_proof = None
    if task_contract is not None:
        task_proof = prove_task_guard_contract(
            task_contract,
            family_catalog_path=skill_root / "guard-model" / "contract.json",
        )
    passed = family_passed and (
        task_proof is None or task_proof.get("status") == "passed"
    )
    return {
        "artifact_kind": "traceguard_family_baseline_proof",
        "status": "passed" if passed else "blocked",
        "authority_scope": "family_capability_regression",
        "production_authority": False,
        "model_id": contract["model_id"],
        "failure_class_count": len(failure_ids),
        "known_good_count": len(known_good["cases"]),
        "known_bad_count": len(bad_rows),
        "native_universe_count": len(universe_ids),
        "calibration_check_count": len(calibration_rows),
        "family_catalog_fingerprint": canonical_guard_contract_fingerprint(contract),
        "family_case_results": case_results,
        "task_model_purpose_proof": task_proof,
        "claim_boundary": contract["claim_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prove-all", "prove-task"))
    parser.add_argument("--skill-root", required=True)
    parser.add_argument("--task-contract")
    args = parser.parse_args()
    skill_root = Path(args.skill_root).resolve()
    if args.command == "prove-task":
        if not args.task_contract:
            parser.error("prove-task requires --task-contract")
        *_, prove_task_guard_contract = _native_api(skill_root)
        result = prove_task_guard_contract(
            Path(args.task_contract).resolve(),
            family_catalog_path=skill_root / "guard-model" / "contract.json",
        )
    else:
        result = prove_all(
            skill_root,
            Path(args.task_contract).resolve() if args.task_contract else None,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
