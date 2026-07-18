"""Portable package import/export for LogicGuard source libraries."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

import yaml

from .source_library import DEFAULT_MODEL_SUFFIX, LIBRARY_VERSION, ProjectBranch, SourceLibrary, SourceLibraryError, SourceRecord


PACKAGE_FORMAT = "researchguard.logic.source-library-package.v1"
PACKAGE_VERSION = 1
EXPORT_MODE_PROJECT = "project"
EXPORT_MODE_ALL = "all"
EXPORT_MODE_UNCATEGORIZED = "uncategorized"
EXPORT_MODE_SOURCES = "sources"
EXPORT_MODES = {EXPORT_MODE_PROJECT, EXPORT_MODE_ALL, EXPORT_MODE_UNCATEGORIZED, EXPORT_MODE_SOURCES}


@dataclass(frozen=True)
class LibraryPackageExportResult:
    package_path: str
    mode: str
    source_ids: tuple[str, ...]
    project_ids: tuple[str, ...]
    file_count: int
    checksum_count: int

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_ids"] = list(self.source_ids)
        data["project_ids"] = list(self.project_ids)
        return data


@dataclass(frozen=True)
class LibraryPackageImportResult:
    package_path: str
    dry_run: bool
    source_id_map: Mapping[str, str] = field(default_factory=dict)
    created_sources: tuple[str, ...] = ()
    reused_sources: tuple[str, ...] = ()
    created_projects: tuple[str, ...] = ()
    merged_projects: tuple[str, ...] = ()
    copied_models: tuple[str, ...] = ()
    skipped: tuple[dict[str, Any], ...] = ()
    conflicts: tuple[dict[str, Any], ...] = ()

    @property
    def ok(self) -> bool:
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "package_path": self.package_path,
            "dry_run": self.dry_run,
            "source_id_map": dict(self.source_id_map),
            "created_sources": list(self.created_sources),
            "reused_sources": list(self.reused_sources),
            "created_projects": list(self.created_projects),
            "merged_projects": list(self.merged_projects),
            "copied_models": list(self.copied_models),
            "skipped": list(self.skipped),
            "conflicts": list(self.conflicts),
            "counts": {
                "created_sources": len(self.created_sources),
                "reused_sources": len(self.reused_sources),
                "created_projects": len(self.created_projects),
                "merged_projects": len(self.merged_projects),
                "copied_models": len(self.copied_models),
                "skipped": len(self.skipped),
                "conflicts": len(self.conflicts),
            },
        }


def export_library_package(
    root: str | Path,
    output: str | Path,
    *,
    mode: str,
    project_id: str = "",
    source_ids: Iterable[str] = (),
) -> LibraryPackageExportResult:
    """Export a source-library package as one zip archive."""

    if mode not in EXPORT_MODES:
        raise SourceLibraryError(f"Unknown export mode: {mode}")
    library = SourceLibrary(root)
    sources = library.list_sources()
    projects = library.list_projects()
    source_by_id = {source.source_id: source for source in sources}
    project_by_id = {project.project_id: project for project in projects}
    selected_source_ids, selected_project_ids = _resolve_export_scope(
        mode,
        sources=sources,
        projects=projects,
        project_by_id=project_by_id,
        project_id=project_id,
        source_ids=tuple(str(item) for item in source_ids if str(item)),
    )
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    manifest_sources: list[dict[str, Any]] = []
    manifest_projects: list[dict[str, Any]] = []
    checksums: dict[str, str] = {}
    file_count = 0
    source_index = {"version": LIBRARY_VERSION, "sources": []}

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source_id in selected_source_ids:
            source = source_by_id.get(source_id)
            if source is None:
                continue
            source_payload = source.to_dict()
            source_entry = {
                "source_id": source.source_id,
                "metadata": source_payload,
                "metadata_path": "index/sources.json",
                "file_path": "",
                "model_path": "",
                "projects": [project.project_id for project in projects if source.source_id in project.selected_sources],
            }
            source_file = library.root / source.source_path if source.source_path else None
            if source_file is not None and source_file.exists() and source_file.is_file():
                package_file = f"sources/{source.source_id}/{source_file.name}"
                archive.write(source_file, package_file)
                checksums[package_file] = f"sha256:{_file_sha256(source_file)}"
                source_entry["file_path"] = package_file
                file_count += 1
            model_path = library.source_model_path(source.source_id)
            if model_path.exists():
                package_model = f"source_models/{source.source_id}{DEFAULT_MODEL_SUFFIX}"
                archive.write(model_path, package_model)
                checksums[package_model] = f"sha256:{_file_sha256(model_path)}"
                source_entry["model_path"] = package_model
                file_count += 1
            source_index["sources"].append(source_payload)
            manifest_sources.append(source_entry)

        for current_project_id in selected_project_ids:
            project = project_by_id.get(current_project_id)
            if project is None:
                continue
            project_dir = library.project_dir(project.project_id)
            project_paths: dict[str, str] = {}
            for filename in ("topic.json", "selected_sources.json", "node_links.json", "overlays.json"):
                path = project_dir / filename
                if not path.exists():
                    continue
                package_path = f"projects/{project.project_id}/{filename}"
                archive.write(path, package_path)
                checksums[package_path] = f"sha256:{_file_sha256(path)}"
                project_paths[filename.removesuffix(".json")] = package_path
                file_count += 1
            manifest_projects.append(
                {
                    "project_id": project.project_id,
                    "topic": project.topic,
                    "selected_sources": [source_id for source_id in project.selected_sources if source_id in selected_source_ids],
                    "paths": project_paths,
                }
            )

        archive.writestr("index/sources.json", _json_bytes(source_index))
        checksums["index/sources.json"] = f"sha256:{hashlib.sha256(_json_bytes(source_index)).hexdigest()}"
        nodes_path = library.node_index_path
        if nodes_path.exists():
            archive.write(nodes_path, "index/nodes.json")
            checksums["index/nodes.json"] = f"sha256:{_file_sha256(nodes_path)}"
            file_count += 1

        manifest = {
            "package_format": PACKAGE_FORMAT,
            "package_version": PACKAGE_VERSION,
            "library_version": LIBRARY_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "created_by": _created_by(),
            "export": {
                "mode": mode,
                "project_id": project_id,
                "source_ids": selected_source_ids,
            },
            "sources": manifest_sources,
            "projects": manifest_projects,
            "checksums": checksums,
        }
        archive.writestr("manifest.json", _json_bytes(manifest))
        file_count += 2

    return LibraryPackageExportResult(
        package_path=str(output_path),
        mode=mode,
        source_ids=tuple(selected_source_ids),
        project_ids=tuple(selected_project_ids),
        file_count=file_count,
        checksum_count=len(checksums),
    )


def inspect_library_package(package_path: str | Path) -> dict[str, Any]:
    """Read and validate a package manifest without importing it."""

    path = Path(package_path)
    with zipfile.ZipFile(path, "r") as archive:
        _validate_archive_names(archive.namelist())
        manifest = _read_package_json(archive, "manifest.json")
    _validate_manifest(manifest)
    return manifest


def import_library_package(
    root: str | Path,
    package_path: str | Path,
    *,
    dry_run: bool = False,
    include_package_projects: bool = True,
    attach_project_id: str = "",
    attach_project_topic: str = "",
) -> LibraryPackageImportResult:
    """Import a source-library package by safe merge."""

    attach_project_id = _slug(attach_project_id) if attach_project_id else ""

    package = Path(package_path)
    created_sources: list[str] = []
    reused_sources: list[str] = []
    created_projects: list[str] = []
    merged_projects: list[str] = []
    copied_models: list[str] = []
    skipped: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    source_id_map: dict[str, str] = {}

    library = SourceLibrary(root)
    if not dry_run:
        library.init()
    local_sources = library.list_sources()
    local_by_id = {source.source_id: source for source in local_sources}
    local_by_hash = {source.content_hash: source for source in local_sources if source.content_hash}
    existing_ids = set(local_by_id)
    next_sources = list(local_sources)

    with zipfile.ZipFile(package, "r") as archive:
        _validate_archive_names(archive.namelist())
        manifest = _read_package_json(archive, "manifest.json")
        _validate_manifest(manifest)
        package_sources = _read_package_sources(archive)

        for source in package_sources:
            target_id = source.source_id
            reused = False
            if source.content_hash and source.content_hash in local_by_hash:
                target_id = local_by_hash[source.content_hash].source_id
                reused = True
            elif source.source_id in local_by_id:
                local = local_by_id[source.source_id]
                if local.content_hash == source.content_hash:
                    reused = True
                else:
                    conflicts.append(
                        {
                            "kind": "source_id_conflict",
                            "source_id": source.source_id,
                            "local_hash": local.content_hash,
                            "incoming_hash": source.content_hash,
                            "resolution": "imported_with_new_source_id",
                        }
                    )
                    target_id = _unique_id(f"{source.source_id}-imported", existing_ids)
            if target_id != source.source_id:
                source_id_map[source.source_id] = target_id
            else:
                source_id_map.setdefault(source.source_id, target_id)

            if reused:
                reused_sources.append(target_id)
                if not dry_run:
                    next_sources = _merge_source_metadata(next_sources, incoming=source, target_id=target_id)
                continue

            package_file = _manifest_source_entry(manifest, source.source_id).get("file_path") or ""
            target_source_path = ""
            if package_file:
                suffix = Path(PurePosixPath(package_file).name).suffix or Path(source.source_path).suffix
                target = library.sources_dir / f"{target_id}{suffix}"
                target_source_path = str(target.relative_to(library.root))
                if not dry_run:
                    _copy_zip_member(archive, package_file, target)
            record = SourceRecord.from_dict(
                {
                    **source.to_dict(),
                    "source_id": target_id,
                    "source_path": target_source_path,
                    "original_path": source.original_path,
                }
            )
            created_sources.append(target_id)
            existing_ids.add(target_id)
            next_sources.append(record)

        if not dry_run:
            _write_sources(library, next_sources)

        for entry in manifest.get("sources", []) or []:
            if not isinstance(entry, Mapping):
                continue
            old_source_id = str(entry.get("source_id") or "")
            target_source_id = source_id_map.get(old_source_id, old_source_id)
            model_member = str(entry.get("model_path") or "")
            if not model_member:
                continue
            target_model = library.source_model_path(target_source_id)
            package_model_hash = _zip_member_sha256(archive, model_member)
            if target_model.exists():
                if _file_sha256(target_model) == package_model_hash:
                    skipped.append({"kind": "model_exists", "source_id": target_source_id, "resolution": "same_content"})
                else:
                    conflicts.append({"kind": "model_conflict", "source_id": target_source_id, "resolution": "kept_local_model"})
                continue
            copied_models.append(target_source_id)
            if not dry_run:
                raw_model = yaml.safe_load(archive.read(_safe_member_name(model_member)).decode("utf-8")) or {}
                raw_model = _remap_source_model(raw_model, old_source_id=old_source_id, new_source_id=target_source_id)
                _write_yaml(target_model, raw_model)

        if include_package_projects:
            for project_entry in manifest.get("projects", []) or []:
                if not isinstance(project_entry, Mapping):
                    continue
                project_id = _slug(str(project_entry.get("project_id") or ""))
                if not project_id:
                    continue
                project_dir = library.project_dir(project_id)
                project_paths = project_entry.get("paths", {}) if isinstance(project_entry.get("paths"), Mapping) else {}
                incoming_topic = _read_project_member(archive, project_paths, "topic", default={"project_id": project_id, "topic": str(project_entry.get("topic") or "")})
                incoming_selected = _remap_payload(
                    _read_project_member(archive, project_paths, "selected_sources", default={"sources": project_entry.get("selected_sources", []) or []}),
                    source_id_map,
                )
                incoming_links = _remap_payload(_read_project_member(archive, project_paths, "node_links", default={"links": []}), source_id_map)
                incoming_overlays = _remap_payload(_read_project_member(archive, project_paths, "overlays", default={"overlays": []}), source_id_map)
                if project_dir.exists():
                    merged_projects.append(project_id)
                    if not dry_run:
                        _merge_project_files(
                            project_dir,
                            incoming_topic=incoming_topic,
                            incoming_selected=incoming_selected,
                            incoming_links=incoming_links,
                            incoming_overlays=incoming_overlays,
                            conflicts=conflicts,
                        )
                else:
                    created_projects.append(project_id)
                    if not dry_run:
                        project_dir.mkdir(parents=True, exist_ok=True)
                        _write_json(project_dir / "topic.json", incoming_topic)
                        _write_json(project_dir / "selected_sources.json", incoming_selected)
                        _write_json(project_dir / "node_links.json", incoming_links)
                        _write_json(project_dir / "overlays.json", incoming_overlays)
        elif manifest.get("projects"):
            skipped.append({"kind": "package_projects", "resolution": "imported_sources_without_projects"})

        if attach_project_id:
            imported_source_ids = list(dict.fromkeys(source_id_map.values()))
            project_dir = library.project_dir(attach_project_id)
            if project_dir.exists():
                merged_projects.append(attach_project_id)
                incoming_selected = {"sources": imported_source_ids}
                if not dry_run:
                    _merge_project_files(
                        project_dir,
                        incoming_topic={"project_id": attach_project_id, "topic": attach_project_topic},
                        incoming_selected=incoming_selected,
                        incoming_links={"links": []},
                        incoming_overlays={"overlays": []},
                        conflicts=conflicts,
                    )
            else:
                created_projects.append(attach_project_id)
                if not dry_run:
                    project_dir.mkdir(parents=True, exist_ok=True)
                    _write_json(project_dir / "topic.json", {"project_id": attach_project_id, "topic": attach_project_topic})
                    _write_json(project_dir / "selected_sources.json", {"sources": imported_source_ids})
                    _write_json(project_dir / "node_links.json", {"links": []})
                    _write_json(project_dir / "overlays.json", {"overlays": []})

    if not dry_run:
        library.rebuild_index()

    return LibraryPackageImportResult(
        package_path=str(package),
        dry_run=dry_run,
        source_id_map=source_id_map,
        created_sources=tuple(created_sources),
        reused_sources=tuple(dict.fromkeys(reused_sources)),
        created_projects=tuple(dict.fromkeys(created_projects)),
        merged_projects=tuple(dict.fromkeys(merged_projects)),
        copied_models=tuple(copied_models),
        skipped=tuple(skipped),
        conflicts=tuple(conflicts),
    )


def _resolve_export_scope(
    mode: str,
    *,
    sources: list[SourceRecord],
    projects: list[ProjectBranch],
    project_by_id: Mapping[str, ProjectBranch],
    project_id: str,
    source_ids: tuple[str, ...],
) -> tuple[list[str], list[str]]:
    source_order = [source.source_id for source in sources]
    if mode == EXPORT_MODE_ALL:
        return source_order, [project.project_id for project in projects]
    if mode == EXPORT_MODE_PROJECT:
        if not project_id:
            raise SourceLibraryError("project_id is required for project export")
        project = project_by_id.get(_slug(project_id))
        if project is None:
            raise SourceLibraryError(f"Project not found: {project_id}")
        return [source_id for source_id in source_order if source_id in set(project.selected_sources)], [project.project_id]
    if mode == EXPORT_MODE_UNCATEGORIZED:
        selected = {source_id for project in projects for source_id in project.selected_sources}
        return [source_id for source_id in source_order if source_id not in selected], []
    if mode == EXPORT_MODE_SOURCES:
        requested = list(dict.fromkeys(_slug(source_id) for source_id in source_ids if _slug(source_id)))
        missing = [source_id for source_id in requested if source_id not in source_order]
        if missing:
            raise SourceLibraryError(f"Source not found: {', '.join(missing)}")
        return requested, []
    raise SourceLibraryError(f"Unknown export mode: {mode}")


def _read_package_sources(archive: zipfile.ZipFile) -> list[SourceRecord]:
    payload = _read_package_json(archive, "index/sources.json")
    return [SourceRecord.from_dict(item) for item in payload.get("sources", []) or [] if isinstance(item, Mapping)]


def _manifest_source_entry(manifest: Mapping[str, Any], source_id: str) -> Mapping[str, Any]:
    for entry in manifest.get("sources", []) or []:
        if isinstance(entry, Mapping) and str(entry.get("source_id") or "") == source_id:
            return entry
    return {}


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("package_format") != PACKAGE_FORMAT:
        raise SourceLibraryError("Invalid LogicGuard source-library package format")
    if int(manifest.get("package_version") or 0) != PACKAGE_VERSION:
        raise SourceLibraryError(f"Unsupported package version: {manifest.get('package_version')}")


def _read_package_json(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    safe_name = _safe_member_name(name)
    try:
        return json.loads(archive.read(safe_name).decode("utf-8"))
    except KeyError as exc:
        raise SourceLibraryError(f"Package missing {name}") from exc


def _validate_archive_names(names: Iterable[str]) -> None:
    for name in names:
        _safe_member_name(name)


def _safe_member_name(name: str) -> str:
    path = PurePosixPath(str(name))
    if path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:", str(name)):
        raise SourceLibraryError(f"Unsafe package path: {name}")
    return str(path)


def _copy_zip_member(archive: zipfile.ZipFile, member: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with archive.open(_safe_member_name(member), "r") as source:
        target.write_bytes(source.read())


def _zip_member_sha256(archive: zipfile.ZipFile, member: str) -> str:
    return hashlib.sha256(archive.read(_safe_member_name(member))).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(dict(payload), sort_keys=False, allow_unicode=True), encoding="utf-8")


def _write_sources(library: SourceLibrary, sources: list[SourceRecord]) -> None:
    _write_json(library.source_index_path, {"version": LIBRARY_VERSION, "sources": [source.to_dict() for source in sources]})


def _read_json(path: Path, *, default: Mapping[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    return json.loads(path.read_text(encoding="utf-8"))


def _merge_source_metadata(sources: list[SourceRecord], *, incoming: SourceRecord, target_id: str) -> list[SourceRecord]:
    merged: list[SourceRecord] = []
    for source in sources:
        if source.source_id != target_id:
            merged.append(source)
            continue
        data = source.to_dict()
        incoming_data = incoming.to_dict()
        for key, value in incoming_data.items():
            if key == "source_id":
                continue
            if data.get(key) in ("", None, [], ()):
                data[key] = value
        merged.append(SourceRecord.from_dict(data))
    return merged


def _remap_source_model(raw: Any, *, old_source_id: str, new_source_id: str) -> dict[str, Any]:
    payload = _remap_payload(raw, {old_source_id: new_source_id})
    if isinstance(payload, dict):
        model_info = payload.setdefault("model", {})
        if isinstance(model_info, dict):
            model_info["source_id"] = new_source_id
            if str(model_info.get("id") or "") == f"source_{old_source_id}":
                model_info["id"] = f"source_{new_source_id}"
    return payload if isinstance(payload, dict) else {}


def _read_project_member(
    archive: zipfile.ZipFile,
    paths: Mapping[str, Any],
    key: str,
    *,
    default: Mapping[str, Any],
) -> dict[str, Any]:
    member = str(paths.get(key) or "")
    if not member:
        return dict(default)
    try:
        return _read_package_json(archive, member)
    except SourceLibraryError:
        return dict(default)


def _merge_project_files(
    project_dir: Path,
    *,
    incoming_topic: Mapping[str, Any],
    incoming_selected: Mapping[str, Any],
    incoming_links: Mapping[str, Any],
    incoming_overlays: Mapping[str, Any],
    conflicts: list[dict[str, Any]],
) -> None:
    existing_topic = _read_json(project_dir / "topic.json", default={})
    existing_topic_text = str(existing_topic.get("topic") or "")
    incoming_topic_text = str(incoming_topic.get("topic") or "")
    if incoming_topic_text and existing_topic_text and incoming_topic_text != existing_topic_text:
        conflicts.append(
            {
                "kind": "project_topic_conflict",
                "project_id": project_dir.name,
                "resolution": "kept_local_topic",
            }
        )
    elif incoming_topic_text and not existing_topic_text:
        existing_topic["topic"] = incoming_topic_text
        _write_json(project_dir / "topic.json", existing_topic)

    existing_selected = _read_json(project_dir / "selected_sources.json", default={"sources": []})
    selected = _merge_scalar_lists(existing_selected.get("sources", []), incoming_selected.get("sources", []))
    _write_json(project_dir / "selected_sources.json", {"sources": selected})

    existing_links = _read_json(project_dir / "node_links.json", default={"links": []})
    links = _merge_dict_lists(existing_links.get("links", []), incoming_links.get("links", []))
    _write_json(project_dir / "node_links.json", {"links": links})

    existing_overlays = _read_json(project_dir / "overlays.json", default={"overlays": []})
    overlays = _merge_dict_lists(existing_overlays.get("overlays", []), incoming_overlays.get("overlays", []))
    _write_json(project_dir / "overlays.json", {"overlays": overlays})


def _merge_scalar_lists(existing: Any, incoming: Any) -> list[str]:
    merged: list[str] = []
    for item in list(existing or []) + list(incoming or []):
        value = str(item)
        if value and value not in merged:
            merged.append(value)
    return merged


def _merge_dict_lists(existing: Any, incoming: Any) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in list(existing or []) + list(incoming or []):
        if not isinstance(item, Mapping):
            continue
        normalized = json.dumps(item, sort_keys=True)
        if normalized in seen:
            continue
        seen.add(normalized)
        merged.append(dict(item))
    return merged


def _remap_payload(payload: Any, source_id_map: Mapping[str, str]) -> Any:
    if isinstance(payload, Mapping):
        remapped: dict[str, Any] = {}
        for key, value in payload.items():
            if key == "source_id" and isinstance(value, str):
                remapped[key] = source_id_map.get(value, value)
            else:
                remapped[key] = _remap_payload(value, source_id_map)
        return remapped
    if isinstance(payload, list):
        return [source_id_map.get(item, item) if isinstance(item, str) else _remap_payload(item, source_id_map) for item in payload]
    return payload


def _unique_id(base: str, existing: set[str]) -> str:
    clean = _slug(base) or "source"
    if clean not in existing:
        return clean
    index = 2
    while f"{clean}-{index}" in existing:
        index += 1
    return f"{clean}-{index}"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "item"


def _created_by() -> str:
    try:
        from . import __version__

        return f"logicguard {__version__}"
    except Exception:
        return "logicguard"
