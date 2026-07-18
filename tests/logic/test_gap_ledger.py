from __future__ import annotations

from researchguard.logic import build_gap_ledger, evaluate_model, load_model
from researchguard.logic.diagnostics import diagnose_model


def test_gap_ledger_routes_evidence_and_warrant_gaps() -> None:
    model = load_model("examples/logic/engineering_efficiency_argument.yaml")
    result = evaluate_model(model)
    diagnostics = diagnose_model(model, result)

    ledger = build_gap_ledger(model, result=result, diagnostics=diagnostics)
    payload = ledger.to_dict()
    routes = payload["route_summary"]
    items = payload["items"]

    assert payload["model_id"] == "engineering_efficiency_argument"
    assert routes["researchguard.logic.source-library:search"] >= 1
    assert routes["logicguard:argument-repair"] >= 1
    assert any(item["gap_type"] == "warrant_gap" for item in items)
    assert any(item["source_query"] for item in items if item["recommended_route"] == "researchguard.logic.source-library:search")


def test_gap_ledger_preserves_importance_context() -> None:
    model = load_model("examples/logic/structured_artifact_deck.yaml")
    ledger = build_gap_ledger(model, include_simulation=False)

    assert ledger.items
    assert max(item.importance for item in ledger.items) > 0
    assert any(item.salience for item in ledger.items)
