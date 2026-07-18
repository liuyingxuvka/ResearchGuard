"""
Purpose: Provide the local SourceGuard command line interface.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: SourceGuard
Math boundary: Expected utility ranks search value, not factual truth or calibrated probability.
CLI: researchguard source --help
Boundary: Source candidates and evidence anchors require downstream TraceGuard/LogicGuard review before final claims.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

import yaml

from researchguard import __version__

from .depth import apply_observation_and_replan
from .guard_contract import load_target_contract, prove_target_model_contract
from .handoff import export_logicguard_source_candidates, export_traceguard_seed
from .loader import load_model, validate_model, write_yaml
from .planner import frontier_summary, plan_next_actions
from .report import render_json, render_markdown, render_text
from .schema import (
    BeliefState,
    Observation,
    sourceguard_model_contract_fingerprint,
    to_plain,
)
from .scoring import score_actions
from .update import apply_observation
from .task_iteration import (
    GAP_REDUCTION_LEVELS,
    SearchOutcomePrediction,
    freeze_search_outcome_prediction,
    rollback_search_iteration,
    run_search_iteration,
)


def starter_model_dict(model_contract_path: str | Path) -> dict[str, Any]:
    payload = {
        "metadata": {
            "purpose": "Starter SourceGuard belief state",
            "repository": "https://github.com/liuyingxuvka/ResearchGuard",
            "skill": "SourceGuard",
            "math_boundary": "POMDP-inspired approximate planner; utility ranks source discovery value, not truth.",
            "cli": "researchguard source plan starter_researchguard.source.yaml --model-contract starter_researchguard.source.contract.json",
            "boundary": "Candidate sources are not evidence; anchors are not events; handoff is not downstream validation.",
            "version": __version__,
            "source_policy": "public_only",
            "domain_hints": ["example entity"],
            "qualification_thresholds": {
                "source_reliability": 0.5,
                "extraction_confidence": 0.5,
                "specificity": 0.5,
            },
        },
        "leads": [
            {
                "lead_id": "lead-1",
                "question": "What independent source should be searched next?",
                "hypothesis": "A candidate claim needs independent corroborating or limiting material.",
                "importance": 0.7,
                "status": "open",
                "related_entities": ["example entity"],
                "gaps": ["gap-independent-1"],
            }
        ],
        "sources": [],
        "anchors": [],
        "gaps": [
            {
                "gap_id": "gap-independent-1",
                "lead_id": "lead-1",
                "gap_type": "missing_independent_source",
                "description": "No independent source candidate has been recorded.",
                "importance": 0.8,
                "blocking": True,
                "suggested_source_roles": ["independent_report"],
                "suggested_modalities": ["text"],
                "semantic_state": "discovered",
                "requires_claim_usability": True,
            }
        ],
        "actions": [
            {
                "action_id": "action-independent-search-1",
                "action_type": "text_search",
                "query": "example entity independent report",
                "target_lead_id": "lead-1",
                "target_gap_id": "gap-independent-1",
                "expected_source_role": "independent_report",
                "expected_modality": "text",
                "source_policy": "public_only",
                "cost": 0.3,
                "permission_risk": 0.0,
                "status": "proposed",
            }
        ],
        "observations": [],
        "graph_edges": [],
        "weights": {},
    }
    contract = load_target_contract(model_contract_path)
    payload["guard_contract"] = contract.to_dict()
    payload["candidate_contract_fingerprint"] = sourceguard_model_contract_fingerprint(contract)
    return payload


def _json_out(payload: Any, pretty: bool = False) -> None:
    print(json.dumps(to_plain(payload), ensure_ascii=False, indent=2 if pretty else None))


def _load_observation(path: str | Path) -> Observation:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Observation.from_dict(data or {})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="researchguard source")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("--output", required=True)
    create.add_argument("--model-contract", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("model")
    validate.add_argument("--model-contract", required=True)
    validate.add_argument("--pretty", action="store_true")

    plan = sub.add_parser("plan")
    plan.add_argument("model")
    plan.add_argument("--model-contract", required=True)
    plan.add_argument("--limit", type=int, default=5)
    plan.add_argument("--pretty", action="store_true")

    score = sub.add_parser("score-actions")
    score.add_argument("model")
    score.add_argument("--model-contract", required=True)
    score.add_argument("--pretty", action="store_true")

    frontier = sub.add_parser("frontier")
    frontier.add_argument("model")
    frontier.add_argument("--model-contract", required=True)
    frontier.add_argument("--pretty", action="store_true")

    depth = sub.add_parser("depth")
    depth.add_argument("model")
    depth.add_argument("--model-contract", required=True)
    depth.add_argument("--observation", default="")
    depth.add_argument(
        "--provider-status",
        choices=["NOT_RUN", "PROVIDER_UNAVAILABLE", "OBSERVATION_SUPPLIED"],
        default="NOT_RUN",
    )
    depth.add_argument("--limit", type=int, default=5)
    depth.add_argument("--output", default="")
    depth.add_argument("--updated-model-output", default="")
    depth.add_argument("--updated-model-contract-output", default="")
    depth.add_argument("--pretty", action="store_true")

    add_obs = sub.add_parser("add-observation")
    add_obs.add_argument("model")
    add_obs.add_argument("--model-contract", required=True)
    add_obs.add_argument("--observation", required=True)
    add_obs.add_argument("--output", required=True)
    add_obs.add_argument("--output-model-contract", required=True)
    add_obs.add_argument("--pretty", action="store_true")

    iteration = sub.add_parser(
        "search-iteration",
        help="Freeze, run, or roll back one task-local search-model iteration.",
    )
    iteration_sub = iteration.add_subparsers(dest="iteration_command", required=True)
    iteration_freeze = iteration_sub.add_parser(
        "freeze", help="Freeze expected search outcomes before applying an observation."
    )
    iteration_freeze.add_argument("model")
    iteration_freeze.add_argument("--model-contract", required=True)
    iteration_freeze.add_argument("--action-id", required=True)
    iteration_freeze.add_argument(
        "--expected-gap-reduction",
        required=True,
        choices=sorted(GAP_REDUCTION_LEVELS),
    )
    iteration_freeze.add_argument(
        "--expected-independent-lineage", required=True, choices=["true", "false"]
    )
    iteration_freeze.add_argument(
        "--expected-counterevidence", required=True, choices=["true", "false"]
    )
    iteration_freeze.add_argument("--expected-cost", required=True, type=float)
    iteration_freeze.add_argument("--cost-tolerance", type=float, default=0.1)
    iteration_freeze.add_argument(
        "--protect-gap",
        action="append",
        default=[],
        help="Gap whose complete task-local state must remain unchanged; repeat as needed.",
    )
    iteration_freeze.add_argument("--prediction-id")
    iteration_freeze.add_argument("--output", required=True)
    iteration_freeze.set_defaults(func=_cmd_search_iteration_freeze)

    iteration_run = iteration_sub.add_parser(
        "run", help="Apply one supplied observation and decide candidate v2."
    )
    iteration_run.add_argument("model")
    iteration_run.add_argument("--model-contract", required=True)
    iteration_run.add_argument("--prediction", required=True)
    iteration_run.add_argument("--observation", required=True)
    iteration_run.add_argument("--actual-cost", required=True, type=float)
    iteration_run.add_argument("--decision", choices=["accept", "reject"], default="reject")
    iteration_run.add_argument("--limit", type=int, default=5)
    iteration_run.add_argument("--candidate-output", required=True)
    iteration_run.add_argument("--candidate-model-contract-output", required=True)
    iteration_run.add_argument("--receipt-output", required=True)
    iteration_run.add_argument("--pretty", action="store_true")
    iteration_run.set_defaults(func=_cmd_search_iteration_run)

    iteration_rollback = iteration_sub.add_parser(
        "rollback", help="Write a new baseline-equivalent projection from an accepted receipt."
    )
    iteration_rollback.add_argument("model")
    iteration_rollback.add_argument("--model-contract", required=True)
    iteration_rollback.add_argument("--accepted-receipt", required=True)
    iteration_rollback.add_argument("--output", required=True)
    iteration_rollback.add_argument("--output-model-contract", required=True)
    iteration_rollback.add_argument("--receipt-output", required=True)
    iteration_rollback.add_argument("--pretty", action="store_true")
    iteration_rollback.set_defaults(func=_cmd_search_iteration_rollback)

    report = sub.add_parser("report")
    report.add_argument("model")
    report.add_argument("--model-contract", required=True)
    report.add_argument("--format", choices=["markdown", "txt", "json"], default="markdown")

    trace = sub.add_parser("export-traceguard")
    trace.add_argument("model")
    trace.add_argument("--model-contract", required=True)
    trace.add_argument("--output", required=True)

    logic = sub.add_parser("export-logicguard")
    logic.add_argument("model")
    logic.add_argument("--model-contract", required=True)
    logic.add_argument("--output", required=True)

    simulate = sub.add_parser("simulate")
    simulate.add_argument(
        "--mode",
        choices=["fuel-cell-project", "paper-lineage", "multimodal", "gap-closure"],
        required=True,
    )
    simulate.add_argument("--model", default="")
    simulate.add_argument("--model-contract", default="")
    simulate.add_argument("--pretty", action="store_true")

    compare = sub.add_parser("compare")
    compare.add_argument("before")
    compare.add_argument("after")
    compare.add_argument("--before-model-contract", required=True)
    compare.add_argument("--after-model-contract", required=True)
    compare.add_argument("--pretty", action="store_true")
    return parser


def _gap_summary(gap: Any) -> dict[str, Any]:
    return {
        "gap_id": gap.gap_id,
        "lead_id": gap.lead_id,
        "gap_type": gap.gap_type,
        "semantic_state": gap.semantic_state,
        "review_required": gap.review_required,
        "blocking": gap.blocking,
        "importance": gap.importance,
        "description": gap.description,
    }


def _action_summary(action: Any) -> dict[str, Any]:
    return {
        "action_id": action.action_id,
        "action_type": action.action_type,
        "target_gap_id": action.target_gap_id,
        "expected_source_role": action.expected_source_role,
        "expected_modality": action.expected_modality,
        "status": action.status,
        "query": action.query,
    }


def _simulate_gap_closure(model_path: str, model_contract_path: str) -> dict[str, Any]:
    if not model_path:
        raise ValueError("simulate --mode gap-closure requires --model <path>")
    if not model_contract_path:
        raise ValueError("simulate --mode gap-closure requires --model-contract <path>")
    model = load_model(model_path, model_contract_path)
    plan = plan_next_actions(model)
    frontier = frontier_summary(model)
    selected_gap_ids = sorted({action.target_gap_id for action in plan.selected_actions if action.target_gap_id})
    return {
        "ok": True,
        "mode": "gap-closure",
        "model": model_path,
        "model_contract": model_contract_path,
        "frontier": frontier,
        "open_gaps": [_gap_summary(gap) for gap in plan.open_gaps],
        "blocking_gaps": [_gap_summary(gap) for gap in plan.blocked_gaps],
        "selected_actions": [_action_summary(action) for action in plan.selected_actions],
        "would_rehearse_gap_ids": selected_gap_ids,
        "warnings": plan.warnings,
        "boundary": (
            "Local rehearsal only: selected actions would need external observations before any gap is closed. "
            "Scores are search utility, not truth or final claim confidence."
        ),
    }


def _simulate(mode: str, model_path: str = "", model_contract_path: str = "") -> dict[str, Any]:
    if mode == "gap-closure":
        return _simulate_gap_closure(model_path, model_contract_path)
    return {
        "ok": True,
        "mode": mode,
        "boundary": "Conceptual simulation only; no external search, OCR, video analysis, or source validation was performed.",
        "pipeline": [
            "load belief state",
            "identify leads and gaps",
            "generate candidate search actions",
            "score expected utility",
            "record observations only if externally supplied",
            "export candidate handoff bundle when ready",
        ],
    }


def _ids_by(items: list[Any], field_name: str) -> set[str]:
    return {str(getattr(item, field_name)) for item in items}


def _changed_gaps(before: BeliefState, after: BeliefState) -> list[dict[str, Any]]:
    before_gaps = before.gap_by_id()
    after_gaps = after.gap_by_id()
    changed: list[dict[str, Any]] = []
    for gap_id in sorted(set(before_gaps) & set(after_gaps)):
        old = before_gaps[gap_id]
        new = after_gaps[gap_id]
        fields = (
            "gap_type",
            "status",
            "semantic_state",
            "review_required",
            "blocking",
            "importance",
            "description",
        )
        delta = {
            field: {"before": getattr(old, field), "after": getattr(new, field)}
            for field in fields
            if getattr(old, field) != getattr(new, field)
        }
        if delta:
            changed.append({"gap_id": gap_id, "changes": delta})
    return changed


def _changed_actions(before: BeliefState, after: BeliefState) -> list[dict[str, Any]]:
    before_actions = before.action_by_id()
    after_actions = after.action_by_id()
    changed: list[dict[str, Any]] = []
    for action_id in sorted(set(before_actions) & set(after_actions)):
        old = before_actions[action_id]
        new = after_actions[action_id]
        fields = ("target_gap_id", "expected_source_role", "expected_modality", "status", "query")
        delta = {
            field: {"before": getattr(old, field), "after": getattr(new, field)}
            for field in fields
            if getattr(old, field) != getattr(new, field)
        }
        if delta:
            changed.append({"action_id": action_id, "changes": delta})
    return changed


def _compare_models(
    before_path: str,
    after_path: str,
    before_contract_path: str,
    after_contract_path: str,
) -> dict[str, Any]:
    before = load_model(before_path, before_contract_path)
    after = load_model(after_path, after_contract_path)
    before_sources = _ids_by(before.sources, "source_id")
    after_sources = _ids_by(after.sources, "source_id")
    before_anchors = _ids_by(before.anchors, "anchor_id")
    after_anchors = _ids_by(after.anchors, "anchor_id")
    before_gaps = set(before.gap_by_id())
    after_gaps = set(after.gap_by_id())
    before_actions = set(before.action_by_id())
    after_actions = set(after.action_by_id())
    return {
        "ok": True,
        "before": before_path,
        "after": after_path,
        "source_delta": {
            "added": sorted(after_sources - before_sources),
            "removed": sorted(before_sources - after_sources),
        },
        "anchor_delta": {
            "added": sorted(after_anchors - before_anchors),
            "removed": sorted(before_anchors - after_anchors),
        },
        "gap_delta": {
            "added": sorted(after_gaps - before_gaps),
            "removed": sorted(before_gaps - after_gaps),
            "changed": _changed_gaps(before, after),
        },
        "action_delta": {
            "added": sorted(after_actions - before_actions),
            "removed": sorted(before_actions - after_actions),
            "changed": _changed_actions(before, after),
        },
        "boundary": "Model comparison reviews source-discovery state changes; it is not evidence validation.",
    }


def _cmd_search_iteration_freeze(args: argparse.Namespace) -> int:
    _require_new_outputs(
        inputs=[args.model, args.model_contract],
        outputs=[args.output],
    )
    baseline = load_model(args.model, args.model_contract)
    prediction = freeze_search_outcome_prediction(
        baseline,
        action_id=args.action_id,
        expected_gap_reduction=args.expected_gap_reduction,
        expected_independent_lineage=args.expected_independent_lineage == "true",
        expected_counterevidence=args.expected_counterevidence == "true",
        expected_cost=args.expected_cost,
        cost_tolerance=args.cost_tolerance,
        protected_gap_ids=args.protect_gap,
        prediction_id=args.prediction_id,
    )
    _write_json(args.output, prediction.to_dict())
    _json_out({"ok": True, "prediction": prediction.to_dict()}, True)
    return 0


def _cmd_search_iteration_run(args: argparse.Namespace) -> int:
    _require_new_outputs(
        inputs=[
            args.model,
            args.model_contract,
            args.prediction,
            args.observation,
        ],
        outputs=[
            args.candidate_output,
            args.candidate_model_contract_output,
            args.receipt_output,
        ],
    )
    baseline = load_model(args.model, args.model_contract)
    prediction = SearchOutcomePrediction.from_dict(
        _load_json_object(args.prediction)
    )
    observation = _load_observation(args.observation)
    candidate, receipt = run_search_iteration(
        baseline,
        prediction,
        observation,
        actual_cost=args.actual_cost,
        decision=args.decision,
        limit=args.limit,
    )
    write_yaml(args.candidate_output, candidate)
    assert candidate.guard_contract is not None
    _write_json(
        args.candidate_model_contract_output,
        candidate.guard_contract.to_dict(),
    )
    _write_json(args.receipt_output, receipt.to_dict())
    _json_out({"ok": True, **receipt.to_dict()}, args.pretty)
    if args.decision == "accept" and receipt.effective_disposition != "accepted":
        return 3
    return 0


def _cmd_search_iteration_rollback(args: argparse.Namespace) -> int:
    _require_new_outputs(
        inputs=[args.model, args.model_contract, args.accepted_receipt],
        outputs=[args.output, args.output_model_contract, args.receipt_output],
    )
    baseline = load_model(args.model, args.model_contract)
    restored, receipt = rollback_search_iteration(
        baseline, _load_json_object(args.accepted_receipt)
    )
    write_yaml(args.output, restored)
    assert restored.guard_contract is not None
    _write_json(args.output_model_contract, restored.guard_contract.to_dict())
    _write_json(args.receipt_output, receipt.to_dict())
    _json_out({"ok": True, **receipt.to_dict()}, args.pretty)
    return 0


def run(args: argparse.Namespace) -> int:
    command_func = getattr(args, "func", None)
    if command_func is not None:
        return command_func(args)
    if args.command == "create":
        model = BeliefState.from_dict(starter_model_dict(args.model_contract))
        prove_target_model_contract(model, args.model_contract)
        write_yaml(args.output, model)
        _json_out(
            {
                "ok": True,
                "output": args.output,
                "model_contract": args.model_contract,
                "boundary": model.metadata["boundary"],
            },
            True,
        )
        return 0
    if args.command == "validate":
        _json_out(validate_model(args.model, args.model_contract), args.pretty)
        return 0
    if args.command == "plan":
        model = load_model(args.model, args.model_contract)
        _json_out(plan_next_actions(model, limit=args.limit), args.pretty)
        return 0
    if args.command == "score-actions":
        _json_out(
            {
                "ok": True,
                "scored_actions": score_actions(load_model(args.model, args.model_contract)),
            },
            args.pretty,
        )
        return 0
    if args.command == "frontier":
        _json_out(
            {"ok": True, **frontier_summary(load_model(args.model, args.model_contract))},
            args.pretty,
        )
        return 0
    if args.command == "depth":
        model = load_model(args.model, args.model_contract)
        observation = _load_observation(args.observation) if args.observation else None
        updated, receipt = apply_observation_and_replan(
            model,
            observation,
            provider_status=args.provider_status,
            limit=args.limit,
        )
        payload = to_plain(receipt)
        if args.output:
            Path(args.output).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        if args.updated_model_output:
            if not args.updated_model_contract_output:
                raise ValueError(
                    "--updated-model-output requires --updated-model-contract-output"
                )
            write_yaml(args.updated_model_output, updated)
            assert updated.guard_contract is not None
            Path(args.updated_model_contract_output).write_text(
                json.dumps(updated.guard_contract.to_dict(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        elif args.updated_model_contract_output:
            raise ValueError(
                "--updated-model-contract-output requires --updated-model-output"
            )
        _json_out(payload, args.pretty)
        return 0
    if args.command == "add-observation":
        model = load_model(args.model, args.model_contract)
        updated = apply_observation(model, _load_observation(args.observation))
        write_yaml(args.output, updated)
        assert updated.guard_contract is not None
        Path(args.output_model_contract).write_text(
            json.dumps(updated.guard_contract.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        _json_out(
            {
                "ok": True,
                "output": args.output,
                "output_model_contract": args.output_model_contract,
                "warnings": updated.metadata.get("warnings", []),
            },
            args.pretty,
        )
        return 0
    if args.command == "report":
        model = load_model(args.model, args.model_contract)
        if args.format == "markdown":
            print(render_markdown(model), end="")
        elif args.format == "txt":
            print(render_text(model), end="")
        else:
            print(render_json(model))
        return 0
    if args.command == "export-traceguard":
        write_yaml(
            args.output,
            export_traceguard_seed(load_model(args.model, args.model_contract)),
        )
        _json_out({"ok": True, "output": args.output}, True)
        return 0
    if args.command == "export-logicguard":
        write_yaml(
            args.output,
            export_logicguard_source_candidates(load_model(args.model, args.model_contract)),
        )
        _json_out({"ok": True, "output": args.output}, True)
        return 0
    if args.command == "simulate":
        _json_out(_simulate(args.mode, args.model, args.model_contract), args.pretty)
        return 0
    if args.command == "compare":
        _json_out(
            _compare_models(
                args.before,
                args.after,
                args.before_model_contract,
                args.after_model_contract,
            ),
            args.pretty,
        )
        return 0
    raise ValueError(f"Unknown command {args.command!r}")


def _load_json_object(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must contain an object: {path}")
    return payload


def _write_json(path: str | Path, payload: Mapping[str, Any] | dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _require_new_outputs(
    *,
    inputs: list[str | Path],
    outputs: list[str | Path],
) -> None:
    input_paths = {Path(item).resolve() for item in inputs}
    output_paths = [Path(item).resolve() for item in outputs]
    if len(output_paths) != len(set(output_paths)):
        raise ValueError("task-local iteration output paths must be distinct")
    for output in output_paths:
        if output in input_paths:
            raise ValueError(f"task-local iteration cannot overwrite an input: {output}")
        if output.exists():
            raise ValueError(f"task-local iteration output already exists: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        return run(args)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
