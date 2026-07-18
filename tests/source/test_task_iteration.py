from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import researchguard.source.task_iteration as task_iteration_module
from researchguard.source import (
    BeliefState,
    EvidenceAnchor,
    Gap,
    Observation,
    SearchAction,
    SourceRecord,
)
from researchguard.source.depth import model_fingerprint
from researchguard.source.schema import (
    SourceGuardPreventedFailure,
    SourceGuardProofCase,
    bind_sourceguard_model_contract,
    build_sourceguard_model_contract,
)
from researchguard.source.task_iteration import (
    SearchOutcomePrediction,
    freeze_search_outcome_prediction,
    review_search_candidate,
    rollback_search_iteration,
    run_search_iteration,
    validate_search_prediction_binding,
)


ROOT = Path(__file__).resolve().parents[2]


def _guarded_state() -> BeliefState:
    target = Gap(
        gap_id="g-target",
        lead_id="l1",
        gap_type="missing_independent_source",
        description="Independent outcome evidence is missing.",
        importance=0.9,
        blocking=True,
        suggested_source_roles=["independent_report"],
        suggested_modalities=["text"],
    )
    protected = Gap(
        gap_id="g-protected",
        lead_id="l1",
        gap_type="missing_counterevidence",
        description="Counterevidence review remains independently pending.",
        importance=0.8,
        blocking=True,
        suggested_source_roles=["independent_report"],
        suggested_modalities=["text"],
    )
    state = BeliefState(
        metadata={"purpose": "task-local search iteration"},
        gaps=[target, protected],
        actions=[
            SearchAction(
                action_id="a1",
                action_type="text_search",
                query="independent outcome evidence",
                target_lead_id="l1",
                target_gap_id="g-target",
                expected_source_role="independent_report",
                expected_modality="text",
                cost=0.3,
            )
        ],
        weights={"gap_closure": 0.25, "search_cost": 0.1},
    )
    failure = SourceGuardPreventedFailure(
        failure_id="failure:task-local:unqualified-closure",
        title="Unqualified source observation closes a gap",
        block_when="an observation without a claim-usable anchor closes the target gap",
        oracle_id="oracle:sourceguard:source-qualification",
        known_good=SourceGuardProofCase("good:task-local", "good.yaml", "pass"),
        known_bad=SourceGuardProofCase(
            "bad:task-local",
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
            purpose="Prevent task-local observations from licensing unqualified source closure.",
            prevented_failures=[failure],
            gap_ids=["g-protected", "g-target"],
            target_unit_ids=[],
            claim_boundary="Task-local source discovery only; factual truth is not licensed.",
        ),
    )


def _qualified_observation(*, touch_protected: bool = False, counter: bool = False) -> Observation:
    sources = [
        SourceRecord(
            source_id="s-independent",
            source_type="paper",
            source_role="independent_report",
            source_reliability=0.9,
            lineage_id="lineage-independent",
            access_status="public",
        )
    ]
    if counter:
        sources.append(
            SourceRecord(
                source_id="s-counter",
                source_type="report",
                source_role="counter_evidence",
                source_reliability=0.8,
                lineage_id="lineage-counter",
                access_status="public",
            )
        )
    supports = ["g-target", "g-protected"] if touch_protected else ["g-target"]
    return Observation(
        observation_id="obs-a1",
        action_id="a1",
        observed_sources=sources,
        observed_anchors=[
            EvidenceAnchor(
                anchor_id="anchor-independent",
                source_id="s-independent",
                anchor_type="paragraph",
                locator="results:paragraph-2",
                modality="text",
                extraction_confidence=0.9,
                specificity=0.9,
                supports=supports,
                usable_for_claim=True,
            )
        ],
        contradictions=["reported limiting result"] if counter else [],
    )


def _prediction(state: BeliefState, **overrides) -> SearchOutcomePrediction:
    values = {
        "action_id": "a1",
        "expected_gap_reduction": "closed",
        "expected_independent_lineage": True,
        "expected_counterevidence": False,
        "expected_cost": 0.2,
        "cost_tolerance": 0.05,
        "protected_gap_ids": ("g-protected",),
        "prediction_id": "prediction-task-local",
    }
    values.update(overrides)
    return freeze_search_outcome_prediction(state, **values)


def test_freeze_binds_action_and_baseline_without_observation() -> None:
    state = _guarded_state()
    prediction = _prediction(state)

    assert prediction.action_id == "a1"
    assert prediction.target_gap_id == "g-target"
    assert prediction.baseline_fingerprint == model_fingerprint(state)
    assert "realized_outcome" not in prediction.to_dict()


def test_stale_baseline_or_wrong_observation_action_is_rejected() -> None:
    state = _guarded_state()
    prediction = _prediction(state)
    state.metadata["changed_after_freeze"] = True

    with pytest.raises(ValueError, match="stale search prediction"):
        validate_search_prediction_binding(state, prediction)

    fresh = _guarded_state()
    wrong = _qualified_observation()
    wrong.action_id = "another-action"
    with pytest.raises(ValueError, match="observation action_id"):
        run_search_iteration(
            fresh,
            _prediction(fresh),
            wrong,
            actual_cost=0.2,
            decision="accept",
        )


def test_valid_candidate_can_be_accepted_even_when_cost_prediction_misses() -> None:
    state = _guarded_state()
    prediction = _prediction(state)

    candidate, receipt = run_search_iteration(
        state,
        prediction,
        _qualified_observation(),
        actual_cost=0.8,
        decision="accept",
    )

    assert state.gap_by_id()["g-target"].semantic_state == "discovered"
    assert candidate.gap_by_id()["g-target"].semantic_state == "closed"
    assert receipt.realized_outcome.gap_reduction == "closed"
    assert receipt.realized_outcome.independent_lineage_found is True
    assert receipt.prediction_error.cost_within_tolerance is False
    assert receipt.prediction_error.overall_matches is False
    assert receipt.candidate_review.weights_unchanged is True
    assert receipt.effective_disposition == "accepted"
    assert receipt.selected_model_fingerprint == model_fingerprint(candidate)


def test_counterevidence_prediction_error_is_explicit() -> None:
    state = _guarded_state()
    prediction = _prediction(state, expected_counterevidence=False)

    _, receipt = run_search_iteration(
        state,
        prediction,
        _qualified_observation(counter=True),
        actual_cost=0.2,
        decision="accept",
    )

    assert receipt.realized_outcome.counterevidence_found is True
    assert receipt.prediction_error.counterevidence_matches is False


def test_protected_gap_change_blocks_requested_accept() -> None:
    state = _guarded_state()
    prediction = _prediction(state)

    _, receipt = run_search_iteration(
        state,
        prediction,
        _qualified_observation(touch_protected=True),
        actual_cost=0.2,
        decision="accept",
    )

    assert receipt.candidate_review.protected_gaps[0].status == "fail"
    assert receipt.effective_disposition == "rejected"
    assert receipt.selected_model_fingerprint == prediction.baseline_fingerprint


def test_native_depth_failure_blocks_requested_accept(monkeypatch) -> None:
    state = _guarded_state()
    prediction = _prediction(state)
    native_update = task_iteration_module.apply_observation_and_replan

    def _failed_native_update(*args, **kwargs):
        candidate, receipt = native_update(*args, **kwargs)
        receipt.result_model_fingerprint = "stale-candidate-fingerprint"
        receipt.status = "planning_only"
        return candidate, receipt

    monkeypatch.setattr(
        task_iteration_module,
        "apply_observation_and_replan",
        _failed_native_update,
    )

    _, receipt = run_search_iteration(
        state,
        prediction,
        _qualified_observation(),
        actual_cost=0.2,
        decision="accept",
    )

    assert receipt.native_depth_revalidation.passed is False
    assert receipt.native_depth_revalidation.candidate_binding_current is False
    assert receipt.effective_disposition == "rejected"
    assert receipt.selected_model_fingerprint == prediction.baseline_fingerprint


def test_global_weight_drift_fails_candidate_review() -> None:
    state = _guarded_state()
    candidate = copy.deepcopy(state)
    candidate.weights["gap_closure"] = 0.99

    review = review_search_candidate(state, candidate, ("g-protected",))

    assert review.weights_unchanged is False
    assert review.passed is False


def test_explicit_reject_and_accepted_rollback_preserve_baseline() -> None:
    state = _guarded_state()
    prediction = _prediction(state)
    candidate, rejected = run_search_iteration(
        state,
        prediction,
        _qualified_observation(),
        actual_cost=0.2,
        decision="reject",
    )
    assert rejected.effective_disposition == "rejected"
    assert rejected.selected_model_fingerprint == model_fingerprint(state)
    assert model_fingerprint(candidate) != model_fingerprint(state)

    _, accepted = run_search_iteration(
        state,
        prediction,
        _qualified_observation(),
        actual_cost=0.2,
        decision="accept",
    )
    restored, rollback = rollback_search_iteration(state, accepted.to_dict())

    assert rollback.effective_disposition == "rolled_back"
    assert model_fingerprint(restored) == model_fingerprint(state)
    with pytest.raises(ValueError, match="accepted"):
        rollback_search_iteration(state, rejected.to_dict())


def test_cli_freeze_run_and_rollback_use_new_output_paths(tmp_path: Path) -> None:
    prediction_path = tmp_path / "prediction.json"
    observation_path = tmp_path / "observation.yaml"
    candidate_path = tmp_path / "candidate.yaml"
    candidate_contract_path = tmp_path / "candidate.contract.json"
    run_receipt_path = tmp_path / "run-receipt.json"
    restored_path = tmp_path / "restored.yaml"
    restored_contract_path = tmp_path / "restored.contract.json"
    rollback_receipt_path = tmp_path / "rollback-receipt.json"
    observation = yaml.safe_load(
        (ROOT / "examples" / "source" / "model-purpose-observation.yaml").read_text(
            encoding="utf-8"
        )
    )
    observation["action_id"] = "action-independent-search-1"
    observation_path.write_text(
        yaml.safe_dump(observation, sort_keys=False),
        encoding="utf-8",
    )

    frozen = _run_cli(
        "search-iteration",
        "freeze",
        "examples/source/starter_researchguard.source.yaml",
        "--model-contract",
        "examples/source/starter_researchguard.source.contract.json",
        "--action-id",
        "action-independent-search-1",
        "--expected-gap-reduction",
        "closed",
        "--expected-independent-lineage",
        "true",
        "--expected-counterevidence",
        "false",
        "--expected-cost",
        "0.3",
        "--prediction-id",
        "prediction-cli",
        "--output",
        str(prediction_path),
    )
    assert frozen.returncode == 0, frozen.stderr

    run = _run_cli(
        "search-iteration",
        "run",
        "examples/source/starter_researchguard.source.yaml",
        "--model-contract",
        "examples/source/starter_researchguard.source.contract.json",
        "--prediction",
        str(prediction_path),
        "--observation",
        str(observation_path),
        "--actual-cost",
        "0.3",
        "--decision",
        "accept",
        "--candidate-output",
        str(candidate_path),
        "--candidate-model-contract-output",
        str(candidate_contract_path),
        "--receipt-output",
        str(run_receipt_path),
    )
    assert run.returncode == 0, run.stderr
    assert json.loads(run_receipt_path.read_text(encoding="utf-8"))[
        "effective_disposition"
    ] == "accepted"

    rollback = _run_cli(
        "search-iteration",
        "rollback",
        "examples/source/starter_researchguard.source.yaml",
        "--model-contract",
        "examples/source/starter_researchguard.source.contract.json",
        "--accepted-receipt",
        str(run_receipt_path),
        "--output",
        str(restored_path),
        "--output-model-contract",
        str(restored_contract_path),
        "--receipt-output",
        str(rollback_receipt_path),
    )
    assert rollback.returncode == 0, rollback.stderr
    assert json.loads(rollback_receipt_path.read_text(encoding="utf-8"))[
        "effective_disposition"
    ] == "rolled_back"

    overwrite = _run_cli(
        "search-iteration",
        "freeze",
        "examples/source/starter_researchguard.source.yaml",
        "--model-contract",
        "examples/source/starter_researchguard.source.contract.json",
        "--action-id",
        "action-independent-search-1",
        "--expected-gap-reduction",
        "none",
        "--expected-independent-lineage",
        "false",
        "--expected-counterevidence",
        "false",
        "--expected-cost",
        "0.3",
        "--output",
        "examples/source/starter_researchguard.source.yaml",
    )
    assert overwrite.returncode == 2
    assert "cannot overwrite an input" in overwrite.stderr


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "researchguard", "source", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
