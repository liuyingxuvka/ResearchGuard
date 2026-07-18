from __future__ import annotations

from researchguard.logic import markdown_to_model, markdown_to_model_dict


def test_markdown_structure_maps_headings_and_labeled_fields() -> None:
    model = markdown_to_model(
        "\n".join(
            [
                "# AI Report",
                "## Evidence",
                "### Controlled task result",
                "Claim: AI tools reduce bounded task time.",
                "Evidence: Participants finished faster.",
                "Warrant: Task time is a bounded proxy.",
                "Limitation: Long-term quality was not measured.",
            ]
        ),
        model_id="ai_report",
        artifact_kind="report",
    )

    assert model.title == "AI Report"
    assert model.root_claim == "C1"
    assert model.children_of("D0") == ["S1"]
    assert model.children_of("S1") == ["B1"]
    assert model.children_of("B1") == ["C1", "E1", "W1", "L1"]
    assert {edge.type for edge in model.edges} == {"supports", "qualifies"}
    assert model.nodes["B1"].metadata["locator"] == "Controlled task result"


def test_markdown_structure_stays_conservative_for_unlabeled_text() -> None:
    raw = markdown_to_model_dict("plain paragraph without labels", model_id="plain")

    assert raw["model"]["root_claim"] is None
    assert raw["nodes"]["D0"]["type"] == "Document"
    assert raw["hierarchy"] == {"D0": []}
