"""Independent, adapter-neutral inventory for LogicGuard artifact blueprints."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
import re
from typing import Literal, Mapping, Sequence

from ..native_receipts import NativeReceiptReference
from ..target_authority import (
    ExpectedTargetAnchor,
    NativeTargetMaterialReplay,
    TargetAuthorityItem,
    TargetPurposeAuthority,
    content_addressed_request_id,
    _issue_replayed_target_authority,
    read_target_material_bytes,
)

ARTIFACT_INVENTORY_SCHEMA = "researchguard.logic.artifact-inventory.v1"
RESOURCE_ROLES = {"content", "layout", "page", "asset", "citation", "receipt"}
LOGIC_TARGET_AUTHORITY_OWNER = "researchguard.logic.artifact-inventory"
LOGIC_TARGET_AUTHORITY_TOOL = "researchguard.logic.target-parser"
LOGIC_TARGET_ADAPTER_ID = "researchguard.logic.target-material-adapter"
LOGIC_TARGET_ADAPTER_VERSION = "2"
LOGIC_TARGET_MATERIAL_SCHEMA = "researchguard.logic.target-material.v1"
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def _exact_keys(raw: Mapping[str, object], allowed: set[str], where: str) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ValueError(f"{where} contains unknown fields: {unknown!r}")


def _mapping_rows(value: object, where: str) -> Sequence[Mapping[str, object]]:
    if not isinstance(value, list):
        raise ValueError(f"{where} must be a list")
    rows: list[Mapping[str, object]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ValueError(f"{where}[{index}] must be an object")
        rows.append(item)
    return rows


def _digest(value: object) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(body.encode('utf-8')).hexdigest()}"


@dataclass(frozen=True)
class ArtifactResourceBinding:
    resource_id: str
    role: Literal["content", "layout", "page", "asset", "citation", "receipt"]
    locator: str
    content_fingerprint: str
    owner_id: str
    required: bool = True
    disposition: Literal["bound", "unresolved", "excluded"] = "bound"
    disposition_reason: str = ""
    observation_kind: Literal["not_observed", "local_file", "external_identity"] = "not_observed"
    observation_root: str = ""
    subject_revision: str = ""
    observed_fingerprint: str = ""
    observation_receipt_id: str = ""
    observation_receipt_fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.resource_id.strip() or self.role not in RESOURCE_ROLES:
            raise ValueError("artifact resources require a current id and role")
        if self.disposition == "bound":
            if not self.locator.strip() or not self.owner_id.strip():
                raise ValueError("bound artifact resources require locator and owner")
            if not _SHA256.fullmatch(self.content_fingerprint):
                raise ValueError("bound artifact resources require an exact sha256 fingerprint")
        elif not self.disposition_reason.strip():
            raise ValueError("unresolved or excluded resources require a disposition reason")
        if self.observation_kind not in {"not_observed", "local_file", "external_identity"}:
            raise ValueError("artifact resource observation_kind is not current")
        if self.observation_kind != "not_observed":
            required_observation = (
                self.subject_revision,
                self.observed_fingerprint,
                self.observation_receipt_id,
                self.observation_receipt_fingerprint,
            )
            if any(not value.strip() for value in required_observation):
                raise ValueError("observed artifact resources require current subject and receipt identities")
            if not _SHA256.fullmatch(self.observed_fingerprint) or not _SHA256.fullmatch(
                self.observation_receipt_fingerprint
            ):
                raise ValueError("artifact resource observation fingerprints must be exact sha256 values")
        if self.observation_kind == "local_file" and not self.observation_root.strip():
            raise ValueError("local artifact observations require an explicit observation_root")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @property
    def expected_observation_receipt_fingerprint(self) -> str:
        return _digest(
            {
                "resource_id": self.resource_id,
                "role": self.role,
                "locator": self.locator,
                "content_fingerprint": self.content_fingerprint,
                "owner_id": self.owner_id,
                "observation_kind": self.observation_kind,
                "subject_revision": self.subject_revision,
                "observed_fingerprint": self.observed_fingerprint,
            }
        )

    def current_observation_gap(self) -> tuple[str, str] | None:
        """Return a visible gap unless current evidence proves the bound bytes.

        External identities remain useful provenance, but they cannot by themselves
        license exact-content reconstruction because this process did not observe
        their bytes.
        """

        if self.disposition != "bound":
            return ("resource-not-bound", self.disposition_reason)
        if self.observation_kind == "not_observed":
            return ("resource-not-observed", "declared locator and hash are not observation evidence")
        if self.observation_kind == "external_identity":
            if self.observation_receipt_fingerprint != self.expected_observation_receipt_fingerprint:
                return ("resource-observation-receipt-mismatch", "observation receipt does not bind the current resource identity")
            return (
                "external-resource-content-unverified",
                "external identity is bounded provenance, not locally observed exact content",
            )
        root = Path(self.observation_root)
        locator = Path(self.locator)
        if not root.is_absolute() or locator.is_absolute() or ".." in locator.parts:
            return ("unsafe-local-resource-locator", "local resource must stay beneath one absolute observation root")
        try:
            resolved_root = root.resolve(strict=True)
            resolved = (resolved_root / locator).resolve(strict=True)
            if not resolved.is_relative_to(resolved_root) or not resolved.is_file():
                return ("unsafe-local-resource-locator", "resolved resource is outside its observation root or is not a file")
            actual = f"sha256:{hashlib.sha256(resolved.read_bytes()).hexdigest()}"
        except (OSError, RuntimeError):
            return ("missing-local-resource", "local observed resource cannot be read")
        if actual != self.content_fingerprint or actual != self.observed_fingerprint:
            return ("local-resource-bytes-mismatch", "current file bytes do not match the declared observation")
        if self.observation_receipt_fingerprint != self.expected_observation_receipt_fingerprint:
            return ("resource-observation-receipt-mismatch", "observation receipt does not bind the current resource identity")
        return None


@dataclass(frozen=True)
class ArtifactUnit:
    unit_id: str
    parent_unit_id: str
    locator: str
    content_fingerprint: str
    required_resource_roles: tuple[str, ...] = ()
    resources: tuple[ArtifactResourceBinding, ...] = ()
    parse_disposition: Literal["parsed", "unparsed", "excluded"] = "parsed"
    disposition_reason: str = ""

    def __post_init__(self) -> None:
        if not self.unit_id.strip() or not self.locator.strip():
            raise ValueError("artifact units require unit_id and locator")
        if self.parse_disposition == "parsed" and not _SHA256.fullmatch(self.content_fingerprint):
            raise ValueError("parsed artifact units require an exact sha256 content fingerprint")
        if self.parse_disposition != "parsed" and not self.disposition_reason.strip():
            raise ValueError("unparsed or excluded artifact units require a disposition reason")
        if any(role not in RESOURCE_ROLES for role in self.required_resource_roles):
            raise ValueError("artifact required_resource_roles contains an unknown role")
        if len(set(self.required_resource_roles)) != len(self.required_resource_roles):
            raise ValueError("artifact required_resource_roles must be unique")
        resource_ids = tuple(item.resource_id for item in self.resources)
        if len(set(resource_ids)) != len(resource_ids):
            raise ValueError("artifact resource ids must be unique")

    def to_dict(self) -> dict[str, object]:
        return {
            "unit_id": self.unit_id,
            "parent_unit_id": self.parent_unit_id,
            "locator": self.locator,
            "content_fingerprint": self.content_fingerprint,
            "required_resource_roles": list(self.required_resource_roles),
            "resources": [item.to_dict() for item in self.resources],
            "parse_disposition": self.parse_disposition,
            "disposition_reason": self.disposition_reason,
        }


@dataclass(frozen=True)
class ArtifactInventory:
    inventory_id: str
    source_revision: str
    root_unit_id: str
    units: tuple[ArtifactUnit, ...]
    target_authority: TargetPurposeAuthority | None = None
    native_receipt_refs: tuple[NativeReceiptReference, ...] = ()
    schema_version: str = ARTIFACT_INVENTORY_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != ARTIFACT_INVENTORY_SCHEMA:
            raise ValueError("artifact inventory requires the current schema")
        if not self.inventory_id.strip() or not self.source_revision.strip() or not self.root_unit_id.strip():
            raise ValueError("artifact inventory identity fields are required")
        ids = [item.unit_id for item in self.units]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("artifact inventory unit ids must be non-empty and unique")
        units = {item.unit_id: item for item in self.units}
        roots = [item.unit_id for item in self.units if not item.parent_unit_id]
        if roots != [self.root_unit_id]:
            raise ValueError(f"artifact inventory must have one declared root; roots={roots!r}")
        for unit in self.units:
            if unit.parent_unit_id and unit.parent_unit_id not in units:
                raise ValueError(f"artifact unit {unit.unit_id!r} has missing parent {unit.parent_unit_id!r}")
        for start in ids:
            seen: set[str] = set()
            current = start
            while current:
                if current in seen:
                    raise ValueError(f"artifact inventory contains a cycle at {current!r}")
                seen.add(current)
                current = units[current].parent_unit_id
        receipt_ids = tuple(item.receipt_id for item in self.native_receipt_refs)
        if len(receipt_ids) != len(set(receipt_ids)):
            raise ValueError("artifact inventory native receipt ids must be unique")

    @property
    def fingerprint(self) -> str:
        return _digest(self.to_dict(include_fingerprint=False, include_receipts=False))

    def to_dict(
        self, *, include_fingerprint: bool = True, include_receipts: bool = True
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "inventory_id": self.inventory_id,
            "source_revision": self.source_revision,
            "root_unit_id": self.root_unit_id,
            "units": [item.to_dict() for item in sorted(self.units, key=lambda item: item.unit_id)],
            "target_authority": self.target_authority.to_dict() if self.target_authority else None,
        }
        if include_receipts:
            payload["native_receipt_refs"] = [
                item.to_dict() for item in self.native_receipt_refs
            ]
        if include_fingerprint:
            payload["inventory_fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "ArtifactInventory":
        _exact_keys(
            raw,
            {"schema_version", "inventory_id", "source_revision", "root_unit_id", "units", "target_authority", "native_receipt_refs", "inventory_fingerprint"},
            "artifact inventory",
        )
        rows = _mapping_rows(raw.get("units"), "artifact inventory units")
        parsed_units: list[ArtifactUnit] = []
        for index, item in enumerate(rows):
            _exact_keys(
                item,
                {
                    "unit_id", "parent_unit_id", "locator", "content_fingerprint",
                    "required_resource_roles", "resources", "parse_disposition", "disposition_reason",
                },
                f"artifact inventory units[{index}]",
            )
            role_rows = item.get("required_resource_roles", [])
            if not isinstance(role_rows, list):
                raise ValueError(f"artifact inventory units[{index}].required_resource_roles must be a list")
            resource_rows = _mapping_rows(item.get("resources", []), f"artifact inventory units[{index}].resources")
            parsed_resources: list[ArtifactResourceBinding] = []
            for resource_index, resource in enumerate(resource_rows):
                _exact_keys(
                    resource,
                    {
                        "resource_id", "role", "locator", "content_fingerprint", "owner_id", "required",
                        "disposition", "disposition_reason", "observation_kind", "observation_root",
                        "subject_revision", "observed_fingerprint", "observation_receipt_id",
                        "observation_receipt_fingerprint",
                    },
                    f"artifact inventory units[{index}].resources[{resource_index}]",
                )
                parsed_resources.append(
                    ArtifactResourceBinding(
                        resource_id=str(resource.get("resource_id", "")),
                        role=str(resource.get("role", "")),
                        locator=str(resource.get("locator", "")),
                        content_fingerprint=str(resource.get("content_fingerprint", "")),
                        owner_id=str(resource.get("owner_id", "")),
                        required=bool(resource.get("required", True)),
                        disposition=str(resource.get("disposition", "bound")),
                        disposition_reason=str(resource.get("disposition_reason", "")),
                        observation_kind=str(resource.get("observation_kind", "not_observed")),
                        observation_root=str(resource.get("observation_root", "")),
                        subject_revision=str(resource.get("subject_revision", "")),
                        observed_fingerprint=str(resource.get("observed_fingerprint", "")),
                        observation_receipt_id=str(resource.get("observation_receipt_id", "")),
                        observation_receipt_fingerprint=str(resource.get("observation_receipt_fingerprint", "")),
                    )
                )
            parsed_units.append(
                ArtifactUnit(
                    unit_id=str(item.get("unit_id", "")),
                    parent_unit_id=str(item.get("parent_unit_id", "")),
                    locator=str(item.get("locator", "")),
                    content_fingerprint=str(item.get("content_fingerprint", "")),
                    required_resource_roles=tuple(str(value) for value in role_rows),
                    resources=tuple(parsed_resources),
                    parse_disposition=str(item.get("parse_disposition", "")),
                    disposition_reason=str(item.get("disposition_reason", "")),
                )
            )
        inventory = cls(
            schema_version=str(raw.get("schema_version", "")),
            inventory_id=str(raw.get("inventory_id", "")),
            source_revision=str(raw.get("source_revision", "")),
            root_unit_id=str(raw.get("root_unit_id", "")),
            units=tuple(parsed_units),
            target_authority=(
                TargetPurposeAuthority.from_dict(raw["target_authority"])
                if isinstance(raw.get("target_authority"), Mapping)
                else None
            ),
            native_receipt_refs=tuple(
                NativeReceiptReference.from_dict(item)
                for item in _mapping_rows(
                    raw.get("native_receipt_refs", []),
                    "artifact inventory native_receipt_refs",
                )
            ),
        )
        supplied = str(raw.get("inventory_fingerprint", ""))
        if supplied and supplied != inventory.fingerprint:
            raise ValueError("artifact inventory fingerprint mismatch")
        return inventory


def artifact_inventory_subject_fingerprint(inventory: ArtifactInventory) -> str:
    return _digest(
        {
            "schema_version": inventory.schema_version,
            "inventory_id": inventory.inventory_id,
            "source_revision": inventory.source_revision,
            "root_unit_id": inventory.root_unit_id,
            "units": [item.to_dict() for item in sorted(inventory.units, key=lambda item: item.unit_id)],
        }
    )


def artifact_inventory_purpose_fingerprint(inventory: ArtifactInventory) -> str:
    return _digest(
        {
            "inventory_id": inventory.inventory_id,
            "root_unit_id": inventory.root_unit_id,
            "source_revision": inventory.source_revision,
        }
    )


def artifact_inventory_request_fingerprint(inventory: ArtifactInventory) -> str:
    return _digest(
        {
            "inventory_id": inventory.inventory_id,
            "root_unit_id": inventory.root_unit_id,
            "source_revision": inventory.source_revision,
        }
    )


def _artifact_target_items(inventory: ArtifactInventory) -> tuple[TargetAuthorityItem, ...]:
    items: list[TargetAuthorityItem] = []
    for unit in inventory.units:
        disposition = "required" if unit.parse_disposition == "parsed" else "unresolved"
        items.append(
            TargetAuthorityItem(
                "artifact-unit", unit.unit_id, disposition,
                "target parser could not parse this unit" if disposition == "unresolved" else "",
            )
        )
        if unit.parent_unit_id:
            items.append(TargetAuthorityItem("containment", f"{unit.parent_unit_id}->{unit.unit_id}", "required"))
        for role in unit.required_resource_roles:
            items.append(TargetAuthorityItem("resource-role", f"{unit.unit_id}:{role}", "required"))
        for resource in unit.resources:
            disposition = (
                "required" if resource.required and resource.disposition == "bound"
                else "excluded" if resource.disposition == "excluded"
                else "unresolved"
            )
            reason = "" if disposition == "required" else (resource.disposition_reason or "target resource is not currently bound")
            items.append(TargetAuthorityItem("resource", resource.resource_id, disposition, reason))
    return tuple(items)


def _noncurrent_logic_replay(
    inventory: ArtifactInventory,
    locator: str,
    status: Literal["unverified", "failed"],
    detail: str,
) -> NativeTargetMaterialReplay:
    marker = _digest({"locator": locator, "status": status})
    request_fingerprint = artifact_inventory_request_fingerprint(inventory)
    target_fingerprint = artifact_inventory_subject_fingerprint(inventory)
    return NativeTargetMaterialReplay(
        adapter_id=LOGIC_TARGET_ADAPTER_ID,
        adapter_version=LOGIC_TARGET_ADAPTER_VERSION,
        request_id=content_addressed_request_id(request_fingerprint),
        request_fingerprint=request_fingerprint,
        input_id=locator or "unreplayable:logic-target-material",
        input_fingerprint=marker,
        target_id=inventory.inventory_id,
        target_revision=target_fingerprint,
        target_fingerprint=target_fingerprint,
        purpose_fingerprint=artifact_inventory_purpose_fingerprint(inventory),
        material_locator=locator or "unreplayable:logic-target-material",
        material_media_type="application/json",
        material_fingerprint=marker,
        items=(),
        status=status,
        detail=detail,
    )


def replay_artifact_target_material(
    inventory: ArtifactInventory, locator: str
) -> NativeTargetMaterialReplay:
    """LogicGuard-owned closed parser for raw artifact target material."""

    body, material_fingerprint, gap = read_target_material_bytes(locator)
    if body is None:
        return _noncurrent_logic_replay(inventory, locator, "unverified", gap)
    try:
        raw = json.loads(body.decode("utf-8"))
        if not isinstance(raw, Mapping) or set(raw) != {
            "schema_version", "request_contract", "artifact_subject"
        }:
            raise ValueError("logic target material has an unknown or missing root field")
        if raw.get("schema_version") != LOGIC_TARGET_MATERIAL_SCHEMA:
            raise ValueError("logic target material schema is not current")
        request = raw.get("request_contract")
        subject = raw.get("artifact_subject")
        if not isinstance(request, Mapping) or set(request) != {
            "request_id", "inventory_id", "root_unit_id", "source_revision"
        }:
            raise ValueError("logic target request contract is not exact-current")
        if not isinstance(subject, Mapping) or set(subject) != {
            "schema_version", "inventory_id", "source_revision", "root_unit_id", "units"
        }:
            raise ValueError("logic artifact subject is not exact-current")
        parsed = ArtifactInventory.from_dict(
            {
                **dict(subject),
                "target_authority": None,
                "inventory_fingerprint": "",
            }
        )
        request_material = {
            "inventory_id": str(request["inventory_id"]),
            "root_unit_id": str(request["root_unit_id"]),
            "source_revision": str(request["source_revision"]),
        }
        request_fingerprint = _digest(request_material)
        target_fingerprint = artifact_inventory_subject_fingerprint(parsed)
        return NativeTargetMaterialReplay(
            adapter_id=LOGIC_TARGET_ADAPTER_ID,
            adapter_version=LOGIC_TARGET_ADAPTER_VERSION,
            request_id=str(request["request_id"]),
            request_fingerprint=request_fingerprint,
            input_id=locator,
            input_fingerprint=material_fingerprint,
            target_id=parsed.inventory_id,
            target_revision=target_fingerprint,
            target_fingerprint=target_fingerprint,
            purpose_fingerprint=artifact_inventory_purpose_fingerprint(parsed),
            material_locator=locator,
            material_media_type="application/json",
            material_fingerprint=material_fingerprint,
            items=_artifact_target_items(parsed),
            status="current",
        )
    except Exception as exc:
        return _noncurrent_logic_replay(inventory, locator, "failed", str(exc))


def _bind_artifact_inventory_authority(
    inventory: ArtifactInventory, *, expected_target_anchor: ExpectedTargetAnchor
) -> ArtifactInventory:
    """Replay only the externally admitted LogicGuard artifact target."""

    replay = replay_artifact_target_material(
        inventory, expected_target_anchor.material_locator
    )
    authority = _issue_replayed_target_authority(
        member_id="logicguard",
        owner_id=LOGIC_TARGET_AUTHORITY_OWNER,
        tool_id=LOGIC_TARGET_AUTHORITY_TOOL,
        tool_revision="1",
        expected_target_anchor=expected_target_anchor,
        replay=replay,
    )
    return replace(inventory, target_authority=authority)


__all__ = [
    "ARTIFACT_INVENTORY_SCHEMA",
    "RESOURCE_ROLES",
    "LOGIC_TARGET_AUTHORITY_OWNER",
    "LOGIC_TARGET_AUTHORITY_TOOL",
    "LOGIC_TARGET_MATERIAL_SCHEMA",
    "ArtifactInventory",
    "ArtifactResourceBinding",
    "ArtifactUnit",
    "artifact_inventory_purpose_fingerprint",
    "artifact_inventory_request_fingerprint",
    "artifact_inventory_subject_fingerprint",
    "replay_artifact_target_material",
]
