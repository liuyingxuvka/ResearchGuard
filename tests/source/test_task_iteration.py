from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from researchguard.source import (
    BeliefState,
    EvidenceAnchor,
    Gap,
    Observation,
    SearchAction,
    SourceRecord,
)
from researchguard.source.depth import model_fingerprint
from researchguard.source.task_iteration import (
    SearchOutcomePrediction,
    freeze_search_outcome_prediction,
    run_search_iteration,
    validate_search_prediction_binding,
)


ROOT = Path(__file__).resolve().parents[2]


def _state() -> BeliefState:
    gaps = [
        Gap(
            gap_id=gap_id,
            lead_id="lead-1",
            gap_type="missing_independent_source",
            description=description,
            importance=0.9,
            blocking=True,
            suggested_source_roles=["independent_report"],
            suggested_modalities=["text"],
        )
        for gap_id, description in (
            ("g-target", "Outcome evidence is missing."),
            ("g-holdout", "Independent holdout evidence is missing."),
        )
    ]
    state = BeliefState(
        metadata={"purpose": "strict task-local source iteration"},
        gaps=gaps,
        actions=[
            SearchAction(
                action_id="a1",
                action_type="text_search",
                query="independent evidence",
                target_lead_id="lead-1",
                target_gap_id="g-target",
                expected_source_role="independent_report",
                expected_modality="text",
                cost=0.2,
            ),
            SearchAction(
                action_id="a2",
                action_type="text_search",
                query="holdout evidence",
                target_lead_id="lead-1",
                target_gap_id="g-holdout",
                expected_source_role="independent_report",
                expected_modality="text",
                cost=0.2,
            ),
        ],
    )
    return state


def _prediction(state: BeliefState, **overrides) -> SearchOutcomePrediction:
    values = {
        "action_id": "a1",
        "expected_gap_reduction": "closed",
        "expected_independent_lineage": True,
        "expected_counterevidence": False,
        "expected_cost": 0.2,
        "protected_gap_ids": (),
        "prediction_id": "prediction-source-task",
        "task_id": "source-task-1",
        "purpose": "close both declared source obligations",
        "coverage_ids": ("g-target", "g-holdout"),
        "assumptions": (),
        "unknowns": (),
        "iteration": 0,
        "max_iterations": 4,
    }
    values.update(overrides)
    return freeze_search_outcome_prediction(state, **values)


def test_loaded_prediction_accepts_missing_optional_task_fields() -> None:
    state = _state()
    raw = _prediction(state).to_dict()
    for key in ("task_id", "purpose", "coverage_ids", "assumptions", "unknowns"):
        raw.pop(key)
    loaded = SearchOutcomePrediction.from_dict(raw)
    assert loaded.coverage_ids == ()
    assert "coverage_fingerprint" not in loaded.to_dict()


def _observation(*, close_holdout: bool = False) -> Observation:
    source = SourceRecord(
        source_id="source-independent",
        source_type="paper",
        source_role="independent_report",
        source_reliability=0.9,
        lineage_id="lineage-independent",
        access_status="public",
    )
    supports = ["g-target", "g-holdout"] if close_holdout else ["g-target"]
    return Observation(
        observation_id="observation-a1",
        action_id="a1",
        observed_sources=[source],
        observed_anchors=[
            EvidenceAnchor(
                anchor_id="anchor-independent",
                source_id=source.source_id,
                anchor_type="paragraph",
                locator="results:2",
                modality="text",
                extraction_confidence=0.9,
                specificity=0.9,
                supports=supports,
                usable_for_claim=True,
            )
        ],
    )


def test_prediction_needs_only_the_action_and_expected_outcome() -> None:
    state = _state()
    prediction = freeze_search_outcome_prediction(
        state, action_id="a1", expected_gap_reduction="closed", expected_independent_lineage=True,
        expected_counterevidence=False, expected_cost=0.2,
    )
    assert prediction.target_gap_id == "g-target"
    assert prediction.iteration == 0
    with pytest.raises(ValueError, match="missing from baseline"):
        _prediction(state, action_id="a-missing")
    with pytest.raises(ValueError, match="coverage gaps are missing from baseline: g-unknown"):
        _prediction(state, coverage_ids=("g-target", "g-unknown"))


def test_stale_baseline_is_rejected() -> None:
    state = _state()
    prediction = _prediction(state)
    state.metadata["changed"] = True
    with pytest.raises(ValueError, match="stale search prediction"):
        validate_search_prediction_binding(state, prediction)


def test_open_native_gap_forces_continuation_after_local_success() -> None:
    state = _state()
    _, result = run_search_iteration(
        state, _prediction(state), _observation(), actual_cost=0.2, decision="accept"
    )
    assert "g-holdout" in result.open_gap_ids
    assert result.terminal_reason == "continue_iteration"
    assert result.next_actions == ("a2",)


def test_provider_unavailable_has_exact_visible_terminal() -> None:
    state = _state()
    _, result = run_search_iteration(
        state,
        _prediction(state),
        None,
        actual_cost=0.0,
        decision="accept",
        provider_status="PROVIDER_UNAVAILABLE",
    )
    assert result.terminal_reason == "provider_access_required"
    assert result.next_actions == ("a1", "a2") or result.next_actions == ("a1",)
    assert result.effective_disposition != "accepted"


def test_same_gap_set_is_progress_stalled() -> None:
    state = _state()
    _, first = run_search_iteration(
        state, _prediction(state), _observation(), actual_cost=0.2, decision="accept"
    )
    second_prediction = _prediction(
        state,
        iteration=1,
        prior_open_gap_ids=first.open_gap_ids,
    )
    _, second = run_search_iteration(
        state, second_prediction, _observation(), actual_cost=0.2, decision="accept"
    )
    assert second.terminal_reason == "progress_stalled"
    assert second.persisted_gap_ids == first.open_gap_ids


def test_closing_every_gap_leaves_the_baseline_untouched() -> None:
    state = _state()
    before = model_fingerprint(state)
    candidate, result = run_search_iteration(
        state,
        _prediction(state),
        _observation(close_holdout=True),
        actual_cost=0.2,
        decision="accept",
    )
    assert model_fingerprint(state) == before
    assert model_fingerprint(candidate) != before
    assert result.effective_disposition == "accepted"
    assert result.terminal_reason == "model_closed_for_task"
    assert "receipt_fingerprint" not in result.to_dict()


def test_cli_freeze_rejects_old_shape_and_emits_v2(tmp_path: Path) -> None:
    output = tmp_path / "prediction.json"
    result = subprocess.run(
        [
            sys.executable, "-m", "researchguard", "source", "search-iteration", "freeze",
            "examples/source/starter_researchguard.source.yaml", "--action-id",
            "action-independent-search-1", "--expected-gap-reduction", "closed",
            "--expected-independent-lineage", "true", "--expected-counterevidence", "false",
            "--expected-cost", "0.3", "--output", str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "researchguard.source.search-outcome-prediction.v2"
    assert "coverage_fingerprint" not in payload
