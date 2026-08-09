from __future__ import annotations

from dataclasses import replace

import pytest

from admission_fixtures import attach_logic_inventory_receipts
from target_material_fixtures import artifact_expected_target_anchor

from researchguard.logic import (
    ArtifactInventory,
    ArtifactRealizationBinding,
    ArtifactResourceBinding,
    ArtifactUnit,
    block_interface_payload_fingerprint,
    block_interface_receipt_payload,
    block_interface_receipt_fingerprint,
    check_blueprint,
    interface_model_fingerprint,
    load_model_from_dict,
    validate_model,
)
from researchguard.logic.artifact_inventory import (
    _bind_artifact_inventory_authority as issue_artifact_inventory_authority,
)


def _refresh_interfaces(model):
    for binding in model.block_interfaces:
        binding.consumed_fingerprint = block_interface_payload_fingerprint(model, binding)
        binding.producer_result_fingerprint = binding.consumed_fingerprint
        binding.producer_model_fingerprint = interface_model_fingerprint(model)
        binding.parent_receipt_fingerprint = block_interface_receipt_fingerprint(model, binding)
    return model


def _model(
    *,
    interfaces: bool = True,
    structural_parent: str = "B_PARENT",
    receipt_namespace: str = "",
):
    payload = {
        "model": {"id": "logic-blueprint", "root_claim": "C_ROOT", "blueprint_interfaces_required": True},
        "nodes": {
            "B_PARENT": {"type": "ArgumentBlock", "text": "Parent"},
            "B_CHILD": {"type": "ArgumentBlock", "text": "Child", "parent": structural_parent},
            "N_INPUT": {"type": "Evidence", "text": "Child contribution", "importance": 0.8},
            "C_ROOT": {"type": "Claim", "text": "Conclusion", "importance": 1.0},
            "C_CHILD": {"type": "Claim", "text": "Leaf conclusion", "importance": 0.8, "source_id": "source:leaf"},
        },
        "edges": [{"source": "C_CHILD", "target": "C_ROOT", "type": "supports"}],
        "blocks": {
            "B_PARENT": {
                "parent": None,
                "child_blocks": ["B_CHILD"],
                "input_nodes": ["N_INPUT"],
                "output_claims": ["C_ROOT"],
                "root_claim": "C_ROOT",
                "member_nodes": ["N_INPUT", "C_ROOT"],
                "input_classifications": {"N_INPUT": "claim-summary"},
                "output_classifications": {"C_ROOT": "conclusion"},
            },
            "B_CHILD": {
                "parent": "B_PARENT",
                "output_claims": ["C_CHILD"],
                "root_claim": "C_CHILD",
                "member_nodes": ["C_CHILD"],
                "output_classifications": {"C_CHILD": "claim-summary"},
            },
        },
        "block_interfaces": (
            [
                {
                    "child_block_id": "B_CHILD",
                    "child_output_claim_id": "C_CHILD",
                    "parent_block_id": "B_PARENT",
                    "parent_input_node_id": "N_INPUT",
                    "output_classification": "claim-summary",
                    "input_classification": "claim-summary",
                    "scope": "artifact:report",
                    "payload_schema_id": "logic.claim-summary.v1",
                    "refinement_id": "refinement:claim-summary-to-parent-input",
                    "consumer_status": "consumed",
                    "consumed_fingerprint": "sha256:" + "0" * 64,
                    "parent_receipt_id": f"receipt:parent{receipt_namespace}",
                    "parent_receipt_fingerprint": "sha256:" + "0" * 64,
                    "producer_model_fingerprint": "sha256:" + "0" * 64,
                    "producer_result_fingerprint": "sha256:" + "0" * 64,
                    "producer_task_id": "logic-blueprint",
                    "receipt_status": "current",
                }
            ]
            if interfaces
            else []
        ),
    }
    model = load_model_from_dict(payload, validate=False)
    return _refresh_interfaces(model)


def _inventory(
    *,
    child_disposition: str = "parsed",
    model=None,
    receipt_namespace: str = "",
    inventory_id: str | None = None,
    source_revision: str | None = None,
) -> ArtifactInventory:
    document_fingerprint = "sha256:" + "b" * 64
    section_fingerprint = "sha256:" + "c" * 64 if child_disposition == "parsed" else ""
    current_model = model or _model()
    parent_receipt_fingerprint = current_model.block_interfaces[0].parent_receipt_fingerprint
    inventory = ArtifactInventory(
        inventory_id=inventory_id
        or (
            "inventory:report"
            if child_disposition == "parsed"
            else "inventory:report:unparsed"
        ),
        source_revision=source_revision
        or (
            "revision:1"
            if child_disposition == "parsed"
            else "revision:1:unparsed"
        ),
        root_unit_id="unit:document",
        units=(
            ArtifactUnit(
                "unit:document",
                "",
                "document",
                document_fingerprint,
                required_resource_roles=("content", "layout", "receipt"),
                resources=(
                    ArtifactResourceBinding(
                        "resource:document-content",
                        "content",
                        "document",
                        document_fingerprint,
                        "owner:document",
                    ),
                    ArtifactResourceBinding(
                        "resource:document-layout",
                        "layout",
                        "document:layout",
                        "sha256:" + "d" * 64,
                        "owner:layout",
                    ),
                    ArtifactResourceBinding(
                        f"receipt:parent{receipt_namespace}",
                        "receipt",
                        "receipt-store:parent",
                        parent_receipt_fingerprint,
                        "owner:logicguard",
                    ),
                ),
            ),
            ArtifactUnit(
                "unit:section",
                "unit:document",
                "section 1",
                section_fingerprint,
                required_resource_roles=("content", "citation", "receipt") if child_disposition == "parsed" else (),
                resources=(
                    ArtifactResourceBinding(
                        "resource:section-content",
                        "content",
                        "section 1",
                        section_fingerprint,
                        "owner:section",
                    ),
                    ArtifactResourceBinding(
                        "citation:leaf",
                        "citation",
                        "section 1:citation 1",
                        "sha256:" + "e" * 64,
                        "owner:citation",
                    ),
                    ArtifactResourceBinding(
                        f"receipt:leaf{receipt_namespace}",
                        "receipt",
                        "receipt-store:leaf",
                        "sha256:" + "f" * 64,
                        "owner:logicguard",
                    ),
                ) if child_disposition == "parsed" else (),
                parse_disposition=child_disposition,
                disposition_reason="parser unavailable" if child_disposition != "parsed" else "",
            ),
        ),
    )
    inventory = issue_artifact_inventory_authority(
        inventory,
        expected_target_anchor=artifact_expected_target_anchor(inventory),
    )
    return attach_logic_inventory_receipts(current_model, inventory)


def _bindings(inventory: ArtifactInventory):
    fingerprints = {item.unit_id: item.content_fingerprint for item in inventory.units}
    dispositions = {item.unit_id: item.parse_disposition for item in inventory.units}
    resources = {
        item.unit_id: tuple(resource.resource_id for resource in item.resources)
        for item in inventory.units
    }
    section_binding = (
        ArtifactRealizationBinding(
            "unit:section",
            "B_CHILD",
            ("C_CHILD",),
            resource_ids=resources["unit:section"],
            consumed_content_fingerprint=fingerprints["unit:section"],
        )
        if dispositions["unit:section"] == "parsed"
        else ArtifactRealizationBinding(
            "unit:section",
            "B_CHILD",
            ("C_CHILD",),
            disposition="unresolved",
        )
    )
    return (
        ArtifactRealizationBinding(
            "unit:document",
            "B_PARENT",
            ("N_INPUT", "C_ROOT"),
            resource_ids=resources["unit:document"],
            consumed_content_fingerprint=fingerprints["unit:document"],
        ),
        section_binding,
    )


def test_child_output_closes_exact_parent_input() -> None:
    model = _model()
    inventory = _inventory()
    result = check_blueprint(model, inventory, _bindings(inventory))
    assert validate_model(model).ok
    assert result.status == "incomplete"
    assert result.completion_scope == "incomplete"
    assert result.structural_reconstruction == "not_licensed"
    assert result.content_reconstruction == "not_licensed"
    assert result.deepest_proven_layer == "argument-model"
    assert result.native_depth_status == "not_run"
    assert any(item.code == "native-depth-not-run" for item in result.gaps)
    assert any(item.code == "resource-not-observed" for item in result.gaps)


def test_missing_producer_and_unconsumed_output_block() -> None:
    result = validate_model(_model(interfaces=False))
    assert not result.ok
    assert any("has no permitted producer" in item for item in result.errors)
    assert any("is unconsumed" in item for item in result.errors)


def test_conflicting_structural_parent_is_error_not_warning() -> None:
    result = validate_model(_model(structural_parent="OTHER"))
    assert not result.ok
    assert any("parent disagrees" in item or "outside the canonical" in item for item in result.errors)


@pytest.mark.parametrize("defect", ["unknown_block", "unknown_node", "subset", "duplicate_block", "omitted_block"])
def test_realization_defects_never_license_structure_or_content(defect: str) -> None:
    inventory = _inventory()
    bindings = list(_bindings(inventory))
    if defect == "unknown_block":
        bindings[1] = replace(bindings[1], argument_block_id="B_UNKNOWN")
    elif defect == "unknown_node":
        bindings[1] = replace(bindings[1], node_ids=("C_CHILD", "N_UNKNOWN"))
    elif defect == "subset":
        bindings[0] = replace(bindings[0], node_ids=("C_ROOT",))
    elif defect == "duplicate_block":
        bindings[1] = replace(bindings[1], argument_block_id="B_PARENT", node_ids=("N_INPUT", "C_ROOT"))
    else:
        bindings = bindings[:1]
    result = check_blueprint(_model(), inventory, bindings)
    assert result.status == "incomplete"
    assert result.structural_reconstruction == "not_licensed"
    assert result.content_reconstruction == "not_licensed"
    assert any(row["status"] == "failed" for row in result.layer_statuses)
    failed_index = next(index for index, row in enumerate(result.layer_statuses) if row["status"] == "failed")
    assert all(row["status"] == "not_run" for row in result.layer_statuses[failed_index + 1 :])


def test_interface_consumed_fingerprint_is_derived_not_caller_chosen() -> None:
    model = _model()
    model.block_interfaces[0].consumed_fingerprint = "sha256:" + "9" * 64
    result = validate_model(model)
    assert not result.ok
    assert any("consumed fingerprint" in item for item in result.errors)
