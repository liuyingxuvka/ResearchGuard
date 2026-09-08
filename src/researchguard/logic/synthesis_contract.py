"""Current contract for LogicGuard artifact synthesis.

The contract deliberately has no compatibility reader for the former
``target_goal/profile/max_items`` call.  Editorial selection belongs to the
caller; this module validates the resulting, explicit unit request while the
native LogicGuard depth owner validates argument roles and support.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping


SYNTHESIS_REQUEST_SCHEMA = "researchguard.logic.synthesis-request.v1"
EDITORIAL_PROMINENCE = {"lead", "normal", "brief"}
PLACEMENTS = {"body", "note", "appendix", "omit"}
PROGRESSION_RELATIONS = {
    "establishes",
    "explains",
    "contrasts",
    "narrows",
    "applies",
    "concludes",
    "background",
}


class SelectionRequestError(ValueError):
    """Raised when a selection request cannot be normalized."""


@dataclass(frozen=True)
class SelectionRequest:
    request_id: str
    target_id: str
    target_goal: str
    artifact_kind: str
    reader_id: str
    model_id: str
    model_fingerprint: str
    body_unit_order: tuple[str, ...]
    max_body_units: int
    units: tuple[dict[str, Any], ...]
    source_branch_bindings: tuple[dict[str, Any], ...]
    request_fingerprint: str
    native_depth_receipt_ref: str = ""
    native_mesh_overlay_ref: str = ""
    claim_use_dispositions: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        def _row(value: Any) -> Any:
            return dict(value) if isinstance(value, Mapping) else value

        return {
            "schema": SYNTHESIS_REQUEST_SCHEMA,
            "request_id": self.request_id,
            "target_id": self.target_id,
            "target_goal": self.target_goal,
            "artifact_kind": self.artifact_kind,
            "reader_id": self.reader_id,
            "model_id": self.model_id,
            "model_fingerprint": self.model_fingerprint,
            "body_unit_order": list(self.body_unit_order),
            "max_body_units": self.max_body_units,
            "units": [_row(unit) for unit in self.units],
            "source_branch_bindings": [_row(binding) for binding in self.source_branch_bindings],
            "native_depth_receipt_ref": self.native_depth_receipt_ref,
            "native_mesh_overlay_ref": self.native_mesh_overlay_ref,
            "claim_use_dispositions": [_row(item) for item in self.claim_use_dispositions],
        }


def request_fingerprint(request: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(request), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_selection_request(
    request: Mapping[str, Any] | SelectionRequest,
    *,
    expected_model_id: str,
    expected_model_fingerprint: str,
) -> tuple[SelectionRequest | None, tuple[str, ...]]:
    """Validate the current request and return stable, machine-readable gaps."""

    # A dataclass is only a transport shape.  It may have been assembled by a
    # caller with ``dataclasses.replace`` or by deserialising an untrusted
    # artifact, so it must pass exactly the same checks as a plain mapping.
    # In particular, never trust its cached request_fingerprint.
    if isinstance(request, SelectionRequest):
        request = request.to_dict()
    if not isinstance(request, Mapping):
        return None, ("request_not_mapping",)

    errors: list[str] = []
    schema = request.get("schema")
    if type(schema) is not str or schema != SYNTHESIS_REQUEST_SCHEMA:
        errors.append("invalid_schema")
    required = (
        "request_id", "target_id", "target_goal", "artifact_kind", "reader_id",
        "model_id", "model_fingerprint", "body_unit_order", "max_body_units", "units",
        "source_branch_bindings",
    )
    allowed_request_keys = {
        "schema",
        *required,
        "native_depth_receipt_ref",
        "native_mesh_overlay_ref",
        "claim_use_dispositions",
    }
    errors.extend(
        f"unknown_request_field:{key}"
        for key in sorted(
            set(request).difference(allowed_request_keys),
            key=str,
        )
    )
    for key in required:
        if key not in request or request.get(key) in (None, ""):
            errors.append(f"missing:{key}")

    def _text(key: str) -> str:
        value = request.get(key, "")
        if type(value) is not str or not value.strip():
            errors.append(f"invalid:{key}")
            return ""
        return value

    request_id = _text("request_id")
    target_id = _text("target_id")
    target_goal = _text("target_goal")
    artifact_kind = _text("artifact_kind")
    reader_id = _text("reader_id")
    model_id = _text("model_id")
    model_fp = _text("model_fingerprint")
    if model_id and model_id != expected_model_id:
        errors.append("model_identity_mismatch")
    if model_fp and model_fp != expected_model_fingerprint:
        errors.append("model_fingerprint_mismatch")

    raw_order = request.get("body_unit_order", ())
    raw_units = request.get("units", ())
    raw_bindings = request.get("source_branch_bindings", ())
    if isinstance(raw_order, str) or not isinstance(raw_order, (list, tuple)):
        errors.append("body_unit_order_not_list")
        body_order: tuple[str, ...] = ()
    else:
        body_order = tuple(item for item in raw_order if type(item) is str and item.strip())
        if len(body_order) != len(raw_order):
            errors.append("body_unit_order_items_not_nonempty_strings")
    if isinstance(raw_units, Mapping) or not isinstance(raw_units, (list, tuple)):
        errors.append("units_not_list")
        units: tuple[dict[str, Any], ...] = ()
    else:
        units = tuple(dict(item) for item in raw_units if isinstance(item, Mapping))
        if len(units) != len(raw_units):
            errors.append("unit_not_mapping")
    if isinstance(raw_bindings, Mapping) or not isinstance(raw_bindings, (list, tuple)):
        errors.append("source_branch_bindings_not_list")
        bindings: tuple[dict[str, Any], ...] = ()
    else:
        bindings = tuple(dict(item) for item in raw_bindings if isinstance(item, Mapping))
        if len(bindings) != len(raw_bindings):
            errors.append("source_branch_binding_not_mapping")

    raw_budget = request.get("max_body_units", 0)
    if type(raw_budget) is not int:
        max_body_units = 0
        errors.append("max_body_units_not_integer")
    else:
        max_body_units = raw_budget
        if max_body_units <= 0:
            errors.append("max_body_units_not_positive")

    def _string_list(value: Any, *, field: str, allow_empty: bool = True) -> tuple[str, ...]:
        if not isinstance(value, (list, tuple)) or isinstance(value, str):
            errors.append(f"{field}_not_list")
            return ()
        values = tuple(item for item in value if type(item) is str and item.strip())
        if len(values) != len(value):
            errors.append(f"{field}_items_not_nonempty_strings")
        if not allow_empty and not values:
            errors.append(f"{field}_required")
        if len(set(values)) != len(values):
            errors.append(f"{field}_duplicate")
        return values

    def _acyclic(edges: Mapping[str, str | tuple[str, ...]], *, code: str) -> None:
        state: dict[str, int] = {}

        def visit(node_id: str) -> None:
            if state.get(node_id) == 1:
                errors.append(code)
                return
            if state.get(node_id) == 2:
                return
            state[node_id] = 1
            values = edges.get(node_id, ())
            targets = (values,) if isinstance(values, str) else values
            for target in targets:
                if target in edges:
                    visit(target)
            state[node_id] = 2

        for node_id in edges:
            visit(node_id)

    if isinstance(raw_budget, bool):
        # bool is an int subclass; keep a stable, specific diagnostic.
        errors.append("max_body_units_bool_forbidden")

    optional_depth_ref = request.get("native_depth_receipt_ref", "")
    optional_mesh_ref = request.get("native_mesh_overlay_ref", "")
    if optional_depth_ref not in (None, "") and type(optional_depth_ref) is not str:
        errors.append("native_depth_receipt_ref_not_string")
        optional_depth_ref = ""
    if optional_mesh_ref not in (None, "") and type(optional_mesh_ref) is not str:
        errors.append("native_mesh_overlay_ref_not_string")
        optional_mesh_ref = ""

    raw_claim_use = request.get("claim_use_dispositions", ())
    if isinstance(raw_claim_use, Mapping):
        claim_use_rows = tuple(
            {**dict(value), "claim_id": key}
            for key, value in raw_claim_use.items()
            if isinstance(value, Mapping)
        )
        if len(claim_use_rows) != len(raw_claim_use):
            errors.append("claim_use_dispositions_not_mapping_rows")
    elif isinstance(raw_claim_use, (list, tuple)):
        claim_use_rows = tuple(dict(item) for item in raw_claim_use if isinstance(item, Mapping))
        if len(claim_use_rows) != len(raw_claim_use):
            errors.append("claim_use_disposition_not_mapping")
    else:
        errors.append("claim_use_dispositions_not_list_or_mapping")
        claim_use_rows = ()

    # Validate all unit fields before resolving graph references.  Missing
    # optional-looking graph keys are errors because omitting them would make
    # the graph depend on whichever consumer happens to read it.
    unit_ids: list[str] = []
    unit_by_id: dict[str, dict[str, Any]] = {}
    parent_graph: dict[str, str] = {}
    predecessor_graph: dict[str, tuple[str, ...]] = {}
    unit_required_keys = (
        "unit_id", "parent_unit_id", "reader_question", "unit_job", "claim_ids",
        "predecessor_unit_ids", "progression_relation", "editorial_prominence",
        "placement", "placement_reason", "required",
    )
    for index, unit in enumerate(units):
        unit_label = f"unit[{index}]"
        for key in unit_required_keys:
            if key not in unit:
                errors.append(f"{unit_label}:missing:{key}")
        unit_id = unit.get("unit_id", "")
        if type(unit_id) is not str or not unit_id.strip():
            errors.append(f"{unit_label}:invalid_unit_id")
            unit_id = ""
        else:
            unit_ids.append(unit_id)
            if unit_id in unit_by_id:
                errors.append(f"duplicate_unit_id:{unit_id}")
            else:
                unit_by_id[unit_id] = unit
        for key in ("reader_question", "unit_job", "progression_relation", "editorial_prominence", "placement", "placement_reason"):
            value = unit.get(key)
            if type(value) is not str or not value.strip():
                errors.append(f"unit:{unit_id or index}:invalid:{key}")
        if unit.get("progression_relation") not in PROGRESSION_RELATIONS:
            errors.append(f"unit:{unit_id or index}:invalid_progression_relation")
        if unit.get("editorial_prominence") not in EDITORIAL_PROMINENCE:
            errors.append(f"unit:{unit_id or index}:invalid_editorial_prominence")
        if unit.get("placement") not in PLACEMENTS:
            errors.append(f"unit:{unit_id or index}:invalid_placement")
        if type(unit.get("required")) is not bool:
            errors.append(f"unit:{unit_id or index}:required_not_bool")
        elif unit.get("required") is True and unit.get("placement") == "omit":
            errors.append("required_unit_omitted")
        claims = _string_list(unit.get("claim_ids", ()), field=f"unit:{unit_id or index}:claim_ids", allow_empty=False)
        predecessors = _string_list(unit.get("predecessor_unit_ids", ()), field=f"unit:{unit_id or index}:predecessor_unit_ids")
        predecessor_graph[unit_id] = predecessors
        if unit_id and predecessors:
            if unit_id in predecessors:
                errors.append(f"unit:{unit_id}:self_predecessor")
        parent = unit.get("parent_unit_id")
        if parent is not None and (type(parent) is not str or not parent.strip()):
            errors.append(f"unit:{unit_id or index}:parent_not_null_or_string")
        elif isinstance(parent, str):
            parent_graph[unit_id] = parent
            if parent == unit_id:
                errors.append(f"unit:{unit_id}:self_parent")
        if type(unit.get("claim_ids")) not in (list, tuple):
            # _string_list already reports this; this branch keeps the
            # canonical variable explicit for static/type checkers.
            _ = claims

    if len(set(unit_ids)) != len(unit_ids):
        # Duplicate IDs have already been reported, but this makes the graph
        # diagnostics deterministic if duplicate rows appear in a request.
        errors.append("unit_id_set_not_unique")
    known_ids = set(unit_by_id)
    for unit_id, parent in parent_graph.items():
        if parent not in known_ids:
            errors.append(f"unit:{unit_id}:unknown_parent:{parent}")
    for unit_id, predecessors in predecessor_graph.items():
        for predecessor in predecessors:
            if predecessor not in known_ids:
                errors.append(f"unit:{unit_id}:unknown_predecessor:{predecessor}")
    _acyclic(parent_graph, code="parent_graph_cycle")
    _acyclic(predecessor_graph, code="predecessor_graph_cycle")

    if len(set(body_order)) != len(body_order):
        errors.append("body_unit_order_duplicate")
    body_ids = {unit_id for unit_id, unit in unit_by_id.items() if unit.get("placement") == "body"}
    if set(body_order) != body_ids:
        errors.append("body_unit_order_must_cover_body_units")
    if len(body_order) > max_body_units > 0:
        # A syntactically valid request may exceed its explicit editorial
        # budget.  The synthesis owner classifies that as blocked_budget so a
        # caller can repair the budget without losing other validation data.
        pass
    order_index = {unit_id: index for index, unit_id in enumerate(body_order)}
    for unit_id, unit in unit_by_id.items():
        predecessors = predecessor_graph.get(unit_id, ())
        if unit.get("placement") != "body":
            continue
        for predecessor in predecessors:
            predecessor_unit = unit_by_id.get(predecessor)
            if predecessor_unit is None:
                continue
            if predecessor_unit.get("placement") != "body":
                errors.append(f"unit:{unit_id}:body_predecessor_not_body:{predecessor}")
            elif predecessor in order_index and order_index[predecessor] >= order_index.get(unit_id, 10**9):
                errors.append(f"unit:{unit_id}:predecessor_order_violation:{predecessor}")

    # A body unit cannot silently depend on an appendix/omit unit through its
    # parent relation either.  The reader-facing graph must remain visible.
    for unit_id, parent in parent_graph.items():
        unit = unit_by_id.get(unit_id)
        parent_unit = unit_by_id.get(parent)
        if unit and parent_unit and unit.get("placement") == "body" and parent_unit.get("placement") != "body":
            errors.append(f"unit:{unit_id}:body_parent_not_body:{parent}")

    # Binding rows are strict identity assertions.  The source library and
    # native receipt owners perform the content checks later; this layer still
    # refuses malformed or ambiguous rows.
    binding_keys: dict[tuple[str, str, str], dict[str, Any]] = {}
    for index, binding in enumerate(bindings):
        destination = binding.get("destination_unit_id")
        if type(destination) is not str or not destination.strip():
            errors.append(f"binding[{index}]:invalid_destination_unit_id")
            destination = ""
        elif destination not in known_ids:
            errors.append(f"binding[{index}]:unknown_destination_unit:{destination}")
        for key in ("branch_id", "source_id", "current_native_evidence_ref"):
            if type(binding.get(key)) is not str or not binding.get(key, "").strip():
                errors.append(f"binding[{index}]:invalid:{key}")
        for key in ("project_id", "source_model_fingerprint"):
            if key in binding and binding.get(key) not in (None, "") and type(binding.get(key)) is not str:
                errors.append(f"binding[{index}]:invalid:{key}")
        if "source_node_ids" in binding and not isinstance(binding.get("source_node_ids"), (list, tuple)):
            errors.append(f"binding[{index}]:source_node_ids_not_list")
        elif "source_node_ids" in binding:
            _string_list(binding.get("source_node_ids"), field=f"binding[{index}]:source_node_ids")
        anchor_node = binding.get("anchor_node_id", "")
        anchor_block = binding.get("anchor_block_id", "")
        if bool(anchor_node) == bool(anchor_block) or any(type(value) is not str for value in (anchor_node, anchor_block) if value not in (None, "")):
            errors.append(f"binding[{index}]:exactly_one_anchor_required")
        claim_ids = _string_list(binding.get("claim_ids", ()), field=f"binding[{index}]:claim_ids", allow_empty=False)
        if destination in unit_by_id:
            unit_claims = set(_string_list(unit_by_id[destination].get("claim_ids", ()), field=f"unit:{destination}:claim_ids"))
            for claim_id in claim_ids:
                if claim_id not in unit_claims:
                    errors.append(f"binding[{index}]:claim_not_in_destination_unit:{claim_id}")
        key = (str(binding.get("source_id", "")), str(binding.get("branch_id", "")), str(destination))
        if key in binding_keys:
            if binding != binding_keys[key]:
                errors.append(f"duplicate_source_branch_binding_conflict:{key[0]}:{key[1]}:{key[2]}")
            else:
                errors.append(f"duplicate_source_branch_binding:{key[0]}:{key[1]}:{key[2]}")
        else:
            binding_keys[key] = binding

    claim_ids_in_units = {claim_id for unit in units for claim_id in _string_list(unit.get("claim_ids", ()), field="claim_ids")}
    claim_use_ids: set[str] = set()
    for index, row in enumerate(claim_use_rows):
        claim_id = row.get("claim_id")
        if type(claim_id) is not str or not claim_id.strip():
            errors.append(f"claim_use[{index}]:invalid_claim_id")
            claim_id = ""
        elif claim_id not in claim_ids_in_units:
            errors.append(f"claim_use[{index}]:unknown_claim:{claim_id}")
        if claim_id in claim_use_ids:
            errors.append(f"claim_use[{index}]:duplicate_claim:{claim_id}")
        claim_use_ids.add(str(claim_id))
        if row.get("use") not in {"assert", "qualified_discussion", "rejected_alternative"}:
            errors.append(f"claim_use[{index}]:invalid_use")
        for key in ("native_allowed_wording", "native_evaluation_ref"):
            if type(row.get(key)) is not str or not row.get(key, "").strip():
                errors.append(f"claim_use[{index}]:missing:{key}")

    if errors:
        return None, tuple(dict.fromkeys(errors))

    normalized_bindings = tuple(binding_keys.values())
    canonical = {
        "schema": SYNTHESIS_REQUEST_SCHEMA,
        "request_id": request_id,
        "target_id": target_id,
        "target_goal": target_goal,
        "artifact_kind": artifact_kind,
        "reader_id": reader_id,
        "model_id": model_id,
        "model_fingerprint": model_fp,
        "body_unit_order": list(body_order),
        "max_body_units": max_body_units,
        "units": [dict(unit) for unit in units],
        "source_branch_bindings": [dict(binding) for binding in normalized_bindings],
        "native_depth_receipt_ref": str(optional_depth_ref or ""),
        "native_mesh_overlay_ref": str(optional_mesh_ref or ""),
        "claim_use_dispositions": [dict(item) for item in claim_use_rows],
    }
    normalized = SelectionRequest(
        request_id=request_id,
        target_id=target_id,
        target_goal=target_goal,
        artifact_kind=artifact_kind,
        reader_id=reader_id,
        model_id=model_id,
        model_fingerprint=model_fp,
        body_unit_order=body_order,
        max_body_units=max_body_units,
        units=units,
        source_branch_bindings=normalized_bindings,
        request_fingerprint=request_fingerprint(canonical),
        native_depth_receipt_ref=str(optional_depth_ref or ""),
        native_mesh_overlay_ref=str(optional_mesh_ref or ""),
        claim_use_dispositions=tuple(dict(item) for item in claim_use_rows),
    )
    return normalized, ()


__all__ = [
    "EDITORIAL_PROMINENCE",
    "PLACEMENTS",
    "PROGRESSION_RELATIONS",
    "SYNTHESIS_REQUEST_SCHEMA",
    "SelectionRequest",
    "SelectionRequestError",
    "request_fingerprint",
    "validate_selection_request",
]
