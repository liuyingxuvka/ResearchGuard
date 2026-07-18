"""
Purpose: Apply SourceGuard observations to a belief state without converting candidates into final evidence.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: SourceGuard
Math boundary: Expected utility ranks search value, not factual truth or calibrated probability.
CLI: researchguard source add-observation <model.yaml> --model-contract <model.contract.json> --observation observation.yaml --output updated.yaml --output-model-contract updated.contract.json
Boundary: Source candidates and evidence anchors require downstream TraceGuard/LogicGuard review before final claims.
"""

from __future__ import annotations

from dataclasses import replace

from .schema import (
    BeliefState,
    EvidenceAnchor,
    Gap,
    GapClosureBasis,
    GapQualification,
    Lead,
    Observation,
    SourceRecord,
    bind_sourceguard_model_contract,
    clamp01,
    utc_now,
    validate_model_guard_binding,
)


DEFAULT_QUALIFICATION_THRESHOLDS = {
    "source_reliability": 0.5,
    "extraction_confidence": 0.5,
    "specificity": 0.5,
}


def _upsert_by_id(items, new_item, attr: str):
    output = []
    replaced = False
    new_id = getattr(new_item, attr)
    for item in items:
        if getattr(item, attr) == new_id:
            output.append(new_item)
            replaced = True
        else:
            output.append(item)
    if not replaced:
        output.append(new_item)
    return output


def add_source(belief_state: BeliefState, source: SourceRecord) -> BeliefState:
    source = replace(source, source_status=source.source_status or "candidate")
    return replace(belief_state, sources=_upsert_by_id(belief_state.sources, source, "source_id"))


def add_anchor(belief_state: BeliefState, anchor: EvidenceAnchor) -> BeliefState:
    return replace(belief_state, anchors=_upsert_by_id(belief_state.anchors, anchor, "anchor_id"))


def add_gap(belief_state: BeliefState, gap: Gap) -> BeliefState:
    return replace(belief_state, gaps=_upsert_by_id(belief_state.gaps, gap, "gap_id"))


def add_lead(belief_state: BeliefState, lead: Lead) -> BeliefState:
    return replace(belief_state, leads=_upsert_by_id(belief_state.leads, lead, "lead_id"))


def mark_action_executed(belief_state: BeliefState, action_id: str) -> BeliefState:
    actions = []
    for action in belief_state.actions:
        if action.action_id == action_id:
            actions.append(replace(action, status="executed"))
        else:
            actions.append(action)
    return replace(belief_state, actions=actions)


def _source_is_accessible_candidate(belief_state: BeliefState, source_id: str) -> bool:
    source = belief_state.source_by_id().get(source_id)
    if source is None:
        return False
    return source.access_status not in {"permission_gated", "unavailable"} and source.source_status not in {
        "permission_gated",
        "inaccessible",
        "rejected",
    }


def _qualification_thresholds(belief_state: BeliefState) -> dict[str, float]:
    configured = belief_state.metadata.get("qualification_thresholds") or {}
    if not isinstance(configured, dict):
        configured = {}
    return {
        name: clamp01(configured.get(name), default)
        for name, default in DEFAULT_QUALIFICATION_THRESHOLDS.items()
    }


def qualify_gap_from_anchor(
    belief_state: BeliefState,
    anchor: EvidenceAnchor,
    *,
    observation_id: str = "",
) -> BeliefState:
    """Advance matching gaps only when semantic qualification is explicit.

    A locator is one input, not a closure decision. Closure additionally needs
    an accessible source, reliability/extraction/specificity floors, explicit
    target fit, and claim usability when the gap requests claim closure.
    """

    source = belief_state.source_by_id().get(anchor.source_id)
    accessible = _source_is_accessible_candidate(belief_state, anchor.source_id)
    thresholds = _qualification_thresholds(belief_state)
    gaps = []
    for gap in belief_state.gaps:
        if gap.gap_id not in set(anchor.supports) or gap.gap_type == "permission_gap":
            gaps.append(gap)
            continue

        role_match = bool(source) and (
            not gap.suggested_source_roles or source.source_role in gap.suggested_source_roles
        )
        modality_match = not gap.suggested_modalities or anchor.modality in gap.suggested_modalities
        target_match = role_match and modality_match
        reliability = source.source_reliability if source else 0.0
        reasons: list[str] = []
        checks = {
            "locator present": bool(anchor.locator),
            "source accessible": accessible,
            "source reliability threshold": reliability >= thresholds["source_reliability"],
            "extraction confidence threshold": anchor.extraction_confidence
            >= thresholds["extraction_confidence"],
            "specificity threshold": anchor.specificity >= thresholds["specificity"],
            "target role and modality match": target_match,
            "observation id recorded": bool(observation_id),
        }
        for label, passed in checks.items():
            if not passed:
                reasons.append(f"failed: {label}")
        if gap.requires_claim_usability and not anchor.usable_for_claim:
            reasons.append("failed: anchor is not usable for claim closure")

        evidence_qualified = all(checks.values())
        claim_use_ok = not gap.requires_claim_usability or anchor.usable_for_claim
        closure_qualified = evidence_qualified and claim_use_ok
        if (
            not closure_qualified
            and gap.semantic_state == "closed"
            and gap.closure_basis.is_complete()
        ):
            # A later portfolio, limiting, or independent anchor may be linked
            # to an already closed gap without matching the primary closure
            # role.  It must not erase the earlier qualified closure.
            gaps.append(gap)
            continue
        if closure_qualified:
            decision = "claim_usable" if gap.requires_claim_usability else "qualified_non_claim_closure"
            semantic_state = "closed"
        elif not accessible:
            decision = "blocked"
            semantic_state = "blocked"
        elif evidence_qualified and gap.requires_claim_usability:
            decision = "qualified_not_claim_usable"
            semantic_state = "qualified"
        else:
            decision = "observed_not_qualified"
            semantic_state = "observed"

        qualification = GapQualification(
            anchor_id=anchor.anchor_id,
            source_id=anchor.source_id,
            observation_id=observation_id,
            locator_present=bool(anchor.locator),
            source_accessible=accessible,
            source_reliability=reliability,
            extraction_confidence=anchor.extraction_confidence,
            specificity=anchor.specificity,
            supports_gap=True,
            role_match=role_match,
            modality_match=modality_match,
            target_match=target_match,
            usable_for_claim=anchor.usable_for_claim,
            decision=decision,
            reasons=reasons,
        )
        closure_basis = gap.closure_basis
        if closure_qualified:
            closure_basis = GapClosureBasis(
                anchor_ids=[anchor.anchor_id],
                source_ids=[anchor.source_id],
                observation_ids=[observation_id],
                thresholds=thresholds,
                target_match="source role, anchor modality, and explicit gap support matched",
                claim_use_decision=decision,
                qualified=True,
            )
        note = "Semantically qualified and closed." if closure_qualified else "Anchor observed; semantic closure not licensed."
        gaps.append(
            replace(
                gap,
                semantic_state=semantic_state,
                qualification=qualification,
                closure_basis=closure_basis,
                review_required=not closure_qualified,
                notes=f"{gap.notes} {note}".strip(),
            )
        )
    return replace(belief_state, gaps=gaps)


def detect_basic_contradiction(belief_state: BeliefState, observation: Observation) -> list[Gap]:
    gaps: list[Gap] = []
    for index, contradiction in enumerate(observation.contradictions, start=1):
        gaps.append(
            Gap(
                gap_id=f"contradiction-{observation.observation_id}-{index}",
                lead_id="",
                gap_type="contradiction",
                description=contradiction,
                importance=0.7,
                blocking=True,
                suggested_source_roles=["counter_evidence", "limiting_evidence"],
                semantic_state="contradicted",
                notes="Observation reported a contradiction; existing support is preserved.",
            )
        )
    for source in observation.observed_sources:
        if source.source_role == "counter_evidence":
            gaps.append(
                Gap(
                    gap_id=f"counter-source-{source.source_id}",
                    gap_type="contradiction",
                    description=f"Counterevidence candidate observed: {source.title or source.source_id}",
                    importance=0.7,
                    blocking=False,
                    suggested_source_roles=["counter_evidence", "limiting_evidence"],
                    semantic_state="contradicted",
                    notes="Counterevidence should be modeled downstream rather than overwriting prior support.",
                )
            )
    return gaps


def update_frontier(belief_state: BeliefState) -> BeliefState:
    metadata = dict(belief_state.metadata)
    metadata["updated_at"] = utc_now()
    metadata["frontier_boundary"] = "Updated frontier preserves candidates and anchors; it does not validate final claims."
    return replace(belief_state, metadata=metadata)


def apply_observation(belief_state: BeliefState, observation: Observation) -> BeliefState:
    validate_model_guard_binding(belief_state)
    frozen_contract = belief_state.guard_contract
    assert frozen_contract is not None
    state = belief_state
    warnings = list(state.metadata.get("warnings", []))
    for source in observation.observed_sources:
        state = add_source(state, source)
        if source.access_status in {"permission_gated", "unavailable"} or source.source_status == "permission_gated":
            warnings.append(f"Source {source.source_id} is permission-gated or unavailable and remains an access gap.")
    for anchor in observation.observed_anchors:
        anchor_warnings = list(anchor.warnings)
        if not anchor.locator:
            anchor_warnings.append("Anchor has no locator and cannot safely close a specific evidence gap.")
            warnings.append(f"Anchor {anchor.anchor_id} has no locator.")
        safe_anchor = replace(anchor, warnings=anchor_warnings)
        state = add_anchor(state, safe_anchor)
        state = qualify_gap_from_anchor(state, safe_anchor, observation_id=observation.observation_id)
        for gap in state.gaps:
            if gap.qualification.anchor_id == safe_anchor.anchor_id and gap.semantic_state != "closed":
                warnings.append(
                    f"Anchor {safe_anchor.anchor_id} observed for {gap.gap_id} but did not satisfy semantic closure: "
                    + "; ".join(gap.qualification.reasons)
                )
    for lead in observation.new_leads:
        state = add_lead(state, lead)
    for gap in observation.new_gaps:
        state = add_gap(state, gap)
    for gap in detect_basic_contradiction(state, observation):
        state = add_gap(state, gap)
    if observation.action_id:
        state = mark_action_executed(state, observation.action_id)
    state = replace(state, observations=_upsert_by_id(state.observations, observation, "observation_id"))
    metadata = dict(state.metadata)
    metadata["warnings"] = warnings
    successor = update_frontier(replace(state, metadata=metadata))
    # Preserve the AI-authored purpose, failure declarations, proof cases, and
    # claim boundary.  A newly observed gap expands only the successor's exact
    # external universe and construction sequence, producing a new fingerprint
    # that must be written as a new explicit sidecar before later reuse.
    successor_contract = replace(
        frozen_contract,
        external_universe={
            "gap_ids": sorted({gap.gap_id for gap in successor.gaps}),
            "target_unit_ids": sorted(
                {gap.structure_unit_id for gap in successor.gaps if gap.structure_unit_id}
            ),
        },
        candidate_construction_sequence=frozen_contract.candidate_construction_sequence + 1,
    )
    return bind_sourceguard_model_contract(successor, contract=successor_contract)
