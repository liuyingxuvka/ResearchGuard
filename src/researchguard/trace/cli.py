"""TraceGuard command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .evaluator import evaluate_model
from .export_logicguard import render_logicguard_yaml
from .inference.types import InferenceError
from . import library as case_library
from .loader import dump_yaml, load_model
from .purpose_contract import GuardPurposeContractError, bind_task_guard_purpose
from .report import render_markdown, render_text
from .schema import SchemaError
from .validation import validate_references
from .storyline_depth import (
    evaluate_storyline_depth,
    hypotheses_for_model,
    run_single_perturbation,
    select_perturbation_plan,
)
from .task_iteration import (
    TaskIterationError,
    compare_prediction_observation,
    decide_candidate_revision,
    freeze_prediction,
    load_comparison,
    load_observation,
    load_prediction,
    write_artifact,
)


STARTER_MODEL: dict[str, Any] = {
    "metadata": {
        "schema_version": "researchguard.trace.model.v2",
        "purpose": "Starter TraceGuard evidence-to-trace model.",
        "repository": "https://github.com/liuyingxuvka/ResearchGuard",
        "skill": "TraceGuard",
        "math_boundary": (
            "Typed constrained HL-MRF/MAP inference compiled to one convex QP "
            "and solved directly by OSQP; structural support is not calibrated probability."
        ),
        "cli": "researchguard trace validate starter.yaml",
        "boundary": "Source rows must become evidence, events, and traces before storyline claims.",
    },
    "sources": [
        {
            "source_id": "src_1",
            "title": "Example source",
            "url": None,
            "source_type": "other",
            "lineage_id": "lineage:src_1",
            "independence_group": "source:src_1",
            "source_reliability": 0.5,
            "source_status": "stable_keep",
            "cleaning_category": None,
        }
    ],
    "evidence": [
        {
            "evidence_id": "ev_1",
            "source_id": "src_1",
            "raw_text": "Replace with source-backed evidence.",
            "evidence_type": "unknown",
            "extraction_confidence": 0.5,
            "evidence_specificity": 0.5,
            "supports": [],
            "limits": ["starter model"],
            "warnings": [],
            "usable_as_trace_evidence": False,
            "usable_as_project_evidence": False,
        }
    ],
    "events": [],
    "traces": [],
    "storyline_hypotheses": [],
    "hypothesis_evidence_links": [],
    "hypothesis_relations": [],
    "causal_mechanisms": [],
    "confounder_reviews": [],
    "causal_scopes": [],
    "causal_candidates": [],
    "evidence_ablations": [],
    "scenario_perturbations": [],
    "expected_sensitivities": [],
}


def _print_json(data: Any, *, pretty: bool = False) -> None:
    indent = 2 if pretty else None
    print(json.dumps(data, indent=indent, sort_keys=False))


def _load_and_evaluate(path: str) -> tuple[object, object]:
    model = load_model(path)
    return model, evaluate_model(model)


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        model = load_model(args.model)
        validate_references(model)
        if not model.traces:
            _print_json(
                {
                    "ok": False,
                    "schema_ok": True,
                    "trace_count": 0,
                    "diagnostic_count": 0,
                    "gap_count": 0,
                    "contradiction_count": 0,
                    "storyline_depth_status": "NOT_RUN_EMPTY_MODEL",
                    "inference_status": "NOT_RUN_EMPTY_MODEL",
                    "traces": [],
                },
                pretty=args.pretty,
            )
            return 0
        result = evaluate_model(model)
    except (OSError, SchemaError, ValueError, InferenceError) as exc:
        _print_json({"ok": False, "error": str(exc)}, pretty=args.pretty)
        return 2
    payload = {
        "ok": result.ok,
        "schema_ok": True,
        "trace_count": len(model.traces),
        "diagnostic_count": len(result.diagnostics),
        "gap_count": len(result.gaps),
        "contradiction_count": len(result.contradictions),
        "storyline_depth_status": result.storyline_depth.closure_status
        if result.storyline_depth is not None
        else "NOT_RUN",
        "traces": [
            {
                "trace_id": trace.trace_id,
                "validation_status": trace.validation_status,
                "support": round(trace.support, 6),
            }
            for trace in result.traces
        ],
    }
    _print_json(payload, pretty=args.pretty)
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    try:
        _, result = _load_and_evaluate(args.model)
    except (OSError, SchemaError, ValueError, InferenceError) as exc:
        _print_json({"ok": False, "error": str(exc)}, pretty=args.pretty)
        return 2
    _print_json(result.to_dict(), pretty=args.pretty)
    return 0


def cmd_depth(args: argparse.Namespace) -> int:
    try:
        model = load_model(args.model)
        baseline = evaluate_model(model, include_storyline_depth=False)
        receipt = evaluate_storyline_depth(
            model,
            baseline,
            max_perturbations=args.max_perturbations,
            requested_claim_scope=args.claim_scope,
        )
    except (OSError, SchemaError, ValueError, InferenceError) as exc:
        _print_json({"ok": False, "error": str(exc)}, pretty=args.pretty)
        return 2
    _print_json(receipt.to_dict(), pretty=args.pretty)
    return 0


def cmd_diagnose(args: argparse.Namespace) -> int:
    try:
        _, result = _load_and_evaluate(args.model)
    except (OSError, SchemaError, ValueError, InferenceError) as exc:
        _print_json({"ok": False, "error": str(exc)}, pretty=args.pretty)
        return 2
    _print_json(
        {
            "ok": result.ok,
            "diagnostics": [item.to_dict() for item in result.diagnostics],
            "contradictions": [item.to_dict() for item in result.contradictions],
        },
        pretty=args.pretty,
    )
    return 0


def cmd_gaps(args: argparse.Namespace) -> int:
    try:
        _, result = _load_and_evaluate(args.model)
    except (OSError, SchemaError, ValueError, InferenceError) as exc:
        _print_json({"ok": False, "error": str(exc)}, pretty=args.pretty)
        return 2
    _print_json({"ok": result.ok, "gaps": [item.to_dict() for item in result.gaps]}, pretty=args.pretty)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    try:
        _, result = _load_and_evaluate(args.model)
    except (OSError, SchemaError, ValueError, InferenceError) as exc:
        _print_json({"ok": False, "error": str(exc)}, pretty=False)
        return 2
    if args.format == "json":
        _print_json(result.to_dict(), pretty=True)
    elif args.format == "txt":
        print(render_text(result), end="")
    else:
        print(render_markdown(result), end="")
    return 0


def cmd_export_logicguard(args: argparse.Namespace) -> int:
    try:
        _, result = _load_and_evaluate(args.model)
    except (OSError, SchemaError, ValueError, InferenceError) as exc:
        _print_json({"ok": False, "error": str(exc)}, pretty=False)
        return 2
    text = render_logicguard_yaml(result)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    try:
        text = dump_yaml(
            bind_task_guard_purpose(
                STARTER_MODEL,
                contract_path=args.purpose_contract,
                candidate_path=args.output,
            )
        )
    except GuardPurposeContractError as exc:
        _print_json({"ok": False, "error_code": exc.code, "error": str(exc)})
        return 2
    Path(args.output).write_text(text, encoding="utf-8")
    return 0


def _result_summary(result: Any) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "objective_score": result.objective_score,
        "trace_statuses": [
            {
                "trace_id": trace.trace_id,
                "validation_status": trace.validation_status,
                "support": round(trace.support, 6),
                "current_stage": trace.current_stage,
            }
            for trace in result.traces
        ],
        "diagnostic_count": len(result.diagnostics),
        "gap_count": len(result.gaps),
        "contradiction_count": len(result.contradictions),
    }


def _simulate_model(mode: str, model_path: str) -> dict[str, Any]:
    if not model_path:
        raise ValueError(f"simulate --mode {mode} requires --model <path>")
    original = load_model(model_path)
    before = evaluate_model(original, include_storyline_depth=False)
    hypotheses = hypotheses_for_model(original)
    plan, _ = select_perturbation_plan(original, hypotheses)
    target_kind = mode.replace("-", "_")
    selected = next((item for item in plan if item.kind == target_kind), None)
    if selected is None:
        raise ValueError(
            f"model-derived {mode} simulation found no relevant current-model candidate"
        )
    effect, _, after = run_single_perturbation(
        original,
        before,
        selected,
        hypotheses,
    )
    return {
        "mode": mode,
        "model": model_path,
        "perturbation": selected.to_dict(),
        "effect": effect.to_dict(),
        "before": _result_summary(before),
        "after": _result_summary(after),
        "boundary": "Model-derived local rehearsal only; no source was fetched and the original model file was not changed.",
    }


def cmd_simulate(args: argparse.Namespace) -> int:
    if args.mode in {"evidence-removal", "contradiction-injection"}:
        try:
            _print_json(_simulate_model(args.mode, args.model), pretty=args.pretty)
            return 0
        except (OSError, SchemaError, ValueError, InferenceError) as exc:
            _print_json({"ok": False, "error": str(exc)}, pretty=args.pretty)
            return 2
    if args.mode == "storyline-depth":
        try:
            model, result = _load_and_evaluate(args.model)
            if not model.traces:
                raise ValueError("storyline-depth simulation requires at least one trace")
            _print_json(result.storyline_depth.to_dict(), pretty=args.pretty)
            return 0
        except (OSError, SchemaError, ValueError, InferenceError) as exc:
            _print_json({"ok": False, "error": str(exc)}, pretty=args.pretty)
            return 2
    if args.mode == "weak-signal":
        payload = {
            "mode": args.mode,
            "expected_status": "weak_signal",
            "reason": "a single weak lane is not enough for a validated storyline claim",
        }
    elif args.mode == "projectradar":
        payload = {
            "mode": args.mode,
            "pipeline": ["source_registry", "evidence", "event", "trace_candidate", "storyline", "ProjectRadar status lane", "LogicGuard handoff"],
            "boundary": "ProjectRadar is one application; source registry row is not a project database row.",
        }
    else:
        payload = {
            "mode": args.mode,
            "pipeline": ["source", "evidence", "entity_mention", "event", "temporal_relation", "trace_candidate", "storyline", "claim_boundary", "LogicGuard handoff"],
            "boundary": "a source row is not itself a trace, storyline, incident, project, or final claim",
        }
    _print_json(payload, pretty=args.pretty)
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    try:
        before = evaluate_model(load_model(args.before))
        after = evaluate_model(load_model(args.after))
    except (OSError, SchemaError, ValueError, InferenceError) as exc:
        _print_json({"ok": False, "error": str(exc)}, pretty=args.pretty)
        return 2
    before_by_id = {trace.trace_id: trace for trace in before.traces}
    after_by_id = {trace.trace_id: trace for trace in after.traces}
    changed_traces: list[dict[str, Any]] = []
    for trace_id in sorted(set(before_by_id) & set(after_by_id)):
        old = before_by_id[trace_id]
        new = after_by_id[trace_id]
        changes: dict[str, Any] = {}
        if old.validation_status != new.validation_status:
            changes["validation_status"] = {"before": old.validation_status, "after": new.validation_status}
        if round(old.support, 6) != round(new.support, 6):
            changes["support"] = {
                "before": round(old.support, 6),
                "after": round(new.support, 6),
            }
        if old.current_stage != new.current_stage:
            changes["current_stage"] = {"before": old.current_stage, "after": new.current_stage}
        if changes:
            changed_traces.append({"trace_id": trace_id, "changes": changes})
    _print_json(
        {
            "ok": True,
            "before": args.before,
            "after": args.after,
            "trace_delta": {
                "added": sorted(set(after_by_id) - set(before_by_id)),
                "removed": sorted(set(before_by_id) - set(after_by_id)),
                "changed": changed_traces,
            },
            "diagnostic_count_delta": len(after.diagnostics) - len(before.diagnostics),
            "gap_count_delta": len(after.gaps) - len(before.gaps),
            "contradiction_count_delta": len(after.contradictions) - len(before.contradictions),
            "boundary": "Evaluation comparison shows local model support changes; it is not a new factual source.",
        },
        pretty=args.pretty,
    )
    return 0


def cmd_iterate(args: argparse.Namespace) -> int:
    """Run the task-local prediction/observation/revision lifecycle."""

    try:
        if args.iteration_command == "freeze":
            artifact = freeze_prediction(
                model_path=args.model,
                prediction_id=args.prediction_id,
                frozen_at=args.frozen_at,
                target_kind=args.target_kind,
                target_id=args.target_id,
                prediction_kind=args.prediction_kind,
                expected_evidence_ids=args.expected_evidence or [],
                expected_event_ids=args.expected_event or [],
                expected_event_order=args.expected_event_order or [],
                weakens_when=args.weakens_when,
            ).to_dict()
        elif args.iteration_command == "compare":
            artifact = compare_prediction_observation(
                load_prediction(args.prediction),
                load_observation(args.observation),
            )
        elif args.iteration_command == "decide":
            artifact = decide_candidate_revision(
                comparison=load_comparison(args.comparison),
                candidate_model_path=args.candidate,
                observation=load_observation(args.observation),
                required_holdout_evidence_ids=args.required_holdout_evidence or [],
                addressed_mismatch_ids=args.address_mismatch or [],
                force_rollback=args.rollback,
            )
        else:
            raise TaskIterationError("unknown iteration command")
        write_artifact(args.output, artifact)
    except (
        OSError,
        SchemaError,
        ValueError,
        InferenceError,
        TaskIterationError,
    ) as exc:
        _print_json({"ok": False, "error": str(exc)}, pretty=args.pretty)
        return 2
    _print_json({"ok": True, "output": args.output, "artifact": artifact}, pretty=args.pretty)
    return 0


def cmd_library(args: argparse.Namespace) -> int:
    try:
        if args.library_command == "init":
            payload = case_library.init_library(args.root, name=args.name)
        elif args.library_command == "create-case":
            payload = case_library.create_case(args.root, args.case_id, title=args.title, topic=args.topic or "", summary=args.summary or "", tags=args.tag or [])
        elif args.library_command == "add-direction":
            payload = case_library.create_direction(args.root, args.case_id, args.direction_id, title=args.title, question=args.question or "", priority=args.priority, search_terms=args.search_term or [])
        elif args.library_command == "add-source":
            payload = case_library.add_source(
                args.root,
                args.case_id,
                args.direction_id,
                source_id=args.source_id,
                title=args.title,
                source_type=args.source_type,
                url=args.url,
                status=args.status,
                reliability=args.reliability,
                lineage_id=args.lineage_id,
                independence_group=args.independence_group,
                derived_from_source_ids=args.derived_from_source or [],
                source_date=args.source_date,
                notes=args.notes or "",
            )
        elif args.library_command == "add-evidence":
            payload = case_library.add_evidence(
                args.root,
                args.case_id,
                args.direction_id,
                evidence_id=args.evidence_id,
                source_id=args.source_id,
                raw_text=args.text,
                evidence_type=args.evidence_type,
                summary=args.summary,
                confidence=args.confidence,
                specificity=args.specificity,
                status=args.status,
                usable=not args.not_usable,
                limits=args.limit or [],
                warnings=args.warning or [],
            )
        elif args.library_command == "list":
            if args.case_id and args.direction_id:
                paths = case_library.require_library(args.root)
                payload = {
                    section: case_library.read_yaml(
                        paths.ledger(args.case_id, args.direction_id, filename),
                        [],
                    )
                    for section, (filename, _) in case_library.MODEL_LEDGER_SPECS.items()
                }
            elif args.case_id:
                payload = {"directions": case_library.list_directions(args.root, args.case_id)}
            else:
                payload = {"cases": case_library.list_cases(args.root)}
        elif args.library_command == "search":
            payload = {"matches": case_library.search_library(args.root, args.query, case_id=args.case_id)}
        elif args.library_command == "build-model":
            payload = case_library.write_model(
                args.root,
                args.case_id,
                args.output,
                directions=args.direction or [],
                purpose_contract=args.purpose_contract,
            )
            payload = {"ok": True, "output": args.output, "case_id": args.case_id, "directions": payload["metadata"]["directions"]}
        elif args.library_command == "validate":
            payload = case_library.validate_library(args.root)
        elif args.library_command == "write-back-gaps":
            payload = case_library.write_back_gaps(args.root, args.case_id, args.result)
        else:
            raise case_library.LibraryError("unknown library command")
    except (OSError, ValueError, case_library.LibraryError, SchemaError) as exc:
        _print_json({"ok": False, "error": str(exc)}, pretty=args.pretty)
        return 2
    _print_json(payload, pretty=args.pretty)
    return 0


def cmd_library_depth(args: argparse.Namespace) -> int:
    from .library_depth import main as library_depth_main

    argv = [str(args.package)]
    if args.output:
        argv.extend(["--output", str(args.output)])
    if args.pretty:
        argv.append("--pretty")
    return library_depth_main(argv)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="researchguard trace", description="TraceGuard evidence-to-trace evaluator")
    sub = parser.add_subparsers(dest="command", required=True)

    for name, handler in [
        ("validate", cmd_validate),
        ("evaluate", cmd_evaluate),
        ("depth", cmd_depth),
        ("diagnose", cmd_diagnose),
        ("gaps", cmd_gaps),
    ]:
        command = sub.add_parser(name)
        command.add_argument("model")
        if name == "depth":
            command.add_argument("--max-perturbations", type=int)
            command.add_argument("--claim-scope", choices=["bounded", "broad"], default="broad")
        command.add_argument("--pretty", action="store_true")
        command.set_defaults(handler=handler)

    report = sub.add_parser("report")
    report.add_argument("model")
    report.add_argument("--format", choices=["markdown", "txt", "json"], default="markdown")
    report.set_defaults(handler=cmd_report)

    export = sub.add_parser("export-logicguard")
    export.add_argument("model")
    export.add_argument("--output")
    export.set_defaults(handler=cmd_export_logicguard)

    create = sub.add_parser("create")
    create.add_argument("--output", required=True)
    create.add_argument("--purpose-contract", required=True)
    create.set_defaults(handler=cmd_create)

    simulate = sub.add_parser("simulate")
    simulate.add_argument(
        "--mode",
        choices=["storyline", "storyline-depth", "projectradar", "weak-signal", "evidence-removal", "contradiction-injection"],
        default="storyline",
    )
    simulate.add_argument("--model", default="")
    simulate.add_argument("--pretty", action="store_true")
    simulate.set_defaults(handler=cmd_simulate)

    compare = sub.add_parser("compare")
    compare.add_argument("before")
    compare.add_argument("after")
    compare.add_argument("--pretty", action="store_true")
    compare.set_defaults(handler=cmd_compare)

    iterate = sub.add_parser("iterate")
    iteration_sub = iterate.add_subparsers(dest="iteration_command", required=True)

    freeze = iteration_sub.add_parser("freeze")
    freeze.add_argument("--model", required=True)
    freeze.add_argument("--prediction-id", required=True)
    freeze.add_argument("--frozen-at", required=True)
    freeze.add_argument(
        "--target-kind",
        choices=["storyline", "hypothesis"],
        required=True,
    )
    freeze.add_argument("--target-id", required=True)
    freeze.add_argument(
        "--prediction-kind",
        choices=["evidence_footprint", "future_event"],
        default="evidence_footprint",
    )
    freeze.add_argument("--expected-evidence", action="append")
    freeze.add_argument("--expected-event", action="append")
    freeze.add_argument("--expected-event-order", action="append")
    freeze.add_argument("--weakens-when", required=True)
    freeze.add_argument("--output", required=True)
    freeze.add_argument("--pretty", action="store_true")
    freeze.set_defaults(handler=cmd_iterate)

    iteration_compare = iteration_sub.add_parser("compare")
    iteration_compare.add_argument("--prediction", required=True)
    iteration_compare.add_argument("--observation", required=True)
    iteration_compare.add_argument("--output", required=True)
    iteration_compare.add_argument("--pretty", action="store_true")
    iteration_compare.set_defaults(handler=cmd_iterate)

    decide = iteration_sub.add_parser("decide")
    decide.add_argument("--comparison", required=True)
    decide.add_argument("--observation", required=True)
    decide.add_argument("--candidate", required=True)
    decide.add_argument("--required-holdout-evidence", action="append")
    decide.add_argument("--address-mismatch", action="append")
    decide.add_argument("--rollback", action="store_true")
    decide.add_argument("--output", required=True)
    decide.add_argument("--pretty", action="store_true")
    decide.set_defaults(handler=cmd_iterate)

    library = sub.add_parser("library")
    library_sub = library.add_subparsers(dest="library_command", required=True)

    lib_init = library_sub.add_parser("init")
    lib_init.add_argument("root")
    lib_init.add_argument("--name", default=case_library.DEFAULT_LIBRARY_NAME)
    lib_init.add_argument("--pretty", action="store_true")
    lib_init.set_defaults(handler=cmd_library)

    create_case = library_sub.add_parser("create-case")
    create_case.add_argument("root")
    create_case.add_argument("case_id")
    create_case.add_argument("--title", required=True)
    create_case.add_argument("--topic")
    create_case.add_argument("--summary")
    create_case.add_argument("--tag", action="append")
    create_case.add_argument("--pretty", action="store_true")
    create_case.set_defaults(handler=cmd_library)

    add_direction = library_sub.add_parser("add-direction")
    add_direction.add_argument("root")
    add_direction.add_argument("case_id")
    add_direction.add_argument("direction_id")
    add_direction.add_argument("--title", required=True)
    add_direction.add_argument("--question")
    add_direction.add_argument("--priority", default="normal")
    add_direction.add_argument("--search-term", action="append")
    add_direction.add_argument("--pretty", action="store_true")
    add_direction.set_defaults(handler=cmd_library)

    add_source = library_sub.add_parser("add-source")
    add_source.add_argument("root")
    add_source.add_argument("case_id")
    add_source.add_argument("direction_id")
    add_source.add_argument("--source-id", required=True)
    add_source.add_argument("--title", required=True)
    add_source.add_argument("--source-type", default="other")
    add_source.add_argument("--url")
    add_source.add_argument("--status", default="stable_keep")
    add_source.add_argument("--reliability", type=float, default=0.5)
    add_source.add_argument("--lineage-id")
    add_source.add_argument("--independence-group")
    add_source.add_argument("--derived-from-source", action="append")
    add_source.add_argument("--source-date")
    add_source.add_argument("--notes")
    add_source.add_argument("--pretty", action="store_true")
    add_source.set_defaults(handler=cmd_library)

    add_evidence = library_sub.add_parser("add-evidence")
    add_evidence.add_argument("root")
    add_evidence.add_argument("case_id")
    add_evidence.add_argument("direction_id")
    add_evidence.add_argument("--evidence-id", required=True)
    add_evidence.add_argument("--source-id", required=True)
    add_evidence.add_argument("--text", required=True)
    add_evidence.add_argument("--evidence-type", default="unknown")
    add_evidence.add_argument("--summary")
    add_evidence.add_argument("--confidence", type=float, default=0.5)
    add_evidence.add_argument("--specificity", type=float, default=0.5)
    add_evidence.add_argument("--status", default="candidate")
    add_evidence.add_argument("--not-usable", action="store_true")
    add_evidence.add_argument("--limit", action="append")
    add_evidence.add_argument("--warning", action="append")
    add_evidence.add_argument("--pretty", action="store_true")
    add_evidence.set_defaults(handler=cmd_library)

    lib_list = library_sub.add_parser("list")
    lib_list.add_argument("root")
    lib_list.add_argument("--case-id")
    lib_list.add_argument("--direction-id")
    lib_list.add_argument("--pretty", action="store_true")
    lib_list.set_defaults(handler=cmd_library)

    lib_search = library_sub.add_parser("search")
    lib_search.add_argument("root")
    lib_search.add_argument("query")
    lib_search.add_argument("--case-id")
    lib_search.add_argument("--pretty", action="store_true")
    lib_search.set_defaults(handler=cmd_library)

    build_model = library_sub.add_parser("build-model")
    build_model.add_argument("root")
    build_model.add_argument("case_id")
    build_model.add_argument("--output", required=True)
    build_model.add_argument("--purpose-contract", required=True)
    build_model.add_argument("--direction", action="append")
    build_model.add_argument("--pretty", action="store_true")
    build_model.set_defaults(handler=cmd_library)

    lib_validate = library_sub.add_parser("validate")
    lib_validate.add_argument("root")
    lib_validate.add_argument("--pretty", action="store_true")
    lib_validate.set_defaults(handler=cmd_library)

    write_back = library_sub.add_parser("write-back-gaps")
    write_back.add_argument("root")
    write_back.add_argument("case_id")
    write_back.add_argument("--result", required=True)
    write_back.add_argument("--pretty", action="store_true")
    write_back.set_defaults(handler=cmd_library)

    library_depth = sub.add_parser(
        "library-depth",
        help="Issue the current internal case-library execution-depth receipt.",
    )
    library_depth.add_argument("package")
    library_depth.add_argument("--output")
    library_depth.add_argument("--pretty", action="store_true")
    library_depth.set_defaults(handler=cmd_library_depth)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))
