"""The picture of one conclusion: which argument nodes, anchors and sources it rests on.

Boxes and arrows come from the folder's own models: the logic model's edges and its native
evaluation (state, confidence, blockers), the source model's anchors and sources, and the evidence
directions that research_status derives for the trace route. A provenance locator is drawn as
source support only when the source model holds that anchor for that source; otherwise the box says
it is not. The picture lists every status error and warning that names something it draws, and a
logic model that cannot be read is reported as such instead of being drawn as absent. It keeps to
the discussed claim and its two nearest steps, stops at a readable size, and lists by id everything
it leaves out.
"""
from __future__ import annotations

from collections import deque
import re
from typing import Any

from .logic.evaluator import evaluate_model as evaluate_logic
from .logic.minimal_sets import license_model_claim
from .logic.provenance import coerce_provenance
from .source.update import source_identity

# A person reads about this many boxes and arrows at once (FlowGuard design M8); the picture
# groups toward it and lists what it leaves out, it never fails for size.
MAX_BOXES = 12
MAX_ARROWS = 20
OPPOSING = {"attacks", "contradicts", "undercuts"}
DIRECTION = {"supports": "support", "depends_on": "support", "attacks": "oppose", "contradicts": "oppose",
             "undercuts": "oppose", "qualifies": "limit"}


def _short(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _route_failure(status: dict[str, Any], route: str) -> list[str]:
    """The status errors saying that the listed model of ``route`` could not be read or evaluated."""
    return [item for item in status["errors"] if item.startswith(f"model_invalid:{route}:") or item == f"model_missing:{route}"]


def support_picture(tree: Any, status: dict[str, Any], claim_id: str, *,
                    max_boxes: int = MAX_BOXES, max_arrows: int = MAX_ARROWS) -> dict[str, Any]:
    """Compute the boxes, arrows, omissions and status problems of the picture of ``claim_id``."""
    limits = {"boxes": max_boxes, "arrows": max_arrows}
    logic_failure = _route_failure(status, "logic")
    if logic_failure:
        return {"claim": claim_id, "cannot_draw": logic_failure, "boxes": [], "arrows": [], "blocked_by": [],
                "not_drawn": [], "problems": _problems(status, set()), "limits": limits}
    listed = tree.index.get("models", {})
    logic = tree.models.get("logic")
    source = tree.models.get("source")
    source_failure = _route_failure(status, "source")
    nodes = logic.nodes if logic is not None else {}
    results = evaluate_logic(logic).node_results if logic is not None else {}
    incoming: dict[str, list[Any]] = {}
    for edge in (logic.edges if logic is not None else ()):
        if edge.source in nodes and edge.target in nodes:
            incoming.setdefault(edge.target, []).append(edge)
    sources = {row.source_id: row for row in source.sources} if source is not None else {}
    anchors = {row.anchor_id: row for row in source.anchors} if source is not None else {}
    anchor_of: dict[str, tuple[str, str]] = {}
    node_of_anchor: dict[str, str] = {}
    for node_id, node in sorted(nodes.items()):
        if node.type != "Evidence":
            continue
        for record in coerce_provenance(node.provenance):
            if record.locator and record.source_id:
                anchor_of.setdefault(node_id, (record.locator, record.source_id))
                node_of_anchor.setdefault(record.locator, node_id)
    library_sources = {row.source_id for row in tree.library.list_sources()} if tree.library is not None else set()

    def anchor_line(anchor_id: str, source_id: str) -> str:
        """Whether the source model holds this anchor for this source, computed rather than taken from the locator."""
        if source_failure:
            return f"{anchor_id}: not checked, the source model failed to load"
        if source is None:
            return f"{anchor_id}: research.yaml lists no source model"
        anchor = anchors.get(anchor_id)
        if anchor is not None and anchor.source_id == source_id:
            return f"{anchor_id} · {_source_line(sources.get(source_id), source_id)}"
        if source_id in library_sources and anchor_id in tree.library.source_node_ids(source_id):
            return f"{anchor_id} · node of library source {source_id}"
        if source_id not in sources:
            return f"{anchor_id}: source {source_id} is not in the source model"
        return f"{anchor_id}: not an anchor of {source_id} in the source model"

    trace_direction = {row["anchor"]: item["direction"] for row in status["evidence"] for item in row.get("directions", ())
                       if item["route"] == "trace" and item["hypothesis"] == claim_id}
    disagreeing = {row["detail"] for row in status.get("disagreements", ())
                   if row["hypothesis"] == claim_id and row["kind"] == "anchor"}
    result = results.get(claim_id)
    blockers = set(result.blockers) if result is not None else set()

    def rank(edge):
        return (0 if edge.source in blockers else 1 if edge.type in OPPOSING else 2, edge.source)

    first = [edge.source for edge in sorted(incoming.get(claim_id, ()), key=rank)]
    first = list(dict.fromkeys(first))
    traced = [node_of_anchor.get(anchor, f"anchor:{anchor}") for anchor in sorted(trace_direction)]
    second = list(dict.fromkeys(edge.source for parent in first for edge in sorted(incoming.get(parent, ()), key=rank)))
    candidates = list(dict.fromkeys([*first, *traced, *second]))
    candidates = [item for item in candidates if item != claim_id]

    def arrows(drawn: set[str]) -> list[dict[str, Any]]:
        rows: dict[tuple[str, str], dict[str, Any]] = {}
        for target in sorted(drawn):
            for edge in incoming.get(target, ()):
                if edge.source in drawn:
                    blocking = target == claim_id and edge.source in blockers
                    rows[(edge.source, target)] = {"from": edge.source, "to": target, "relation": edge.type,
                                                   "routes": ["logic"], "style": "block" if blocking else "logic",
                                                   "label": edge.type + (" · blocks" if blocking else "")}
        for anchor, direction in sorted(trace_direction.items()):
            box = node_of_anchor.get(anchor, f"anchor:{anchor}")
            if box not in drawn:
                continue
            row = rows.get((box, claim_id))
            if row is not None and DIRECTION.get(row["relation"]) == direction and anchor not in disagreeing:
                row["routes"].append("trace")
                row["label"] += " · trace agrees"
            elif row is not None:
                row["routes"].append("trace")
                row["label"] += f" · trace says {direction} (routes disagree)"
            else:
                rows[(box, claim_id)] = {"from": box, "to": claim_id, "relation": direction, "routes": ["trace"],
                                         "style": "trace", "label": f"trace: {direction}"}
        return list(rows.values())

    drawn = {claim_id}
    left_out: list[str] = []
    for item in candidates:
        trial = drawn | {item}
        if len(trial) <= max_boxes and len(arrows(trial)) <= max_arrows:
            drawn = trial
        else:
            left_out.append(item)
    order = [claim_id, *[item for item in candidates if item in drawn]]

    def box(item: str) -> dict[str, Any]:
        if item.startswith("anchor:"):
            anchor_id = item.split(":", 1)[1]
            anchor = anchors.get(anchor_id)
            if anchor is None or source_failure:
                lines = [anchor_id, "not checked, the source model failed to load" if source_failure
                         else "not an anchor in the source model"]
            else:
                lines = [anchor_id, _short(anchor.text, 48), _source_line(sources.get(anchor.source_id), anchor.source_id)]
            return {"id": item, "kind": "anchor", "lines": lines}
        node = nodes.get(item)
        if node is None:
            return {"id": item, "kind": "claim", "lines": [item, "not in the logic route"]}
        node_result = results.get(item)
        state = f"{node_result.state} {node_result.confidence:.2f}" if node_result is not None else ""
        lines = [item if node.type in {"Claim", "Evidence"} else f"{item} ({node.type})", _short(node.text, 60 if item == claim_id else 48)]
        if node.type == "Evidence" and item in anchor_of:
            lines.append(anchor_line(*anchor_of[item]))
        elif node.type == "Evidence":
            lines.append("no anchor in the source model")
        if item == claim_id:
            lines.append(" · ".join(part for part in (state, _licence(logic, item, status)) if part))
        elif state:
            lines.append(state)
        return {"id": item, "kind": "claim" if item == claim_id else node.type.lower(), "lines": lines,
                "blocks": item in blockers}

    ancestors = _distances(incoming, claim_id)
    not_drawn = [_omission(item, incoming, claim_id, nodes) for item in left_out]
    further = sorted(item for item, distance in ancestors.items() if distance > 2)
    if further:
        not_drawn.append(f"{len(further)} argument nodes more than two steps below {claim_id}: {', '.join(further)}")
    unconnected = sorted(set(nodes) - set(ancestors) - {claim_id})
    if unconnected:
        not_drawn.append(f"{len(unconnected)} argument nodes that {claim_id} does not rest on: {', '.join(unconnected)}")
    row = next((item for item in status["hypotheses"] if item["id"] == claim_id), None)
    if row is not None:
        trace, experiment = row.get("trace"), row.get("experiment") or {}
        routes = []
        if trace:
            routes.append("trace " + ("live" if trace.get("live") else "not live"))
        if experiment.get("status") not in (None, "not_listed"):
            routes.append(f"experiment {experiment['status']}")
        if routes:
            not_drawn.append("route states shown as text, not boxes: " + "; ".join(routes))
    not_drawn.append("the timeline order of the trace route and the search plan are not drawn")
    if _route_failure(status, "trace"):
        not_drawn.append("the trace route's evidence directions: the trace model failed to load")
    if "logic" not in listed:
        not_drawn.insert(0, f"research.yaml lists no logic model, so no argument edges reach {claim_id}")
    elif claim_id not in nodes:
        not_drawn.insert(0, f"{claim_id} has no node in the logic model, so no argument edges reach it")
    boxes = [box(item) for item in order]
    named = {item.split(":", 1)[1] if item.startswith("anchor:") else item for item in order}
    named |= {part for item in order if item in anchor_of for part in anchor_of[item]}
    named |= {anchors[item.split(":", 1)[1]].source_id for item in order
              if item.startswith("anchor:") and item.split(":", 1)[1] in anchors}
    problems = _problems(status, named)
    flagged = {token for row in problems for token in _tokens(row["text"])}
    for row in boxes:
        row["problem"] = bool({row["id"], row["id"].split(":", 1)[-1]} & flagged)
    return {"claim": claim_id, "boxes": boxes, "arrows": arrows(drawn), "blocked_by": sorted(blockers),
            "not_drawn": not_drawn, "problems": problems, "limits": limits}


def _tokens(text: str) -> set[str]:
    return set(re.split(r"[\s:(),]+", text))


def _problems(status: dict[str, Any], named: set[str]) -> list[dict[str, str]]:
    """Every status error and warning that names a drawn node, anchor or source, and every failed route."""
    return [{"level": level.rstrip("s"), "text": text} for level in ("errors", "warnings") for text in status[level]
            if text.startswith(("model_invalid:", "model_missing:")) or _tokens(text) & named]


def _source_line(source: Any, source_id: str) -> str:
    if source is None:
        return f"{source_id} (not in the source model)"
    identity = source_identity(source)
    if not identity.names_document:
        return f"{source_id} names no document"
    return _short(identity.title if identity.title_names_document else identity.link, 40)


def _licence(logic: Any, claim_id: str, status: dict[str, Any]) -> str:
    root = status["verdict"].get("root_claim") or {}
    if root.get("id") == claim_id:
        return f"licence {root['wording_license']}"
    if logic is not None and claim_id in logic.nodes and logic.nodes[claim_id].type == "Claim":
        return f"licence {license_model_claim(logic, claim_id).wording_license}"
    return ""


def _distances(incoming: dict[str, list[Any]], claim_id: str) -> dict[str, int]:
    seen: dict[str, int] = {}
    queue = deque([(claim_id, 0)])
    while queue:
        item, distance = queue.popleft()
        for edge in incoming.get(item, ()):
            if edge.source != claim_id and edge.source not in seen:
                seen[edge.source] = distance + 1
                queue.append((edge.source, distance + 1))
    return seen


def _omission(item: str, incoming: dict[str, list[Any]], claim_id: str, nodes: dict[str, Any]) -> str:
    if item.startswith("anchor:"):
        return f"{item.split(':', 1)[1]} (anchor the trace route links to {claim_id}) — kept out to stay readable"
    targets = sorted({target for target, edges in incoming.items() for edge in edges if edge.source == item})
    kind = nodes[item].type if item in nodes else "node"
    return f"{item} ({kind} → {', '.join(targets) or claim_id}) — kept out to stay readable"


def _count(number: int, one: str, many: str) -> str:
    return f"{number} {one if number == 1 else many}"


def _label(lines: list[str]) -> str:
    escaped = (line.replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;") for line in lines if line)
    return "<br/>".join(escaped)


def _render_problems(picture: dict[str, Any]) -> list[str]:
    lines = ["", "**Problems in what is drawn**", ""]
    lines.extend(f"- {row['level']} {row['text']}" for row in picture["problems"])
    if not picture["problems"]:
        lines.append("- none: status reports no error or warning about anything drawn here")
    return lines


def render_picture_markdown(picture: dict[str, Any]) -> str:
    if picture.get("cannot_draw"):
        lines = [f"**What {picture['claim']} rests on: not drawn**", ""]
        lines.extend(f"- {row}" for row in picture["cannot_draw"])
        lines.extend(["", "The argument cannot be drawn while its logic model cannot be read."])
        others = [row for row in picture["problems"] if row["text"] not in picture["cannot_draw"]]
        if others:
            lines.extend(["", "**Other routes that failed**", ""])
            lines.extend(f"- {row['level']} {row['text']}" for row in others)
        return "\n".join(lines) + "\n"
    ids = {row["id"]: f"n{index}" for index, row in enumerate(picture["boxes"])}
    claim = picture["boxes"][0]
    lines = [f"**What {picture['claim']} rests on**", "",
             f"- {picture['claim']}: {claim['lines'][-1]}",
             "- blocked by: " + (", ".join(picture["blocked_by"]) or "none"), "", "```mermaid", "flowchart BT"]
    for row in picture["boxes"]:
        lines.append(f'  {ids[row["id"]]}["{_label(row["lines"])}"]')
    for row in picture["arrows"]:
        source, target, label = ids[row["from"]], ids[row["to"]], row["label"].replace('"', "#quot;")
        arrow = {"block": "==>", "trace": "-.->"}.get(row["style"], "-->")
        lines.append(f'  {source} {arrow}|"{label}"| {target}')
    lines.append("  classDef claim stroke-width:3px")
    lines.append(f"  class {ids[claim['id']]} claim")
    blocking = [ids[row["id"]] for row in picture["boxes"] if row.get("blocks")]
    if blocking:
        lines.append("  classDef blocker stroke:#b03030,stroke-width:2px")
        lines.append(f"  class {','.join(blocking)} blocker")
    flagged = [ids[row["id"]] for row in picture["boxes"] if row.get("problem")]
    if flagged:
        lines.append("  classDef problem stroke:#b03030,stroke-dasharray:4 3")
        lines.append(f"  class {','.join(flagged)} problem")
    lines.extend(["```", "",
                  f"Drawn: {_count(len(picture['boxes']), 'box', 'boxes')} and {_count(len(picture['arrows']), 'arrow', 'arrows')}, computed from the logic model, "
                  "its evaluation, the source model and the trace route's evidence directions "
                  f"(readable size {picture['limits']['boxes']} boxes, {picture['limits']['arrows']} arrows).",
                  "", "**Not drawn**", ""])
    lines.extend(f"- {row}" for row in picture["not_drawn"])
    lines.extend(_render_problems(picture))
    return "\n".join(lines) + "\n"
