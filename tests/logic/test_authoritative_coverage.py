from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from researchguard.logic import (
    build_argument_coverage_universe,
    load_model_from_dict,
)
from researchguard.logic.execution_depth import _build_native_depth_analysis


build_logic_depth_receipt = _build_native_depth_analysis


def _role_complete_data() -> dict:
    return {
        "model": {
            "id": "authoritative",
            "root_claim": "C0",
            "target_units": [
                {
                    "unit_id": "unit:central-argument",
                    "node_ids": ["C0", "E1", "W1", "A1", "L1", "R1"],
                }
            ],
            "model_cards": [
                {
                    "card_id": "card:central-argument",
                    "node_ids": ["C0", "E1", "W1", "A1", "L1", "R1"],
                    "importance": 1.0,
                }
            ],
            "role_dispositions": {"competition": "not_applicable"},
        },
        "nodes": {
            "C0": {"type": "Claim", "text": "Bounded conclusion", "importance": 1.0},
            "E1": {"type": "Evidence", "provided": True, "confidence": 0.9, "importance": 0.8},
            "W1": {"type": "Warrant", "confidence": 0.8, "importance": 0.8},
            "A1": {"type": "Assumption", "confidence": 0.8, "importance": 0.7},
            "L1": {"type": "Limitation", "confidence": 0.8, "importance": 0.7},
            "R1": {"type": "Rebuttal", "active": False, "confidence": 0.8, "importance": 0.7},
        },
        "edges": [
            {"source": "E1", "target": "C0", "type": "supports"},
            {"source": "W1", "target": "C0", "type": "supports"},
            {"source": "A1", "target": "C0", "type": "depends_on"},
            {"source": "L1", "target": "C0", "type": "qualifies"},
            {"source": "R1", "target": "C0", "type": "attacks"},
        ],
    }


def _model(data: dict | None = None):
    return load_model_from_dict(data or _role_complete_data())


def test_role_complete_current_universe_can_license_declared_broad_scope() -> None:
    receipt = build_logic_depth_receipt(_model(), budget=8)

    assert receipt.receipt_version == "researchguard.logic.depth.v2"
    assert receipt.status == "pass"
    assert receipt.broad_claim_licensed is True
    assert receipt.coverage_universe is not None
    assert receipt.coverage_universe.owner_id == "researchguard.logic.authoritative-argument-coverage"
    assert len(receipt.coverage_universe.universe_fingerprint) == 64
    assert receipt.coverage_universe.role_coverage[0].status == "pass"
    assert receipt.coverage_universe.claim_scope.passed is True


def test_root_plus_one_evidence_is_shallow_and_cannot_license_broad_scope() -> None:
    model = load_model_from_dict(
        {
            "model": {"id": "shallow", "root_claim": "C0"},
            "nodes": {
                "C0": {"type": "Claim", "importance": 1.0},
                "E1": {"type": "Evidence", "provided": True, "importance": 0.9},
            },
            "edges": [{"source": "E1", "target": "C0", "type": "supports"}],
        }
    )

    receipt = build_logic_depth_receipt(model, budget=8)

    assert receipt.broad_claim_licensed is False
    assert receipt.status == "blocked"
    assert {"warrant", "assumption", "boundary", "opposition"} <= set(
        receipt.coverage_universe.role_coverage[0].missing_roles
    )


def test_broad_scope_requires_explicit_target_unit_and_card_denominators() -> None:
    data = _role_complete_data()
    data["model"].pop("target_units")
    data["model"].pop("model_cards")

    receipt = build_logic_depth_receipt(_model(data), budget=8)

    assert "target_unit_inventory_empty" in receipt.unresolved_gaps
    assert "model_card_inventory_empty" in receipt.unresolved_gaps
    assert receipt.broad_claim_licensed is False


def test_competing_conclusion_role_must_be_explicitly_covered_or_disposed() -> None:
    data = _role_complete_data()
    data["model"].pop("role_dispositions")

    receipt = build_logic_depth_receipt(_model(data), budget=8)

    root = next(
        row
        for row in receipt.coverage_universe.role_coverage
        if row.card_id == "root_argument"
    )
    assert "competition" in root.missing_roles
    assert "missing_role:root_argument:competition" in receipt.unresolved_gaps
    assert receipt.broad_claim_licensed is False


def test_disconnected_important_node_remains_in_authoritative_denominator() -> None:
    data = _role_complete_data()
    data["nodes"]["D1"] = {"type": "Warrant", "importance": 0.95}
    receipt = build_logic_depth_receipt(_model(data), budget=10)

    assert "D1" in receipt.coverage_universe.important_node_ids
    assert "D1" in receipt.coverage_universe.unresolved_disconnected_node_ids
    assert "disconnected_important:D1" in receipt.unresolved_gaps
    assert receipt.broad_claim_licensed is False


def test_closed_disposition_is_visible_but_unresolved_disposition_still_blocks() -> None:
    data = _role_complete_data()
    data["nodes"]["D1"] = {"type": "Warrant", "importance": 0.95, "disposition": "not_applicable"}
    closed = build_argument_coverage_universe(_model(data))
    assert "D1" in closed.terminally_disposed_disconnected_node_ids

    data["nodes"]["D1"]["disposition"] = "human_review"
    unresolved = build_logic_depth_receipt(_model(data), budget=10)
    assert "D1" in unresolved.coverage_universe.unresolved_disconnected_node_ids
    assert unresolved.broad_claim_licensed is False


def test_importance_policy_is_target_owned_and_has_no_caller_override() -> None:
    receipt = build_logic_depth_receipt(_model(), budget=8)

    policy = receipt.coverage_universe.importance_policy
    assert policy.profile == "enforced"
    assert policy.effective_threshold == 0.6
    assert policy.requested_threshold is None
    assert policy.threshold_origin == "logicguard_native_enforced"
    assert policy.passed is True
    assert set(receipt.coverage_universe.important_node_ids) == set(_role_complete_data()["nodes"])


def test_nominal_budget_never_drops_a_critical_candidate() -> None:
    data = _role_complete_data()
    data["nodes"]["E1"]["importance"] = 0.95
    data["nodes"]["W1"]["importance"] = 0.95
    receipt = build_logic_depth_receipt(_model(data), budget=1)
    selected = {item.node_id for item in receipt.perturbation_plan}

    assert {"E1", "W1"} <= selected
    assert receipt.critical_perturbation_coverage["selected_count"] == 2
    assert receipt.critical_perturbation_coverage["uncovered_ids"] == []


def test_every_critical_perturbation_must_be_effective() -> None:
    data = _role_complete_data()
    data["nodes"]["R1"].update({"active": True, "importance": 0.95})
    receipt = build_logic_depth_receipt(_model(data), budget=8)

    assert "R1" in receipt.critical_perturbation_coverage["ineffective_ids"]
    assert "ineffective_critical_perturbation:R1" in receipt.unresolved_gaps
    assert receipt.broad_claim_licensed is False


def test_missing_requested_claim_node_blocks_scope_license() -> None:
    receipt = build_logic_depth_receipt(
        _model(),
        budget=8,
        requested_claim_scope_ids=["C0", "C_MISSING"],
    )

    assert receipt.coverage_universe.claim_scope.missing_node_ids == ("C_MISSING",)
    assert "claim_scope_missing:C_MISSING" in receipt.unresolved_gaps
    assert receipt.broad_claim_licensed is False


def test_each_declared_important_card_needs_roles_or_closed_dispositions() -> None:
    data = _role_complete_data()
    data["model"]["model_cards"] = [
        {"card_id": "card-shallow", "node_ids": ["C0", "E1"], "importance": 0.9}
    ]
    receipt = build_logic_depth_receipt(_model(data), budget=8)
    card = next(row for row in receipt.coverage_universe.role_coverage if row.card_id == "card-shallow")

    assert card.status == "blocked"
    assert "warrant" in card.missing_roles
    assert receipt.broad_claim_licensed is False


def test_rich_aggregate_cannot_hide_one_shallow_critical_card() -> None:
    data = _role_complete_data()
    data["nodes"].update(
        {
            "C_KEY": {
                "type": "Claim",
                "importance": 0.95,
                "model_card_id": "card:critical-subclaim",
            },
            "E_KEY": {
                "type": "Evidence",
                "provided": True,
                "confidence": 0.9,
                "importance": 0.95,
                "model_card_id": "card:critical-subclaim",
            },
        }
    )
    data["edges"].extend(
        [
            {"source": "E_KEY", "target": "C_KEY", "type": "supports"},
            {"source": "C_KEY", "target": "C0", "type": "supports"},
        ]
    )
    data["model"]["target_units"].append(
        {
            "unit_id": "unit:critical-subclaim",
            "node_ids": ["C_KEY", "E_KEY"],
        }
    )
    data["model"]["model_cards"].append(
        {
            "card_id": "card:critical-subclaim",
            "node_ids": ["C_KEY", "E_KEY"],
            "importance": 0.95,
        }
    )

    receipt = build_logic_depth_receipt(_model(data), budget=12)
    root = next(
        row
        for row in receipt.coverage_universe.role_coverage
        if row.card_id == "root_argument"
    )
    shallow = next(
        row
        for row in receipt.coverage_universe.role_coverage
        if row.card_id == "card:critical-subclaim"
    )

    assert root.status == "pass"
    assert shallow.status == "blocked"
    assert {"warrant", "boundary", "opposition"} <= set(shallow.missing_roles)
    assert receipt.broad_claim_licensed is False


def test_depth_api_has_no_caller_selectable_profile_or_threshold() -> None:
    with pytest.raises(TypeError):
        build_logic_depth_receipt(_model(), budget=8, profile="bounded")
    with pytest.raises(TypeError):
        build_logic_depth_receipt(_model(), budget=8, important_threshold=0.7)


def test_universe_fingerprint_changes_with_authoritative_inventory() -> None:
    first = build_logic_depth_receipt(_model(), budget=8)
    changed = deepcopy(_role_complete_data())
    changed["model"]["target_unit_ids"] = ["section-1"]
    second = build_logic_depth_receipt(_model(changed), budget=8)

    assert first.coverage_universe.universe_fingerprint != second.coverage_universe.universe_fingerprint
    assert "section-1" in second.coverage_universe.unmodeled_target_unit_ids
    assert second.broad_claim_licensed is False


def test_skill_contract_binds_authoritative_native_receipt_without_parallel_route() -> None:
    root = Path(__file__).resolve().parents[2]
    control = root / "skills" / "logicguard" / ".skillguard"
    contract = json.loads(
        (control / "contract-source.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (control / "check-manifest.json").read_text(encoding="utf-8")
    )
    checks = {row["check_id"]: row for row in contract["checks"]}
    manifest_ids = {item["check_id"] for item in manifest["checks"]}

    assert contract["maintenance_unit_id"] == "unit:researchguard-suite"
    assert contract["member_skill_ids"] == [
        "researchguard",
        "logicguard",
        "sourceguard",
        "traceguard",
    ]
    assert [row["profile_id"] for row in contract["closure_profiles"]] == [
        "enforced",
    ]
    assert set(checks) == manifest_ids == {
        "check:logicguard:consumer-contract",
        "check:logicguard:native-tests",
    }
    assert contract["integration_mode"] == "native-integrated"
    assert contract["may_define_parallel_execution_route"] is False
    assert contract["may_define_skillguard_runtime_route"] is False


def test_low_declared_importance_cannot_remove_an_explicit_shallow_card() -> None:
    data = _role_complete_data()
    data["nodes"].update(
        {
            "C_LOW": {
                "type": "Claim",
                "importance": 0.95,
                "model_card_id": "card:low-self-report",
            },
            "E_LOW": {
                "type": "Evidence",
                "importance": 0.95,
                "provided": True,
                "model_card_id": "card:low-self-report",
            },
        }
    )
    data["edges"].extend(
        [
            {"source": "E_LOW", "target": "C_LOW", "type": "supports"},
            {"source": "C_LOW", "target": "C0", "type": "supports"},
        ]
    )
    data["model"]["model_cards"].append(
        {
            "card_id": "card:low-self-report",
            "node_ids": ["C_LOW", "E_LOW"],
            "importance": 0.1,
        }
    )

    receipt = build_logic_depth_receipt(_model(data), budget=20)
    row = next(
        item
        for item in receipt.coverage_universe.role_coverage
        if item.card_id == "card:low-self-report"
    )

    assert row.declared_importance == 0.1
    assert row.importance >= 0.95
    assert row.status == "blocked"
    assert "missing_role:card:low-self-report:warrant" in receipt.unresolved_gaps
    assert receipt.broad_claim_licensed is False


def test_card_exclusion_requires_closed_reason_and_cannot_hide_active_nodes() -> None:
    unresolved = _role_complete_data()
    unresolved["model"]["model_cards"].append(
        {
            "card_id": "card:excluded-unresolved",
            "node_ids": [],
            "excluded": True,
        }
    )
    unresolved_receipt = build_logic_depth_receipt(_model(unresolved), budget=8)
    assert (
        "model_card_exclusion_unresolved:card:excluded-unresolved"
        in unresolved_receipt.unresolved_gaps
    )

    active = _role_complete_data()
    active["nodes"]["E1"]["model_card_id"] = "card:excluded-active"
    active["model"]["model_cards"] = [
        {
            "card_id": "card:excluded-active",
            "node_ids": ["E1"],
            "excluded": True,
            "exclusion_reason": "claimed background",
            "exclusion_disposition": "not_applicable",
        },
        {
            "card_id": "card:central",
            "node_ids": ["C0", "W1", "A1", "L1", "R1"],
            "importance": 1.0,
        },
    ]
    active_receipt = build_logic_depth_receipt(_model(active), budget=8)
    assert (
        "excluded_model_card_still_structurally_active:E1"
        in active_receipt.unresolved_gaps
    )
    assert active_receipt.broad_claim_licensed is False


def test_closed_disconnected_card_exclusion_is_visible_and_noncontributing() -> None:
    data = _role_complete_data()
    data["nodes"].update(
        {
            "C_BG": {"type": "Claim", "importance": 0.1},
            "E_BG": {"type": "Evidence", "importance": 0.1, "provided": True},
        }
    )
    data["model"]["model_cards"].append(
        {
            "card_id": "card:closed-background",
            "node_ids": ["C_BG", "E_BG"],
            "excluded": True,
            "exclusion_reason": "background outside the requested claim",
            "exclusion_disposition": "not_applicable",
        }
    )

    receipt = build_logic_depth_receipt(_model(data), budget=8)
    row = next(
        item
        for item in receipt.coverage_universe.role_coverage
        if item.card_id == "card:closed-background"
    )
    assert row.status == "excluded_closed"
    assert set(receipt.coverage_universe.excluded_model_card_ids) == {
        "card:closed-background"
    }
    assert receipt.coverage_universe.card_reconciliation_passed is True
    assert "C_BG" not in receipt.coverage_universe.important_node_ids
    assert receipt.broad_claim_licensed is True


def test_each_important_claim_needs_its_own_connected_role_universe() -> None:
    data = _role_complete_data()
    data["nodes"].update(
        {
            "C_CHILD": {"type": "Claim", "importance": 0.95},
            "E_CHILD": {"type": "Evidence", "importance": 0.9, "provided": True},
        }
    )
    data["edges"].extend(
        [
            {"source": "E_CHILD", "target": "C_CHILD", "type": "supports"},
            {"source": "C_CHILD", "target": "C0", "type": "supports"},
        ]
    )
    data["model"]["model_cards"].append(
        {
            "card_id": "card:child",
            "node_ids": ["C_CHILD", "E_CHILD", "W1", "A1", "L1", "R1"],
            "importance": 1.0,
        }
    )

    receipt = build_logic_depth_receipt(_model(data), budget=20)
    child = next(
        item
        for item in receipt.coverage_universe.claim_role_coverage
        if item.claim_id == "C_CHILD"
    )
    assert child.connected_role_node_ids["support"] == ("E_CHILD",)
    assert {"warrant", "assumption", "boundary", "opposition"} <= set(
        child.missing_roles
    )
    assert "claim_role_missing:C_CHILD:warrant" in receipt.unresolved_gaps
    assert receipt.broad_claim_licensed is False


def test_shared_role_node_requires_explicit_consumer_declaration() -> None:
    data = _role_complete_data()
    data["nodes"].update(
        {
            "C_CHILD": {"type": "Claim", "importance": 0.95},
            "W_CHILD": {"type": "Warrant", "importance": 0.8},
            "A_CHILD": {"type": "Assumption", "importance": 0.8},
            "L_CHILD": {"type": "Limitation", "importance": 0.8},
            "R_CHILD": {"type": "Rebuttal", "importance": 0.8, "active": False},
        }
    )
    data["edges"].extend(
        [
            {"source": "E1", "target": "C_CHILD", "type": "supports"},
            {"source": "W_CHILD", "target": "C_CHILD", "type": "supports"},
            {"source": "A_CHILD", "target": "C_CHILD", "type": "depends_on"},
            {"source": "L_CHILD", "target": "C_CHILD", "type": "qualifies"},
            {"source": "R_CHILD", "target": "C_CHILD", "type": "attacks"},
            {"source": "C_CHILD", "target": "C0", "type": "supports"},
        ]
    )
    data["model"]["model_cards"].append(
        {
            "card_id": "card:child",
            "node_ids": ["C_CHILD", "E1", "W_CHILD", "A_CHILD", "L_CHILD", "R_CHILD"],
            "importance": 1.0,
        }
    )

    implicit = build_logic_depth_receipt(_model(data), budget=20)
    child = next(
        item
        for item in implicit.coverage_universe.claim_role_coverage
        if item.claim_id == "C_CHILD"
    )
    assert "E1" in child.implicit_shared_role_node_ids
    assert any(
        gap.startswith("implicit_shared_role_node:E1:")
        for gap in implicit.unresolved_gaps
    )

    data["nodes"]["E1"]["shared_claim_ids"] = ["C0", "C_CHILD"]
    explicit = build_logic_depth_receipt(_model(data), budget=20)
    assert not any(
        gap.startswith("implicit_shared_role_node:E1:")
        for gap in explicit.unresolved_gaps
    )


def test_each_important_claim_has_claim_local_perturbation_coverage() -> None:
    receipt = build_logic_depth_receipt(_model(), budget=1)
    root = next(
        item for item in receipt.claim_perturbation_coverage if item.claim_id == "C0"
    )
    assert root.applicable_node_ids
    assert root.uncovered_node_ids
    assert any(
        gap.startswith("claim_perturbation_uncovered:C0:")
        for gap in receipt.unresolved_gaps
    )
    assert receipt.broad_claim_licensed is False
