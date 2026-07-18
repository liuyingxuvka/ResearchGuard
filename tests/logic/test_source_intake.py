from __future__ import annotations

import json
from pathlib import Path

from researchguard.logic import IntakeMaterial, IntakeOptions, SourceLibrary, build_library_view_payload, intake_materials, load_model
from researchguard.logic.source_intake import IntakeResult


def test_intake_file_preserves_source_and_creates_shallow_model(tmp_path: Path) -> None:
    source_file = tmp_path / "paper.txt"
    source_file.write_text("plain study text", encoding="utf-8")
    library_root = tmp_path / "library"

    result = intake_materials([IntakeMaterial.file(source_file)], options=IntakeOptions(library_root))

    item = result.materials[0]
    assert result.summary["saved"] == 1
    assert item.created is True
    assert item.project_assignment == "uncategorized"
    assert item.modeling_status == "partial"
    assert (library_root / item.source_path).read_text(encoding="utf-8") == "plain study text"
    model = load_model(item.model_path)
    assert model.metadata["source_id"] == item.source_id
    assert model.root_claim is None


def test_intake_preserves_temporal_context(tmp_path: Path) -> None:
    library_root = tmp_path / "library"

    result = intake_materials(
        [
            IntakeMaterial.text(
                "Claim: The report summarizes the project stage.",
                title="Stage Report",
                source_date="2024",
                coverage_period="2021-2023",
            )
        ],
        options=IntakeOptions(library_root),
    )

    source = SourceLibrary(library_root).require_source(result.materials[0].source_id)
    assert source.source_date == "2024"
    assert source.coverage_period == "2021-2023"
    model = load_model(result.materials[0].model_path)
    assert model.metadata["source_date"] == "2024"


def test_intake_reuses_duplicate_without_extra_source_copy(tmp_path: Path) -> None:
    source_file = tmp_path / "paper.txt"
    source_file.write_text("same content", encoding="utf-8")
    library_root = tmp_path / "library"

    first = intake_materials([IntakeMaterial.file(source_file)], options=IntakeOptions(library_root))
    second = intake_materials([IntakeMaterial.file(source_file)], options=IntakeOptions(library_root))

    assert first.materials[0].source_id == second.materials[0].source_id
    assert second.materials[0].reused_existing is True
    assert len(list((library_root / "sources").iterdir())) == 1


def test_intake_text_snapshot_extracts_labeled_nodes_and_assigns_project(tmp_path: Path) -> None:
    text = "\n".join(
        [
            "Claim: AI tools reduce maintenance task time.",
            "Evidence: Treatment participants finished faster.",
            "Warrant: Task time is a bounded efficiency proxy.",
            "Limitation: Long-term quality was not measured.",
        ]
    )
    library_root = tmp_path / "library"

    result = intake_materials(
        [IntakeMaterial.text(text, title="AI Study")],
        options=IntakeOptions(library_root, project_id="AI Paper", project_topic="AI efficiency"),
    )

    item = result.materials[0]
    assert item.project_assignment == "project"
    assert item.project_id == "ai-paper"
    assert item.modeling_status == "modeled"
    assert item.extracted_fields == ("claim", "evidence", "warrant", "limitation")
    assert SourceLibrary(library_root).require_project("AI Paper").selected_sources == (item.source_id,)
    model = load_model(item.model_path)
    assert model.root_claim == "C1"
    assert model.nodes["E1"].text == "Treatment participants finished faster."


def test_intake_without_project_remains_uncategorized_in_viewer_payload(tmp_path: Path) -> None:
    result = intake_materials(
        [IntakeMaterial.text("Claim: Stored without project.", title="Loose Note")],
        options=IntakeOptions(tmp_path / "library"),
    )

    card = build_library_view_payload(tmp_path / "library")["cards"][0]
    assert result.materials[0].project_assignment == "uncategorized"
    assert card["project_ids"] == []
    assert card["project_label"] == "Uncategorized"


def test_intake_extraction_failure_keeps_saved_source(tmp_path: Path) -> None:
    def failing_extractor(_material: IntakeMaterial, _path: Path) -> dict[str, str]:
        raise RuntimeError("extractor failed")

    library_root = tmp_path / "library"
    result = intake_materials(
        [IntakeMaterial.text("Claim: This should still be stored.", title="Failure Note")],
        options=IntakeOptions(library_root),
        extractor=failing_extractor,
    )

    item = result.materials[0]
    assert item.created is True
    assert item.modeling_status == "error"
    assert "extractor failed" in item.error
    assert SourceLibrary(library_root).require_source(item.source_id).source_id == item.source_id
    assert Path(item.model_path).exists()


def test_intake_result_json_summary_counts(tmp_path: Path) -> None:
    result = intake_materials(
        [
            IntakeMaterial.text("Claim: A", title="A"),
            IntakeMaterial.text("unlabeled", title="B"),
        ],
        options=IntakeOptions(tmp_path / "library"),
    )

    payload = result.to_dict()
    assert isinstance(result, IntakeResult)
    assert payload["summary"]["saved"] == 2
    assert payload["summary"]["modeled"] == 1
    assert payload["summary"]["partial"] == 1
    json.dumps(payload)
