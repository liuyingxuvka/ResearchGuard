from __future__ import annotations

from researchguard.logic import evaluate_model, load_model_from_dict


def test_all_of_acceptance_confidence_uses_weakest_dependency() -> None:
    model = load_model_from_dict(
        {
            "model": {"id": "all_of", "root_claim": "C0"},
            "nodes": {
                "C0": {"type": "Claim", "text": "Root"},
                "E1": {"type": "Evidence", "confidence": 0.8},
                "E2": {"type": "Evidence", "confidence": 0.6},
            },
            "acceptance": {"C0": {"all_of": ["E1", "E2"], "threshold": 0.5}},
        }
    )
    result = evaluate_model(model)
    root = result.root()
    assert root is not None
    assert root.state == "IN"
    assert root.confidence == 0.6


def test_at_least_k_acceptance_averages_top_k() -> None:
    model = load_model_from_dict(
        {
            "model": {"id": "k", "root_claim": "C0"},
            "nodes": {
                "C0": {"type": "Claim", "text": "Root"},
                "E1": {"type": "Evidence", "confidence": 0.9},
                "E2": {"type": "Evidence", "confidence": 0.7},
                "E3": {"type": "Evidence", "confidence": 0.1, "missing": True},
            },
            "acceptance": {"C0": {"at_least_k": {"k": 2, "nodes": ["E1", "E2", "E3"]}}},
        }
    )
    root = evaluate_model(model).root()
    assert root is not None
    assert root.state == "IN"
    assert root.confidence == 0.8


def test_warrant_required_blocks_direct_evidence_support() -> None:
    model = load_model_from_dict(
        {
            "model": {"id": "missing_warrant", "root_claim": "C0"},
            "nodes": {
                "C0": {"type": "Claim", "text": "Root"},
                "E1": {"type": "Evidence", "confidence": 0.9},
            },
            "edges": [{"source": "E1", "target": "C0", "type": "supports"}],
            "acceptance": {"C0": {"all_of": ["E1"], "warrant_required": True}},
        }
    )
    root = evaluate_model(model).root()
    assert root is not None
    assert root.state == "UNDECIDED"
    assert "warrant" in root.explanation.lower()
