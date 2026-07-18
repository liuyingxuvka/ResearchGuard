"""Source logic library workflow for LogicGuard.

The source library is the second internal LogicGuard flow. It stores source
documents once, lets projects reference those sources, and grows source logic
models through topic-focused deepening.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from .loader import load_model
from .localization import DEFAULT_LANGUAGE, field_i18n, localized_field, normalize_i18n
from .schema import EDGE_TYPES, NODE_TYPES


LIBRARY_VERSION = "1"
DEFAULT_MODEL_SUFFIX = ".logic.yaml"


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    title: str = ""
    authors: tuple[str, ...] = ()
    year: str = ""
    source_date: str = ""
    coverage_period: str = ""
    doi: str = ""
    url: str = ""
    content_hash: str = ""
    source_path: str = ""
    original_path: str = ""
    status: str = "imported"
    possible_duplicates: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["authors"] = list(self.authors)
        data["possible_duplicates"] = list(self.possible_duplicates)
        return {key: value for key, value in data.items() if value not in ("", [], ())}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "SourceRecord":
        return cls(
            source_id=str(raw.get("source_id", "")),
            title=str(raw.get("title", "")),
            authors=tuple(str(item) for item in raw.get("authors", []) or []),
            year=str(raw.get("year", "")),
            source_date=str(raw.get("source_date", "")),
            coverage_period=str(raw.get("coverage_period", "")),
            doi=str(raw.get("doi", "")),
            url=str(raw.get("url", "")),
            content_hash=str(raw.get("content_hash", "")),
            source_path=str(raw.get("source_path", "")),
            original_path=str(raw.get("original_path", "")),
            status=str(raw.get("status", "imported")),
            possible_duplicates=tuple(str(item) for item in raw.get("possible_duplicates", []) or []),
        )


@dataclass(frozen=True)
class SourceImportResult:
    source: SourceRecord
    created: bool
    reused_existing: bool
    possible_duplicates: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "created": self.created,
            "reused_existing": self.reused_existing,
            "possible_duplicates": list(self.possible_duplicates),
        }


@dataclass(frozen=True)
class ProjectBranch:
    project_id: str
    topic: str
    selected_sources: tuple[str, ...] = ()
    argument_model: str = "argument_model.yaml"

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "topic": self.topic,
            "selected_sources": list(self.selected_sources),
            "argument_model": self.argument_model,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ProjectBranch":
        return cls(
            project_id=str(raw.get("project_id", "")),
            topic=str(raw.get("topic", "")),
            selected_sources=tuple(str(item) for item in raw.get("selected_sources", []) or []),
            argument_model=str(raw.get("argument_model", "argument_model.yaml")),
        )


@dataclass(frozen=True)
class IndexEntry:
    source_id: str
    node_id: str
    node_type: str
    text: str
    scope: str = ""
    locator: str = ""
    topic_focus: str = ""
    source_title: str = ""
    source_date: str = ""
    coverage_period: str = ""
    importance: float | None = None
    salience: str = ""
    importance_reason: str = ""
    branch_id: str = ""
    anchor_node_id: str = ""
    anchor_block_id: str = ""
    branch_role: str = ""
    branch_status: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value not in ("", [], (), None)}


@dataclass(frozen=True)
class SearchHit:
    entry: IndexEntry
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {"score": round(self.score, 4), **self.entry.to_dict()}


@dataclass(frozen=True)
class NodeLink:
    project_id: str
    project_node_id: str
    source_id: str
    source_node_id: str
    relation: str
    note: str = ""
    importance: float | None = None
    salience: str = ""
    importance_reason: str = ""
    source_branch_id: str = ""
    anchor_node_id: str = ""
    anchor_block_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value not in ("", [], (), None)}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "NodeLink":
        return cls(
            project_id=str(raw.get("project_id", "")),
            project_node_id=str(raw.get("project_node_id", "")),
            source_id=str(raw.get("source_id", "")),
            source_node_id=str(raw.get("source_node_id", "")),
            relation=str(raw.get("relation", "")),
            note=str(raw.get("note", "")),
            importance=_optional_float(raw.get("importance")),
            salience=str(raw.get("salience", "")),
            importance_reason=str(raw.get("importance_reason", "")),
            source_branch_id=str(raw.get("source_branch_id", "")),
            anchor_node_id=str(raw.get("anchor_node_id", "")),
            anchor_block_id=str(raw.get("anchor_block_id", "")),
        )


@dataclass(frozen=True)
class DeepeningRecord:
    project_id: str
    source_id: str
    topic_focus: str
    locator: str
    node_ids: tuple[str, ...]
    note: str = ""
    branch_id: str = ""
    anchor_node_id: str = ""
    anchor_block_id: str = ""
    branch_role: str = ""
    status: str = "project"
    importance: float | None = None
    salience: str = ""
    importance_reason: str = ""
    source_date: str = ""
    coverage_period: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = {
            "project_id": self.project_id,
            "source_id": self.source_id,
            "topic_focus": self.topic_focus,
            "locator": self.locator,
            "node_ids": list(self.node_ids),
            "note": self.note,
            "branch_id": self.branch_id,
            "anchor_node_id": self.anchor_node_id,
            "anchor_block_id": self.anchor_block_id,
            "branch_role": self.branch_role,
            "status": self.status,
            "importance": self.importance,
            "salience": self.salience,
            "importance_reason": self.importance_reason,
            "source_date": self.source_date,
            "coverage_period": self.coverage_period,
        }
        return {key: value for key, value in data.items() if value not in ("", [], (), None)}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "DeepeningRecord":
        source_id = str(raw.get("source_id", "")).strip()
        if not source_id:
            raise SourceLibraryError(
                "deepening branch source_id is required in the current schema"
            )
        return cls(
            project_id=str(raw.get("project_id", "")),
            source_id=source_id,
            topic_focus=str(raw.get("topic_focus", "")),
            locator=str(raw.get("locator", "")),
            node_ids=tuple(str(item) for item in raw.get("node_ids", []) or []),
            note=str(raw.get("note", "")),
            branch_id=str(raw.get("branch_id", "")),
            anchor_node_id=str(raw.get("anchor_node_id", "")),
            anchor_block_id=str(raw.get("anchor_block_id", "")),
            branch_role=str(raw.get("branch_role", "")),
            status=str(raw.get("status", "project")),
            importance=_optional_float(raw.get("importance")),
            salience=str(raw.get("salience", "")),
            importance_reason=str(raw.get("importance_reason", "")),
            source_date=str(raw.get("source_date", "")),
            coverage_period=str(raw.get("coverage_period", "")),
        )


DeepeningBranch = DeepeningRecord


@dataclass(frozen=True)
class BranchFinding:
    branch_id: str
    code: str
    severity: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BranchAuditReport:
    source_id: str
    findings: tuple[BranchFinding, ...]

    @property
    def ok(self) -> bool:
        return not any(finding.severity in {"error", "critical"} for finding in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "ok": self.ok,
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def to_markdown(self) -> str:
        lines = [f"# Source Branch Audit: {self.source_id}", "", f"- Status: {'OK' if self.ok else 'ISSUES'}", ""]
        if not self.findings:
            lines.append("- No branch findings.")
            return "\n".join(lines) + "\n"
        for finding in self.findings:
            lines.append(f"- {finding.severity.upper()} {finding.branch_id}: {finding.code}")
            lines.append(f"  - {finding.message}")
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class ModelNodeDraft:
    node_type: str
    text: str
    scope: str = ""
    locator: str = ""
    importance: float | None = None
    salience: str = ""
    importance_reason: str = ""


class SourceLibraryError(ValueError):
    """Raised when a source-library operation cannot be completed."""


class SourceLibrary:
    """File-backed global source library with project branch overlays."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    @property
    def sources_dir(self) -> Path:
        return self.root / "sources"

    @property
    def source_models_dir(self) -> Path:
        return self.root / "source_models"

    @property
    def index_dir(self) -> Path:
        return self.root / "index"

    @property
    def projects_dir(self) -> Path:
        return self.root / "projects"

    @property
    def source_index_path(self) -> Path:
        return self.index_dir / "sources.json"

    @property
    def node_index_path(self) -> Path:
        return self.index_dir / "nodes.json"

    def init(self) -> None:
        for directory in (self.sources_dir, self.source_models_dir, self.index_dir, self.projects_dir):
            directory.mkdir(parents=True, exist_ok=True)
        if not self.source_index_path.exists():
            _write_json(self.source_index_path, {"version": LIBRARY_VERSION, "sources": []})
        if not self.node_index_path.exists():
            _write_json(self.node_index_path, {"version": LIBRARY_VERSION, "entries": []})

    def list_sources(self) -> list[SourceRecord]:
        """Read source records without creating or mutating library files."""
        return self._load_sources()

    def list_projects(self) -> list[ProjectBranch]:
        """Read project branches without creating or mutating library files."""
        if not self.projects_dir.exists():
            return []
        projects: list[ProjectBranch] = []
        for project_dir in sorted(self.projects_dir.iterdir()):
            if not project_dir.is_dir():
                continue
            try:
                projects.append(self.require_project(project_dir.name))
            except SourceLibraryError:
                continue
        return projects

    def import_source(
        self,
        source_path: str | Path,
        *,
        title: str = "",
        authors: Iterable[str] = (),
        year: str = "",
        source_date: str = "",
        coverage_period: str = "",
        doi: str = "",
        url: str = "",
    ) -> SourceImportResult:
        self.init()
        path = Path(source_path)
        if not path.exists() or not path.is_file():
            raise SourceLibraryError(f"Source file not found: {path}")
        content_hash = _file_sha256(path)
        sources = self._load_sources()
        for existing in sources:
            if existing.content_hash == content_hash:
                return SourceImportResult(
                    source=existing,
                    created=False,
                    reused_existing=True,
                    possible_duplicates=existing.possible_duplicates,
                )

        possible_duplicates = tuple(
            source.source_id
            for source in sources
            if _metadata_may_match(source, title=title, year=year, source_date=source_date, doi=doi, url=url)
        )
        source_id = _unique_source_id(
            base=_source_id_base(path, title=title, year=year, source_date=source_date, doi=doi, url=url, content_hash=content_hash),
            existing={source.source_id for source in sources},
        )
        target = self.sources_dir / f"{source_id}{path.suffix.lower()}"
        shutil.copy2(path, target)
        record = SourceRecord(
            source_id=source_id,
            title=title or path.stem,
            authors=tuple(str(item) for item in authors if str(item)),
            year=year,
            source_date=source_date,
            coverage_period=coverage_period,
            doi=doi,
            url=url,
            content_hash=content_hash,
            source_path=str(target.relative_to(self.root)),
            original_path=str(path),
            possible_duplicates=possible_duplicates,
        )
        self._save_sources([*sources, record])
        return SourceImportResult(
            source=record,
            created=True,
            reused_existing=False,
            possible_duplicates=possible_duplicates,
        )

    def create_source_model(
        self,
        source_id: str,
        *,
        title: str = "",
        claim: str = "",
        evidence: str = "",
        warrant: str = "",
        method: str = "",
        result: str = "",
        scope: str = "",
        limitation: str = "",
        rebuttal: str = "",
        locator: str = "",
        importance: float | None = None,
        salience: str = "",
        importance_reason: str = "",
        i18n: Mapping[str, Any] | None = None,
    ) -> Path:
        self.init()
        source = self.require_source(source_id)
        localized = normalize_i18n(i18n)
        model_title = title or localized_field(localized, "title", DEFAULT_LANGUAGE) or source.title or source.source_id
        path = self.source_model_path(source_id)
        raw = self._load_source_model_raw(source_id) if path.exists() else _base_source_model(source, model_title)
        raw.setdefault("model", {})["title"] = model_title
        _apply_model_i18n(raw, localized)
        _apply_document_title(raw, model_title, localized)
        drafts = [
            ("claim", ModelNodeDraft("Claim", claim or localized_field(localized, "claim", DEFAULT_LANGUAGE), scope=scope, locator=locator, importance=importance, salience=salience, importance_reason=importance_reason)),
            ("evidence", ModelNodeDraft("Evidence", evidence or localized_field(localized, "evidence", DEFAULT_LANGUAGE), scope=scope, locator=locator, importance=importance, salience=salience, importance_reason=importance_reason)),
            ("warrant", ModelNodeDraft("Warrant", warrant or localized_field(localized, "warrant", DEFAULT_LANGUAGE), scope=scope, locator=locator, importance=importance, salience=salience, importance_reason=importance_reason)),
            ("method", ModelNodeDraft("Method", method or localized_field(localized, "method", DEFAULT_LANGUAGE), scope=scope, locator=locator, importance=importance, salience=salience, importance_reason=importance_reason)),
            ("result", ModelNodeDraft("Result", result or localized_field(localized, "result", DEFAULT_LANGUAGE), scope=scope, locator=locator, importance=importance, salience=salience, importance_reason=importance_reason)),
            ("limitation", ModelNodeDraft("Limitation", limitation or localized_field(localized, "limitation", DEFAULT_LANGUAGE), scope=scope, locator=locator, importance=importance, salience=salience, importance_reason=importance_reason)),
            ("rebuttal", ModelNodeDraft("Rebuttal", rebuttal or localized_field(localized, "rebuttal", DEFAULT_LANGUAGE), scope=scope, locator=locator, importance=importance, salience=salience, importance_reason=importance_reason)),
        ]
        for field_key, draft in drafts:
            if draft.text:
                _append_node(raw, source_id=source_id, draft=draft, i18n=field_i18n(localized, field_key))
        _connect_standard_source_nodes(raw)
        _write_yaml(path, raw)
        self.rebuild_index()
        return path

    def deepen_source(
        self,
        source_id: str,
        *,
        project_id: str,
        topic_focus: str,
        locator: str,
        anchor_node_id: str = "",
        anchor_block_id: str = "",
        branch_role: str = "",
        branch_id: str = "",
        promote: bool = False,
        claim: str = "",
        evidence: str = "",
        warrant: str = "",
        method: str = "",
        result: str = "",
        scope: str = "",
        limitation: str = "",
        rebuttal: str = "",
        note: str = "",
        importance: float | None = None,
        salience: str = "",
        importance_reason: str = "",
        i18n: Mapping[str, Any] | None = None,
    ) -> DeepeningRecord:
        self.init()
        source = self.require_source(source_id)
        if not topic_focus:
            raise SourceLibraryError("topic_focus is required for source deepening")
        if not locator:
            raise SourceLibraryError("locator is required for source deepening")
        if anchor_node_id and anchor_block_id:
            raise SourceLibraryError("Use anchor_node_id or anchor_block_id, not both")
        raw = self._load_source_model_raw(source_id)
        _require_anchor(raw, anchor_node_id=anchor_node_id, anchor_block_id=anchor_block_id)
        status = "promoted" if promote else "project"
        branch_id = branch_id or _next_branch_id(raw)
        if _find_branch_raw(raw, branch_id):
            raise SourceLibraryError(f"Deepening branch already exists: {branch_id}")
        localized = normalize_i18n(i18n)
        drafts = [
            ("claim", ModelNodeDraft("Claim", claim or localized_field(localized, "claim", DEFAULT_LANGUAGE), scope=scope, locator=locator, importance=importance, salience=salience, importance_reason=importance_reason)),
            ("evidence", ModelNodeDraft("Evidence", evidence or localized_field(localized, "evidence", DEFAULT_LANGUAGE), scope=scope, locator=locator, importance=importance, salience=salience, importance_reason=importance_reason)),
            ("warrant", ModelNodeDraft("Warrant", warrant or localized_field(localized, "warrant", DEFAULT_LANGUAGE), scope=scope, locator=locator, importance=importance, salience=salience, importance_reason=importance_reason)),
            ("method", ModelNodeDraft("Method", method or localized_field(localized, "method", DEFAULT_LANGUAGE), scope=scope, locator=locator, importance=importance, salience=salience, importance_reason=importance_reason)),
            ("result", ModelNodeDraft("Result", result or localized_field(localized, "result", DEFAULT_LANGUAGE), scope=scope, locator=locator, importance=importance, salience=salience, importance_reason=importance_reason)),
            ("limitation", ModelNodeDraft("Limitation", limitation or localized_field(localized, "limitation", DEFAULT_LANGUAGE), scope=scope, locator=locator, importance=importance, salience=salience, importance_reason=importance_reason)),
            ("rebuttal", ModelNodeDraft("Rebuttal", rebuttal or localized_field(localized, "rebuttal", DEFAULT_LANGUAGE), scope=scope, locator=locator, importance=importance, salience=salience, importance_reason=importance_reason)),
        ]
        added: list[str] = []
        for field_key, draft in drafts:
            if not draft.text:
                continue
            node_id = _append_node(
                raw,
                source_id=source_id,
                draft=draft,
                i18n=field_i18n(localized, field_key),
                extra_metadata={
                    "topic_focus": topic_focus,
                    "project_id": project_id,
                    "deepened": True,
                    "branch_id": branch_id,
                    "anchor_node_id": anchor_node_id,
                    "anchor_block_id": anchor_block_id,
                    "branch_role": branch_role,
                    "branch_status": status,
                },
            )
            added.append(node_id)
        if not added:
            raise SourceLibraryError("At least one claim, evidence, warrant, method, result, limitation, or rebuttal is required")
        _connect_standard_source_nodes(raw)
        record = DeepeningRecord(
            project_id=project_id,
            source_id=source_id,
            topic_focus=topic_focus,
            locator=locator,
            node_ids=tuple(added),
            note=note,
            branch_id=branch_id,
            anchor_node_id=anchor_node_id,
            anchor_block_id=anchor_block_id,
            branch_role=branch_role,
            status=status,
            importance=importance,
            salience=salience,
            importance_reason=importance_reason,
            source_date=source.source_date or source.year,
            coverage_period=source.coverage_period,
        )
        _connect_deepening_branch_nodes(raw, record)
        _append_branch(raw, record)
        _write_yaml(self.source_model_path(source_id), raw)
        self._append_overlay(project_id, record.to_dict())
        self.rebuild_index()
        return record

    def list_deepening_branches(
        self,
        source_id: str = "",
        *,
        project_id: str = "",
        anchor_node_id: str = "",
        anchor_block_id: str = "",
        topic_focus: str = "",
        status: str = "",
    ) -> list[DeepeningRecord]:
        self.init()
        records: list[DeepeningRecord] = []
        source_records = {source.source_id: source for source in self._load_sources()}
        source_ids = [source_id] if source_id else list(source_records)
        for current_source_id in source_ids:
            raw = self._load_source_model_raw(current_source_id)
            for record in _load_branches(raw):
                source = source_records.get(record.source_id)
                if source:
                    record = replace(
                        record,
                        source_date=record.source_date or source.source_date or source.year,
                        coverage_period=record.coverage_period or source.coverage_period,
                    )
                if project_id and record.project_id != project_id:
                    continue
                if anchor_node_id and record.anchor_node_id != anchor_node_id:
                    continue
                if anchor_block_id and record.anchor_block_id != anchor_block_id:
                    continue
                if topic_focus and topic_focus.lower() not in record.topic_focus.lower():
                    continue
                if status and record.status != status:
                    continue
                records.append(record)
        return sorted(records, key=lambda record: (record.source_id, record.branch_id or "", record.topic_focus))

    def audit_deepening_branches(self, source_id: str = "") -> BranchAuditReport:
        self.init()
        findings: list[BranchFinding] = []
        source_ids = [source_id] if source_id else [source.source_id for source in self._load_sources()]
        seen: set[tuple[str, str, str, str, str]] = set()
        for current_source_id in source_ids:
            raw = self._load_source_model_raw(current_source_id)
            nodes = raw.get("nodes", {}) if isinstance(raw.get("nodes", {}), Mapping) else {}
            for record in _load_branches(raw):
                branch_label = record.branch_id or f"{record.source_id}:{record.topic_focus}"
                if not record.branch_id:
                    findings.append(_branch_finding(branch_label, "missing_branch_id", "warning", "Deepening branch has no stable branch id."))
                if not (record.anchor_node_id or record.anchor_block_id):
                    findings.append(_branch_finding(branch_label, "unanchored_branch", "warning", "Branch is not attached to a source node or block."))
                if record.anchor_node_id and not _anchor_exists(raw, anchor_node_id=record.anchor_node_id):
                    findings.append(_branch_finding(branch_label, "missing_anchor_node", "error", f"Anchor node {record.anchor_node_id} does not exist in the source model."))
                if record.anchor_block_id and not _anchor_exists(raw, anchor_block_id=record.anchor_block_id):
                    findings.append(_branch_finding(branch_label, "missing_anchor_block", "error", f"Anchor block {record.anchor_block_id} does not exist in the source model."))
                if not record.node_ids:
                    findings.append(_branch_finding(branch_label, "empty_branch", "error", "Branch does not contain generated node ids."))
                if not record.branch_role:
                    findings.append(_branch_finding(branch_label, "unclear_branch_role", "warning", "Branch does not state whether it supports, explains, limits, contextualizes, or rebuts the anchor."))
                if record.importance is not None and not 0 <= record.importance <= 1:
                    findings.append(_branch_finding(branch_label, "invalid_importance", "error", "Branch importance must be in [0, 1]."))
                branch_types = {str(nodes.get(node_id, {}).get("type", "")) for node_id in record.node_ids if isinstance(nodes.get(node_id), Mapping)}
                if "Claim" in branch_types and not ({"Evidence", "Result", "Warrant"} & branch_types):
                    findings.append(_branch_finding(branch_label, "claim_without_support", "warning", "Branch introduces a claim without evidence, result, or warrant in the same branch."))
                key = (record.source_id, record.project_id, record.topic_focus.lower(), record.anchor_node_id or record.anchor_block_id, record.branch_role)
                if key in seen:
                    findings.append(_branch_finding(branch_label, "duplicate_branch_focus", "warning", "Another branch already uses the same source, project, topic, anchor, and role."))
                seen.add(key)
        return BranchAuditReport(source_id or "all", tuple(findings))

    def create_project(self, project_id: str, *, topic: str) -> ProjectBranch:
        self.init()
        clean_project_id = _slug(project_id)
        if not clean_project_id:
            raise SourceLibraryError("project_id is required")
        project = ProjectBranch(project_id=clean_project_id, topic=topic)
        project_dir = self.project_dir(clean_project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        _write_json(project_dir / "topic.json", {"project_id": clean_project_id, "topic": topic})
        _write_json(project_dir / "selected_sources.json", {"sources": []})
        _write_json(project_dir / "node_links.json", {"links": []})
        _write_json(project_dir / "overlays.json", {"overlays": []})
        return project

    def select_source(self, project_id: str, source_id: str) -> ProjectBranch:
        self.init()
        self.require_source(source_id)
        project = self.require_project(project_id)
        selected = list(project.selected_sources)
        if source_id not in selected:
            selected.append(source_id)
        updated = ProjectBranch(
            project_id=project.project_id,
            topic=project.topic,
            selected_sources=tuple(selected),
            argument_model=project.argument_model,
        )
        _write_json(self.project_dir(project.project_id) / "selected_sources.json", {"sources": selected})
        return updated

    def delete_project(self, project_id: str) -> ProjectBranch:
        self.init()
        project = self.require_project(project_id)
        shutil.rmtree(self.project_dir(project.project_id))
        return project

    def link_node(
        self,
        project_id: str,
        *,
        project_node_id: str,
        source_id: str,
        source_node_id: str,
        relation: str,
        note: str = "",
        importance: float | None = None,
        salience: str = "",
        importance_reason: str = "",
        source_branch_id: str = "",
    ) -> NodeLink:
        self.init()
        project = self.require_project(project_id)
        if source_id not in project.selected_sources:
            raise SourceLibraryError(f"Source {source_id} is not selected for project {project.project_id}")
        if relation not in EDGE_TYPES:
            raise SourceLibraryError(f"Unknown relation type: {relation}")
        model = load_model(self.source_model_path(source_id))
        if source_node_id not in model.nodes:
            raise SourceLibraryError(f"Source node not found: {source_id}:{source_node_id}")
        branch = self._branch_for_node(source_id, source_node_id, branch_id=source_branch_id)
        if source_branch_id and branch is None:
            raise SourceLibraryError(f"Source branch not found: {source_id}:{source_branch_id}")
        link = NodeLink(
            project_id=project.project_id,
            project_node_id=project_node_id,
            source_id=source_id,
            source_node_id=source_node_id,
            relation=relation,
            note=note,
            importance=importance,
            salience=salience,
            importance_reason=importance_reason,
            source_branch_id=branch.branch_id if branch else "",
            anchor_node_id=branch.anchor_node_id if branch else "",
            anchor_block_id=branch.anchor_block_id if branch else "",
        )
        path = self.project_dir(project.project_id) / "node_links.json"
        payload = _read_json(path, default={"links": []})
        links = [NodeLink.from_dict(item) for item in payload.get("links", [])]
        if link not in links:
            links.append(link)
        _write_json(path, {"links": [item.to_dict() for item in links]})
        return link

    def list_links(self, project_id: str, *, project_node_id: str = "") -> list[NodeLink]:
        project = self.require_project(project_id)
        payload = _read_json(self.project_dir(project.project_id) / "node_links.json", default={"links": []})
        links = [NodeLink.from_dict(item) for item in payload.get("links", [])]
        if project_node_id:
            return [link for link in links if link.project_node_id == project_node_id]
        return links

    def search(
        self,
        query: str,
        *,
        node_type: str = "",
        project_id: str = "",
        branch_id: str = "",
        anchor_node_id: str = "",
        anchor_block_id: str = "",
        limit: int = 10,
    ) -> list[SearchHit]:
        self.init()
        if node_type and node_type not in NODE_TYPES:
            raise SourceLibraryError(f"Unknown node type: {node_type}")
        entries = [IndexEntry(**item) for item in _read_json(self.node_index_path, default={"entries": []}).get("entries", [])]
        selected_sources: set[str] = set()
        if project_id:
            selected_sources.update(self.require_project(project_id).selected_sources)
        query_tokens = _tokens(query)
        hits: list[SearchHit] = []
        for entry in entries:
            if node_type and entry.node_type != node_type:
                continue
            if branch_id and entry.branch_id != branch_id:
                continue
            if anchor_node_id and entry.anchor_node_id != anchor_node_id:
                continue
            if anchor_block_id and entry.anchor_block_id != anchor_block_id:
                continue
            haystack = " ".join(
                item
                for item in (
                    entry.text,
                    entry.scope,
                    entry.locator,
                    entry.topic_focus,
                    entry.source_title,
                    entry.source_date,
                    entry.coverage_period,
                    entry.branch_role,
                )
                if item
            )
            score = _score(query_tokens, haystack)
            if selected_sources and entry.source_id in selected_sources:
                score += 1.5
            if score > 0 or not query_tokens:
                hits.append(SearchHit(entry=entry, score=score))
        return sorted(hits, key=lambda hit: (-hit.score, hit.entry.source_id, hit.entry.node_id))[:limit]

    def rebuild_index(self) -> list[IndexEntry]:
        self.init()
        sources = {source.source_id: source for source in self._load_sources()}
        entries: list[IndexEntry] = []
        for model_path in sorted(self.source_models_dir.glob(f"*{DEFAULT_MODEL_SUFFIX}")):
            model = load_model(model_path)
            source_id = str(model.metadata.get("source_id") or model_path.name.removesuffix(DEFAULT_MODEL_SUFFIX))
            source = sources.get(source_id)
            for node_id, node in sorted(model.nodes.items()):
                if node.type in {"Document", "Section", "ArgumentBlock"}:
                    continue
                entries.append(
                    IndexEntry(
                        source_id=source_id,
                        node_id=node_id,
                        node_type=node.type,
                        text=node.text,
                        scope=node.scope or "",
                        locator=str(node.metadata.get("locator", "")),
                        topic_focus=str(node.metadata.get("topic_focus", "")),
                        source_title=source.title if source else model.title,
                        source_date=str(node.metadata.get("source_date", "")) or (source.source_date if source else ""),
                        coverage_period=str(node.metadata.get("coverage_period", "")) or (source.coverage_period if source else ""),
                        importance=node.importance,
                        salience=node.salience or "",
                        importance_reason=node.importance_reason or "",
                        branch_id=str(node.metadata.get("branch_id", "")),
                        anchor_node_id=str(node.metadata.get("anchor_node_id", "")),
                        anchor_block_id=str(node.metadata.get("anchor_block_id", "")),
                        branch_role=str(node.metadata.get("branch_role", "")),
                        branch_status=str(node.metadata.get("branch_status", "")),
                    )
                )
        _write_json(self.node_index_path, {"version": LIBRARY_VERSION, "entries": [entry.to_dict() for entry in entries]})
        return entries

    def source_model_path(self, source_id: str) -> Path:
        return self.source_models_dir / f"{source_id}{DEFAULT_MODEL_SUFFIX}"

    def project_dir(self, project_id: str) -> Path:
        return self.projects_dir / _slug(project_id)

    def require_source(self, source_id: str) -> SourceRecord:
        for source in self._load_sources():
            if source.source_id == source_id:
                return source
        raise SourceLibraryError(f"Source not found: {source_id}")

    def require_project(self, project_id: str) -> ProjectBranch:
        clean_project_id = _slug(project_id)
        project_dir = self.project_dir(clean_project_id)
        if not project_dir.exists():
            raise SourceLibraryError(f"Project not found: {project_id}")
        topic_payload = _read_json(project_dir / "topic.json", default={})
        selected_payload = _read_json(project_dir / "selected_sources.json", default={"sources": []})
        return ProjectBranch(
            project_id=clean_project_id,
            topic=str(topic_payload.get("topic", "")),
            selected_sources=tuple(str(item) for item in selected_payload.get("sources", []) or []),
        )

    def _load_sources(self) -> list[SourceRecord]:
        payload = _read_json(self.source_index_path, default={"sources": []})
        return [SourceRecord.from_dict(item) for item in payload.get("sources", [])]

    def _save_sources(self, sources: list[SourceRecord]) -> None:
        _write_json(self.source_index_path, {"version": LIBRARY_VERSION, "sources": [source.to_dict() for source in sources]})

    def _load_source_model_raw(self, source_id: str) -> dict[str, Any]:
        path = self.source_model_path(source_id)
        if not path.exists():
            source = self.require_source(source_id)
            raw = _base_source_model(source, source.title or source.source_id)
            _write_yaml(path, raw)
            return raw
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise SourceLibraryError(f"Source model must be a mapping: {path}")
        return payload

    def _append_overlay(self, project_id: str, overlay: dict[str, Any]) -> None:
        project = self.require_project(project_id)
        path = self.project_dir(project.project_id) / "overlays.json"
        payload = _read_json(path, default={"overlays": []})
        overlays = list(payload.get("overlays", []) or [])
        if overlay not in overlays:
            overlays.append(overlay)
        _write_json(path, {"overlays": overlays})

    def _branch_for_node(self, source_id: str, node_id: str, *, branch_id: str = "") -> DeepeningRecord | None:
        raw = self._load_source_model_raw(source_id)
        for branch in _load_branches(raw):
            if branch_id and branch.branch_id != branch_id:
                continue
            if node_id in branch.node_ids:
                return branch
        return None


def _base_source_model(source: SourceRecord, title: str) -> dict[str, Any]:
    return {
        "model": {
            "id": f"source_{source.source_id}",
            "title": title,
            "root_claim": None,
            "source_id": source.source_id,
            "source_title": source.title,
            "source_date": source.source_date or source.year,
            "coverage_period": source.coverage_period,
            "source_path": source.source_path,
            "extraction_status": "navigation",
            "deepening_branches": [],
        },
        "nodes": {
            "D0": {
                "type": "Document",
                "text": title,
                "source_id": source.source_id,
                "source_date": source.source_date or source.year,
                "coverage_period": source.coverage_period,
                "locator": source.source_path,
            }
        },
        "edges": [],
        "acceptance": {},
        "hierarchy": {"D0": []},
    }


def _apply_model_i18n(raw: dict[str, Any], localized: Mapping[str, Mapping[str, str]]) -> None:
    if not localized:
        return
    model_i18n: dict[str, dict[str, str]] = {}
    for language, values in localized.items():
        title = str(values.get("title", "")).strip()
        if title:
            model_i18n.setdefault(str(language), {})["title"] = title
    if model_i18n:
        raw.setdefault("model", {})["i18n"] = model_i18n


def _apply_document_title(raw: dict[str, Any], title: str, localized: Mapping[str, Mapping[str, str]]) -> None:
    nodes = raw.setdefault("nodes", {})
    document = nodes.get("D0")
    if not isinstance(document, dict):
        return
    document["text"] = title
    title_i18n = field_i18n(localized, "title", scope_key="")
    if title_i18n:
        document["i18n"] = title_i18n


def _load_branches(raw: Mapping[str, Any]) -> list[DeepeningRecord]:
    model_info = raw.get("model", {}) if isinstance(raw.get("model", {}), Mapping) else {}
    branches = model_info.get("deepening_branches", []) or []
    records: list[DeepeningRecord] = []
    for item in branches:
        if not isinstance(item, Mapping):
            raise SourceLibraryError(
                "deepening branch entries must be current object mappings"
            )
        records.append(DeepeningRecord.from_dict(item))
    return records


def _append_branch(raw: dict[str, Any], record: DeepeningRecord) -> None:
    model_info = raw.setdefault("model", {})
    branches = list(model_info.get("deepening_branches", []) or [])
    record_data = record.to_dict()
    for index, item in enumerate(branches):
        if isinstance(item, Mapping) and item.get("branch_id") == record.branch_id:
            branches[index] = record_data
            model_info["deepening_branches"] = branches
            return
    branches.append(record_data)
    model_info["deepening_branches"] = branches


def _find_branch_raw(raw: Mapping[str, Any], branch_id: str) -> Mapping[str, Any] | None:
    model_info = raw.get("model", {}) if isinstance(raw.get("model", {}), Mapping) else {}
    for item in model_info.get("deepening_branches", []) or []:
        if isinstance(item, Mapping) and item.get("branch_id") == branch_id:
            return item
    return None


def _next_branch_id(raw: Mapping[str, Any]) -> str:
    existing = {
        str(item.get("branch_id", ""))
        for item in (raw.get("model", {}) or {}).get("deepening_branches", []) or []
        if isinstance(item, Mapping)
    }
    index = 1
    while f"BR{index}" in existing:
        index += 1
    return f"BR{index}"


def _require_anchor(raw: Mapping[str, Any], *, anchor_node_id: str = "", anchor_block_id: str = "") -> None:
    if anchor_node_id and not _anchor_exists(raw, anchor_node_id=anchor_node_id):
        raise SourceLibraryError(f"Anchor node not found: {anchor_node_id}")
    if anchor_block_id and not _anchor_exists(raw, anchor_block_id=anchor_block_id):
        raise SourceLibraryError(f"Anchor block not found: {anchor_block_id}")


def _anchor_exists(raw: Mapping[str, Any], *, anchor_node_id: str = "", anchor_block_id: str = "") -> bool:
    nodes = raw.get("nodes", {}) if isinstance(raw.get("nodes", {}), Mapping) else {}
    if anchor_node_id:
        return anchor_node_id in nodes
    if anchor_block_id:
        blocks = raw.get("blocks", {}) if isinstance(raw.get("blocks", {}), Mapping) else {}
        hierarchy = raw.get("hierarchy", {}) if isinstance(raw.get("hierarchy", {}), Mapping) else {}
        node = nodes.get(anchor_block_id)
        return anchor_block_id in blocks or anchor_block_id in hierarchy or (
            isinstance(node, Mapping) and node.get("type") == "ArgumentBlock"
        )
    return False


def _branch_finding(branch_id: str, code: str, severity: str, message: str) -> BranchFinding:
    return BranchFinding(branch_id=branch_id, code=code, severity=severity, message=message)


def _append_node(
    raw: dict[str, Any],
    *,
    source_id: str,
    draft: ModelNodeDraft,
    i18n: Mapping[str, Any] | None = None,
    extra_metadata: Mapping[str, Any] | None = None,
) -> str:
    node_type = draft.node_type
    if node_type not in NODE_TYPES:
        raise SourceLibraryError(f"Unknown node type: {node_type}")
    nodes = raw.setdefault("nodes", {})
    node_id = _next_node_id(nodes, node_type)
    data: dict[str, Any] = {
        "type": node_type,
        "text": draft.text,
        "source_id": source_id,
    }
    if draft.scope:
        data["scope"] = draft.scope
    if draft.locator:
        data["locator"] = draft.locator
    if draft.importance is not None:
        data["importance"] = draft.importance
    if draft.salience:
        data["salience"] = draft.salience
    if draft.importance_reason:
        data["importance_reason"] = draft.importance_reason
    if i18n:
        data["i18n"] = dict(i18n)
    if extra_metadata:
        data.update({key: value for key, value in extra_metadata.items() if value not in ("", None, [], {})})
    nodes[node_id] = data
    hierarchy = raw.setdefault("hierarchy", {})
    children = list(hierarchy.get("D0", []) or [])
    if node_id not in children:
        children.append(node_id)
    hierarchy["D0"] = children
    return node_id


def _connect_standard_source_nodes(raw: dict[str, Any]) -> None:
    nodes = raw.get("nodes", {})
    edges = list(raw.get("edges", []) or [])
    existing = {(edge.get("source"), edge.get("target"), edge.get("type")) for edge in edges if isinstance(edge, Mapping)}
    claims = [node_id for node_id, node in nodes.items() if node.get("type") == "Claim" and not node.get("branch_id")]
    if not claims:
        raw["edges"] = edges
        return
    target = claims[0]
    raw["model"]["root_claim"] = target
    for node_id, node in nodes.items():
        if node.get("branch_id"):
            continue
        node_type = node.get("type")
        if node_id == target:
            continue
        edge_target = target
        edge_type = _standard_edge_type(node_type)
        if node_type == "Evidence":
            edge_target = _first_node_of_type(nodes, "Result") or target
        elif node_type == "Method":
            edge_target = _first_node_of_type(nodes, "Result") or _first_node_of_type(nodes, "Evidence") or target
            edge_type = "contextualizes"
        if edge_type and edge_target and (node_id, edge_target, edge_type) not in existing:
            edges.append({"source": node_id, "target": edge_target, "type": edge_type, "weight": 1.0})
            existing.add((node_id, edge_target, edge_type))
    raw["edges"] = edges


def _standard_edge_type(node_type: Any) -> str:
    if node_type in {"Evidence", "Warrant", "Result"}:
        return "supports"
    if node_type == "Limitation":
        return "qualifies"
    if node_type == "Rebuttal":
        return "attacks"
    if node_type in {"Context", "Definition", "Method"}:
        return "contextualizes"
    return ""


def _first_node_of_type(nodes: Mapping[str, Any], node_type: str) -> str:
    for node_id, node in nodes.items():
        if isinstance(node, Mapping) and node.get("type") == node_type and not node.get("branch_id"):
            return str(node_id)
    return ""


def _connect_deepening_branch_nodes(raw: dict[str, Any], branch: DeepeningRecord) -> None:
    nodes = raw.get("nodes", {})
    edges = list(raw.get("edges", []) or [])
    existing = {(edge.get("source"), edge.get("target"), edge.get("type")) for edge in edges if isinstance(edge, Mapping)}
    node_ids = [node_id for node_id in branch.node_ids if node_id in nodes]
    if not node_ids:
        raw["edges"] = edges
        return

    branch_claims = [node_id for node_id in node_ids if nodes[node_id].get("type") == "Claim"]
    branch_target = branch_claims[0] if branch_claims else branch.anchor_node_id
    if not branch_target:
        branch_target = node_ids[0]

    for node_id in node_ids:
        if node_id == branch_target:
            continue
        node_type = nodes[node_id].get("type")
        edge_type = _edge_type_for_source_node(node_type)
        if edge_type and (node_id, branch_target, edge_type) not in existing:
            edges.append({"source": node_id, "target": branch_target, "type": edge_type, "weight": 1.0, "branch_id": branch.branch_id})
            existing.add((node_id, branch_target, edge_type))

    if branch.anchor_node_id and branch_target != branch.anchor_node_id:
        edge_type = _edge_type_for_branch_role(branch.branch_role)
        if (branch_target, branch.anchor_node_id, edge_type) not in existing:
            edges.append(
                {
                    "source": branch_target,
                    "target": branch.anchor_node_id,
                    "type": edge_type,
                    "weight": 1.0,
                    "branch_id": branch.branch_id,
                    "explanation": f"{branch.branch_id} expands {branch.anchor_node_id}.",
                }
            )
            existing.add((branch_target, branch.anchor_node_id, edge_type))
    raw["edges"] = edges


def _edge_type_for_source_node(node_type: str) -> str:
    if node_type in {"Evidence", "Warrant", "Method", "Result"}:
        return "supports"
    if node_type == "Limitation":
        return "qualifies"
    if node_type == "Rebuttal":
        return "attacks"
    if node_type in {"Context", "Definition"}:
        return "contextualizes"
    return ""


def _edge_type_for_branch_role(branch_role: str) -> str:
    role = branch_role.lower()
    if any(token in role for token in ("limit", "scope", "qualif", "boundary")):
        return "qualifies"
    if any(token in role for token in ("rebut", "attack", "contradict")):
        return "attacks"
    if any(token in role for token in ("context", "background")):
        return "contextualizes"
    if any(token in role for token in ("derive", "mechanism", "detail", "explain")):
        return "depends_on"
    return "supports"


def _next_node_id(nodes: Mapping[str, Any], node_type: str) -> str:
    prefix = {
        "Claim": "C",
        "Evidence": "E",
        "Warrant": "W",
        "Method": "M",
        "Result": "RSLT",
        "Limitation": "L",
        "Rebuttal": "R",
    }.get(node_type, node_type[:1].upper())
    index = 1
    while f"{prefix}{index}" in nodes:
        index += 1
    return f"{prefix}{index}"


def _metadata_may_match(source: SourceRecord, *, title: str, year: str, source_date: str, doi: str, url: str) -> bool:
    if doi and source.doi and _normalize_identifier(doi) == _normalize_identifier(source.doi):
        return True
    if url and source.url and url.rstrip("/").lower() == source.url.rstrip("/").lower():
        return True
    requested_date = source_date or year
    existing_date = source.source_date or source.year
    if title and source.title and _slug(title) == _slug(source.title) and (not requested_date or not existing_date or requested_date == existing_date):
        return True
    return False


def _source_id_base(path: Path, *, title: str, year: str, source_date: str, doi: str, url: str, content_hash: str) -> str:
    if doi:
        return f"doi-{_normalize_identifier(doi)}"
    if url:
        return f"url-{_slug(url.rstrip('/').split('/')[-1] or path.stem)}"
    if title:
        return "-".join(part for part in (_slug(title), _slug(source_date or year)) if part)
    return f"{_slug(path.stem)}-{content_hash[:8]}"


def _unique_source_id(base: str, existing: set[str]) -> str:
    source_id = _slug(base) or "source"
    candidate = source_id
    index = 2
    while candidate in existing:
        candidate = f"{source_id}-{index}"
        index += 1
    return candidate


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _slug(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def _normalize_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(token for token in re.split(r"[^a-z0-9]+", value.lower()) if token)


def _score(tokens: tuple[str, ...], value: str) -> float:
    if not tokens:
        return 1.0
    haystack = value.lower()
    score = 0.0
    for token in tokens:
        if token in haystack:
            score += 1.0
    if all(token in haystack for token in tokens):
        score += 0.5
    return score


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_json(path: Path, *, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(dict(payload), sort_keys=False, allow_unicode=False), encoding="utf-8")
