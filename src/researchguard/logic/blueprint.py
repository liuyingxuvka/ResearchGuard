"""LogicGuard-owned argument/artifact blueprint inspection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Iterable, Literal, Mapping

from ..native_receipts import (
    NativeReceiptExpectation,
    NativeReceiptReference,
    native_receipt_expectation,
    resolve_expected_native_receipts,
)
from .artifact_inventory import (
    LOGIC_TARGET_AUTHORITY_OWNER,
    LOGIC_TARGET_AUTHORITY_TOOL,
    ArtifactInventory,
    artifact_inventory_purpose_fingerprint,
    artifact_inventory_request_fingerprint,
    artifact_inventory_subject_fingerprint,
    replay_artifact_target_material,
)
from .execution_depth import build_logic_depth_receipt, model_fingerprint
from .model import LogicModel, block_interface_receipt_fingerprint
from .validator import validate_model
from ..target_authority import verify_registered_target_authority

LOGIC_BLUEPRINT_SCHEMA = "researchguard.logic.domain-blueprint.v1"
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def _digest(value: object) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(body.encode('utf-8')).hexdigest()}"


@dataclass(frozen=True)
class ArtifactRealizationBinding:
    artifact_unit_id: str
    argument_block_id: str
    node_ids: tuple[str, ...]
    resource_ids: tuple[str, ...] = ()
    disposition: Literal["bound", "unresolved", "excluded"] = "bound"
    consumed_content_fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.artifact_unit_id.strip() or not self.argument_block_id.strip():
            raise ValueError("artifact realization requires unit and argument block identities")
        if len(set(self.node_ids)) != len(self.node_ids) or len(set(self.resource_ids)) != len(self.resource_ids):
            raise ValueError("artifact realization node and resource identities must be unique")
        if self.disposition == "bound" and not _SHA256.fullmatch(self.consumed_content_fingerprint):
            raise ValueError("bound artifact realization requires an exact consumed content fingerprint")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class LogicBlueprintGap:
    code: str
    object_id: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class LogicBlueprintResult:
    status: Literal["complete", "incomplete"]
    completion_scope: Literal["incomplete", "structural", "content_resource"]
    model_id: str
    model_fingerprint: str
    inventory_fingerprint: str
    blueprint_fingerprint: str
    deepest_proven_layer: str
    first_unresolved_gap: str
    structural_reconstruction: Literal["licensed", "not_licensed"]
    content_reconstruction: Literal["licensed", "not_licensed"]
    gaps: tuple[LogicBlueprintGap, ...]
    layer_statuses: tuple[dict[str, object], ...]
    native_depth_status: Literal["current", "stale", "failed", "not_run"] = "not_run"
    native_depth_gaps: tuple[LogicBlueprintGap, ...] = ()
    claim_boundary: str = (
        "LogicGuard licenses only the modeled argument and artifact structure. Exact prose, layout, "
        "citations, and assets require their own current content/resource bindings."
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": LOGIC_BLUEPRINT_SCHEMA,
            "status": self.status,
            "completion_scope": self.completion_scope,
            "model_id": self.model_id,
            "model_fingerprint": self.model_fingerprint,
            "inventory_fingerprint": self.inventory_fingerprint,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "deepest_proven_layer": self.deepest_proven_layer,
            "first_unresolved_gap": self.first_unresolved_gap,
            "structural_reconstruction": self.structural_reconstruction,
            "content_reconstruction": self.content_reconstruction,
            "gaps": [item.to_dict() for item in self.gaps],
            "layer_statuses": list(self.layer_statuses),
            "native_depth_status": self.native_depth_status,
            "native_depth_gaps": [item.to_dict() for item in self.native_depth_gaps],
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class LogicNativeDepthEvidence:
    target_root: str
    guard_contract: str
    budget: int
    receipt: Mapping[str, object]
    receipt_fingerprint: str
    status: Literal["current", "stale", "failed", "not_run"] = "current"
    native_receipt_ref: NativeReceiptReference | None = None

    def __post_init__(self) -> None:
        if not self.target_root.strip() or not self.guard_contract.strip() or self.budget < 1:
            raise ValueError("logic native depth evidence requires target, contract, and positive budget")
        if not _SHA256.fullmatch(self.receipt_fingerprint):
            raise ValueError("logic native depth evidence requires an exact receipt fingerprint")
        if self.status not in {"current", "stale", "failed", "not_run"}:
            raise ValueError("logic native depth evidence status is not current")
        if isinstance(self.native_receipt_ref, Mapping):
            object.__setattr__(
                self,
                "native_receipt_ref",
                NativeReceiptReference.from_dict(self.native_receipt_ref),
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "target_root": self.target_root,
            "guard_contract": self.guard_contract,
            "budget": self.budget,
            "receipt": dict(self.receipt),
            "receipt_fingerprint": self.receipt_fingerprint,
            "status": self.status,
            "native_receipt_ref": (
                self.native_receipt_ref.to_dict() if self.native_receipt_ref else None
            ),
        }


def _logic_native_receipt_expectations(
    model: LogicModel,
    inventory: ArtifactInventory,
    bindings: tuple[ArtifactRealizationBinding, ...],
    native_depth_evidence: LogicNativeDepthEvidence | None,
) -> tuple[NativeReceiptExpectation, ...]:
    authority = inventory.target_authority
    if authority is None:
        return ()
    anchor = authority.expected_target_anchor
    result: list[NativeReceiptExpectation] = []
    for interface in model.block_interfaces:
        result.append(
            native_receipt_expectation(
                receipt_id=interface.parent_receipt_id,
                member_id="logicguard",
                native_owner_id="logicguard.block-interface",
                checker_id="researchguard.logic.block-interface",
                checker_version="1",
                checker_entrypoint="researchguard.logic.blueprint:check_blueprint",
                task_id=interface.producer_task_id,
                expected_target_anchor_id=anchor.anchor_id,
                expected_target_anchor_fingerprint=anchor.anchor_fingerprint,
                native_model_id=interface.child_block_id,
                model_fingerprint=interface.producer_model_fingerprint,
                request_fingerprint=_digest(
                    {
                        "parent_receipt_id": interface.parent_receipt_id,
                        "child_block_id": interface.child_block_id,
                        "parent_block_id": interface.parent_block_id,
                        "payload_schema_id": interface.payload_schema_id,
                        "refinement_id": interface.refinement_id,
                        "expected_target_anchor_id": anchor.anchor_id,
                    }
                ),
                input_fingerprint=interface.consumed_fingerprint,
                result_fingerprint=interface.producer_result_fingerprint,
            )
        )
    interface_receipt_ids = {
        item.parent_receipt_id for item in model.block_interfaces
    }
    for unit in inventory.units:
        for resource in unit.resources:
            if (
                resource.role != "receipt"
                or not resource.required
                or resource.resource_id in interface_receipt_ids
            ):
                continue
            result.append(
                native_receipt_expectation(
                    receipt_id=resource.resource_id,
                    member_id="logicguard",
                    native_owner_id="logicguard.resource-leaf",
                    checker_id="researchguard.logic.resource-leaf",
                    checker_version="1",
                    checker_entrypoint="researchguard.logic.blueprint:check_blueprint",
                    task_id=inventory.inventory_id,
                    expected_target_anchor_id=anchor.anchor_id,
                    expected_target_anchor_fingerprint=anchor.anchor_fingerprint,
                    native_model_id=unit.unit_id,
                    model_fingerprint=unit.content_fingerprint,
                    request_fingerprint=_digest(
                        {
                            "resource_id": resource.resource_id,
                            "unit_id": unit.unit_id,
                            "role": resource.role,
                            "owner_id": resource.owner_id,
                            "expected_target_anchor_id": anchor.anchor_id,
                        }
                    ),
                    input_fingerprint=resource.content_fingerprint,
                    result_fingerprint=resource.content_fingerprint,
                )
            )
    if native_depth_evidence is not None and native_depth_evidence.status == "current":
        result.append(
            native_receipt_expectation(
                receipt_id=f"logic-native-depth:{model.id}",
                member_id="logicguard",
                native_owner_id="logicguard.native-depth",
                checker_id="researchguard.logic.native-depth",
                checker_version="1",
                checker_entrypoint="researchguard.logic.blueprint:check_blueprint",
                task_id=inventory.inventory_id,
                expected_target_anchor_id=anchor.anchor_id,
                expected_target_anchor_fingerprint=anchor.anchor_fingerprint,
                native_model_id=model.id,
                model_fingerprint=f"sha256:{model_fingerprint(model)}",
                request_fingerprint=_digest(
                    {
                        "target_root": native_depth_evidence.target_root,
                        "guard_contract": native_depth_evidence.guard_contract,
                        "budget": native_depth_evidence.budget,
                        "inventory_fingerprint": inventory.fingerprint,
                        "realization_ids": sorted(item.artifact_unit_id for item in bindings),
                        "expected_target_anchor_id": anchor.anchor_id,
                    }
                ),
                input_fingerprint=_digest(native_depth_evidence.receipt),
                result_fingerprint=native_depth_evidence.receipt_fingerprint,
            )
        )
    return tuple(result)


def _depth_receipt_fingerprint(receipt: Mapping[str, object]) -> str:
    material = dict(receipt)
    material.pop("generated_at", None)
    return _digest(material)


def _realized_interface_receipt_refs(
    model: LogicModel,
    inventory: ArtifactInventory,
    bindings: Iterable[ArtifactRealizationBinding],
) -> tuple[str, ...]:
    required_receipt_ids = {
        item.parent_receipt_id
        for item in model.block_interfaces
        if item.consumer_status == "consumed"
    }
    receipt_resource_ids = {
        resource.resource_id
        for unit in inventory.units
        for resource in unit.resources
        if resource.role == "receipt"
        and resource.required
        and resource.disposition == "bound"
    }
    return tuple(
        sorted(
            {
                resource_id
                for binding in bindings
                for resource_id in binding.resource_ids
                if resource_id in receipt_resource_ids
                and resource_id in required_receipt_ids
            }
        )
    )


def _run_logic_native_depth_evidence(
    model: LogicModel,
    inventory: ArtifactInventory,
    realizations: Iterable[ArtifactRealizationBinding],
    *,
    target_root: str,
    guard_contract: str,
    budget: int = 6,
) -> LogicNativeDepthEvidence:
    bindings = tuple(realizations)
    receipt = build_logic_depth_receipt(
        model,
        target_root=target_root,
        guard_contract=guard_contract,
        budget=budget,
        artifact_inventory=inventory,
        artifact_binding_unit_ids=(item.artifact_unit_id for item in bindings),
        interface_receipt_refs=_realized_interface_receipt_refs(model, inventory, bindings),
    ).to_dict()
    status = "current" if receipt.get("status") == "pass" else "failed"
    return LogicNativeDepthEvidence(
        target_root=target_root,
        guard_contract=guard_contract,
        budget=budget,
        receipt=receipt,
        receipt_fingerprint=_depth_receipt_fingerprint(receipt),
        status=status,
    )


def check_blueprint(
    model: LogicModel,
    inventory: ArtifactInventory,
    realizations: Iterable[ArtifactRealizationBinding],
    native_depth_evidence: LogicNativeDepthEvidence | None = None,
) -> LogicBlueprintResult:
    bindings = tuple(realizations)
    gaps: list[LogicBlueprintGap] = []
    validation = validate_model(model)
    gaps.extend(LogicBlueprintGap("model-validation", model.id, item) for item in validation.errors)
    units = {item.unit_id: item for item in inventory.units}
    resources = {
        resource.resource_id: (unit.unit_id, resource)
        for unit in inventory.units
        for resource in unit.resources
    }
    native_depth_gaps: list[LogicBlueprintGap] = []
    native_depth_status: Literal["current", "stale", "failed", "not_run"] = "not_run"
    if native_depth_evidence is None:
        native_depth_gaps.append(
            LogicBlueprintGap(
                "native-depth-not-run",
                model.id,
                "current build_logic_depth_receipt and target proof were not replayed",
            )
        )
    elif native_depth_evidence.status != "current":
        native_depth_status = native_depth_evidence.status
        native_depth_gaps.append(
            LogicBlueprintGap(
                "native-depth-not-current",
                model.id,
                native_depth_evidence.status,
            )
        )
    else:
        try:
            replay = build_logic_depth_receipt(
                model,
                target_root=native_depth_evidence.target_root,
                guard_contract=native_depth_evidence.guard_contract,
                budget=native_depth_evidence.budget,
                artifact_inventory=inventory,
                artifact_binding_unit_ids=(item.artifact_unit_id for item in bindings),
                interface_receipt_refs=_realized_interface_receipt_refs(model, inventory, bindings),
            ).to_dict()
        except Exception as exc:  # native owner supplies the precise blocked reason
            native_depth_status = "failed"
            native_depth_gaps.append(LogicBlueprintGap("native-depth-replay-failed", model.id, str(exc)))
        else:
            replay_fingerprint = _depth_receipt_fingerprint(replay)
            supplied_fingerprint = _depth_receipt_fingerprint(native_depth_evidence.receipt)
            if native_depth_evidence.receipt_fingerprint != supplied_fingerprint:
                native_depth_status = "stale"
                native_depth_gaps.append(LogicBlueprintGap("native-depth-receipt-fingerprint-mismatch", model.id, native_depth_evidence.receipt_fingerprint))
            elif replay_fingerprint != supplied_fingerprint:
                native_depth_status = "stale"
                native_depth_gaps.append(LogicBlueprintGap("native-depth-receipt-stale", model.id, replay_fingerprint))
            elif replay.get("status") != "pass":
                native_depth_status = "failed"
                native_depth_gaps.append(LogicBlueprintGap("native-depth-blocked", model.id, str(replay.get("first_unresolved_gap", "native depth blocked"))))
            else:
                native_depth_status = "current"
    authority = inventory.target_authority
    if authority is None:
        gaps.append(
            LogicBlueprintGap(
                "missing-target-purpose-authority",
                inventory.inventory_id,
                "independent target parser owner/request/input/target/tool authority required",
            )
        )
    else:
        subject = artifact_inventory_subject_fingerprint(inventory)
        identity_checks = (
            (authority.member_id == "logicguard", "target-authority-member-mismatch", authority.member_id),
            (authority.owner_id == LOGIC_TARGET_AUTHORITY_OWNER, "target-authority-owner-mismatch", authority.owner_id),
            (authority.tool_id == LOGIC_TARGET_AUTHORITY_TOOL, "target-authority-tool-mismatch", authority.tool_id),
            (authority.target_id == inventory.inventory_id, "target-authority-target-mismatch", authority.target_id),
            (authority.target_revision == authority.target_fingerprint, "target-authority-revision-mismatch", authority.target_revision),
            (
                authority.request_fingerprint == artifact_inventory_request_fingerprint(inventory),
                "target-authority-request-stale",
                authority.request_fingerprint,
            ),
            (authority.target_fingerprint == subject, "target-authority-target-stale", authority.target_fingerprint),
            (authority.purpose_fingerprint == artifact_inventory_purpose_fingerprint(inventory), "target-authority-purpose-stale", authority.purpose_fingerprint),
            (authority.status == "current", "target-authority-not-current", authority.status),
            (authority.authority_fingerprint == authority.expected_fingerprint, "target-authority-fingerprint-mismatch", authority.authority_id),
        )
        for ok, code, detail in identity_checks:
            if not ok:
                gaps.append(LogicBlueprintGap(code, inventory.inventory_id, detail))
        actual_by_kind = {
            "artifact-unit": {item.unit_id for item in inventory.units},
            "containment": {f"{item.parent_unit_id}->{item.unit_id}" for item in inventory.units if item.parent_unit_id},
            "resource-role": {f"{item.unit_id}:{role}" for item in inventory.units for role in item.required_resource_roles},
            "resource": {resource.resource_id for item in inventory.units for resource in item.resources if resource.required and resource.disposition == "bound"},
        }
        for kind, actual in actual_by_kind.items():
            required = authority.ids(kind)
            for object_id in sorted(required - actual):
                gaps.append(LogicBlueprintGap(f"target-authority-omitted-{kind}", object_id, "missing from artifact inventory"))
            for object_id in sorted(actual - required):
                gaps.append(LogicBlueprintGap(f"target-authority-foreign-{kind}", object_id, "not owned by target parser authority"))
        for item in authority.unresolved_items:
            gaps.append(LogicBlueprintGap("target-authority-unresolved", item.object_id, item.reason))
        replay = replay_artifact_target_material(
            inventory,
            authority.expected_target_anchor.material_locator
            if authority.native_attestation is not None
            else "",
        )
        for code, detail in verify_registered_target_authority(authority, replay):
            gaps.append(LogicBlueprintGap(code, inventory.inventory_id, detail))
    receipt_refs = list(inventory.native_receipt_refs)
    if native_depth_evidence is not None and native_depth_evidence.native_receipt_ref is not None:
        receipt_refs.append(native_depth_evidence.native_receipt_ref)
    for code, detail in resolve_expected_native_receipts(
        receipt_refs,
        _logic_native_receipt_expectations(
            model, inventory, bindings, native_depth_evidence
        ),
    ):
        gap = LogicBlueprintGap(code, detail.split(":", 1)[0], detail)
        gaps.append(gap)
        if code.startswith("native-receipt") and "depth" in detail:
            native_depth_gaps.append(gap)
    bound: dict[str, ArtifactRealizationBinding] = {}
    bound_blocks: dict[str, ArtifactRealizationBinding] = {}
    for binding in bindings:
        if binding.artifact_unit_id in bound:
            gaps.append(LogicBlueprintGap("duplicate-artifact-binding", binding.artifact_unit_id, "multiple realization owners"))
        bound[binding.artifact_unit_id] = binding
        if binding.argument_block_id in bound_blocks:
            gaps.append(
                LogicBlueprintGap(
                    "duplicate-argument-block-binding",
                    binding.argument_block_id,
                    "multiple artifact realization owners",
                )
            )
        bound_blocks[binding.argument_block_id] = binding
        if binding.artifact_unit_id not in units:
            gaps.append(LogicBlueprintGap("unknown-artifact-unit", binding.artifact_unit_id, "not in independent inventory"))
            continue
        if binding.argument_block_id not in model.blocks:
            gaps.append(LogicBlueprintGap("unknown-argument-block", binding.argument_block_id, binding.artifact_unit_id))
        else:
            owned_nodes = set(model.blocks[binding.argument_block_id].member_node_ids())
            realized_nodes = set(binding.node_ids)
            for node_id in sorted(realized_nodes - set(model.nodes)):
                gaps.append(LogicBlueprintGap("unknown-realized-node", node_id, binding.artifact_unit_id))
            for node_id in sorted((realized_nodes & set(model.nodes)) - owned_nodes):
                gaps.append(LogicBlueprintGap("foreign-realized-node", node_id, binding.argument_block_id))
            for node_id in sorted(owned_nodes - realized_nodes):
                gaps.append(LogicBlueprintGap("omitted-owned-node", node_id, binding.argument_block_id))
            for interface in model.block_interfaces:
                if interface.parent_block_id != binding.argument_block_id:
                    continue
                if interface.parent_receipt_id not in binding.resource_ids:
                    gaps.append(
                        LogicBlueprintGap(
                            "missing-parent-interface-receipt",
                            interface.parent_receipt_id,
                            binding.argument_block_id,
                        )
                    )
                    continue
                receipt_row = resources.get(interface.parent_receipt_id)
                if receipt_row is None or receipt_row[1].role != "receipt":
                    gaps.append(LogicBlueprintGap("invalid-parent-interface-receipt", interface.parent_receipt_id, binding.argument_block_id))
                elif receipt_row[1].content_fingerprint != block_interface_receipt_fingerprint(model, interface):
                    gaps.append(LogicBlueprintGap("stale-parent-interface-receipt", interface.parent_receipt_id, binding.argument_block_id))
        if binding.disposition == "bound" and binding.consumed_content_fingerprint != units[binding.artifact_unit_id].content_fingerprint:
            gaps.append(LogicBlueprintGap("stale-content-binding", binding.artifact_unit_id, "content fingerprint changed"))
        unit = units[binding.artifact_unit_id]
        unit_resource_ids = {item.resource_id for item in unit.resources}
        for resource_id in binding.resource_ids:
            if resource_id not in resources:
                gaps.append(LogicBlueprintGap("unknown-resource-binding", resource_id, binding.artifact_unit_id))
            elif resource_id not in unit_resource_ids:
                gaps.append(LogicBlueprintGap("foreign-resource-binding", resource_id, binding.artifact_unit_id))
        required_resource_ids = {item.resource_id for item in unit.resources if item.required}
        for resource_id in sorted(required_resource_ids - set(binding.resource_ids)):
            gaps.append(LogicBlueprintGap("unconsumed-required-resource", resource_id, binding.artifact_unit_id))
    for unit in inventory.units:
        if unit.unit_id not in bound:
            gaps.append(LogicBlueprintGap("unmodeled-artifact-unit", unit.unit_id, "required independent inventory unit has no binding"))
        if unit.parse_disposition == "unparsed":
            gaps.append(LogicBlueprintGap("artifact-parse-gap", unit.unit_id, unit.disposition_reason))
        if not unit.required_resource_roles:
            gaps.append(
                LogicBlueprintGap(
                    "content-resource-role-not-declared",
                    unit.unit_id,
                    "independent inventory did not declare applicable exact-content roles",
                )
            )
        resources_by_role = {role: [] for role in unit.required_resource_roles}
        for resource in unit.resources:
            if resource.role in resources_by_role:
                resources_by_role[resource.role].append(resource)
            if resource.required and resource.disposition != "bound":
                gaps.append(
                    LogicBlueprintGap(
                        "required-resource-unresolved",
                        resource.resource_id,
                        resource.disposition_reason,
                    )
                )
            if resource.required and resource.disposition == "bound":
                observation_gap = resource.current_observation_gap()
                if observation_gap is not None:
                    code, detail = observation_gap
                    gaps.append(LogicBlueprintGap(code, resource.resource_id, detail))
        for role, rows in resources_by_role.items():
            if not rows:
                gaps.append(LogicBlueprintGap("missing-required-resource-role", unit.unit_id, role))
        content_resources = [item for item in unit.resources if item.role == "content" and item.disposition == "bound"]
        if "content" in unit.required_resource_roles and not any(
            item.content_fingerprint == unit.content_fingerprint for item in content_resources
        ):
            gaps.append(
                LogicBlueprintGap(
                    "content-resource-fingerprint-mismatch",
                    unit.unit_id,
                    "no bound content resource matches the unit content fingerprint",
                )
            )
    for block_id in sorted(set(model.blocks) - set(bound_blocks)):
        gaps.append(
            LogicBlueprintGap(
                "unrealized-argument-block",
                block_id,
                "no artifact unit realizes this current argument block",
            )
        )
    structural_gap_codes = {
        "model-validation",
        "unmodeled-artifact-unit",
        "unknown-artifact-unit",
        "duplicate-artifact-binding",
        "duplicate-argument-block-binding",
        "unknown-argument-block",
        "unknown-realized-node",
        "foreign-realized-node",
        "omitted-owned-node",
        "unrealized-argument-block",
        "missing-target-purpose-authority",
        "target-authority-member-mismatch",
        "target-authority-owner-mismatch",
        "target-authority-tool-mismatch",
        "target-authority-target-mismatch",
        "target-authority-revision-mismatch",
        "target-authority-request-stale",
        "target-authority-input-stale",
        "target-authority-target-stale",
        "target-authority-purpose-stale",
        "target-authority-not-current",
        "target-authority-fingerprint-mismatch",
        "target-authority-unresolved",
        "missing-parent-interface-receipt",
        "invalid-parent-interface-receipt",
        "stale-parent-interface-receipt",
    }
    inventory_gap_codes = {
        "unmodeled-artifact-unit",
        "unknown-artifact-unit",
        "duplicate-artifact-binding",
    }
    # Native depth is not an informational side channel.  It is the member's
    # current semantic execution proof, so a missing, stale, or failed depth
    # replay must participate in the same qualification that licenses the
    # blueprint and its export.
    gaps.extend(native_depth_gaps)
    structural_gaps = [item for item in gaps if item.code in structural_gap_codes]
    inventory_gaps = [item for item in gaps if item.code in inventory_gap_codes]
    inventory_gaps.extend(item for item in gaps if item.code.startswith("target-authority-") or item.code == "missing-target-purpose-authority")
    content_gap_codes = {
        "artifact-parse-gap",
        "stale-content-binding",
        "content-resource-role-not-declared",
        "missing-required-resource-role",
        "required-resource-unresolved",
        "unknown-resource-binding",
        "foreign-resource-binding",
        "unconsumed-required-resource",
        "content-resource-fingerprint-mismatch",
        "resource-not-bound",
        "resource-not-observed",
        "resource-observation-receipt-mismatch",
        "external-resource-content-unverified",
        "unsafe-local-resource-locator",
        "missing-local-resource",
        "local-resource-bytes-mismatch",
    }
    content_gaps = [item for item in gaps if item.code in content_gap_codes]
    native_depth_ok = native_depth_status == "current" and not native_depth_gaps
    structural_ok = not structural_gaps and native_depth_ok
    content_ok = (
        structural_ok
        and not content_gaps
        and all(item.disposition == "bound" for item in bindings)
        and all(item.required_resource_roles for item in inventory.units)
    )
    layer_definitions = (
        ("argument-model", tuple(item for item in gaps if item.code == "model-validation")),
        ("native-depth-evidence", tuple(native_depth_gaps)),
        ("artifact-realization", tuple(item for item in gaps if item.code in structural_gap_codes - {"model-validation"})),
        ("independent-artifact-inventory", tuple(inventory_gaps)),
        ("structural-reconstruction", tuple(structural_gaps)),
        ("content-resource-reconstruction", tuple(content_gaps)),
    )
    layer_statuses: list[dict[str, object]] = []
    prior_passed = True
    deepest = "none"
    for layer_id, layer_gaps in layer_definitions:
        if not prior_passed:
            layer_statuses.append({"layer_id": layer_id, "status": "not_run", "gap_ids": []})
            continue
        passed = not layer_gaps
        layer_statuses.append(
            {
                "layer_id": layer_id,
                "status": "passed" if passed else "failed",
                "gap_ids": [f"{item.code}:{item.object_id}" for item in layer_gaps],
            }
        )
        if passed:
            deepest = layer_id
        else:
            prior_passed = False
    fingerprint = _digest(
        {
            "model": model.canonical_dict(),
            "inventory": inventory.to_dict(),
            "realizations": [item.to_dict() for item in sorted(bindings, key=lambda item: item.artifact_unit_id)],
            "native_depth_evidence": (
                native_depth_evidence.to_dict()
                if native_depth_evidence is not None
                else None
            ),
        }
    )
    first = next(
        (
            str(row["gap_ids"][0])
            for row in layer_statuses
            if row["status"] == "failed" and row["gap_ids"]
        ),
        "",
    )
    return LogicBlueprintResult(
        status="complete" if structural_ok else "incomplete",
        completion_scope=(
            "content_resource" if content_ok else "structural" if structural_ok else "incomplete"
        ),
        model_id=model.id,
        model_fingerprint=f"sha256:{model_fingerprint(model)}",
        inventory_fingerprint=inventory.fingerprint,
        blueprint_fingerprint=fingerprint,
        deepest_proven_layer=deepest,
        first_unresolved_gap=first,
        structural_reconstruction="licensed" if structural_ok else "not_licensed",
        content_reconstruction="licensed" if content_ok else "not_licensed",
        gaps=tuple(gaps),
        layer_statuses=tuple(layer_statuses),
        native_depth_status=native_depth_status,
        native_depth_gaps=tuple(native_depth_gaps),
    )


def impact_blueprint(
    model: LogicModel,
    inventory: ArtifactInventory,
    realizations: Iterable[ArtifactRealizationBinding],
    changed_ids: Iterable[str],
    native_depth_evidence: LogicNativeDepthEvidence | None = None,
) -> dict[str, object]:
    changed = set(changed_ids)
    bindings = tuple(realizations)
    qualification = check_blueprint(
        model, inventory, bindings, native_depth_evidence
    )
    authority = inventory.target_authority
    if (
        qualification.status != "complete"
        or qualification.native_depth_status != "current"
    ):
        return {
            "query_status": "blocked",
            "qualification_status": qualification.status,
            "qualification_model_fingerprint": qualification.model_fingerprint,
            "native_depth_status": qualification.native_depth_status,
            "qualification_gaps": [item.to_dict() for item in qualification.gaps],
            "native_depth_gaps": [
                item.to_dict() for item in qualification.native_depth_gaps
            ],
            "target_authority_status": authority.status if authority else "not_run",
            "target_material_status": (
                authority.native_attestation.status
                if authority and authority.native_attestation
                else "not_run"
            ),
            "model_id": model.id,
            "model_fingerprint": f"sha256:{model_fingerprint(model)}",
            "inventory_id": inventory.inventory_id,
            "inventory_fingerprint": inventory.fingerprint,
            "changed_ids": sorted(changed),
            "affected_artifact_unit_ids": [],
            "affected_argument_block_ids": [],
            "affected_node_ids": [],
            "affected_model_edge_ids": [],
            "affected_block_interface_ids": [],
            "affected_realization_binding_ids": [],
            "affected_citation_ids": [],
            "affected_resource_ids": [],
            "affected_overlay_ids": [],
            "affected_synthesis_projection_ids": [],
            "affected_receipt_refs": [],
            "unknown_dependency_ids": [],
            "unknown_ownership": False,
            "partial_result_suppressed": True,
        }
    inventory_units = {item.unit_id: item for item in inventory.units}
    resource_roles = {
        resource.resource_id: resource.role
        for unit in inventory.units
        for resource in unit.resources
    }
    resource_owners = {
        resource.resource_id: unit.unit_id
        for unit in inventory.units
        for resource in unit.resources
    }
    def stable_strings(value: object) -> set[str]:
        result: set[str] = set()

        def visit(item: object) -> None:
            if isinstance(item, Mapping):
                for child in item.values():
                    visit(child)
            elif isinstance(item, (list, tuple, set)):
                for child in item:
                    visit(child)
            elif isinstance(item, str) and item:
                result.add(item)

        visit(value)
        return result

    node_tokens = {
        node_id: stable_strings(node.canonical_dict()) | {_digest(node.canonical_dict())}
        for node_id, node in model.nodes.items()
    }
    block_tokens = {
        block_id: stable_strings(block.to_dict()) | {_digest(block.to_dict())}
        for block_id, block in model.blocks.items()
    }
    edge_rows = {
        (edge.id or f"edge:{edge.source}:{edge.type}:{edge.target}"): edge
        for edge in model.edges
    }
    edge_tokens = {
        edge_id: stable_strings(edge.canonical_dict()) | {edge_id, _digest(edge.canonical_dict())}
        for edge_id, edge in edge_rows.items()
    }
    interface_rows = {
        (
            f"interface:{item.child_block_id}:{item.child_output_claim_id}"
            f"->{item.parent_block_id}:{item.parent_input_node_id}"
        ): item
        for item in model.block_interfaces
    }
    interface_tokens = {
        interface_id: stable_strings(item.to_dict()) | {interface_id, _digest(item.to_dict())}
        for interface_id, item in interface_rows.items()
    }
    realization_rows = {
        f"realization:{item.artifact_unit_id}->{item.argument_block_id}": item
        for item in bindings
    }
    realization_tokens = {
        realization_id: stable_strings(item.to_dict()) | {realization_id, _digest(item.to_dict())}
        for realization_id, item in realization_rows.items()
    }
    unit_tokens = {
        unit.unit_id: stable_strings(unit.to_dict()) | {_digest(unit.to_dict())}
        for unit in inventory.units
    }
    resource_rows = {
        resource.resource_id: resource
        for unit in inventory.units
        for resource in unit.resources
    }
    resource_tokens = {
        resource_id: stable_strings(resource.to_dict()) | {
            _digest(resource.to_dict()),
            resource.expected_observation_receipt_fingerprint,
        }
        for resource_id, resource in resource_rows.items()
    }
    global_tokens = {
        model.id,
        model.schema_version,
        f"sha256:{model_fingerprint(model)}",
        inventory.inventory_id,
        inventory.source_revision,
        inventory.root_unit_id,
        inventory.fingerprint,
        qualification.blueprint_fingerprint,
        *stable_strings(model.metadata),
    }
    known_dependency_ids = set(global_tokens)
    for token_map in (
        node_tokens,
        block_tokens,
        edge_tokens,
        interface_tokens,
        realization_tokens,
        unit_tokens,
        resource_tokens,
    ):
        known_dependency_ids.update(value for values in token_map.values() for value in values)

    global_change = bool(changed & global_tokens)
    affected_nodes = set(model.nodes) if global_change else {
        node_id for node_id, values in node_tokens.items() if changed & values
    }
    affected_blocks = set(model.blocks) if global_change else {
        block_id for block_id, values in block_tokens.items() if changed & values
    }
    affected_edges = set(edge_rows) if global_change else {
        edge_id for edge_id, values in edge_tokens.items() if changed & values
    }
    affected_interfaces = set(interface_rows) if global_change else {
        interface_id for interface_id, values in interface_tokens.items() if changed & values
    }
    affected_realizations = set(realization_rows) if global_change else {
        realization_id for realization_id, values in realization_tokens.items() if changed & values
    }
    affected_units = set(inventory_units) if global_change else {
        unit_id for unit_id, values in unit_tokens.items() if changed & values
    }
    affected_resources = set(resource_rows) if global_change else {
        resource_id for resource_id, values in resource_tokens.items() if changed & values
    }

    # Close the declared direction graph to a fixed point. This lets a resource
    # fingerprint reach its unit, realization, block, parent interface, claims,
    # overlays, and receipts without selecting an unrelated sibling branch.
    while True:
        before = (
            len(affected_nodes), len(affected_blocks), len(affected_edges),
            len(affected_interfaces), len(affected_realizations),
            len(affected_units), len(affected_resources),
        )
        for edge_id, edge in edge_rows.items():
            if edge_id in affected_edges or edge.source in affected_nodes:
                affected_edges.add(edge_id)
                affected_nodes.add(edge.target)
        for block_id, block in model.blocks.items():
            if affected_nodes & set(block.member_node_ids()):
                affected_blocks.add(block_id)
            if block_id in affected_blocks:
                affected_nodes.update(block.member_node_ids())
                if block.parent:
                    affected_blocks.add(block.parent)
        for interface_id, interface in interface_rows.items():
            if (
                interface_id in affected_interfaces
                or interface.child_block_id in affected_blocks
                or interface.child_output_claim_id in affected_nodes
            ):
                affected_interfaces.add(interface_id)
                affected_blocks.update((interface.child_block_id, interface.parent_block_id))
                affected_nodes.update(
                    (interface.child_output_claim_id, interface.parent_input_node_id)
                )
        for realization_id, binding in realization_rows.items():
            if (
                realization_id in affected_realizations
                or binding.artifact_unit_id in affected_units
                or binding.argument_block_id in affected_blocks
                or affected_nodes & set(binding.node_ids)
                or affected_resources & set(binding.resource_ids)
            ):
                affected_realizations.add(realization_id)
                affected_units.add(binding.artifact_unit_id)
                affected_blocks.add(binding.argument_block_id)
        for resource_id in tuple(affected_resources):
            owner = resource_owners.get(resource_id)
            if owner:
                affected_units.add(owner)
        for unit_id in tuple(affected_units):
            unit = inventory_units.get(unit_id)
            if unit:
                affected_resources.update(item.resource_id for item in unit.resources)
                if unit.parent_unit_id:
                    affected_units.add(unit.parent_unit_id)
        after = (
            len(affected_nodes), len(affected_blocks), len(affected_edges),
            len(affected_interfaces), len(affected_realizations),
            len(affected_units), len(affected_resources),
        )
        if after == before:
            break

    affected_citations = {item for item in affected_resources if resource_roles.get(item) == "citation"}
    affected_receipts = {item for item in affected_resources if resource_roles.get(item) == "receipt"}
    unknown_dependency_ids = sorted(changed - known_dependency_ids)
    result = {
        "query_status": "complete",
        "qualification_status": qualification.status,
        "qualification_model_fingerprint": qualification.model_fingerprint,
        "native_depth_status": qualification.native_depth_status,
        "qualification_gaps": [],
        "native_depth_gaps": [],
        "target_authority_status": authority.status if authority else "not_run",
        "target_material_status": (
            authority.native_attestation.status
            if authority and authority.native_attestation
            else "not_run"
        ),
        "model_id": model.id,
        "model_fingerprint": f"sha256:{model_fingerprint(model)}",
        "inventory_id": inventory.inventory_id,
        "inventory_fingerprint": inventory.fingerprint,
        "changed_ids": sorted(changed),
        "affected_artifact_unit_ids": sorted(affected_units),
        "affected_argument_block_ids": sorted(affected_blocks),
        "affected_node_ids": sorted(affected_nodes),
        "affected_model_edge_ids": sorted(affected_edges),
        "affected_block_interface_ids": sorted(affected_interfaces),
        "affected_realization_binding_ids": sorted(affected_realizations),
        "affected_citation_ids": sorted(affected_citations),
        "affected_resource_ids": sorted(affected_resources),
        "affected_overlay_ids": sorted(f"overlay:{item}" for item in affected_blocks),
        "affected_synthesis_projection_ids": sorted(f"synthesis:{item}" for item in affected_units),
        "affected_receipt_refs": sorted(affected_receipts),
        "unknown_dependency_ids": unknown_dependency_ids,
        "unknown_ownership": bool(unknown_dependency_ids),
    }
    if unknown_dependency_ids:
        for key in tuple(result):
            if key.startswith("affected_"):
                result[key] = []
        result["partial_result_suppressed"] = True
    else:
        result["partial_result_suppressed"] = False
    return result


def reverse_trace_artifact(
    model: LogicModel,
    inventory: ArtifactInventory,
    realizations: Iterable[ArtifactRealizationBinding],
    artifact_unit_id: str,
    native_depth_evidence: LogicNativeDepthEvidence | None = None,
) -> dict[str, object]:
    bindings = tuple(realizations)
    qualification = check_blueprint(
        model, inventory, bindings, native_depth_evidence
    )
    authority = inventory.target_authority
    target_material_status = (
        authority.native_attestation.status
        if authority and authority.native_attestation
        else "not_run"
    )
    if (
        qualification.status != "complete"
        or qualification.native_depth_status != "current"
    ):
        trace_gap_by_identity = {
            (item.code, item.object_id, item.detail): item.to_dict()
            for item in qualification.gaps
        }
        trace_gaps = sorted(
            trace_gap_by_identity.values(),
            key=lambda item: (item["code"], item["object_id"], item["detail"]),
        )
        return {
            "query_status": "blocked",
            "qualification_status": qualification.status,
            "qualification_model_fingerprint": qualification.model_fingerprint,
            "artifact_unit": {},
            "argument_block_id": "",
            "output_claim_ids": [],
            "trace_status": "incomplete",
            "blueprint_status": qualification.status,
            "blueprint_gaps": [item.to_dict() for item in qualification.gaps],
            "native_depth_status": qualification.native_depth_status,
            "native_depth_gaps": [
                item.to_dict() for item in qualification.native_depth_gaps
            ],
            "target_authority_status": authority.status if authority else "not_run",
            "target_material_status": target_material_status,
            "traced_nodes": [],
            "relation_hops": [],
            "support_ids": [],
            "opposition_ids": [],
            "warrant_ids": [],
            "assumption_ids": [],
            "rebuttal_ids": [],
            "evidence_ids": [],
            "boundary_ids": [],
            "cycle_witnesses": [],
            "trace_gaps": trace_gaps,
            "citation_ids": [],
            "source_refs": [],
            "receipt_refs": [],
            "resource_bindings": [],
            "partial_result_suppressed": True,
            "claim_boundary": qualification.claim_boundary,
        }
    binding = next((item for item in bindings if item.artifact_unit_id == artifact_unit_id), None)
    if binding is None:
        raise ValueError(f"artifact unit {artifact_unit_id!r} has no realization binding")
    unit = next(item for item in inventory.units if item.unit_id == artifact_unit_id)
    block = model.blocks[binding.argument_block_id]
    output_claims = list(block.output_claims)
    relation_rows: list[dict[str, object]] = []
    traced_nodes: dict[str, dict[str, object]] = {}
    source_refs: set[str] = set()
    cycle_witnesses: list[list[str]] = []
    gaps: list[dict[str, str]] = []
    completed: set[str] = set()

    def visit(node_id: str, path: tuple[str, ...]) -> None:
        if node_id in path:
            cycle_witnesses.append([*path[path.index(node_id) :], node_id])
            return
        if node_id in completed:
            return
        node = model.nodes.get(node_id)
        if node is None:
            gaps.append({"code": "missing-node", "object_id": node_id, "detail": ""})
            return
        traced_nodes[node_id] = {
            "node_id": node.id,
            "node_type": node.type,
            "text": node.text,
        }
        for key in ("source_id", "source_ref", "citation_id"):
            value = node.get(key)
            if value:
                source_refs.add(str(value))
        incoming = sorted(
            model.incoming(node_id),
            key=lambda edge: (edge.source, edge.target, edge.type, edge.id),
        )
        if not incoming:
            declared_terminus = node.type in {
                "Evidence",
                "Warrant",
                "Assumption",
                "Rebuttal",
                "Undercutter",
                "Qualifier",
                "Context",
                "Definition",
                "Method",
                "Result",
                "Limitation",
            } or any(node.get(key) for key in ("source_id", "source_ref", "citation_id"))
            if not declared_terminus:
                gaps.append(
                    {"code": "missing-predecessor", "object_id": node_id, "detail": ""}
                )
        for edge in incoming:
            row = edge.to_dict()
            row["direction"] = "source_to_target"
            relation_rows.append(row)
            visit(edge.source, (*path, node_id))
        completed.add(node_id)

    for claim_id in output_claims:
        visit(claim_id, ())
    if not output_claims:
        gaps.append(
            {"code": "empty-terminal-chain", "object_id": block.id, "detail": ""}
        )
    resources = {
        resource.resource_id: resource
        for artifact_unit in inventory.units
        for resource in artifact_unit.resources
    }
    bound_resources = [resources[item] for item in binding.resource_ids if item in resources]
    nodes_by_type: dict[str, list[str]] = {}
    for node_id, row in traced_nodes.items():
        nodes_by_type.setdefault(str(row["node_type"]), []).append(node_id)
    return {
        "query_status": "complete",
        "qualification_status": qualification.status,
        "qualification_model_fingerprint": qualification.model_fingerprint,
        "artifact_unit": unit.to_dict(),
        "argument_block_id": block.id,
        "output_claim_ids": output_claims,
        "trace_status": "incomplete" if gaps or cycle_witnesses else "complete",
        "blueprint_status": qualification.status,
        "blueprint_gaps": [],
        "native_depth_status": qualification.native_depth_status,
        "native_depth_gaps": [],
        "target_authority_status": authority.status if authority else "not_run",
        "target_material_status": target_material_status,
        "traced_nodes": [traced_nodes[item] for item in sorted(traced_nodes)],
        "relation_hops": sorted(relation_rows, key=lambda item: (str(item.get("target")), str(item.get("source")), str(item.get("type")))),
        "support_ids": sorted(
            {str(item["source"]) for item in relation_rows if item.get("type") in {"supports", "depends_on", "refines", "derives", "aggregates"}}
        ),
        "opposition_ids": sorted(
            {str(item["source"]) for item in relation_rows if item.get("type") in {"attacks", "contradicts", "undercuts"}}
        ),
        "warrant_ids": sorted(nodes_by_type.get("Warrant", [])),
        "assumption_ids": sorted(set(block.local_assumptions) | set(nodes_by_type.get("Assumption", []))),
        "rebuttal_ids": sorted(set(block.local_rebuttals) | set(nodes_by_type.get("Rebuttal", []))),
        "evidence_ids": sorted(nodes_by_type.get("Evidence", [])),
        "boundary_ids": sorted(
            set(nodes_by_type.get("Qualifier", [])) | set(nodes_by_type.get("Limitation", []))
        ),
        "cycle_witnesses": sorted(cycle_witnesses),
        "trace_gaps": sorted(
            {
                (item["code"], item["object_id"], item["detail"]): item
                for item in gaps
            }.values(),
            key=lambda item: (item["code"], item["object_id"], item["detail"]),
        ),
        "citation_ids": sorted(item.resource_id for item in bound_resources if item.role == "citation"),
        "source_refs": sorted(source_refs),
        "receipt_refs": sorted(item.resource_id for item in bound_resources if item.role == "receipt"),
        "resource_bindings": [item.to_dict() for item in sorted(bound_resources, key=lambda row: row.resource_id)],
        "partial_result_suppressed": False,
        "claim_boundary": qualification.claim_boundary,
    }


def export_blueprint(
    model: LogicModel,
    inventory: ArtifactInventory,
    realizations: Iterable[ArtifactRealizationBinding],
    native_depth_evidence: LogicNativeDepthEvidence | None = None,
) -> dict[str, object]:
    bindings = tuple(realizations)
    return {
        "schema_version": LOGIC_BLUEPRINT_SCHEMA,
        "model": model.canonical_dict(),
        "artifact_inventory": inventory.to_dict(),
        "realizations": [item.to_dict() for item in sorted(bindings, key=lambda item: item.artifact_unit_id)],
        "check": check_blueprint(
            model,
            inventory,
            bindings,
            native_depth_evidence,
        ).to_dict(),
    }


__all__ = [
    "LOGIC_BLUEPRINT_SCHEMA",
    "ArtifactRealizationBinding",
    "LogicBlueprintGap",
    "LogicBlueprintResult",
    "LogicNativeDepthEvidence",
    "check_blueprint",
    "export_blueprint",
    "impact_blueprint",
    "reverse_trace_artifact",
]
