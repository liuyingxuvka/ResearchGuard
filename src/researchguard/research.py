"""Read a research folder, check shared identities, and project native results."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

import yaml

from . import SUITE_ID
from .experiment.loader import _load_observations, _load_spec
from .experiment.engine import observe_experiments, recommend_experiments
from .logic.evaluator import evaluate_model as evaluate_logic
from .logic.loader import load_model as load_logic
from .logic.provenance import validate_evidence_provenance
from .logic.validator import source_model_provenance_problems
from .source.loader import load_model as load_source
from .source.planner import plan_next_actions
from .source.schema import to_plain
from .trace.evaluator import evaluate_model as evaluate_trace
from .trace.loader import load_model as load_trace


@dataclass
class ResearchTree:
    path: Path
    index: dict[str, Any]
    models: dict[str, Any] = field(default_factory=dict)
    observations: tuple[Any, ...] = ()
    errors: list[str] = field(default_factory=list)


def _validate_index(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or data.get("schema") != "researchguard.research.v1":
        raise ValueError("expected researchguard.research.v1 index")
    if not isinstance(data.get("question"), str) or not data["question"].strip():
        raise ValueError("question must be a nonempty string")
    rows = data.get("hypotheses")
    if not isinstance(rows, list) or not rows:
        raise ValueError("hypotheses must contain at least one id/text row")
    for row in rows:
        if not isinstance(row, dict) or any(not isinstance(row.get(k), str) or not row[k].strip() for k in ("id", "text")):
            raise ValueError("each hypothesis needs nonempty id and text")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("hypothesis ids must be unique")
    models = data.get("models", {})
    if not isinstance(models, dict) or set(models) - {"source", "trace", "logic", "experiment", "experiment_observations"}:
        raise ValueError("models must map current route names to paths")
    for route, value in models.items():
        if route == "experiment_observations":
            if not isinstance(value, list) or any(not isinstance(p, str) or not p.strip() for p in value):
                raise ValueError("experiment_observations must be a list of paths")
        elif not isinstance(value, str) or not value.strip():
            raise ValueError(f"model path for {route} must be a nonempty string")
    if "root_claim" in data and (not isinstance(data["root_claim"], str) or not data["root_claim"].strip()):
        raise ValueError("root_claim must be a nonempty id")
    if models.get("experiment_observations") and "experiment" not in models:
        raise ValueError("experiment observations require an experiment model")
    return data


def load_research(path: str | Path) -> ResearchTree:
    index_path = Path(path)
    if index_path.is_dir():
        index_path /= "research.yaml"
    data = _validate_index(yaml.safe_load(index_path.read_text(encoding="utf-8")))
    tree = ResearchTree(index_path, data)
    loaders = {"source": load_source, "trace": load_trace, "logic": load_logic, "experiment": _load_spec}
    for route, loader in loaders.items():
        if route not in data.get("models", {}):
            continue
        model_path = index_path.parent / data["models"][route]
        if not model_path.is_file():
            tree.errors.append(f"model_missing:{route}")
            continue
        try:
            tree.models[route] = loader(model_path)
        except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as exc:
            tree.errors.append(f"model_invalid:{route}: {exc}")
    observations = []
    for name in data.get("models", {}).get("experiment_observations", []):
        obs_path = index_path.parent / name
        if not obs_path.is_file():
            tree.errors.append(f"model_missing:experiment_observations:{name}")
            continue
        try:
            observations.extend(_load_observations(obs_path))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            tree.errors.append(f"model_invalid:experiment_observations:{name}: {exc}")
    tree.observations = tuple(observations)
    return tree


def check_research_tree(index: dict[str, Any], models: dict[str, Any], observations: tuple[Any, ...] = ()) -> dict[str, list[str]]:
    """Check already-loaded native models in memory; perform no file I/O or solving."""
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    ids = {row["id"] for row in index["hypotheses"]}
    used: set[str] = set()
    trace = models.get("trace")
    if trace is not None:
        trace_ids = {row.hypothesis_id for row in trace.storyline_hypotheses}
        used.update(trace_ids)
        errors.extend(f"unknown_hypothesis:trace:{item}" for item in sorted(trace_ids - ids))
    experiment = models.get("experiment")
    if experiment is not None:
        exp_ids = {row.hypothesis_id for row in experiment.hypothesis_predictions}
        used.update(exp_ids)
        errors.extend(f"unknown_hypothesis:experiment:{item}" for item in sorted(exp_ids - ids))
    logic = models.get("logic")
    if logic is not None:
        claims = {key for key, row in logic.nodes.items() if row.type == "Claim"}
        used.update(claims)
        root = index.get("root_claim", "<not declared>")
        if root not in claims:
            errors.append(f"root_claim_missing:{root}")
        warnings.extend(f"hypothesis_not_in_logic:{item}" for item in sorted(ids - claims))
    warnings.extend(f"hypothesis_unused:{item}" for item in sorted(ids - used))
    source = models.get("source")
    if source is None:
        if "source" not in index.get("models", {}):
            info.append("source_model_not_listed")
    else:
        source_ids = {row.source_id for row in source.sources}
        anchors = {row.anchor_id: row.source_id for row in source.anchors}
        if trace is not None:
            errors.extend(f"dangling_source:trace:{row.source_id}" for row in trace.sources if row.source_id not in source_ids)
            errors.extend(f"dangling_anchor:trace:{row.evidence_id}" for row in trace.evidence
                          if anchors.get(row.evidence_id) != row.source_id)
        if logic is not None:
            errors.extend(source_model_provenance_problems(logic, to_plain(source)))
        for row in observations:
            if row.evidence_id not in anchors or anchors.get(row.evidence_id) != row.source_ref:
                errors.append(f"dangling_anchor:experiment:{row.evidence_id}")
            if row.source_ref not in source_ids:
                errors.append(f"dangling_source:experiment:{row.source_ref}")
    return {"errors": sorted(set(errors)), "warnings": sorted(set(warnings)), "info": info}


def research_status(tree: ResearchTree) -> dict[str, Any]:
    problems = check_research_tree(tree.index, tree.models, tree.observations)
    problems["errors"] = sorted(set(tree.errors + problems["errors"]))
    results: dict[str, Any] = {}
    for route, model in tree.models.items():
        try:
            if route == "logic":
                results[route] = evaluate_logic(model)
            elif route == "trace":
                results[route] = evaluate_trace(model, include_storyline_depth=True)
            elif route == "source":
                results[route] = plan_next_actions(model)
            elif route == "experiment":
                results[route] = observe_experiments(model, tree.observations) if tree.observations else recommend_experiments(model)
        except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
            problems["errors"].append(f"model_invalid:{route}: {exc}")
    logic = results.get("logic")
    trace = results.get("trace")
    trace_rows = {row.hypothesis_id: row.to_dict() for row in trace.inference.hypothesis_projections} if trace else {}
    exp_payload = results["experiment"].to_dict() if "experiment" in results else {}
    exp_rows = {row["hypothesis_id"]: row for row in exp_payload.get("hypothesis_dispositions", [])}
    hypotheses = [{**row,
                   "logic": logic.node_results[row["id"]].to_dict() if logic and row["id"] in logic.node_results else None,
                   "trace": trace_rows.get(row["id"]),
                   "experiment": exp_rows.get(row["id"], {"status": exp_payload.get("status", "not_listed")})}
                  for row in tree.index["hypotheses"]]
    evidence = []
    source = tree.models.get("source")
    if source:
        sources = {row.source_id: row for row in source.sources}
        for anchor in source.anchors:
            used_by = []
            trace_model = tree.models.get("trace")
            if trace_model:
                used_by.extend(f"trace:{row.hypothesis_id}:{row.polarity}" for row in trace_model.hypothesis_evidence_links if row.evidence_id == anchor.anchor_id)
                for hypothesis in trace_model.storyline_hypotheses:
                    if anchor.anchor_id in hypothesis.evidence_ids:
                        used_by.append(f"trace:{hypothesis.hypothesis_id}:support")
                    if anchor.anchor_id in hypothesis.contradicting_evidence_ids:
                        used_by.append(f"trace:{hypothesis.hypothesis_id}:oppose")
            if "logic" in tree.models:
                for node in tree.models["logic"].nodes.values():
                    if node.type == "Evidence" and any(row.locator == anchor.anchor_id and row.source_id == anchor.source_id
                                                     for row in validate_evidence_provenance(node.id, node.provenance)):
                        used_by.append(f"logic:{node.id}")
            evidence.append({"anchor": anchor.anchor_id, "source": anchor.source_id,
                             "lineage": sources[anchor.source_id].lineage_id if anchor.source_id in sources else "",
                             "used_by": sorted(set(used_by))})
    gaps: list[dict[str, Any]] = []
    next_actions: list[dict[str, Any]] = []
    plan = results.get("source")
    if plan:
        next_actions.extend({"route": "search", "id": row.action_id, "query": row.query} for row in plan.selected_actions)
        gaps.extend({"route": "source", "id": row.gap_id, "blocking": row.blocking,
                     "next": [action.action_id for action in plan.selected_actions if action.target_gap_id == row.gap_id]}
                    for row in plan.open_gaps)
    if trace and trace.storyline_depth:
        depth = trace.storyline_depth.to_dict()
        gaps.append({"route": "trace depth", **{key: depth[key] for key in (
            "closure_status", "broad_claim_licensed", "covered_claim_scope", "unresolved_gaps")}})
    if logic:
        root = tree.index.get("root_claim")
        gaps.append({"route": "logic", "root_claim": root,
                     "blocked_by": logic.node_results[root].blockers if root in logic.node_results else []})
    if exp_payload:
        next_actions.append({"route": "experiment", "ids": exp_payload.get("selected_experiment_ids", exp_payload.get("next_experiment_ids", [])),
                             "status": exp_payload.get("status", exp_payload.get("terminal_reason"))})
    return {"suite": SUITE_ID, "question": tree.index["question"], "models": {
        key: {"path": value, "status": "ok" if key in results else "invalid"}
        for key, value in tree.index.get("models", {}).items() if key != "experiment_observations"},
        "hypotheses": hypotheses, "evidence": evidence, "open_gaps": gaps,
        "next": next_actions, **problems}


def render_status_markdown(status: dict[str, Any]) -> str:
    def cell(value: Any) -> str:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
        return text.replace("|", "\\|").replace("\n", " ")
    lines = [f"# {status['question']}", "", "Models: " + " | ".join(
        f"{key} {row['status']} ({row['path']})" for key, row in status["models"].items()),
        "", "## Hypotheses", "", "| id | text | logic (state, confidence) | trace (support, rank, live, causal) | experiment |",
        "|---|---|---|---|---|---|"]
    for row in status["hypotheses"]:
        lines.append("| " + " | ".join(cell(row[key]) for key in ("id", "text", "logic", "trace", "experiment")) + " |")
    lines.extend(["", "## Evidence", "", "| anchor | source | lineage | used by |", "|---|---|---|---|"])
    for row in status["evidence"]:
        lines.append("| " + " | ".join(cell(row[key]) for key in ("anchor", "source", "lineage", "used_by")) + " |")
    for title, key in [("Open gaps", "open_gaps"), ("Next", "next")]:
        lines.extend(["", f"## {title}", ""])
        lines.extend("- " + cell(row) for row in status[key])
    lines.extend(["", "## Problems", ""])
    for kind in ("errors", "warnings", "info"):
        lines.extend(f"- {kind.rstrip('s')} {cell(row)}" for row in status[kind])
    return "\n".join(lines) + "\n"


def status_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="researchguard status")
    parser.add_argument("path")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        status = research_status(load_research(args.path))
    except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
        print(json.dumps({"errors": [f"research_index_invalid: {exc}"]}, ensure_ascii=False))
        return 2
    text = json.dumps(status, ensure_ascii=False, indent=2) + "\n" if args.json else render_status_markdown(status)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 1 if status["errors"] else 0
