"""Command line interface for LogicGuard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import __version__
from .diagnostics import diagnose_model
from .delivery import adapt_delivery
from .evaluator import evaluate_model
from .execution_depth import build_logic_depth_receipt
from .argument_modeling import create_argument_model
from .citation_matrix import (
    audit_claim_source_paragraph_matrix,
    build_claim_source_paragraph_matrix,
    render_matrix_audit,
)
from .gap_ledger import build_gap_ledger
from .guard_model_contract import (
    bind_target_candidate,
    freeze_target_contract,
    verify_target_contract,
)
from .importance import summarize_importance
from .library_viewer import build_library_view_payload, build_source_graph_payload
from .loader import load_model
from .markdown_structure import markdown_to_model_dict
from .report import generate_markdown_report
from .source_library import SourceLibrary
from .source_library_io import export_library_package, import_library_package, inspect_library_package
from .source_intake import IntakeMaterial, IntakeOptions, intake_materials
from .simulator import simulate_model
from .task_iteration import (
    ArgumentPrediction,
    SUPPORTED_PREDICTION_MODES,
    freeze_argument_prediction,
    rollback_argument_revision,
    run_argument_iteration,
)
from .file_model_store import FileModelStore
from .structure_audit import audit_structure
from .structured_artifact import build_artifact_map
from .synthesis import synthesize_artifact_plan
from .validator import validate_model
from .writer import (
    claim_strength_adjustment,
    model_to_outline,
    model_to_section_plan,
    paragraph_blueprint,
    review_report_generator,
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # pragma: no cover - exercised by CLI smoke manually
        if getattr(args, "debug", False):
            raise
        print(f"LogicGuard error: {exc}")
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="researchguard logic", description="Audit structured reasoning with H-WADF models.")
    parser.add_argument("--debug", action="store_true", help="Show traceback on errors.")
    parser.add_argument("--version", action="version", version=f"logicguard {__version__}")
    sub = parser.add_subparsers(required=True)

    validate = sub.add_parser("validate", help="Validate a YAML/JSON LogicGuard model.")
    validate.add_argument("model")
    validate.add_argument("--output")
    validate.set_defaults(func=_cmd_validate)

    evaluate = sub.add_parser("evaluate", help="Evaluate model states and confidence.")
    evaluate.add_argument("model")
    evaluate.add_argument("--output")
    evaluate.set_defaults(func=_cmd_evaluate)

    diagnose = sub.add_parser("diagnose", help="Generate a logic diagnostic report.")
    diagnose.add_argument("model")
    diagnose.add_argument("--output")
    diagnose.add_argument("--json", action="store_true")
    diagnose.set_defaults(func=_cmd_diagnose)

    simulate = sub.add_parser("simulate", help="Run a what-if simulation.")
    simulate.add_argument("model")
    simulate.add_argument("--root")
    simulate.add_argument(
        "--mode",
        default="fragility",
        choices=[
            "fragility",
            "counterexample",
            "combination-counterexample",
            "premise-removal",
            "evidence-weakening",
            "rebuttal-activation",
            "assumption-flip",
            "scope-narrowing",
            "dependency-trace",
            "repair",
        ],
    )
    simulate.add_argument("--node")
    simulate.add_argument("--confidence", type=float)
    simulate.add_argument("--max-size", type=int, default=2, help="Maximum combination size for combination-counterexample mode.")
    simulate.add_argument("--output")
    simulate.set_defaults(func=_cmd_simulate)

    iteration = sub.add_parser(
        "argument-iteration",
        help="Freeze, run, or roll back one task-local argument-model iteration.",
    )
    iteration_sub = iteration.add_subparsers(required=True)
    iteration_freeze = iteration_sub.add_parser(
        "freeze", help="Freeze a claim-status prediction before native simulation."
    )
    iteration_freeze.add_argument("baseline")
    iteration_freeze.add_argument("--expected-state", required=True, choices=["IN", "OUT", "UNDECIDED"])
    iteration_freeze.add_argument("--mode", required=True, choices=sorted(SUPPORTED_PREDICTION_MODES))
    iteration_freeze.add_argument("--root")
    iteration_freeze.add_argument("--node")
    iteration_freeze.add_argument("--confidence", type=float)
    iteration_freeze.add_argument("--max-size", type=int, default=2)
    iteration_freeze.add_argument(
        "--protect-claim",
        action="append",
        default=[],
        help="Claim whose unperturbed native status must remain unchanged; repeat as needed.",
    )
    iteration_freeze.add_argument("--prediction-id")
    iteration_freeze.add_argument("--output", required=True)
    iteration_freeze.set_defaults(func=_cmd_argument_iteration_freeze)

    iteration_run = iteration_sub.add_parser(
        "run", help="Observe a frozen prediction and accept or reject a candidate revision."
    )
    iteration_run.add_argument("baseline")
    iteration_run.add_argument("--prediction", required=True)
    iteration_run.add_argument("--candidate")
    iteration_run.add_argument("--store-root", required=True)
    iteration_run.add_argument("--decision", choices=["accept", "reject"], default="reject")
    iteration_run.add_argument("--actor", default="logicguard-task-iteration")
    iteration_run.add_argument("--idempotency-key")
    iteration_run.add_argument("--output", required=True)
    iteration_run.set_defaults(func=_cmd_argument_iteration_run)

    iteration_rollback = iteration_sub.add_parser(
        "rollback", help="Append a compensating revision from a historical snapshot."
    )
    iteration_rollback.add_argument("--store-root", required=True)
    iteration_rollback.add_argument("--model-id", required=True)
    iteration_rollback.add_argument("--source-revision", required=True)
    iteration_rollback.add_argument("--actor", default="logicguard-task-iteration")
    iteration_rollback.add_argument("--idempotency-key")
    iteration_rollback.add_argument("--output", required=True)
    iteration_rollback.set_defaults(func=_cmd_argument_iteration_rollback)

    gaps = sub.add_parser("gaps", help="Generate a routeable gap ledger from diagnostics and simulation.")
    gaps.add_argument("model")
    gaps.add_argument("--no-simulation", action="store_true")
    gaps.add_argument("--output")
    gaps.set_defaults(func=_cmd_gaps)

    guard_contract = sub.add_parser(
        "guard-contract",
        help="Freeze, bind, or verify the mandatory target-local model purpose contract.",
    )
    guard_contract_sub = guard_contract.add_subparsers(required=True)
    guard_freeze = guard_contract_sub.add_parser(
        "freeze", help="Freeze the AI declaration before candidate construction."
    )
    guard_freeze.add_argument("--target-root", required=True)
    guard_freeze.add_argument("--declaration", required=True)
    guard_freeze.add_argument("--contract", required=True)
    guard_freeze.add_argument("--output")
    guard_freeze.set_defaults(func=_cmd_guard_contract_freeze)
    guard_bind = guard_contract_sub.add_parser(
        "bind", help="Bind the current candidate to the exact frozen contract."
    )
    guard_bind.add_argument("--target-root", required=True)
    guard_bind.add_argument("--contract", required=True)
    guard_bind.add_argument("--output")
    guard_bind.set_defaults(func=_cmd_guard_contract_bind)
    guard_verify = guard_contract_sub.add_parser(
        "verify", help="Exhaust every declared good/bad/candidate native proof."
    )
    guard_verify.add_argument("--target-root", required=True)
    guard_verify.add_argument("--contract", required=True)
    guard_verify.add_argument("--target-skill-id")
    guard_verify.add_argument("--output")
    guard_verify.set_defaults(func=_cmd_guard_contract_verify)

    depth = sub.add_parser(
        "depth", help="Emit a target-contract-bound native execution-depth receipt."
    )
    depth.add_argument("model")
    depth.add_argument("--target-root", required=True)
    depth.add_argument("--guard-contract", required=True)
    depth.add_argument(
        "--budget",
        type=int,
        default=6,
        help="Nominal perturbation budget; every target-owned critical perturbation still executes.",
    )
    depth.add_argument(
        "--claim-scope-node",
        action="append",
        default=None,
        help="Required claim node id; repeat to bind an explicit requested claim scope.",
    )
    depth.add_argument("--output")
    depth.set_defaults(func=_cmd_depth)

    route_depth = sub.add_parser(
        "route-depth",
        help="Issue the current LogicGuard internal-route execution-depth receipt.",
    )
    route_depth.add_argument("package")
    route_depth.add_argument("--output")
    route_depth.add_argument("--pretty", action="store_true")
    route_depth.set_defaults(func=_cmd_route_depth)

    report = sub.add_parser("report", help="Generate a full Markdown report.")
    report.add_argument("model")
    report.add_argument("--output")
    report.set_defaults(func=_cmd_report)

    outline = sub.add_parser("outline", help="Generate a model-grounded writing outline.")
    outline.add_argument("model")
    outline.add_argument("--output")
    outline.add_argument("--section-plan", action="store_true")
    outline.add_argument("--paragraph")
    outline.add_argument("--with-citations", action="store_true", help="Include claim-source-paragraph handoff details for paragraph output.")
    outline.add_argument("--paper-structure", action="store_true")
    outline.set_defaults(func=_cmd_outline)

    citation = sub.add_parser("citation", help="Build or audit claim-source-paragraph matrices.")
    citation_sub = citation.add_subparsers(required=True)
    citation_matrix = citation_sub.add_parser("matrix", help="Render a claim-source-paragraph matrix.")
    citation_matrix.add_argument("model")
    citation_matrix.add_argument("--json", action="store_true")
    citation_matrix.add_argument("--output")
    citation_matrix.set_defaults(func=_cmd_citation_matrix)
    citation_audit = citation_sub.add_parser("audit", help="Audit claim-source-paragraph coverage.")
    citation_audit.add_argument("model")
    citation_audit.add_argument("--json", action="store_true")
    citation_audit.add_argument("--output")
    citation_audit.set_defaults(func=_cmd_citation_audit)

    rewrite = sub.add_parser("rewrite-suggestions", help="Generate claim-strength rewrite suggestions.")
    rewrite.add_argument("model")
    rewrite.add_argument("--output")
    rewrite.add_argument("--review-report", action="store_true")
    rewrite.set_defaults(func=_cmd_rewrite)

    importance = sub.add_parser("importance", help="Summarize cross-cutting model importance.")
    importance.add_argument("model")
    importance.add_argument("--json", action="store_true")
    importance.add_argument("--limit", type=int, default=12)
    importance.add_argument("--output")
    importance.set_defaults(func=_cmd_importance)

    structure = sub.add_parser("structure", help="Inspect or audit a structured artifact model.")
    structure_sub = structure.add_subparsers(required=True)
    structure_map = structure_sub.add_parser("map", help="Build an ordered artifact map from model hierarchy.")
    structure_map.add_argument("model")
    structure_map.add_argument("--output")
    structure_map.set_defaults(func=_cmd_structure_map)
    structure_markdown = structure_sub.add_parser("from-markdown", help="Convert Markdown-like headings and labeled fields into a structured model.")
    structure_markdown.add_argument("input")
    structure_markdown.add_argument("--id", default="markdown_artifact")
    structure_markdown.add_argument("--title", default="")
    structure_markdown.add_argument("--artifact-kind", default="paper")
    structure_markdown.add_argument("--output")
    structure_markdown.set_defaults(func=_cmd_structure_from_markdown)
    structure_audit = structure_sub.add_parser("audit", help="Run structure-flow diagnostics.")
    structure_audit.add_argument("model")
    structure_audit.add_argument("--json", action="store_true")
    structure_audit.add_argument("--output")
    structure_audit.set_defaults(func=_cmd_structure_audit)

    synthesize = sub.add_parser("synthesize", help="Create an importance-aware target artifact story plan.")
    synthesize.add_argument("model")
    synthesize.add_argument("--goal", required=True)
    synthesize.add_argument("--profile", default="presentation", choices=["presentation", "paper", "report"])
    synthesize.add_argument("--max-items", type=int, default=8)
    synthesize.add_argument("--library-root", default="", help="Optional source library root for branch candidates.")
    synthesize.add_argument("--source-id", default="", help="Optional source id to load branch candidates from.")
    synthesize.add_argument("--project", default="", help="Optional project id to filter source branch candidates.")
    synthesize.add_argument("--branch", action="append", default=[], help="Specific source branch id to include. Can be repeated.")
    synthesize.add_argument("--delivery", action="store_true", help="Also produce delivery-profile guidance.")
    synthesize.add_argument("--json", action="store_true")
    synthesize.add_argument("--output")
    synthesize.set_defaults(func=_cmd_synthesize)

    argument = sub.add_parser("argument", help="Create or maintain the user's own argument model.")
    argument_sub = argument.add_subparsers(required=True)
    argument_create = argument_sub.add_parser("create", help="Create a starter argument model.")
    argument_create.add_argument("output")
    argument_create.add_argument("--id", default="argument_model")
    argument_create.add_argument("--title", default="Argument model")
    argument_create.add_argument("--claim", required=True, help="Root claim text.")
    argument_create.add_argument("--section", action="append", default=[], help="Section-level claim. Can be repeated.")
    argument_create.set_defaults(func=_cmd_argument_create)

    intake = sub.add_parser("intake", help="Preserve materials in the source library and build shallow source models.")
    _add_intake_args(intake)
    intake.set_defaults(func=_cmd_intake)

    library = sub.add_parser("library", help="Maintain a reusable source logic library.")
    library_sub = library.add_subparsers(required=True)

    library_init = library_sub.add_parser("init", help="Initialize a source logic library.")
    library_init.add_argument("root")
    library_init.set_defaults(func=_cmd_library_init)

    library_import = library_sub.add_parser("import", help="Import a source file into the global library.")
    library_import.add_argument("root")
    library_import.add_argument("source")
    library_import.add_argument("--title", default="")
    library_import.add_argument("--author", action="append", default=[])
    library_import.add_argument("--year", default="")
    library_import.add_argument("--source-date", default="")
    library_import.add_argument("--coverage-period", default="")
    library_import.add_argument("--doi", default="")
    library_import.add_argument("--url", default="")
    library_import.set_defaults(func=_cmd_library_import)

    library_intake = library_sub.add_parser("intake", help="Preserve materials and build shallow source models.")
    _add_intake_args(library_intake)
    library_intake.set_defaults(func=_cmd_intake)

    library_model = library_sub.add_parser("model-source", help="Create a shallow source logic model.")
    _add_source_model_args(library_model)
    library_model.set_defaults(func=_cmd_library_model_source)

    library_deepen = library_sub.add_parser("deepen-source", help="Deepen one topic-relevant source path.")
    _add_source_model_args(library_deepen)
    library_deepen.add_argument("--project", required=True)
    library_deepen.add_argument("--topic-focus", required=True)
    library_deepen.add_argument("--anchor-node", default="")
    library_deepen.add_argument("--anchor-block", default="")
    library_deepen.add_argument("--branch-id", default="")
    library_deepen.add_argument("--branch-role", default="")
    library_deepen.add_argument("--promote", action="store_true", help="Mark the branch as promoted source knowledge.")
    library_deepen.add_argument("--note", default="")
    library_deepen.set_defaults(func=_cmd_library_deepen_source)

    library_project = library_sub.add_parser("create-project", help="Create a project branch.")
    library_project.add_argument("root")
    library_project.add_argument("project")
    library_project.add_argument("--topic", required=True)
    library_project.set_defaults(func=_cmd_library_create_project)

    library_select = library_sub.add_parser("select-source", help="Select a global source for a project.")
    library_select.add_argument("root")
    library_select.add_argument("project")
    library_select.add_argument("source_id")
    library_select.set_defaults(func=_cmd_library_select_source)

    library_search = library_sub.add_parser("search", help="Search source logic nodes.")
    library_search.add_argument("root")
    library_search.add_argument("query")
    library_search.add_argument("--type", default="")
    library_search.add_argument("--project", default="")
    library_search.add_argument("--branch", default="")
    library_search.add_argument("--anchor-node", default="")
    library_search.add_argument("--anchor-block", default="")
    library_search.add_argument("--limit", type=int, default=10)
    library_search.set_defaults(func=_cmd_library_search)

    library_branches = library_sub.add_parser("branches", help="List anchored source deepening branches.")
    library_branches.add_argument("root")
    library_branches.add_argument("source_id", nargs="?")
    library_branches.add_argument("--project", default="")
    library_branches.add_argument("--anchor-node", default="")
    library_branches.add_argument("--anchor-block", default="")
    library_branches.add_argument("--topic-focus", default="")
    library_branches.add_argument("--status", default="")
    library_branches.set_defaults(func=_cmd_library_branches)

    library_audit_branches = library_sub.add_parser("audit-branches", help="Audit source deepening branch structure.")
    library_audit_branches.add_argument("root")
    library_audit_branches.add_argument("source_id", nargs="?")
    library_audit_branches.add_argument("--json", action="store_true")
    library_audit_branches.set_defaults(func=_cmd_library_audit_branches)

    library_link = library_sub.add_parser("link", help="Link a project argument node to a source node.")
    library_link.add_argument("root")
    library_link.add_argument("project")
    library_link.add_argument("--project-node", required=True)
    library_link.add_argument("--source-id", required=True)
    library_link.add_argument("--source-node", required=True)
    library_link.add_argument("--relation", required=True)
    library_link.add_argument("--note", default="")
    library_link.add_argument("--importance", type=float)
    library_link.add_argument("--salience", default="")
    library_link.add_argument("--importance-reason", default="")
    library_link.add_argument("--source-branch", default="")
    library_link.set_defaults(func=_cmd_library_link)

    library_links = library_sub.add_parser("links", help="List source links for a project.")
    library_links.add_argument("root")
    library_links.add_argument("project")
    library_links.add_argument("--project-node", default="")
    library_links.set_defaults(func=_cmd_library_links)

    library_export = library_sub.add_parser("export-package", help="Export a portable source-library package.")
    library_export.add_argument("root")
    library_export.add_argument("output")
    export_scope = library_export.add_mutually_exclusive_group(required=True)
    export_scope.add_argument("--project", default="")
    export_scope.add_argument("--all", action="store_true", dest="all_sources")
    export_scope.add_argument("--uncategorized", action="store_true")
    export_scope.add_argument("--source", nargs="+", default=[])
    library_export.set_defaults(func=_cmd_library_export_package)

    library_import_package = library_sub.add_parser("import-package", help="Import a portable source-library package by safe merge.")
    library_import_package.add_argument("root")
    library_import_package.add_argument("package")
    library_import_package.add_argument("--dry-run", action="store_true")
    library_import_package.add_argument("--output")
    library_import_package.set_defaults(func=_cmd_library_import_package)

    library_inspect_package = library_sub.add_parser("inspect-package", help="Inspect a source-library package manifest.")
    library_inspect_package.add_argument("package")
    library_inspect_package.add_argument("--output")
    library_inspect_package.set_defaults(func=_cmd_library_inspect_package)

    library_view = library_sub.add_parser("view-snapshot", help="Build the read-only project library viewer payload.")
    library_view.add_argument("root")
    library_view.add_argument("--output")
    library_view.set_defaults(func=_cmd_library_view_snapshot)

    library_view_graph = library_sub.add_parser("view-graph", help="Build the read-only viewer graph payload for one source.")
    library_view_graph.add_argument("root")
    library_view_graph.add_argument("source_id")
    library_view_graph.add_argument("--language", default="en", choices=["en", "zh-CN"])
    library_view_graph.add_argument("--output")
    library_view_graph.set_defaults(func=_cmd_library_view_graph)

    library_viewer = library_sub.add_parser(
        "viewer",
        help="Open or headlessly check the read-only project library viewer.",
    )
    library_viewer.add_argument("--library-root", default="auto")
    library_viewer.add_argument("--route", default="")
    library_viewer.add_argument("--source-id", default="")
    library_viewer.add_argument("--language", default="", choices=["", "en", "zh-CN"])
    library_viewer.add_argument("--check", action="store_true")
    library_viewer.set_defaults(func=_cmd_library_viewer)

    return parser


def _cmd_validate(args: argparse.Namespace) -> int:
    model = load_model(args.model, validate=False)
    validation = validate_model(model)
    payload = validation.to_dict()
    if args.output:
        _write(args.output, payload)
    else:
        print(validation.format_text())
    return 0 if validation.ok else 2


def _cmd_evaluate(args: argparse.Namespace) -> int:
    model = load_model(args.model)
    result = evaluate_model(model)
    payload = result.to_dict()
    if args.output:
        _write(args.output, payload)
    else:
        print(json.dumps(payload, indent=2))
    return 0


def _cmd_route_depth(args: argparse.Namespace) -> int:
    from .route_execution_depth import main as route_depth_main

    argv = [str(args.package)]
    if args.output:
        argv.extend(["--output", str(args.output)])
    if args.pretty:
        argv.append("--pretty")
    return route_depth_main(argv)


def _cmd_library_viewer(args: argparse.Namespace) -> int:
    from researchguard.logic_viewer.launcher import main as viewer_main

    argv = ["--library-root", str(args.library_root)]
    if args.route:
        argv.extend(["--route", str(args.route)])
    if args.source_id:
        argv.extend(["--source-id", str(args.source_id)])
    if args.language:
        argv.extend(["--language", str(args.language)])
    if args.check:
        argv.append("--check")
    viewer_main(argv)
    return 0


def _cmd_diagnose(args: argparse.Namespace) -> int:
    model = load_model(args.model)
    result = evaluate_model(model)
    report = diagnose_model(model, result)
    payload: Any = report.to_dict() if args.json or (args.output and args.output.endswith(".json")) else report.to_markdown()
    if args.output:
        _write(args.output, payload)
    else:
        print(json.dumps(payload, indent=2) if isinstance(payload, dict) else payload)
    return 0


def _cmd_simulate(args: argparse.Namespace) -> int:
    model = load_model(args.model)
    result = simulate_model(
        model,
        root_claim=args.root,
        mode=args.mode,
        node_id=args.node,
        confidence=args.confidence,
        max_size=args.max_size,
    )
    payload = result.to_dict()
    if args.output:
        _write(args.output, payload)
    else:
        print(json.dumps(payload, indent=2))
    return 0


def _cmd_argument_iteration_freeze(args: argparse.Namespace) -> int:
    model = load_model(args.baseline)
    prediction = freeze_argument_prediction(
        model,
        expected_state=args.expected_state,
        mode=args.mode,
        root_claim=args.root,
        node_id=args.node,
        confidence=args.confidence,
        max_size=args.max_size,
        protected_claim_ids=args.protect_claim,
        prediction_id=args.prediction_id,
    )
    _write(args.output, prediction.to_dict())
    return 0


def _cmd_argument_iteration_run(args: argparse.Namespace) -> int:
    baseline = load_model(args.baseline)
    candidate = load_model(args.candidate) if args.candidate else None
    prediction = ArgumentPrediction.from_dict(_load_json_object(args.prediction))
    receipt = run_argument_iteration(
        FileModelStore(args.store_root),
        baseline,
        prediction,
        candidate=candidate,
        decision=args.decision,
        actor=args.actor,
        idempotency_key=args.idempotency_key,
    )
    _write(args.output, receipt.to_dict())
    return 0 if receipt.effective_disposition not in {"conflict"} else 3


def _cmd_argument_iteration_rollback(args: argparse.Namespace) -> int:
    receipt = rollback_argument_revision(
        FileModelStore(args.store_root),
        model_id=args.model_id,
        source_revision=args.source_revision,
        actor=args.actor,
        idempotency_key=args.idempotency_key,
    )
    _write(args.output, receipt.to_dict())
    return 0


def _cmd_gaps(args: argparse.Namespace) -> int:
    model = load_model(args.model)
    result = evaluate_model(model)
    diagnostics = diagnose_model(model, result)
    ledger = build_gap_ledger(model, result=result, diagnostics=diagnostics, include_simulation=not args.no_simulation)
    payload = ledger.to_dict()
    if args.output:
        _write(args.output, payload)
    else:
        print(json.dumps(payload, indent=2))
    return 0


def _cmd_depth(args: argparse.Namespace) -> int:
    model = load_model(args.model)
    receipt = build_logic_depth_receipt(
        model,
        target_root=args.target_root,
        guard_contract=args.guard_contract,
        budget=args.budget,
        requested_claim_scope_ids=args.claim_scope_node,
    )
    payload = receipt.to_dict()
    if args.output:
        _write(args.output, payload)
    else:
        print(json.dumps(payload, indent=2))
    return 0 if receipt.status == "pass" else 3


def _emit_guard_contract_result(args: argparse.Namespace, payload: dict[str, Any]) -> int:
    if args.output:
        _write(args.output, payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _cmd_guard_contract_freeze(args: argparse.Namespace) -> int:
    payload = freeze_target_contract(
        target_root=args.target_root,
        declaration_path=args.declaration,
        output_path=args.contract,
    )
    return _emit_guard_contract_result(args, payload)


def _cmd_guard_contract_bind(args: argparse.Namespace) -> int:
    payload = bind_target_candidate(
        target_root=args.target_root,
        contract_path=args.contract,
    )
    return _emit_guard_contract_result(args, payload)


def _cmd_guard_contract_verify(args: argparse.Namespace) -> int:
    payload = verify_target_contract(
        target_root=args.target_root,
        contract_path=args.contract,
        expected_target_skill_id=args.target_skill_id,
    )
    return _emit_guard_contract_result(args, payload)


def _cmd_report(args: argparse.Namespace) -> int:
    model = load_model(args.model)
    payload = generate_markdown_report(model)
    if args.output:
        _write(args.output, payload)
    else:
        print(payload)
    return 0


def _cmd_outline(args: argparse.Namespace) -> int:
    model = load_model(args.model)
    if args.section_plan:
        payload = model_to_section_plan(model)
    elif args.paragraph:
        citation_matrix = build_claim_source_paragraph_matrix(model) if args.with_citations else None
        payload = paragraph_blueprint(model, args.paragraph, citation_matrix=citation_matrix)
    elif args.paper_structure:
        from .writer import paper_structure_generator

        payload = paper_structure_generator(model)
    else:
        payload = model_to_outline(model)
    if args.output:
        _write(args.output, payload)
    else:
        print(payload)
    return 0


def _cmd_citation_matrix(args: argparse.Namespace) -> int:
    model = load_model(args.model)
    matrix = build_claim_source_paragraph_matrix(model)
    payload: Any = matrix.to_dict() if args.json or (args.output and args.output.endswith(".json")) else matrix.to_markdown()
    if args.output:
        _write(args.output, payload)
    else:
        print(json.dumps(payload, indent=2) if isinstance(payload, dict) else payload)
    return 0


def _cmd_citation_audit(args: argparse.Namespace) -> int:
    model = load_model(args.model)
    matrix = build_claim_source_paragraph_matrix(model)
    findings = audit_claim_source_paragraph_matrix(matrix)
    payload: Any = (
        {"model_id": matrix.model_id, "findings": [finding.to_dict() for finding in findings]}
        if args.json or (args.output and args.output.endswith(".json"))
        else render_matrix_audit(findings)
    )
    if args.output:
        _write(args.output, payload)
    else:
        print(json.dumps(payload, indent=2) if isinstance(payload, dict) else payload)
    return 0


def _cmd_rewrite(args: argparse.Namespace) -> int:
    model = load_model(args.model)
    result = evaluate_model(model)
    diagnostics = diagnose_model(model, result)
    payload = review_report_generator(model, diagnostics) if args.review_report else claim_strength_adjustment(model, diagnostics)
    if args.output:
        _write(args.output, payload)
    else:
        print(payload)
    return 0


def _cmd_importance(args: argparse.Namespace) -> int:
    model = load_model(args.model)
    summary = summarize_importance(model, limit=args.limit)
    payload: Any = summary.to_dict() if args.json or (args.output and args.output.endswith(".json")) else summary.to_markdown()
    if args.output:
        _write(args.output, payload)
    else:
        print(json.dumps(payload, indent=2) if isinstance(payload, dict) else payload)
    return 0


def _cmd_structure_map(args: argparse.Namespace) -> int:
    model = load_model(args.model)
    payload = build_artifact_map(model).to_dict()
    if args.output:
        _write(args.output, payload)
    else:
        print(json.dumps(payload, indent=2))
    return 0


def _cmd_structure_from_markdown(args: argparse.Namespace) -> int:
    source = Path(args.input)
    text = source.read_text(encoding="utf-8")
    payload = markdown_to_model_dict(
        text,
        model_id=args.id,
        title=args.title,
        artifact_kind=args.artifact_kind,
    )
    if args.output:
        _write(args.output, payload)
    else:
        print(json.dumps(payload, indent=2))
    return 0


def _cmd_structure_audit(args: argparse.Namespace) -> int:
    model = load_model(args.model)
    report = audit_structure(model)
    payload: Any = report.to_dict() if args.json or (args.output and args.output.endswith(".json")) else report.to_markdown()
    if args.output:
        _write(args.output, payload)
    else:
        print(json.dumps(payload, indent=2) if isinstance(payload, dict) else payload)
    return 0


def _cmd_synthesize(args: argparse.Namespace) -> int:
    model = load_model(args.model)
    source_branches = ()
    if args.library_root:
        library = SourceLibrary(args.library_root)
        branches = library.list_deepening_branches(args.source_id, project_id=args.project)
        if args.branch:
            wanted = set(args.branch)
            branches = [branch for branch in branches if branch.branch_id in wanted]
        source_branches = tuple(branches)
    plan = synthesize_artifact_plan(
        model,
        target_goal=args.goal,
        profile=args.profile,
        max_items=args.max_items,
        source_branches=source_branches,
    )
    if args.delivery:
        guidance = adapt_delivery(plan, profile=args.profile)
        payload = {
            "plan": plan.to_dict(),
            "delivery": guidance.to_dict(),
        } if args.json or (args.output and args.output.endswith(".json")) else plan.to_markdown() + "\n" + guidance.to_markdown()
    else:
        payload = plan.to_dict() if args.json or (args.output and args.output.endswith(".json")) else plan.to_markdown()
    if args.output:
        _write(args.output, payload)
    else:
        print(json.dumps(payload, indent=2) if isinstance(payload, dict) else payload)
    return 0


def _cmd_argument_create(args: argparse.Namespace) -> int:
    path = create_argument_model(
        args.output,
        model_id=args.id,
        title=args.title,
        root_claim=args.claim,
        section_claims=args.section,
    )
    print(json.dumps({"created": str(path)}, indent=2))
    return 0


def _cmd_intake(args: argparse.Namespace) -> int:
    result = intake_materials(
        _intake_materials_from_args(args),
        options=IntakeOptions(
            library_root=args.root,
            project_id=args.project,
            project_topic=args.project_topic,
        ),
    )
    payload: Any = result.to_dict() if args.json or (args.output and args.output.endswith(".json")) else result.format_text()
    if args.output:
        _write(args.output, payload)
    else:
        print(json.dumps(payload, indent=2) if isinstance(payload, dict) else payload)
    return 0


def _cmd_library_init(args: argparse.Namespace) -> int:
    library = SourceLibrary(args.root)
    library.init()
    print(json.dumps({"root": str(library.root), "initialized": True}, indent=2))
    return 0


def _cmd_library_import(args: argparse.Namespace) -> int:
    result = SourceLibrary(args.root).import_source(
        args.source,
        title=args.title,
        authors=args.author,
        year=args.year,
        source_date=args.source_date,
        coverage_period=args.coverage_period,
        doi=args.doi,
        url=args.url,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0


def _cmd_library_model_source(args: argparse.Namespace) -> int:
    path = SourceLibrary(args.root).create_source_model(
        args.source_id,
        title=args.title,
        claim=args.claim,
        evidence=args.evidence,
        warrant=args.warrant,
        method=args.method,
        result=args.result,
        scope=args.scope,
        limitation=args.limitation,
        rebuttal=args.rebuttal,
        locator=args.locator,
        importance=args.importance,
        salience=args.salience,
        importance_reason=args.importance_reason,
        i18n=_load_i18n_payload(args.i18n_json),
    )
    print(json.dumps({"model": str(path)}, indent=2))
    return 0


def _cmd_library_deepen_source(args: argparse.Namespace) -> int:
    record = SourceLibrary(args.root).deepen_source(
        args.source_id,
        project_id=args.project,
        topic_focus=args.topic_focus,
        locator=args.locator,
        anchor_node_id=args.anchor_node,
        anchor_block_id=args.anchor_block,
        branch_id=args.branch_id,
        branch_role=args.branch_role,
        promote=args.promote,
        claim=args.claim,
        evidence=args.evidence,
        warrant=args.warrant,
        method=args.method,
        result=args.result,
        scope=args.scope,
        limitation=args.limitation,
        rebuttal=args.rebuttal,
        note=args.note,
        importance=args.importance,
        salience=args.salience,
        importance_reason=args.importance_reason,
        i18n=_load_i18n_payload(args.i18n_json),
    )
    print(json.dumps(record.to_dict(), indent=2))
    return 0


def _cmd_library_create_project(args: argparse.Namespace) -> int:
    project = SourceLibrary(args.root).create_project(args.project, topic=args.topic)
    print(json.dumps(project.to_dict(), indent=2))
    return 0


def _cmd_library_select_source(args: argparse.Namespace) -> int:
    project = SourceLibrary(args.root).select_source(args.project, args.source_id)
    print(json.dumps(project.to_dict(), indent=2))
    return 0


def _cmd_library_search(args: argparse.Namespace) -> int:
    hits = SourceLibrary(args.root).search(
        args.query,
        node_type=args.type,
        project_id=args.project,
        branch_id=args.branch,
        anchor_node_id=args.anchor_node,
        anchor_block_id=args.anchor_block,
        limit=args.limit,
    )
    print(json.dumps({"hits": [hit.to_dict() for hit in hits]}, indent=2))
    return 0


def _cmd_library_branches(args: argparse.Namespace) -> int:
    branches = SourceLibrary(args.root).list_deepening_branches(
        args.source_id or "",
        project_id=args.project,
        anchor_node_id=args.anchor_node,
        anchor_block_id=args.anchor_block,
        topic_focus=args.topic_focus,
        status=args.status,
    )
    print(json.dumps({"branches": [branch.to_dict() for branch in branches]}, indent=2))
    return 0


def _cmd_library_audit_branches(args: argparse.Namespace) -> int:
    report = SourceLibrary(args.root).audit_deepening_branches(args.source_id or "")
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.to_markdown())
    return 0 if report.ok else 2


def _cmd_library_link(args: argparse.Namespace) -> int:
    link = SourceLibrary(args.root).link_node(
        args.project,
        project_node_id=args.project_node,
        source_id=args.source_id,
        source_node_id=args.source_node,
        relation=args.relation,
        note=args.note,
        importance=args.importance,
        salience=args.salience,
        importance_reason=args.importance_reason,
        source_branch_id=args.source_branch,
    )
    print(json.dumps(link.to_dict(), indent=2))
    return 0


def _cmd_library_links(args: argparse.Namespace) -> int:
    links = SourceLibrary(args.root).list_links(args.project, project_node_id=args.project_node)
    print(json.dumps({"links": [link.to_dict() for link in links]}, indent=2))
    return 0


def _cmd_library_export_package(args: argparse.Namespace) -> int:
    if args.project:
        mode = "project"
    elif args.all_sources:
        mode = "all"
    elif args.uncategorized:
        mode = "uncategorized"
    else:
        mode = "sources"
    result = export_library_package(
        args.root,
        args.output,
        mode=mode,
        project_id=args.project,
        source_ids=args.source,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0


def _cmd_library_import_package(args: argparse.Namespace) -> int:
    result = import_library_package(args.root, args.package, dry_run=args.dry_run)
    payload = result.to_dict()
    if args.output:
        _write(args.output, payload)
    else:
        print(json.dumps(payload, indent=2))
    return 0


def _cmd_library_inspect_package(args: argparse.Namespace) -> int:
    payload = inspect_library_package(args.package)
    if args.output:
        _write(args.output, payload)
    else:
        print(json.dumps(payload, indent=2))
    return 0


def _cmd_library_view_snapshot(args: argparse.Namespace) -> int:
    payload = build_library_view_payload(args.root)
    if args.output:
        _write(args.output, payload)
    else:
        print(json.dumps(payload, indent=2))
    return 0


def _cmd_library_view_graph(args: argparse.Namespace) -> int:
    payload = build_source_graph_payload(args.root, args.source_id, language=args.language)
    if args.output:
        _write(args.output, payload)
    else:
        print(json.dumps(payload, indent=2))
    return 0


def _add_source_model_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("root")
    parser.add_argument("source_id")
    parser.add_argument("--title", default="")
    parser.add_argument("--claim", default="")
    parser.add_argument("--evidence", default="")
    parser.add_argument("--warrant", default="")
    parser.add_argument("--method", default="")
    parser.add_argument("--result", default="")
    parser.add_argument("--scope", default="")
    parser.add_argument("--limitation", default="")
    parser.add_argument("--rebuttal", default="")
    parser.add_argument("--locator", default="")
    parser.add_argument("--importance", type=float)
    parser.add_argument("--salience", default="")
    parser.add_argument("--importance-reason", default="")
    parser.add_argument("--i18n-json", default="", help="JSON string or JSON file with language-first localized model text.")


def _load_i18n_payload(value: str) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        path = Path(text)
        if path.exists() and path.is_file():
            text = path.read_text(encoding="utf-8")
    except OSError:
        pass
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise SystemExit("--i18n-json must decode to a JSON object")
    return payload


def _load_json_object(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must contain an object: {path}")
    return payload


def _add_intake_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("root", nargs="?", default=".logicguard-library")
    parser.add_argument("--file", action="append", default=[], help="File to preserve as source material. Can be repeated.")
    parser.add_argument("--text", action="append", default=[], help="Long-form text to snapshot and preserve. Can be repeated.")
    parser.add_argument("--text-file", action="append", default=[], help="Read a text file and preserve it as a snapshot. Can be repeated.")
    parser.add_argument("--url", action="append", default=[], help="URL to preserve as a local source snapshot. Can be repeated.")
    parser.add_argument("--title", default="")
    parser.add_argument("--author", action="append", default=[])
    parser.add_argument("--year", default="")
    parser.add_argument("--source-date", default="")
    parser.add_argument("--coverage-period", default="")
    parser.add_argument("--doi", default="")
    parser.add_argument("--project", default="")
    parser.add_argument("--project-topic", default="")
    parser.add_argument("--claim", default="")
    parser.add_argument("--evidence", default="")
    parser.add_argument("--warrant", default="")
    parser.add_argument("--method", default="")
    parser.add_argument("--result", default="")
    parser.add_argument("--scope", default="")
    parser.add_argument("--limitation", default="")
    parser.add_argument("--rebuttal", default="")
    parser.add_argument("--locator", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output")


def _intake_materials_from_args(args: argparse.Namespace) -> list[IntakeMaterial]:
    hints = {
        key: value
        for key in ("claim", "evidence", "warrant", "method", "result", "scope", "limitation", "rebuttal", "locator")
        if (value := getattr(args, key, ""))
    }
    common = {
        "title": args.title,
        "authors": tuple(args.author),
        "year": args.year,
        "source_date": args.source_date,
        "coverage_period": args.coverage_period,
        "doi": args.doi,
        "modeling_hints": hints,
    }
    materials: list[IntakeMaterial] = []
    for path in args.file:
        materials.append(IntakeMaterial.file(path, **common))
    for path_text in args.text_file:
        path = Path(path_text)
        text = path.read_text(encoding="utf-8")
        materials.append(IntakeMaterial.text(text, **{**common, "title": args.title or path.stem}))
    for text in args.text:
        materials.append(IntakeMaterial.text(text, **common))
    for url in args.url:
        materials.append(IntakeMaterial.url_snapshot(url, **common))
    return materials


def _write(path: str, payload: Any) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        output.write_text(payload, encoding="utf-8")
    else:
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
