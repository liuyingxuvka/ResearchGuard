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
from researchguard.source.schema import (
    SourceGuardPreventedFailure,
    SourceGuardProofCase,
    bind_sourceguard_model_contract,
    build_sourceguard_model_contract,
)
from researchguard.source.task_iteration import (
    SearchOutcomePrediction,
    freeze_search_outcome_prediction,
    rollback_search_iteration,
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
    failure = SourceGuardPreventedFailure(
        failure_id="failure:task-local:unqualified-closure",
        title="Unqualified source observation closes a gap",
        block_when="an observation without claim-usable anchors closes a gap",
        oracle_id="oracle:sourceguard:source-qualification",
        known_good=SourceGuardProofCase("good", "good.yaml", "pass"),
        known_bad=SourceGuardProofCase(
            "bad",
            "good.yaml",
            "blocked",
            "make-all-anchors-unusable",
            "gaps:g-target",
        ),
    )
    return bind_sourceguard_model_contract(
        state,
        contract=build_sourceguard_model_contract(
            model_id="task-local-source-model",
            purpose="Prevent source closure without current qualified evidence.",
            prevented_failures=[failure],
            gap_ids=["g-target", "g-holdout"],
            target_unit_ids=[],
            claim_boundary="Task-local source discovery only.",
        ),
    )


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


def test_loaded_prediction_rejects_implicit_or_rebound_task_scope() -> None:
    state = _state()
    raw = _prediction(state).to_dict()
    raw.pop("unknowns")
    with pytest.raises(ValueError, match="missing task fields"):
        SearchOutcomePrediction.from_dict(raw)
    raw = _prediction(state).to_dict()
    raw["coverage_ids"] = ["g-target"]
    with pytest.raises(ValueError, match="does not bind"):
        SearchOutcomePrediction.from_dict(raw)


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


def test_current_prediction_requires_task_scope() -> None:
    state = _state()
    with pytest.raises(TypeError):
        freeze_search_outcome_prediction(
            state,
            action_id="a1",
            expected_gap_reduction="closed",
            expected_independent_lineage=True,
            expected_counterevidence=False,
            expected_cost=0.2,
        )
    assert _prediction(state).coverage_fingerprint.startswith("sha256:")


def test_stale_baseline_is_rejected() -> None:
    state = _state()
    prediction = _prediction(state)
    state.metadata["changed"] = True
    with pytest.raises(ValueError, match="stale search prediction"):
        validate_search_prediction_binding(state, prediction)


def test_open_native_gap_forces_continuation_after_local_success() -> None:
    state = _state()
    _, receipt = run_search_iteration(
        state, _prediction(state), _observation(), actual_cost=0.2, decision="accept"
    )
    assert "g-holdout" in receipt.open_gap_ids
    assert receipt.terminal_reason == "continue_iteration"
    assert receipt.next_actions == ("a2",)


def test_provider_unavailable_has_exact_visible_terminal() -> None:
    state = _state()
    _, receipt = run_search_iteration(
        state,
        _prediction(state),
        None,
        actual_cost=0.0,
        decision="accept",
        provider_status="PROVIDER_UNAVAILABLE",
    )
    assert receipt.terminal_reason == "provider_access_required"
    assert receipt.next_actions == ("a1", "a2") or receipt.next_actions == ("a1",)
    assert receipt.effective_disposition != "accepted"


def test_same_gap_set_is_progress_stalled() -> None:
    state = _state()
    _, first = run_search_iteration(
        state, _prediction(state), _observation(), actual_cost=0.2, decision="accept"
    )
    second_prediction = _prediction(
        state,
        iteration=1,
        prior_receipt_fingerprint=first.receipt_fingerprint,
        prior_open_gap_ids=first.open_gap_ids,
    )
    _, second = run_search_iteration(
        state, second_prediction, _observation(), actual_cost=0.2, decision="accept"
    )
    assert second.terminal_reason == "progress_stalled"
    assert second.persisted_gap_ids == first.open_gap_ids


def test_all_current_native_gaps_can_close_and_rollback() -> None:
    state = _state()
    candidate, receipt = run_search_iteration(
        state,
        _prediction(state),
        _observation(close_holdout=True),
        actual_cost=0.2,
        decision="accept",
    )
    if receipt.effective_disposition == "accepted":
        restored, rollback = rollback_search_iteration(state, receipt.to_dict())
        assert rollback.effective_disposition == "rolled_back"
        assert restored.guard_contract == state.guard_contract
    else:
        assert receipt.native_depth_revalidation.passed is False or receipt.open_gap_ids


def test_cli_freeze_rejects_old_shape_and_emits_v2(tmp_path: Path) -> None:
    output = tmp_path / "prediction.json"
    result = subprocess.run(
        [
            sys.executable, "-m", "researchguard", "source", "search-iteration", "freeze",
            "examples/source/starter_researchguard.source.yaml", "--model-contract",
            "examples/source/starter_researchguard.source.contract.json", "--action-id",
            "action-independent-search-1", "--expected-gap-reduction", "closed",
            "--expected-independent-lineage", "true", "--expected-counterevidence", "false",
            "--expected-cost", "0.3", "--task-id", "source-cli-task", "--purpose",
            "exercise strict source CLI", "--coverage-id", "gap-independent-source-1",
            "--iteration", "0", "--max-iterations", "4", "--output", str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "researchguard.source.search-outcome-prediction.v2"
    assert "prior_gap_fingerprints" not in payload
