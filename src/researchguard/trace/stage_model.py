"""TraceGuard project-stage finite-state model.

Purpose: Map event types to stage signals and detect stage-transition contradictions.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: TraceGuard
Math boundary: Conservative finite-state factor, not the whole TraceGuard model.
CLI: researchguard trace diagnose <model.yaml>
Boundary: Stage order plausibility is not proof of real-world project status.
"""

from __future__ import annotations


STAGES = [
    "weak_signal",
    "early_signal",
    "announced",
    "funded",
    "tendering",
    "awarded",
    "permitted",
    "FID",
    "construction",
    "commissioning",
    "operation",
    "expansion",
    "delayed",
    "cancelled",
    "unknown",
]

ORDERED_STAGE_INDEX = {
    "weak_signal": 0,
    "early_signal": 1,
    "announced": 2,
    "funded": 3,
    "tendering": 4,
    "awarded": 5,
    "permitted": 6,
    "FID": 7,
    "construction": 8,
    "commissioning": 9,
    "operation": 10,
    "expansion": 11,
}

EVENT_STAGE_SIGNALS = {
    "funding_call": "early_signal",
    "funding_announced": "announced",
    "funding_award": "funded",
    "funding_awarded": "funded",
    "tender_notice": "tendering",
    "contract_award": "awarded",
    "permit": "permitted",
    "fid": "FID",
    "construction_start": "construction",
    "commissioning": "commissioning",
    "operation_start": "operation",
    "operation": "operation",
    "expansion": "expansion",
    "delayed": "delayed",
    "cancelled": "cancelled",
    "patent": "weak_signal",
    "hiring": "weak_signal",
    "company_announcement": "announced",
    "official_project_page": "announced",
    "source_only": "unknown",
}


def stage_for_event(event_type: str, stage_hint: str | None = None) -> str:
    if stage_hint and stage_hint in STAGES:
        return stage_hint
    return EVENT_STAGE_SIGNALS.get(event_type, "unknown")


def valid_stage_transition(stage_a: str, stage_b: str) -> bool:
    if "weak_signal" in {stage_a, stage_b}:
        return True
    if stage_a in {"unknown", "delayed", "cancelled"} or stage_b in {"unknown", "delayed", "cancelled"}:
        return True
    if stage_a not in ORDERED_STAGE_INDEX or stage_b not in ORDERED_STAGE_INDEX:
        return True
    return ORDERED_STAGE_INDEX[stage_b] >= ORDERED_STAGE_INDEX[stage_a]


def stronger_stage(stage_a: str, stage_b: str) -> str:
    if stage_a not in ORDERED_STAGE_INDEX:
        return stage_b
    if stage_b not in ORDERED_STAGE_INDEX:
        return stage_a
    return stage_a if ORDERED_STAGE_INDEX[stage_a] >= ORDERED_STAGE_INDEX[stage_b] else stage_b
