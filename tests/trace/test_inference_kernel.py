from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from researchguard.trace.inference.osqp_backend import solve_problem
from researchguard.trace.inference.policy import DEFAULT_POLICY
from researchguard.trace.inference.types import (
    CompiledProblem,
    HardConstraint,
    HingeFactor,
    LatentAtom,
    LinearExpression,
    ObservedAtom,
    SolverError,
)
from researchguard.trace.evaluator import evaluate_model
from researchguard.trace.schema import SchemaError, TraceGuardModel
from researchguard.trace.loader import load_model


def _problem(
    *,
    factors: tuple[HingeFactor, ...],
    constraints: tuple[HardConstraint, ...] = (),
) -> CompiledProblem:
    return CompiledProblem(
        schema_id="researchguard.trace.model.v2",
        policy_id=DEFAULT_POLICY.policy_id,
        factor_set_id=DEFAULT_POLICY.factor_set_id,
        solver_id=DEFAULT_POLICY.solver_id,
        observed_atoms=(
            ObservedAtom(
                atom_id="observed",
                value=0.8,
                kind="oracle",
                object_id="oracle",
            ),
        ),
        latent_atoms=(
            LatentAtom(
                atom_id="latent",
                kind="oracle",
                object_id="oracle",
            ),
        ),
        factors=factors,
        hard_constraints=constraints,
    )


def test_squared_hinge_qp_matches_analytic_optimum() -> None:
    problem = _problem(
        factors=(
            HingeFactor(
                factor_id="support",
                family="oracle",
                description="observed support",
                expression=LinearExpression(
                    (("observed", 1.0), ("latent", -1.0))
                ),
                weight=1.0,
                power=2,
                direction="support",
            ),
            HingeFactor(
                factor_id="sparsity",
                family="oracle",
                description="latent sparsity",
                expression=LinearExpression((("latent", 1.0),)),
                weight=1.0,
                power=2,
                direction="oppose",
            ),
        )
    )
    solution = solve_problem(problem, DEFAULT_POLICY)
    assert solution.atom_values["latent"] == pytest.approx(0.4, abs=1e-6)
    assert solution.objective == pytest.approx(0.32, abs=1e-6)
    assert solution.maximum_constraint_violation <= 1e-8


def test_hard_constraint_cannot_be_compensated_by_soft_support() -> None:
    problem = _problem(
        factors=(
            HingeFactor(
                factor_id="strong-support",
                family="oracle",
                description="strong observed support",
                expression=LinearExpression(
                    (("observed", 1.0), ("latent", -1.0))
                ),
                weight=10_000.0,
                power=2,
                direction="support",
            ),
        ),
        constraints=(
            HardConstraint(
                constraint_id="hard-cap",
                description="non-compensable cap",
                expression=LinearExpression((("latent", 1.0),)),
                upper=0.2,
            ),
        ),
    )
    solution = solve_problem(problem, DEFAULT_POLICY)
    assert solution.atom_values["latent"] <= 0.20001


def test_infeasible_problem_fails_closed_without_fallback() -> None:
    problem = _problem(
        factors=(
            HingeFactor(
                factor_id="sparsity",
                family="oracle",
                description="sparsity",
                expression=LinearExpression((("latent", 1.0),)),
                weight=1.0,
            ),
        ),
        constraints=(
            HardConstraint(
                constraint_id="lower",
                description="lower",
                expression=LinearExpression((("latent", 1.0),)),
                lower=0.8,
            ),
            HardConstraint(
                constraint_id="upper",
                description="upper",
                expression=LinearExpression((("latent", 1.0),)),
                upper=0.2,
            ),
        ),
    )
    with pytest.raises(SolverError, match="accepted status"):
        solve_problem(problem, DEFAULT_POLICY)


def _base_payload() -> dict[str, object]:
    return {
        "metadata": {
            "schema_version": "researchguard.trace.model.v2",
            "model_instance_id": "kernel-test",
        },
        "sources": [
            {
                "source_id": "s1",
                "title": "Source 1",
                "source_type": "funding",
                "source_reliability": 0.9,
                "source_status": "stable_keep",
                "lineage_id": "lineage-1",
                "independence_group": "group-1",
            }
        ],
        "evidence": [
            {
                "evidence_id": "e1",
                "source_id": "s1",
                "raw_text": "Supported event.",
                "evidence_type": "funding_award",
                "extraction_confidence": 0.9,
                "evidence_specificity": 0.9,
                "usable_as_trace_evidence": True,
            }
        ],
        "events": [
            {
                "event_id": "event",
                "evidence_ids": ["e1"],
                "event_type": "funding_award",
                "time_interval": {
                    "start": "2024",
                    "precision": "year",
                    "confidence": 0.9,
                },
                "stage_hint": "funded",
            }
        ],
        "traces": [
            {
                "trace_id": "trace",
                "title": "Trace",
                "event_ids": ["event"],
                "current_stage": "funded",
            }
        ],
    }


def test_schema_v2_rejects_retired_event_confidence_output_field() -> None:
    payload = _base_payload()
    payload["events"][0]["confidence"] = 0.8
    with pytest.raises(SchemaError, match="event confidence is retired"):
        TraceGuardModel.from_dict(payload)


def test_duplicate_lineage_does_not_create_independent_support() -> None:
    base = _base_payload()
    baseline = evaluate_model(
        TraceGuardModel.from_dict(base),
        include_storyline_depth=False,
    ).traces[0].support

    duplicated = _base_payload()
    duplicated["sources"].append(
        {
            "source_id": "s-copy",
            "title": "Syndicated copy",
            "source_type": "funding",
            "source_reliability": 0.9,
            "source_status": "stable_keep",
            "lineage_id": "lineage-1",
            "independence_group": "group-1",
            "derived_from_source_ids": ["s1"],
        }
    )
    duplicated["evidence"].append(
        {
            "evidence_id": "e-copy",
            "source_id": "s-copy",
            "raw_text": "Syndicated supported event.",
            "evidence_type": "funding_award",
            "extraction_confidence": 0.9,
            "evidence_specificity": 0.9,
            "usable_as_trace_evidence": True,
        }
    )
    duplicated["events"][0]["evidence_ids"].append("e-copy")
    duplicate_support = evaluate_model(
        TraceGuardModel.from_dict(duplicated),
        include_storyline_depth=False,
    ).traces[0].support
    assert duplicate_support == pytest.approx(baseline, abs=1e-8)

    independent = _base_payload()
    independent["sources"].append(
        {
            "source_id": "s2",
            "title": "Independent source",
            "source_type": "government_database",
            "source_reliability": 0.9,
            "source_status": "stable_keep",
            "lineage_id": "lineage-2",
            "independence_group": "group-2",
        }
    )
    independent["evidence"].append(
        {
            "evidence_id": "e2",
            "source_id": "s2",
            "raw_text": "Independent supported event.",
            "evidence_type": "official_project_page",
            "extraction_confidence": 0.9,
            "evidence_specificity": 0.9,
            "usable_as_trace_evidence": True,
        }
    )
    independent["events"][0]["evidence_ids"].append("e2")
    independent_support = evaluate_model(
        TraceGuardModel.from_dict(independent),
        include_storyline_depth=False,
    ).traces[0].support
    assert independent_support > baseline


def test_causal_license_requires_all_typed_boundaries() -> None:
    payload = _base_payload()
    payload["sources"].extend(
        [
            {
                "source_id": "s2",
                "title": "Outcome source",
                "source_type": "government_database",
                "source_reliability": 0.95,
                "source_status": "stable_keep",
                "lineage_id": "lineage-2",
                "independence_group": "group-2",
            },
            {
                "source_id": "s3",
                "title": "Confounder review",
                "source_type": "government_database",
                "source_reliability": 0.95,
                "source_status": "stable_keep",
                "lineage_id": "lineage-3",
                "independence_group": "group-3",
            },
        ]
    )
    payload["evidence"].extend(
        [
            {
                "evidence_id": "e2",
                "source_id": "s2",
                "raw_text": "Observed outcome.",
                "evidence_type": "official_project_page",
                "extraction_confidence": 0.95,
                "evidence_specificity": 0.95,
                "usable_as_trace_evidence": True,
            },
            {
                "evidence_id": "e3",
                "source_id": "s3",
                "raw_text": "Confounder addressed.",
                "evidence_type": "official_project_page",
                "extraction_confidence": 0.95,
                "evidence_specificity": 0.95,
                "usable_as_trace_evidence": True,
            },
        ]
    )
    payload["events"].append(
        {
            "event_id": "effect",
            "evidence_ids": ["e2"],
            "event_type": "operation_start",
            "time_interval": {
                "start": "2025",
                "precision": "year",
                "confidence": 0.9,
            },
            "stage_hint": "operation",
        }
    )
    payload["traces"][0]["event_ids"].append("effect")
    payload["storyline_hypotheses"] = [
        {
            "hypothesis_id": "h-causal",
            "claim": "Bounded causal candidate",
            "role": "primary",
            "trace_ids": ["trace"],
            "event_ids": ["event", "effect"],
            "mechanism_ids": ["mechanism"],
            "confounder_ids": ["confounder"],
            "importance": 0.9,
            "uncertainty": 0.2,
            "causal": True,
        },
        {
            "hypothesis_id": "h-alternative",
            "claim": "Alternative storyline",
            "role": "alternative",
            "trace_ids": ["trace"],
            "event_ids": ["event", "effect"],
            "importance": 0.6,
            "uncertainty": 0.5,
            "bounded_non_causal": True,
        },
    ]
    payload["hypothesis_evidence_links"] = [
        {
            "link_id": "link-causal",
            "hypothesis_id": "h-causal",
            "evidence_id": "e1",
            "polarity": "support",
        },
        {
            "link_id": "link-alternative",
            "hypothesis_id": "h-alternative",
            "evidence_id": "e2",
            "polarity": "support",
        },
    ]
    payload["hypothesis_relations"] = [
        {
            "relation_id": "relation",
            "left_hypothesis_id": "h-causal",
            "right_hypothesis_id": "h-alternative",
            "relation": "alternative",
        }
    ]
    payload["causal_mechanisms"] = [
        {
            "mechanism_id": "mechanism",
            "hypothesis_id": "h-causal",
            "description": "Evidence-backed mechanism.",
            "evidence_ids": ["e1"],
            "declared_relevance": 1.0,
        }
    ]
    payload["confounder_reviews"] = [
        {
            "confounder_id": "confounder",
            "hypothesis_id": "h-causal",
            "description": "Declared confounder review.",
            "status": "addressed",
            "evidence_ids": ["e3"],
            "importance": 0.9,
        }
    ]
    payload["causal_scopes"] = [
        {
            "scope_id": "scope",
            "description": "Bounded place and time.",
            "time_window": "2024-2025",
            "boundary_conditions": ["declared sources"],
        }
    ]
    payload["causal_candidates"] = [
        {
            "causal_id": "causal",
            "hypothesis_id": "h-causal",
            "cause_event_ids": ["event"],
            "effect_event_ids": ["effect"],
            "mechanism_ids": ["mechanism"],
            "confounder_ids": ["confounder"],
            "alternative_hypothesis_ids": ["h-alternative"],
            "scope_id": "scope",
        }
    ]
    supported_model = TraceGuardModel.from_dict(payload)
    supported = evaluate_model(
        supported_model,
        include_storyline_depth=False,
    ).inference_receipt.hypothesis_projections[0]
    assert supported.causal_status == "supported"

    unresolved_payload = _base_payload()
    unresolved_payload.update(payload)
    unresolved_payload["confounder_reviews"] = [
        {
            **payload["confounder_reviews"][0],
            "status": "unresolved",
        }
    ]
    unresolved = evaluate_model(
        TraceGuardModel.from_dict(unresolved_payload),
        include_storyline_depth=False,
    ).inference_receipt.hypothesis_projections[0]
    assert unresolved.causal_status != "supported"
    assert unresolved.causal_support < supported.causal_support


def test_caller_authored_inference_outputs_fail_closed() -> None:
    payload = _base_payload()
    payload["traces"][0]["validation_status"] = "validated"
    with pytest.raises(SchemaError, match="inference outputs are forbidden"):
        TraceGuardModel.from_dict(payload)


def test_permutation_and_replay_are_deterministic() -> None:
    payload = _base_payload()
    first = evaluate_model(
        TraceGuardModel.from_dict(payload),
        include_storyline_depth=False,
    ).inference_receipt
    permuted = deepcopy(payload)
    permuted["sources"] = list(reversed(permuted["sources"]))
    permuted["evidence"] = list(reversed(permuted["evidence"]))
    second = evaluate_model(
        TraceGuardModel.from_dict(permuted),
        include_storyline_depth=False,
    ).inference_receipt
    replay = evaluate_model(
        TraceGuardModel.from_dict(payload),
        include_storyline_depth=False,
    ).inference_receipt
    assert first.problem_fingerprint == second.problem_fingerprint
    assert first.solution_fingerprint == second.solution_fingerprint
    assert first.to_dict() == replay.to_dict()


def test_irrelevant_unlinked_evidence_does_not_change_trace_support() -> None:
    payload = _base_payload()
    baseline = evaluate_model(
        TraceGuardModel.from_dict(payload),
        include_storyline_depth=False,
    ).traces[0].support
    changed = deepcopy(payload)
    changed["sources"].append(
        {
            "source_id": "irrelevant-source",
            "title": "Irrelevant source",
            "source_type": "official_project_page",
            "source_reliability": 1.0,
            "source_status": "stable_keep",
            "lineage_id": "irrelevant-lineage",
            "independence_group": "irrelevant-group",
        }
    )
    changed["evidence"].append(
        {
            "evidence_id": "irrelevant-evidence",
            "source_id": "irrelevant-source",
            "raw_text": "Strong but unlinked evidence.",
            "evidence_type": "official_project_page",
            "extraction_confidence": 1.0,
            "evidence_specificity": 1.0,
            "usable_as_trace_evidence": True,
        }
    )
    observed = evaluate_model(
        TraceGuardModel.from_dict(changed),
        include_storyline_depth=False,
    ).traces[0].support
    assert observed == pytest.approx(baseline, abs=1e-8)


def test_typed_opposition_reduces_hypothesis_support() -> None:
    payload = _base_payload()
    payload["storyline_hypotheses"] = [
        {
            "hypothesis_id": "h",
            "claim": "Hypothesis",
            "trace_ids": ["trace"],
            "event_ids": ["event"],
            "bounded_non_causal": True,
        }
    ]
    payload["hypothesis_evidence_links"] = [
        {
            "link_id": "support",
            "hypothesis_id": "h",
            "evidence_id": "e1",
            "polarity": "support",
        }
    ]
    supported = evaluate_model(
        TraceGuardModel.from_dict(payload),
        include_storyline_depth=False,
    ).inference_receipt.hypothesis_projections[0].support
    opposed = deepcopy(payload)
    opposed["hypothesis_evidence_links"].append(
        {
            "link_id": "oppose",
            "hypothesis_id": "h",
            "evidence_id": "e1",
            "polarity": "oppose",
        }
    )
    opposed_support = evaluate_model(
        TraceGuardModel.from_dict(opposed),
        include_storyline_depth=False,
    ).inference_receipt.hypothesis_projections[0].support
    assert opposed_support < supported


def test_projection_explanations_are_bound_to_receipt_contributions() -> None:
    from researchguard.trace.inference.engine import verify_inference_receipt

    receipt = evaluate_model(
        TraceGuardModel.from_dict(_base_payload()),
        include_storyline_depth=False,
    ).inference_receipt
    verify_inference_receipt(receipt)
    contribution_ids = {item.factor_id for item in receipt.contributions}
    assert receipt.problem_fingerprint
    assert receipt.solution_fingerprint
    assert receipt.atom_values_fingerprint
    assert receipt.factor_catalog_fingerprint
    assert receipt.hard_constraint_catalog_fingerprint
    assert receipt.provenance_fingerprint
    assert receipt.solver_configuration_fingerprint
    assert receipt.solver_backend == "osqp"
    assert receipt.solver_backend_version
    assert receipt.solver_status in {"solved", "solved inaccurate"}
    assert receipt.primal_residual <= DEFAULT_POLICY.maximum_primal_residual
    assert receipt.dual_residual <= DEFAULT_POLICY.maximum_dual_residual
    assert (
        receipt.maximum_constraint_violation
        <= DEFAULT_POLICY.maximum_constraint_violation
    )
    for projection in (
        *receipt.trace_projections,
        *receipt.hypothesis_projections,
    ):
        assert set(projection.top_support_factor_ids) <= contribution_ids
        assert set(projection.top_opposition_factor_ids) <= contribution_ids


def test_maintained_example_differential_inventory_has_no_unexplained_delta() -> None:
    root = Path(__file__).resolve().parents[2]
    inventory = json.loads(
        (
            root
            / "tests"
            / "trace"
            / "fixtures"
            / "unified_inference_approved_deltas.json"
        ).read_text(
            encoding="utf-8"
        )
    )
    assert inventory["policy_id"] == DEFAULT_POLICY.policy_id
    assert inventory["cases"]
    for row in inventory["cases"]:
        result = evaluate_model(
            load_model(root / row["model"]),
            include_storyline_depth=False,
        )
        projection = next(
            trace for trace in result.traces if trace.trace_id == row["trace_id"]
        )
        assert projection.validation_status == row["current_status"]
        assert row["delta_disposition"]
        assert row["support_min"] <= projection.support <= row["support_max"]
