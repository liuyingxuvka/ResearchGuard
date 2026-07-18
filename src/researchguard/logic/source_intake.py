"""Default material intake for LogicGuard source libraries."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .source_library import SourceLibrary, SourceLibraryError


INTAKE_SNAPSHOT_DIR = "intake_snapshots"
MODEL_FIELDS = ("claim", "evidence", "warrant", "method", "result", "scope", "limitation", "rebuttal", "locator")
NODE_FIELDS = ("claim", "evidence", "warrant", "method", "result", "limitation", "rebuttal")


@dataclass(frozen=True)
class IntakeMaterial:
    kind: str
    value: str
    title: str = ""
    authors: tuple[str, ...] = ()
    year: str = ""
    source_date: str = ""
    coverage_period: str = ""
    doi: str = ""
    url: str = ""
    modeling_hints: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def file(cls, path: str | Path, **kwargs: Any) -> "IntakeMaterial":
        return cls(kind="file", value=str(path), **kwargs)

    @classmethod
    def text(cls, text: str, **kwargs: Any) -> "IntakeMaterial":
        return cls(kind="text", value=text, **kwargs)

    @classmethod
    def url_snapshot(cls, url: str, text: str = "", **kwargs: Any) -> "IntakeMaterial":
        return cls(kind="url", value=text, url=url, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["authors"] = list(self.authors)
        data["modeling_hints"] = dict(self.modeling_hints)
        return {key: value for key, value in data.items() if value not in ("", [], (), {})}


@dataclass(frozen=True)
class IntakeOptions:
    library_root: str | Path = ".logicguard-library"
    project_id: str = ""
    project_topic: str = ""
    snapshot_dir: str = INTAKE_SNAPSHOT_DIR


@dataclass(frozen=True)
class IntakeMaterialResult:
    kind: str
    source_id: str = ""
    title: str = ""
    source_path: str = ""
    created: bool = False
    reused_existing: bool = False
    project_id: str = ""
    project_assignment: str = "uncategorized"
    model_path: str = ""
    modeling_status: str = "skipped"
    extracted_fields: tuple[str, ...] = ()
    error: str = ""
    skipped: bool = False
    skip_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["extracted_fields"] = list(self.extracted_fields)
        return {key: value for key, value in data.items() if value not in ("", [], (), None)}


@dataclass(frozen=True)
class IntakeResult:
    library_root: str
    materials: tuple[IntakeMaterialResult, ...]

    @property
    def summary(self) -> dict[str, int]:
        return {
            "total": len(self.materials),
            "saved": sum(1 for item in self.materials if item.created),
            "reused": sum(1 for item in self.materials if item.reused_existing),
            "project_assigned": sum(1 for item in self.materials if item.project_assignment == "project"),
            "uncategorized": sum(1 for item in self.materials if item.project_assignment == "uncategorized" and not item.skipped),
            "modeled": sum(1 for item in self.materials if item.modeling_status in {"modeled", "reused_model"}),
            "partial": sum(1 for item in self.materials if item.modeling_status == "partial"),
            "errors": sum(1 for item in self.materials if item.error),
            "skipped": sum(1 for item in self.materials if item.skipped),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "library_root": self.library_root,
            "summary": self.summary,
            "materials": [item.to_dict() for item in self.materials],
        }

    def format_text(self) -> str:
        summary = self.summary
        return (
            "Intake complete: "
            f"{summary['saved']} saved, "
            f"{summary['reused']} reused, "
            f"{summary['project_assigned']} assigned to projects, "
            f"{summary['uncategorized']} uncategorized, "
            f"{summary['modeled']} modeled, "
            f"{summary['partial']} partial, "
            f"{summary['errors']} errors, "
            f"{summary['skipped']} skipped."
        )


Extractor = Callable[[IntakeMaterial, Path], Mapping[str, str]]


def intake_materials(
    materials: Iterable[IntakeMaterial],
    *,
    options: IntakeOptions | None = None,
    extractor: Extractor | None = None,
) -> IntakeResult:
    opts = options or IntakeOptions()
    library = SourceLibrary(opts.library_root)
    results = tuple(_intake_one(library, material, opts, extractor or _extract_logic_fields) for material in materials)
    return IntakeResult(library_root=str(library.root), materials=results)


def _intake_one(library: SourceLibrary, material: IntakeMaterial, options: IntakeOptions, extractor: Extractor) -> IntakeMaterialResult:
    try:
        source_file, title, import_url = _material_source_file(library, material, options)
    except SourceLibraryError as exc:
        return IntakeMaterialResult(kind=material.kind, skipped=True, skip_reason=str(exc), error=str(exc))

    import_result = library.import_source(
        source_file,
        title=title,
        authors=material.authors,
        year=material.year,
        source_date=material.source_date,
        coverage_period=material.coverage_period,
        doi=material.doi,
        url=import_url,
    )
    source = import_result.source
    project_id = _assign_project(library, source.source_id, options)
    project_assignment = "project" if project_id else "uncategorized"
    model_path = library.source_model_path(source.source_id)
    model_existed = model_path.exists()
    modeling_status = "reused_model" if model_existed else "partial"
    extracted_fields: tuple[str, ...] = ()
    error = ""

    try:
        if not model_existed:
            model_path = library.create_source_model(source.source_id, title=source.title or title)
        fields = _clean_fields(extractor(material, source_file))
        if fields and not model_existed:
            model_path = library.create_source_model(source.source_id, title=source.title or title, **fields)
            extracted_fields = tuple(key for key in NODE_FIELDS if fields.get(key))
            modeling_status = "modeled" if extracted_fields else "partial"
        elif model_existed:
            modeling_status = "reused_model"
        else:
            modeling_status = "partial"
    except Exception as exc:
        error = str(exc)
        modeling_status = "error"

    return IntakeMaterialResult(
        kind=material.kind,
        source_id=source.source_id,
        title=source.title,
        source_path=source.source_path,
        created=import_result.created,
        reused_existing=import_result.reused_existing,
        project_id=project_id,
        project_assignment=project_assignment,
        model_path=str(model_path),
        modeling_status=modeling_status,
        extracted_fields=extracted_fields,
        error=error,
    )


def _assign_project(library: SourceLibrary, source_id: str, options: IntakeOptions) -> str:
    if not options.project_id:
        return ""
    try:
        project = library.require_project(options.project_id)
    except SourceLibraryError:
        project = library.create_project(options.project_id, topic=options.project_topic or options.project_id)
    library.select_source(project.project_id, source_id)
    return project.project_id


def _material_source_file(library: SourceLibrary, material: IntakeMaterial, options: IntakeOptions) -> tuple[Path, str, str]:
    kind = material.kind.lower()
    if kind in {"file", "model"}:
        path = Path(material.value)
        if not path.exists() or not path.is_file():
            raise SourceLibraryError(f"Source file not found: {path}")
        return path, material.title or path.stem, material.url
    if kind == "text":
        text = material.value.strip()
        if not text:
            raise SourceLibraryError("Text material is empty")
        title = material.title or _title_from_text(text)
        return _write_snapshot(library, options, title=title, body=text, suffix=".md"), title, material.url
    if kind == "url":
        if not material.url:
            raise SourceLibraryError("URL material requires a url")
        body = material.value.strip() or f"Source URL: {material.url}"
        title = material.title or material.url.rstrip("/").split("/")[-1] or material.url
        snapshot_body = f"# {title}\n\nSource URL: {material.url}\n\n{body}\n"
        return _write_snapshot(library, options, title=title, body=snapshot_body, suffix=".md"), title, material.url
    raise SourceLibraryError(f"Unsupported intake material kind: {material.kind}")


def _write_snapshot(library: SourceLibrary, options: IntakeOptions, *, title: str, body: str, suffix: str) -> Path:
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    snapshot_dir = library.root / options.snapshot_dir
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_dir / f"{_slug(title) or 'intake'}-{digest[:12]}{suffix}"
    if not path.exists() or path.read_text(encoding="utf-8") != body:
        path.write_text(body, encoding="utf-8")
    return path


def _extract_logic_fields(material: IntakeMaterial, source_file: Path) -> Mapping[str, str]:
    fields = _clean_fields(material.modeling_hints)
    text = _read_text_for_extraction(material, source_file)
    for key, value in _parse_labeled_fields(text).items():
        fields.setdefault(key, value)
    return fields


def _read_text_for_extraction(material: IntakeMaterial, source_file: Path) -> str:
    if material.kind.lower() in {"text", "url"}:
        return material.value
    if source_file.suffix.lower() not in {".txt", ".md", ".rst", ".yaml", ".yml", ".json"}:
        return ""
    try:
        return source_file.read_text(encoding="utf-8")[:200_000]
    except UnicodeDecodeError:
        return ""


def _parse_labeled_fields(text: str) -> dict[str, str]:
    fields: dict[str, list[str]] = {}
    labels = {
        "claim": "claim",
        "claims": "claim",
        "evidence": "evidence",
        "warrant": "warrant",
        "method": "method",
        "result": "result",
        "scope": "scope",
        "limitation": "limitation",
        "limitations": "limitation",
        "rebuttal": "rebuttal",
    }
    pattern = re.compile(r"^\s*(?:[-*]\s*)?([A-Za-z][A-Za-z ]{1,30})\s*[:：-]\s*(.+?)\s*$")
    for line in text.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        key = labels.get(match.group(1).strip().lower())
        value = match.group(2).strip()
        if key and value:
            fields.setdefault(key, []).append(value)
    return {key: " | ".join(values) for key, values in fields.items()}


def _clean_fields(raw: Mapping[str, str]) -> dict[str, str]:
    fields = {key: str(raw.get(key, "")).strip() for key in MODEL_FIELDS}
    return {key: value for key, value in fields.items() if value}


def _title_from_text(text: str) -> str:
    for line in text.splitlines():
        clean = line.strip().strip("#").strip()
        if clean:
            return clean[:80]
    return "Intake text"


def _slug(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")
