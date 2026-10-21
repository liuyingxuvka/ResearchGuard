import json
import subprocess
import sys
from pathlib import Path

import pytest

from researchguard.logic.loader import load_model, load_model_from_dict
from researchguard.logic.minimal_sets import license_conclusion, license_model_claim

ROOT = Path(__file__).resolve().parents[2]


def test_support_and_attack_are_deletion_minimal() -> None:
    result = license_conclusion(
        ("s3", "s2", "s1"),
        ("a2", "a1"),
        supports_conclusion=lambda ids: {"s1", "s2"} <= set(ids),
        defeats_conclusion=lambda ids: {"a1"} <= set(ids),
    )
    assert result.wording_license == "qualify"
    assert result.support is not None
    assert result.support.node_ids == ("s1", "s2")
    assert result.support.deletion_minimal
    assert result.attack is not None
    assert result.attack.node_ids == ("a1",)


def test_missing_support_withholds_conclusion() -> None:
    result = license_conclusion(
        ("s1",),
        (),
        supports_conclusion=lambda _ids: False,
        defeats_conclusion=lambda _ids: False,
    )
    assert result.wording_license == "withhold"


def test_model_claim_sets_come_from_the_model_evaluator() -> None:
    model = load_model_from_dict(
        {
            "model": {"id": "m", "root_claim": "C"},
            "nodes": {
                "C": {"type": "Claim", "text": "c", "confidence": 0.8},
                "E1": {"type": "Evidence", "text": "e1", "confidence": 0.9},
                "E2": {"type": "Evidence", "text": "e2", "confidence": 0.9},
                "R": {"type": "Rebuttal", "text": "r", "confidence": 0.9, "active": False},
            },
            "edges": [
                {"source": "E1", "target": "C", "type": "supports", "weight": 0.9},
                {"source": "E2", "target": "C", "type": "supports", "weight": 0.9},
                {"source": "R", "target": "C", "type": "attacks", "weight": 0.9},
            ],
            "acceptance": {"C": {"any_of": ["E1", "E2"], "no_undefeated_rebuttal": True}},
        }
    )
    result = license_model_claim(model, "C")
    assert result.wording_license == "qualify"
    assert result.support is not None and result.support.node_ids == ("E2",)
    assert result.attack is not None and result.attack.node_ids == ("R",)
    with pytest.raises(ValueError, match="not a Claim"):
        license_model_claim(model, "E1")


def test_minimal_sets_cli_prints_the_license() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "researchguard", "logic", "minimal-sets",
         "examples/logic/structured_artifact_deck.yaml", "--claim", "C1"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["wording_license"] == "assert"
    assert payload["support"]["node_ids"] == ["E1", "L1", "W1"]
    assert payload["support"]["deletion_minimal"] is True
