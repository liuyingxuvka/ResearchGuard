"""
Purpose: Export SourceGuard candidate material to TraceGuard or LogicGuard without claiming downstream validation.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: SourceGuard
Math boundary: Expected utility ranks search value, not factual truth or calibrated probability.
CLI: researchguard source export-traceguard <model.yaml> --model-contract <model.contract.json> --output traceguard_seed.yaml
Boundary: Source candidates and evidence anchors require downstream TraceGuard/LogicGuard review before final claims.
"""

from __future__ import annotations

from researchguard import __version__

from .loader import dump_yaml
from .schema import BeliefState, to_plain


TRACEGUARD_BOUNDARY = (
    "Generated from SourceGuard source discovery state; candidate sources are not validated "
    "evidence-to-trace conclusions."
)

LOGICGUARD_BOUNDARY = (
    "Candidate material must still be preserved and modeled in LogicGuard source library "
    "before final claim support."
)


def _require_suite_version(belief_state: BeliefState) -> str:
    version = belief_state.metadata.get("version")
    if version != __version__:
        raise ValueError(
            "SourceGuard model version must equal the active ResearchGuard "
            f"suite version {__version__}; got {version!r}"
        )
    return version


def export_traceguard_seed(belief_state: BeliefState) -> dict:
    return {
        "metadata": {
            "generated_by": "SourceGuard",
            "boundary": TRACEGUARD_BOUNDARY,
            "source_model_version": _require_suite_version(belief_state),
        },
        "sources": [to_plain(source) for source in belief_state.sources],
        "evidence_anchors": [to_plain(anchor) for anchor in belief_state.anchors],
        "source_gaps": [to_plain(gap) for gap in belief_state.gaps],
        "events": [],
        "traces": [],
        "warnings": [
            "SourceGuard does not generate validated events or traces.",
            "Permission-gated and unavailable material remains an access gap.",
        ],
    }


def export_logicguard_source_candidates(belief_state: BeliefState) -> dict:
    anchors_by_source: dict[str, list[dict]] = {}
    for anchor in belief_state.anchors:
        anchors_by_source.setdefault(anchor.source_id, []).append(to_plain(anchor))
    candidates = []
    for source in belief_state.sources:
        candidates.append(
            {
                "source_id": source.source_id,
                "title": source.title,
                "source_role": source.source_role,
                "source_date": source.source_date,
                "coverage_period": source.coverage_period,
                "access_status": source.access_status,
                "can_support_structural_use": source.can_support_structural_use,
                "cannot_support_structural_use": source.cannot_support_structural_use,
                "anchors": anchors_by_source.get(source.source_id, []),
                "candidate_claim_support_role": source.source_role,
                "limitations": [anchor.limits for anchor in belief_state.anchors if anchor.source_id == source.source_id],
                "counterevidence_notes": source.notes if source.source_role == "counter_evidence" else "",
                "boundary": "Candidate source only; LogicGuard has not modeled or validated final claim support.",
            }
        )
    return {
        "metadata": {
            "generated_by": "SourceGuard",
            "boundary": LOGICGUARD_BOUNDARY,
            "source_model_version": _require_suite_version(belief_state),
        },
        "source_candidates": candidates,
        "source_gap_rows": [to_plain(gap) for gap in belief_state.gaps],
    }


def render_traceguard_yaml(belief_state: BeliefState) -> str:
    return dump_yaml(export_traceguard_seed(belief_state))


def render_logicguard_yaml(belief_state: BeliefState) -> str:
    return dump_yaml(export_logicguard_source_candidates(belief_state))
