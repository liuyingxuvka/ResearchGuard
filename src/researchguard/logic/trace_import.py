"""Turn a TraceGuard export-logicguard bundle into a starter LogicGuard model."""
from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any, Mapping

from .provenance import content_hash_for
from researchguard.ownership import handoff_logic_owned, refresh_logic_provenance


TRACE_HANDOFF_SCHEMA = "researchguard.trace.logic-handoff.v1"


def model_dict_from_trace_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle, Mapping) or bundle.get("schema") != TRACE_HANDOFF_SCHEMA:
        raise ValueError(f"expected a TraceGuard export-logicguard bundle ({TRACE_HANDOFF_SCHEMA})")
    if "hypotheses" in bundle:
        if not isinstance(bundle["hypotheses"], list) or not isinstance(bundle.get("evidence"), list):
            raise ValueError("handoff hypotheses and evidence must both be lists")
        if bundle["hypotheses"]:
            return _model_dict_from_hypotheses(bundle)
    if not bundle.get("claims"):
        raise ValueError("expected at least one handoff claim or hypothesis")
    nodes = {}
    edges = []
    for claim in bundle["claims"]:
        claim_id = str(claim["claim_id"])
        nodes[claim_id] = {
            "type": "Claim",
            "text": str(claim.get("domain_proposition") or claim.get("trace_title") or claim_id),
            "scope": str(claim.get("limitation", "")),
        }
        for value in claim.get("evidence", []):
            evidence_id = str(value)
            nodes.setdefault(evidence_id, {"type": "Evidence", "text": f"TraceGuard evidence {evidence_id} (trace {claim.get('trace_id', '')})"})
            edges.append({"source": evidence_id, "target": claim_id, "type": "supports"})
        for index, text in enumerate(claim.get("domain_boundaries", []), start=1):
            node_id = f"{claim_id}__boundary_{index}"
            nodes[node_id] = {"type": "Limitation", "text": str(text)}
            edges.append({"source": node_id, "target": claim_id, "type": "qualifies"})
    root = str(bundle["claims"][0]["claim_id"])
    return {"model": {"id": f"trace_import_{root}", "title": "Imported from a TraceGuard bundle", "root_claim": root},
            "nodes": nodes, "edges": edges}


def _model_dict_from_hypotheses(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Import signed data records only; never load or invoke a sibling route."""

    hypotheses, evidence = bundle["hypotheses"], bundle["evidence"]
    nodes: dict[str, Any] = {}
    edges = []
    evidence_by_id = {}
    for item in evidence:
        if not isinstance(item, Mapping) or any(type(item.get(key)) is not str for key in ("evidence_id", "source_id", "text", "locator")):
            raise ValueError("handoff evidence requires string evidence_id, source_id, text and locator")
        if not all(item[key].strip() for key in ("evidence_id", "source_id")):
            raise ValueError("handoff evidence id and source id must have content")
        evidence_id = item["evidence_id"]
        if evidence_id in evidence_by_id:
            raise ValueError(f"duplicate handoff evidence id: {evidence_id}")
        evidence_by_id[evidence_id] = item
    for hypothesis in hypotheses:
        if not isinstance(hypothesis, Mapping) or any(type(hypothesis.get(key)) is not str or not hypothesis[key].strip()
                                                     for key in ("hypothesis_id", "claim", "role")):
            raise ValueError("handoff hypothesis requires nonempty hypothesis_id, claim and role")
        hypothesis_id = hypothesis["hypothesis_id"]
        if hypothesis_id in nodes or hypothesis_id in evidence_by_id:
            raise ValueError(f"duplicate or conflicting handoff hypothesis id: {hypothesis_id}")
        nodes[hypothesis_id] = {"type": "Claim", "text": hypothesis["claim"]}

    def new_id(base: str) -> str:
        node_id, index = base, 1
        while node_id in nodes or node_id in evidence_by_id:
            node_id = f"{base}_{index}"
            index += 1
        return node_id

    for hypothesis in hypotheses:
        hypothesis_id = hypothesis["hypothesis_id"]
        sides = {}
        for key in ("supporting_evidence_ids", "opposing_evidence_ids", "limiting_evidence_ids"):
            ids = hypothesis.get(key)
            if not isinstance(ids, list) or any(type(item) is not str for item in ids):
                raise ValueError(f"handoff {key} must be a list of evidence ids")
            if set(ids) - evidence_by_id.keys():
                raise ValueError(f"handoff {key} references missing evidence")
            sides[key] = sorted(set(ids))
        for evidence_id in sorted(set(sides["supporting_evidence_ids"]) & set(sides["opposing_evidence_ids"])):
            logging.getLogger(__name__).warning("Handoff evidence %s both supports and opposes hypothesis %s; retaining both paths.", evidence_id, hypothesis_id)
        for key, kind in (("supporting_evidence_ids", "support"), ("opposing_evidence_ids", "oppose"), ("limiting_evidence_ids", "limit")):
            for evidence_id in sides[key]:
                item = evidence_by_id[evidence_id]
                nodes.setdefault(evidence_id, {"type": "Evidence", "text": item["text"], "provenance": [{
                    "origin_kind": "external_source",
                    **handoff_logic_owned(item, content_hash_for=content_hash_for),
                    "metadata": {"locator_text": item["locator"]},
                }]})
                target = hypothesis_id
                if kind != "support":
                    target = new_id(f"{'R' if kind == 'oppose' else 'L'}_{hypothesis_id}_{evidence_id}")
                    nodes[target] = {"type": "Rebuttal" if kind == "oppose" else "Limitation",
                                     "text": f"{'Opposing' if kind == 'oppose' else 'Limiting'} evidence for {hypothesis_id}: {item['text']}"}
                    edges.append({"source": target, "target": hypothesis_id, "type": "attacks" if kind == "oppose" else "qualifies"})
                edges.append({"source": evidence_id, "target": target, "type": "supports"})
    root = next((item["hypothesis_id"] for item in hypotheses if item["role"] == "primary"), hypotheses[0]["hypothesis_id"])
    return {"model": {"id": f"trace_import_{root}", "title": "Imported from TraceGuard hypotheses", "root_claim": root},
            "nodes": nodes, "edges": edges}


def sync_trace_bundle(bundle: Mapping[str, Any], existing: dict[str, Any]) -> tuple[dict, dict, dict, list]:
    """Refresh owned Evidence provenance while retaining authored nodes and links."""
    if not isinstance(existing, dict) or not isinstance(existing.get("nodes"), dict):
        raise ValueError("--into logic model must contain a nodes mapping")
    merged = deepcopy(existing)
    incoming = model_dict_from_trace_bundle(bundle)
    added: dict[str, list] = {"nodes": [], "edges": []}
    updated: dict[str, list] = {"nodes": [], "edges": []}
    conflicts = []
    nodes = merged["nodes"]
    remapped, blocked = {}, set()

    def provenance(row):
        records = row.get("provenance", [])
        if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
            raise ValueError("--into Evidence provenance must be a list of mappings")
        return records

    for node_id, row in incoming["nodes"].items():
        if node_id in nodes and not isinstance(nodes[node_id], dict):
            raise ValueError("--into nodes must contain record mappings")
        if row.get("type") != "Evidence":
            if node_id not in nodes:
                nodes[node_id] = row
                added["nodes"].append(node_id)
            elif nodes[node_id].get("type") != row.get("type"):
                conflicts.append({"kind": "nodes", "id": node_id})
                blocked.add(node_id)
            continue
        incoming_provenance = row.get("provenance", [])
        if not incoming_provenance:
            # Legacy claim-only bundles carry no owned source payload to refresh.
            if node_id not in nodes:
                nodes[node_id] = row
                added["nodes"].append(node_id)
            elif nodes[node_id].get("type") != "Evidence":
                conflicts.append({"kind": "nodes", "id": node_id})
                blocked.add(node_id)
            continue
        owned, = incoming_provenance
        identity = (owned.get("source_id"), owned.get("locator"))
        target = node_id
        if node_id in nodes:
            if nodes[node_id].get("type") != "Evidence":
                conflicts.append({"kind": "nodes", "id": node_id})
                blocked.add(node_id)
                continue
            records = provenance(nodes[node_id])
            source_ids = {record.get("source_id") for record in records if record.get("source_id")}
            if source_ids and identity[0] not in source_ids:
                conflicts.append({"kind": "nodes", "id": node_id})
                blocked.add(node_id)
                continue
        else:
            matches = []
            wrong_sources = []
            for candidate, current in nodes.items():
                if not isinstance(current, dict) or current.get("type") != "Evidence":
                    continue
                for record in provenance(current):
                    pair = (record.get("source_id"), record.get("locator"))
                    if pair == identity:
                        if candidate not in matches:
                            matches.append(candidate)
                    elif pair[1] == identity[1] and pair[0] not in (None, "", identity[0]):
                        if candidate not in wrong_sources:
                            wrong_sources.append(candidate)
            if len(matches) > 1:
                raise ValueError(f"ambiguous existing Evidence provenance for {node_id}: {', '.join(matches)}")
            if matches:
                target = matches[0]
            elif wrong_sources:
                conflicts.extend({"kind": "nodes", "id": candidate} for candidate in wrong_sources)
                blocked.add(node_id)
                continue
            else:
                nodes[node_id] = row
                added["nodes"].append(node_id)
                continue
        remapped[node_id] = target
        current = nodes[target]
        records = provenance(current)
        matches = [record for record in records if (record.get("source_id"), record.get("locator")) == identity]
        if not matches:
            matches = [record for record in records
                       if record.get("source_id") in (None, "", identity[0])
                       and record.get("locator") in (None, "", identity[1])]
            if len(matches) > 1:
                raise ValueError(f"ambiguous existing Evidence provenance for {node_id}")
        changed = False
        if matches:
            for record in matches:
                changed = refresh_logic_provenance(record, owned) or changed
        else:
            records.append(deepcopy(owned))
            current["provenance"] = records
            changed = True
        if changed and target not in updated["nodes"]:
            updated["nodes"].append(target)
    edges = merged.setdefault("edges", [])
    if not isinstance(edges, list):
        raise ValueError("--into edges must be a list")
    def key(row):
        return (row["source"], row["target"], row["type"])
    by_key = {key(row): row for row in edges}
    for original in incoming["edges"]:
        if original["source"] in blocked or original["target"] in blocked:
            continue
        row = {**original, "source": remapped.get(original["source"], original["source"]),
               "target": remapped.get(original["target"], original["target"])}
        identity = key(row)
        if identity not in by_key:
            edges.append(row)
            by_key[identity] = row
            added["edges"].append(list(identity))
        # Existing edge metadata and authored relations are never copy fields.
    return merged, added, updated, conflicts
