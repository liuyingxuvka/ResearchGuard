from __future__ import annotations

from researchguard.logic import load_model
from researchguard.logic.hierarchy import descendants, hierarchy_roots


def test_hierarchy_descendants_include_argument_block_nodes() -> None:
    model = load_model("examples/logic/engineering_efficiency_argument.yaml")
    assert hierarchy_roots(model) == ["D0"]
    items = descendants(model, "B_results")
    assert "C0" in items
    assert "W1" in items
