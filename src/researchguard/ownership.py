"""Source-owned copy projections shared by checking and both handoff syncs.

This foundation module has no route imports. Callers supply the existing native
content-hash function; it never introduces another provenance hash or resolver.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class OwnedField:
    owner: str
    copy: str
    fallback: str | None = None
    empty: Any = None


TRACE_ANCHOR_FIELDS = (
    OwnedField("text", "raw_text", "normalized_summary", ""),
    OwnedField("source_id", "source_id"),
    OwnedField("locator", "locator"),
)
TRACE_SOURCE_FIELDS = (
    OwnedField("title", "title", empty=""),
    OwnedField("url", "url"),
    OwnedField("source_date", "source_date"),
    OwnedField("lineage_id", "lineage_id", "source_id"),
)
LOGIC_ANCHOR_FIELDS = (
    OwnedField("text", "quote", empty=""),
    OwnedField("source_id", "source_id"),
    OwnedField("anchor_id", "locator"),
)
LOGIC_SOURCE_FIELDS = (
    OwnedField("url", "source_reference"),
    OwnedField("source_date", "source_date"),
)
# The same copy columns are used through the existing trace handoff envelope.
HANDOFF_ANCHOR_FIELDS = (
    OwnedField("text", "quote", empty=""),
    OwnedField("source_id", "source_id"),
    OwnedField("evidence_id", "locator"),
)
HANDOFF_SOURCE_FIELDS = tuple(OwnedField(field.copy, field.copy) for field in LOGIC_SOURCE_FIELDS)


def _get(record: Any, key: str, default: Any = None) -> Any:
    return record.get(key, default) if isinstance(record, Mapping) else getattr(record, key, default)


def _project(record: Any, fields: tuple[OwnedField, ...]) -> dict[str, Any]:
    output = {}
    for field in fields:
        value = _get(record, field.owner)
        if value in (None, "") and field.fallback:
            value = _get(record, field.fallback)
        output[field.copy] = field.empty if value in (None, "") else value
    return output


def trace_anchor_owned(anchor: Any) -> dict[str, Any]:
    return _project(anchor, TRACE_ANCHOR_FIELDS)


def trace_source_owned(source: Any) -> dict[str, Any]:
    return _project(source, TRACE_SOURCE_FIELDS)


def handoff_source_owned(source: Any) -> dict[str, Any]:
    return _project(source, LOGIC_SOURCE_FIELDS)


def handoff_logic_owned(item: Mapping[str, Any], *, content_hash_for: Callable) -> dict[str, Any]:
    """Owned provenance only; optional absent source fields do not erase old copies."""
    fields = _project(item, HANDOFF_ANCHOR_FIELDS)
    fields["content_hash"] = content_hash_for(fields["quote"])
    if fields["quote"] == "":
        del fields["quote"]
    for field in HANDOFF_SOURCE_FIELDS:
        if field.owner in item:
            fields.update(_project(item, (field,)))
    return fields


def refresh_logic_provenance(existing: dict, incoming: Mapping) -> bool:
    """Refresh only declared copy columns, keeping hash-only records hash-only."""
    updated = False
    if "quote" not in incoming and "content_hash" in incoming and "quote" in existing:
        del existing["quote"]
        updated = True
    fields = [field.copy for field in LOGIC_ANCHOR_FIELDS + LOGIC_SOURCE_FIELDS]
    fields.append("content_hash")
    for field in fields:
        if field not in incoming or (field == "quote" and not existing.get("quote")):
            continue
        if existing.get(field) != incoming[field]:
            existing[field] = incoming[field]
            updated = True
    return updated


def copied_content_problems(models: Mapping[str, Any], *, content_hash_for: Callable) -> list[str]:
    """Compare nonempty copied values with the one SourceGuard owner, exactly."""
    source = models.get("source")
    if source is None:
        return []
    sources = {_get(row, "source_id"): row for row in _get(source, "sources", ())}
    anchors = {_get(row, "anchor_id"): row for row in _get(source, "anchors", ())}
    problems = []
    def compare(kind, identity, row, expected):
        for field, value in expected.items():
            actual = _get(row, field)
            if actual not in (None, "") and actual != value:
                code = f"copy_drift:{kind}:{identity}:{field}"
                if code not in problems:
                    problems.append(code)
    trace = models.get("trace")
    if trace is not None:
        for row in _get(trace, "sources", ()):
            identity = _get(row, "source_id")
            if identity in sources:
                compare("trace", identity, row, trace_source_owned(sources[identity]))
        for row in _get(trace, "evidence", ()):
            identity = _get(row, "evidence_id")
            if identity in anchors:
                compare("trace", identity, row, trace_anchor_owned(anchors[identity]))
    logic = models.get("logic")
    if logic is not None:
        for node_id, node in _get(logic, "nodes", {}).items():
            for provenance in _get(node, "provenance", ()):
                anchor = anchors.get(_get(provenance, "locator"))
                if anchor is None:
                    continue
                expected = _project(anchor, LOGIC_ANCHOR_FIELDS)
                owner_source = sources.get(_get(anchor, "source_id"))
                if owner_source is not None:
                    expected.update(_project(owner_source, LOGIC_SOURCE_FIELDS))
                if not _get(provenance, "quote"):
                    expected.pop("quote")
                    expected["content_hash"] = content_hash_for(_get(anchor, "text", ""))
                compare("logic", node_id, provenance, expected)
    return problems
