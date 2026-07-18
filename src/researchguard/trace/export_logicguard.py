"""TraceGuard to LogicGuard export.

Purpose: Convert evaluated traces into LogicGuard-ready claim/evidence/warrant bundles.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: TraceGuard
Math boundary: Export preserves TraceGuard boundaries; LogicGuard audits final claims separately.
CLI: researchguard trace export-logicguard <model.yaml> --output bundle.yaml
Boundary: Export is a handoff, not proof that the written claim is licensed.
"""

from __future__ import annotations

from .evaluator import EvaluationResult
from .loader import dump_yaml


def logicguard_bundle(result: EvaluationResult) -> dict[str, object]:
    claims = []
    for trace in result.traces:
        claims.append(
            {
                "claim_id": f"claim_{trace.trace_id}",
                "claim": trace.safe_wording,
                "evidence": list(trace.evidence_ids),
                "warrant": "TraceGuard links source-backed evidence to events and a trace candidate through soft rules and hard gates.",
                "assumption": "The supplied model file contains the relevant source extracts and does not omit material contradictory evidence.",
                "limitation": trace.claim_boundary,
                "scope": f"Status is {trace.validation_status}; do not upgrade this to confirmed/operational unless TraceGuard and LogicGuard evidence both support it.",
                "rebuttal": [item.message for item in trace.contradictions],
                "safe_wording": trace.safe_wording,
                "unsafe_wording_avoided": trace.unsafe_wording_avoided,
                "handoff_id": f"lead_{trace.trace_id}",
                "structure_unit_id": trace.structure_unit_id,
                "source_unit_id": trace.source_unit_id,
                "destination_unit_id": trace.destination_unit_id,
                "trace_layer": trace.trace_layer,
                "weakest_link": trace.weakest_link,
                "conclusion_transfer_status": trace.conclusion_transfer_status,
                "downstream_consumer": trace.downstream_consumer,
            }
        )
    return {
        "metadata": {
            "purpose": "LogicGuard-ready claim bundle generated from TraceGuard.",
            "repository": "https://github.com/liuyingxuvka/ResearchGuard",
            "skill": "TraceGuard",
            "boundary": "TraceGuard reconstructs traces; LogicGuard audits claims about those traces.",
        },
        "claims": claims,
        "handoffs": [item.to_dict() for item in result.handoffs if hasattr(item, "to_dict")],
        "consolidation_findings": [item.to_dict() for item in result.consolidation_findings if hasattr(item, "to_dict")],
        "storyline_depth": result.storyline_depth.to_dict()
        if hasattr(result.storyline_depth, "to_dict")
        else None,
    }


def render_logicguard_yaml(result: EvaluationResult) -> str:
    return dump_yaml(logicguard_bundle(result))
