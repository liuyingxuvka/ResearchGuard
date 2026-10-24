"""
Purpose: Provide the local SourceGuard command line interface.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: SourceGuard
Math boundary: Expected utility ranks search value, not factual truth or calibrated probability.
CLI: researchguard source --help
Boundary: Source candidates and evidence anchors require downstream TraceGuard/LogicGuard review before final claims.
"""

from __future__ import annotations

from researchguard._artifact_io import _load_json_object

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

import yaml

from researchguard import __version__

from .depth import apply_observation_and_replan
from .handoff import export_traceguard_seed, sync_traceguard_seed
from .loader import load_model, validate_model, write_yaml
from .planner import frontier_summary, plan_next_actions
from .report import render_json, render_markdown, render_text
from .schema import (
    BeliefState,
    Observation,
    to_plain,
)
from .stop_decision import decide_model_search_stop
from .update import apply_observation
from .task_iteration import (
    GAP_REDUCTION_LEVELS,
    SearchOutcomePrediction,
    freeze_search_outcome_prediction,
    run_search_iteration,
)


def starter_model_dict() -> dict[str, Any]:
    payload = {'metadata': {'purpose': 'Illustrate source discovery for a bounded recovery claim; the sample is '
                             'synthetic.',
                  'repository': 'https://github.com/liuyingxuvka/ResearchGuard',
                  'skill': 'SourceGuard',
                  'math_boundary': 'Expected utility ranks discovery value, not factual truth or '
                                   'calibrated probability.',
                  'cli': 'researchguard source validate starter.yaml',
                  'boundary': 'Replace the teaching rows with retrieved material; sample anchors do '
                              'not license real claims.',
                  'source_policy': 'public_only',
                  'domain_hints': ['harbor departures', 'reopening'],
                  'qualification_thresholds': {'source_reliability': 0.5,
                                               'extraction_confidence': 0.5,
                                               'specificity': 0.5}},
     'leads': [{'lead_id': 'example-recovery',
                'question': 'Did daily harbor departures recover after reopening?',
                'hypothesis': 'Daily departures recovered within the reported observation period.',
                'importance': 0.7,
                'status': 'open',
                'related_sources': ['example-departure-log'],
                'related_anchors': ['example-log-row'],
                'gaps': ['example-independent-report', 'example-later-period']}],
     'sources': [{'source_id': 'example-departure-log',
                  'title': 'Synthetic daily departure log',
                  'source_type': 'local_file',
                  'source_status': 'saved',
                  'source_role': 'primary_source',
                  'lineage_id': 'example-log-lineage',
                  'access_status': 'local',
                  'notes': 'Teaching data only; no real-world source was retrieved.'}],
     'anchors': [{'anchor_id': 'example-log-row',
                  'source_id': 'example-departure-log',
                  'anchor_type': 'dataset_row',
                  'locator': 'row 1',
                  'text': 'Synthetic example: daily departures increased during the stated period.',
                  'modality': 'text',
                  'supports': ['example-recovery'],
                  'limits': ['Synthetic teaching data; not evidence for an actual harbor.'],
                  'usable_for_trace': False,
                  'usable_for_claim': False}],
     'gaps': [{'gap_id': 'example-independent-report',
               'lead_id': 'example-recovery',
               'gap_type': 'missing_independent_source',
               'description': 'Retrieve an independent report before licensing the recovery claim.',
               'importance': 0.8,
               'blocking': True,
               'suggested_source_roles': ['independent_report'],
               'suggested_modalities': ['text']},
              {'gap_id': 'example-later-period',
               'lead_id': 'example-recovery',
               'gap_type': 'unclear_scope',
               'description': 'A later observation period would bound persistence of any recovery.',
               'importance': 0.3,
               'blocking': False,
               'suggested_source_roles': ['limiting_evidence'],
               'suggested_modalities': ['text']}],
     'actions': [{'action_id': 'example-search-independent',
                  'action_type': 'text_search',
                  'query': 'harbor departures reopening independent report',
                  'target_lead_id': 'example-recovery',
                  'target_gap_id': 'example-independent-report',
                  'expected_source_role': 'independent_report',
                  'expected_modality': 'text',
                  'source_policy': 'public_only',
                  'cost': 0.3,
                  'permission_risk': 0.0,
                  'status': 'proposed'}],
     'observations': [],
     'graph_edges': [],
     'weights': {},
     'depth_policy': {'requested_claim_scope': 'bounded'}}
    payload["metadata"]["version"] = __version__
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

    validate = sub.add_parser("validate")
    validate.add_argument("model")
    validate.add_argument("--pretty", action="store_true")

    plan = sub.add_parser("plan")
    plan.add_argument("model")
    plan.add_argument("--limit", type=int, default=5)
    plan.add_argument("--all-scores", action="store_true", help="Also print every scored candidate action.")
    plan.add_argument("--pretty", action="store_true")

    score = sub.add_parser("score-actions")
    score.add_argument("model")
    score.add_argument("--pretty", action="store_true")

    frontier = sub.add_parser("frontier")
    frontier.add_argument("model")
    frontier.add_argument("--pretty", action="store_true")

    stop = sub.add_parser("stop-decision", help="Decide whether the search should continue.")
    stop.add_argument("model")
    stop.add_argument("--budget", type=float, required=True, help="Remaining search budget, in the units of action cost.")
    stop.add_argument("--sufficient", action="store_true", help="Declare that the evidence already suffices for the claim scope.")
    stop.add_argument("--pretty", action="store_true")

    depth = sub.add_parser("depth")
    depth.add_argument("model")
    depth.add_argument("--observation", default="")
    depth.add_argument(
        "--provider-status",
        choices=["NOT_RUN", "PROVIDER_UNAVAILABLE", "OBSERVATION_SUPPLIED"],
        default="NOT_RUN",
    )
    depth.add_argument("--limit", type=int, default=5)
    depth.add_argument("--output", default="")
    depth.add_argument("--updated-model-output", default="")
    depth.add_argument("--pretty", action="store_true")

    add_obs = sub.add_parser("add-observation")
    add_obs.add_argument("model")
    add_obs.add_argument("--observation", required=True)
    add_obs.add_argument("--output", required=True)
    add_obs.add_argument("--pretty", action="store_true")

    iteration = sub.add_parser(
        "search-iteration",
        help="Freeze or run one task-local search-model iteration.",
    )
    iteration_sub = iteration.add_subparsers(dest="iteration_command", required=True)
    iteration_freeze = iteration_sub.add_parser(
        "freeze", help="Freeze expected search outcomes before applying an observation."
    )
    iteration_freeze.add_argument("model")
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
    iteration_freeze.add_argument("--task-id", default="")
    iteration_freeze.add_argument("--purpose", default="")
    iteration_freeze.add_argument("--coverage-id", action="append", default=[])
    iteration_freeze.add_argument("--assumption", action="append", default=[])
    iteration_freeze.add_argument("--unknown", action="append", default=[])
    iteration_freeze.add_argument("--iteration", type=int, default=0)
    iteration_freeze.add_argument("--max-iterations", type=int, default=8)
    iteration_freeze.add_argument("--prior-open-gap-id", action="append", default=[])
    iteration_freeze.add_argument("--output", required=True)
    iteration_freeze.set_defaults(func=_cmd_search_iteration_freeze)

    iteration_run = iteration_sub.add_parser(
        "run", help="Apply one supplied observation and decide candidate v2."
    )
    iteration_run.add_argument("model")
    iteration_run.add_argument("--prediction", required=True)
    iteration_run.add_argument("--observation", default="")
    iteration_run.add_argument(
        "--provider-status",
        choices=["OBSERVATION_SUPPLIED", "PROVIDER_UNAVAILABLE", "NOT_RUN"],
        default="OBSERVATION_SUPPLIED",
    )
    iteration_run.add_argument("--actual-cost", required=True, type=float)
    iteration_run.add_argument("--decision", choices=["accept", "reject"], default="reject")
    iteration_run.add_argument("--limit", type=int, default=5)
    iteration_run.add_argument("--candidate-output", required=True)
    iteration_run.add_argument("--output", required=True)
    iteration_run.add_argument("--pretty", action="store_true")
    iteration_run.set_defaults(func=_cmd_search_iteration_run)


    report = sub.add_parser("report")
    report.add_argument("model")
    report.add_argument("--format", choices=["markdown", "txt", "json"], default="markdown")

    trace = sub.add_parser("export-traceguard")
    trace.add_argument("model")
    trace.add_argument("--output", required=True)
    trace.add_argument("--into", help="Append missing source and anchor ids to an existing trace model.")

    simulate = sub.add_parser("simulate")
    simulate.add_argument(
        "--mode",
        choices=["fuel-cell-project", "paper-lineage", "multimodal", "gap-closure"],
        required=True,
    )
    simulate.add_argument("--model", default="")
    simulate.add_argument("--pretty", action="store_true")

    compare = sub.add_parser("compare")
    compare.add_argument("before")
    compare.add_argument("after")
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


def _simulate_gap_closure(model_path: str) -> dict[str, Any]:
    if not model_path:
        raise ValueError("simulate --mode gap-closure requires --model <path>")
    model = load_model(model_path)
    plan = plan_next_actions(model)
    frontier = frontier_summary(model)
    selected_gap_ids = sorted({action.target_gap_id for action in plan.selected_actions if action.target_gap_id})
    return {
        "ok": True,
        "mode": "gap-closure",
        "model": model_path,
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


def _simulate(mode: str, model_path: str = "") -> dict[str, Any]:
    if mode == "gap-closure":
        return _simulate_gap_closure(model_path)
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
        fields = {
            field: (lambda gap, field=field: getattr(gap, field))
            for field in ("gap_type", "semantic_state", "review_required", "blocking", "importance", "description")
        }
        fields["qualification_decision"] = lambda gap: gap.qualification.decision
        delta = {
            field: {"before": read(old), "after": read(new)}
            for field, read in fields.items()
            if read(old) != read(new)
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


def _compare_models(before_path: str, after_path: str) -> dict[str, Any]:
    before = load_model(before_path)
    after = load_model(after_path)
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
        inputs=[args.model],
        outputs=[args.output],
    )
    baseline = load_model(args.model)
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
        task_id=args.task_id,
        purpose=args.purpose,
        coverage_ids=args.coverage_id,
        assumptions=args.assumption,
        unknowns=args.unknown,
        iteration=args.iteration,
        max_iterations=args.max_iterations,
        prior_open_gap_ids=args.prior_open_gap_id,
    )
    _write_json(args.output, prediction.to_dict())
    _json_out({"ok": True, "prediction": prediction.to_dict()}, True)
    return 0


def _cmd_search_iteration_run(args: argparse.Namespace) -> int:
    _require_new_outputs(
        inputs=[
            args.model,
            args.prediction,
            *([args.observation] if args.observation else []),
        ],
        outputs=[
            args.candidate_output,
            args.output,
        ],
    )
    baseline = load_model(args.model)
    prediction = SearchOutcomePrediction.from_dict(
        _load_json_object(args.prediction)
    )
    observation = _load_observation(args.observation) if args.observation else None
    candidate, result = run_search_iteration(
        baseline,
        prediction,
        observation,
        actual_cost=args.actual_cost,
        decision=args.decision,
        limit=args.limit,
        provider_status=args.provider_status,
    )
    write_yaml(args.candidate_output, candidate)
    _write_json(args.output, result.to_dict())
    _json_out({"ok": True, **result.to_dict()}, args.pretty)
    if args.decision == "accept" and result.effective_disposition != "accepted":
        return 3
    return 0


def run(args: argparse.Namespace) -> int:
    command_func = getattr(args, "func", None)
    if command_func is not None:
        return command_func(args)
    if args.command == "create":
        model = BeliefState.from_dict(starter_model_dict())
        write_yaml(args.output, model)
        _json_out(
            {
                "ok": True,
                "output": args.output,
                "boundary": model.metadata["boundary"],
            },
            True,
        )
        return 0
    if args.command == "validate":
        _json_out(validate_model(args.model), args.pretty)
        return 0
    if args.command == "plan":
        model = load_model(args.model)
        payload = to_plain(plan_next_actions(model, limit=args.limit))
        if not args.all_scores:
            payload.pop("scored_actions", None)
        _json_out(payload, args.pretty)
        return 0
    if args.command == "score-actions":
        _json_out(
            {
                "ok": True,
                "scored_actions": plan_next_actions(load_model(args.model), limit=None).scored_actions,
            },
            args.pretty,
        )
        return 0
    if args.command == "frontier":
        _json_out(
            {"ok": True, **frontier_summary(load_model(args.model))},
            args.pretty,
        )
        return 0
    if args.command == "stop-decision":
        inputs, decision = decide_model_search_stop(
            load_model(args.model),
            remaining_budget=args.budget,
            evidence_sufficient_for_scope=args.sufficient,
        )
        _json_out({"ok": decision.status != "not_run", "inputs": inputs.to_dict(), **decision.to_dict()}, args.pretty)
        return 0
    if args.command == "depth":
        model = load_model(args.model)
        observation = _load_observation(args.observation) if args.observation else None
        updated, depth_result = apply_observation_and_replan(
            model,
            observation,
            provider_status=args.provider_status,
            limit=args.limit,
        )
        payload = to_plain(depth_result)
        if args.output:
            Path(args.output).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        if args.updated_model_output:
            write_yaml(args.updated_model_output, updated)
        _json_out(payload, args.pretty)
        return 0
    if args.command == "add-observation":
        model = load_model(args.model)
        updated = apply_observation(model, _load_observation(args.observation))
        write_yaml(args.output, updated)
        _json_out(
            {
                "ok": True,
                "output": args.output,
                "warnings": updated.metadata.get("warnings", []),
            },
            args.pretty,
        )
        return 0
    if args.command == "report":
        model = load_model(args.model)
        if args.format == "markdown":
            print(render_markdown(model), end="")
        elif args.format == "txt":
            print(render_text(model), end="")
        else:
            print(render_json(model))
        return 0
    if args.command == "export-traceguard":
        source = load_model(args.model)
        payload = {"ok": True, "output": args.output}
        if args.into:
            if Path(args.into).resolve() == Path(args.output).resolve():
                raise ValueError("--output must be different from --into")
            existing = yaml.safe_load(Path(args.into).read_text(encoding="utf-8"))
            merged, added, updated, conflicts = sync_traceguard_seed(source, existing)
            payload.update(added=added, updated=updated, conflicts=conflicts)
        else:
            merged = export_traceguard_seed(source)
        write_yaml(args.output, merged)
        _json_out(payload, True)
        return 0
    if args.command == "simulate":
        _json_out(_simulate(args.mode, args.model), args.pretty)
        return 0
    if args.command == "compare":
        _json_out(
            _compare_models(args.before, args.after),
            args.pretty,
        )
        return 0
    raise ValueError(f"Unknown command {args.command!r}")




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
