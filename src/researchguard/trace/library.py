"""TraceGuard Case Library.

Purpose: Maintain lightweight case/direction-scoped investigation memory for sources, evidence, events, traces, gaps, and search tasks.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: TraceGuard internal case-library route
Math boundary: Library storage only; TraceGuard evaluator remains the reasoning authority.
CLI: researchguard trace library <command>
Boundary: A saved source is not evidence, evidence is not an event, and an event is not a final claim.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from .loader import dump_yaml, load_model
from .purpose_contract import bind_task_guard_purpose


LIBRARY_VERSION = "0.3"
DEFAULT_LIBRARY_NAME = "TraceGuard Case Library"
MODEL_LEDGER_SPECS = {
    "sources": ("sources.yaml", "source_id"),
    "evidence": ("evidence.yaml", "evidence_id"),
    "entities": ("entities.yaml", "mention_id"),
    "entity_resolutions": ("entity_resolutions.yaml", "resolution_id"),
    "locations": ("locations.yaml", "location_id"),
    "events": ("events.yaml", "event_id"),
    "traces": ("traces.yaml", "trace_id"),
    "storyline_hypotheses": ("storyline_hypotheses.yaml", "hypothesis_id"),
    "hypothesis_evidence_links": (
        "hypothesis_evidence_links.yaml",
        "link_id",
    ),
    "hypothesis_relations": ("hypothesis_relations.yaml", "relation_id"),
    "causal_mechanisms": ("causal_mechanisms.yaml", "mechanism_id"),
    "confounder_reviews": ("confounder_reviews.yaml", "confounder_id"),
    "causal_scopes": ("causal_scopes.yaml", "scope_id"),
    "causal_candidates": ("causal_candidates.yaml", "causal_id"),
    "evidence_ablations": ("evidence_ablations.yaml", "ablation_id"),
    "scenario_perturbations": (
        "scenario_perturbations.yaml",
        "perturbation_id",
    ),
    "expected_sensitivities": (
        "expected_sensitivities.yaml",
        "sensitivity_id",
    ),
}


class LibraryError(ValueError):
    """Raised when a TraceGuard case library operation cannot be completed."""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-").lower()
    if not normalized:
        raise LibraryError("id cannot be empty after normalization")
    return normalized


def read_yaml(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return default if data is None else data


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_yaml(data), encoding="utf-8")


def append_unique_by_id(path: Path, item: dict[str, Any], id_key: str) -> dict[str, Any]:
    records = read_yaml(path, [])
    if not isinstance(records, list):
        raise LibraryError(f"{path} must contain a list")
    item_id = item[id_key]
    replaced = False
    for index, existing in enumerate(records):
        if isinstance(existing, dict) and existing.get(id_key) == item_id:
            records[index] = {**existing, **item, "updated_at": now_iso()}
            replaced = True
            break
    if not replaced:
        records.append(item)
    write_yaml(path, records)
    return item


@dataclass(frozen=True)
class LibraryPaths:
    root: Path

    @property
    def metadata(self) -> Path:
        return self.root / "library.yaml"

    @property
    def cases(self) -> Path:
        return self.root / "cases"

    def case_dir(self, case_id: str) -> Path:
        return self.cases / slug(case_id)

    def case_file(self, case_id: str) -> Path:
        return self.case_dir(case_id) / "case.yaml"

    def directions_dir(self, case_id: str) -> Path:
        return self.case_dir(case_id) / "directions"

    def direction_dir(self, case_id: str, direction_id: str) -> Path:
        return self.directions_dir(case_id) / slug(direction_id)

    def direction_file(self, case_id: str, direction_id: str) -> Path:
        return self.direction_dir(case_id, direction_id) / "direction.yaml"

    def ledger(self, case_id: str, direction_id: str, name: str) -> Path:
        return self.direction_dir(case_id, direction_id) / name

    def case_ledger(self, case_id: str, name: str) -> Path:
        return self.case_dir(case_id) / name


def init_library(root: str | Path, *, name: str = DEFAULT_LIBRARY_NAME) -> dict[str, Any]:
    paths = LibraryPaths(Path(root))
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.cases.mkdir(parents=True, exist_ok=True)
    metadata = {
        "library_version": LIBRARY_VERSION,
        "name": name,
        "purpose": "Lightweight project/case-scoped TraceGuard investigation memory.",
        "boundary": "Case library material is not a LogicGuard source-library model unless explicitly promoted.",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    if paths.metadata.exists():
        existing = read_yaml(paths.metadata, {})
        if isinstance(existing, dict):
            metadata = {
                **metadata,
                **{
                    key: value
                    for key, value in existing.items()
                    if key != "library_version"
                },
                "library_version": LIBRARY_VERSION,
                "updated_at": now_iso(),
            }
    write_yaml(paths.metadata, metadata)
    return metadata


def require_library(root: str | Path) -> LibraryPaths:
    paths = LibraryPaths(Path(root))
    if not paths.metadata.exists():
        raise LibraryError(f"TraceGuard library not initialized at {paths.root}")
    metadata = read_yaml(paths.metadata, {})
    if not isinstance(metadata, dict) or metadata.get("library_version") != LIBRARY_VERSION:
        raise LibraryError(
            f"library_version must equal {LIBRARY_VERSION}; legacy library readers "
            "are not available"
        )
    return paths


def require_direction(paths: LibraryPaths, case_id: str, direction_id: str) -> tuple[str, str]:
    cid = slug(case_id)
    did = slug(direction_id)
    if not paths.case_file(cid).exists():
        raise LibraryError(f"case does not exist: {cid}")
    if not paths.direction_file(cid, did).exists():
        raise LibraryError(f"direction does not exist: {did}")
    return cid, did


def create_case(root: str | Path, case_id: str, *, title: str, topic: str = "", summary: str = "", tags: Iterable[str] = ()) -> dict[str, Any]:
    paths = require_library(root)
    cid = slug(case_id)
    case_dir = paths.case_dir(cid)
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "directions").mkdir(exist_ok=True)
    for name in (
        "gaps.yaml",
        "contradictions.yaml",
        "search_tasks.yaml",
        "inference_receipts.yaml",
    ):
        if not (case_dir / name).exists():
            write_yaml(case_dir / name, [])
    notes = case_dir / "notes.md"
    if not notes.exists():
        notes.write_text(f"# {title}\n\n", encoding="utf-8")
    existing = read_yaml(paths.case_file(cid), {})
    record = {
        "case_id": cid,
        "title": title,
        "topic": topic,
        "summary": summary,
        "status": existing.get("status", "active") if isinstance(existing, dict) else "active",
        "tags": list(tags),
        "created_at": existing.get("created_at", now_iso()) if isinstance(existing, dict) else now_iso(),
        "updated_at": now_iso(),
    }
    write_yaml(paths.case_file(cid), record)
    return record


def create_direction(
    root: str | Path,
    case_id: str,
    direction_id: str,
    *,
    title: str,
    question: str = "",
    priority: str = "normal",
    search_terms: Iterable[str] = (),
) -> dict[str, Any]:
    paths = require_library(root)
    cid = slug(case_id)
    if not paths.case_file(cid).exists():
        raise LibraryError(f"case does not exist: {cid}")
    did = slug(direction_id)
    direction_dir = paths.direction_dir(cid, did)
    direction_dir.mkdir(parents=True, exist_ok=True)
    for folder in ("sources", "artifacts"):
        (direction_dir / folder).mkdir(exist_ok=True)
    for name in (
        *[spec[0] for spec in MODEL_LEDGER_SPECS.values()],
        "gaps.yaml",
        "contradictions.yaml",
        "search_tasks.yaml",
    ):
        if not (direction_dir / name).exists():
            write_yaml(direction_dir / name, [])
    notes = direction_dir / "notes.md"
    if not notes.exists():
        notes.write_text(f"# {title}\n\n", encoding="utf-8")
    existing = read_yaml(paths.direction_file(cid, did), {})
    record = {
        "direction_id": did,
        "case_id": cid,
        "title": title,
        "question": question,
        "status": existing.get("status", "open") if isinstance(existing, dict) else "open",
        "priority": priority,
        "search_terms": list(search_terms),
        "created_at": existing.get("created_at", now_iso()) if isinstance(existing, dict) else now_iso(),
        "updated_at": now_iso(),
    }
    write_yaml(paths.direction_file(cid, did), record)
    return record


def add_source(
    root: str | Path,
    case_id: str,
    direction_id: str,
    *,
    source_id: str,
    title: str,
    source_type: str = "other",
    url: str | None = None,
    status: str = "stable_keep",
    reliability: float = 0.5,
    lineage_id: str | None = None,
    independence_group: str | None = None,
    derived_from_source_ids: Iterable[str] = (),
    source_date: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    paths = require_library(root)
    sid = slug(source_id)
    cid, did = require_direction(paths, case_id, direction_id)
    record = {
        "source_id": sid,
        "title": title,
        "url": url,
        "source_type": source_type,
        "lineage_id": lineage_id or f"lineage:{sid}",
        "independence_group": independence_group or f"source:{sid}",
        "derived_from_source_ids": list(derived_from_source_ids),
        "source_reliability": float(reliability),
        "source_status": status,
        "cleaning_category": "access_gap" if status == "need_auth_or_permission" else None,
        "source_date": source_date,
        "notes": notes,
        "case_id": cid,
        "direction_id": did,
        "library_status": "saved",
        "added_at": now_iso(),
    }
    return append_unique_by_id(paths.ledger(cid, did, "sources.yaml"), record, "source_id")


def add_evidence(
    root: str | Path,
    case_id: str,
    direction_id: str,
    *,
    evidence_id: str,
    source_id: str,
    raw_text: str,
    evidence_type: str = "unknown",
    summary: str | None = None,
    confidence: float = 0.5,
    specificity: float = 0.5,
    status: str = "candidate",
    usable: bool = True,
    limits: Iterable[str] = (),
    warnings: Iterable[str] = (),
) -> dict[str, Any]:
    paths = require_library(root)
    cid, did = require_direction(paths, case_id, direction_id)
    sources = read_yaml(paths.ledger(cid, did, "sources.yaml"), [])
    if source_id not in {item.get("source_id") for item in sources if isinstance(item, dict)}:
        raise LibraryError(f"source does not exist in direction: {source_id}")
    eid = slug(evidence_id)
    record = {
        "evidence_id": eid,
        "source_id": slug(source_id),
        "raw_text": raw_text,
        "normalized_summary": summary,
        "evidence_type": evidence_type,
        "extraction_confidence": float(confidence),
        "evidence_specificity": float(specificity),
        "supports": [],
        "limits": list(limits),
        "warnings": list(warnings),
        "usable_as_trace_evidence": usable,
        "library_status": status,
        "added_at": now_iso(),
    }
    return append_unique_by_id(paths.ledger(cid, did, "evidence.yaml"), record, "evidence_id")


def list_cases(root: str | Path) -> list[dict[str, Any]]:
    paths = require_library(root)
    if not paths.cases.exists():
        return []
    return [read_yaml(case_file, {}) for case_file in sorted(paths.cases.glob("*/case.yaml"))]


def list_directions(root: str | Path, case_id: str) -> list[dict[str, Any]]:
    paths = require_library(root)
    base = paths.directions_dir(case_id)
    if not base.exists():
        return []
    return [read_yaml(item, {}) for item in sorted(base.glob("*/direction.yaml"))]


def direction_ids(paths: LibraryPaths, case_id: str, only: Iterable[str] = ()) -> list[str]:
    selected = [slug(item) for item in only]
    if selected:
        return selected
    base = paths.directions_dir(case_id)
    if not base.exists():
        return []
    return [item.parent.name for item in sorted(base.glob("*/direction.yaml"))]


def _extend_from_direction(paths: LibraryPaths, case_id: str, direction_id: str, filename: str) -> list[Any]:
    data = read_yaml(paths.ledger(case_id, direction_id, filename), [])
    if not isinstance(data, list):
        raise LibraryError(f"{filename} must contain a list")
    return data


def build_model(
    root: str | Path,
    case_id: str,
    *,
    directions: Iterable[str] = (),
    purpose_contract: str | Path,
    candidate_path: str | Path,
) -> dict[str, Any]:
    paths = require_library(root)
    cid = slug(case_id)
    case = read_yaml(paths.case_file(cid), {})
    if not case:
        raise LibraryError(f"case does not exist: {cid}")
    selected = direction_ids(paths, cid, directions)
    merged: dict[str, list[Any]] = {
        section: [] for section in MODEL_LEDGER_SPECS
    }
    seen: dict[str, set[str]] = {key: set() for key in merged}
    for direction_id in selected:
        for section, (filename, id_key) in MODEL_LEDGER_SPECS.items():
            for item in _extend_from_direction(paths, cid, direction_id, filename):
                if not isinstance(item, dict):
                    continue
                item_id = item.get(id_key)
                if item_id and item_id not in seen[section]:
                    seen[section].add(item_id)
                    clean_item = {key: value for key, value in item.items() if key not in {"case_id", "direction_id", "library_status", "added_at", "updated_at"}}
                    merged[section].append(clean_item)
    model = {
        "metadata": {
            "schema_version": "researchguard.trace.model.v2",
            "purpose": f"TraceGuard model built from case library case {cid}.",
            "repository": "https://github.com/liuyingxuvka/ResearchGuard",
            "skill": "TraceGuard",
            "math_boundary": "Typed constrained HL-MRF/MAP inference with a direct OSQP backend.",
            "cli": "researchguard trace validate <generated-model.yaml>",
            "boundary": "Generated from TraceGuard Case Library; saved sources remain distinct from evidence and final claims.",
            "case_id": cid,
            "case_title": case.get("title", cid),
            "directions": selected,
            "generated_at": now_iso(),
        },
        **merged,
    }
    return bind_task_guard_purpose(
        model,
        contract_path=purpose_contract,
        candidate_path=candidate_path,
    )


def write_model(
    root: str | Path,
    case_id: str,
    output: str | Path,
    *,
    directions: Iterable[str] = (),
    purpose_contract: str | Path,
) -> dict[str, Any]:
    model = build_model(
        root,
        case_id,
        directions=directions,
        purpose_contract=purpose_contract,
        candidate_path=output,
    )
    write_yaml(Path(output), model)
    load_model(output)
    return model


def validate_library(root: str | Path) -> dict[str, Any]:
    paths = require_library(root)
    findings: list[dict[str, Any]] = []
    cases = list_cases(root)
    for case in cases:
        cid = case.get("case_id")
        for direction in list_directions(root, cid):
            did = direction.get("direction_id")
            sources = _extend_from_direction(paths, cid, did, "sources.yaml")
            evidence = _extend_from_direction(paths, cid, did, "evidence.yaml")
            source_ids = {item.get("source_id") for item in sources if isinstance(item, dict)}
            evidence_ids = {
                item.get("evidence_id")
                for item in evidence
                if isinstance(item, dict)
            }
            for item in sources:
                if not isinstance(item, dict):
                    findings.append(
                        {
                            "finding_id": "invalid_source_row",
                            "case_id": cid,
                            "direction_id": did,
                            "message": "Source ledger rows must be mappings.",
                        }
                    )
                    continue
                if not item.get("lineage_id") or not item.get("independence_group"):
                    findings.append(
                        {
                            "finding_id": "source_lineage_incomplete",
                            "case_id": cid,
                            "direction_id": did,
                            "source_id": item.get("source_id"),
                            "message": "Every source requires lineage_id and independence_group.",
                        }
                    )
            for item in evidence:
                if isinstance(item, dict) and item.get("source_id") not in source_ids:
                    findings.append({
                        "finding_id": "missing_source_reference",
                        "case_id": cid,
                        "direction_id": did,
                        "evidence_id": item.get("evidence_id"),
                        "message": f"Evidence references missing source {item.get('source_id')}",
                    })
            traces = _extend_from_direction(paths, cid, did, "traces.yaml")
            for item in traces:
                retired = {
                    "validation_status",
                    "confidence",
                    "allowed_wording",
                    "unsafe_wording",
                } & set(item if isinstance(item, dict) else {})
                if retired:
                    findings.append(
                        {
                            "finding_id": "inferred_output_in_model_ledger",
                            "case_id": cid,
                            "direction_id": did,
                            "trace_id": item.get("trace_id"),
                            "fields": sorted(retired),
                            "message": "Trace inference outputs belong in receipt history, not model input.",
                        }
                    )
            links = _extend_from_direction(
                paths,
                cid,
                did,
                "hypothesis_evidence_links.yaml",
            )
            for item in links:
                if not isinstance(item, dict):
                    continue
                if item.get("polarity") not in {"support", "oppose", "limit"}:
                    findings.append(
                        {
                            "finding_id": "invalid_hypothesis_polarity",
                            "case_id": cid,
                            "direction_id": did,
                            "link_id": item.get("link_id"),
                            "message": "Hypothesis links require support, oppose, or limit polarity.",
                        }
                    )
                if item.get("evidence_id") not in evidence_ids:
                    findings.append(
                        {
                            "finding_id": "hypothesis_link_missing_evidence",
                            "case_id": cid,
                            "direction_id": did,
                            "link_id": item.get("link_id"),
                            "message": f"Hypothesis link references missing evidence {item.get('evidence_id')}",
                        }
                    )
    return {"ok": not findings, "case_count": len(cases), "findings": findings}


def search_library(root: str | Path, query: str, *, case_id: str | None = None) -> list[dict[str, Any]]:
    paths = require_library(root)
    needle = query.lower()
    roots = [paths.case_dir(case_id)] if case_id else [paths.cases]
    matches: list[dict[str, Any]] = []
    for base in roots:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".yaml", ".yml", ".md", ".txt", ".json"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
                lower = text.lower()
                if needle in lower:
                    index = lower.find(needle)
                    snippet = text[max(0, index - 80): index + len(query) + 80].replace("\n", " ")
                    matches.append({"path": str(path.relative_to(paths.root)), "snippet": snippet})
    return matches


def write_back_gaps(root: str | Path, case_id: str, result_path: str | Path) -> dict[str, Any]:
    paths = require_library(root)
    result = json.loads(Path(result_path).read_text(encoding="utf-8"))
    gaps: list[dict[str, Any]] = []
    contradictions: list[dict[str, Any]] = []
    handoff_followups: list[dict[str, Any]] = []
    gaps.extend(result.get("gaps", []))
    contradictions.extend(result.get("contradictions", []))
    handoff_followups.extend(result.get("consolidation_findings", []))
    inference_receipt = result.get("inference_receipt")
    receipt_written = False
    if isinstance(inference_receipt, dict) and inference_receipt.get("receipt_id"):
        append_unique_by_id(
            paths.case_ledger(case_id, "inference_receipts.yaml"),
            {
                **inference_receipt,
                "case_id": slug(case_id),
                "observed_at": now_iso(),
                "record_kind": "inference_observation",
            },
            "receipt_id",
        )
        receipt_written = True
    for trace in result.get("traces", []):
        gaps.extend(trace.get("gaps", []))
        contradictions.extend(trace.get("contradictions", []))
    for handoff in result.get("handoffs", []):
        for index, missing in enumerate(handoff.get("missing_evidence", []), start=1):
            handoff_followups.append(
                {
                    "gap_id": f"{handoff.get('lead_id', 'lead')}:missing_evidence:{index}",
                    "message": missing,
                    "trace_id": handoff.get("trace_id"),
                    "lead_id": handoff.get("lead_id"),
                    "suggested_next_evidence": handoff.get("next_search_task", ""),
                }
            )

    written_gaps = 0
    for index, gap in enumerate(gaps, start=1):
        gap_id = gap.get("gap_id") or f"gap_{index}"
        record = {"gap_id": gap_id, **gap, "case_id": slug(case_id), "followup_status": "open", "written_at": now_iso()}
        append_unique_by_id(paths.case_ledger(case_id, "gaps.yaml"), record, "gap_id")
        written_gaps += 1
    for index, followup in enumerate(handoff_followups, start=1):
        gap_id = followup.get("gap_id") or followup.get("finding_id") or f"handoff_followup_{index}"
        record = {"gap_id": gap_id, **followup, "case_id": slug(case_id), "followup_status": "open", "written_at": now_iso()}
        append_unique_by_id(paths.case_ledger(case_id, "gaps.yaml"), record, "gap_id")
        written_gaps += 1

    written_contradictions = 0
    for index, contradiction in enumerate(contradictions, start=1):
        contradiction_id = contradiction.get("contradiction_id") or f"contradiction_{index}"
        record = {"contradiction_id": contradiction_id, **contradiction, "case_id": slug(case_id), "followup_status": "open", "written_at": now_iso()}
        append_unique_by_id(paths.case_ledger(case_id, "contradictions.yaml"), record, "contradiction_id")
        written_contradictions += 1

    return {
        "ok": True,
        "gaps_written": written_gaps,
        "contradictions_written": written_contradictions,
        "inference_receipt_written": receipt_written,
    }


def jsonable(data: Any) -> Any:
    return data
