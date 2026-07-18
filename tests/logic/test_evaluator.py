from __future__ import annotations

from researchguard.logic import evaluate_model, load_model, load_model_from_dict


def test_support_propagation_accepts_claim() -> None:
    model = load_model_from_dict(
        {
            "model": {"id": "support", "root_claim": "C0"},
            "nodes": {
                "C0": {"type": "Claim", "text": "Root"},
                "E1": {"type": "Evidence", "confidence": 0.7},
            },
            "edges": [{"source": "E1", "target": "C0", "type": "supports", "weight": 0.8}],
        }
    )
    root = evaluate_model(model).root()
    assert root is not None
    assert root.state == "IN"
    assert root.confidence == 0.7


def test_attack_and_undercut_make_claim_unresolved() -> None:
    model = load_model("examples/logic/engineering_efficiency_argument.yaml")
    result = evaluate_model(model)
    assert result.node_results["W1"].state == "UNDECIDED"
    assert result.node_results["C0"].state == "UNDECIDED"
    assert result.converged


def test_circular_reasoning_detection() -> None:
    model = load_model_from_dict(
        {
            "model": {"id": "cycle", "root_claim": "C0"},
            "nodes": {
                "C0": {"type": "Claim", "text": "Root"},
                "C1": {"type": "Claim", "text": "Child"},
            },
            "edges": [
                {"source": "C0", "target": "C1", "type": "supports"},
                {"source": "C1", "target": "C0", "type": "supports"},
            ],
        }
    )
    result = evaluate_model(model)
    assert result.cycles
