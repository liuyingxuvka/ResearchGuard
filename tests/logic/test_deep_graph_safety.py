from __future__ import annotations

from researchguard.logic.evaluator import detect_argument_cycles, evaluate_model
from researchguard.logic.execution_depth import compute_depth_coverage
from researchguard.logic.hierarchy import descendants
from researchguard.logic.model import Edge, LogicModel, Node
from researchguard.logic import simulator


def test_cycle_detection_handles_a_ten_thousand_node_chain() -> None:
    node_count = 10_000
    model = LogicModel(
        id="deep-support-chain",
        root_claim=f"N{node_count - 1}",
        nodes={f"N{index}": Node(id=f"N{index}", type="Claim") for index in range(node_count)},
        edges=[
            Edge(source=f"N{index}", target=f"N{index + 1}", type="supports")
            for index in range(node_count - 1)
        ],
    )

    assert detect_argument_cycles(model) == []

    model.edges.append(Edge(source=f"N{node_count - 1}", target="N0", type="supports"))
    cycles = detect_argument_cycles(model)

    assert len(cycles) == 1
    assert len(cycles[0]) == node_count + 1
    assert cycles[0][0] == cycles[0][-1] == "N0"


def test_descendants_handles_deep_and_cyclic_hierarchy_once() -> None:
    node_count = 10_000
    model = LogicModel(
        id="deep-hierarchy",
        hierarchy={f"N{index}": [f"N{index + 1}"] for index in range(node_count - 1)},
    )
    model.hierarchy[f"N{node_count - 1}"] = ["N0"]

    result = descendants(model, "N0")

    assert len(result) == node_count - 1
    assert result[0] == "N1"
    assert result[-1] == f"N{node_count - 1}"
    assert "N0" not in result


def test_depth_coverage_inspects_ten_thousand_node_chain_iteratively() -> None:
    node_count = 10_000
    model = LogicModel(
        id="deep-depth-chain",
        root_claim=f"N{node_count - 1}",
        nodes={
            f"N{index}": Node(
                id=f"N{index}",
                type="Claim",
                importance=1.0 if index == node_count - 1 else 0.1,
            )
            for index in range(node_count)
        },
        edges=[
            Edge(
                source=f"N{index}",
                target=f"N{index + 1}",
                type="supports",
                id=f"edge-{index}",
            )
            for index in range(node_count - 1)
        ],
    )

    coverage = compute_depth_coverage(model)

    assert coverage.required_count == 1
    assert coverage.items[0].node_id == model.root_claim


def test_support_cycle_does_not_amplify_seed_confidence() -> None:
    model = LogicModel(
        id="bounded-cycle-confidence",
        root_claim="A",
        nodes={
            "E": Node(id="E", type="Evidence", confidence=0.6),
            "A": Node(id="A", type="Claim", confidence=0.95),
            "B": Node(id="B", type="Claim", confidence=0.95),
        },
        edges=[
            Edge(source="E", target="A", type="supports"),
            Edge(source="A", target="B", type="supports"),
            Edge(source="B", target="A", type="supports"),
        ],
    )

    result = evaluate_model(model)

    assert result.converged
    assert result.cycles == [["A", "B", "A"]]
    assert result.node_results["A"].confidence == 0.6
    assert result.node_results["B"].confidence == 0.6


def test_public_default_perturbation_mutates_the_selected_evidence() -> None:
    model = LogicModel(
        id="public-perturbation",
        nodes={"E": Node(id="E", type="Evidence", confidence=0.8)},
    )

    action = simulator.apply_default_perturbation(model, "E")

    assert action == {"node_id": "E", "action": "remove evidence"}
    assert model.nodes["E"].confidence == 0.0
    assert model.nodes["E"].metadata["provided"] is False
