from researchguard.source.loader import load_model
from researchguard.source.planner import generate_actions_from_gaps, plan_next_actions
from researchguard.source.schema import (
    BeliefState,
    Gap,
)


def _guard(state: BeliefState, model_id: str) -> BeliefState:
    return state


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
    state = load_model("examples/source/structural_source_gap.yaml")
    actions = generate_actions_from_gaps(state)
    assert actions
    assert {action.expected_source_role for action in actions} & {"bridge_evidence", "method_source"}
    assert state.gaps[0].structure_unit_id == "chapter_3.technology_summary"
    assert all(action.target_gap_id == state.gaps[0].gap_id for action in actions)
    assert not any("chapter_3" in action.query for action in actions)


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
    state = load_model("examples/source/fuel_cell_project_discovery.yaml")
    result = plan_next_actions(state, limit=3)
    assert result.ok
    assert result.selected_actions
    assert result.scored_actions[0].reasons


def test_declared_action_suppresses_generated_duplicate() -> None:
    from pathlib import Path
    from dataclasses import replace
    state = load_model(Path(__file__).parent / "fixtures/evergiven/src_v1.yaml")
    before_actions = tuple(state.actions)
    plan = plan_next_actions(state, limit=5)
    assert tuple(state.actions) == before_actions
    assert not generate_actions_from_gaps(state)
    assert len({item.target_gap_id for item in plan.selected_actions}) == len(plan.selected_actions)
    for status in ("proposed", "selected"):
        changed = replace(state, actions=[replace(action, status=status) for action in state.actions])
        assert not generate_actions_from_gaps(changed)
    for status in ("blocked", "rejected", "completed", "executed"):
        changed = replace(state, actions=[replace(action, status=status) for action in state.actions])
        assert generate_actions_from_gaps(changed)


def test_generated_queries_are_short_and_use_only_gap_and_two_hints() -> None:
    from researchguard.source.schema import Lead
    description = "Required observed dates and independently reported outcome data"
    lead_question = "This long unrelated lead question must never enter a gap query"
    state = BeliefState(metadata={"domain_hints": ["hint-one", "hint-two", "forbidden-hint"]},
                        leads=[Lead("lead", question=lead_question)],
                        gaps=[Gap("gap", lead_id="lead", gap_type="missing_execution_evidence", description=description)])
    actions = generate_actions_from_gaps(state)
    assert actions
    for action in actions:
        assert 0 < len(action.query) <= 120
        assert action.query.startswith(description)
        assert "hint-one" in action.query and "hint-two" in action.query
        assert lead_question not in action.query and "forbidden-hint" not in action.query
        assert action.query.split()[-1] in (description + " hint-one hint-two implementation operation outcome official record independent report direct observation source deployment image visual recorded report evidence").split()
    empty = BeliefState(gaps=[Gap("empty", gap_type="missing_primary_source")])
    assert all(action.query.startswith("missing_primary_source") for action in generate_actions_from_gaps(empty))


def test_lead_only_generated_query_keeps_real_question_with_nonempty_character_bound() -> None:
    from researchguard.source.planner import generate_actions_from_leads
    from researchguard.source.schema import Lead
    for question in ("无空格的真实中文研究问题" * 20, "A real lead question " * 20):
        state = BeliefState(leads=[Lead("lead-only", question=question)])
        action = generate_actions_from_leads(state)[0]
        assert 0 < len(action.query) <= 120
        assert question.startswith(action.query)
        assert action.query != "unclear_scope"


def test_declared_search_comes_first():
    from dataclasses import replace
    from researchguard.source.schema import BeliefState, Gap, SourceRecord
    from researchguard.source.planner import plan_next_actions, generate_actions_from_gaps
    model = BeliefState(sources=[SourceRecord('s', title='A dated source')],
        gaps=[Gap('counter-source-s', gap_type='contradiction', description='Counterevidence candidate observed')])
    generated = generate_actions_from_gaps(model)
    assert len(generated) == 1
    assert generated[0].action_type == 'report_page_search' and generated[0].query == 'A dated source'
    declared = replace(generated[0], action_id='declared', query='Independent source')
    model = replace(model, actions=[declared], sources=[*model.sources, SourceRecord('t', title='Another source')],
        gaps=[*model.gaps, replace(model.gaps[0], gap_id='counter-source-t')])
    generated = generate_actions_from_gaps(model)
    assert len(generated) == 1
    plan = plan_next_actions(model, limit=None)
    scores = {row.action_id: row.total_score for row in plan.scored_actions}
    assert scores['declared'] == scores[generated[0].action_id]
    assert plan.selected_actions[0].action_id == 'declared'


def test_counter_source_query_drops_trailing_notes():
    from researchguard.source.schema import SourceRecord

    cases = [
        (
            "UNCTAD Review of Maritime Transport 2021, ch. 3 (trial transcription)",
            "UNCTAD Review of Maritime Transport 2021, ch. 3",
        ),
        (
            "Drewry WCI Shanghai-Los Angeles lane (trial transcription, approximate)",
            "Drewry WCI Shanghai-Los Angeles lane",
        ),
        ("Port report (draft) (copy)", "Port report"),
        ("Port (Yantian) congestion", "Port (Yantian) congestion"),
        ("(note only)", "Find an independent source"),
    ]
    for title, expected in cases:
        state = BeliefState(
            sources=[SourceRecord("s", title=title)],
            gaps=[
                Gap(
                    "counter-source-s",
                    gap_type="contradiction",
                    description="Find an independent source",
                )
            ],
        )
        actions = generate_actions_from_gaps(state)
        assert len(actions) == 1
        assert actions[0].query == expected
