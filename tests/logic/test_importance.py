from __future__ import annotations

import pytest

from researchguard.logic import load_model_from_dict, summarize_importance
from researchguard.logic.loader import ModelLoadError


def test_importance_is_separate_from_confidence_and_weight() -> None:
    model = load_model_from_dict(
        {
            "model": {"id": "importance_test", "root_claim": "C0"},
            "nodes": {
                "C0": {
                    "type": "Claim",
                    "text": "The target claim matters most.",
                    "confidence": 0.4,
                    "importance": 0.95,
                    "salience": "core",
                    "importance_reason": "User-facing decision claim.",
                },
                "E1": {"type": "Evidence", "text": "Supporting evidence.", "confidence": 0.9},
            },
            "edges": [
                {
                    "source": "E1",
                    "target": "C0",
                    "type": "supports",
                    "weight": 0.2,
                    "importance": 0.8,
                    "importance_reason": "Only direct evidence path.",
                }
            ],
        }
    )

    assert model.nodes["C0"].confidence == 0.4
    assert model.nodes["C0"].importance == 0.95
    assert model.edges[0].weight == 0.2
    assert model.edges[0].importance == 0.8

    summary = summarize_importance(model)
    root = summary.records[0]
    assert root.subject_id == "C0"
    assert root.salience == "core"


def test_invalid_importance_is_rejected() -> None:
    with pytest.raises(ModelLoadError, match="numeric field"):
        load_model_from_dict(
            {
                "model": {"id": "bad_importance", "root_claim": "C0"},
                "nodes": {"C0": {"type": "Claim", "text": "Claim", "importance": "high"}},
            }
        )
