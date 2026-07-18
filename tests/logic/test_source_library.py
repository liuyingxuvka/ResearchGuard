from __future__ import annotations

import json
from pathlib import Path

import pytest

from researchguard.logic import SourceLibrary, SourceLibraryError, load_model


def test_import_source_deduplicates_by_content_hash(tmp_path: Path) -> None:
    source_file = tmp_path / "paper.txt"
    source_file.write_text("AI tools reduce task time in controlled maintenance tasks.", encoding="utf-8")
    library = SourceLibrary(tmp_path / "library")

    first = library.import_source(source_file, title="AI Maintenance Study", year="2026")
    second = library.import_source(source_file, title="AI Maintenance Study", year="2026")

    assert first.created is True
    assert second.reused_existing is True
    assert first.source.source_id == second.source.source_id
    copied_files = list((tmp_path / "library" / "sources").iterdir())
    assert len(copied_files) == 1


def test_import_source_preserves_temporal_context_and_search_index(tmp_path: Path) -> None:
    source_file = tmp_path / "report.txt"
    source_file.write_text("Report content", encoding="utf-8")
    library = SourceLibrary(tmp_path / "library")

    imported = library.import_source(
        source_file,
        title="Project Stage Report",
        source_date="2024-05",
        coverage_period="2021-2023",
    )
    library.create_source_model(imported.source.source_id, evidence="The report summarizes stage evidence.")

    source = library.require_source(imported.source.source_id)
    assert source.source_date == "2024-05"
    assert source.coverage_period == "2021-2023"
    hits = library.search("2021-2023")
    assert hits[0].entry.coverage_period == "2021-2023"


def test_create_source_model_persists_bilingual_node_metadata(tmp_path: Path) -> None:
    source_file = tmp_path / "paper.txt"
    source_file.write_text("Study content", encoding="utf-8")
    library = SourceLibrary(tmp_path / "library")
    imported = library.import_source(source_file, title="Battery Paper")

    model_path = library.create_source_model(
        imported.source.source_id,
        i18n={
            "en": {"title": "Battery Paper", "claim": "The composite improves performance.", "scope": "tested cells"},
            "zh-CN": {"title": "电池论文", "claim": "复合材料改善性能。", "scope": "测试电池"},
        },
    )

    model = load_model(model_path)
    assert model.title == "Battery Paper"
    assert model.metadata["i18n"]["zh-CN"]["title"] == "电池论文"
    assert model.nodes["C1"].text == "The composite improves performance."
    assert model.nodes["C1"].metadata["i18n"]["zh-CN"]["text"] == "复合材料改善性能。"
    assert model.nodes["C1"].metadata["i18n"]["zh-CN"]["scope"] == "测试电池"


def test_source_model_deepening_search_and_link(tmp_path: Path) -> None:
    source_file = tmp_path / "paper.txt"
    source_file.write_text("Experiment details", encoding="utf-8")
    library = SourceLibrary(tmp_path / "library")
    imported = library.import_source(source_file, title="AI Maintenance Study")

    model_path = library.create_source_model(
        imported.source.source_id,
        claim="AI tools can reduce short-term maintenance task time.",
        evidence="Participants completed simple maintenance tasks faster.",
        warrant="Task time is a bounded proxy for short-term efficiency.",
        scope="simple maintenance tasks",
        limitation="Long-term quality was not measured.",
        locator="abstract",
    )
    model = load_model(model_path)
    assert model.root_claim == "C1"
    assert "E1" in model.nodes

    project = library.create_project("AI Efficiency Paper", topic="AI effects on software engineering efficiency")
    project = library.select_source(project.project_id, imported.source.source_id)
    assert project.selected_sources == (imported.source.source_id,)

    deepening = library.deepen_source(
        imported.source.source_id,
        project_id=project.project_id,
        topic_focus="short-term software engineering efficiency",
        locator="section 4",
        evidence="The study reports lower completion time for the treatment group.",
        limitation="The task set excludes large feature design.",
    )
    assert deepening.node_ids

    hits = library.search("completion time efficiency", project_id=project.project_id)
    assert hits
    assert hits[0].entry.source_id == imported.source.source_id

    source_node = hits[0].entry.node_id
    link = library.link_node(
        project.project_id,
        project_node_id="C3",
        source_id=imported.source.source_id,
        source_node_id=source_node,
        relation="supports",
        note="Supports the short-term efficiency claim.",
    )
    assert link.project_node_id == "C3"
    assert library.list_links(project.project_id, project_node_id="C3") == [link]


def test_anchored_deepening_branch_records_search_context_and_link_provenance(tmp_path: Path) -> None:
    source_file = tmp_path / "paper.txt"
    source_file.write_text("Experiment details", encoding="utf-8")
    library = SourceLibrary(tmp_path / "library")
    imported = library.import_source(source_file, title="Measurement Study")
    library.create_source_model(
        imported.source.source_id,
        claim="Measured flow is not used as the calibration reference.",
        evidence="The measured flow signal is implausible in several operating regions.",
        locator="summary",
    )
    project = library.create_project("Calibration Deck", topic="calibration validation")
    project = library.select_source(project.project_id, imported.source.source_id)

    branch = library.deepen_source(
        imported.source.source_id,
        project_id=project.project_id,
        topic_focus="measured flow plausibility",
        locator="section 4",
        anchor_node_id="C1",
        branch_role="limitation_detail",
        evidence="The sensor response deviates from the expected mass balance trend.",
        limitation="Measured flow is retained only as a plausibility check.",
        importance=0.93,
        salience="risk",
        importance_reason="This limitation controls the calibration reference choice.",
    )

    assert branch.branch_id == "BR1"
    assert branch.anchor_node_id == "C1"
    assert branch.branch_role == "limitation_detail"
    branches = library.list_deepening_branches(imported.source.source_id, anchor_node_id="C1")
    assert branches == [branch]

    hits = library.search("plausibility", project_id=project.project_id, branch_id=branch.branch_id)
    assert hits
    assert hits[0].entry.branch_id == branch.branch_id
    assert hits[0].entry.anchor_node_id == "C1"
    assert hits[0].entry.branch_role == "limitation_detail"

    link = library.link_node(
        project.project_id,
        project_node_id="C7",
        source_id=imported.source.source_id,
        source_node_id=hits[0].entry.node_id,
        relation="qualifies",
    )
    assert link.source_branch_id == branch.branch_id
    assert link.anchor_node_id == "C1"


def test_deepening_branch_inherits_source_temporal_context(tmp_path: Path) -> None:
    source_file = tmp_path / "report.txt"
    source_file.write_text("content", encoding="utf-8")
    library = SourceLibrary(tmp_path / "library")
    imported = library.import_source(
        source_file,
        title="Timeline Report",
        source_date="2025",
        coverage_period="2022-2024",
    )
    library.create_source_model(imported.source.source_id, claim="Claim")
    project = library.create_project("Project", topic="Topic")
    library.select_source(project.project_id, imported.source.source_id)

    branch = library.deepen_source(
        imported.source.source_id,
        project_id=project.project_id,
        topic_focus="timeline",
        locator="p. 1",
        evidence="Evidence",
    )

    assert branch.source_date == "2025"
    assert branch.coverage_period == "2022-2024"
    assert library.list_deepening_branches(imported.source.source_id)[0].source_date == "2025"


def test_deepening_branch_rejects_invalid_anchor_and_audits_legacy_unanchored(tmp_path: Path) -> None:
    source_file = tmp_path / "paper.txt"
    source_file.write_text("content", encoding="utf-8")
    library = SourceLibrary(tmp_path / "library")
    imported = library.import_source(source_file, title="Paper")
    library.create_source_model(imported.source.source_id, claim="Claim")
    project = library.create_project("Project", topic="Topic")
    library.select_source(project.project_id, imported.source.source_id)

    with pytest.raises(SourceLibraryError, match="Anchor node"):
        library.deepen_source(
            imported.source.source_id,
            project_id=project.project_id,
            topic_focus="Topic",
            locator="p. 2",
            anchor_node_id="missing",
            evidence="Evidence",
        )

    branch = library.deepen_source(
        imported.source.source_id,
        project_id=project.project_id,
        topic_focus="legacy topic",
        locator="p. 3",
        evidence="Legacy unanchored evidence.",
    )
    report = library.audit_deepening_branches(imported.source.source_id)
    assert branch.branch_id
    assert any(finding.code == "unanchored_branch" for finding in report.findings)
    assert report.ok is True


def test_project_link_requires_selected_source(tmp_path: Path) -> None:
    source_file = tmp_path / "paper.txt"
    source_file.write_text("content", encoding="utf-8")
    library = SourceLibrary(tmp_path / "library")
    imported = library.import_source(source_file, title="Paper")
    library.create_source_model(imported.source.source_id, claim="Claim")
    project = library.create_project("Project", topic="Topic")

    with pytest.raises(SourceLibraryError, match="not selected"):
        library.link_node(
            project.project_id,
            project_node_id="C1",
            source_id=imported.source.source_id,
            source_node_id="C1",
            relation="supports",
        )


def test_deepening_requires_topic_and_locator(tmp_path: Path) -> None:
    source_file = tmp_path / "paper.txt"
    source_file.write_text("content", encoding="utf-8")
    library = SourceLibrary(tmp_path / "library")
    imported = library.import_source(source_file, title="Paper")
    project = library.create_project("Project", topic="Topic")
    library.select_source(project.project_id, imported.source.source_id)

    with pytest.raises(SourceLibraryError, match="topic_focus"):
        library.deepen_source(imported.source.source_id, project_id=project.project_id, topic_focus="", locator="p. 1", claim="Claim")

    with pytest.raises(SourceLibraryError, match="locator"):
        library.deepen_source(imported.source.source_id, project_id=project.project_id, topic_focus="Topic", locator="", claim="Claim")


def test_project_branch_uses_references_not_source_copies(tmp_path: Path) -> None:
    source_file = tmp_path / "paper.txt"
    source_file.write_text("content", encoding="utf-8")
    library_root = tmp_path / "library"
    library = SourceLibrary(library_root)
    imported = library.import_source(source_file, title="Paper")
    project = library.create_project("Project", topic="Topic")
    library.select_source(project.project_id, imported.source.source_id)

    selected = json.loads((library_root / "projects" / project.project_id / "selected_sources.json").read_text(encoding="utf-8"))
    assert selected == {"sources": [imported.source.source_id]}
    assert not list((library_root / "projects" / project.project_id).glob("*.txt"))


def test_delete_project_removes_project_relationships_without_deleting_sources_or_models(tmp_path: Path) -> None:
    source_file = tmp_path / "paper.txt"
    source_file.write_text("content", encoding="utf-8")
    library_root = tmp_path / "library"
    library = SourceLibrary(library_root)
    imported = library.import_source(source_file, title="Paper")
    library.create_source_model(imported.source.source_id, claim="Claim")
    project = library.create_project("Temporary Project", topic="Temporary")
    library.select_source(project.project_id, imported.source.source_id)

    removed = library.delete_project(project.project_id)

    assert removed.project_id == project.project_id
    with pytest.raises(SourceLibraryError, match="Project not found"):
        library.require_project(project.project_id)
    assert library.require_source(imported.source.source_id).source_id == imported.source.source_id
    assert library.source_model_path(imported.source.source_id).exists()


def test_source_library_preserves_importance_on_nodes_links_and_search(tmp_path: Path) -> None:
    source_file = tmp_path / "paper.txt"
    source_file.write_text("content", encoding="utf-8")
    library = SourceLibrary(tmp_path / "library")
    imported = library.import_source(source_file, title="Paper")
    library.create_source_model(
        imported.source.source_id,
        claim="This is the source main claim.",
        importance=0.91,
        salience="core",
        importance_reason="Main reusable claim.",
    )
    project = library.create_project("Project", topic="Topic")
    project = library.select_source(project.project_id, imported.source.source_id)

    hits = library.search("main claim", project_id=project.project_id)
    assert hits[0].entry.importance == 0.91
    assert hits[0].entry.salience == "core"

    link = library.link_node(
        project.project_id,
        project_node_id="C1",
        source_id=imported.source.source_id,
        source_node_id=hits[0].entry.node_id,
        relation="supports",
        importance=0.88,
        salience="key-evidence",
        importance_reason="Best source support.",
    )
    assert link.importance == 0.88
    stored = library.list_links(project.project_id, project_node_id="C1")[0]
    assert stored.salience == "key-evidence"
