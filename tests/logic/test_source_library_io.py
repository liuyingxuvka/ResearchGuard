from __future__ import annotations

import json
import zipfile
from pathlib import Path

from researchguard.logic import SourceLibrary
from researchguard.logic.source_library_io import (
    export_library_package,
    import_library_package,
    inspect_library_package,
)


def _source_with_project(root: Path, *, filename: str = "study.pdf", title: str = "Study") -> tuple[SourceLibrary, str, str]:
    source_file = root.parent / filename
    source_file.write_text(f"{title} source", encoding="utf-8")
    library = SourceLibrary(root)
    imported = library.import_source(source_file, title=title, year="2026", source_date="2026", coverage_period="2024-2025")
    source_id = imported.source.source_id
    library.create_source_model(
        source_id,
        claim=f"{title} supports the project claim.",
        evidence="The source reports bounded evidence.",
        limitation="The source is limited to the studied setting.",
        importance=0.9,
        salience="core",
    )
    project = library.create_project("Project Alpha", topic="Package IO")
    library.select_source(project.project_id, source_id)
    branch = library.deepen_source(
        source_id,
        project_id=project.project_id,
        topic_focus="important details",
        locator="p. 1",
        anchor_node_id="C1",
        branch_role="supports",
        claim="A branch-level claim.",
        evidence="Branch evidence.",
    )
    library.link_node(
        project.project_id,
        project_node_id="P1",
        source_id=source_id,
        source_node_id=branch.node_ids[0],
        relation="supports",
        source_branch_id=branch.branch_id,
    )
    return library, project.project_id, source_id


def test_export_project_package_contains_sources_models_and_project_files(tmp_path: Path) -> None:
    library_root = tmp_path / "library"
    _library, project_id, source_id = _source_with_project(library_root)
    package = tmp_path / "project.researchguard.logic.zip"

    result = export_library_package(library_root, package, mode="project", project_id=project_id)
    manifest = inspect_library_package(package)

    assert result.source_ids == (source_id,)
    assert result.project_ids == (project_id,)
    assert manifest["package_format"] == "researchguard.logic.source-library-package.v1"
    assert manifest["sources"][0]["model_path"] == f"source_models/{source_id}.logic.yaml"
    assert manifest["projects"][0]["project_id"] == project_id
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "index/sources.json" in names
        assert f"source_models/{source_id}.logic.yaml" in names
        assert f"projects/{project_id}/selected_sources.json" in names
        assert f"projects/{project_id}/node_links.json" in names
        assert f"projects/{project_id}/overlays.json" in names


def test_import_project_package_safe_merge_rebuilds_target_library(tmp_path: Path) -> None:
    source_root = tmp_path / "source-library"
    _library, project_id, source_id = _source_with_project(source_root)
    package = tmp_path / "project.researchguard.logic.zip"
    export_library_package(source_root, package, mode="project", project_id=project_id)
    target_root = tmp_path / "target-library"

    dry_run = import_library_package(target_root, package, dry_run=True)
    assert dry_run.created_sources == (source_id,)
    assert not target_root.exists()

    result = import_library_package(target_root, package)

    target = SourceLibrary(target_root)
    assert result.created_sources == (source_id,)
    assert result.created_projects == (project_id,)
    assert target.require_source(source_id).source_id == source_id
    assert target.require_source(source_id).coverage_period == "2024-2025"
    assert target.require_project(project_id).selected_sources == (source_id,)
    assert target.source_model_path(source_id).exists()
    assert target.list_links(project_id)[0].source_id == source_id
    assert target.search("bounded evidence")


def test_export_uncategorized_only_includes_loose_sources(tmp_path: Path) -> None:
    library_root = tmp_path / "library"
    _library, _project_id, selected_source_id = _source_with_project(library_root, filename="selected.pdf", title="Selected")
    loose_file = tmp_path / "loose.pdf"
    loose_file.write_text("loose source", encoding="utf-8")
    loose = SourceLibrary(library_root).import_source(loose_file, title="Loose", year="2026")
    package = tmp_path / "loose.researchguard.logic.zip"

    result = export_library_package(library_root, package, mode="uncategorized")
    manifest = inspect_library_package(package)

    assert result.source_ids == (loose.source.source_id,)
    assert selected_source_id not in result.source_ids
    assert manifest["projects"] == []


def test_import_conflicting_source_id_remaps_project_references(tmp_path: Path) -> None:
    source_root = tmp_path / "source-library"
    source_file = tmp_path / "incoming.pdf"
    source_file.write_text("incoming", encoding="utf-8")
    source_library = SourceLibrary(source_root)
    incoming = source_library.import_source(source_file, title="Shared", year="2026")
    project = source_library.create_project("Conflict Project", topic="Import conflict")
    source_library.select_source(project.project_id, incoming.source.source_id)
    package = tmp_path / "conflict.researchguard.logic.zip"
    export_library_package(source_root, package, mode="project", project_id=project.project_id)

    target_root = tmp_path / "target-library"
    target_file = tmp_path / "local.pdf"
    target_file.write_text("local different content", encoding="utf-8")
    local = SourceLibrary(target_root).import_source(target_file, title="Shared", year="2026")
    assert local.source.source_id == incoming.source.source_id

    result = import_library_package(target_root, package)
    remapped_source_id = result.source_id_map[incoming.source.source_id]
    selected = SourceLibrary(target_root).require_project(project.project_id).selected_sources

    assert result.conflicts
    assert remapped_source_id != incoming.source.source_id
    assert remapped_source_id in selected
    source_index = json.loads((target_root / "index" / "sources.json").read_text(encoding="utf-8"))
    assert {item["source_id"] for item in source_index["sources"]} >= {incoming.source.source_id, remapped_source_id}


def test_import_package_can_attach_sources_to_current_project_while_preserving_package_project(tmp_path: Path) -> None:
    source_root = tmp_path / "source-library"
    _source_library, package_project_id, source_id = _source_with_project(source_root)
    package = tmp_path / "project.researchguard.logic.zip"
    export_library_package(source_root, package, mode="project", project_id=package_project_id)

    target_root = tmp_path / "target-library"
    target = SourceLibrary(target_root)
    current_project = target.create_project("Current Project", topic="Active UI project")

    result = import_library_package(target_root, package, attach_project_id=current_project.project_id)

    target = SourceLibrary(target_root)
    assert package_project_id in result.created_projects
    assert current_project.project_id in result.merged_projects
    assert target.require_project(package_project_id).selected_sources == (source_id,)
    assert target.require_project(current_project.project_id).selected_sources == (source_id,)
