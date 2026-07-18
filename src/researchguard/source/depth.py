"""Native SourceGuard semantic-depth receipts and observation replanning."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from .planner import plan_next_actions
from .schema import (
    BeliefState,
    GapTransition,
    Observation,
    PlanResult,
    ReplanComparison,
    SOURCE_DEPTH_NATIVE_POLICY_ORIGIN,
    SOURCE_PORTFOLIO_CLASSES,
    SourceCoverageDimension,
    SourceCoverageUniverse,
    SourceDepthReceipt,
    SourceObjectDepthRow,
    to_plain,
    validate_model_guard_binding,
)
from .update import DEFAULT_QUALIFICATION_THRESHOLDS, apply_observation


def model_fingerprint(belief_state: BeliefState) -> str:
    """Return a deterministic fingerprint for the supplied belief state."""

    payload = to_plain(belief_state)
    if isinstance(payload, dict):
        payload = dict(payload)
        payload.pop("generated_at", None)
        metadata = dict(payload.get("metadata") or {})
        metadata.pop("updated_at", None)
        payload["metadata"] = metadata
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_sha256(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _action_order(plan: PlanResult) -> list[str]:
    return [action.action_id for action in plan.selected_actions]


def _score_map(plan: PlanResult) -> dict[str, float]:
    return {item.action_id: item.total_score for item in plan.scored_actions}


def compare_replans(before: PlanResult, after: PlanResult) -> ReplanComparison:
    before_ids = _action_order(before)
    after_ids = _action_order(after)
    before_rank = {action_id: index for index, action_id in enumerate(before_ids)}
    after_rank = {action_id: index for index, action_id in enumerate(after_ids)}
    before_scores = _score_map(before)
    after_scores = _score_map(after)
    reprioritized: list[dict[str, object]] = []
    for action_id in sorted(set(before_ids) & set(after_ids)):
        old_score = before_scores.get(action_id, 0.0)
        new_score = after_scores.get(action_id, 0.0)
        if before_rank[action_id] != after_rank[action_id] or abs(old_score - new_score) > 1e-9:
            reprioritized.append(
                {
                    "action_id": action_id,
                    "before_rank": before_rank[action_id],
                    "after_rank": after_rank[action_id],
                    "before_score": old_score,
                    "after_score": new_score,
                }
            )
    before_open = [gap.gap_id for gap in before.open_gaps]
    after_open = [gap.gap_id for gap in after.open_gaps]
    return ReplanComparison(
        before_action_ids=before_ids,
        after_action_ids=after_ids,
        added_action_ids=sorted(set(after_ids) - set(before_ids)),
        removed_action_ids=sorted(set(before_ids) - set(after_ids)),
        reprioritized_actions=reprioritized,
        before_open_gap_ids=before_open,
        after_open_gap_ids=after_open,
        remaining_gap_ids=sorted({gap.gap_id for gap in after.open_gaps + after.blocked_gaps}),
    )


def _gap_transitions(
    before: BeliefState,
    after: BeliefState,
    observation_id: str = "",
) -> list[GapTransition]:
    before_gaps = before.gap_by_id()
    after_gaps = after.gap_by_id()
    transitions: list[GapTransition] = []
    for gap_id in sorted(set(before_gaps) | set(after_gaps)):
        old = before_gaps.get(gap_id)
        new = after_gaps.get(gap_id)
        before_semantic = old.semantic_state if old else "absent"
        after_semantic = new.semantic_state if new else "absent"
        if before_semantic == after_semantic:
            continue
        reason = "observation changed semantic gap state"
        if new and new.qualification.reasons:
            reason = "; ".join(new.qualification.reasons)
        elif new and new.qualification.decision not in {"", "not_evaluated"}:
            reason = new.qualification.decision
        transitions.append(
            GapTransition(
                gap_id=gap_id,
                before_semantic_state=before_semantic,
                after_semantic_state=after_semantic,
                observation_ids=[observation_id] if observation_id else [],
                reason=reason,
            )
        )
    return transitions


def _portfolio_class(source_role: str) -> str:
    if source_role in {"primary_source", "official_claim", "validation_evidence", "method_source"}:
        return "direct_or_primary"
    if source_role == "independent_report":
        return "independent"
    if source_role in {"counter_evidence", "limiting_evidence"}:
        return "counter_or_limiting"
    return ""


def _anchor_depth_rows(belief_state: BeliefState) -> list[dict[str, object]]:
    """Return target-owned anchor/source rows used by broad depth checks.

    Merely naming a source or locator is intentionally insufficient.  The row
    is qualified only when the current source is accessible, the anchor has
    content, the native semantic thresholds pass, and claim use is explicit.
    """

    configured = belief_state.metadata.get("qualification_thresholds") or {}
    if not isinstance(configured, dict):
        configured = {}
    thresholds = {
        name: float(configured.get(name, default))
        for name, default in DEFAULT_QUALIFICATION_THRESHOLDS.items()
    }
    source_by_id = belief_state.source_by_id()
    rows: list[dict[str, object]] = []
    for anchor in belief_state.anchors:
        source = source_by_id.get(anchor.source_id)
        portfolio_class = _portfolio_class(source.source_role) if source else ""
        linked_gap_ids = sorted(set(anchor.supports) | set(anchor.limits))
        accessible = bool(
            source
            and source.access_status not in {"permission_gated", "unavailable"}
            and source.source_status not in {"permission_gated", "inaccessible", "rejected"}
        )
        content_present = bool(anchor.text.strip() or anchor.normalized_summary.strip())
        qualified = bool(
            source
            and portfolio_class
            and linked_gap_ids
            and anchor.locator.strip()
            and (content_present or not belief_state.depth_policy.require_anchor_content)
            and accessible
            and source.source_reliability >= thresholds["source_reliability"]
            and anchor.extraction_confidence >= thresholds["extraction_confidence"]
            and anchor.specificity >= thresholds["specificity"]
            and anchor.usable_for_claim
        )
        rows.append(
            {
                "anchor_id": anchor.anchor_id,
                "source_id": anchor.source_id,
                "portfolio_class": portfolio_class,
                "lineage_id": source.lineage_id.strip() if source else "",
                "linked_gap_ids": linked_gap_ids,
                "supports_gap_ids": sorted(set(anchor.supports)),
                "limits_gap_ids": sorted(set(anchor.limits)),
                "selected": bool(source and portfolio_class and linked_gap_ids),
                "qualified": qualified,
                "content_present": content_present,
                "evidence_ref": f"sourceguard:anchor:{anchor.anchor_id}",
                "evidence_sha256": _canonical_sha256(
                    {
                        "anchor": {
                            "anchor_id": anchor.anchor_id,
                            "source_id": anchor.source_id,
                            "locator": anchor.locator,
                            "text": anchor.text,
                            "normalized_summary": anchor.normalized_summary,
                            "extraction_confidence": anchor.extraction_confidence,
                            "specificity": anchor.specificity,
                            "supports": sorted(set(anchor.supports)),
                            "limits": sorted(set(anchor.limits)),
                            "usable_for_claim": anchor.usable_for_claim,
                        },
                        "source": (
                            {
                                "source_id": source.source_id,
                                "source_status": source.source_status,
                                "source_reliability": source.source_reliability,
                                "source_role": source.source_role,
                                "lineage_id": source.lineage_id,
                                "access_status": source.access_status,
                            }
                            if source
                            else None
                        ),
                    }
                ),
            }
        )
    return rows


def _coverage_floor(belief_state: BeliefState, dimension_id: str) -> float:
    declared = belief_state.depth_policy.coverage_floors.get(dimension_id, 1.0)
    return max(1.0, float(declared))


def _coverage_dimension(
    *,
    dimension_id: str,
    universe_ids: list[str],
    critical_ids: list[str],
    selected_ids: list[str],
    qualified_ids: list[str],
    covered_ids: list[str],
    coverage_floor: float,
    required: bool,
) -> SourceCoverageDimension:
    universe = sorted(set(universe_ids))
    critical = sorted(set(critical_ids))
    selected = sorted(set(selected_ids))
    qualified = sorted(set(qualified_ids))
    covered = sorted(set(covered_ids))
    eligible_count = len(universe)
    closed_count = len(set(covered) & set(universe))
    ratio = closed_count / eligible_count if eligible_count else 0.0
    critical_uncovered = sorted(set(critical) - set(covered))
    findings: list[str] = []
    if required and not universe:
        findings.append(f"{dimension_id}_required_universe_empty")
    if required and ratio < coverage_floor:
        findings.append(f"{dimension_id}_coverage_below_floor")
    if critical_uncovered:
        findings.append(f"{dimension_id}_critical_items_uncovered")
    return SourceCoverageDimension(
        dimension_id=dimension_id,
        universe_ids=universe,
        critical_ids=critical,
        selected_ids=selected,
        qualified_ids=qualified,
        covered_ids=covered,
        available_count=len(universe),
        eligible_count=eligible_count,
        selected_count=len(selected),
        qualified_count=len(qualified),
        closed_count=closed_count,
        coverage_ratio=ratio,
        coverage_floor=coverage_floor,
        floor_origin=SOURCE_DEPTH_NATIVE_POLICY_ORIGIN,
        critical_uncovered_ids=critical_uncovered,
        status="pass" if not findings else "fail",
        findings=findings,
    )


def build_source_coverage_universe(
    baseline: BeliefState,
    updated: BeliefState,
    closure_source_ids: set[str],
    *,
    observation_depth: bool,
) -> SourceCoverageUniverse:
    """Build the target-owned denominator and quantitative adequacy decision."""

    policy = baseline.depth_policy
    broad_requested = policy.requested_claim_scope == "broad"
    threshold = policy.important_threshold
    updated_gap_by_id = updated.gap_by_id()
    closed_gap_ids = {
        gap_id
        for gap_id, gap in updated_gap_by_id.items()
        if gap.semantic_state == "closed" and gap.closure_basis.is_complete()
    }
    gap_ids = sorted(gap.gap_id for gap in baseline.gaps)
    critical_gap_ids = sorted(
        gap.gap_id for gap in baseline.gaps if gap.blocking or gap.importance >= threshold
    )
    qualified_gap_ids = sorted(
        gap.gap_id
        for gap in updated.gaps
        if gap.qualification.decision not in {"", "not_evaluated"}
    )

    lead_ids = sorted(lead.lead_id for lead in baseline.leads)
    critical_lead_ids = sorted(lead.lead_id for lead in baseline.leads if lead.importance >= threshold)
    updated_leads = updated.lead_by_id()
    covered_lead_ids: list[str] = []
    for lead in baseline.leads:
        current = updated_leads.get(lead.lead_id)
        if current is None:
            continue
        linked_gap_ids = set(lead.gaps)
        if current.status == "closed" or (linked_gap_ids and linked_gap_ids <= closed_gap_ids):
            covered_lead_ids.append(lead.lead_id)

    required_roles = sorted(
        set(policy.required_source_roles)
        | {role for gap in baseline.gaps for role in gap.suggested_source_roles if role != "unknown"}
    )
    required_classes = set(policy.required_portfolio_classes)
    if broad_requested:
        required_classes |= SOURCE_PORTFOLIO_CLASSES

    anchor_rows = _anchor_depth_rows(updated)
    updated_source_by_id = updated.source_by_id()
    selected_source_roles = sorted(
        {source.source_role for source in updated.sources if source.source_role != "unknown"}
    )
    closed_sources = [
        updated_source_by_id[source_id]
        for source_id in sorted(closure_source_ids)
        if source_id in updated_source_by_id
    ]
    closed_roles = sorted({source.source_role for source in closed_sources if source.source_role != "unknown"})
    selected_classes = sorted(
        {portfolio_class for source in updated.sources if (portfolio_class := _portfolio_class(source.source_role))}
    )
    covered_classes = sorted(
        {
            str(row["portfolio_class"])
            for row in anchor_rows
            if row["qualified"] and row["portfolio_class"]
        }
    )

    qualified_source_ids = sorted(
        {str(row["source_id"]) for row in anchor_rows if row["qualified"]}
    )
    lineage_ids = sorted(
        {str(row["lineage_id"]) for row in anchor_rows if row["qualified"] and row["lineage_id"]}
    )
    lineage_slot_ids = [
        f"independent_lineage_slot:{index}"
        for index in range(1, policy.minimum_independent_lineages + 1)
    ]
    covered_lineage_slots = lineage_slot_ids[: min(len(lineage_ids), len(lineage_slot_ids))]

    special_gap_ids = sorted(
        gap.gap_id
        for gap in baseline.gaps
        if gap.gap_type in {"missing_bridge_evidence", "missing_numeric_provenance", "missing_date"}
    )

    declared_target_units = sorted(set(policy.target_unit_inventory_ids))
    discovered_target_units = sorted(
        {gap.structure_unit_id for gap in baseline.gaps if gap.structure_unit_id}
    )
    required_target_units = sorted(set(policy.required_target_unit_ids))
    excluded_target_units = sorted(set(policy.excluded_target_unit_ids))
    exclusion_reasons = {
        str(unit_id): (reason.strip() if isinstance(reason, str) else "")
        for unit_id, reason in policy.target_unit_exclusion_reasons.items()
        if str(unit_id).strip()
    }
    declared_set = set(declared_target_units)
    discovered_set = set(discovered_target_units)
    required_set = set(required_target_units)
    excluded_set = set(excluded_target_units)
    reconciliation_findings: list[str] = []
    if broad_requested and not declared_set:
        reconciliation_findings.append("target_unit_inventory_required_for_broad")
    missing_discovered = sorted(discovered_set - declared_set)
    if missing_discovered:
        reconciliation_findings.append(
            "target_unit_inventory_missing_discovered:" + ",".join(missing_discovered)
        )
    required_outside = sorted(required_set - declared_set)
    if required_outside:
        reconciliation_findings.append(
            "target_unit_required_outside_inventory:" + ",".join(required_outside)
        )
    excluded_outside = sorted(excluded_set - declared_set)
    if excluded_outside:
        reconciliation_findings.append(
            "target_unit_excluded_outside_inventory:" + ",".join(excluded_outside)
        )
    overlap = sorted(required_set & excluded_set)
    if overlap:
        reconciliation_findings.append(
            "target_unit_required_excluded_overlap:" + ",".join(overlap)
        )
    unclassified = sorted(declared_set - required_set - excluded_set)
    if unclassified:
        reconciliation_findings.append(
            "target_unit_inventory_unclassified:" + ",".join(unclassified)
        )
    missing_reasons = sorted(
        unit_id for unit_id in excluded_set if not exclusion_reasons.get(unit_id)
    )
    if missing_reasons:
        reconciliation_findings.append(
            "target_unit_exclusion_reason_missing:" + ",".join(missing_reasons)
        )
    orphan_reasons = sorted(set(exclusion_reasons) - excluded_set)
    if orphan_reasons:
        reconciliation_findings.append(
            "target_unit_exclusion_reason_orphan:" + ",".join(orphan_reasons)
        )
    excluded_with_gaps = sorted(discovered_set & excluded_set)
    if excluded_with_gaps:
        reconciliation_findings.append(
            "target_unit_excluded_has_active_gap:" + ",".join(excluded_with_gaps)
        )
    selected_target_units = discovered_target_units
    covered_target_units: list[str] = []
    for unit_id in required_target_units:
        unit_gap_ids = [gap.gap_id for gap in baseline.gaps if gap.structure_unit_id == unit_id]
        if unit_gap_ids and set(unit_gap_ids) <= closed_gap_ids:
            covered_target_units.append(unit_id)

    per_gap_portfolio_universe: list[str] = []
    per_gap_portfolio_selected: list[str] = []
    per_gap_portfolio_covered: list[str] = []
    per_gap_lineage_universe: list[str] = []
    per_gap_lineage_covered: list[str] = []
    object_depth_rows: list[SourceObjectDepthRow] = []
    for gap_id in critical_gap_ids:
        gap = next(item for item in baseline.gaps if item.gap_id == gap_id)
        linked_rows = [row for row in anchor_rows if gap_id in row["linked_gap_ids"]]
        qualified_rows = [row for row in linked_rows if row["qualified"]]
        covered_gap_classes = sorted(
            {str(row["portfolio_class"]) for row in qualified_rows if row["portfolio_class"]}
        )
        for portfolio_class in sorted(required_classes):
            item_id = f"{gap_id}:portfolio:{portfolio_class}"
            per_gap_portfolio_universe.append(item_id)
            if any(row["portfolio_class"] == portfolio_class for row in linked_rows):
                per_gap_portfolio_selected.append(item_id)
            if portfolio_class in covered_gap_classes:
                per_gap_portfolio_covered.append(item_id)
        gap_lineages = sorted(
            {str(row["lineage_id"]) for row in qualified_rows if row["lineage_id"]}
        )
        for index in range(1, policy.minimum_independent_lineages + 1):
            slot_id = f"{gap_id}:lineage_slot:{index}"
            per_gap_lineage_universe.append(slot_id)
            if len(gap_lineages) >= index:
                per_gap_lineage_covered.append(slot_id)
        row_findings: list[str] = []
        missing_classes = sorted(required_classes - set(covered_gap_classes))
        if missing_classes:
            row_findings.append("missing_portfolio_classes:" + ",".join(missing_classes))
        if len(gap_lineages) < policy.minimum_independent_lineages:
            row_findings.append("independent_lineage_floor_not_met")
        if not qualified_rows:
            row_findings.append("no_content_qualified_anchor")
        obligation_evidence: list[dict[str, object]] = []
        for portfolio_class in sorted(required_classes):
            for evidence_row in qualified_rows:
                if evidence_row["portfolio_class"] != portfolio_class:
                    continue
                obligation_evidence.append(
                    {
                        "target_obligation_ids": [
                            f"{gap_id}:portfolio:{portfolio_class}"
                        ],
                        "evidence_kind": "qualified_source_anchor",
                        "evidence_ref": evidence_row["evidence_ref"],
                        "evidence_sha256": evidence_row["evidence_sha256"],
                        "anchor_id": evidence_row["anchor_id"],
                        "source_id": evidence_row["source_id"],
                        "portfolio_class": portfolio_class,
                        "lineage_id": evidence_row["lineage_id"],
                    }
                )
        for index, lineage_id in enumerate(gap_lineages, start=1):
            matching_rows = [
                evidence_row
                for evidence_row in qualified_rows
                if evidence_row["lineage_id"] == lineage_id
            ]
            for evidence_row in matching_rows:
                obligation_evidence.append(
                    {
                        "target_obligation_ids": [f"{gap_id}:lineage:{index}"],
                        "evidence_kind": "independent_lineage_anchor",
                        "evidence_ref": evidence_row["evidence_ref"],
                        "evidence_sha256": evidence_row["evidence_sha256"],
                        "anchor_id": evidence_row["anchor_id"],
                        "source_id": evidence_row["source_id"],
                        "lineage_id": lineage_id,
                    }
                )
        for evidence_row in qualified_rows:
            obligation_evidence.append(
                {
                    "target_obligation_ids": [f"{gap_id}:content-anchor"],
                    "evidence_kind": "content_bearing_anchor",
                    "evidence_ref": evidence_row["evidence_ref"],
                    "evidence_sha256": evidence_row["evidence_sha256"],
                    "anchor_id": evidence_row["anchor_id"],
                    "source_id": evidence_row["source_id"],
                }
            )
        if gap.structure_unit_id:
            target_unit_content = {
                "gap_id": gap_id,
                "target_unit_id": gap.structure_unit_id,
                "gap_type": gap.gap_type,
                "blocking": gap.blocking,
                "importance": gap.importance,
            }
            obligation_evidence.append(
                {
                    "target_obligation_ids": [f"{gap_id}:target-unit"],
                    "evidence_kind": "target_unit_binding",
                    "evidence_ref": f"sourceguard:gap:{gap_id}:target-unit",
                    "evidence_sha256": _canonical_sha256(target_unit_content),
                    **target_unit_content,
                }
            )
        object_depth_rows.append(
            SourceObjectDepthRow(
                gap_id=gap_id,
                target_unit_id=gap.structure_unit_id,
                required_portfolio_classes=sorted(required_classes),
                covered_portfolio_classes=covered_gap_classes,
                selected_source_ids=sorted({str(row["source_id"]) for row in linked_rows}),
                qualified_source_ids=sorted({str(row["source_id"]) for row in qualified_rows}),
                anchor_ids=sorted({str(row["anchor_id"]) for row in qualified_rows}),
                explicit_lineage_ids=gap_lineages,
                required_lineage_count=policy.minimum_independent_lineages,
                obligation_evidence=obligation_evidence,
                status="pass" if not row_findings else "fail",
                findings=row_findings,
            )
        )
    dimensions = [
        _coverage_dimension(
            dimension_id="gaps",
            universe_ids=gap_ids,
            critical_ids=critical_gap_ids,
            selected_ids=sorted(updated_gap_by_id),
            qualified_ids=qualified_gap_ids,
            covered_ids=sorted(closed_gap_ids),
            coverage_floor=_coverage_floor(baseline, "gaps"),
            required=broad_requested,
        ),
        _coverage_dimension(
            dimension_id="branches",
            universe_ids=lead_ids,
            critical_ids=critical_lead_ids,
            selected_ids=sorted(updated_leads),
            qualified_ids=covered_lead_ids,
            covered_ids=covered_lead_ids,
            coverage_floor=_coverage_floor(baseline, "branches"),
            required=broad_requested,
        ),
        _coverage_dimension(
            dimension_id="portfolio_classes",
            universe_ids=sorted(required_classes),
            critical_ids=sorted(required_classes),
            selected_ids=selected_classes,
            qualified_ids=covered_classes,
            covered_ids=covered_classes,
            coverage_floor=_coverage_floor(baseline, "portfolio_classes"),
            required=broad_requested,
        ),
        _coverage_dimension(
            dimension_id="independent_lineages",
            universe_ids=lineage_slot_ids,
            critical_ids=lineage_slot_ids,
            selected_ids=lineage_ids,
            qualified_ids=lineage_ids,
            covered_ids=covered_lineage_slots,
            coverage_floor=_coverage_floor(baseline, "independent_lineages"),
            required=broad_requested,
        ),
        _coverage_dimension(
            dimension_id="target_units",
            universe_ids=required_target_units,
            critical_ids=required_target_units,
            selected_ids=selected_target_units,
            qualified_ids=covered_target_units,
            covered_ids=covered_target_units,
            coverage_floor=_coverage_floor(baseline, "target_units"),
            required=broad_requested,
        ),
        _coverage_dimension(
            dimension_id="per_gap_portfolio",
            universe_ids=per_gap_portfolio_universe,
            critical_ids=per_gap_portfolio_universe,
            selected_ids=per_gap_portfolio_selected,
            qualified_ids=per_gap_portfolio_covered,
            covered_ids=per_gap_portfolio_covered,
            coverage_floor=_coverage_floor(baseline, "per_gap_portfolio"),
            required=broad_requested and policy.per_gap_portfolio_required,
        ),
        _coverage_dimension(
            dimension_id="per_gap_lineages",
            universe_ids=per_gap_lineage_universe,
            critical_ids=per_gap_lineage_universe,
            selected_ids=per_gap_lineage_covered,
            qualified_ids=per_gap_lineage_covered,
            covered_ids=per_gap_lineage_covered,
            coverage_floor=_coverage_floor(baseline, "per_gap_lineages"),
            required=broad_requested,
        ),
        _coverage_dimension(
            dimension_id="explicit_lineage_sources",
            universe_ids=qualified_source_ids,
            critical_ids=qualified_source_ids,
            selected_ids=qualified_source_ids,
            qualified_ids=sorted(
                {
                    str(row["source_id"])
                    for row in anchor_rows
                    if row["qualified"] and row["lineage_id"]
                }
            ),
            covered_ids=sorted(
                {
                    str(row["source_id"])
                    for row in anchor_rows
                    if row["qualified"] and row["lineage_id"]
                }
            ),
            coverage_floor=_coverage_floor(baseline, "explicit_lineage_sources"),
            required=broad_requested and policy.require_explicit_lineage,
        ),
    ]
    if required_roles:
        dimensions.append(
            _coverage_dimension(
                dimension_id="source_roles",
                universe_ids=required_roles,
                critical_ids=required_roles,
                selected_ids=selected_source_roles,
                qualified_ids=closed_roles,
                covered_ids=closed_roles,
                coverage_floor=_coverage_floor(baseline, "source_roles"),
                required=broad_requested,
            )
        )
    if special_gap_ids:
        dimensions.append(
            _coverage_dimension(
                dimension_id="bridge_and_provenance",
                universe_ids=special_gap_ids,
                critical_ids=special_gap_ids,
                selected_ids=sorted(updated_gap_by_id),
                qualified_ids=qualified_gap_ids,
                covered_ids=sorted(closed_gap_ids),
                coverage_floor=_coverage_floor(baseline, "bridge_and_provenance"),
                required=broad_requested,
            )
        )

    fingerprint_payload = {
        "owner_id": "researchguard.source.semantic-gap-depth",
        "policy_origin": SOURCE_DEPTH_NATIVE_POLICY_ORIGIN,
        "requested_claim_scope": policy.requested_claim_scope,
        "important_threshold": threshold,
        "minimum_independent_lineages": policy.minimum_independent_lineages,
        "target_unit_inventory_ids": declared_target_units,
        "required_target_unit_ids": required_target_units,
        "excluded_target_unit_ids": excluded_target_units,
        "target_unit_exclusion_reasons": exclusion_reasons,
        "discovered_target_unit_ids": discovered_target_units,
        "require_explicit_lineage": policy.require_explicit_lineage,
        "require_anchor_content": policy.require_anchor_content,
        "per_gap_portfolio_required": policy.per_gap_portfolio_required,
        "dimensions": [
            {
                "dimension_id": item.dimension_id,
                "universe_ids": item.universe_ids,
                "critical_ids": item.critical_ids,
                "coverage_floor": item.coverage_floor,
                "floor_origin": item.floor_origin,
            }
            for item in dimensions
        ],
    }
    universe_fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    critical_uncovered = sorted(
        f"{item.dimension_id}:{item_id}"
        for item in dimensions
        for item_id in item.critical_uncovered_ids
    )
    findings = sorted(
        {finding for item in dimensions for finding in item.findings}
        | set(reconciliation_findings)
    )
    if not observation_depth:
        adequacy_status = "not_run"
        covered_scope = "planning_only"
    elif not broad_requested:
        adequacy_status = "bounded"
        covered_scope = "bounded"
    elif findings or critical_uncovered:
        adequacy_status = "fail"
        covered_scope = "bounded"
    else:
        adequacy_status = "pass"
        covered_scope = "broad"
    return SourceCoverageUniverse(
        owner_id="researchguard.source.semantic-gap-depth",
        policy_origin=SOURCE_DEPTH_NATIVE_POLICY_ORIGIN,
        requested_claim_scope=policy.requested_claim_scope,
        covered_claim_scope=covered_scope,
        universe_fingerprint=universe_fingerprint,
        declared_target_unit_ids=declared_target_units,
        discovered_target_unit_ids=discovered_target_units,
        required_target_unit_ids=required_target_units,
        excluded_target_unit_ids=excluded_target_units,
        target_unit_exclusion_reasons=exclusion_reasons,
        target_unit_reconciliation_status=(
            "pass" if not reconciliation_findings else "fail"
        ),
        dimensions=dimensions,
        object_depth_rows=object_depth_rows,
        critical_uncovered_ids=critical_uncovered,
        adequacy_status=adequacy_status,
        findings=findings,
    )


def apply_observation_and_replan(
    belief_state: BeliefState,
    observation: Observation | None = None,
    *,
    provider_status: str = "NOT_RUN",
    limit: int = 5,
) -> tuple[BeliefState, SourceDepthReceipt]:
    """Clone a baseline, optionally apply one supplied observation, and replan.

    This function never invokes a provider. An absent observation remains
    explicitly NOT_RUN or PROVIDER_UNAVAILABLE and cannot create closure depth.
    """

    validate_model_guard_binding(belief_state)
    baseline = deepcopy(belief_state)
    before_plan = plan_next_actions(baseline, limit=limit)
    normalized_provider = str(provider_status or "NOT_RUN").upper()
    if normalized_provider not in {"NOT_RUN", "PROVIDER_UNAVAILABLE", "OBSERVATION_SUPPLIED"}:
        raise ValueError(f"unsupported provider_status {provider_status!r}")

    if observation is None:
        updated = deepcopy(baseline)
        observation_status = "PROVIDER_UNAVAILABLE" if normalized_provider == "PROVIDER_UNAVAILABLE" else "NOT_RUN"
        observations_used: list[str] = []
    else:
        normalized_provider = "OBSERVATION_SUPPLIED"
        updated = apply_observation(deepcopy(baseline), observation)
        observation_status = "APPLIED"
        observations_used = [observation.observation_id]

    after_plan = plan_next_actions(updated, limit=limit)
    comparison = compare_replans(before_plan, after_plan)
    transitions = _gap_transitions(
        baseline,
        updated,
        observation.observation_id if observation is not None else "",
    )
    qualifications = [
        gap.qualification
        for gap in updated.gaps
        if gap.qualification.decision not in {"", "not_evaluated"}
        and (observation is None or gap.qualification.observation_id == observation.observation_id)
    ]
    closure_bases = {
        gap.gap_id: gap.closure_basis
        for gap in updated.gaps
        if gap.semantic_state == "closed" and gap.closure_basis.is_complete()
    }
    closure_source_ids = {
        source_id
        for basis in closure_bases.values()
        for source_id in basis.source_ids
    }
    unresolved = sorted(
        gap.gap_id
        for gap in updated.gaps
        if gap.semantic_state != "closed"
    )
    observation_depth = observation is not None
    coverage_universe = build_source_coverage_universe(
        baseline,
        updated,
        closure_source_ids,
        observation_depth=observation_depth,
    )
    broad_claim_licensed = bool(
        baseline.depth_policy.requested_claim_scope == "broad"
        and observation_depth
        and closure_bases
        and not unresolved
        and coverage_universe.adequacy_status == "pass"
        and coverage_universe.covered_claim_scope == "broad"
    )
    status = "pass" if broad_claim_licensed else ("bounded" if observation_depth else "planning_only")
    receipt = SourceDepthReceipt(
        receipt_version="researchguard.source.depth.v2",
        model_fingerprint=model_fingerprint(baseline),
        result_model_fingerprint=model_fingerprint(updated),
        provider_status=normalized_provider,
        observation_status=observation_status,
        planning_depth_completed=True,
        observation_depth_completed=observation_depth,
        observations_used=observations_used,
        gap_transitions=transitions,
        qualifications=qualifications,
        closure_bases=closure_bases,
        replan_comparison=comparison,
        unresolved_gap_ids=unresolved,
        coverage_universe=coverage_universe,
        requested_claim_scope=coverage_universe.requested_claim_scope,
        covered_claim_scope=coverage_universe.covered_claim_scope,
        adequacy_status=coverage_universe.adequacy_status,
        critical_uncovered_ids=coverage_universe.critical_uncovered_ids,
        native_obligation_evidence=[
            {
                "native_object_id": row.gap_id,
                **evidence,
            }
            for row in coverage_universe.object_depth_rows
            for evidence in row.obligation_evidence
        ],
        broad_claim_licensed=broad_claim_licensed,
        status=status,
    )
    return updated, receipt


def build_source_depth_receipt(
    belief_state: BeliefState,
    observation: Observation | None = None,
    *,
    provider_status: str = "NOT_RUN",
    limit: int = 5,
) -> SourceDepthReceipt:
    return apply_observation_and_replan(
        belief_state,
        observation,
        provider_status=provider_status,
        limit=limit,
    )[1]


__all__ = [
    "apply_observation_and_replan",
    "build_source_depth_receipt",
    "build_source_coverage_universe",
    "compare_replans",
    "model_fingerprint",
]
