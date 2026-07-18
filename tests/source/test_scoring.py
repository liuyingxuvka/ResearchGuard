from dataclasses import replace

from researchguard.source.schema import (
    BeliefState,
    Gap,
    SearchAction,
    SourceRecord,
    SourceGuardPreventedFailure,
    SourceGuardProofCase,
    bind_sourceguard_model_contract,
    build_sourceguard_model_contract,
)
from researchguard.source.scoring import score_action


def _guard_state(state: BeliefState, model_id: str) -> BeliefState:
    gap_id = state.gaps[0].gap_id if state.gaps else "test-gap"
    failure = SourceGuardPreventedFailure(
        failure_id=f"failure:{model_id}:unsafe-ranking",
        title="Unsafe source route is preferred",
        block_when="an unqualified result is treated as closing the ranked gap",
        oracle_id="oracle:sourceguard:source-qualification",
        known_good=SourceGuardProofCase("good:test", "good.yaml", "pass"),
        known_bad=SourceGuardProofCase(
            "bad:test", "good.yaml", "blocked",
            "make-all-anchors-unusable", f"gaps:{gap_id}"
        ),
    )
    return bind_sourceguard_model_contract(
        state,
        contract=build_sourceguard_model_contract(
            model_id=model_id,
            purpose="Prevent source-action scoring from preferring shallow or unsafe evidence routes.",
            prevented_failures=[failure],
            gap_ids=[gap.gap_id for gap in state.gaps],
            target_unit_ids=[gap.structure_unit_id for gap in state.gaps if gap.structure_unit_id],
            claim_boundary="Action ranking only; the score does not establish factual truth.",
        ),
    )


def _state(*, gap_type="missing_independent_source", blocking=True):
    gap = Gap(
        gap_id="g1",
        lead_id="l1",
        gap_type=gap_type,
        description="Need stronger material",
        importance=0.9,
        blocking=blocking,
        suggested_source_roles=["independent_report"],
        suggested_modalities=["text"],
    )
    action = SearchAction(
        action_id="a1",
        action_type="text_search",
        query="project independent report",
        target_lead_id="l1",
        target_gap_id="g1",
        expected_source_role="independent_report",
        expected_modality="text",
        cost=0.2,
    )
    return _guard_state(
        BeliefState(gaps=[gap], actions=[action]),
        f"test-scoring-{gap_type}-{blocking}",
    )


def test_blocking_high_importance_gap_action_scores_higher():
    high = _state(blocking=True)
    low_gap = replace(high.gaps[0], gap_id="g2", importance=0.2, blocking=False)
    low_action = replace(high.actions[0], action_id="a2", target_gap_id="g2")
    low = _guard_state(
        BeliefState(gaps=[low_gap], actions=[low_action]),
        "test-scoring-low",
    )
    assert score_action(high.actions[0], high).gap_closure_value > score_action(low.actions[0], low).gap_closure_value


def test_permission_risk_lowers_total_score():
    state = _state()
    safe = state.actions[0]
    risky = replace(safe, action_id="risky", permission_risk=1.0)
    assert score_action(safe, state).total_score > score_action(risky, state).total_score


def test_counterevidence_search_scores_higher_for_one_sided_gap():
    state = _state(gap_type="one_sided_support")
    counter = replace(state.actions[0], action_id="counter", action_type="counterevidence_search", expected_source_role="counter_evidence")
    normal = replace(state.actions[0], action_id="normal", action_type="text_search", expected_source_role="independent_report")
    assert score_action(counter, state).counterevidence_value > score_action(normal, state).counterevidence_value


def test_multimodal_action_scores_higher_for_visual_gap():
    gap = Gap(
        gap_id="g1",
        gap_type="missing_visual_anchor",
        importance=0.9,
        blocking=True,
        suggested_source_roles=["visual_evidence"],
        suggested_modalities=["image"],
    )
    visual = SearchAction(
        action_id="visual",
        action_type="image_search",
        query="site photo",
        target_gap_id="g1",
        expected_source_role="visual_evidence",
        expected_modality="image",
    )
    text = replace(visual, action_id="text", action_type="text_search", expected_source_role="independent_report", expected_modality="text")
    state = _guard_state(
        BeliefState(gaps=[gap], actions=[visual, text]),
        "test-scoring-multimodal",
    )
    assert score_action(visual, state).multimodal_anchor_value > score_action(text, state).multimodal_anchor_value


def test_duplicate_action_has_redundancy_penalty():
    state = _state()
    duplicate = replace(state.actions[0], action_id="dup")
    state = replace(state, actions=[state.actions[0], duplicate])
    assert score_action(duplicate, state).redundancy_penalty > 0


def test_existing_role_cluster_adds_redundancy_penalty():
    state = _state()
    state = replace(
        state,
        sources=[
            SourceRecord(source_id="s1", source_role="independent_report"),
            SourceRecord(source_id="s2", source_role="independent_report"),
            SourceRecord(source_id="s3", source_role="independent_report"),
        ],
    )
    assert score_action(state.actions[0], state).redundancy_penalty >= 0.35
