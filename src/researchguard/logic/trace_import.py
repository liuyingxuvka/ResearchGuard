"""Turn a TraceGuard export-logicguard bundle into a starter LogicGuard model."""
from __future__ import annotations

from typing import Any, Mapping


TRACE_HANDOFF_SCHEMA = "researchguard.trace.logic-handoff.v1"


def model_dict_from_trace_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle, Mapping) or bundle.get("schema") != TRACE_HANDOFF_SCHEMA or not bundle.get("claims"):
        raise ValueError(f"expected a TraceGuard export-logicguard bundle ({TRACE_HANDOFF_SCHEMA}) with at least one claim")
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
