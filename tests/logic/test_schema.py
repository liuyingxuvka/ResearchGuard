from __future__ import annotations

from pathlib import Path

from researchguard.logic import load_model, load_model_from_dict, validate_model


ROOT = Path(__file__).resolve().parents[2]


def test_all_examples_validate() -> None:
    for path in (ROOT / "examples" / "logic").glob("*.yaml"):
        model = load_model(path)
        result = validate_model(model)
        assert result.ok, f"{path.name}: {result.errors}"


def test_validation_rejects_unknown_edge_target() -> None:
    model = load_model_from_dict(
        {
            "model": {"id": "bad", "root_claim": "C0"},
            "nodes": {"C0": {"type": "Claim", "text": "Root"}},
            "edges": [{"source": "E1", "target": "C0", "type": "supports"}],
        },
        validate=False,
    )
    result = validate_model(model)
    assert not result.ok
    assert any("source" in item for item in result.errors)
