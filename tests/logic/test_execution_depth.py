from __future__ import annotations

import json
from pathlib import Path

from researchguard.logic import (
    PerturbationPlanItem,
    build_conclusion_tournament,
    compute_depth_coverage,
    evaluate_model,
    evaluate_perturbation_effectiveness,
    load_model_from_dict,
    select_perturbation_plan,
)
from researchguard.logic.execution_depth import _build_native_depth_analysis


def _model(*, with_objection: bool = False, with_competitor: bool = False):
    nodes = {
        "C0": {"type": "Claim", "text": "Root", "importance": 1.0},
        "E1": {"type": "Evidence", "text": "Evidence", "confidence": 0.8, "importance": 0.8, "provided": True},
        "W1": {"type": "Warrant", "text": "Mechanism", "confidence": 0.6, "importance": 0.8},
        "A1": {"type": "Assumption", "text": "Declared assumption", "confidence": 0.7, "importance": 0.7},
        "L1": {"type": "Limitation", "text": "Declared boundary", "confidence": 0.7, "importance": 0.7},
        "R_SAFE": {"type": "Rebuttal", "text": "Considered but inactive objection", "active": False, "importance": 0.7},
    }
    edges = [
        {"source": "E1", "target": "C0", "type": "supports"},
        {"source": "W1", "target": "C0", "type": "supports"},
        {"source": "A1", "target": "C0", "type": "depends_on"},
        {"source": "L1", "target": "C0", "type": "qualifies"},
        {"source": "R_SAFE", "target": "C0", "type": "attacks"},
    ]
    if with_objection:
        nodes["R1"] = {"type": "Rebuttal", "text": "Live objection", "active": True, "importance": 0.95}
        edges.append({"source": "R1", "target": "C0", "type": "attacks"})
    if with_competitor:
        nodes["C_ALT"] = {
            "type": "Claim",
            "text": "Alternative",
            "role": "alternative",
            "alternative_to": "C0",
            "importance": 0.9,
        }
        nodes["E_ALT"] = {"type": "Evidence", "confidence": 0.8, "importance": 0.7, "provided": True}
        edges.append({"source": "E_ALT", "target": "C_ALT", "type": "supports"})
    return load_model_from_dict(
        {
            "model": {
                "id": "depth",
                "root_claim": "C0",
                "target_units": [
                    {"unit_id": "unit:depth", "node_ids": list(nodes)}
                ],
                "model_cards": [
                    {
                        "card_id": "card:depth",
                        "node_ids": list(nodes),
                        "importance": 1.0,
                    }
                ],
                "role_dispositions": {"competition": "not_applicable"},
            },
            "nodes": nodes,
            "edges": edges,
        }
    )


def test_native_depth_result_is_model_bound_and_serializable() -> None:
    result = _build_native_depth_analysis(_model(), budget=8)
    payload = result.to_dict()

    assert result.broad_claim_licensed
    assert len(payload["model_fingerprint"]) == 64
    assert payload["coverage"]["semantic_coverage_passed"] is True
    assert payload["perturbation_plan"]
    assert payload["effective_perturbation_count"] >= 1
    assert "native_obligation_evidence" not in payload
    assert "factual truth" in payload["claim_boundary"]


def test_active_important_objection_without_response_blocks_coverage() -> None:
    model = _model(with_objection=True)
    coverage = compute_depth_coverage(model)

    assert coverage.semantic_coverage_passed is False
    assert "R1" in coverage.uncovered_node_ids
    assert next(item for item in coverage.items if item.node_id == "R1").coverage_status == "unresolved_objection"


def test_comparable_competing_conclusion_remains_visible() -> None:
    model = _model(with_competitor=True)
    tournament = build_conclusion_tournament(model)

    assert "C_ALT" in tournament.unresolved_competitor_ids
    assert tournament.status == "bounded"
    assert _build_native_depth_analysis(model, budget=8).broad_claim_licensed is False


def test_explicitly_unresolved_objection_stays_in_tournament_boundary() -> None:
    model = _model(with_objection=True)
    model.nodes["R1"].metadata["disposition"] = "unresolved"

    assert compute_depth_coverage(model).semantic_coverage_passed is True
    tournament = build_conclusion_tournament(model)
    root = next(candidate for candidate in tournament.candidates if candidate.is_root)
    assert "R1" in root.unresolved_objection_ids
    assert tournament.status == "bounded"


def test_model_derived_plan_ranks_high_importance_uncertain_warrant_before_storage_order() -> None:
    model = load_model_from_dict(
        {
            "model": {"id": "ranking", "root_claim": "C0"},
            "nodes": {
                "C0": {"type": "Claim", "importance": 1.0},
                "E_FIRST": {"type": "Evidence", "confidence": 0.95, "importance": 0.1, "provided": True},
                "W_LATE": {"type": "Warrant", "confidence": 0.5, "importance": 1.0},
            },
            "edges": [
                {"source": "E_FIRST", "target": "C0", "type": "supports"},
                {"source": "W_LATE", "target": "C0", "type": "supports"},
            ],
        }
    )

    plan = select_perturbation_plan(model, budget=2)
    assert plan[0].node_id == "W_LATE"


def test_inert_mutation_is_recorded_but_not_counted_as_depth() -> None:
    model = _model(with_objection=True)
    result = evaluate_model(model)
    plan = (
        PerturbationPlanItem(
            node_id="R1",
            node_type="Rebuttal",
            mutation="activate_opposition",
            importance=0.95,
            uncertainty=0.0,
            centrality=0.25,
            priority=1.0,
            reasons=("already active",),
        ),
    )

    effects = evaluate_perturbation_effectiveness(model, plan, result)
    assert effects[0].effective is False
    assert effects[0].state_changed is False
    assert effects[0].support_path_changed is False


def test_plain_shallow_inventory_still_has_real_role_gaps() -> None:
    model = load_model_from_dict({
        "model": {"id": "plain-shallow", "root_claim": "C0"},
        "nodes": {
            "C0": {"type": "Claim", "importance": 1.0},
            "E1": {"type": "Evidence", "importance": 0.9, "provided": True},
        },
        "edges": [{"source": "E1", "target": "C0", "type": "supports"}],
    })
    result = _build_native_depth_analysis(model, budget=8)

    assert result.coverage_universe.implicit_inventory is True
    assert result.status == "blocked" and result.broad_claim_licensed is False
    assert "target_unit_inventory_empty" not in result.unresolved_gaps
    assert "model_card_inventory_empty" not in result.unresolved_gaps
    assert {"warrant", "assumption", "boundary", "opposition"} <= set(
        result.coverage_universe.role_coverage[0].missing_roles
    )


def test_plain_example_reaches_native_depth_pass() -> None:
    from researchguard.logic import load_model
    from researchguard.logic.execution_depth import model_fingerprint

    path = Path(__file__).resolve().parents[2] / "examples/logic/plain_research_argument.yaml"
    model = load_model(path)
    original = json.loads(json.dumps(model.to_dict()))
    fingerprint = model_fingerprint(model)
    result = _build_native_depth_analysis(model, budget=24)

    assert result.coverage_universe.implicit_inventory is True
    assert result.status == "pass"
    assert result.broad_claim_licensed is True
    assert result.unresolved_gaps == ()
    assert model.to_dict() == original
    assert model_fingerprint(model) == fingerprint
