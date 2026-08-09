from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from admission_fixtures import (
    attach_logic_depth_receipt,
    attach_logic_inventory_receipts,
    self_resign_target_authority,
)
from target_material_fixtures import (
    artifact_expected_target_anchor,
    expected_target_anchor_from_material,
)
import researchguard.target_authority as target_authority_transport
import researchguard.logic.blueprint as blueprint_module

from researchguard.logic import (
    ArtifactInventory,
    ArtifactRealizationBinding,
    ArtifactResourceBinding,
    ArtifactUnit,
    artifact_inventory_subject_fingerprint,
    block_interface_receipt_payload,
    Edge,
    LogicNativeDepthEvidence,
    Node,
    check_blueprint,
    export_blueprint,
    impact_blueprint as _impact_blueprint,
    load_model,
    reverse_trace_artifact,
)
from researchguard.logic.blueprint import (
    _run_logic_native_depth_evidence as issue_logic_native_depth_evidence,
)
from researchguard.logic.artifact_inventory import (
    _bind_artifact_inventory_authority as issue_artifact_inventory_authority,
)

from .test_blueprint_interfaces import _bindings, _inventory, _model, _refresh_interfaces
from .test_dynamic_model_purpose_contract import _prepare
from researchguard.logic.execution_depth import _build_native_depth_analysis


def _as_current_native_depth(result):
    remaining_gaps = tuple(
        item for item in result.gaps if not item.code.startswith("native-depth-")
    )
    layer_statuses = []
    prior_passed = True
    for row in result.layer_statuses:
        current = dict(row)
        if current["layer_id"] == "native-depth-evidence":
            current = {"layer_id": current["layer_id"], "status": "passed", "gap_ids": []}
        elif current["status"] == "not_run" and prior_passed:
            current = {"layer_id": current["layer_id"], "status": "passed", "gap_ids": []}
        if current["status"] == "failed":
            prior_passed = False
        layer_statuses.append(current)
    return replace(
        result,
        status="complete",
        completion_scope=(
            "content_resource"
            if not any(item.code.startswith("resource-") or "content" in item.code for item in remaining_gaps)
            else "structural"
        ),
        structural_reconstruction="licensed",
        gaps=remaining_gaps,
        layer_statuses=tuple(layer_statuses),
        native_depth_status="current",
        native_depth_gaps=(),
    )


def _admit_current_native_depth(monkeypatch: pytest.MonkeyPatch) -> None:
    original = blueprint_module.check_blueprint

    def current(*args, **kwargs):
        return _as_current_native_depth(original(*args, **kwargs))

    monkeypatch.setattr(blueprint_module, "check_blueprint", current)


def impact_blueprint(
    model,
    inventory,
    bindings,
    changed_ids,
) -> dict[str, object]:
    """Exercise impact closure after one admitted native-depth qualification."""

    original = blueprint_module.check_blueprint

    def current(*args, **kwargs):
        return _as_current_native_depth(original(*args, **kwargs))

    with patch.object(blueprint_module, "check_blueprint", current):
        return _impact_blueprint(model, inventory, bindings, changed_ids)


def test_inventory_fingerprint_and_export_are_deterministic() -> None:
    inventory = _inventory()
    payload = inventory.to_dict()
    assert ArtifactInventory.from_dict(payload).fingerprint == inventory.fingerprint
    assert export_blueprint(_model(), inventory, _bindings(inventory)) == export_blueprint(
        _model(), inventory, _bindings(inventory)
    )


def test_native_depth_requires_the_exact_leaf_interface_receipt_set() -> None:
    model = _model()
    inventory = _inventory()
    bindings = _bindings(inventory)
    common = {
        "budget": 8,
        "artifact_inventory": inventory,
        "artifact_binding_unit_ids": tuple(
            item.artifact_unit_id for item in bindings
        ),
    }
    missing = _build_native_depth_analysis(
        model,
        interface_receipt_refs=(),
        **common,
    )
    assert "leaf_interface_receipt_missing:receipt:parent" in missing.unresolved_gaps

    foreign = _build_native_depth_analysis(
        model,
        interface_receipt_refs=("receipt:parent", "receipt:aggregate"),
        **common,
    )
    assert "leaf_interface_receipt_foreign:receipt:aggregate" in foreign.unresolved_gaps

    exact = _build_native_depth_analysis(
        model,
        interface_receipt_refs=("receipt:parent",),
        **common,
    )
    assert not any(
        gap.startswith("leaf_interface_receipt_")
        for gap in exact.unresolved_gaps
    )


@pytest.mark.parametrize("defect", ["missing", "stale", "foreign"])
def test_leaf_receipt_requires_exact_immutable_producer_bytes(defect: str) -> None:
    model = _model()
    inventory = _inventory(model=model)
    leaf = next(
        item
        for item in inventory.native_receipt_refs
        if item.receipt_id == "receipt:leaf"
    )
    if defect == "missing":
        refs = tuple(
            item
            for item in inventory.native_receipt_refs
            if item.receipt_id != "receipt:leaf"
        )
    elif defect == "stale":
        refs = tuple(
            replace(item, result_fingerprint="sha256:" + "0" * 64)
            if item.receipt_id == "receipt:leaf"
            else item
            for item in inventory.native_receipt_refs
        )
    else:
        refs = tuple(
            replace(item, receipt_id="receipt:never-published")
            if item.receipt_id == leaf.receipt_id
            else item
            for item in inventory.native_receipt_refs
        )
    result = check_blueprint(
        model,
        replace(inventory, native_receipt_refs=refs),
        _bindings(inventory),
    )
    codes = {item.code for item in result.gaps}
    assert result.status == "incomplete"
    if defect in {"missing", "foreign"}:
        assert "native-receipt-missing" in codes
    if defect == "stale":
        assert "native-receipt-result-mismatch" in codes
    if defect == "foreign":
        assert "native-receipt-foreign" in codes


def test_logic_impact_without_current_qualification_is_atomically_blocked() -> None:
    inventory = replace(_inventory(), target_authority=None)
    result = _impact_blueprint(
        _model(), inventory, _bindings(inventory), ("unit:section",)
    )
    assert result["query_status"] == "blocked"
    assert result["qualification_status"] == "incomplete"
    assert result["target_authority_status"] == "not_run"
    assert result["target_material_status"] == "not_run"
    assert {item["code"] for item in result["qualification_gaps"]} >= {
        "missing-target-purpose-authority"
    }
    assert result["affected_artifact_unit_ids"] == []
    assert result["partial_result_suppressed"] is True


def test_serialized_logic_authority_replays_without_process_registry() -> None:
    inventory = ArtifactInventory.from_dict(
        json.loads(json.dumps(_inventory().to_dict()))
    )
    result = check_blueprint(_model(), inventory, _bindings(inventory))
    assert result.status == "incomplete"
    assert {item.code for item in result.gaps} >= {"native-depth-not-run"}
    assert not hasattr(target_authority_transport, "_FROZEN_NATIVE_RESULTS")


def test_fresh_process_accepts_independently_authored_alternate_logic_target(
    tmp_path: Path,
) -> None:
    alternate_model = _model(receipt_namespace=":alternate")
    inventory = _inventory(
        model=alternate_model,
        receipt_namespace=":alternate",
        inventory_id="inventory:alternate-report",
        source_revision="revision:alternate",
    )
    bindings = _bindings(inventory)
    result = check_blueprint(alternate_model, inventory, bindings)
    assert result.status == "incomplete"
    assert {item.code for item in result.gaps} >= {"native-depth-not-run"}
    context_path = tmp_path / "alternate-logic-context.json"
    context_path.write_text(
        json.dumps(
            {
                "inventory": inventory.to_dict(),
                "bindings": [item.to_dict() for item in bindings],
            }
        ),
        encoding="utf-8",
    )
    child = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            """
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd() / 'tests'))
from target_material_fixtures import install_test_expected_target_producer
install_test_expected_target_producer()
from admission_fixtures import install_test_native_receipt_producers
install_test_native_receipt_producers()
from logic.test_blueprint_interfaces import _model
from researchguard.logic import ArtifactInventory, ArtifactRealizationBinding, check_blueprint

context = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
inventory = ArtifactInventory.from_dict(context['inventory'])
bindings = tuple(
    ArtifactRealizationBinding(
        artifact_unit_id=row['artifact_unit_id'],
        argument_block_id=row['argument_block_id'],
        node_ids=tuple(row['node_ids']),
        resource_ids=tuple(row['resource_ids']),
        disposition=row['disposition'],
        consumed_content_fingerprint=row['consumed_content_fingerprint'],
    )
    for row in context['bindings']
)
result = check_blueprint(_model(receipt_namespace=':alternate'), inventory, bindings)
authority = inventory.target_authority
print(json.dumps({
    'status': result.status,
    'target_id': authority.target_id,
    'request_id': authority.request_id,
    'target_revision': authority.target_revision,
    'target_fingerprint': authority.target_fingerprint,
}))
""",
            str(context_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(child.stdout)
    assert result["status"] == "incomplete"
    assert result["target_id"] == "inventory:alternate-report"
    assert result["request_id"].startswith("request:")
    assert result["target_revision"] == result["target_fingerprint"]


def test_logic_queries_each_consume_one_blueprint_qualification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = _model()
    inventory = _inventory()
    bindings = _bindings(inventory)
    original = blueprint_module.check_blueprint
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(blueprint_module, "check_blueprint", counted)
    blueprint_module.impact_blueprint(model, inventory, bindings, ("unit:section",))
    assert calls == 1
    blueprint_module.reverse_trace_artifact(model, inventory, bindings, "unit:section")
    assert calls == 2


@pytest.mark.parametrize("native_status", ["stale", "failed", "not_run"])
def test_logic_reverse_gate_precedes_unknown_target_resolution(
    native_status: str,
) -> None:
    evidence = LogicNativeDepthEvidence(
        target_root="unused-target-root",
        guard_contract="unused-contract.json",
        budget=1,
        receipt={},
        receipt_fingerprint="sha256:" + "0" * 64,
        status=native_status,
    )
    inventory = _inventory()
    trace = reverse_trace_artifact(
        _model(),
        inventory,
        _bindings(inventory),
        "unit:missing",
        evidence,
    )
    assert trace["query_status"] == "blocked"
    assert trace["native_depth_status"] == native_status
    assert trace["artifact_unit"] == {}
    assert trace["traced_nodes"] == []
    assert trace["resource_bindings"] == []
    assert trace["partial_result_suppressed"] is True


def test_external_logic_target_material_remains_unverified() -> None:
    inventory = _inventory()
    unsigned = replace(inventory, target_authority=None)
    current_anchor = inventory.target_authority.expected_target_anchor
    external_anchor = expected_target_anchor_from_material(
        member_id="logicguard",
        task_id=current_anchor.task_id,
        target_request_fingerprint=current_anchor.target_request_fingerprint,
        target_id=current_anchor.target_id,
        target_revision=current_anchor.target_revision,
        material_locator="https://example.invalid/logic-target.json",
        material_fingerprint=current_anchor.material_fingerprint,
        admission_request_scope="external-unavailable",
    )
    unverified = issue_artifact_inventory_authority(
        unsigned,
        expected_target_anchor=external_anchor,
    )
    result = check_blueprint(_model(), unverified, _bindings(unverified))
    assert unverified.target_authority.status == "unverified"
    assert any(item.code == "native-target-material-unverified" for item in result.gaps)
    trace = reverse_trace_artifact(
        _model(),
        unverified,
        _bindings(unverified),
        "unit:missing",
    )
    assert trace["query_status"] == "blocked"
    assert trace["target_material_status"] == "unverified"
    assert trace["artifact_unit"] == {}
    assert trace["receipt_refs"] == []
    assert trace["partial_result_suppressed"] is True


def _with_local_observations(inventory: ArtifactInventory, root) -> ArtifactInventory:
    units = []
    for unit in inventory.units:
        resources = []
        unit_content_fingerprint = unit.content_fingerprint
        for resource in unit.resources:
            filename = resource.resource_id.replace(":", "-") + ".bin"
            if resource.resource_id == "receipt:parent":
                model = _model()
                body = json.dumps(
                    block_interface_receipt_payload(model, model.block_interfaces[0]),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            else:
                body = f"current bytes for {resource.resource_id}\n".encode()
            (root / filename).write_bytes(body)
            fingerprint = "sha256:" + hashlib.sha256(body).hexdigest()
            observed = replace(
                resource,
                locator=filename,
                content_fingerprint=fingerprint,
                observation_kind="local_file",
                observation_root=str(root.resolve()),
                subject_revision=inventory.source_revision,
                observed_fingerprint=fingerprint,
                observation_receipt_id=f"observation:{resource.resource_id}",
                observation_receipt_fingerprint="sha256:" + "0" * 64,
            )
            observed = replace(
                observed,
                observation_receipt_fingerprint=observed.expected_observation_receipt_fingerprint,
            )
            resources.append(observed)
            if resource.role == "content":
                unit_content_fingerprint = fingerprint
        units.append(replace(unit, content_fingerprint=unit_content_fingerprint, resources=tuple(resources)))
    changed = replace(inventory, units=tuple(units), target_authority=None)
    return issue_artifact_inventory_authority(
        changed,
        expected_target_anchor=artifact_expected_target_anchor(
            changed,
            admission_request_scope=f"observed-content:{artifact_inventory_subject_fingerprint(changed)}",
        ),
    )


def test_content_scope_requires_observed_current_bytes(tmp_path) -> None:
    inventory = _with_local_observations(_inventory(), tmp_path)
    result = check_blueprint(_model(), inventory, _bindings(inventory))
    assert result.completion_scope == "incomplete"
    assert result.content_reconstruction == "not_licensed"
    assert result.deepest_proven_layer == "argument-model"
    assert result.native_depth_status == "not_run"


def test_resource_declarations_do_not_replace_current_observation() -> None:
    inventory = _inventory()
    result = check_blueprint(_model(), inventory, _bindings(inventory))
    assert result.completion_scope == "incomplete"
    assert {item.object_id for item in result.gaps if item.code == "resource-not-observed"} == {
        resource.resource_id for unit in inventory.units for resource in unit.resources
    }


@pytest.mark.parametrize("bad_unit_id", ["unit:document", "unit:section"])
def test_every_inventory_unit_runs_resource_role_checks(bad_unit_id: str) -> None:
    current = _inventory()
    units = tuple(
        replace(unit, required_resource_roles=("asset",)) if unit.unit_id == bad_unit_id else unit
        for unit in current.units
    )
    inventory = replace(current, units=units)
    result = check_blueprint(_model(), inventory, _bindings(inventory))
    assert any(
        item.code == "missing-required-resource-role" and item.object_id == bad_unit_id
        for item in result.gaps
    )


@pytest.mark.parametrize("level", ["root", "unit", "resource"])
def test_inventory_loader_rejects_unknown_current_fields(level: str) -> None:
    payload = _inventory().to_dict()
    if level == "root":
        payload["future"] = True
    elif level == "unit":
        payload["units"][0]["future"] = True
    else:
        payload["units"][0]["resources"][0]["future"] = True
    with pytest.raises(ValueError, match="unknown fields"):
        ArtifactInventory.from_dict(payload)


@pytest.mark.parametrize("field", ["units", "resources"])
def test_inventory_loader_rejects_non_object_rows(field: str) -> None:
    payload = _inventory().to_dict()
    if field == "units":
        payload["units"].append("not-an-object")
    else:
        payload["units"][0]["resources"].append("not-an-object")
    with pytest.raises(ValueError, match="must be an object"):
        ArtifactInventory.from_dict(payload)


@pytest.mark.parametrize(
    ("mutation", "gap_code"),
    [
        ("bytes", "local-resource-bytes-mismatch"),
        ("escape", "unsafe-local-resource-locator"),
        ("missing", "missing-local-resource"),
        ("receipt", "resource-observation-receipt-mismatch"),
    ],
)
def test_local_resource_observation_fails_visibly(tmp_path, mutation: str, gap_code: str) -> None:
    inventory = _with_local_observations(_inventory(), tmp_path)
    first_unit = inventory.units[0]
    first_resource = first_unit.resources[0]
    if mutation == "bytes":
        (tmp_path / first_resource.locator).write_bytes(b"changed")
        changed = first_resource
    elif mutation == "escape":
        changed = replace(first_resource, locator="../outside.bin")
    elif mutation == "missing":
        changed = replace(first_resource, locator="missing.bin")
    else:
        changed = replace(first_resource, observation_receipt_fingerprint="sha256:" + "f" * 64)
    units = (
        replace(first_unit, resources=(changed, *first_unit.resources[1:])),
        *inventory.units[1:],
    )
    result = check_blueprint(_model(), replace(inventory, units=units), _bindings(inventory))
    assert any(item.code == gap_code and item.object_id == changed.resource_id for item in result.gaps)


def test_independent_inventory_omission_blocks_structure() -> None:
    inventory = _inventory()
    result = check_blueprint(_model(), inventory, _bindings(inventory)[:1])
    assert result.status == "incomplete"
    assert any(item.code == "unmodeled-artifact-unit" and item.object_id == "unit:section" for item in result.gaps)


def test_simultaneous_inventory_authority_shrink_cannot_self_sign_complete() -> None:
    inventory = _inventory()
    authority = inventory.target_authority
    assert authority is not None
    units = []
    for unit in inventory.units:
        if unit.unit_id == "unit:section":
            units.append(
                replace(
                    unit,
                    required_resource_roles=("content", "receipt"),
                    resources=tuple(
                        item for item in unit.resources if item.resource_id != "citation:leaf"
                    ),
                )
            )
        else:
            units.append(unit)
    resigned = self_resign_target_authority(
        authority,
        (
            item
            for item in authority.items
            if item.object_id not in {"unit:section:citation", "citation:leaf"}
        ),
    )
    shrunk = replace(inventory, units=tuple(units), target_authority=resigned)
    bindings = list(_bindings(shrunk))
    bindings[1] = replace(
        bindings[1],
        resource_ids=tuple(item for item in bindings[1].resource_ids if item != "citation:leaf"),
    )
    result = check_blueprint(_model(), shrunk, tuple(bindings))
    assert result.status == "incomplete"
    assert any(item.code == "native-target-denominator-mismatch" for item in result.gaps)


def test_fresh_process_first_issue_replays_original_logic_target_material(
    tmp_path: Path,
) -> None:
    inventory = _inventory()
    units = []
    for unit in inventory.units:
        if unit.unit_id == "unit:section":
            units.append(
                replace(
                    unit,
                    required_resource_roles=("content", "receipt"),
                    resources=tuple(
                        item for item in unit.resources if item.resource_id != "citation:leaf"
                    ),
                )
            )
        else:
            units.append(unit)
    shrunk = replace(inventory, units=tuple(units), target_authority=None)
    bindings = list(_bindings(shrunk))
    bindings[1] = replace(
        bindings[1],
        resource_ids=tuple(
            item for item in bindings[1].resource_ids if item != "citation:leaf"
        ),
    )
    assert inventory.target_authority is not None
    assert inventory.target_authority.native_attestation is not None
    context_path = tmp_path / "logic-child-context.json"
    context_path.write_text(
        json.dumps(
            {
                "inventory": shrunk.to_dict(),
                "bindings": [item.to_dict() for item in bindings],
                "expected_target_anchor": inventory.target_authority.expected_target_anchor.to_dict(),
            }
        ),
        encoding="utf-8",
    )
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd() / 'tests'))
from target_material_fixtures import install_test_expected_target_producer
install_test_expected_target_producer()
from admission_fixtures import install_test_native_receipt_producers
install_test_native_receipt_producers()
from logic.test_blueprint_interfaces import _model
from researchguard.logic import ArtifactInventory, ArtifactRealizationBinding, check_blueprint
from researchguard.logic.artifact_inventory import _bind_artifact_inventory_authority as issue_artifact_inventory_authority
from researchguard.target_authority import ExpectedTargetAnchor

context = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
inventory = ArtifactInventory.from_dict(context['inventory'])
inventory = issue_artifact_inventory_authority(
    inventory,
    expected_target_anchor=ExpectedTargetAnchor.from_dict(context['expected_target_anchor']),
)
bindings = tuple(
    ArtifactRealizationBinding(
        artifact_unit_id=row['artifact_unit_id'],
        argument_block_id=row['argument_block_id'],
        node_ids=tuple(row['node_ids']),
        resource_ids=tuple(row['resource_ids']),
        disposition=row['disposition'],
        consumed_content_fingerprint=row['consumed_content_fingerprint'],
    )
    for row in context['bindings']
)
result = check_blueprint(_model(), inventory, bindings)
print(json.dumps({'status': result.status, 'gaps': [[gap.code, gap.object_id] for gap in result.gaps]}))
""",
            str(context_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(child.stdout)
    assert payload["status"] == "incomplete"
    assert ["target-authority-omitted-resource", "citation:leaf"] in payload["gaps"]


def test_parse_gap_separates_structural_and_content_claims() -> None:
    inventory = _inventory(child_disposition="unparsed")
    bindings = (
        _bindings(inventory)[0],
        ArtifactRealizationBinding(
            "unit:section",
            "B_CHILD",
            ("C_CHILD",),
            disposition="unresolved",
        ),
    )
    result = check_blueprint(_model(), inventory, bindings)
    assert result.status == "incomplete"
    assert result.completion_scope == "incomplete"
    assert result.structural_reconstruction == "not_licensed"
    assert result.structural_reconstruction == "not_licensed"
    assert result.content_reconstruction == "not_licensed"
    assert any(item.code == "artifact-parse-gap" for item in result.gaps)


def test_content_change_invalidates_only_bound_branch_and_ancestors() -> None:
    inventory = _inventory()
    impact = impact_blueprint(_model(), inventory, _bindings(inventory), ("unit:section",))
    assert impact["affected_artifact_unit_ids"] == ["unit:document", "unit:section"]
    assert impact["affected_argument_block_ids"] == ["B_CHILD", "B_PARENT"]
    assert impact["affected_receipt_refs"] == ["receipt:leaf", "receipt:parent"]


def test_reverse_trace_preserves_argument_and_source_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _admit_current_native_depth(monkeypatch)
    inventory = _inventory()
    trace = reverse_trace_artifact(_model(), inventory, _bindings(inventory), "unit:section")
    assert trace["argument_block_id"] == "B_CHILD"
    assert trace["output_claim_ids"] == ["C_CHILD"]
    assert trace["citation_ids"] == ["citation:leaf"]
    assert trace["trace_status"] == "complete"
    assert trace["native_depth_status"] == "current"
    assert trace["receipt_refs"] == ["receipt:leaf"]
    with pytest.raises(ValueError, match="has no realization binding"):
        reverse_trace_artifact(_model(), inventory, _bindings(inventory), "unit:missing")


@pytest.mark.parametrize("role", ["asset", "citation", "receipt"])
def test_naked_resource_ids_cannot_license_exact_content(role: str) -> None:
    with pytest.raises(ValueError, match="exact sha256"):
        ArtifactResourceBinding(
            f"{role}:leaf",
            role,
            f"section 1:{role}",
            f"{role}:leaf",
            f"owner:{role}",
        )


def test_content_scope_requires_inventory_declared_resource_roles() -> None:
    current = _inventory()
    inventory = replace(
        current,
        inventory_id="inventory:structural-only",
        units=tuple(
            replace(item, required_resource_roles=(), resources=())
            for item in current.units
        ),
    )
    unsigned = replace(inventory, target_authority=None)
    inventory = issue_artifact_inventory_authority(
        unsigned,
        expected_target_anchor=artifact_expected_target_anchor(unsigned),
    )
    bindings = tuple(replace(item, resource_ids=()) for item in _bindings(inventory))
    result = check_blueprint(_model(), inventory, bindings)
    assert result.completion_scope == "incomplete"
    assert result.structural_reconstruction == "not_licensed"
    assert result.content_reconstruction == "not_licensed"
    assert any(item.code == "content-resource-role-not-declared" for item in result.gaps)


def test_recursive_reverse_trace_walks_three_layers_to_evidence_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _admit_current_native_depth(monkeypatch)
    model = _model()
    model.nodes["W_LEAF"] = Node("W_LEAF", "Warrant", "why the evidence supports the leaf")
    model.nodes["E_LEAF"] = Node(
        "E_LEAF",
        "Evidence",
        "measured result",
        metadata={"source_ref": "source:measured", "citation_id": "citation:leaf"},
    )
    model.edges.extend(
        [
            Edge("E_LEAF", "W_LEAF", "supports"),
            Edge("W_LEAF", "C_CHILD", "supports"),
        ]
    )
    model.rebuild_edge_indexes()
    model.blocks["B_CHILD"].internal_nodes.extend(["W_LEAF", "E_LEAF"])
    _refresh_interfaces(model)
    inventory = _inventory(model=model)
    bindings = list(_bindings(inventory))
    bindings[1] = replace(bindings[1], node_ids=("C_CHILD", "W_LEAF", "E_LEAF"))
    trace = reverse_trace_artifact(model, inventory, bindings, "unit:section")
    assert trace["trace_status"] == "complete"
    assert trace["native_depth_status"] == "current"
    assert trace["warrant_ids"] == ["W_LEAF"]
    assert trace["evidence_ids"] == ["E_LEAF"]
    assert trace["source_refs"] == ["citation:leaf", "source:leaf", "source:measured"]
    assert len(trace["relation_hops"]) == 2
    impact = impact_blueprint(model, inventory, tuple(bindings), ("E_LEAF",))
    assert impact["affected_node_ids"] == ["C_CHILD", "C_ROOT", "E_LEAF", "N_INPUT", "W_LEAF"]
    assert impact["affected_argument_block_ids"] == ["B_CHILD", "B_PARENT"]


def test_reverse_trace_preserves_cycle_witness_and_broken_predecessor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _admit_current_native_depth(monkeypatch)
    model = _model()
    model.nodes["P_LEAF"] = Node("P_LEAF", "Premise", "unsupported premise")
    model.nodes["W_LEAF"] = Node("W_LEAF", "Warrant", "cyclic warrant")
    model.edges.extend(
        [
            Edge("P_LEAF", "C_CHILD", "supports"),
            Edge("W_LEAF", "C_CHILD", "supports"),
            Edge("C_CHILD", "W_LEAF", "depends_on"),
        ]
    )
    model.rebuild_edge_indexes()
    _refresh_interfaces(model)
    inventory = _inventory(model=model)
    trace = reverse_trace_artifact(model, inventory, _bindings(inventory), "unit:section")
    assert trace["trace_status"] == "incomplete"
    assert trace["cycle_witnesses"] == [["C_CHILD", "W_LEAF", "C_CHILD"]]
    assert {
        (item["code"], item["object_id"])
        for item in trace["trace_gaps"]
        if item["code"] == "missing-predecessor"
    } == {("missing-predecessor", "P_LEAF")}
    trace_gap_keys = [
        (item["code"], item["object_id"], item["detail"])
        for item in trace["trace_gaps"]
    ]
    assert len(trace_gap_keys) == len(set(trace_gap_keys))
    assert {row["direction"] for row in trace["relation_hops"]} == {"source_to_target"}


def test_mixed_known_and_unknown_logic_change_remains_blocked() -> None:
    inventory = _inventory()
    impact = impact_blueprint(
        _model(),
        inventory,
        _bindings(inventory),
        ("citation:leaf", "foreign:unowned"),
    )
    assert impact["affected_argument_block_ids"] == []
    assert impact["affected_artifact_unit_ids"] == []
    assert impact["unknown_dependency_ids"] == ["foreign:unowned"]
    assert impact["unknown_ownership"] is True
    assert impact["partial_result_suppressed"] is True


@pytest.mark.parametrize(
    ("changed_id", "affected_key", "affected_id"),
    (
        ("edge-000000", "affected_model_edge_ids", "edge-000000"),
        (
            "interface:B_CHILD:C_CHILD->B_PARENT:N_INPUT",
            "affected_block_interface_ids",
            "interface:B_CHILD:C_CHILD->B_PARENT:N_INPUT",
        ),
        (
            "realization:unit:section->B_CHILD",
            "affected_realization_binding_ids",
            "realization:unit:section->B_CHILD",
        ),
        ("sha256:" + "e" * 64, "affected_citation_ids", "citation:leaf"),
    ),
)
def test_logic_stable_identity_denominator_drives_directional_impact(
    changed_id: str,
    affected_key: str,
    affected_id: str,
) -> None:
    inventory = _inventory()
    impact = impact_blueprint(_model(), inventory, _bindings(inventory), (changed_id,))
    assert affected_id in impact[affected_key]
    assert impact["affected_argument_block_ids"]
    assert impact["unknown_ownership"] is False


def test_logic_model_and_inventory_fingerprints_are_global_stable_seeds() -> None:
    model = _model()
    inventory = _inventory()
    bindings = _bindings(inventory)
    result = check_blueprint(model, inventory, bindings)
    for changed_id in (result.model_fingerprint, inventory.fingerprint, result.blueprint_fingerprint):
        impact = impact_blueprint(model, inventory, bindings, (changed_id,))
        assert impact["affected_argument_block_ids"] == ["B_CHILD", "B_PARENT"]
        assert impact["affected_artifact_unit_ids"] == ["unit:document", "unit:section"]


def test_logic_blueprint_cli_uses_one_grouped_native_surface(tmp_path, capsys) -> None:
    from researchguard.logic.cli import main

    model = _model()
    inventory = _inventory()
    bindings = _bindings(inventory)
    model_path = tmp_path / "logic-model.json"
    inventory_path = tmp_path / "logic-inventory.json"
    bindings_path = tmp_path / "logic-bindings.json"
    export_path = tmp_path / "logic-blueprint-export.json"
    model_path.write_text(json.dumps(model.to_dict()), encoding="utf-8")
    inventory_path.write_text(json.dumps(inventory.to_dict()), encoding="utf-8")
    bindings_path.write_text(
        json.dumps({"realizations": [item.to_dict() for item in bindings]}),
        encoding="utf-8",
    )
    common = [str(model_path), "--inventory", str(inventory_path), "--bindings", str(bindings_path)]

    assert main(["blueprint", "check", *common]) == 3
    assert json.loads(capsys.readouterr().out)["status"] == "incomplete"
    assert main(["blueprint", "impact", *common, "--changed-id", "citation:leaf"]) == 0
    blocked_depth = json.loads(capsys.readouterr().out)
    assert blocked_depth["query_status"] == "blocked"
    assert blocked_depth["native_depth_status"] == "not_run"
    assert blocked_depth["affected_argument_block_ids"] == []
    assert main(
        ["blueprint", "impact", *common, "--changed-id", "citation:leaf", "--changed-id", "foreign:unowned"]
    ) == 0
    blocked = json.loads(capsys.readouterr().out)
    assert blocked["partial_result_suppressed"] is True
    assert blocked["affected_argument_block_ids"] == []
    assert main(["blueprint", "trace", *common, "--artifact-unit-id", "unit:section"]) == 0
    blocked_trace = json.loads(capsys.readouterr().out)
    assert blocked_trace["query_status"] == "blocked"
    assert blocked_trace["artifact_unit"] == {}
    assert main(["blueprint", "export", *common, "--output", str(export_path)]) == 3
    exported_check = json.loads(export_path.read_text(encoding="utf-8"))["check"]
    assert exported_check["status"] == "incomplete"
    assert exported_check["native_depth_status"] == "not_run"


def test_reverse_trace_empty_output_chain_is_never_complete() -> None:
    model = _model()
    model.blocks["B_CHILD"].output_claims.clear()
    inventory = _inventory()
    trace = reverse_trace_artifact(model, inventory, _bindings(inventory), "unit:section")
    assert trace["trace_status"] == "incomplete"
    assert trace["partial_result_suppressed"] is True
    assert trace["output_claim_ids"] == []
    assert {item["code"] for item in trace["trace_gaps"]} >= {"model-validation"}


def test_blueprint_replays_current_native_depth_and_target_proof(tmp_path) -> None:
    contract, candidate = _prepare(tmp_path)
    model = load_model(candidate)
    unsigned = ArtifactInventory(
            inventory_id="inventory:current-model",
            source_revision="revision:current-model",
            root_unit_id="unit:central-argument",
            units=(
                ArtifactUnit(
                    "unit:central-argument",
                    "",
                    "models/current.json",
                    "sha256:" + "7" * 64,
                    required_resource_roles=(),
                ),
            ),
        )
    inventory = issue_artifact_inventory_authority(
        unsigned,
        expected_target_anchor=artifact_expected_target_anchor(unsigned),
    )
    bindings = (
        ArtifactRealizationBinding(
            "unit:central-argument",
            "B_MAIN",
            ("C0", "E1", "W1", "A1", "L1", "R1"),
            consumed_content_fingerprint="sha256:" + "7" * 64,
        ),
    )
    evidence = issue_logic_native_depth_evidence(
        model,
        inventory,
        bindings,
        target_root=str(tmp_path),
        guard_contract=str(contract),
        budget=8,
    )
    evidence = attach_logic_depth_receipt(model, inventory, bindings, evidence)
    result = check_blueprint(model, inventory, bindings, evidence)
    assert evidence.status == "current"
    assert result.status == "complete"
    assert result.native_depth_status == "current"
    assert result.native_depth_gaps == ()
    exported = export_blueprint(model, inventory, bindings, evidence)
    assert exported["check"]["status"] == "complete"
    assert exported["check"]["native_depth_status"] == "current"

    context_path = tmp_path / "logic-reverse-context.json"
    context_path.write_text(
        json.dumps(
            {
                "model_path": str(candidate),
                "inventory": inventory.to_dict(),
                "bindings": [item.to_dict() for item in bindings],
                "native_depth_evidence": evidence.to_dict(),
            }
        ),
        encoding="utf-8",
    )
    child = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            """
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path.cwd() / 'tests'))
from target_material_fixtures import install_test_expected_target_producer
install_test_expected_target_producer()
from admission_fixtures import install_test_native_receipt_producers
install_test_native_receipt_producers()
from researchguard.logic import (
    ArtifactInventory,
    ArtifactRealizationBinding,
    LogicNativeDepthEvidence,
    load_model,
    reverse_trace_artifact,
)

context = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
model = load_model(context['model_path'])
inventory = ArtifactInventory.from_dict(context['inventory'])
bindings = tuple(
    ArtifactRealizationBinding(
        artifact_unit_id=row['artifact_unit_id'],
        argument_block_id=row['argument_block_id'],
        node_ids=tuple(row['node_ids']),
        resource_ids=tuple(row['resource_ids']),
        disposition=row['disposition'],
        consumed_content_fingerprint=row['consumed_content_fingerprint'],
    )
    for row in context['bindings']
)
native_depth = LogicNativeDepthEvidence(**context['native_depth_evidence'])
trace = reverse_trace_artifact(
    model,
    inventory,
    bindings,
    'unit:central-argument',
    native_depth,
)
print(json.dumps({
    'query_status': trace['query_status'],
    'trace_status': trace['trace_status'],
    'artifact_unit_id': trace['artifact_unit']['unit_id'],
    'partial_result_suppressed': trace['partial_result_suppressed'],
}))
""",
            str(context_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        check=True,
        capture_output=True,
        text=True,
    )
    child_result = json.loads(child.stdout)
    assert child_result["query_status"] == "complete"
    assert child_result["trace_status"] == "complete"
    assert child_result["artifact_unit_id"] == "unit:central-argument"
    assert child_result["partial_result_suppressed"] is False

    stale = replace(evidence, status="stale")
    stale_result = check_blueprint(model, inventory, bindings, stale)
    assert stale_result.native_depth_status == "stale"
    assert any(item.code == "native-depth-not-current" for item in stale_result.native_depth_gaps)
