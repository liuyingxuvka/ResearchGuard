from researchguard.source.loader import load_model
from researchguard.source.planner import generate_actions_from_gaps, plan_next_actions
from researchguard.source.schema import (
    BeliefState,
    Gap,
    SourceGuardPreventedFailure,
    SourceGuardProofCase,
    build_sourceguard_model_contract,
    bind_sourceguard_model_contract,
)


def _guard(state: BeliefState, model_id: str) -> BeliefState:
    failure = SourceGuardPreventedFailure(
        failure_id=f"failure:{model_id}:unqualified-candidate",
        title="Unqualified candidate is promoted",
        block_when="a candidate without a usable anchor closes a gap",
        oracle_id="oracle:sourceguard:source-qualification",
        known_good=SourceGuardProofCase("good:test:qualified", "good.yaml", "pass"),
        known_bad=SourceGuardProofCase(
            "bad:test:unqualified",
            "good.yaml",
            "blocked",
            "make-all-anchors-unusable",
            f"gaps:{state.gaps[0].gap_id}" if state.gaps else "gaps:test",
        ),
    )
    return bind_sourceguard_model_contract(
        state,
        contract=build_sourceguard_model_contract(
            model_id=model_id,
            purpose="Prevent incomplete or misleading source-discovery plans.",
            prevented_failures=[failure],
            gap_ids=[gap.gap_id for gap in state.gaps],
            target_unit_ids=[gap.structure_unit_id for gap in state.gaps if gap.structure_unit_id],
            claim_boundary="Planning quality only; factual truth remains downstream.",
        ),
    )


def test_gap_types_generate_reasonable_actions():
    gap_types = [
        "missing_primary_source",
        "missing_independent_source",
        "missing_date",
        "missing_location",
        "missing_execution_evidence",
        "weak_signal_only",
        "one_sided_support",
        "contradiction",
        "missing_visual_anchor",
        "missing_audio_anchor",
        "missing_book_page",
        "missing_pdf_page",
        "missing_structural_source_support",
        "missing_bridge_evidence",
        "missing_conclusion_recovery_source",
        "unclear_entity",
    ]
    gaps = [Gap(gap_id=f"g{i}", lead_id="l1", gap_type=gap_type, importance=0.8) for i, gap_type in enumerate(gap_types)]
    state = _guard(BeliefState(gaps=gaps), "test-gap-types")
    actions = generate_actions_from_gaps(state)
    targeted = {action.target_gap_id for action in actions}
    assert {gap.gap_id for gap in gaps} <= targeted


def test_missing_execution_evidence_not_only_plain_text_search():
    gap = Gap(gap_id="g1", lead_id="l1", gap_type="missing_execution_evidence", importance=1.0, blocking=True)
    actions = generate_actions_from_gaps(_guard(BeliefState(gaps=[gap]), "test-execution-evidence"))
    assert actions
    assert any(action.action_type in {"source_domain_search", "image_search", "video_search", "report_page_search"} for action in actions)
    assert not all(action.action_type == "text_search" for action in actions)


def test_structural_source_gap_generates_structural_roles():
    state = load_model(
        "examples/source/structural_source_gap.yaml",
        "examples/source/structural_source_gap.contract.json",
    )
    actions = generate_actions_from_gaps(state)
    assert actions
    assert {action.expected_source_role for action in actions} & {"bridge_evidence", "method_source"}
    assert any("chapter_3" in action.query for action in actions)


def test_permission_gap_blocked_when_policy_disallows():
    gap = Gap(gap_id="g1", lead_id="l1", gap_type="permission_gap", importance=0.9)
    actions = generate_actions_from_gaps(
        _guard(
            BeliefState(metadata={"source_policy": "public_only"}, gaps=[gap]),
            "test-permission-policy",
        )
    )
    assert actions[0].status == "blocked"


def test_plan_next_actions_returns_reasons():
    state = load_model(
        "examples/source/fuel_cell_project_discovery.yaml",
        "examples/source/fuel_cell_project_discovery.contract.json",
    )
    result = plan_next_actions(state, limit=3)
    assert result.ok
    assert result.selected_actions
    assert result.scored_actions[0].reasons
