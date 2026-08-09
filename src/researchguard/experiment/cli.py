"""ExperimentGuard command-line owner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping

from ..native_receipts import NativeReceiptReference
from ..target_authority import TargetPurposeAuthority

from .blueprint import check_blueprint, export_blueprint, impact_blueprint, reverse_trace_experiment
from .engine import observe_experiments, recommend_experiments
from .schema import (
    ExperimentConstraint,
    ExperimentChildOutputBinding,
    ExperimentDesignBlock,
    ExperimentInputBinding,
    ExperimentNativeCaseEvidence,
    ExperimentObservation,
    ExperimentPort,
    ExperimentSpec,
    ExperimentTargetUniverse,
    HypothesisPrediction,
    ProcedureStep,
)


def _require_exact_keys(
    value: Mapping[str, object],
    allowed: set[str],
    label: str,
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"{label} contains unknown current-blueprint fields: {unknown!r}")


def _require_string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise ValueError(f"{label}[{index}] must be a non-empty string")
    return value


def _load_spec(path: Path) -> ExperimentSpec:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _load_spec_payload(payload)


def _load_spec_payload(payload: object) -> ExperimentSpec:
    if not isinstance(payload, Mapping):
        raise ValueError("experiment spec root must be an object")
    blueprint_current = any(
        key in payload for key in ("design_root_id", "design_blocks", "target_universe")
    )
    if blueprint_current:
        _require_exact_keys(
            payload,
            {
                "schema_version", "task_id", "purpose", "coverage_ids", "assumptions",
                "unknowns", "iteration", "max_iterations", "hypothesis_predictions",
                "candidate_experiment_ids", "design_root_id", "design_blocks", "target_universe",
                "maximum_experiment_count", "prior_receipt_fingerprint", "prior_open_gap_ids",
            },
            "experiment blueprint",
        )
        for index, item in enumerate(payload.get("hypothesis_predictions", [])):
            _require_exact_keys(
                item,
                {"hypothesis_id", "outcomes_by_experiment", "observation_port_by_experiment", "outcome_port_by_experiment"},
                f"hypothesis_predictions[{index}]",
            )
        for index, item in enumerate(payload.get("design_blocks", [])):
            _require_exact_keys(
                item,
                {"block_id", "kind", "parent_id", "child_ids", "candidate_experiment_id", "ports", "procedure_steps", "constraints", "external_execution_owner", "consumed_child_output_port_ids", "output_dispositions", "input_bindings", "child_output_bindings"},
                f"design_blocks[{index}]",
            )
            for port_index, port in enumerate(item.get("ports", [])):
                _require_exact_keys(port, {"port_id", "kind", "schema_id", "allowed_values"}, f"design_blocks[{index}].ports[{port_index}]")
            for step_index, step in enumerate(item.get("procedure_steps", [])):
                _require_exact_keys(step, {"step_id", "order", "action", "input_port_ids", "output_port_ids"}, f"design_blocks[{index}].procedure_steps[{step_index}]")
            for constraint_index, constraint in enumerate(item.get("constraints", [])):
                _require_exact_keys(constraint, {"constraint_id", "description"}, f"design_blocks[{index}].constraints[{constraint_index}]")
            for binding_index, binding in enumerate(item.get("input_bindings", [])):
                _require_exact_keys(binding, {"binding_id", "consumer_port_id", "producer_kind", "producer_id", "producer_port_id", "payload_schema_id", "cardinality", "owner_id"}, f"design_blocks[{index}].input_bindings[{binding_index}]")
            for binding_index, binding in enumerate(item.get("child_output_bindings", [])):
                _require_exact_keys(
                    binding,
                    {"binding_id", "child_block_id", "child_output_port_id", "parent_block_id", "parent_input_port_id", "payload_schema_id", "refinement_id", "payload_fingerprint", "producer_model_fingerprint", "producer_result_fingerprint", "producer_task_id", "receipt_id", "receipt_fingerprint", "receipt_status"},
                    f"design_blocks[{index}].child_output_bindings[{binding_index}]",
                )
        if "target_universe" in payload and not isinstance(payload["target_universe"], Mapping):
            raise ValueError("target_universe must be an object")
        if isinstance(payload.get("target_universe"), Mapping):
            _require_exact_keys(
                payload["target_universe"],
                {"universe_id", "required_hypothesis_ids", "required_discrimination_ids", "required_candidate_ids", "required_port_ids", "required_procedure_step_ids", "required_constraint_ids", "required_input_binding_ids", "required_child_output_binding_ids", "known_good_case_ids", "known_bad_case_ids", "native_case_evidence", "native_receipt_refs", "target_authority"},
                "target_universe",
            )
            for field in (
                "required_hypothesis_ids",
                "required_discrimination_ids",
                "required_candidate_ids",
                "required_port_ids",
                "required_procedure_step_ids",
                "required_constraint_ids",
                "required_input_binding_ids",
                "required_child_output_binding_ids",
                "known_good_case_ids",
                "known_bad_case_ids",
            ):
                _require_string_list(payload["target_universe"].get(field), f"target_universe.{field}")
            case_rows = payload["target_universe"].get("native_case_evidence", [])
            if not isinstance(case_rows, list):
                raise ValueError("target_universe.native_case_evidence must be a list")
            for case_index, case in enumerate(case_rows):
                if not isinstance(case, Mapping):
                    raise ValueError(f"target_universe.native_case_evidence[{case_index}] must be an object")
                _require_exact_keys(
                    case,
                    {"case_id", "case_kind", "owner_id", "native_check_id", "task_id", "subject_model_fingerprint", "prediction_matrix_fingerprint", "candidate_design_fingerprint", "target_authority_fingerprint", "failure_class_id", "case_input_fingerprint", "expected_terminal", "observed_terminal", "oracle_id", "result_fingerprint", "receipt_id", "receipt_fingerprint", "status"},
                    f"target_universe.native_case_evidence[{case_index}]",
                )
            receipt_rows = payload["target_universe"].get("native_receipt_refs", [])
            if not isinstance(receipt_rows, list) or any(
                not isinstance(item, Mapping) for item in receipt_rows
            ):
                raise ValueError("target_universe.native_receipt_refs must be a list of objects")
    universe = payload.get("target_universe")
    return ExperimentSpec(
        schema_version=str(payload.get("schema_version", "")),
        task_id=str(payload["task_id"]),
        purpose=str(payload["purpose"]),
        coverage_ids=tuple(str(item) for item in payload["coverage_ids"]),
        assumptions=tuple(str(item) for item in payload["assumptions"]),
        unknowns=tuple(str(item) for item in payload["unknowns"]),
        iteration=int(payload["iteration"]),
        max_iterations=int(payload["max_iterations"]),
        prior_receipt_fingerprint=str(payload.get("prior_receipt_fingerprint", "")),
        prior_open_gap_ids=tuple(str(item) for item in payload.get("prior_open_gap_ids", [])),
        hypothesis_predictions=tuple(
            HypothesisPrediction(
                hypothesis_id=str(item["hypothesis_id"]),
                outcomes_by_experiment={
                    str(key): str(value)
                    for key, value in item["outcomes_by_experiment"].items()
                },
                observation_port_by_experiment={
                    str(key): str(value)
                    for key, value in (item.get("observation_port_by_experiment") or {}).items()
                },
                outcome_port_by_experiment={
                    str(key): str(value)
                    for key, value in (item.get("outcome_port_by_experiment") or {}).items()
                },
            )
            for item in payload["hypothesis_predictions"]
        ),
        candidate_experiment_ids=tuple(
            str(item) for item in payload["candidate_experiment_ids"]
        ),
        maximum_experiment_count=payload.get("maximum_experiment_count"),
        design_root_id=str(payload.get("design_root_id", "")),
        design_blocks=tuple(
            ExperimentDesignBlock(
                block_id=str(item["block_id"]),
                kind=str(item["kind"]),
                parent_id=str(item.get("parent_id", "")),
                child_ids=tuple(str(value) for value in item.get("child_ids", [])),
                candidate_experiment_id=str(item.get("candidate_experiment_id", "")),
                ports=tuple(
                    ExperimentPort(
                        port_id=str(port["port_id"]),
                        kind=str(port["kind"]),
                        schema_id=str(port["schema_id"]),
                        allowed_values=tuple(str(value) for value in port.get("allowed_values", [])),
                    )
                    for port in item.get("ports", [])
                ),
                procedure_steps=tuple(
                    ProcedureStep(
                        step_id=str(step["step_id"]),
                        order=int(step["order"]),
                        action=str(step["action"]),
                        input_port_ids=tuple(str(value) for value in step.get("input_port_ids", [])),
                        output_port_ids=tuple(str(value) for value in step.get("output_port_ids", [])),
                    )
                    for step in item.get("procedure_steps", [])
                ),
                constraints=tuple(
                    ExperimentConstraint(
                        constraint_id=str(constraint["constraint_id"]),
                        description=str(constraint["description"]),
                    )
                    for constraint in item.get("constraints", [])
                ),
                external_execution_owner=str(item.get("external_execution_owner", "")),
                consumed_child_output_port_ids=tuple(
                    str(value) for value in item.get("consumed_child_output_port_ids", [])
                ),
                output_dispositions=tuple(
                    (str(value[0]), str(value[1])) for value in item.get("output_dispositions", [])
                ),
                input_bindings=tuple(
                    ExperimentInputBinding(
                        binding_id=str(binding["binding_id"]),
                        consumer_port_id=str(binding["consumer_port_id"]),
                        producer_kind=str(binding["producer_kind"]),
                        producer_id=str(binding["producer_id"]),
                        producer_port_id=str(binding.get("producer_port_id", "")),
                        payload_schema_id=str(binding["payload_schema_id"]),
                        cardinality=str(binding["cardinality"]),
                        owner_id=str(binding["owner_id"]),
                    )
                    for binding in item.get("input_bindings", [])
                ),
                child_output_bindings=tuple(
                    ExperimentChildOutputBinding(
                        binding_id=str(binding["binding_id"]),
                        child_block_id=str(binding["child_block_id"]),
                        child_output_port_id=str(binding["child_output_port_id"]),
                        parent_block_id=str(binding["parent_block_id"]),
                        parent_input_port_id=str(binding["parent_input_port_id"]),
                        payload_schema_id=str(binding["payload_schema_id"]),
                        refinement_id=str(binding["refinement_id"]),
                        payload_fingerprint=str(binding["payload_fingerprint"]),
                        producer_model_fingerprint=str(binding["producer_model_fingerprint"]),
                        producer_result_fingerprint=str(binding["producer_result_fingerprint"]),
                        producer_task_id=str(binding["producer_task_id"]),
                        receipt_id=str(binding["receipt_id"]),
                        receipt_fingerprint=str(binding["receipt_fingerprint"]),
                        receipt_status=str(binding.get("receipt_status", "current")),
                    )
                    for binding in item.get("child_output_bindings", [])
                ),
            )
            for item in payload.get("design_blocks", [])
        ),
        target_universe=(
            ExperimentTargetUniverse(
                universe_id=str(universe["universe_id"]),
                required_hypothesis_ids=tuple(str(item) for item in universe["required_hypothesis_ids"]),
                required_discrimination_ids=tuple(str(item) for item in universe["required_discrimination_ids"]),
                required_candidate_ids=tuple(str(item) for item in universe["required_candidate_ids"]),
                required_port_ids=tuple(str(item) for item in universe["required_port_ids"]),
                required_procedure_step_ids=tuple(str(item) for item in universe["required_procedure_step_ids"]),
                required_constraint_ids=tuple(str(item) for item in universe["required_constraint_ids"]),
                required_input_binding_ids=tuple(str(item) for item in universe["required_input_binding_ids"]),
                required_child_output_binding_ids=tuple(str(item) for item in universe["required_child_output_binding_ids"]),
                known_good_case_ids=tuple(str(item) for item in universe.get("known_good_case_ids", [])),
                known_bad_case_ids=tuple(str(item) for item in universe.get("known_bad_case_ids", [])),
                native_case_evidence=tuple(
                    ExperimentNativeCaseEvidence(
                        case_id=str(item["case_id"]),
                        case_kind=str(item["case_kind"]),
                        owner_id=str(item["owner_id"]),
                        native_check_id=str(item["native_check_id"]),
                        task_id=str(item["task_id"]),
                        subject_model_fingerprint=str(item["subject_model_fingerprint"]),
                        prediction_matrix_fingerprint=str(item["prediction_matrix_fingerprint"]),
                        candidate_design_fingerprint=str(item["candidate_design_fingerprint"]),
                        target_authority_fingerprint=str(item["target_authority_fingerprint"]),
                        failure_class_id=str(item["failure_class_id"]),
                        case_input_fingerprint=str(item["case_input_fingerprint"]),
                        expected_terminal=str(item["expected_terminal"]),
                        observed_terminal=str(item["observed_terminal"]),
                        oracle_id=str(item["oracle_id"]),
                        result_fingerprint=str(item["result_fingerprint"]),
                        receipt_id=str(item["receipt_id"]),
                        receipt_fingerprint=str(item["receipt_fingerprint"]),
                        status=str(item.get("status", "current")),
                    )
                    for item in universe.get("native_case_evidence", [])
                ),
                native_receipt_refs=tuple(
                    NativeReceiptReference.from_dict(item)
                    for item in universe.get("native_receipt_refs", [])
                    if isinstance(item, Mapping)
                ),
                target_authority=(
                    TargetPurposeAuthority.from_dict(universe["target_authority"])
                    if isinstance(universe.get("target_authority"), Mapping)
                    else None
                ),
            )
            if isinstance(universe, dict)
            else None
        ),
    )


def _load_observations(path: Path) -> tuple[ExperimentObservation, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("observations", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("observations artifact must contain a list")
    return tuple(
        ExperimentObservation(
            experiment_id=str(item["experiment_id"]),
            observed_outcome=str(item["observed_outcome"]),
            evidence_id=str(item["evidence_id"]),
            evidence_fingerprint=str(item["evidence_fingerprint"]),
            source_ref=str(item["source_ref"]),
            observed_at=str(item["observed_at"]),
            role=str(item["role"]),
            status=str(item.get("status", "valid")),
            observation_port_id=str(item.get("observation_port_id", "")),
            outcome_port_id=str(item.get("outcome_port_id", "")),
        )
        for item in rows
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="researchguard experiment")
    subparsers = parser.add_subparsers(dest="command", required=True)
    recommend = subparsers.add_parser("recommend")
    recommend.add_argument("spec", type=Path)
    observe = subparsers.add_parser("observe")
    observe.add_argument("spec", type=Path)
    observe.add_argument("observations", type=Path)
    iterate = subparsers.add_parser("iterate")
    iterate.add_argument("spec", type=Path)
    iterate.add_argument("observations", type=Path)
    blueprint = subparsers.add_parser("blueprint")
    blueprint_subparsers = blueprint.add_subparsers(dest="blueprint_operation", required=True)
    blueprint_check = blueprint_subparsers.add_parser("check")
    blueprint_check.add_argument("spec", type=Path)
    blueprint_impact = blueprint_subparsers.add_parser("impact")
    blueprint_impact.add_argument("spec", type=Path)
    blueprint_impact.add_argument("changed_ids", nargs="+")
    blueprint_trace = blueprint_subparsers.add_parser("trace")
    blueprint_trace.add_argument("spec", type=Path)
    blueprint_trace.add_argument("experiment_id")
    blueprint_export = blueprint_subparsers.add_parser("export")
    blueprint_export.add_argument("spec", type=Path)
    args = parser.parse_args(argv)
    if args.command == "recommend":
        result = recommend_experiments(_load_spec(args.spec))
        print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
        return 0 if result.status == "recommended" else 2
    if args.command == "blueprint" and args.blueprint_operation == "check":
        result = check_blueprint(_load_spec(args.spec))
        print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
        return 0 if result.status == "complete" else 2
    if args.command == "blueprint" and args.blueprint_operation == "impact":
        result = impact_blueprint(_load_spec(args.spec), args.changed_ids)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 3 if result["unknown_ownership"] else 0
    if args.command == "blueprint" and args.blueprint_operation == "trace":
        print(json.dumps(reverse_trace_experiment(_load_spec(args.spec), args.experiment_id), ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "blueprint" and args.blueprint_operation == "export":
        result = export_blueprint(_load_spec(args.spec))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["check"]["status"] == "complete" else 2
    receipt = observe_experiments(_load_spec(args.spec), _load_observations(args.observations))
    print(json.dumps(receipt.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0 if receipt.terminal_reason == "model_closed_for_task" else 2


if __name__ == "__main__":
    raise SystemExit(main())
