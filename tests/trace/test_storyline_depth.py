from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import yaml

from researchguard.trace.evaluator import evaluate_model
from researchguard.trace.schema import TraceGuardModel
from researchguard.trace.storyline_depth import (
    CRITICAL_PERTURBATION_THRESHOLD,
    PerturbationPlanItem,
    _object_depth_coverage,
    evaluate_storyline_depth,
    hypotheses_for_model,
    perturbation_candidates,
    run_single_perturbation,
    select_perturbation_plan,
)
from researchguard.trace.validation import validate_references


ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "trace" / "project_radar_hydrogen_trace.yaml"


def _data() -> dict:
    return deepcopy(yaml.safe_load(EXAMPLE.read_text(encoding="utf-8")))


def _model(data: dict) -> TraceGuardModel:
    model = TraceGuardModel.from_dict(data)
    validate_references(model)
    return model


def test_broad_causal_storyline_without_alternative_records_gap():
    data = _data()
    data["storyline_hypotheses"] = [
        {
            "hypothesis_id": "h_causal",
            "claim": "Funding caused implementation to begin.",
            "role": "primary",
            "trace_ids": ["trace_rhine_h2"],
            "event_ids": ["event_funding", "event_tender"],
            "mechanism_ids": ["m_funding"],
            "confounder_ids": ["c_policy"],
            "importance": 0.9,
            "uncertainty": 0.4,
            "causal": True,
        }
    ]
    data["hypothesis_evidence_links"] = [
        {
            "link_id": "link_causal_funding",
            "hypothesis_id": "h_causal",
            "evidence_id": "ev_funding",
            "polarity": "support",
            "declared_relevance": 1.0,
        },
        {
            "link_id": "link_causal_tender",
            "hypothesis_id": "h_causal",
            "evidence_id": "ev_tender",
            "polarity": "support",
            "declared_relevance": 1.0,
        },
    ]
    data["hypothesis_relations"] = []
    data["causal_mechanisms"] = [
        {
            "mechanism_id": "m_funding",
            "hypothesis_id": "h_causal",
            "description": "Funding enables tender activity.",
            "evidence_ids": ["ev_funding"],
            "declared_relevance": 1.0,
        }
    ]
    data["confounder_reviews"] = [
        {
            "confounder_id": "c_policy",
            "hypothesis_id": "h_causal",
            "description": "Concurrent policy and company planning may explain the timing.",
            "status": "unresolved",
            "evidence_ids": ["ev_company"],
        }
    ]
    data["causal_scopes"] = [
        {
            "scope_id": "scope_causal",
            "description": "This project and the declared evidence period.",
            "time_window": "declared evidence period",
            "boundary_conditions": ["No transfer beyond this project."],
        }
    ]
    data["causal_candidates"] = [
        {
            "causal_id": "candidate_causal",
            "hypothesis_id": "h_causal",
            "cause_event_ids": ["event_funding"],
            "effect_event_ids": ["event_tender"],
            "mechanism_ids": ["m_funding"],
            "confounder_ids": ["c_policy"],
            "alternative_hypothesis_ids": [],
            "scope_id": "scope_causal",
        }
    ]
    data["evidence_ablations"] = []
    data["scenario_perturbations"] = []
    data["expected_sensitivities"] = []

    receipt = evaluate_model(_model(data)).storyline_depth

    assert receipt.closure_status == "BLOCKED"
    assert {"missing_alternative", "unresolved_confounder_review"} <= {
        gap["gap_id"] for gap in receipt.unresolved_gaps
    }


def test_important_causal_storyline_without_mechanism_or_confounder_blocks_depth():
    data = _data()
    data["storyline_hypotheses"][0].update(
        {
            "claim": "Funding caused implementation to begin.",
            "causal": True,
            "bounded_non_causal": False,
            "mechanism_ids": [],
            "confounder_ids": [],
        }
    )
    data["causal_mechanisms"] = []
    data["confounder_reviews"] = []
    data["causal_scopes"] = []
    data["causal_candidates"] = [
        {
            "causal_id": "candidate_incomplete",
            "hypothesis_id": "h_implementation",
            "cause_event_ids": ["event_funding"],
            "effect_event_ids": ["event_tender"],
            "mechanism_ids": [],
            "confounder_ids": [],
            "alternative_hypothesis_ids": ["h_public_signal_only"],
            "scope_id": None,
        }
    ]

    receipt = evaluate_model(_model(data)).storyline_depth

    assert receipt.closure_status == "BLOCKED"
    assert {
        "missing_causal_mechanism",
        "missing_confounder_review",
    } <= {gap["gap_id"] for gap in receipt.unresolved_gaps}


def test_model_derived_selection_prefers_later_central_evidence_over_storage_order():
    data = _data()
    data["sources"].insert(
        0,
        {
            "source_id": "src_low",
            "lineage_id": "lineage_low",
            "independence_group": "group_low",
            "title": "Low-impact context note",
            "source_type": "other",
            "source_reliability": 0.2,
            "source_status": "stable_keep",
        },
    )
    data["evidence"].insert(
        0,
        {
            "evidence_id": "ev_low",
            "source_id": "src_low",
            "raw_text": "Background context unrelated to alternative discrimination.",
            "evidence_type": "news",
            "extraction_confidence": 0.2,
            "evidence_specificity": 0.1,
            "importance": 0.0,
            "supports": [],
            "limits": ["low impact"],
            "warnings": [],
            "usable_as_trace_evidence": True,
        },
    )
    data["events"].insert(
        0,
        {
            "event_id": "event_low",
            "evidence_ids": ["ev_low"],
            "event_type": "unknown",
            "time_interval": {"precision": "unknown", "confidence": 0.0},
            "importance": 0.0,
            "extraction_confidence": 0.1,
        },
    )
    data["traces"][0]["event_ids"].insert(0, "event_low")
    model = _model(data)

    plan, _ = select_perturbation_plan(model, hypotheses_for_model(model))
    removal = next(item for item in plan if item.kind == "evidence_removal")

    assert data["evidence"][0]["evidence_id"] == "ev_low"
    assert removal.target_evidence_id in {"ev_funding", "ev_tender"}
    assert removal.target_evidence_id != "ev_low"
    assert any("alternative_discrimination" in reason for reason in removal.reasons)


def test_unlinked_fixed_event_is_ineffective_and_does_not_count_toward_depth():
    model = _model(_data())
    baseline = evaluate_model(model, include_storyline_depth=False)
    plan = PerturbationPlanItem(
        perturbation_id="fixed-unlinked-event",
        kind="irrelevant_event_injection",
        target_trace_id="trace_rhine_h2",
        target_event_id="event_funding",
        expected_effect="challenge_storyline_support",
        model_derived=False,
    )

    effect, perturbed_model, _ = run_single_perturbation(
        model,
        baseline,
        plan,
        hypotheses_for_model(model),
    )

    assert len(perturbed_model.events) == len(model.events) + 1
    assert not effect.effective
    assert not effect.informative_null
    assert not effect.counts_toward_depth


def test_native_receipt_binds_baseline_alternatives_plan_effects_and_gaps():
    receipt = evaluate_model(_model(_data())).storyline_depth

    assert receipt.schema_version == "researchguard.trace.storyline_depth.v2"
    assert len(receipt.model_fingerprint) == 64
    assert receipt.receipt_id.endswith(receipt.model_fingerprint[:16])
    assert receipt.baseline["hypothesis_snapshots"]
    assert any(row.alternative_ids for row in receipt.alternatives)
    assert receipt.perturbation_plan
    assert receipt.effects
    assert receipt.candidate_universe_fingerprint
    assert receipt.critical_threshold == CRITICAL_PERTURBATION_THRESHOLD
    assert receipt.coverage_counts["critical_uncovered_count"] == 0
    assert receipt.critical_uncovered_ids == ()
    assert receipt.critical_ineffective_ids == ()
    assert receipt.sensitivity_mismatch_ids == ()
    assert receipt.untested_high_impact == ()
    assert receipt.broad_claim_licensed is True
    assert receipt.object_universe_fingerprint
    assert receipt.object_coverage_counts["critical_uncovered_count"] == 0
    assert receipt.object_depth_rows
    assert all(row["status"] == "pass" for row in receipt.object_depth_rows if row["critical"])
    assert all(row["start_middle_end_covered"] for row in receipt.temporal_coverage)
    assert len(receipt.native_obligation_evidence) >= (
        len(receipt.object_depth_rows) + len(receipt.perturbation_plan)
    )
    for observation in receipt.native_obligation_evidence:
        assert observation["target_obligation_ids"]
        assert str(observation["evidence_ref"]).startswith("traceguard:")
        assert len(str(observation["evidence_sha256"])) == 64
        assert str(observation["evidence_sha256"]) == str(observation["evidence_sha256"]).lower()
        assert observation["content"]
    assert receipt.predictive_holdout_status == "not_requested"
    assert receipt.predictive_claim_licensed is False
    assert receipt.covered_claim_scope == "broad"
    assert receipt.effective_perturbation_count == sum(
        effect.counts_toward_depth for effect in receipt.effects
    )
    for effect in receipt.effects:
        assert effect.baseline_inference_receipt_id
        assert effect.perturbed_inference_receipt_id
        assert effect.baseline_problem_fingerprint
        assert effect.perturbed_problem_fingerprint
        assert effect.baseline_problem_fingerprint != effect.perturbed_problem_fingerprint
        assert effect.baseline_solver_id == "osqp.direct.v1"
        assert effect.perturbed_solver_id == effect.baseline_solver_id
        for row in effect.deltas.values():
            assert {"rank", "confidence", "event_support", "contradictions", "gaps"} <= set(row)
    assert "does not prove factual truth" in receipt.claim_boundary


def test_native_obligation_evidence_hash_tracks_exact_evidence_content() -> None:
    baseline = evaluate_model(_model(_data())).storyline_depth
    changed_data = _data()
    changed_data["evidence"][0]["raw_text"] += " Exact evidence content changed."
    changed = evaluate_model(_model(changed_data)).storyline_depth

    object_id = f"evidence:{changed_data['evidence'][0]['evidence_id']}"
    baseline_row = next(
        item for item in baseline.native_obligation_evidence
        if item["native_object_id"] == object_id
    )
    changed_row = next(
        item for item in changed.native_obligation_evidence
        if item["native_object_id"] == object_id
    )
    assert baseline_row["evidence_ref"] == changed_row["evidence_ref"]
    assert baseline_row["evidence_sha256"] != changed_row["evidence_sha256"]


def test_cli_depth_and_model_backed_simulation_expose_native_receipt():
    depth = subprocess.run(
        [sys.executable, "-m", "researchguard", "trace", "depth", str(EXAMPLE), "--pretty"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    receipt = json.loads(depth.stdout)
    assert receipt["schema_version"] == "researchguard.trace.storyline_depth.v2"
    assert receipt["effects"]

    simulation = subprocess.run(
        [
            sys.executable,
            "-m",
            "researchguard", "trace",
            "simulate",
            "--mode",
            "evidence-removal",
            "--model",
            str(EXAMPLE),
            "--pretty",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(simulation.stdout)
    assert payload["perturbation"]["model_derived"] is True
    assert payload["perturbation"]["reasons"]
    assert payload["effect"]["counts_toward_depth"] is True


def test_nonpassing_baseline_cannot_receive_storyline_depth_pass() -> None:
    negative = ROOT / "examples" / "trace" / "operation_before_tender_contradiction.yaml"
    receipt = evaluate_model(_model(yaml.safe_load(negative.read_text(encoding="utf-8")))).storyline_depth

    assert receipt.closure_status == "BLOCKED"
    assert receipt.broad_claim_licensed is False
    assert "baseline_model_not_ok" in {gap["gap_id"] for gap in receipt.unresolved_gaps}


def test_default_plan_executes_every_critical_candidate() -> None:
    model = _model(_data())
    candidates = perturbation_candidates(model, hypotheses_for_model(model))
    critical_ids = {
        item.perturbation_id
        for item in candidates
        if item.priority_score >= CRITICAL_PERTURBATION_THRESHOLD
    }
    receipt = evaluate_model(model).storyline_depth
    executed_ids = {effect.perturbation.perturbation_id for effect in receipt.effects}

    assert critical_ids
    assert critical_ids <= executed_ids
    assert receipt.coverage_counts["critical_count"] == len(critical_ids)
    assert receipt.coverage_counts["executed_count"] == len(receipt.effects)
    assert all(row["required_coverage_ratio"] == 1.0 for row in receipt.coverage_by_kind)


def test_budget_exhaustion_preserves_universe_and_blocks_broad_closure() -> None:
    model = _model(_data())
    baseline = evaluate_model(model, include_storyline_depth=False)
    receipt = evaluate_storyline_depth(model, baseline, max_perturbations=1)

    assert receipt.closure_status == "GAP"
    assert receipt.requested_claim_scope == "broad"
    assert receipt.covered_claim_scope == "bounded"
    assert receipt.broad_claim_licensed is False
    assert receipt.coverage_counts["eligible_count"] > receipt.coverage_counts["executed_count"]
    assert receipt.coverage_counts["critical_uncovered_count"] > 0
    assert receipt.untested_high_impact
    assert "untested_high_impact_perturbations" in {
        gap["gap_id"] for gap in receipt.unresolved_gaps
    }

    cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "researchguard", "trace",
            "depth",
            str(EXAMPLE),
            "--max-perturbations",
            "1",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    cli_receipt = json.loads(cli.stdout)
    assert cli_receipt["closure_status"] == "GAP"
    assert cli_receipt["critical_uncovered_ids"]


def test_bounded_request_never_becomes_broad_license() -> None:
    model = _model(_data())
    baseline = evaluate_model(model, include_storyline_depth=False)
    receipt = evaluate_storyline_depth(model, baseline, requested_claim_scope="bounded")

    assert receipt.closure_status == "PASS"
    assert receipt.requested_claim_scope == "bounded"
    assert receipt.covered_claim_scope == "bounded"
    assert receipt.broad_claim_licensed is False


def test_candidate_universe_fingerprint_changes_with_authoritative_model() -> None:
    first = evaluate_model(_model(_data())).storyline_depth
    changed_data = _data()
    changed_data["events"][0]["importance"] = 0.01
    second = evaluate_model(_model(changed_data)).storyline_depth

    assert first.candidate_universe_fingerprint != second.candidate_universe_fingerprint


def test_single_event_noncausal_trace_cannot_license_broad_depth() -> None:
    data = _data()
    data["traces"][0]["event_ids"] = ["event_funding"]
    data["storyline_hypotheses"] = []
    data["hypothesis_evidence_links"] = []
    data["hypothesis_relations"] = []
    data["causal_mechanisms"] = []
    data["confounder_reviews"] = []
    data["causal_candidates"] = []
    data["evidence_ablations"] = []
    data["scenario_perturbations"] = []
    data["expected_sensitivities"] = []

    receipt = evaluate_model(_model(data)).storyline_depth

    assert receipt.broad_claim_licensed is False
    assert receipt.closure_status == "BLOCKED"
    assert any(
        row["object_type"] == "trace"
        and row["status"] == "fail"
        and "trace_event_count_below_native_floor" in row["findings"]
        for row in receipt.object_depth_rows
    )


def test_one_ineffective_critical_perturbation_is_not_hidden_by_effective_ones() -> None:
    data = _data()
    data["sources"].append(
        {
            "source_id": "src_unlinked",
            "lineage_id": "lineage_unlinked",
            "independence_group": "group_unlinked",
            "title": "Unlinked control source",
            "source_status": "stable_keep",
            "source_reliability": 0.8,
        }
    )
    data["evidence"].append(
        {
            "evidence_id": "ev_unlinked",
            "source_id": "src_unlinked",
            "raw_text": "Unlinked control evidence.",
            "extraction_confidence": 0.9,
            "evidence_specificity": 0.9,
            "importance": 0.1,
            "usable_as_trace_evidence": True,
        }
    )
    data["evidence_ablations"].append(
        {
            "ablation_id": "remove_unlinked_control",
            "hypothesis_id": "h_implementation",
            "trace_id": None,
            "description": "Remove an intentionally unlinked control item.",
            "remove_evidence_ids": ["ev_unlinked"],
            "importance": 0.9,
        }
    )

    receipt = evaluate_model(_model(data)).storyline_depth

    assert "evidence_ablation:remove_unlinked_control" in receipt.critical_ineffective_ids
    assert receipt.broad_claim_licensed is False
    assert "ineffective_critical_perturbations" in {
        gap["gap_id"] for gap in receipt.unresolved_gaps
    }


def test_expected_sensitivity_must_match_same_engine_support_effect() -> None:
    data = _data()
    data["expected_sensitivities"][0]["expected_direction"] = "increase"

    receipt = evaluate_model(_model(data)).storyline_depth

    assert receipt.sensitivity_mismatch_ids == (
        "sensitivity_without_strong_signals",
    )
    assert receipt.broad_claim_licensed is False
    assert "expected_sensitivity_mismatch" in {
        gap["gap_id"] for gap in receipt.unresolved_gaps
    }


def test_critical_event_without_time_blocks_object_depth() -> None:
    data = _data()
    next(item for item in data["events"] if item["event_id"] == "event_funding")["time_interval"] = None

    receipt = evaluate_model(_model(data)).storyline_depth

    assert receipt.closure_status == "BLOCKED"
    assert any(
        row["object_id"] == "event_funding"
        and "event_time_missing_or_unknown" in row["findings"]
        for row in receipt.object_depth_rows
    )


def test_traceguard_never_promotes_internal_perturbation_to_future_prediction() -> None:
    data = _data()
    data["metadata"]["storyline_depth_policy"] = {"prediction_requested": True}

    receipt = evaluate_model(_model(data)).storyline_depth

    assert receipt.predictive_holdout_status == "unsupported_without_native_future_holdout"
    assert receipt.predictive_claim_licensed is False
    assert receipt.closure_status == "BLOCKED"
    assert "predictive_holdout_not_supported" in {
        gap["gap_id"] for gap in receipt.unresolved_gaps
    }


def test_object_universe_fingerprint_changes_with_trace_inventory() -> None:
    first = evaluate_model(_model(_data())).storyline_depth
    changed = _data()
    changed["sources"].append(
        {
            "source_id": "src_extra",
            "lineage_id": "lineage_extra",
            "independence_group": "group_extra",
            "title": "Extra source",
            "source_status": "stable_keep",
            "source_reliability": 0.8,
        }
    )
    changed["evidence"].append(
        {
            "evidence_id": "ev_extra",
            "source_id": "src_extra",
            "raw_text": "Extra low-impact evidence.",
            "extraction_confidence": 0.9,
            "evidence_specificity": 0.9,
            "importance": 0.1,
            "usable_as_trace_evidence": True,
        }
    )
    second = evaluate_model(_model(changed)).storyline_depth

    assert first.object_universe_fingerprint != second.object_universe_fingerprint


def test_low_importance_explicit_trace_cannot_escape_broad_object_denominator() -> None:
    data = _data()
    data["traces"].append(
        {
            "trace_id": "trace_low_importance_shallow",
            "title": "Explicit but shallow secondary trace",
            "trace_type": "storyline",
            "event_ids": ["event_funding"],
            "importance": 0.1,
        }
    )

    receipt = evaluate_model(_model(data)).storyline_depth
    row = next(
        item
        for item in receipt.object_depth_rows
        if item["object_type"] == "trace"
        and item["object_id"] == "trace_low_importance_shallow"
    )

    assert row["critical"] is True
    assert row["status"] == "fail"
    assert "trace_event_count_below_native_floor" in row["findings"]
    assert receipt.broad_claim_licensed is False


def _long_trace_depth_row(
    qualified_indices: set[int],
    *,
    event_count: int = 1000,
    policy: dict | None = None,
) -> dict:
    data = _data()
    event_ids: list[str] = []
    events: list[dict] = []
    for index in range(event_count):
        event_id = f"event_long_{index:04d}"
        event_ids.append(event_id)
        qualified = index in qualified_indices
        events.append(
            {
                "event_id": event_id,
                "evidence_ids": ["ev_funding" if index % 2 == 0 else "ev_tender"],
                "action": "observed project signal",
                "event_type": "project_signal",
                "time_interval": (
                    {
                        "start": f"2025-01-{(index % 28) + 1:02d}T{index:04d}",
                        "precision": "exact_date",
                        "confidence": 0.9,
                    }
                    if qualified
                    else {"precision": "unknown", "confidence": 0.0}
                ),
                "extraction_confidence": 0.8,
                "importance": 0.1,
            }
        )
    data["events"] = events
    data["traces"][0]["event_ids"] = event_ids
    data["storyline_hypotheses"][0]["event_ids"] = sorted(
        event_ids[index] for index in qualified_indices
    )[:3]
    data["storyline_hypotheses"][1]["event_ids"] = sorted(
        event_ids[index] for index in qualified_indices
    )[-3:]
    data["metadata"]["storyline_depth_policy"] = policy or {}
    model = TraceGuardModel.from_dict(data)
    _, _, rows, _, _ = _object_depth_coverage(
        model,
        hypotheses_for_model(model),
        requested_claim_scope="broad",
    )
    return next(
        row
        for row in rows
        if row["object_type"] == "trace" and row["object_id"] == "trace_rhine_h2"
    )


def test_long_trace_cannot_pass_with_only_three_isolated_time_points() -> None:
    row = _long_trace_depth_row({0, 500, 999})

    assert row["critical"] is True
    assert row["status"] == "fail"
    assert row["temporal"]["eligible_event_count"] == 1000
    assert row["temporal"]["qualified_event_count"] == 3
    assert row["temporal"]["required_qualified_event_count"] == 32
    assert "trace_qualified_event_count_below_dynamic_floor" in row["findings"]
    assert "trace_temporal_gap_above_dynamic_ceiling" in row["findings"]


def test_long_trace_cannot_cluster_all_required_points_at_the_start() -> None:
    row = _long_trace_depth_row(set(range(32)))

    assert row["temporal"]["qualified_event_count"] == 32
    assert row["temporal"]["start_middle_end_covered"] is False
    assert "trace_temporal_strata_incomplete" in row["findings"]
    assert "trace_temporal_gap_above_dynamic_ceiling" in row["findings"]


def test_long_trace_accepts_distributed_dynamic_floor_without_requiring_every_point() -> None:
    row = _long_trace_depth_row(set(range(0, 1000, 32)))

    assert row["status"] == "pass"
    assert row["temporal"]["qualified_event_count"] == 32
    assert row["temporal"]["qualified_event_ratio"] < 0.04
    assert row["temporal"]["start_middle_end_covered"] is True
    assert row["temporal"]["maximum_consecutive_unqualified_run"] <= 32


def test_target_policy_can_raise_but_not_lower_native_trace_depth() -> None:
    row = _long_trace_depth_row(
        set(range(0, 1000, 32)),
        policy={"minimum_per_trace_qualified_event_ratio": 0.1},
    )

    assert row["status"] == "fail"
    assert row["temporal"]["required_qualified_event_count"] == 100
    assert "trace_qualified_event_ratio_below_policy_floor" in row["findings"]
