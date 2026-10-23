"""
Purpose: Export SourceGuard candidate material to TraceGuard without claiming downstream validation.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: SourceGuard
Math boundary: Expected utility ranks search value, not factual truth or calibrated probability.
CLI: researchguard source export-traceguard <model.yaml> --output traceguard_seed.yaml
Boundary: Source candidates and evidence anchors require downstream TraceGuard/LogicGuard review before final claims.
"""

from __future__ import annotations

from copy import deepcopy


from .loader import dump_yaml
from .schema import BeliefState


TRACEGUARD_BOUNDARY = (
    "Generated from SourceGuard source discovery state; candidate sources are not validated "
    "evidence-to-trace conclusions."
)

TRACEGUARD_SOURCE_STATUS = {
    "saved": "stable_keep",
    "promoted_traceguard": "stable_keep",
    "promoted_logicguard": "stable_keep",
    "permission_gated": "need_auth_or_permission",
    "inaccessible": "need_auth_or_permission",
    "rejected": "invalid_or_empty",
    "duplicate": "invalid_or_empty",
}


def export_traceguard_seed(belief_state: BeliefState) -> dict:
    return {
        "metadata": {
            "schema_version": "researchguard.trace.model.v2",
            "generated_by": "SourceGuard",
            "boundary": TRACEGUARD_BOUNDARY,
            "source_model_version": str(belief_state.metadata.get("version", "")),
            "notes": [
                f"SourceGuard gap {gap.gap_id} ({gap.gap_type}): {gap.description}"
                for gap in belief_state.gaps
            ] + [
                "SourceGuard does not generate validated events or traces.",
                "Permission-gated and unavailable material remains an access gap.",
            ],
        },
        "sources": [{
            "source_id": source.source_id,
            "title": source.title,
            "url": source.url or None,
            "source_type": source.source_type,
            "lineage_id": source.lineage_id or source.source_id,
            "independence_group": source.lineage_id or source.source_id,
            "source_reliability": source.source_reliability,
            "source_status": TRACEGUARD_SOURCE_STATUS.get(source.source_status, "unknown"),
            "source_date": source.source_date or None,
            "coverage_period": source.coverage_period or None,
        } for source in belief_state.sources],
        "evidence": [{
            "evidence_id": anchor.anchor_id,
            "source_id": anchor.source_id,
            "raw_text": anchor.text or anchor.normalized_summary,
            "normalized_summary": anchor.normalized_summary or None,
            "evidence_type": anchor.anchor_type,
            "extraction_confidence": anchor.extraction_confidence,
            "evidence_specificity": anchor.specificity,
            "locator": anchor.locator or None,
            "limits": list(anchor.limits),
            "warnings": list(anchor.warnings),
            "usable_as_trace_evidence": anchor.usable_for_trace or anchor.usable_for_claim,
        } for anchor in belief_state.anchors],
        "events": [],
        "traces": [],
    }


def sync_traceguard_seed(belief_state: BeliefState, existing: dict) -> tuple[dict, dict, list]:
    """Append missing source/anchor ids; preserve every existing downstream field."""
    if not isinstance(existing, dict):
        raise ValueError("--into trace model must be a mapping")
    merged = deepcopy(existing)
    incoming = export_traceguard_seed(belief_state)
    added = {"sources": [], "evidence": []}
    conflicts = []
    for kind, id_key in (("sources", "source_id"), ("evidence", "evidence_id")):
        rows = merged.setdefault(kind, [])
        if not isinstance(rows, list) or any(not isinstance(row, dict) or not row.get(id_key) for row in rows):
            raise ValueError(f"--into {kind} must be id-bearing records")
        by_id = {row[id_key]: row for row in rows}
        if len(by_id) != len(rows):
            raise ValueError(f"--into {kind} ids must be unique")
        for row in incoming[kind]:
            item_id = row[id_key]
            if item_id not in by_id:
                rows.append(row)
                by_id[item_id] = row
                added[kind].append(item_id)
            elif by_id[item_id] != row:
                conflicts.append({"kind": kind, "id": item_id})
    return merged, added, conflicts


def affected_member_handoffs(
    belief_state: BeliefState,
    *,
    gap_ids: list[str] | tuple[str, ...] = (),
    claim_use_ids: list[str] | tuple[str, ...] = (),
) -> dict[str, object]:
    """Project exact handoff consumers without interpreting their payloads."""

    by_gap = belief_state.metadata.get("member_handoffs_by_gap", {})
    by_claim = belief_state.metadata.get("member_handoffs_by_claim_use", {})
    invalid_maps = []
    if not isinstance(by_gap, dict):
        by_gap = {}
        invalid_maps.append("member_handoffs_by_gap")
    if not isinstance(by_claim, dict):
        by_claim = {}
        invalid_maps.append("member_handoffs_by_claim_use")
    affected = {
        str(handoff_id)
        for gap_id in gap_ids
        for handoff_id in by_gap.get(gap_id, [])
    }
    affected.update(
        str(handoff_id)
        for claim_use_id in claim_use_ids
        for handoff_id in by_claim.get(claim_use_id, [])
    )
    declared = {str(item) for item in belief_state.metadata.get("handoff_ids", [])}
    foreign = sorted(affected - declared)
    return {
        "affected_handoff_ids": sorted(affected & declared),
        "unknown_handoff_ids": foreign,
        "invalid_dependency_maps": invalid_maps,
        "unknown_ownership": bool(foreign or invalid_maps),
    }


def render_traceguard_yaml(belief_state: BeliefState) -> str:
    return dump_yaml(export_traceguard_seed(belief_state))


__all__ = [
    "TRACEGUARD_BOUNDARY",
    "affected_member_handoffs",
    "export_traceguard_seed",
    "render_traceguard_yaml",
    "sync_traceguard_seed",
]
