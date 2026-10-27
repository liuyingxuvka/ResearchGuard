"""Read a research folder, check shared identities, and project native results."""
from __future__ import annotations

import argparse
import copy
import hashlib
import os
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from typing import Any

import yaml

from . import SUITE_ID
from .experiment.loader import load_observations, load_spec
from .experiment.engine import observe_experiments, recommend_experiments
from .logic.evaluator import evaluate_model as evaluate_logic
from .logic.loader import load_model as load_logic
from .logic.provenance import content_hash_for, validate_evidence_provenance
from .logic.minimal_sets import license_model_claim
from .logic.source_library import SourceLibrary
from .logic.validator import source_model_provenance_problems
from .source.loader import load_model as load_source
from .source.planner import plan_next_actions
from .source.stop_decision import decide_model_search_stop
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
    library: Any = None
    input_paths: list[Path] = field(default_factory=list)


class _ResearchLibrary(SourceLibrary):
    """Record only the library files that the research checker actually reads."""

    def __init__(self, root, input_paths):
        super().__init__(root)
        self.input_paths = input_paths

    def list_sources(self):
        result = super().list_sources()
        if self.source_index_path.is_file():
            self.input_paths.append(self.source_index_path)
        return result

    def source_node_ids(self, source_id):
        result = super().source_node_ids(source_id)
        path = self.source_model_path(source_id)
        if path.is_file():
            self.input_paths.append(path)
        return result


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
    if "library" in data and (not isinstance(data["library"], str) or not data["library"].strip()):
        raise ValueError("library must be a nonempty path")
    if "search" in data:
        search = data["search"]
        if not isinstance(search, dict) or set(search) - {"budget", "scope_sufficient"}:
            raise ValueError("search must contain budget and optional scope_sufficient")
        budget = search.get("budget")
        if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not math.isfinite(budget) or budget < 0:
            raise ValueError("search.budget must be a finite nonnegative number")
        if not isinstance(search.get("scope_sufficient", False), bool):
            raise ValueError("search.scope_sufficient must be a boolean")
    rows = data.get("ablations", [])
    if not isinstance(rows, list):
        raise ValueError("ablations must be a list")
    for row in rows:
        if not isinstance(row, dict) or any(not isinstance(row.get(key), str) or not row[key].strip() for key in ("id", "hypothesis")):
            raise ValueError("each ablation needs id and hypothesis")
        if row.get("expect") not in {"weaken", "eliminate"}:
            raise ValueError("ablation.expect must be weaken or eliminate")
        if not isinstance(row.get("remove_anchors"), list) or not row["remove_anchors"] or any(not isinstance(item, str) or not item for item in row["remove_anchors"]):
            raise ValueError("ablation.remove_anchors must contain nonempty anchor ids")
    return data


def load_research(path: str | Path) -> ResearchTree:
    index_path = Path(path)
    if index_path.is_dir():
        index_path /= "research.yaml"
    data = _validate_index(yaml.safe_load(index_path.read_text(encoding="utf-8")))
    tree = ResearchTree(index_path, data, input_paths=[index_path])
    if "library" in data:
        library_path = index_path.parent / data["library"]
        library = _ResearchLibrary(library_path, tree.input_paths)
        if library.source_index_path.is_file():
            tree.library = library
        else:
            tree.errors.append(f"library_missing:{data['library']}")
    loaders = {"source": load_source, "trace": load_trace, "logic": load_logic, "experiment": load_spec}
    for route, loader in loaders.items():
        if route not in data.get("models", {}):
            continue
        model_path = index_path.parent / data["models"][route]
        if not model_path.is_file():
            tree.errors.append(f"model_missing:{route}")
            continue
        tree.input_paths.append(model_path)
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
        tree.input_paths.append(obs_path)
        try:
            observations.extend(load_observations(obs_path))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            tree.errors.append(f"model_invalid:experiment_observations:{name}: {exc}")
    tree.observations = tuple(observations)
    return tree


def check_research_tree(index: dict[str, Any], models: dict[str, Any], observations: tuple[Any, ...] = (), *, source_library=None) -> dict[str, list[str]]:
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
        errors.extend(f"unknown_hypothesis:source:{gap.gap_id}:{item}" for gap in source.gaps
                      for item in gap.hypothesis_ids if item not in ids)
        source_ids = {row.source_id for row in source.sources}
        anchors = {row.anchor_id: row.source_id for row in source.anchors}
        if trace is not None:
            errors.extend(f"dangling_source:trace:{row.source_id}" for row in trace.sources if row.source_id not in source_ids)
            errors.extend(f"dangling_anchor:trace:{row.evidence_id}" for row in trace.evidence
                          if anchors.get(row.evidence_id) != row.source_id)
        if logic is not None:
            errors.extend(source_model_provenance_problems(logic, to_plain(source), source_library=source_library))
        for row in observations:
            if row.evidence_id not in anchors or anchors.get(row.evidence_id) != row.source_ref:
                errors.append(f"dangling_anchor:experiment:{row.evidence_id}")
            if row.source_ref not in source_ids:
                errors.append(f"dangling_source:experiment:{row.source_ref}")
    from .ownership import copied_content_problems
    errors.extend(copied_content_problems(models, content_hash_for=content_hash_for))
    return {"errors": sorted(set(errors)), "warnings": sorted(set(warnings)), "info": info}


LOGIC_DIRECTIONS = {"supports": "support", "attacks": "oppose", "contradicts": "oppose", "undercuts": "oppose", "qualifies": "limit"}


def evidence_directions(models, hypothesis_ids=None):
    """Direct evidence directions per route: one row {anchor, route, hypothesis, direction, node}.

    Trace uses link polarity and storyline evidence lists; logic uses the direct edges of the
    Evidence node whose provenance names the anchor, only when the edge targets a hypothesis
    (any target when hypothesis_ids is None). Indirect argument chains carry no direction.
    """
    trace, logic = models.get("trace"), models.get("logic")
    rows = set()
    if trace:
        for link in trace.hypothesis_evidence_links:
            if link.polarity in {"support", "oppose", "limit"}:
                rows.add((link.evidence_id, "trace", link.hypothesis_id, link.polarity, None))
        for hypothesis in trace.storyline_hypotheses:
            rows.update((anchor, "trace", hypothesis.hypothesis_id, "support", None) for anchor in hypothesis.evidence_ids)
            rows.update((anchor, "trace", hypothesis.hypothesis_id, "oppose", None) for anchor in hypothesis.contradicting_evidence_ids)
    if logic:
        for edge in logic.edges:
            node = logic.nodes.get(edge.source)
            direction = LOGIC_DIRECTIONS.get(edge.type)
            if node is None or node.type != "Evidence" or not direction or (hypothesis_ids is not None and edge.target not in hypothesis_ids):
                continue
            rows.update((provenance.locator, "logic", edge.target, direction, node.id)
                        for provenance in validate_evidence_provenance(node.id, node.provenance))
    return [{"anchor": anchor, "route": route, "hypothesis": hypothesis, "direction": direction, "node": node}
            for anchor, route, hypothesis, direction, node in sorted(rows, key=lambda row: (row[0], row[1], row[2], row[3], row[4] or ""))]


def route_disagreements(models, hypotheses):
    """Compare direct shared-anchor evidence and explicit native conclusions."""
    directions = {"trace": {}, "logic": {}}
    for row in evidence_directions(models):
        if row["direction"] in {"support", "oppose"}:
            directions[row["route"]].setdefault((row["hypothesis"], row["anchor"]), set()).add(row["direction"])
    result = []
    for key in sorted(directions["trace"].keys() & directions["logic"].keys()):
        left, right = directions["trace"][key], directions["logic"][key]
        if (left, right) in [({"support"}, {"oppose"}), ({"oppose"}, {"support"})]:
            result.append({"hypothesis": key[0], "kind": "anchor", "detail": key[1]})
    for row in hypotheses:
        values, accepted, rejected = {}, [], []
        for route, key, accept, reject in (("logic", "state", "IN", "OUT"), ("trace", "live", True, False), ("experiment", "status", None, "eliminated")):
            payload = row.get(route)
            if payload is None or key not in payload:
                continue
            value = payload[key]
            values[route] = value
            if accept is not None and value == accept:
                accepted.append(route)
            if value == reject:
                rejected.append(route)
        if accepted and rejected:
            result.append({"hypothesis": row["id"], "kind": "status", "detail": ",".join(f"{key}={values[key]}" for key in sorted(values))})
    return result


def apply_ablations(index, models, results):
    """Use the native evaluators on disposable, anchor-ablated route models.

    The trace route is judged by TraceGuard's own expected-sensitivity check: a trace-declared
    ablation uses its declared sensitivity, a question-level row a synthetic one with threshold 0.
    """
    rows = [dict(row) for row in index.get("ablations", [])]
    trace = models.get("trace")
    if trace:
        for ablation in trace.evidence_ablations:
            if not ablation.remove_evidence_ids or ablation.remove_event_ids:
                continue
            for expectation in trace.expected_sensitivities:
                if expectation.perturbation_id == ablation.ablation_id and expectation.target_kind == "hypothesis" and expectation.expected_direction == "decrease":
                    rows.append({"id": ablation.ablation_id, "hypothesis": expectation.target_id,
                                 "remove_anchors": list(ablation.remove_evidence_ids), "expect": "weaken",
                                 "native_ablation": ablation.ablation_id, "sensitivity": expectation.sensitivity_id})
                    break
    errors, warnings, outcomes, seen = [], [], [], set()
    source = models.get("source")
    anchors = {row.anchor_id for row in source.anchors} if source else set()
    hypothesis_ids = {row["id"] for row in index["hypotheses"]}
    logic = models.get("logic")
    for row in rows:
        name, hypothesis = row["id"], row["hypothesis"]
        if name in seen:
            errors.append(f"duplicate_ablation:{name}")
            continue
        seen.add(name)
        missing = set(row["remove_anchors"]) - anchors
        errors.extend(f"unknown_anchor:ablation:{name}:{anchor}" for anchor in sorted(missing))
        if hypothesis not in hypothesis_ids:
            errors.append(f"unknown_hypothesis:ablation:{name}:{hypothesis}")
        if missing or hypothesis not in hypothesis_ids:
            continue
        removed, caught, effects = set(row["remove_anchors"]), [], []
        if logic and "logic" in results:
            candidate = copy.deepcopy(logic)
            deleted = {node.id for node in candidate.nodes.values() if node.type == "Evidence" and any(p.locator in removed for p in validate_evidence_provenance(node.id, node.provenance))}
            if deleted:
                candidate.nodes = {key: node for key, node in candidate.nodes.items() if key not in deleted}
                candidate.edges = [edge for edge in candidate.edges if edge.source not in deleted and edge.target not in deleted]
                after_results = evaluate_logic(candidate).node_results
                before = results["logic"].node_results.get(hypothesis)
                after = after_results.get(hypothesis)
                if before and after and ((row["expect"] == "eliminate" and after.state == "OUT") or (row["expect"] == "weaken" and (after.confidence < before.confidence or before.state == "IN" and after.state != "IN"))):
                    caught.append("logic")
                for other in sorted(hypothesis_ids - {hypothesis}):
                    old, new = results["logic"].node_results.get(other), after_results.get(other)
                    if old and new and old.state != new.state:
                        effects.append({"hypothesis": other, "route": "logic", "field": "state", "before": old.state, "after": new.state})
        if trace and "trace" in results and any(item.evidence_id in removed for item in trace.evidence):
            moved, trace_effects = _trace_ablation(trace, results["trace"], row, hypothesis_ids)
            if moved:
                caught.append("trace")
            effects.extend(trace_effects)
        outcome = {"id": name, "hypothesis": hypothesis, "expect": row["expect"], "caught_by": caught}
        if effects:
            outcome["effects"] = sorted(effects, key=lambda item: (item["hypothesis"], item["route"]))
        outcomes.append(outcome)
        if not caught:
            warnings.append(f"ablation_not_caught:{row['id']}")
    return outcomes, errors, warnings


def _trace_ablation(trace, baseline, row, hypothesis_ids):
    """Run one ablation through TraceGuard's perturbation and expected-sensitivity check, in memory only."""
    from dataclasses import replace
    from .trace.schema import EvidenceAblation, ExpectedSensitivity
    from .trace.storyline_depth import PerturbationPlanItem, expected_sensitivity_matches, run_single_perturbation
    hypothesis = row["hypothesis"]
    if row.get("native_ablation"):
        model, ablation_id, sensitivity_id = trace, row["native_ablation"], row["sensitivity"]
    else:
        ablation_id, sensitivity_id = f"research-ablation:{row['id']}", f"research-sensitivity:{row['id']}"
        model = replace(trace,
            evidence_ablations=(*trace.evidence_ablations, EvidenceAblation(ablation_id, hypothesis, None, "Research-folder anchor ablation", sorted(set(row["remove_anchors"])))),
            expected_sensitivities=(*trace.expected_sensitivities, ExpectedSensitivity(sensitivity_id, ablation_id, "hypothesis", hypothesis, "decrease", 0.0)))
    plan = PerturbationPlanItem(perturbation_id=f"expected_sensitivity:{sensitivity_id}", kind="expected_sensitivity",
                                target_hypothesis_id=hypothesis, declared_perturbation_id=ablation_id, expected_sensitivity_id=sensitivity_id)
    effect, _, perturbed = run_single_perturbation(model, baseline, plan)
    before = {item.hypothesis_id: item for item in baseline.inference.hypothesis_projections}
    after = {item.hypothesis_id: item for item in perturbed.inference.hypothesis_projections}
    if row["expect"] == "eliminate":
        moved = hypothesis in after and not after[hypothesis].live
    else:
        moved = expected_sensitivity_matches(model, effect)
    effects = [{"hypothesis": other, "route": "trace", "field": "live", "before": before[other].live, "after": after[other].live}
               for other in sorted(hypothesis_ids - {hypothesis}) if other in before and other in after and before[other].live != after[other].live]
    return moved, effects


def verdict_for_writers(tree, hypotheses, disagreements, errors):
    search = "not_run"
    if "source" in tree.models and "search" in tree.index:
        configuration = tree.index["search"]
        _, decision = decide_model_search_stop(tree.models["source"], remaining_budget=configuration["budget"], evidence_sufficient_for_scope=configuration.get("scope_sufficient", False))
        search = decision.status
    root = None
    if "logic" in tree.models and tree.index.get("root_claim"):
        claim = tree.index["root_claim"]
        if claim in tree.models["logic"].nodes:
            license = license_model_claim(tree.models["logic"], claim)
            root = {"id": claim, "wording_license": license.wording_license, "reason": license.reason}
    live = [row["id"] for row in hypotheses if not ((row.get("logic") or {}).get("state") == "OUT" or (row.get("trace") or {}).get("live") is False or (row.get("experiment") or {}).get("status") == "eliminated")]
    return {"search": search, "root_claim": root, "live_hypotheses": live, "contested": bool(disagreements), "errors": len(errors)}


def research_status(tree: ResearchTree) -> dict[str, Any]:
    problems = check_research_tree(tree.index, tree.models, tree.observations, source_library=tree.library)
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
    directed: dict[str, list[dict[str, Any]]] = {}
    for row in evidence_directions(tree.models, [item["id"] for item in tree.index["hypotheses"]]):
        directed.setdefault(row.pop("anchor"), []).append(row)
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
                             "locator": anchor.locator,
                             "summary": anchor.normalized_summary or anchor.text[:200],
                             "boundary": sources[anchor.source_id].cannot_support_structural_use if anchor.source_id in sources else "",
                             "used_by": sorted(set(used_by)),
                             "directions": sorted(directed.get(anchor.anchor_id, []), key=lambda row: (row["route"], row["hypothesis"], row["direction"]))})
    gaps: list[dict[str, Any]] = []
    next_actions: list[dict[str, Any]] = []
    plan = results.get("source")
    if plan:
        named = {row.gap_id: list(row.hypothesis_ids) for row in tree.models["source"].gaps}
        next_actions.extend({"route": "search", "id": row.action_id, "query": row.query,
                             "hypotheses": named.get(row.target_gap_id, [])} for row in plan.selected_actions)
        gaps.extend({"route": "source", "id": row.gap_id, "blocking": row.blocking,
                     "next": [action.action_id for action in plan.selected_actions if action.target_gap_id == row.gap_id],
                     "hypotheses": named.get(row.gap_id, [])}
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
    disagreements = route_disagreements(tree.models, hypotheses)
    problems["warnings"].extend(f"route_disagreement:{row['hypothesis']}:{row['kind']}:{row['detail']}" for row in disagreements)
    try:
        ablations, errors, warnings = apply_ablations(tree.index, tree.models, results)
        problems["errors"].extend(errors)
        problems["warnings"].extend(warnings)
    except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
        ablations = []
        problems["errors"].append(f"model_invalid:ablation: {exc}")
    try:
        verdict = verdict_for_writers(tree, hypotheses, disagreements, problems["errors"])
    except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
        problems["errors"].append(f"model_invalid:verdict: {exc}")
        verdict = {"search": "not_run", "root_claim": None, "live_hypotheses": [], "contested": bool(disagreements), "errors": len(problems["errors"])}
    input_digests = []
    for path in set(tree.input_paths):
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
        input_digests.append({"path": Path(os.path.relpath(path, tree.path.parent)).as_posix(), "sha256": digest})
    input_digests.sort(key=lambda row: row['path'])
    return {"input_digests": input_digests, "suite": SUITE_ID, "question": tree.index["question"], "verdict": verdict,
        "ablations": ablations, "disagreements": disagreements, "models": {
        key: {"path": value, "status": "ok" if key in results else "invalid"}
        for key, value in tree.index.get("models", {}).items() if key != "experiment_observations"},
        "hypotheses": hypotheses, "evidence": evidence, "open_gaps": gaps,
        "next": next_actions, **problems}


def _named(row: dict[str, Any]) -> str:
    return f" ({', '.join(row['hypotheses'])})" if row.get("hypotheses") else ""


def render_status_markdown(status: dict[str, Any]) -> str:
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    verdict = status["verdict"]
    root = verdict["root_claim"]
    lines = [f"# {status['question']}", "", "## Verdict", "",
             f"- search: {verdict['search']}",
             "- root_claim: " + (f"{root['id']}: {root['wording_license']} — {root['reason']}" if root else "not_run"),
             "- live_hypotheses: " + (", ".join(verdict["live_hypotheses"]) or "none"),
             f"- contested: {str(verdict['contested']).lower()}", f"- errors: {verdict['errors']}", "",
             "Models: " + " | ".join(f"{key} {row['status']} ({row['path']})" for key, row in status["models"].items()),
             "", "## Hypotheses", "", "| id | text | logic | trace | experiment |", "|---|---|---|---|---|"]
    for row in status["hypotheses"]:
        logic, trace, experiment = row["logic"], row["trace"], row["experiment"]
        logic_text = f"{logic['state']} {logic['confidence']:.2f}" if logic else "not listed"
        trace_text = (f"rank {trace['rank']}, support {trace['support']:.2f}, " + ("live" if trace["live"] else "not live") + (f", causal {trace['causal_support']:.2f}" if trace.get("causal_support") is not None else "")) if trace else "not listed"
        lines.append("| " + " | ".join(cell(item) for item in (row["id"], row["text"], logic_text, trace_text, experiment.get("status", "not_run"))) + " |")
    lines.extend(["", "## Evidence", "", "| anchor | source | lineage | used by |", "|---|---|---|---|"])
    for row in status["evidence"]:
        lines.append("| " + " | ".join(cell(item) for item in (row["anchor"], row["source"], row["lineage"], ", ".join(_used_by(row)))) + " |")
    lines.extend(["", "## Open gaps", ""])
    for row in status["open_gaps"]:
        if row["route"] == "source":
            text = f"source gap {row['id']} ({'blocking' if row['blocking'] else 'optional'}) → next: {', '.join(row['next']) or 'none'}" + _named(row)
        elif row["route"] == "trace depth":
            text = f"trace depth: {row['closure_status']}, {len(row['unresolved_gaps'])} unresolved gaps"
        else:
            text = f"logic: {row['root_claim']} blocked by {', '.join(row['blocked_by']) or 'none'}"
        lines.append("- " + cell(text))
    _none(lines, status["open_gaps"])
    lines.extend(["", "## Next", ""])
    for row in status["next"]:
        if row["route"] == "search":
            gaps = [gap['id'] for gap in status['open_gaps'] if gap['route'] == 'source' and row['id'] in gap['next']]
            text = f"search {row['id']} -> {', '.join(gaps) or 'none'}" + _named(row) + f": {row['query']}"
        else:
            text = f"experiment: {row.get('status')}; next: {', '.join(row['ids']) or 'none'}"
        lines.append("- " + cell(text))
    _none(lines, status["next"])
    lines.extend(["", "## Ablations", ""])
    for row in status["ablations"]:
        effects = "; effects: " + ", ".join(f"{item['hypothesis']} {item['route']} {item['field']} {str(item['before']).lower()} → {str(item['after']).lower()}" for item in row["effects"]) if row.get("effects") else ""
        lines.append(f"- {cell(row['id'])}: {cell(row['hypothesis'])} {row['expect']}; caught by {', '.join(row['caught_by']) or 'none'}{cell(effects)}")
    _none(lines, status["ablations"])
    lines.extend(["", "## Disagreements", ""])
    lines.extend(f"- {cell(row['hypothesis'])}: {row['kind']} {cell(row['detail'])}" for row in status["disagreements"])
    _none(lines, status["disagreements"])
    lines.extend(["", "## Problems", ""])
    for kind in ("errors", "warnings", "info"):
        lines.extend(f"- {kind.rstrip('s')} {cell(row)}" for row in status[kind])
    _none(lines, status["errors"] + status["warnings"] + status["info"])
    return "\n".join(lines) + "\n"


def _none(lines: list[str], rows: list[Any]) -> None:
    if not rows:
        lines.append("- none")


def _used_by(row: dict[str, Any]) -> list[str]:
    """Page form of an evidence row: route:hypothesis:direction, or logic:<node> when no direct hypothesis edge."""
    directed_nodes = {item["node"] for item in row.get("directions", ()) if item["route"] == "logic"}
    text = [f"{item['route']}:{item['hypothesis']}:{item['direction']}" for item in row.get("directions", ())]
    text.extend(item for item in row["used_by"] if item.startswith("logic:") and item.split(":", 1)[1] not in directed_nodes)
    text.extend(item for item in row["used_by"] if item.startswith("trace:") and item not in text)
    return sorted(set(text))


def hypothesis_view(status: dict[str, Any], hypothesis_id: str, experiment: Any = None) -> dict[str, Any]:
    """One hypothesis read back from an already computed status; no route is run again."""
    row = next((item for item in status["hypotheses"] if item["id"] == hypothesis_id), None)
    if row is None:
        raise KeyError(hypothesis_id)
    evidence = {"support": [], "oppose": [], "limit": []}
    for item in status["evidence"]:
        for direction in item.get("directions", ()):
            if direction["hypothesis"] == hypothesis_id:
                evidence[direction["direction"]].append({"anchor": item["anchor"], "route": direction["route"]})
    predicted = None
    if experiment is not None:
        predicted = {experiment_id for prediction in experiment.hypothesis_predictions if prediction.hypothesis_id == hypothesis_id
                     for experiment_id in prediction.outcomes_by_experiment}
    next_rows = [item for item in status["next"] if item["route"] == "search" and hypothesis_id in item.get("hypotheses", ())]
    for item in status["next"]:
        if item["route"] == "experiment":
            ids = [value for value in item["ids"] if predicted is None or value in predicted]
            if ids:
                next_rows.append({**item, "ids": ids})
    return {"id": hypothesis_id, "text": row["text"],
            "routes": {"logic": row["logic"], "trace": row["trace"], "experiment": row["experiment"]},
            "evidence": evidence,
            "ablations": [item for item in status["ablations"] if item["hypothesis"] == hypothesis_id
                          or any(effect["hypothesis"] == hypothesis_id for effect in item.get("effects", ()))],
            "disagreements": [item for item in status["disagreements"] if item["hypothesis"] == hypothesis_id],
            "open_gaps": [item for item in status["open_gaps"] if item["route"] == "source" and hypothesis_id in item.get("hypotheses", ())],
            "next": next_rows}


def render_hypothesis_view(view: dict[str, Any]) -> str:
    routes = view["routes"]
    logic, trace, experiment = routes["logic"], routes["trace"], routes["experiment"]
    lines = [f"# {view['id']}: {view['text']}", "", "## Routes", "",
             "- logic: " + (f"{logic['state']}, confidence {logic['confidence']:.2f}" if logic else "not in logic"),
             "- trace: " + (f"rank {trace['rank']}, support {trace['support']:.2f}, " + ("live" if trace["live"] else "not live") if trace else "not in trace"),
             "- experiment: " + (experiment or {}).get("status", "not_listed"), "", "## Evidence", ""]
    for direction in ("support", "oppose", "limit"):
        rows = view["evidence"][direction]
        anchors = {}
        for row in rows:
            anchors.setdefault(row['anchor'], set()).add(row['route'])
        lines.append(f"- {direction}:")
        lines.extend(f"  - {anchor} ({', '.join(sorted(routes))})" for anchor, routes in anchors.items())
        if not anchors:
            lines.append("  - none")
    lines.extend(["", "## Ablations", ""])
    for row in view["ablations"]:
        effects = [f"{item['hypothesis']} {item['route']} {item['field']} {str(item['before']).lower()} → {str(item['after']).lower()}" for item in row.get("effects", ()) if item['hypothesis'] == view['id']]
        if row['hypothesis'] != view['id']:
            if effects:
                lines.append(f"- {row['id']} (targets {row['hypothesis']}): effects " + ", ".join(effects))
        else:
            lines.append(f"- {row['id']}: {row['hypothesis']} {row['expect']}; caught by {', '.join(row['caught_by']) or 'none'}" + ("; effects: " + ", ".join(effects) if effects else ""))
    _none(lines, view["ablations"])
    lines.extend(["", "## Disagreements", ""])
    lines.extend(f"- {row['kind']} {row['detail']}" for row in view["disagreements"])
    _none(lines, view["disagreements"])
    lines.extend(["", "## Open gaps", ""])
    lines.extend(f"- source gap {row['id']} ({'blocking' if row['blocking'] else 'optional'}) → next: {', '.join(row['next']) or 'none'}" for row in view["open_gaps"])
    _none(lines, view["open_gaps"])
    lines.extend(["", "## Next", ""])
    lines.extend(f"- search {row['id']}" if row["route"] == "search" else f"- experiment: {', '.join(row['ids'])}" for row in view["next"])
    _none(lines, view["next"])
    return "\n".join(lines) + "\n"


HYPOTHESIS_FIELDS = ("state", "confidence", "rank", "support", "live", "status")
VERDICT_KEYS = ("search", "root_claim.id", "root_claim.wording_license", "root_claim.reason", "live_hypotheses", "contested", "errors")


def _verdict_value(verdict, key):
    if key.startswith("root_claim."):
        return (verdict.get("root_claim") or {}).get(key.split(".", 1)[1])
    return verdict.get(key)


def compare_research_status(current, candidate):
    """Compare what readers and writers see: hypothesis fields, verdict keys, ablations, disagreements, anchors and problems."""
    changes = []
    old = {row["id"]: row for row in current["hypotheses"]}
    new = {row["id"]: row for row in candidate["hypotheses"]}
    projected = lambda row: {route: {key: value for key, value in (row.get(route) or {}).items() if key in HYPOTHESIS_FIELDS} for route in ("logic", "trace", "experiment")}
    for identifier in dict.fromkeys((*old, *new)):
        before, after = old.get(identifier), new.get(identifier)
        if before is None or after is None:
            changes.append({"kind": "hypothesis", "id": identifier, "before": projected(before) if before else None, "after": projected(after) if after else None})
            continue
        left, right = projected(before), projected(after)
        changed_left, changed_right = {}, {}
        for route in left:
            for key in dict.fromkeys((*left[route], *right[route])):
                if left[route].get(key) != right[route].get(key):
                    changed_left.setdefault(route, {})[key] = left[route].get(key)
                    changed_right.setdefault(route, {})[key] = right[route].get(key)
        if changed_left:
            changes.append({"kind": "hypothesis", "id": identifier, "before": changed_left, "after": changed_right})
    for key in VERDICT_KEYS:
        before, after = _verdict_value(current["verdict"], key), _verdict_value(candidate["verdict"], key)
        if before != after:
            changes.append({"kind": "verdict", "id": key, "before": before, "after": after})
    old_ablations = {row["id"]: row for row in current.get("ablations", [])}
    new_ablations = {row["id"]: row for row in candidate.get("ablations", [])}
    for identifier in dict.fromkeys((*old_ablations, *new_ablations)):
        before, after = old_ablations.get(identifier), new_ablations.get(identifier)
        if before is None or after is None:
            changes.append({"kind": "ablation", "id": identifier, "change": "added" if before is None else "removed"})
            continue
        shown = lambda row: {key: row.get(key, []) for key in ("caught_by", "effects")}
        if shown(before) != shown(after):
            left, right = shown(before), shown(after)
            changes.append({"kind": "ablation", "id": identifier,
                            "before": {key: value for key, value in left.items() if value != right[key]},
                            "after": {key: value for key, value in right.items() if value != left[key]}})
    disagreement = lambda rows: {f"{row['hypothesis']}:{row['kind']}:{row['detail']}" for row in rows}
    for key, values in (("evidence", lambda status: {row["anchor"] for row in status["evidence"]}),
                        ("disagreement", lambda status: disagreement(status.get("disagreements", []))),
                        ("errors", lambda status: set(status["errors"])), ("warnings", lambda status: set(status["warnings"]))):
        left, right = values(current), values(candidate)
        for value in sorted(left - right):
            changes.append({"kind": key, "id": value, "change": "removed"})
        for value in sorted(right - left):
            changes.append({"kind": key, "id": value, "change": "added"})
    return {"current": current, "candidate": candidate, "changes": changes}


def _shown(value):
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return "none"
    if isinstance(value, list):
        return "[" + ", ".join(_shown(item) if not isinstance(item, str) else item for item in value) + "]"
    return str(value)


def render_comparison(comparison):
    lines = ["## Current and candidate", ""]
    for row in comparison["changes"]:
        if row["kind"] == "hypothesis" and (row["before"] is None or row["after"] is None):
            lines.append(f"- hypothesis {'added' if row['before'] is None else 'removed'}: {row['id']}")
        elif row["kind"] == "hypothesis":
            for route, fields in row["before"].items():
                for key, before in fields.items():
                    lines.append(f"- {row['id']}: {route} {key} {_shown(before)} → {_shown(row['after'][route][key])}")
        elif row["kind"] == "verdict":
            lines.append(f"- verdict {row['id']}: {_shown(row['before'])} → {_shown(row['after'])}")
        elif "change" in row:
            lines.append(f"- {row['kind']} {row['change']}: {row['id']}")
        else:
            for key, before in row["before"].items():
                lines.append(f"- {row['kind']} {row['id']}: {key} {_shown(before)} → {_shown(row['after'][key])}")
    if not comparison["changes"]:
        lines.append("no changes")
    return "\n".join(lines) + "\n"


def status_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="researchguard status")
    parser.add_argument("path")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--hypothesis")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.hypothesis and args.candidate:
        print(json.dumps({"errors": ["status_options_conflict: --hypothesis cannot be combined with --candidate"]}, ensure_ascii=False))
        return 2
    try:
        tree = load_research(args.path)
        status = research_status(tree)
        if args.candidate:
            status = compare_research_status(status, research_status(load_research(args.candidate)))
    except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
        print(json.dumps({"errors": [f"research_index_invalid: {exc}; create research.yaml first (researchguard skill, references/research-tree.md, \"Start a question\")"]}, ensure_ascii=False))
        return 2
    view = None
    if args.hypothesis:
        if args.hypothesis not in {row["id"] for row in tree.index["hypotheses"]}:
            print(json.dumps({"errors": [f"unknown_hypothesis:{args.hypothesis}"]}, ensure_ascii=False))
            return 2
        view = hypothesis_view(status, args.hypothesis, tree.models.get("experiment"))
    if args.json:
        text = json.dumps(view if view is not None else status, ensure_ascii=False, indent=2) + "\n"
    else:
        text = render_hypothesis_view(view) if view is not None else render_comparison(status) if args.candidate else render_status_markdown(status)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 1 if (status["candidate"] if args.candidate else status)["errors"] else 0
