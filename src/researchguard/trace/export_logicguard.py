"""TraceGuard to LogicGuard export.

The export is a versioned, immutable handoff. Domain fields come from the
validated TraceGuard projection; generic solver boundaries stay in the audit
envelope and are never presented as object-level limitations.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

from .evaluator import EvaluationResult
from .loader import dump_yaml


LOGICGUARD_HANDOFF_SCHEMA = "researchguard.trace.logic-handoff.v1"
LOGICGUARD_HANDOFF_EXPORT_VERSION = "1"


def _as_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        payload = value.to_dict()
    elif isinstance(value, Mapping):
        payload = value
    else:
        return {}
    return copy.deepcopy(dict(payload)) if isinstance(payload, Mapping) else {}


def _stable_unique(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    output: list[str] = []
    iterable = sorted(values) if isinstance(values, set) else values
    for value in iterable:
        text = str(value).strip()
        if text and text not in output:
            output.append(text)
    return output


def _receipt_identity(result: EvaluationResult) -> dict[str, Any]:
    receipt = getattr(result, "inference_receipt", None)
    payload = _as_dict(receipt)
    if not payload:
        return {
            "receipt_id": "",
            "model_fingerprint": "",
            "problem_fingerprint": "",
            "solution_fingerprint": "",
            "schema_id": "",
        }
    keys = (
        "receipt_id",
        "model_fingerprint",
        "problem_fingerprint",
        "solution_fingerprint",
        "schema_id",
        "policy_id",
        "factor_set_id",
        "solver_id",
        "solver_backend",
        "solver_backend_version",
    )
    return {key: copy.deepcopy(payload.get(key, "")) for key in keys}


def _domain_gap_list(trace: Any, audit_context: Mapping[str, Any]) -> list[str]:
    gaps: list[str] = []
    gaps.extend(_stable_unique(getattr(trace, "domain_gaps", ())))
    gaps.extend(_stable_unique(audit_context.get("domain_gaps", ())))
    if not str(getattr(trace, "domain_proposition", "") or "").strip():
        gaps.append("missing_domain_proposition")
    if not getattr(trace, "domain_mechanism_refs", ()):
        gaps.append("missing_domain_mechanism")
    return _stable_unique(gaps)


def logicguard_bundle(result: EvaluationResult) -> dict[str, object]:
    receipt_payload = _as_dict(getattr(result, "inference_receipt", None))
    receipt_identity = _receipt_identity(result)
    claims: list[dict[str, Any]] = []
    for trace in getattr(result, "traces", ()):
        original_context = _as_dict(getattr(trace, "audit_context", {}))
        domain_gaps = _domain_gap_list(trace, original_context)
        audit_context = copy.deepcopy(original_context)
        audit_context.update(
            {
                "validation_status": getattr(trace, "validation_status", ""),
                "current_stage": getattr(trace, "current_stage", ""),
                "safe_wording": getattr(trace, "safe_wording", ""),
                "unsafe_wording_avoided": getattr(trace, "unsafe_wording_avoided", ""),
                # Generic solver language belongs to this audit envelope.
                "claim_boundary": getattr(trace, "claim_boundary", ""),
                "tool_template": "TraceGuard links source-backed evidence to events and a trace candidate through soft rules and hard gates.",
                "native_inference_receipt_id": receipt_identity.get("receipt_id", ""),
                "source_model_fingerprint": receipt_identity.get("model_fingerprint", ""),
                "domain_gaps": domain_gaps,
            }
        )
        domain_boundaries = _stable_unique(getattr(trace, "domain_boundaries", ()))
        claims.append(
            {
                "claim_id": f"claim_{trace.trace_id}",
                "trace_id": trace.trace_id,
                "trace_title": trace.title,
                "trace_type": trace.trace_type,
                "domain_proposition": trace.domain_proposition,
                "domain_candidate_propositions": _stable_unique(getattr(trace, "domain_candidate_propositions", ())),
                "evidence": list(trace.evidence_ids),
                "domain_mechanism_refs": list(trace.domain_mechanism_refs),
                "domain_assumption_refs": list(trace.domain_assumption_refs),
                "object_scope": list(trace.object_scope),
                "material_alternatives": list(trace.material_alternatives),
                "domain_boundaries": domain_boundaries,
                # Kept for existing typed consumers, now strictly domain-only.
                "limitation": "; ".join(domain_boundaries),
                "native_causal_license": getattr(trace, "native_causal_license", "not_licensed"),
                "domain_gaps": domain_gaps,
                "source_model_fingerprint": receipt_identity.get("model_fingerprint", ""),
                "native_inference_receipt_id": receipt_identity.get("receipt_id", ""),
                "audit_context": audit_context,
                "handoff_id": f"lead_{trace.trace_id}",
                "structure_unit_id": trace.structure_unit_id,
                "source_unit_id": trace.source_unit_id,
                "destination_unit_id": trace.destination_unit_id,
                "trace_layer": trace.trace_layer,
                "weakest_link": trace.weakest_link,
                "conclusion_transfer_status": trace.conclusion_transfer_status,
                "downstream_consumer": trace.downstream_consumer,
                "rebuttal": [item.message for item in trace.contradictions],
            }
        )
    return {
        "schema": LOGICGUARD_HANDOFF_SCHEMA,
        "schema_id": LOGICGUARD_HANDOFF_SCHEMA,
        "export_version": LOGICGUARD_HANDOFF_EXPORT_VERSION,
        "metadata": {
            "schema": LOGICGUARD_HANDOFF_SCHEMA,
            "schema_id": LOGICGUARD_HANDOFF_SCHEMA,
            "export_version": LOGICGUARD_HANDOFF_EXPORT_VERSION,
            "purpose": "LogicGuard-ready claim bundle generated from TraceGuard.",
            "repository": "https://github.com/liuyingxuvka/ResearchGuard",
            "skill": "TraceGuard",
            "source_model_fingerprint": receipt_identity.get("model_fingerprint", ""),
            "native_inference_receipt_id": receipt_identity.get("receipt_id", ""),
            "native_inference_receipt": receipt_payload,
            "boundary": "TraceGuard reconstructs traces; LogicGuard audits claims about those traces.",
        },
        "claims": claims,
        "handoffs": [_as_dict(item) for item in getattr(result, "handoffs", ()) if hasattr(item, "to_dict")],
        "consolidation_findings": [_as_dict(item) for item in getattr(result, "consolidation_findings", ()) if hasattr(item, "to_dict")],
        "storyline_depth": _as_dict(getattr(result, "storyline_depth", None)) or None,
    }


def validate_logicguard_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the single current typed handoff contract.

    This is intentionally a small consumer-side gate.  It rejects the former
    unversioned claim/warrant shape instead of allowing it to become a second
    successful path.
    """

    if not isinstance(bundle, Mapping):
        raise ValueError("LogicGuard handoff must be a mapping")
    if bundle.get("schema") != LOGICGUARD_HANDOFF_SCHEMA or bundle.get("schema_id") != LOGICGUARD_HANDOFF_SCHEMA:
        raise ValueError(f"LogicGuard handoff schema must equal {LOGICGUARD_HANDOFF_SCHEMA}")
    if bundle.get("export_version") != LOGICGUARD_HANDOFF_EXPORT_VERSION:
        raise ValueError(f"LogicGuard handoff export_version must equal {LOGICGUARD_HANDOFF_EXPORT_VERSION}")
    metadata = bundle.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("LogicGuard handoff metadata must be a mapping")
    if metadata.get("schema") != LOGICGUARD_HANDOFF_SCHEMA or metadata.get("schema_id") != LOGICGUARD_HANDOFF_SCHEMA:
        raise ValueError("LogicGuard handoff metadata schema is not current")
    if metadata.get("export_version") != LOGICGUARD_HANDOFF_EXPORT_VERSION:
        raise ValueError("LogicGuard handoff metadata export_version is not current")
    if not str(metadata.get("source_model_fingerprint", "") or "").strip():
        raise ValueError("LogicGuard handoff source model fingerprint is required")
    if not str(metadata.get("native_inference_receipt_id", "") or "").strip():
        raise ValueError("LogicGuard handoff native inference receipt identity is required")
    if not isinstance(metadata.get("native_inference_receipt"), Mapping):
        raise ValueError("LogicGuard handoff native inference receipt is required")
    claims = bundle.get("claims")
    if not isinstance(claims, list):
        raise ValueError("LogicGuard handoff claims must be a list")
    claim_ids: set[str] = set()
    for index, claim in enumerate(claims):
        if not isinstance(claim, Mapping):
            raise ValueError(f"claim[{index}] must be a mapping")
        if "warrant" in claim:
            raise ValueError("legacy claim.warrant field is forbidden in the current handoff")
        required = {
            "claim_id",
            "trace_id",
            "domain_proposition",
            "domain_mechanism_refs",
            "domain_boundaries",
            "native_causal_license",
            "domain_gaps",
            "audit_context",
        }
        missing = sorted(required.difference(claim))
        if missing:
            raise ValueError(f"claim[{index}] missing fields: {','.join(missing)}")
        if not isinstance(claim.get("audit_context"), Mapping):
            raise ValueError(f"claim[{index}].audit_context must be a mapping")
        claim_id = claim.get("claim_id")
        if type(claim_id) is not str or not claim_id.strip():
            raise ValueError(f"claim[{index}].claim_id must be a nonempty string")
        if claim_id in claim_ids:
            raise ValueError(f"duplicate claim id in LogicGuard handoff: {claim_id}")
        claim_ids.add(claim_id)
        for key in ("domain_mechanism_refs", "domain_assumption_refs", "object_scope", "material_alternatives", "domain_boundaries", "domain_gaps"):
            value = claim.get(key)
            if not isinstance(value, list) or any(type(item) is not str or not item.strip() for item in value):
                raise ValueError(f"claim[{index}].{key} must be a list of nonempty strings")
        if len(claim["domain_gaps"]) != len(set(claim["domain_gaps"])):
            raise ValueError(f"claim[{index}].domain_gaps must be stable and deduplicated")
        if claim.get("native_causal_license") not in {"causal_assertion_licensed", "not_licensed", "bounded_non_causal"}:
            raise ValueError(f"claim[{index}].native_causal_license is invalid")
        limitation = str(claim.get("limitation", "") or "")
        if any(token in limitation for token in ("HL-MRF", "MAP solution", "calibrated probability", "TraceGuard solver")):
            raise ValueError(f"claim[{index}].limitation contains generic solver language")
    handoffs = bundle.get("handoffs", [])
    if not isinstance(handoffs, list):
        raise ValueError("LogicGuard handoff handoffs must be a list")
    for index, handoff in enumerate(handoffs):
        if not isinstance(handoff, Mapping) or handoff.get("handoff_schema") != LOGICGUARD_HANDOFF_SCHEMA:
            raise ValueError(f"handoff[{index}] is not a current LogicGuard handoff")
    return copy.deepcopy(dict(bundle))


def render_logicguard_yaml(result: EvaluationResult) -> str:
    return dump_yaml(logicguard_bundle(result))


__all__ = [
    "LOGICGUARD_HANDOFF_EXPORT_VERSION",
    "LOGICGUARD_HANDOFF_SCHEMA",
    "logicguard_bundle",
    "render_logicguard_yaml",
    "validate_logicguard_bundle",
]
