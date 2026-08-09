"""SourceGuard-owned typed information blueprint operations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from typing import Iterable, Literal, Mapping

from ..native_receipts import (
    NativeReceiptExpectation,
    NativeReceiptReference,
    native_receipt_expectation,
    resolve_expected_native_receipts,
)
from ..target_authority import (
    ExpectedTargetAnchor,
    NativeTargetMaterialReplay,
    TargetAuthorityItem,
    TargetPurposeAuthority,
    content_addressed_request_id,
    _issue_replayed_target_authority,
    read_target_material_bytes,
    verify_registered_target_authority,
)

from .depth import model_fingerprint
from .handoff import affected_member_handoffs
from .guard_contract import TARGET_PURPOSE_RESULT_SCHEMA, prove_target_model_contract
from .schema import (
    BLUEPRINT_OUTPUT_DISPOSITIONS,
    BeliefState,
    to_plain,
    validate_graph_edges,
    validate_model_guard_binding,
)
from .task_iteration import affected_source_obligations

SOURCE_BLUEPRINT_SCHEMA = "researchguard.source.information-blueprint.v1"
SOURCE_TARGET_AUTHORITY_OWNER = "researchguard.source.target-purpose"
SOURCE_TARGET_AUTHORITY_TOOL = "researchguard.source.guard-contract+target-parser"
SOURCE_TARGET_ADAPTER_ID = "researchguard.source.target-material-adapter"
SOURCE_TARGET_ADAPTER_VERSION = "2"
SOURCE_TARGET_MATERIAL_SCHEMA = "researchguard.source.target-material.v1"


def _digest(value: object) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(body.encode('utf-8')).hexdigest()}"


@dataclass(frozen=True)
class TargetUnitPort:
    port_id: str
    direction: Literal["input", "output"]
    schema_id: str

    def __post_init__(self) -> None:
        if not self.port_id.strip() or not self.schema_id.strip() or self.direction not in {"input", "output"}:
            raise ValueError("target-unit ports require current id, direction, and schema")

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class TargetUnit:
    unit_id: str
    parent_unit_id: str
    depth: int
    child_unit_ids: tuple[str, ...]
    ports: tuple[TargetUnitPort, ...]
    output_dispositions: tuple[tuple[str, Literal["terminal", "excluded", "unresolved"]], ...] = ()

    def __post_init__(self) -> None:
        if not self.unit_id.strip() or self.depth < 0:
            raise ValueError("target units require stable identity and non-negative depth")
        if len(set(self.child_unit_ids)) != len(self.child_unit_ids):
            raise ValueError("target-unit child ids must be unique")
        port_ids = tuple(item.port_id for item in self.ports)
        if len(port_ids) != len(set(port_ids)):
            raise ValueError("target-unit port ids must be unique")
        disposed = tuple(item[0] for item in self.output_dispositions)
        if len(disposed) != len(set(disposed)):
            raise ValueError("target-unit output dispositions must be unique")

    def to_dict(self) -> dict[str, object]:
        return {
            "unit_id": self.unit_id,
            "parent_unit_id": self.parent_unit_id,
            "depth": self.depth,
            "child_unit_ids": list(self.child_unit_ids),
            "ports": [item.to_dict() for item in self.ports],
            "output_dispositions": [list(item) for item in self.output_dispositions],
        }


@dataclass(frozen=True)
class TargetUnitInterfaceBinding:
    binding_id: str
    child_unit_id: str
    child_output_port_id: str
    parent_unit_id: str
    parent_input_port_id: str
    payload_schema_id: str
    consumer_status: Literal["consumed", "unresolved", "excluded"]
    disposition_reason: str = ""

    def __post_init__(self) -> None:
        required = (
            self.binding_id,
            self.child_unit_id,
            self.child_output_port_id,
            self.parent_unit_id,
            self.parent_input_port_id,
            self.payload_schema_id,
        )
        if any(not value.strip() for value in required):
            raise ValueError("target-unit interfaces require exact endpoint and schema identities")
        if self.consumer_status not in {"consumed", "unresolved", "excluded"}:
            raise ValueError("target-unit interface consumer_status is not current")
        if self.consumer_status != "consumed" and not self.disposition_reason.strip():
            raise ValueError("unresolved or excluded target-unit interfaces require a reason")

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class InformationTargetUniverse:
    universe_id: str
    target_root_unit_id: str
    target_units: tuple[TargetUnit, ...]
    target_unit_interfaces: tuple[TargetUnitInterfaceBinding, ...]
    required_target_unit_ids: tuple[str, ...]
    required_gap_ids: tuple[str, ...]
    required_source_role_ids: tuple[str, ...]
    required_lineage_slot_ids: tuple[str, ...]
    required_anchor_requirement_ids: tuple[str, ...]
    required_handoff_ids: tuple[str, ...]
    known_good_case_ids: tuple[str, ...]
    known_bad_case_ids: tuple[str, ...]
    native_purpose_receipt: Mapping[str, object] | None = None
    native_receipt_refs: tuple[NativeReceiptReference, ...] = ()
    target_authority: TargetPurposeAuthority | None = None

    def __post_init__(self) -> None:
        if not self.universe_id.strip():
            raise ValueError("information target universe requires universe_id")
        if not self.target_root_unit_id.strip():
            raise ValueError("information target universe requires target_root_unit_id")
        for name in (
            "required_target_unit_ids",
            "required_gap_ids",
            "required_source_role_ids",
            "required_lineage_slot_ids",
            "required_anchor_requirement_ids",
            "required_handoff_ids",
            "known_good_case_ids",
            "known_bad_case_ids",
        ):
            values = getattr(self, name)
            if len(values) != len(set(values)) or any(not value.strip() for value in values):
                raise ValueError(f"{name} must contain unique non-empty ids")
        unit_ids = tuple(item.unit_id for item in self.target_units)
        if not unit_ids or len(unit_ids) != len(set(unit_ids)):
            raise ValueError("information target units must be non-empty and unique")
        binding_ids = tuple(item.binding_id for item in self.target_unit_interfaces)
        if len(binding_ids) != len(set(binding_ids)):
            raise ValueError("target-unit interface ids must be unique")
        receipt_ids = tuple(item.receipt_id for item in self.native_receipt_refs)
        if len(receipt_ids) != len(set(receipt_ids)):
            raise ValueError("information target native receipt ids must be unique")

    @property
    def fingerprint(self) -> str:
        return _digest(
            {
                "universe_id": self.universe_id,
                "target_root_unit_id": self.target_root_unit_id,
                "target_units": [item.to_dict() for item in self.target_units],
                "target_unit_interfaces": [item.to_dict() for item in self.target_unit_interfaces],
                "required_target_unit_ids": list(self.required_target_unit_ids),
                "required_gap_ids": list(self.required_gap_ids),
                "required_source_role_ids": list(self.required_source_role_ids),
                "required_lineage_slot_ids": list(self.required_lineage_slot_ids),
                "required_anchor_requirement_ids": list(self.required_anchor_requirement_ids),
                "required_handoff_ids": list(self.required_handoff_ids),
                "known_good_case_ids": list(self.known_good_case_ids),
                "known_bad_case_ids": list(self.known_bad_case_ids),
                "native_purpose_receipt": dict(self.native_purpose_receipt) if self.native_purpose_receipt else None,
                "native_receipt_refs": [],
                "target_authority": self.target_authority.to_dict() if self.target_authority else None,
            }
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "universe_id": self.universe_id,
            "target_root_unit_id": self.target_root_unit_id,
            "target_units": [item.to_dict() for item in self.target_units],
            "target_unit_interfaces": [item.to_dict() for item in self.target_unit_interfaces],
            "required_target_unit_ids": list(self.required_target_unit_ids),
            "required_gap_ids": list(self.required_gap_ids),
            "required_source_role_ids": list(self.required_source_role_ids),
            "required_lineage_slot_ids": list(self.required_lineage_slot_ids),
            "required_anchor_requirement_ids": list(self.required_anchor_requirement_ids),
            "required_handoff_ids": list(self.required_handoff_ids),
            "known_good_case_ids": list(self.known_good_case_ids),
            "known_bad_case_ids": list(self.known_bad_case_ids),
            "native_purpose_receipt": dict(self.native_purpose_receipt) if self.native_purpose_receipt else None,
            "native_receipt_refs": [item.to_dict() for item in self.native_receipt_refs],
            "target_authority": self.target_authority.to_dict() if self.target_authority else None,
            "universe_fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "InformationTargetUniverse":
        allowed = {
            "universe_id", "target_root_unit_id", "target_units", "target_unit_interfaces",
            "required_target_unit_ids", "required_gap_ids", "required_source_role_ids",
            "required_lineage_slot_ids", "required_anchor_requirement_ids", "required_handoff_ids",
            "known_good_case_ids", "known_bad_case_ids", "native_purpose_receipt", "native_receipt_refs", "target_authority", "universe_fingerprint",
        }
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ValueError(f"information target universe contains unknown fields: {unknown!r}")
        keys = (
            "required_target_unit_ids",
            "required_gap_ids",
            "required_source_role_ids",
            "required_lineage_slot_ids",
            "required_anchor_requirement_ids",
            "required_handoff_ids",
            "known_good_case_ids",
            "known_bad_case_ids",
        )
        unit_rows = raw.get("target_units")
        interface_rows = raw.get("target_unit_interfaces")
        if not isinstance(unit_rows, list) or not isinstance(interface_rows, list):
            raise ValueError("target_units and target_unit_interfaces must be lists")
        units: list[TargetUnit] = []
        for index, row in enumerate(unit_rows):
            if not isinstance(row, Mapping):
                raise ValueError(f"target_units[{index}] must be an object")
            unknown = sorted(set(row) - {"unit_id", "parent_unit_id", "depth", "child_unit_ids", "ports", "output_dispositions"})
            if unknown:
                raise ValueError(f"target_units[{index}] contains unknown fields: {unknown!r}")
            port_rows = row.get("ports")
            if not isinstance(port_rows, list):
                raise ValueError(f"target_units[{index}].ports must be a list")
            ports: list[TargetUnitPort] = []
            for port_index, port in enumerate(port_rows):
                if not isinstance(port, Mapping):
                    raise ValueError(f"target_units[{index}].ports[{port_index}] must be an object")
                unknown = sorted(set(port) - {"port_id", "direction", "schema_id"})
                if unknown:
                    raise ValueError(f"target_units[{index}].ports[{port_index}] contains unknown fields: {unknown!r}")
                ports.append(TargetUnitPort(str(port.get("port_id", "")), str(port.get("direction", "")), str(port.get("schema_id", ""))))
            dispositions = row.get("output_dispositions", [])
            if not isinstance(dispositions, list) or any(not isinstance(item, list) or len(item) != 2 for item in dispositions):
                raise ValueError(f"target_units[{index}].output_dispositions must contain pairs")
            children = row.get("child_unit_ids")
            if not isinstance(children, list):
                raise ValueError(f"target_units[{index}].child_unit_ids must be a list")
            units.append(TargetUnit(str(row.get("unit_id", "")), str(row.get("parent_unit_id", "")), int(row.get("depth", -1)), tuple(str(item) for item in children), tuple(ports), tuple((str(item[0]), str(item[1])) for item in dispositions)))
        interfaces: list[TargetUnitInterfaceBinding] = []
        for index, row in enumerate(interface_rows):
            if not isinstance(row, Mapping):
                raise ValueError(f"target_unit_interfaces[{index}] must be an object")
            allowed_interface = {"binding_id", "child_unit_id", "child_output_port_id", "parent_unit_id", "parent_input_port_id", "payload_schema_id", "consumer_status", "disposition_reason"}
            unknown = sorted(set(row) - allowed_interface)
            if unknown:
                raise ValueError(f"target_unit_interfaces[{index}] contains unknown fields: {unknown!r}")
            interfaces.append(TargetUnitInterfaceBinding(**{key: str(row.get(key, "")) for key in allowed_interface}))
        native_receipt = raw.get("native_purpose_receipt")
        if native_receipt is not None and not isinstance(native_receipt, Mapping):
            raise ValueError("native_purpose_receipt must be an object")
        result = cls(
            universe_id=str(raw.get("universe_id", "")),
            target_root_unit_id=str(raw.get("target_root_unit_id", "")),
            target_units=tuple(units),
            target_unit_interfaces=tuple(interfaces),
            native_purpose_receipt=dict(native_receipt) if native_receipt is not None else None,
            native_receipt_refs=tuple(
                NativeReceiptReference.from_dict(item)
                for item in raw.get("native_receipt_refs", [])
                if isinstance(item, Mapping)
            ),
            target_authority=(
                TargetPurposeAuthority.from_dict(raw["target_authority"])
                if isinstance(raw.get("target_authority"), Mapping)
                else None
            ),
            **{key: tuple(str(item) for item in raw.get(key, [])) for key in keys},
        )
        supplied = str(raw.get("universe_fingerprint", ""))
        if supplied and supplied != result.fingerprint:
            raise ValueError("information target universe fingerprint mismatch")
        return result


def source_target_subject_fingerprint(
    state: BeliefState, universe: InformationTargetUniverse
) -> str:
    contract = state.guard_contract
    return _digest(
        {
            "model_id": contract.model_id if contract else "",
            "candidate_contract_fingerprint": state.candidate_contract_fingerprint,
            "universe_id": universe.universe_id,
            "target_root_unit_id": universe.target_root_unit_id,
            "target_units": [item.to_dict() for item in universe.target_units],
            "target_unit_interfaces": [item.to_dict() for item in universe.target_unit_interfaces],
            "required_target_unit_ids": list(universe.required_target_unit_ids),
            "required_gap_ids": list(universe.required_gap_ids),
            "required_source_role_ids": list(universe.required_source_role_ids),
            "required_lineage_slot_ids": list(universe.required_lineage_slot_ids),
            "required_anchor_requirement_ids": list(universe.required_anchor_requirement_ids),
            "required_handoff_ids": list(universe.required_handoff_ids),
            "known_good_case_ids": list(universe.known_good_case_ids),
            "known_bad_case_ids": list(universe.known_bad_case_ids),
            "failure_class_ids": [
                item.failure_id for item in (contract.prevented_failures if contract else ())
            ],
        }
    )


def source_target_purpose_fingerprint(state: BeliefState) -> str:
    contract = state.guard_contract
    return _digest(
        {
            "model_id": contract.model_id if contract else "",
            "purpose": contract.purpose if contract else "",
            "claim_boundary": contract.claim_boundary if contract else "",
        }
    )


def source_target_request_fingerprint(state: BeliefState) -> str:
    contract = state.guard_contract
    return _digest(
        {
            "model_id": contract.model_id if contract else "",
            "purpose": contract.purpose if contract else "",
            "claim_boundary": contract.claim_boundary if contract else "",
            "candidate_contract_fingerprint": state.candidate_contract_fingerprint,
        }
    )


def _noncurrent_source_replay(
    state: BeliefState,
    universe: InformationTargetUniverse,
    locator: str,
    status: Literal["unverified", "failed"],
    detail: str,
) -> NativeTargetMaterialReplay:
    contract = state.guard_contract
    target_id = contract.model_id if contract else "sourceguard-unbound-target"
    marker = _digest({"locator": locator, "status": status})
    request_fingerprint = source_target_request_fingerprint(state)
    target_fingerprint = source_target_subject_fingerprint(state, universe)
    return NativeTargetMaterialReplay(
        adapter_id=SOURCE_TARGET_ADAPTER_ID,
        adapter_version=SOURCE_TARGET_ADAPTER_VERSION,
        request_id=content_addressed_request_id(request_fingerprint),
        request_fingerprint=request_fingerprint,
        input_id=locator or "unreplayable:source-target-material",
        input_fingerprint=marker,
        target_id=target_id,
        target_revision=target_fingerprint,
        target_fingerprint=target_fingerprint,
        purpose_fingerprint=source_target_purpose_fingerprint(state),
        material_locator=locator or "unreplayable:source-target-material",
        material_media_type="application/json",
        material_fingerprint=marker,
        items=(),
        status=status,
        detail=detail,
    )


def replay_information_target_material(
    state: BeliefState,
    universe: InformationTargetUniverse,
    locator: str,
) -> NativeTargetMaterialReplay:
    """SourceGuard-owned parser for raw target tree and obligation material."""

    body, material_fingerprint, gap = read_target_material_bytes(locator)
    if body is None:
        return _noncurrent_source_replay(state, universe, locator, "unverified", gap)
    try:
        raw = json.loads(body.decode("utf-8"))
        if not isinstance(raw, Mapping) or set(raw) != {
            "schema_version", "request_contract", "target_id", "target_revision",
            "target_snapshot",
        }:
            raise ValueError("source target material has an unknown or missing root field")
        if raw.get("schema_version") != SOURCE_TARGET_MATERIAL_SCHEMA:
            raise ValueError("source target material schema is not current")
        request = raw.get("request_contract")
        snapshot = raw.get("target_snapshot")
        if not isinstance(request, Mapping) or set(request) != {
            "request_id", "model_id", "purpose", "claim_boundary",
            "candidate_contract_fingerprint",
        }:
            raise ValueError("source request contract is not exact-current")
        snapshot_keys = {
            "universe_id", "target_root_unit_id", "target_units",
            "target_unit_interfaces", "required_target_unit_ids", "required_gap_ids",
            "required_source_role_ids", "required_lineage_slot_ids",
            "required_anchor_requirement_ids", "required_handoff_ids",
            "known_good_case_ids", "known_bad_case_ids", "failure_class_ids",
        }
        if not isinstance(snapshot, Mapping) or set(snapshot) != snapshot_keys:
            raise ValueError("source target snapshot is not exact-current")
        parsed = InformationTargetUniverse.from_dict(
            {
                **{key: snapshot[key] for key in snapshot_keys if key != "failure_class_ids"},
                "native_purpose_receipt": None,
                "target_authority": None,
                "universe_fingerprint": "",
            }
        )
        failure_ids = snapshot["failure_class_ids"]
        if not isinstance(failure_ids, list) or any(not str(value).strip() for value in failure_ids):
            raise ValueError("source failure_class_ids must be a list of ids")
        items: list[TargetAuthorityItem] = []
        for unit in parsed.target_units:
            items.append(TargetAuthorityItem("target-unit", unit.unit_id, "required"))
            items.extend(
                TargetAuthorityItem("target-port", port.port_id, "required")
                for port in unit.ports
            )
        items.extend(
            TargetAuthorityItem("target-interface", binding.binding_id, "required")
            for binding in parsed.target_unit_interfaces
        )
        for kind, values in (
            ("gap", parsed.required_gap_ids),
            ("source-role", parsed.required_source_role_ids),
            ("lineage-slot", parsed.required_lineage_slot_ids),
            ("anchor-requirement", parsed.required_anchor_requirement_ids),
            ("handoff", parsed.required_handoff_ids),
            ("known-good-case", parsed.known_good_case_ids),
            ("known-bad-case", parsed.known_bad_case_ids),
            ("failure-class", tuple(str(value) for value in failure_ids)),
        ):
            items.extend(TargetAuthorityItem(kind, object_id, "required") for object_id in values)
        request_material = {
            "model_id": str(request["model_id"]),
            "purpose": str(request["purpose"]),
            "claim_boundary": str(request["claim_boundary"]),
            "candidate_contract_fingerprint": str(request["candidate_contract_fingerprint"]),
        }
        target_subject = {
            "model_id": str(request["model_id"]),
            "candidate_contract_fingerprint": str(request["candidate_contract_fingerprint"]),
            **dict(snapshot),
        }
        request_fingerprint = _digest(request_material)
        target_fingerprint = _digest(target_subject)
        return NativeTargetMaterialReplay(
            adapter_id=SOURCE_TARGET_ADAPTER_ID,
            adapter_version=SOURCE_TARGET_ADAPTER_VERSION,
            request_id=str(request["request_id"]),
            request_fingerprint=request_fingerprint,
            input_id=locator,
            input_fingerprint=material_fingerprint,
            target_id=str(raw["target_id"]),
            target_revision=str(raw["target_revision"]),
            target_fingerprint=target_fingerprint,
            purpose_fingerprint=_digest(
                {
                    "model_id": str(request["model_id"]),
                    "purpose": str(request["purpose"]),
                    "claim_boundary": str(request["claim_boundary"]),
                }
            ),
            material_locator=locator,
            material_media_type="application/json",
            material_fingerprint=material_fingerprint,
            items=tuple(items),
            status="current",
        )
    except Exception as exc:
        return _noncurrent_source_replay(state, universe, locator, "failed", str(exc))


def _bind_information_target_authority(
    state: BeliefState,
    universe: InformationTargetUniverse,
    *,
    expected_target_anchor: ExpectedTargetAnchor,
) -> InformationTargetUniverse:
    """Replay only the externally admitted SourceGuard information target."""

    contract = state.guard_contract
    if contract is None:
        raise ValueError("SourceGuard target authority requires the current native guard contract")
    replay = replay_information_target_material(
        state, universe, expected_target_anchor.material_locator
    )
    authority = _issue_replayed_target_authority(
        member_id="sourceguard",
        owner_id=SOURCE_TARGET_AUTHORITY_OWNER,
        tool_id=SOURCE_TARGET_AUTHORITY_TOOL,
        tool_revision="1",
        expected_target_anchor=expected_target_anchor,
        replay=replay,
    )
    return replace(universe, target_authority=authority)


@dataclass(frozen=True)
class SourceBlueprintGap:
    code: str
    object_id: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class SourceBlueprintResult:
    status: Literal["complete", "incomplete"]
    model_fingerprint: str
    universe_fingerprint: str
    blueprint_fingerprint: str
    deepest_proven_layer: str
    first_unresolved_gap: str
    native_open_gap_ids: tuple[str, ...]
    unconsumed_candidate_ids: tuple[str, ...]
    gaps: tuple[SourceBlueprintGap, ...]
    layer_statuses: tuple[dict[str, object], ...]
    claim_boundary: str = (
        "SourceGuard qualifies discovery identities, anchors, lineage, and information gaps only. "
        "It does not decide final argument truth, causal conclusions, or completed storylines."
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": SOURCE_BLUEPRINT_SCHEMA,
            "status": self.status,
            "model_fingerprint": self.model_fingerprint,
            "universe_fingerprint": self.universe_fingerprint,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "deepest_proven_layer": self.deepest_proven_layer,
            "first_unresolved_gap": self.first_unresolved_gap,
            "native_open_gap_ids": list(self.native_open_gap_ids),
            "unconsumed_candidate_ids": list(self.unconsumed_candidate_ids),
            "gaps": [item.to_dict() for item in self.gaps],
            "layer_statuses": list(self.layer_statuses),
            "claim_boundary": self.claim_boundary,
        }


def _edge_set(state: BeliefState) -> set[tuple[str, str, str]]:
    return {(item.source_id, item.relation_type, item.target_id) for item in state.graph_edges}


def _require_edge(
    edges: set[tuple[str, str, str]],
    source_id: str,
    relation: str,
    target_id: str,
    gaps: list[SourceBlueprintGap],
) -> None:
    if (source_id, relation, target_id) not in edges:
        gaps.append(SourceBlueprintGap("missing-interface-edge", target_id, f"{source_id} -[{relation}]-> {target_id}"))


def _target_unit_gaps(universe: InformationTargetUniverse) -> tuple[list[SourceBlueprintGap], list[SourceBlueprintGap]]:
    hierarchy: list[SourceBlueprintGap] = []
    interfaces: list[SourceBlueprintGap] = []
    units = {item.unit_id: item for item in universe.target_units}
    roots = sorted(item.unit_id for item in universe.target_units if not item.parent_unit_id)
    if roots != [universe.target_root_unit_id]:
        hierarchy.append(SourceBlueprintGap("invalid-target-root", universe.target_root_unit_id, f"roots={roots}"))
    declared_parents: dict[str, list[str]] = {}
    for parent in universe.target_units:
        for child_id in parent.child_unit_ids:
            declared_parents.setdefault(child_id, []).append(parent.unit_id)
            child = units.get(child_id)
            if child is None:
                hierarchy.append(SourceBlueprintGap("missing-target-child", child_id, parent.unit_id))
            elif child.parent_unit_id != parent.unit_id:
                hierarchy.append(SourceBlueprintGap("target-parent-child-mismatch", child_id, parent.unit_id))
            elif child.depth != parent.depth + 1:
                hierarchy.append(SourceBlueprintGap("target-depth-jump", child_id, f"{parent.depth}->{child.depth}"))
    for unit in universe.target_units:
        owners = declared_parents.get(unit.unit_id, [])
        if unit.unit_id != universe.target_root_unit_id and len(owners) != 1:
            hierarchy.append(SourceBlueprintGap("target-parent-owner-count", unit.unit_id, f"owners={sorted(owners)}"))
        if unit.parent_unit_id and unit.parent_unit_id not in units:
            hierarchy.append(SourceBlueprintGap("missing-target-parent", unit.unit_id, unit.parent_unit_id))
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(unit_id: str) -> None:
        if unit_id in visiting:
            hierarchy.append(SourceBlueprintGap("target-hierarchy-cycle", unit_id, "cycle detected"))
            return
        if unit_id in visited or unit_id not in units:
            return
        visiting.add(unit_id)
        for child_id in units[unit_id].child_unit_ids:
            visit(child_id)
        visiting.remove(unit_id)
        visited.add(unit_id)

    visit(universe.target_root_unit_id)
    for unit_id in sorted(set(units) - visited):
        hierarchy.append(SourceBlueprintGap("unreachable-target-unit", unit_id, "not reachable from target root"))

    output_owners: dict[tuple[str, str], list[TargetUnitInterfaceBinding]] = {}
    input_owners: dict[tuple[str, str], list[TargetUnitInterfaceBinding]] = {}
    for binding in universe.target_unit_interfaces:
        child = units.get(binding.child_unit_id)
        parent = units.get(binding.parent_unit_id)
        if child is None or parent is None:
            interfaces.append(SourceBlueprintGap("foreign-target-interface-unit", binding.binding_id, f"{binding.child_unit_id}/{binding.parent_unit_id}"))
            continue
        child_ports = {item.port_id: item for item in child.ports}
        parent_ports = {item.port_id: item for item in parent.ports}
        child_port = child_ports.get(binding.child_output_port_id)
        parent_port = parent_ports.get(binding.parent_input_port_id)
        if child.parent_unit_id != parent.unit_id or child.unit_id not in parent.child_unit_ids:
            interfaces.append(SourceBlueprintGap("foreign-target-interface-parent", binding.binding_id, parent.unit_id))
        if child_port is None or child_port.direction != "output":
            interfaces.append(SourceBlueprintGap("missing-target-child-output", binding.binding_id, binding.child_output_port_id))
        if parent_port is None or parent_port.direction != "input":
            interfaces.append(SourceBlueprintGap("missing-target-parent-input", binding.binding_id, binding.parent_input_port_id))
        if child_port and parent_port and (
            child_port.schema_id != binding.payload_schema_id or parent_port.schema_id != binding.payload_schema_id
        ):
            interfaces.append(SourceBlueprintGap("target-interface-schema-mismatch", binding.binding_id, binding.payload_schema_id))
        output_owners.setdefault((binding.child_unit_id, binding.child_output_port_id), []).append(binding)
        input_owners.setdefault((binding.parent_unit_id, binding.parent_input_port_id), []).append(binding)
        if binding.consumer_status != "consumed":
            interfaces.append(SourceBlueprintGap("target-interface-not-consumed", binding.binding_id, binding.consumer_status))
    for unit in universe.target_units:
        dispositions = dict(unit.output_dispositions)
        output_ports = {item.port_id for item in unit.ports if item.direction == "output"}
        for port_id, disposition in unit.output_dispositions:
            if port_id not in output_ports or disposition not in {"terminal", "excluded", "unresolved"}:
                interfaces.append(SourceBlueprintGap("invalid-target-output-disposition", unit.unit_id, f"{port_id}:{disposition}"))
            elif disposition == "unresolved":
                interfaces.append(SourceBlueprintGap("unresolved-target-output", unit.unit_id, port_id))
        for port_id in sorted(output_ports):
            owners = output_owners.get((unit.unit_id, port_id), [])
            if len(owners) > 1:
                interfaces.append(SourceBlueprintGap("duplicate-target-output-consumer", unit.unit_id, port_id))
            if not owners and port_id not in dispositions:
                interfaces.append(SourceBlueprintGap("unconsumed-target-output", unit.unit_id, port_id))
        for port in (item for item in unit.ports if item.direction == "input"):
            owners = input_owners.get((unit.unit_id, port.port_id), [])
            if len(owners) != 1:
                interfaces.append(SourceBlueprintGap("target-input-owner-count", unit.unit_id, f"{port.port_id}:{len(owners)}"))
    return hierarchy, interfaces


def _native_purpose_gaps(
    state: BeliefState,
    universe: InformationTargetUniverse,
    contract_path: str | None,
) -> list[SourceBlueprintGap]:
    receipt = universe.native_purpose_receipt
    if receipt is None:
        return [SourceBlueprintGap("missing-native-purpose-receipt", universe.universe_id, "current native good/bad execution receipt required")]
    allowed = {
        "schema_version", "status", "model_id", "model_fingerprint", "model_contract_fingerprint",
        "contract_input_fingerprint", "failure_results", "claim_boundary", "receipt_fingerprint",
    }
    unknown = sorted(set(receipt) - allowed)
    gaps: list[SourceBlueprintGap] = []
    if unknown:
        gaps.append(SourceBlueprintGap("native-purpose-receipt-unknown-field", universe.universe_id, repr(unknown)))
    if receipt.get("schema_version") != TARGET_PURPOSE_RESULT_SCHEMA or receipt.get("status") != "pass":
        gaps.append(SourceBlueprintGap("native-purpose-terminal-mismatch", universe.universe_id, str(receipt.get("status", ""))))
    contract = state.guard_contract
    expected_model_id = contract.model_id if contract else ""
    expected_model_fingerprint = f"sha256:{model_fingerprint(state)}"
    if receipt.get("model_id") != expected_model_id:
        gaps.append(SourceBlueprintGap("native-purpose-model-mismatch", universe.universe_id, str(receipt.get("model_id", ""))))
    if receipt.get("model_fingerprint") != expected_model_fingerprint:
        gaps.append(SourceBlueprintGap("native-purpose-model-stale", universe.universe_id, str(receipt.get("model_fingerprint", ""))))
    if receipt.get("model_contract_fingerprint") != state.candidate_contract_fingerprint:
        gaps.append(SourceBlueprintGap("native-purpose-contract-stale", universe.universe_id, str(receipt.get("model_contract_fingerprint", ""))))
    supplied_fingerprint = str(receipt.get("receipt_fingerprint", ""))
    material = dict(receipt)
    material.pop("receipt_fingerprint", None)
    if supplied_fingerprint != _digest(material):
        gaps.append(SourceBlueprintGap("native-purpose-receipt-fingerprint-mismatch", universe.universe_id, supplied_fingerprint))
    failure_rows = receipt.get("failure_results")
    if not isinstance(failure_rows, list):
        gaps.append(SourceBlueprintGap("native-purpose-failure-results-invalid", universe.universe_id, "failure_results must be a list"))
    else:
        observed_good: set[str] = set()
        observed_bad: set[str] = set()
        for index, row in enumerate(failure_rows):
            if not isinstance(row, Mapping):
                gaps.append(SourceBlueprintGap("native-purpose-failure-result-invalid", str(index), "result must be an object"))
                continue
            if set(row) != {"failure_id", "oracle_id", "known_good", "known_bad"}:
                gaps.append(SourceBlueprintGap("native-purpose-failure-result-shape", str(index), repr(sorted(row))))
                continue
            good = row.get("known_good")
            bad = row.get("known_bad")
            if not isinstance(good, Mapping) or not isinstance(bad, Mapping):
                gaps.append(SourceBlueprintGap("native-purpose-case-result-invalid", str(row.get("failure_id", index)), "good/bad result must be objects"))
                continue
            if good.get("status") != "pass" or bad.get("status") != "blocked":
                gaps.append(SourceBlueprintGap("native-purpose-case-terminal-mismatch", str(row.get("failure_id", index)), f"{good.get('status')}/{bad.get('status')}"))
            contract_failure = next((item for item in (contract.prevented_failures if contract else ()) if item.failure_id == row.get("failure_id")), None)
            if contract_failure is None or contract_failure.oracle_id != row.get("oracle_id"):
                gaps.append(SourceBlueprintGap("native-purpose-oracle-owner-mismatch", str(row.get("failure_id", index)), str(row.get("oracle_id", ""))))
            else:
                observed_good.add(contract_failure.known_good.case_id)
                observed_bad.add(contract_failure.known_bad.case_id)
        if observed_good != set(universe.known_good_case_ids) or observed_bad != set(universe.known_bad_case_ids):
            gaps.append(SourceBlueprintGap("native-purpose-case-denominator-mismatch", universe.universe_id, "receipt cases do not match universe"))
    if contract_path is None:
        gaps.append(SourceBlueprintGap("native-purpose-replay-not-run", universe.universe_id, "contract path is required to verify current case bytes"))
    else:
        try:
            current = prove_target_model_contract(state, contract_path)
        except Exception as exc:
            gaps.append(SourceBlueprintGap("native-purpose-replay-failed", universe.universe_id, str(exc)))
        else:
            if dict(receipt) != current:
                gaps.append(SourceBlueprintGap("native-purpose-receipt-not-current", universe.universe_id, "stored receipt differs from current native execution"))
    return gaps


def _source_native_receipt_expectations(
    state: BeliefState, universe: InformationTargetUniverse
) -> tuple[NativeReceiptExpectation, ...]:
    authority = universe.target_authority
    if authority is None:
        return ()
    anchor = authority.expected_target_anchor
    units = {item.unit_id: item for item in universe.target_units}
    result: list[NativeReceiptExpectation] = []
    for binding in universe.target_unit_interfaces:
        child = units.get(binding.child_unit_id)
        child_port = next(
            (
                item
                for item in (child.ports if child else ())
                if item.port_id == binding.child_output_port_id
            ),
            None,
        )
        result.append(
            native_receipt_expectation(
                receipt_id=f"source-interface:{binding.binding_id}",
                member_id="sourceguard",
                native_owner_id="sourceguard.target-interface",
                checker_id="researchguard.source.target-interface",
                checker_version="1",
                checker_entrypoint="researchguard.source.blueprint:check_blueprint",
                task_id=universe.universe_id,
                expected_target_anchor_id=anchor.anchor_id,
                expected_target_anchor_fingerprint=anchor.anchor_fingerprint,
                native_model_id=binding.child_unit_id,
                model_fingerprint=_digest(child.to_dict() if child else {}),
                request_fingerprint=_digest(
                    {
                        "binding_id": binding.binding_id,
                        "child_unit_id": binding.child_unit_id,
                        "parent_unit_id": binding.parent_unit_id,
                        "payload_schema_id": binding.payload_schema_id,
                        "expected_target_anchor_id": anchor.anchor_id,
                    }
                ),
                input_fingerprint=_digest(child_port.to_dict() if child_port else {}),
                result_fingerprint=_digest(binding.to_dict()),
            )
        )
    receipt = universe.native_purpose_receipt
    if receipt is not None:
        model_id = str(receipt.get("model_id", ""))
        receipt_revision = str(receipt.get("receipt_fingerprint", "")).removeprefix(
            "sha256:"
        )
        result.append(
            native_receipt_expectation(
                receipt_id=f"source-native-purpose:{model_id}:{receipt_revision}",
                member_id="sourceguard",
                native_owner_id="sourceguard.native-purpose",
                checker_id="researchguard.source.native-purpose",
                checker_version="1",
                checker_entrypoint="researchguard.source.blueprint:check_blueprint",
                task_id=universe.universe_id,
                expected_target_anchor_id=anchor.anchor_id,
                expected_target_anchor_fingerprint=anchor.anchor_fingerprint,
                native_model_id=model_id,
                model_fingerprint=str(receipt.get("model_fingerprint", "")),
                request_fingerprint=_digest(
                    {
                        "universe_id": universe.universe_id,
                        "model_id": model_id,
                        "expected_target_anchor_id": anchor.anchor_id,
                    }
                ),
                input_fingerprint=_digest(
                    {
                        "model_contract_fingerprint": str(
                            receipt.get("model_contract_fingerprint", "")
                        )
                    }
                ),
                result_fingerprint=str(receipt.get("receipt_fingerprint", "")),
            )
        )
    return tuple(result)


def check_blueprint(
    state: BeliefState,
    universe: InformationTargetUniverse,
    *,
    contract_path: str | None = None,
) -> SourceBlueprintResult:
    validate_model_guard_binding(state)
    validate_graph_edges(state)
    target_hierarchy_gaps, target_interface_gaps = _target_unit_gaps(universe)
    gaps: list[SourceBlueprintGap] = [*target_hierarchy_gaps, *target_interface_gaps]
    edges = _edge_set(state)
    leads = state.lead_by_id()
    sources = state.source_by_id()
    actions = state.action_by_id()
    anchors = {item.anchor_id: item for item in state.anchors}
    for gap in state.gaps:
        if gap.lead_id not in leads:
            gaps.append(SourceBlueprintGap("missing-objective", gap.gap_id, gap.lead_id))
        else:
            _require_edge(edges, gap.lead_id, "opens_gap", gap.gap_id, gaps)
        if not gap.structure_unit_id:
            gaps.append(SourceBlueprintGap("missing-target-unit", gap.gap_id, "structure_unit_id required"))
        elif gap.structure_unit_id not in {item.unit_id for item in universe.target_units}:
            gaps.append(SourceBlueprintGap("foreign-gap-target-unit", gap.gap_id, gap.structure_unit_id))
        else:
            _require_edge(edges, gap.structure_unit_id, "opens_gap", gap.gap_id, gaps)
        for role in gap.suggested_source_roles:
            role_id = f"source-role:{gap.gap_id}:{role}"
            _require_edge(edges, gap.gap_id, "requires_role", role_id, gaps)
        gap_actions = [item for item in state.actions if item.target_gap_id == gap.gap_id]
        if not gap_actions:
            gaps.append(SourceBlueprintGap("missing-search-action", gap.gap_id, "no action targets gap"))
        for action in gap_actions:
            role_id = f"source-role:{gap.gap_id}:{action.expected_source_role}"
            _require_edge(edges, role_id, "addresses", action.action_id, gaps)
            observations = [item for item in state.observations if item.action_id == action.action_id]
            if not observations:
                gaps.append(
                    SourceBlueprintGap(
                        "missing-action-observation",
                        action.action_id,
                        "search action has no current observation or explicit result",
                    )
                )
            for observation in observations:
                _require_edge(
                    edges,
                    action.action_id,
                    "observation_from",
                    observation.observation_id,
                    gaps,
                )
                for source in observation.observed_sources:
                    _require_edge(
                        edges,
                        observation.observation_id,
                        "observation_from",
                        source.source_id,
                        gaps,
                    )
                for anchor in observation.observed_anchors:
                    _require_edge(
                        edges,
                        observation.observation_id,
                        "observation_from",
                        anchor.anchor_id,
                        gaps,
                    )
        if len(gap.closure_basis.anchor_ids) != len(gap.closure_basis.source_ids):
            gaps.append(
                SourceBlueprintGap(
                    "incompatible-closure-interface",
                    gap.gap_id,
                    "closure source and anchor identities must pair exactly",
                )
            )
        for anchor_id, source_id in zip(gap.closure_basis.anchor_ids, gap.closure_basis.source_ids):
            anchor = anchors.get(anchor_id)
            source = sources.get(source_id)
            if source is None or anchor is None:
                gaps.append(SourceBlueprintGap("missing-closure-object", gap.gap_id, f"{source_id}/{anchor_id}"))
                continue
            _require_edge(edges, source.source_id, "contains_anchor", anchor.anchor_id, gaps)
            _require_edge(edges, anchor.anchor_id, "qualifies", gap.gap_id, gaps)
            if not any(
                (action.action_id, "returns_source", source.source_id) in edges
                for action in gap_actions
            ):
                gaps.append(
                    SourceBlueprintGap(
                        "missing-interface-edge",
                        source.source_id,
                        f"search action for {gap.gap_id} -[returns_source]-> {source.source_id}",
                    )
                )
            closure_observed = any(
                observation.action_id in {action.action_id for action in gap_actions}
                and (
                    any(item.source_id == source.source_id for item in observation.observed_sources)
                    or any(item.anchor_id == anchor.anchor_id for item in observation.observed_anchors)
                )
                for observation in state.observations
            )
            if not closure_observed:
                gaps.append(
                    SourceBlueprintGap(
                        "missing-closure-observation",
                        gap.gap_id,
                        f"{source.source_id}/{anchor.anchor_id}",
                    )
                )
            if not anchor.claim_use_ids and not anchor.handoff_ids:
                gaps.append(
                    SourceBlueprintGap(
                        "missing-output-consumer",
                        anchor.anchor_id,
                        "qualified anchor requires claim_use_ids or handoff_ids",
                    )
                )
            for claim_use_id in anchor.claim_use_ids:
                _require_edge(edges, anchor.anchor_id, "consumed_by", claim_use_id, gaps)
            for handoff_id in anchor.handoff_ids:
                _require_edge(edges, anchor.anchor_id, "consumed_by", handoff_id, gaps)
    for source in state.sources:
        missing = [
            name
            for name in (
                "content_fingerprint",
                "retrieval_request_fingerprint",
                "provider_id",
                "provider_revision",
                "retrieved_at",
                "lineage_id",
            )
            if not getattr(source, name)
        ]
        if missing:
            gaps.append(SourceBlueprintGap("incomplete-source-identity", source.source_id, ",".join(missing)))
    for anchor in state.anchors:
        missing = [
            name
            for name in (
                "locator",
                "anchor_content_fingerprint",
                "source_content_fingerprint",
                "extractor_id",
                "extractor_revision",
                "observed_at",
                "observation_fingerprint",
            )
            if not getattr(anchor, name)
        ]
        if missing:
            gaps.append(SourceBlueprintGap("incomplete-anchor-identity", anchor.anchor_id, ",".join(missing)))
        source = sources.get(anchor.source_id)
        if source and anchor.source_content_fingerprint and anchor.source_content_fingerprint != source.content_fingerprint:
            gaps.append(SourceBlueprintGap("stale-anchor-source-content", anchor.anchor_id, anchor.source_id))
    for observation in state.observations:
        if not observation.observation_fingerprint:
            gaps.append(
                SourceBlueprintGap(
                    "incomplete-observation-identity",
                    observation.observation_id,
                    "observation_fingerprint",
                )
            )
    unconsumed_candidates: set[str] = set()
    for rows, id_field, required_relations in (
        (state.actions, "action_id", {"returns_source", "observation_from"}),
        (state.observations, "observation_id", {"observation_from"}),
        (state.sources, "source_id", {"contains_anchor", "candidate_for", "cites", "promoted_to_traceguard", "promoted_to_logicguard"}),
        (state.anchors, "anchor_id", {"qualifies", "closes_gap", "consumed_by", "promoted_to_traceguard", "promoted_to_logicguard", "supports", "limits", "rebuts"}),
    ):
        for row in rows:
            object_id = str(getattr(row, id_field))
            disposition = str(getattr(row, "unconsumed_output_disposition", ""))
            if disposition and disposition not in BLUEPRINT_OUTPUT_DISPOSITIONS:
                gaps.append(
                    SourceBlueprintGap(
                        "invalid-output-disposition", object_id, disposition
                    )
                )
                continue
            has_consumer = any(
                source_id == object_id and relation in required_relations
                for source_id, relation, _target_id in edges
            )
            if not has_consumer and not disposition:
                unconsumed_candidates.add(object_id)
                gaps.append(
                    SourceBlueprintGap(
                        "unconsumed-candidate-output",
                        object_id,
                        "no typed consumer or explicit disposition",
                    )
                )
    actual = {
        "target-unit": {item.unit_id for item in universe.target_units},
        "gap": set(state.gap_by_id()),
        "source-role": {f"source-role:{item.gap_id}:{role}" for item in state.gaps for role in item.suggested_source_roles},
        "lineage-slot": {f"lineage:{item.lineage_id}" for item in state.sources if item.lineage_id},
        "anchor-requirement": set(anchors),
        "handoff": {str(item) for item in state.metadata.get("handoff_ids", [])},
    }
    required = {
        "target-unit": set(universe.required_target_unit_ids),
        "gap": set(universe.required_gap_ids),
        "source-role": set(universe.required_source_role_ids),
        "lineage-slot": set(universe.required_lineage_slot_ids),
        "anchor-requirement": set(universe.required_anchor_requirement_ids),
        "handoff": set(universe.required_handoff_ids),
    }
    authority = universe.target_authority
    authority_gaps: list[SourceBlueprintGap] = []
    if authority is None:
        authority_gaps.append(
            SourceBlueprintGap(
                "missing-target-purpose-authority",
                universe.universe_id,
                "independent SourceGuard contract/parser authority required",
            )
        )
    else:
        contract = state.guard_contract
        subject = source_target_subject_fingerprint(state, universe)
        identity_checks = (
            (authority.member_id == "sourceguard", "target-authority-member-mismatch", authority.member_id),
            (authority.owner_id == SOURCE_TARGET_AUTHORITY_OWNER, "target-authority-owner-mismatch", authority.owner_id),
            (authority.tool_id == SOURCE_TARGET_AUTHORITY_TOOL, "target-authority-tool-mismatch", authority.tool_id),
            (authority.target_id == (contract.model_id if contract else ""), "target-authority-target-mismatch", authority.target_id),
            (authority.target_revision == authority.target_fingerprint, "target-authority-revision-mismatch", authority.target_revision),
            (authority.request_fingerprint == source_target_request_fingerprint(state), "target-authority-request-stale", authority.request_fingerprint),
            (authority.target_fingerprint == subject, "target-authority-target-stale", authority.target_fingerprint),
            (authority.purpose_fingerprint == source_target_purpose_fingerprint(state), "target-authority-purpose-stale", authority.purpose_fingerprint),
            (authority.status == "current", "target-authority-not-current", authority.status),
            (authority.authority_fingerprint == authority.expected_fingerprint, "target-authority-fingerprint-mismatch", authority.authority_id),
        )
        for ok, code, detail in identity_checks:
            if not ok:
                authority_gaps.append(SourceBlueprintGap(code, universe.universe_id, detail))
        actual_authority = {
            **actual,
            "target-port": {port.port_id for unit in universe.target_units for port in unit.ports},
            "target-interface": {item.binding_id for item in universe.target_unit_interfaces},
            "known-good-case": set(universe.known_good_case_ids),
            "known-bad-case": set(universe.known_bad_case_ids),
            "failure-class": {item.failure_id for item in (contract.prevented_failures if contract else ())},
        }
        declared_authority = {
            **required,
            "target-port": actual_authority["target-port"],
            "target-interface": actual_authority["target-interface"],
            "known-good-case": set(universe.known_good_case_ids),
            "known-bad-case": set(universe.known_bad_case_ids),
            "failure-class": actual_authority["failure-class"],
        }
        for kind, current_objects in actual_authority.items():
            authoritative = authority.ids(kind)
            declared_objects = declared_authority[kind]
            for object_id in sorted(authoritative - declared_objects):
                authority_gaps.append(SourceBlueprintGap(f"target-authority-omitted-{kind}", object_id, "missing from member denominator"))
            for object_id in sorted(declared_objects - authoritative):
                authority_gaps.append(SourceBlueprintGap(f"target-authority-foreign-{kind}", object_id, "not owned by target authority"))
            for object_id in sorted(authoritative - current_objects):
                authority_gaps.append(SourceBlueprintGap(f"target-authority-missing-{kind}", object_id, "missing from current SourceGuard model"))
            for object_id in sorted(current_objects - authoritative):
                authority_gaps.append(SourceBlueprintGap(f"target-authority-unowned-{kind}", object_id, "current SourceGuard model object is absent from target authority"))
            for object_id in sorted(authority.ids(kind, "excluded") & current_objects):
                authority_gaps.append(SourceBlueprintGap(f"target-authority-excluded-{kind}", object_id, "excluded object is present"))
        for item in authority.unresolved_items:
            authority_gaps.append(SourceBlueprintGap("target-authority-unresolved", item.object_id, item.reason))
        replay = replay_information_target_material(
            state,
            universe,
            authority.expected_target_anchor.material_locator
            if authority.native_attestation is not None
            else "",
        )
        for code, detail in verify_registered_target_authority(authority, replay):
            authority_gaps.append(SourceBlueprintGap(code, universe.universe_id, detail))
    gaps.extend(authority_gaps)
    for kind in required:
        for object_id in sorted(required[kind] - actual[kind]):
            gaps.append(SourceBlueprintGap(f"omitted-universe-{kind}", object_id, "required by independent universe"))
        for object_id in sorted(actual[kind] - required[kind]):
            gaps.append(SourceBlueprintGap(f"undeclared-universe-{kind}", object_id, "current SourceGuard model object is absent from independent universe"))
    if not universe.known_good_case_ids:
        gaps.append(SourceBlueprintGap("missing-known-good", universe.universe_id, "native purpose good case required"))
    if not universe.known_bad_case_ids:
        gaps.append(SourceBlueprintGap("missing-known-bad", universe.universe_id, "native purpose bad case required"))
    contract = state.guard_contract
    contract_good = {
        failure.known_good.case_id for failure in contract.prevented_failures
    } if contract else set()
    contract_bad = {
        failure.known_bad.case_id for failure in contract.prevented_failures
    } if contract else set()
    for case_id in sorted(set(universe.known_good_case_ids) - contract_good):
        gaps.append(SourceBlueprintGap("unbound-native-good-case", case_id, "not owned by current SourceGuard contract"))
    for case_id in sorted(set(universe.known_bad_case_ids) - contract_bad):
        gaps.append(SourceBlueprintGap("unbound-native-bad-case", case_id, "not owned by current SourceGuard contract"))
    gaps.extend(_native_purpose_gaps(state, universe, contract_path))
    gaps.extend(
        SourceBlueprintGap(code, detail.split(":", 1)[0], detail)
        for code, detail in resolve_expected_native_receipts(
            universe.native_receipt_refs,
            _source_native_receipt_expectations(state, universe),
        )
    )
    unconsumed = tuple(sorted(unconsumed_candidates))
    hierarchy_codes = {"missing-objective", "missing-target-unit", "foreign-gap-target-unit", *(item.code for item in target_hierarchy_gaps)}
    interface_codes = {"missing-search-action", "missing-action-observation", "missing-closure-observation", "missing-interface-edge", "missing-closure-object", "incompatible-closure-interface", "missing-output-consumer", "unconsumed-candidate-output", "invalid-output-disposition", *(item.code for item in target_interface_gaps)}
    hierarchy_gaps = [item for item in gaps if item.code in hierarchy_codes]
    interface_gaps = [item for item in gaps if item.code in interface_codes]
    universe_gaps = [
        item
        for item in gaps
        if item.code.startswith("omitted-universe")
        or item.code.startswith("undeclared-universe")
        or item.code.startswith("missing-known")
        or item.code.startswith("target-authority-")
        or item.code == "missing-target-purpose-authority"
    ]
    identity_gaps = [item for item in gaps if "identity" in item.code or "stale" in item.code]
    categorized = {*hierarchy_gaps, *interface_gaps, *universe_gaps, *identity_gaps}
    native_gaps = [item for item in gaps if item not in categorized]
    layer_definitions = (
        ("objective-and-target-hierarchy", hierarchy_gaps),
        ("target-unit-interfaces", [item for item in interface_gaps if item in target_interface_gaps]),
        ("typed-information-chain", [item for item in interface_gaps if item not in target_interface_gaps]),
        ("independent-universe", universe_gaps),
        ("content-and-lineage", identity_gaps),
        ("native-information-blueprint", native_gaps),
    )
    layer_statuses: list[dict[str, object]] = []
    deepest = "none"
    prior_passed = True
    first = ""
    for layer_id, layer_gaps in layer_definitions:
        if not prior_passed:
            layer_statuses.append({"layer_id": layer_id, "status": "not_run", "gap_ids": []})
            continue
        if layer_gaps:
            gap_ids = [f"{item.code}:{item.object_id}" for item in layer_gaps]
            layer_statuses.append({"layer_id": layer_id, "status": "failed", "gap_ids": gap_ids})
            first = gap_ids[0]
            prior_passed = False
        else:
            layer_statuses.append({"layer_id": layer_id, "status": "passed", "gap_ids": []})
            deepest = layer_id
    fingerprint = _digest(
        {"model": to_plain(state), "universe": universe.to_dict(), "edges": [item.to_dict() for item in state.graph_edges]}
    )
    return SourceBlueprintResult(
        status="complete" if not gaps else "incomplete",
        model_fingerprint=f"sha256:{model_fingerprint(state)}",
        universe_fingerprint=universe.fingerprint,
        blueprint_fingerprint=fingerprint,
        deepest_proven_layer=deepest,
        first_unresolved_gap=first,
        native_open_gap_ids=tuple(sorted(item.gap_id for item in state.gaps if item.semantic_state != "closed")),
        unconsumed_candidate_ids=unconsumed,
        gaps=tuple(gaps),
        layer_statuses=tuple(layer_statuses),
    )


def impact_blueprint(
    state: BeliefState,
    changed_ids: Iterable[str],
    universe: InformationTargetUniverse | None = None,
    *,
    contract_path: str | None = None,
) -> dict[str, object]:
    changed = set(changed_ids)
    qualification = (
        check_blueprint(state, universe, contract_path=contract_path)
        if universe is not None
        else None
    )
    authority = universe.target_authority if universe is not None else None
    if qualification is None or qualification.status != "complete":
        return {
            "query_status": "blocked",
            "qualification_status": (
                qualification.status if qualification is not None else "not_run"
            ),
            "qualification_model_fingerprint": (
                qualification.model_fingerprint if qualification is not None else ""
            ),
            "qualification_gaps": (
                [item.to_dict() for item in qualification.gaps]
                if qualification is not None
                else [
                    SourceBlueprintGap(
                        "missing-target-universe",
                        str(state.metadata.get("model_id", "sourceguard")),
                        "impact requires one current SourceGuard blueprint qualification",
                    ).to_dict()
                ]
            ),
            "target_authority_status": authority.status if authority else "not_run",
            "target_material_status": (
                authority.native_attestation.status
                if authority and authority.native_attestation
                else "not_run"
            ),
            "model_fingerprint": f"sha256:{model_fingerprint(state)}",
            "graph_fingerprint": _digest([item.to_dict() for item in state.graph_edges]),
            "universe_fingerprint": universe.fingerprint if universe else "",
            "changed_ids": sorted(changed),
            "affected_target_unit_ids": [],
            "affected_gap_ids": [],
            "unaffected_gap_ids": [],
            "affected_source_role_ids": [],
            "affected_search_action_ids": [],
            "affected_observation_ids": [],
            "affected_source_ids": [],
            "affected_lineage_slot_ids": [],
            "affected_anchor_ids": [],
            "affected_anchor_requirement_ids": [],
            "affected_claim_use_ids": [],
            "affected_handoff_ids": [],
            "affected_stop_decision_ids": [],
            "unknown_dependency_ids": [],
            "unknown_ownership": False,
            "partial_result_suppressed": True,
        }
    objects = state.graph_object_types()
    adjacency: dict[str, set[str]] = {}
    edge_by_id = {item.edge_id: item for item in state.graph_edges}
    for edge in state.graph_edges:
        adjacency.setdefault(edge.source_id, set()).add(edge.target_id)

    if universe is not None:
        units = {item.unit_id: item for item in universe.target_units}
        for unit in universe.target_units:
            objects[unit.unit_id] = "target_unit"
            if unit.parent_unit_id:
                adjacency.setdefault(unit.unit_id, set()).add(unit.parent_unit_id)

    identity_owners: dict[str, set[str]] = {object_id: {object_id} for object_id in objects}
    for source in state.sources:
        for identity in (
            source.content_fingerprint,
            source.retrieval_request_fingerprint,
            source.provider_id,
            source.provider_revision,
            source.retrieved_at,
            source.url,
            f"lineage:{source.lineage_id}" if source.lineage_id else "",
        ):
            if identity:
                identity_owners.setdefault(identity, set()).add(source.source_id)
    for anchor in state.anchors:
        for identity in (
            anchor.anchor_content_fingerprint,
            anchor.source_content_fingerprint,
            anchor.extractor_id,
            anchor.extractor_revision,
            anchor.observation_fingerprint,
            anchor.locator,
        ):
            if identity:
                identity_owners.setdefault(identity, set()).add(anchor.anchor_id)
    for observation in state.observations:
        if observation.observation_fingerprint:
            identity_owners.setdefault(observation.observation_fingerprint, set()).add(
                observation.observation_id
            )
    stop_map = state.metadata.get("stop_decisions_by_gap", {})
    if isinstance(stop_map, Mapping):
        for gap_id, stop_id in stop_map.items():
            identity_owners.setdefault(str(stop_id), set()).add(str(gap_id))
    for edge_id, edge in edge_by_id.items():
        identity_owners[edge_id] = {edge.source_id, edge.target_id}
    if universe is not None:
        all_unit_ids = {item.unit_id for item in universe.target_units}
        identity_owners[universe.universe_id] = set(all_unit_ids)
        identity_owners[universe.fingerprint] = set(all_unit_ids)
        identity_owners[universe.target_root_unit_id] = {universe.target_root_unit_id}
        for unit in universe.target_units:
            identity_owners[unit.unit_id] = {unit.unit_id}
            for port in unit.ports:
                identity_owners[port.port_id] = {unit.unit_id}
        for binding in universe.target_unit_interfaces:
            identity_owners[binding.binding_id] = {binding.child_unit_id, binding.parent_unit_id}
            identity_owners.setdefault(binding.child_output_port_id, set()).add(binding.child_unit_id)
            identity_owners.setdefault(binding.parent_input_port_id, set()).add(binding.parent_unit_id)
        for case_id in (*universe.known_good_case_ids, *universe.known_bad_case_ids):
            identity_owners[case_id] = set(all_unit_ids)

    seeds = set().union(*(identity_owners[item] for item in changed if item in identity_owners)) if changed else set()
    affected_objects = set(seeds)
    pending = list(seeds)
    while pending:
        object_id = pending.pop()
        for consumer_id in adjacency.get(object_id, ()):
            if consumer_id not in affected_objects:
                affected_objects.add(consumer_id)
                pending.append(consumer_id)

    by_type: dict[str, set[str]] = {}
    for object_id in affected_objects:
        object_type = objects.get(object_id)
        if object_type:
            by_type.setdefault(object_type, set()).add(object_id)
    affected_gaps = by_type.get("gap", set())
    affected_claim_uses = by_type.get("claim_use", set())
    handoffs = affected_member_handoffs(
        state,
        gap_ids=tuple(sorted(affected_gaps)),
        claim_use_ids=tuple(sorted(affected_claim_uses)),
    )
    graph_handoffs = by_type.get("handoff", set())
    affected_handoff_ids = sorted(
        graph_handoffs | set(handoffs["affected_handoff_ids"])
    )
    unknown_changed = sorted(changed - set(identity_owners))
    invalid_dependencies = {
        f"metadata:{item}" for item in handoffs["invalid_dependency_maps"]
    }
    unknown_dependency_ids = sorted(
        set(unknown_changed)
        | set(handoffs["unknown_handoff_ids"])
        | invalid_dependencies
    )
    result = {
        "query_status": "complete",
        "qualification_status": qualification.status,
        "qualification_model_fingerprint": qualification.model_fingerprint,
        "qualification_gaps": [],
        "target_authority_status": authority.status if authority else "not_run",
        "target_material_status": (
            authority.native_attestation.status
            if authority and authority.native_attestation
            else "not_run"
        ),
        "model_fingerprint": f"sha256:{model_fingerprint(state)}",
        "graph_fingerprint": _digest([item.to_dict() for item in state.graph_edges]),
        "universe_fingerprint": universe.fingerprint if universe else "",
        "changed_ids": sorted(changed),
        "affected_target_unit_ids": sorted(by_type.get("target_unit", set())),
        "affected_gap_ids": sorted(affected_gaps),
        "unaffected_gap_ids": sorted(set(state.gap_by_id()) - affected_gaps),
        "affected_source_role_ids": sorted(by_type.get("source_role", set())),
        "affected_search_action_ids": sorted(by_type.get("search_action", set())),
        "affected_observation_ids": sorted(by_type.get("observation", set())),
        "affected_source_ids": sorted(by_type.get("source", set())),
        "affected_lineage_slot_ids": sorted(
            f"lineage:{item.lineage_id}"
            for item in state.sources
            if item.source_id in by_type.get("source", set()) and item.lineage_id
        ),
        "affected_anchor_ids": sorted(by_type.get("anchor", set())),
        "affected_anchor_requirement_ids": sorted(by_type.get("anchor", set())),
        "affected_claim_use_ids": sorted(affected_claim_uses),
        "affected_handoff_ids": affected_handoff_ids,
        "affected_stop_decision_ids": sorted(
            str(stop_map[item])
            for item in affected_gaps
            if isinstance(stop_map, Mapping) and item in stop_map
        ),
        "unknown_dependency_ids": unknown_dependency_ids,
        "unknown_ownership": bool(unknown_dependency_ids),
    }
    if unknown_dependency_ids:
        for key in tuple(result):
            if key.startswith("affected_") or key == "unaffected_gap_ids":
                result[key] = []
        result["partial_result_suppressed"] = True
    else:
        result["partial_result_suppressed"] = False
    return result


def reverse_trace_claim_use(
    state: BeliefState,
    claim_use_id: str,
    universe: InformationTargetUniverse | None = None,
    *,
    contract_path: str | None = None,
) -> dict[str, object]:
    qualification = (
        check_blueprint(state, universe, contract_path=contract_path)
        if universe is not None
        else None
    )
    authority = universe.target_authority if universe is not None else None
    target_material_status = (
        authority.native_attestation.status
        if authority and authority.native_attestation
        else "not_run"
    )
    if qualification is None or qualification.status != "complete":
        trace_gaps = (
            [item.to_dict() for item in qualification.gaps]
            if qualification is not None
            else [
                SourceBlueprintGap(
                    "missing-target-universe",
                    claim_use_id,
                    "reverse trace requires one current SourceGuard blueprint qualification",
                ).to_dict()
            ]
        )
        return {
            "query_status": "blocked",
            "qualification_status": (
                qualification.status if qualification is not None else "not_run"
            ),
            "qualification_model_fingerprint": (
                qualification.model_fingerprint if qualification is not None else ""
            ),
            "trace_status": "incomplete",
            "trace_gaps": trace_gaps,
            "blueprint_status": (
                qualification.status if qualification is not None else "incomplete"
            ),
            "target_authority_status": authority.status if authority else "not_run",
            "target_material_status": target_material_status,
            "claim_use_id": "",
            "output_kind": "",
            "model_fingerprint": f"sha256:{model_fingerprint(state)}",
            "graph_fingerprint": "",
            "target_unit_ids": [],
            "target_unit_paths_to_root": [],
            "target_unit_interfaces": [],
            "gap_ids": [],
            "source_role_ids": [],
            "search_actions": [],
            "search_action_ids": [],
            "observation_chain": [],
            "source_revisions": [],
            "anchors": [],
            "qualification_ids": [],
            "qualifications": [],
            "handoff_ids": [],
            "reverse_trace_fingerprint": "",
            "partial_result_suppressed": True,
            "claim_boundary": (
                qualification.claim_boundary
                if qualification is not None
                else (
                    "SourceGuard qualifies discovery identities, anchors, lineage, and information gaps only. "
                    "It does not decide final argument truth, causal conclusions, or completed storylines."
                )
            ),
            "terminal_capability_boundary": "",
        }
    edges = _edge_set(state)
    anchors = [
        item
        for item in state.anchors
        if claim_use_id in item.claim_use_ids or claim_use_id in item.handoff_ids
    ]
    if not anchors:
        raise ValueError(f"claim use {claim_use_id!r} has no SourceGuard anchor")
    anchor_ids = {item.anchor_id for item in anchors}
    gaps = [item for item in state.gaps if anchor_ids & set(item.closure_basis.anchor_ids)]
    if not gaps:
        raise ValueError(f"claim use {claim_use_id!r} has no qualified gap consumer")
    source_ids = {anchor.source_id for anchor in anchors}
    role_ids: set[str] = set()
    action_ids: set[str] = set()
    for gap in gaps:
        gap_roles = {
            target_id
            for source_id, relation, target_id in edges
            if source_id == gap.gap_id and relation == "requires_role"
        }
        expected_roles = {
            f"source-role:{gap.gap_id}:{role}" for role in gap.suggested_source_roles
        }
        role_ids.update(gap_roles & expected_roles)
        for role_id in gap_roles & expected_roles:
            action_ids.update(
                target_id
                for source_id, relation, target_id in edges
                if source_id == role_id and relation == "addresses"
            )
    valid_actions = {
        action.action_id
        for action in state.actions
        if action.action_id in action_ids
        and action.target_gap_id in {gap.gap_id for gap in gaps}
        and any(
            (action.action_id, "returns_source", source_id) in edges
            for source_id in source_ids
        )
    }
    if not valid_actions:
        raise ValueError(
            f"claim use {claim_use_id!r} has no complete typed search-action-to-source chain"
        )
    observations = [
        item
        for item in state.observations
        if item.action_id in valid_actions
        and (item.action_id, "observation_from", item.observation_id) in edges
        and (
            any(
                (item.observation_id, "observation_from", anchor.anchor_id) in edges
                for anchor in item.observed_anchors
                if anchor.anchor_id in anchor_ids
            )
            or any(
                (item.observation_id, "observation_from", source.source_id) in edges
                for source in item.observed_sources
                if source.source_id in source_ids
            )
        )
    ]
    target_unit_ids = sorted({item.structure_unit_id for item in gaps if item.structure_unit_id})
    target_unit_paths: list[list[str]] = []
    target_unit_interfaces: list[dict[str, str]] = []
    if universe is not None:
        units = {item.unit_id: item for item in universe.target_units}
        for start in target_unit_ids:
            path: list[str] = []
            current = start
            seen: set[str] = set()
            while current and current in units and current not in seen:
                path.append(current)
                seen.add(current)
                current = units[current].parent_unit_id
            target_unit_paths.append(path)
        path_units = {item for path in target_unit_paths for item in path}
        target_unit_interfaces = [
            item.to_dict()
            for item in universe.target_unit_interfaces
            if item.child_unit_id in path_units and item.parent_unit_id in path_units
        ]
    payload = {
        "query_status": "complete",
        "qualification_status": qualification.status,
        "qualification_model_fingerprint": qualification.model_fingerprint,
        "trace_status": "complete",
        "trace_gaps": [],
        "blueprint_status": qualification.status,
        "target_authority_status": authority.status if authority else "not_run",
        "target_material_status": target_material_status,
        "claim_use_id": claim_use_id,
        "output_kind": "handoff" if any(claim_use_id in item.handoff_ids for item in anchors) else "claim_use",
        "model_fingerprint": f"sha256:{model_fingerprint(state)}",
        "graph_fingerprint": _digest([item.to_dict() for item in state.graph_edges]),
        "target_unit_ids": target_unit_ids,
        "target_unit_paths_to_root": target_unit_paths,
        "target_unit_interfaces": target_unit_interfaces,
        "gap_ids": sorted(item.gap_id for item in gaps),
        "source_role_ids": sorted(role_ids),
        "search_actions": [
            {
                "action_id": item.action_id,
                "action_type": item.action_type,
                "query": item.query,
                "target_gap_id": item.target_gap_id,
                "expected_source_role": item.expected_source_role,
                "expected_modality": item.expected_modality,
                "source_policy": item.source_policy,
                "parameters": dict(item.parameters),
            }
            for item in sorted(state.actions, key=lambda item: item.action_id)
            if item.action_id in valid_actions
        ],
        "search_action_ids": sorted(valid_actions),
        "observation_chain": [
            {
                "observation_id": item.observation_id,
                "action_id": item.action_id,
                "observation_fingerprint": item.observation_fingerprint,
                "observed_source_ids": sorted(source.source_id for source in item.observed_sources),
                "observed_anchor_ids": sorted(anchor.anchor_id for anchor in item.observed_anchors),
            }
            for item in sorted(observations, key=lambda item: item.observation_id)
        ],
        "source_revisions": [
            {
                "source_id": source.source_id,
                "url": source.url,
                "content_fingerprint": source.content_fingerprint,
                "retrieval_request_fingerprint": source.retrieval_request_fingerprint,
                "provider_id": source.provider_id,
                "provider_revision": source.provider_revision,
                "retrieved_at": source.retrieved_at,
                "lineage_id": source.lineage_id,
                "source_role": source.source_role,
            }
            for source in state.sources
            if source.source_id in source_ids
        ],
        "anchors": [
            {
                "anchor_id": item.anchor_id,
                "locator": item.locator,
                "anchor_content_fingerprint": item.anchor_content_fingerprint,
                "extractor_id": item.extractor_id,
                "extractor_revision": item.extractor_revision,
            }
            for item in anchors
        ],
        "qualification_ids": sorted(item.qualification.observation_id for item in gaps if item.qualification.observation_id),
        "qualifications": [
            to_plain(item.qualification)
            for item in sorted(gaps, key=lambda row: row.gap_id)
        ],
        "handoff_ids": sorted(str(value) for gap in gaps for value in state.metadata.get("member_handoffs_by_gap", {}).get(gap.gap_id, [])),
        "partial_result_suppressed": False,
        "claim_boundary": qualification.claim_boundary,
        "terminal_capability_boundary": (
            "SourceGuard can reconstruct the declared information-search and qualification chain, "
            "but it cannot reconstruct unread external bytes or decide final truth, causality, or argument validity."
        ),
    }
    payload["reverse_trace_fingerprint"] = _digest(payload)
    return payload


def export_blueprint(
    state: BeliefState,
    universe: InformationTargetUniverse,
    *,
    contract_path: str | None = None,
) -> dict[str, object]:
    return {
        "schema_version": SOURCE_BLUEPRINT_SCHEMA,
        "model": to_plain(state),
        "target_universe": universe.to_dict(),
        "check": check_blueprint(state, universe, contract_path=contract_path).to_dict(),
    }


__all__ = [
    "SOURCE_BLUEPRINT_SCHEMA",
    "InformationTargetUniverse",
    "TargetUnit",
    "TargetUnitInterfaceBinding",
    "TargetUnitPort",
    "SourceBlueprintGap",
    "SourceBlueprintResult",
    "check_blueprint",
    "export_blueprint",
    "impact_blueprint",
    "reverse_trace_claim_use",
    "source_target_purpose_fingerprint",
    "source_target_request_fingerprint",
    "source_target_subject_fingerprint",
    "replay_information_target_material",
]
