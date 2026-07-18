from __future__ import annotations

from researchguard.logic import (
    dependency_trace,
    load_model,
    search_combination_counterexamples,
    search_counterexamples,
    simulate_fragility,
    simulate_model,
)


def test_fragility_analysis_ranks_dependencies() -> None:
    model = load_model("examples/logic/engineering_efficiency_argument.yaml")
    result = simulate_fragility(model, root_claim="C0")
    assert result.mode == "fragility"
    assert result.impacts
    assert result.impacts[0]["node_id"]


def test_counterexample_search_returns_perturbation() -> None:
    model = load_model("examples/logic/ai_generated_answer_audit.yaml")
    result = search_counterexamples(model, root_claim="C0")
    assert result.mode == "counterexample"
    assert result.impacts


def test_dependency_trace_and_rebuttal_activation() -> None:
    model = load_model("examples/logic/policy_argument.yaml")
    trace = dependency_trace(model, root_claim="C0")
    assert any("R1" in row["path"] for row in trace)
    result = simulate_model(model, root_claim="C0", mode="rebuttal-activation", node_id="R1")
    assert result.result_state in {"OUT", "UNDECIDED"}


def test_combination_counterexample_search_is_bounded() -> None:
    model = load_model("examples/logic/engineering_efficiency_argument.yaml")
    result = search_combination_counterexamples(model, root_claim="C0", max_size=2, limit=3)
    assert result.mode == "combination-counterexample"
    assert len(result.impacts) <= 3
    assert all(len(item["minimal_conditions"]) == 2 for item in result.impacts)


def test_simulate_model_combination_counterexample_mode() -> None:
    model = load_model("examples/logic/engineering_efficiency_argument.yaml")
    result = simulate_model(model, root_claim="C0", mode="combination-counterexample", max_size=2)
    assert result.mode == "combination-counterexample"
