from researchguard.source.schema import (
    BeliefState,
    EvidenceAnchor,
    Gap,
    Observation,
    SourceRecord,
)
from researchguard.source.update import apply_observation


def _guard(state: BeliefState, model_id: str) -> BeliefState:
    return state


def test_observation_can_add_source_and_anchor():
    state = _guard(BeliefState(), "test-update-add-source")
    obs = Observation(
        observation_id="obs1",
        observed_sources=[SourceRecord(source_id="s1", source_type="paper")],
        observed_anchors=[EvidenceAnchor(anchor_id="a1", source_id="s1", anchor_type="paragraph", locator="section=1", modality="text")],
    )
    updated = apply_observation(state, obs)
    assert updated.sources[0].source_id == "s1"
    assert updated.anchors[0].anchor_id == "a1"


def test_permission_gated_source_does_not_close_gap():
    state = _guard(
        BeliefState(gaps=[Gap(gap_id="g1", gap_type="missing_primary_source")]),
        "test-update-permission",
    )
    obs = Observation(
        observation_id="obs1",
        observed_sources=[SourceRecord(source_id="s1", source_status="permission_gated", access_status="permission_gated")],
        observed_anchors=[EvidenceAnchor(anchor_id="a1", source_id="s1", locator="page=1", supports=["g1"], modality="pdf_page")],
    )
    updated = apply_observation(state, obs)
    assert updated.gaps[0].semantic_state == "blocked"
    assert updated.metadata["warnings"]


def test_missing_locator_produces_warning():
    state = _guard(BeliefState(), "test-update-locator")
    obs = Observation(
        observation_id="obs1",
        observed_sources=[SourceRecord(source_id="s1")],
        observed_anchors=[EvidenceAnchor(anchor_id="a1", source_id="s1", modality="image")],
    )
    updated = apply_observation(state, obs)
    assert any("no locator" in warning.lower() for warning in updated.metadata["warnings"])


def test_counterevidence_does_not_overwrite_support():
    state = _guard(
        BeliefState(gaps=[Gap(gap_id="g1", gap_type="one_sided_support")]),
        "test-update-counterevidence",
    )
    obs = Observation(
        observation_id="obs1",
        observed_sources=[SourceRecord(source_id="s-counter", source_role="counter_evidence")],
    )
    updated = apply_observation(state, obs)
    assert any(gap.gap_id == "g1" and gap.semantic_state == "discovered" for gap in updated.gaps)
    assert any(gap.gap_type == "contradiction" for gap in updated.gaps)
