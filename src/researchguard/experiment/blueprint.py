"""Native ExperimentGuard design-blueprint projection and inspection."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from typing import Iterable, Literal, Mapping

from ..native_receipts import (
    NativeReceiptExpectation,
    native_receipt_expectation,
    resolve_expected_native_receipts,
)

from .schema import (
    EXPERIMENT_NATIVE_CASE_CHECK,
    EXPERIMENT_SPEC_SCHEMA,
    ExperimentChildOutputBinding,
    ExperimentDesignBlock,
    ExperimentNativeCaseEvidence,
    ExperimentSpec,
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

EXPERIMENT_BLUEPRINT_SCHEMA = "researchguard.experiment.design-blueprint.v1"
EXPERIMENT_TARGET_AUTHORITY_OWNER = "researchguard.experiment.target-purpose"
EXPERIMENT_TARGET_AUTHORITY_TOOL = "researchguard.experiment.target-universe"
EXPERIMENT_TARGET_ADAPTER_ID = "researchguard.experiment.target-material-adapter"
EXPERIMENT_TARGET_ADAPTER_VERSION = "2"
EXPERIMENT_TARGET_MATERIAL_SCHEMA = "researchguard.experiment.target-material.v1"
EXPERIMENT_CHILD_OUTPUT_REFINEMENT = "researchguard.experiment.refinement.exact-schema.v1"


def _digest(value: object) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(body.encode('utf-8')).hexdigest()}"


@dataclass(frozen=True)
class ExperimentBlueprintGap:
    code: str
    object_id: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentBlueprintResult:
    status: Literal["complete", "incomplete"]
    model_id: str
    model_fingerprint: str
    target_universe_fingerprint: str
    deepest_proven_layer: str
    first_unresolved_gap: str
    gaps: tuple[ExperimentBlueprintGap, ...]
    layer_statuses: tuple[dict[str, object], ...]
    external_execution_status: Literal["not_run"] = "not_run"
    claim_boundary: str = (
        "This blueprint validates the caller-declared experiment design and its binding to "
        "ExperimentGuard's finite recommendation matrix. It never executes an external experiment."
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": EXPERIMENT_BLUEPRINT_SCHEMA,
            "status": self.status,
            "model_id": self.model_id,
            "model_fingerprint": self.model_fingerprint,
            "target_universe_fingerprint": self.target_universe_fingerprint,
            "deepest_proven_layer": self.deepest_proven_layer,
            "first_unresolved_gap": self.first_unresolved_gap,
            "gaps": [item.to_dict() for item in self.gaps],
            "layer_statuses": list(self.layer_statuses),
            "external_execution_status": self.external_execution_status,
            "claim_boundary": self.claim_boundary,
        }


def blueprint_fingerprint(spec: ExperimentSpec) -> str:
    material = spec.to_dict()
    material.pop("prior_receipt_fingerprint", None)
    material.pop("prior_open_gap_ids", None)
    return _digest(material)


def experiment_design_subject_fingerprint(spec: ExperimentSpec) -> str:
    """Fingerprint the design under test without recursively including its case receipts."""

    material = spec.to_dict()
    universe = material.get("target_universe")
    if isinstance(universe, dict):
        universe = dict(universe)
        universe["native_case_evidence"] = []
        universe["native_receipt_refs"] = []
        material["target_universe"] = universe
    material.pop("prior_receipt_fingerprint", None)
    material.pop("prior_open_gap_ids", None)
    return _digest(material)


def prediction_matrix_fingerprint(spec: ExperimentSpec) -> str:
    return _digest(
        {
            "task_id": spec.task_id,
            "candidate_experiment_ids": list(spec.candidate_experiment_ids),
            "hypothesis_predictions": [item.to_dict() for item in spec.hypothesis_predictions],
        }
    )


def candidate_design_fingerprint(spec: ExperimentSpec) -> str:
    return _digest(
        [
            item.to_dict()
            for item in sorted(
                (block for block in spec.design_blocks if block.kind == "candidate_experiment"),
                key=lambda block: block.candidate_experiment_id,
            )
        ]
    )


def experiment_block_model_fingerprint(block: ExperimentDesignBlock) -> str:
    """Fingerprint one child producer without any parent-owned binding record."""

    return _digest(block.to_dict())


def child_output_payload_fingerprint(
    spec: ExperimentSpec, child_block_id: str, child_output_port_id: str
) -> str:
    blocks = {item.block_id: item for item in spec.design_blocks}
    child = blocks.get(child_block_id)
    if child is None:
        raise ValueError(f"unknown child block {child_block_id!r}")
    ports = {item.port_id: item for item in child.ports}
    port = ports.get(child_output_port_id)
    if port is None or port.kind not in {"observation", "outcome"}:
        raise ValueError(f"unknown child output port {child_output_port_id!r}")
    return _digest(
        {
            "task_id": spec.task_id,
            "child_block_id": child.block_id,
            "candidate_experiment_id": child.candidate_experiment_id,
            "output_port": port.to_dict(),
        }
    )


def child_output_result_fingerprint(
    spec: ExperimentSpec, child_block_id: str, child_output_port_id: str
) -> str:
    child = next(item for item in spec.design_blocks if item.block_id == child_block_id)
    return _digest(
        {
            "producer_model_fingerprint": experiment_block_model_fingerprint(child),
            "payload_fingerprint": child_output_payload_fingerprint(
                spec, child_block_id, child_output_port_id
            ),
        }
    )


def _build_child_output_binding(
    spec: ExperimentSpec,
    *,
    binding_id: str,
    child_block_id: str,
    child_output_port_id: str,
    parent_block_id: str,
    parent_input_port_id: str,
) -> ExperimentChildOutputBinding:
    """Build non-authoritative interface material for external receipt admission."""

    blocks = {item.block_id: item for item in spec.design_blocks}
    child = blocks.get(child_block_id)
    parent = blocks.get(parent_block_id)
    if child is None or parent is None or child.parent_id != parent.block_id:
        raise ValueError("child-output binding endpoints are not one direct parent/child edge")
    child_port = next(
        (item for item in child.ports if item.port_id == child_output_port_id), None
    )
    parent_port = next(
        (item for item in parent.ports if item.port_id == parent_input_port_id), None
    )
    if child_port is None or child_port.kind not in {"observation", "outcome"}:
        raise ValueError("child-output binding producer must be an observation or outcome port")
    if parent_port is None or parent_port.kind != "input":
        raise ValueError("child-output binding consumer must be a parent input port")
    if child_port.schema_id != parent_port.schema_id:
        raise ValueError("child-output binding endpoints require exact schema refinement")
    payload = child_output_payload_fingerprint(spec, child_block_id, child_output_port_id)
    model = experiment_block_model_fingerprint(child)
    result = child_output_result_fingerprint(spec, child_block_id, child_output_port_id)
    receipt = ExperimentChildOutputBinding(
        binding_id=binding_id,
        child_block_id=child_block_id,
        child_output_port_id=child_output_port_id,
        parent_block_id=parent_block_id,
        parent_input_port_id=parent_input_port_id,
        payload_schema_id=child_port.schema_id,
        refinement_id=EXPERIMENT_CHILD_OUTPUT_REFINEMENT,
        payload_fingerprint=payload,
        producer_model_fingerprint=model,
        producer_result_fingerprint=result,
        producer_task_id=spec.task_id,
        receipt_id=f"experiment-child-output:{spec.task_id}:{binding_id}",
        receipt_fingerprint="sha256:" + "0" * 64,
        receipt_status="current",
    )
    return replace(receipt, receipt_fingerprint=receipt.expected_receipt_fingerprint)


def target_request_fingerprint(spec: ExperimentSpec) -> str:
    return _digest(
        {
            "task_id": spec.task_id,
            "purpose": spec.purpose,
            "coverage_ids": list(spec.coverage_ids),
            "assumptions": list(spec.assumptions),
            "unknowns": list(spec.unknowns),
        }
    )


def target_purpose_fingerprint(spec: ExperimentSpec) -> str:
    return _digest({"task_id": spec.task_id, "purpose": spec.purpose})


def _experiment_target_inventory(spec: ExperimentSpec) -> dict[str, object]:
    universe = spec.target_universe
    if universe is None:
        raise ValueError("ExperimentGuard target material requires a target universe")
    return {
        "hypothesis_ids": sorted(item.hypothesis_id for item in spec.hypothesis_predictions),
        "discrimination_ids": sorted(
            item.block_id for item in spec.design_blocks if item.kind == "discrimination_obligation"
        ),
        "candidate_ids": sorted(
            item.candidate_experiment_id
            for item in spec.design_blocks
            if item.candidate_experiment_id
        ),
        "port_ids": sorted(port.port_id for item in spec.design_blocks for port in item.ports),
        "procedure_step_ids": sorted(
            step.step_id for item in spec.design_blocks for step in item.procedure_steps
        ),
        "constraint_ids": sorted(
            constraint.constraint_id
            for item in spec.design_blocks
            for constraint in item.constraints
        ),
        "input_binding_ids": sorted(
            binding.binding_id
            for item in spec.design_blocks
            for binding in item.input_bindings
        ),
        "child_output_binding_ids": sorted(
            binding.binding_id
            for item in spec.design_blocks
            for binding in item.child_output_bindings
        ),
        "known_good_case_ids": sorted(universe.known_good_case_ids),
        "known_bad_case_ids": sorted(universe.known_bad_case_ids),
        "failure_class_ids": ["missing-observation-port"],
    }


def _noncurrent_experiment_replay(
    spec: ExperimentSpec,
    locator: str,
    status: Literal["unverified", "failed"],
    detail: str,
) -> NativeTargetMaterialReplay:
    marker = _digest({"locator": locator, "status": status})
    request_fingerprint = target_request_fingerprint(spec)
    target_fingerprint = _digest(_experiment_target_inventory(spec))
    return NativeTargetMaterialReplay(
        adapter_id=EXPERIMENT_TARGET_ADAPTER_ID,
        adapter_version=EXPERIMENT_TARGET_ADAPTER_VERSION,
        request_id=content_addressed_request_id(request_fingerprint),
        request_fingerprint=request_fingerprint,
        input_id=locator or "unreplayable:experiment-target-material",
        input_fingerprint=marker,
        target_id=spec.task_id,
        target_revision=target_fingerprint,
        target_fingerprint=target_fingerprint,
        purpose_fingerprint=target_purpose_fingerprint(spec),
        material_locator=locator or "unreplayable:experiment-target-material",
        material_media_type="application/json",
        material_fingerprint=marker,
        items=(),
        status=status,
        detail=detail,
    )


def replay_experiment_target_material(
    spec: ExperimentSpec, locator: str
) -> NativeTargetMaterialReplay:
    """ExperimentGuard-owned parser for exact raw design target material."""

    body, material_fingerprint, gap = read_target_material_bytes(locator)
    if body is None:
        return _noncurrent_experiment_replay(spec, locator, "unverified", gap)
    try:
        raw = json.loads(body.decode("utf-8"))
        if not isinstance(raw, Mapping) or set(raw) != {
            "schema_version", "request_contract", "target_id", "target_revision",
            "target_inventory",
        }:
            raise ValueError("experiment target material has an unknown or missing root field")
        if raw.get("schema_version") != EXPERIMENT_TARGET_MATERIAL_SCHEMA:
            raise ValueError("experiment target material schema is not current")
        request = raw.get("request_contract")
        inventory = raw.get("target_inventory")
        if not isinstance(request, Mapping) or set(request) != {
            "request_id", "task_id", "purpose", "coverage_ids", "assumptions", "unknowns",
        }:
            raise ValueError("experiment request contract is not exact-current")
        inventory_keys = {
            "hypothesis_ids", "discrimination_ids", "candidate_ids", "port_ids",
            "procedure_step_ids", "constraint_ids", "input_binding_ids",
            "child_output_binding_ids", "known_good_case_ids", "known_bad_case_ids",
            "failure_class_ids",
        }
        if not isinstance(inventory, Mapping) or set(inventory) != inventory_keys:
            raise ValueError("experiment target inventory is not exact-current")
        for key in inventory_keys:
            values = inventory.get(key)
            if not isinstance(values, list) or any(not str(value).strip() for value in values):
                raise ValueError(f"experiment target inventory {key} must be non-empty-string ids")
            if len(values) != len(set(str(value) for value in values)):
                raise ValueError(f"experiment target inventory {key} contains duplicate ids")
        request_material = {
            "task_id": str(request["task_id"]),
            "purpose": str(request["purpose"]),
            "coverage_ids": [str(value) for value in request["coverage_ids"]],
            "assumptions": [str(value) for value in request["assumptions"]],
            "unknowns": [str(value) for value in request["unknowns"]],
        }
        kind_keys = (
            ("hypothesis", "hypothesis_ids"),
            ("discrimination", "discrimination_ids"),
            ("candidate", "candidate_ids"),
            ("port", "port_ids"),
            ("procedure-step", "procedure_step_ids"),
            ("constraint", "constraint_ids"),
            ("input-binding", "input_binding_ids"),
            ("child-output-binding", "child_output_binding_ids"),
            ("known-good-case", "known_good_case_ids"),
            ("known-bad-case", "known_bad_case_ids"),
            ("failure-class", "failure_class_ids"),
        )
        items = tuple(
            TargetAuthorityItem(kind, str(object_id), "required")
            for kind, key in kind_keys
            for object_id in inventory[key]
        )
        request_fingerprint = _digest(request_material)
        target_fingerprint = _digest(dict(inventory))
        return NativeTargetMaterialReplay(
            adapter_id=EXPERIMENT_TARGET_ADAPTER_ID,
            adapter_version=EXPERIMENT_TARGET_ADAPTER_VERSION,
            request_id=str(request["request_id"]),
            request_fingerprint=request_fingerprint,
            input_id=locator,
            input_fingerprint=material_fingerprint,
            target_id=str(raw["target_id"]),
            target_revision=str(raw["target_revision"]),
            target_fingerprint=target_fingerprint,
            purpose_fingerprint=_digest(
                {"task_id": str(request["task_id"]), "purpose": str(request["purpose"])}
            ),
            material_locator=locator,
            material_media_type="application/json",
            material_fingerprint=material_fingerprint,
            items=items,
            status="current",
        )
    except Exception as exc:
        return _noncurrent_experiment_replay(spec, locator, "failed", str(exc))


def _bind_experiment_target_authority(
    spec: ExperimentSpec, *, expected_target_anchor: ExpectedTargetAnchor
) -> ExperimentSpec:
    """Replay only the externally admitted ExperimentGuard target bytes."""

    universe = spec.target_universe
    if universe is None:
        raise ValueError("ExperimentGuard target authority requires a target universe")
    replay = replay_experiment_target_material(spec, expected_target_anchor.material_locator)
    authority = _issue_replayed_target_authority(
        member_id="experimentguard",
        owner_id=EXPERIMENT_TARGET_AUTHORITY_OWNER,
        tool_id=EXPERIMENT_TARGET_AUTHORITY_TOOL,
        tool_revision="1",
        expected_target_anchor=expected_target_anchor,
        replay=replay,
    )
    return replace(spec, target_universe=replace(universe, target_authority=authority))


def _native_case_execution(
    spec: ExperimentSpec, case_kind: str, failure_class_id: str
) -> dict[str, object]:
    """Run one fixed native blueprint/recommendation case against current code."""

    if case_kind == "known_good" and failure_class_id == "valid-design":
        fixture_id = "current-design"
        case_spec = spec
    elif case_kind == "known_bad" and failure_class_id == "missing-observation-port":
        fixture_id = "missing-first-observation-port"
        blocks = list(spec.design_blocks)
        candidate_index = next(
            (index for index, block in enumerate(blocks) if block.kind == "candidate_experiment"),
            None,
        )
        if candidate_index is None:
            case_spec = spec
        else:
            candidate = blocks[candidate_index]
            blocks[candidate_index] = replace(
                candidate,
                ports=tuple(port for port in candidate.ports if port.kind != "observation"),
            )
            case_spec = replace(spec, design_blocks=tuple(blocks))
    else:
        raise ValueError(
            f"unknown experiment native case/failure class: {case_kind!r}/{failure_class_id!r}"
        )
    native_gaps = validate_design_identities(case_spec)
    from .engine import recommend_experiments

    recommendation = recommend_experiments(case_spec)
    if case_kind == "known_good":
        terminal = "passed" if not native_gaps and recommendation.status != "blocked_invalid_input" else "rejected"
    else:
        terminal = "rejected" if native_gaps and recommendation.status == "blocked_invalid_input" else "passed"
    fixture_fingerprint = _digest(
        {
            "fixture_id": fixture_id,
            "subject_model_fingerprint": experiment_design_subject_fingerprint(spec),
        }
    )
    result_payload = {
        "fixture_id": fixture_id,
        "terminal": terminal,
        "gaps": [item.to_dict() for item in native_gaps],
        "recommendation": recommendation.to_dict(),
    }
    return {
        "fixture_id": fixture_id,
        "fixture_fingerprint": fixture_fingerprint,
        "terminal": terminal,
        "result_fingerprint": _digest(result_payload),
    }


def _run_native_case_evidence(
    spec: ExperimentSpec,
    *,
    case_id: str,
    case_kind: Literal["known_good", "known_bad"],
) -> ExperimentNativeCaseEvidence:
    """Execute fixed case material; external immutable admission is separate."""

    authority = spec.target_universe.target_authority if spec.target_universe else None
    if authority is None:
        raise ValueError("experiment native case evidence requires an independent target authority")
    failure_class_id = "valid-design"
    if case_kind == "known_bad":
        failure_classes = sorted(authority.ids("failure-class"))
        if len(failure_classes) != 1:
            raise ValueError("experiment known-bad evidence requires exactly one target-owned failure class")
        failure_class_id = failure_classes[0]
    execution = _native_case_execution(spec, case_kind, failure_class_id)
    expected_terminal = "passed" if case_kind == "known_good" else "rejected"
    evidence = ExperimentNativeCaseEvidence(
        case_id=case_id,
        case_kind=case_kind,
        owner_id="researchguard.experiment",
        native_check_id=EXPERIMENT_NATIVE_CASE_CHECK,
        task_id=spec.task_id,
        subject_model_fingerprint=experiment_design_subject_fingerprint(spec),
        prediction_matrix_fingerprint=prediction_matrix_fingerprint(spec),
        candidate_design_fingerprint=candidate_design_fingerprint(spec),
        target_authority_fingerprint=authority.authority_fingerprint,
        failure_class_id=failure_class_id,
        case_input_fingerprint=str(execution["fixture_fingerprint"]),
        expected_terminal=expected_terminal,
        observed_terminal=str(execution["terminal"]),
        oracle_id="experiment-blueprint-validation",
        result_fingerprint=str(execution["result_fingerprint"]),
        receipt_id=f"experiment-native-case:{spec.task_id}:{case_id}",
        receipt_fingerprint="sha256:" + "0" * 64,
        status="current",
    )
    return replace(evidence, receipt_fingerprint=evidence.expected_receipt_fingerprint)


def target_universe_fingerprint(spec: ExperimentSpec) -> str:
    return _digest(spec.target_universe.to_dict() if spec.target_universe else {})


def _hierarchy_gaps(spec: ExperimentSpec) -> list[ExperimentBlueprintGap]:
    gaps: list[ExperimentBlueprintGap] = []
    blocks = {item.block_id: item for item in spec.design_blocks}
    roots = sorted(item.block_id for item in spec.design_blocks if not item.parent_id)
    if roots != [spec.design_root_id]:
        gaps.append(ExperimentBlueprintGap("invalid-root", spec.design_root_id, f"roots={roots}"))
    parents: dict[str, str] = {}
    for block in spec.design_blocks:
        if block.parent_id and block.parent_id not in blocks:
            gaps.append(ExperimentBlueprintGap("missing-parent", block.block_id, block.parent_id))
        for child_id in block.child_ids:
            if child_id not in blocks:
                gaps.append(ExperimentBlueprintGap("missing-child", block.block_id, child_id))
                continue
            prior = parents.setdefault(child_id, block.block_id)
            if prior != block.block_id:
                gaps.append(ExperimentBlueprintGap("multiple-parents", child_id, f"{prior},{block.block_id}"))
            if blocks[child_id].parent_id != block.block_id:
                gaps.append(ExperimentBlueprintGap("parent-child-mismatch", child_id, block.block_id))
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(block_id: str) -> None:
        if block_id in visiting:
            gaps.append(ExperimentBlueprintGap("cycle", block_id, "hierarchy is cyclic"))
            return
        if block_id in visited or block_id not in blocks:
            return
        visiting.add(block_id)
        for child_id in blocks[block_id].child_ids:
            visit(child_id)
        visiting.remove(block_id)
        visited.add(block_id)

    if spec.design_root_id:
        visit(spec.design_root_id)
    for missing_id in sorted(set(blocks) - visited):
        gaps.append(ExperimentBlueprintGap("unreachable-block", missing_id, "not reachable from root"))
    return gaps


def _candidate_gaps(spec: ExperimentSpec) -> list[ExperimentBlueprintGap]:
    gaps: list[ExperimentBlueprintGap] = []
    blocks_by_id = {item.block_id: item for item in spec.design_blocks}
    candidates = {
        item.candidate_experiment_id: item
        for item in spec.design_blocks
        if item.kind == "candidate_experiment"
    }
    for candidate_id in spec.candidate_experiment_ids:
        block = candidates.get(candidate_id)
        if block is None:
            gaps.append(ExperimentBlueprintGap("missing-candidate-block", candidate_id, "matrix candidate has no design block"))
            continue
        ports = {item.port_id: item for item in block.ports}
        kinds = {item.kind for item in block.ports}
        for required_kind in ("input", "manipulation", "observation", "outcome"):
            if required_kind not in kinds:
                gaps.append(ExperimentBlueprintGap(f"missing-{required_kind}-port", candidate_id, required_kind))
        input_ports = {
            item.port_id: item
            for item in block.ports
            if item.kind in {"input", "manipulation"}
        }
        bindings_by_port: dict[str, list[object]] = {}
        for binding in block.input_bindings:
            bindings_by_port.setdefault(binding.consumer_port_id, []).append(binding)
            port = input_ports.get(binding.consumer_port_id)
            if port is None:
                gaps.append(ExperimentBlueprintGap("foreign-input-binding", binding.binding_id, binding.consumer_port_id))
                continue
            if binding.payload_schema_id != port.schema_id:
                gaps.append(ExperimentBlueprintGap("input-schema-mismatch", binding.binding_id, f"{binding.payload_schema_id}!={port.schema_id}"))
            if binding.producer_kind in {"parent", "sibling"}:
                producer = blocks_by_id.get(binding.producer_id)
                producer_ports = {item.port_id: item for item in producer.ports} if producer else {}
                producer_port = producer_ports.get(binding.producer_port_id)
                if producer is None or producer_port is None:
                    gaps.append(ExperimentBlueprintGap("missing-input-producer", binding.binding_id, f"{binding.producer_id}/{binding.producer_port_id}"))
                elif producer_port.schema_id != port.schema_id:
                    gaps.append(ExperimentBlueprintGap("producer-schema-mismatch", binding.binding_id, producer_port.schema_id))
                if binding.producer_kind == "parent" and block.parent_id != binding.producer_id:
                    gaps.append(ExperimentBlueprintGap("foreign-parent-input-producer", binding.binding_id, binding.producer_id))
                if binding.producer_kind == "sibling" and (producer is None or producer.parent_id != block.parent_id):
                    gaps.append(ExperimentBlueprintGap("foreign-sibling-input-producer", binding.binding_id, binding.producer_id))
        for port_id in sorted(input_ports):
            matches = bindings_by_port.get(port_id, [])
            if len(matches) != 1:
                gaps.append(ExperimentBlueprintGap("missing-input-binding" if not matches else "duplicate-input-binding", candidate_id, port_id))
        if not block.procedure_steps:
            gaps.append(ExperimentBlueprintGap("missing-procedure", candidate_id, "no ordered procedure steps"))
        if not block.external_execution_owner:
            gaps.append(ExperimentBlueprintGap("missing-external-owner", candidate_id, "external execution owner required"))
        if len({item.order for item in block.procedure_steps}) != len(block.procedure_steps):
            gaps.append(ExperimentBlueprintGap("duplicate-step-order", candidate_id, "procedure orders must be unique"))
        consumed_entry_ports: set[str] = set()
        produced_result_ports: dict[str, int] = {}
        available_result_ports: set[str] = set()
        for step in sorted(block.procedure_steps, key=lambda item: (item.order, item.step_id)):
            for port_id in (*step.input_port_ids, *step.output_port_ids):
                if port_id not in ports:
                    gaps.append(ExperimentBlueprintGap("unknown-step-port", step.step_id, port_id))
            for port_id in step.input_port_ids:
                port = ports.get(port_id)
                if port is None:
                    continue
                if port.kind in {"input", "manipulation"}:
                    consumed_entry_ports.add(port_id)
                elif port_id not in available_result_ports:
                    gaps.append(
                        ExperimentBlueprintGap(
                            "procedure-input-before-production",
                            step.step_id,
                            port_id,
                        )
                    )
            for port_id in step.output_port_ids:
                port = ports.get(port_id)
                if port is None:
                    continue
                if port.kind not in {"observation", "outcome"}:
                    gaps.append(
                        ExperimentBlueprintGap(
                            "procedure-output-kind-mismatch",
                            step.step_id,
                            f"{port_id}:{port.kind}",
                        )
                    )
                    continue
                produced_result_ports[port_id] = produced_result_ports.get(port_id, 0) + 1
                available_result_ports.add(port_id)
        for port_id in sorted(set(input_ports) - consumed_entry_ports):
            gaps.append(
                ExperimentBlueprintGap(
                    "unconsumed-procedure-input",
                    candidate_id,
                    port_id,
                )
            )
        result_ports = {
            port_id
            for port_id, port in ports.items()
            if port.kind in {"observation", "outcome"}
        }
        for port_id in sorted(result_ports):
            producer_count = produced_result_ports.get(port_id, 0)
            if producer_count == 0:
                gaps.append(
                    ExperimentBlueprintGap(
                        "unproduced-procedure-output",
                        candidate_id,
                        port_id,
                    )
                )
            elif producer_count > 1:
                gaps.append(
                    ExperimentBlueprintGap(
                        "duplicate-procedure-output-producer",
                        candidate_id,
                        f"{port_id}:{producer_count}",
                    )
                )
        for row in spec.hypothesis_predictions:
            observation_port = (row.observation_port_by_experiment or {}).get(candidate_id, "")
            outcome_port = (row.outcome_port_by_experiment or {}).get(candidate_id, "")
            if observation_port not in ports or ports[observation_port].kind != "observation":
                gaps.append(ExperimentBlueprintGap("matrix-observation-port-mismatch", row.hypothesis_id, candidate_id))
            if outcome_port not in ports or ports[outcome_port].kind != "outcome":
                gaps.append(ExperimentBlueprintGap("matrix-outcome-port-mismatch", row.hypothesis_id, candidate_id))
            elif ports[outcome_port].allowed_values and row.outcomes_by_experiment[candidate_id] not in ports[outcome_port].allowed_values:
                gaps.append(ExperimentBlueprintGap("matrix-outcome-value-mismatch", row.hypothesis_id, candidate_id))
    for parent in spec.design_blocks:
        produced = {
            port.port_id
            for child_id in parent.child_ids
            if child_id in blocks_by_id
            for port in blocks_by_id[child_id].ports
            if port.kind in {"observation", "outcome"}
        }
        dispositions: set[str] = set()
        bindings_by_child_port: dict[str, list[ExperimentChildOutputBinding]] = {}
        bindings_by_parent_port: dict[str, list[ExperimentChildOutputBinding]] = {}
        for binding in parent.child_output_bindings:
            bindings_by_child_port.setdefault(binding.child_output_port_id, []).append(binding)
            bindings_by_parent_port.setdefault(binding.parent_input_port_id, []).append(binding)
            child = blocks_by_id.get(binding.child_block_id)
            child_ports = {item.port_id: item for item in child.ports} if child else {}
            child_port = child_ports.get(binding.child_output_port_id)
            parent_ports = {item.port_id: item for item in parent.ports}
            parent_port = parent_ports.get(binding.parent_input_port_id)
            checks = (
                (binding.parent_block_id == parent.block_id, "child-output-parent-mismatch", binding.parent_block_id),
                (child is not None and child.block_id in parent.child_ids, "child-output-foreign-child", binding.child_block_id),
                (child is not None and child.parent_id == parent.block_id, "child-output-parent-child-mismatch", binding.child_block_id),
                (child_port is not None and child_port.kind in {"observation", "outcome"}, "child-output-producer-port-mismatch", binding.child_output_port_id),
                (parent_port is not None and parent_port.kind == "input", "child-output-parent-input-mismatch", binding.parent_input_port_id),
                (child_port is not None and binding.payload_schema_id == child_port.schema_id, "child-output-schema-mismatch", binding.payload_schema_id),
                (parent_port is not None and binding.payload_schema_id == parent_port.schema_id, "child-output-refinement-schema-mismatch", binding.payload_schema_id),
                (binding.refinement_id == EXPERIMENT_CHILD_OUTPUT_REFINEMENT, "child-output-refinement-mismatch", binding.refinement_id),
                (binding.producer_task_id == spec.task_id, "child-output-task-mismatch", binding.producer_task_id),
                (binding.receipt_status == "current", "child-output-receipt-not-current", binding.receipt_status),
                (binding.receipt_fingerprint == binding.expected_receipt_fingerprint, "child-output-receipt-mismatch", binding.receipt_id),
            )
            if child is not None and child_port is not None and child_port.kind in {"observation", "outcome"}:
                expected_payload = child_output_payload_fingerprint(
                    spec, child.block_id, child_port.port_id
                )
                expected_model = experiment_block_model_fingerprint(child)
                expected_result = child_output_result_fingerprint(
                    spec, child.block_id, child_port.port_id
                )
                derived_checks = (
                    (binding.payload_fingerprint == expected_payload, "child-output-payload-stale", binding.payload_fingerprint),
                    (binding.producer_model_fingerprint == expected_model, "child-output-model-stale", binding.producer_model_fingerprint),
                    (binding.producer_result_fingerprint == expected_result, "child-output-result-stale", binding.producer_result_fingerprint),
                )
            else:
                derived_checks = ()
            for ok, code, detail in (*checks, *derived_checks):
                if not ok:
                    gaps.append(ExperimentBlueprintGap(code, binding.binding_id, detail))
        for item in parent.output_dispositions:
            if len(item) != 2 or item[1] not in {"unresolved", "excluded", "terminal"}:
                gaps.append(
                    ExperimentBlueprintGap(
                        "invalid-output-disposition",
                        parent.block_id,
                        repr(item),
                    )
                )
                continue
            port_id, _disposition = item
            if port_id not in produced:
                gaps.append(
                    ExperimentBlueprintGap(
                        "foreign-output-disposition",
                        parent.block_id,
                        port_id,
                    )
                )
                continue
            dispositions.add(port_id)
        for port_id in sorted(set(parent.consumed_child_output_port_ids) - produced):
            gaps.append(
                ExperimentBlueprintGap(
                    "foreign-consumed-child-output",
                    parent.block_id,
                    port_id,
                )
            )
        for port_id in sorted(set(parent.consumed_child_output_port_ids) & produced):
            matches = bindings_by_child_port.get(port_id, [])
            if len(matches) != 1:
                gaps.append(
                    ExperimentBlueprintGap(
                        "missing-child-output-binding" if not matches else "duplicate-child-output-binding",
                        parent.block_id,
                        port_id,
                    )
                )
        parent_input_ids = (
            {item.port_id for item in parent.ports if item.kind == "input"}
            if parent.child_ids
            else set()
        )
        for port_id in sorted(parent_input_ids):
            matches = bindings_by_parent_port.get(port_id, [])
            if len(matches) != 1:
                gaps.append(
                    ExperimentBlueprintGap(
                        "unbound-parent-input" if not matches else "duplicate-parent-input-binding",
                        parent.block_id,
                        port_id,
                    )
                )
        for port_id in sorted(set(bindings_by_parent_port) - parent_input_ids):
            gaps.append(ExperimentBlueprintGap("foreign-parent-input-binding", parent.block_id, port_id))
        for port_id in sorted(produced - set(parent.consumed_child_output_port_ids) - dispositions):
            gaps.append(ExperimentBlueprintGap("unconsumed-child-output", parent.block_id, port_id))
    return gaps


def _universe_gaps(spec: ExperimentSpec) -> list[ExperimentBlueprintGap]:
    if spec.target_universe is None:
        return [ExperimentBlueprintGap("missing-target-universe", spec.task_id, "independent target universe required")]
    universe = spec.target_universe
    block_candidates = {item.candidate_experiment_id for item in spec.design_blocks if item.candidate_experiment_id}
    ports = {port.port_id for item in spec.design_blocks for port in item.ports}
    procedure_steps = {step.step_id for item in spec.design_blocks for step in item.procedure_steps}
    constraints = {constraint.constraint_id for item in spec.design_blocks for constraint in item.constraints}
    input_bindings = {binding.binding_id for item in spec.design_blocks for binding in item.input_bindings}
    child_output_bindings = {
        binding.binding_id for item in spec.design_blocks for binding in item.child_output_bindings
    }
    hypotheses = {item.hypothesis_id for item in spec.hypothesis_predictions}
    discrimination = {item.block_id for item in spec.design_blocks if item.kind == "discrimination_obligation"}
    gaps: list[ExperimentBlueprintGap] = []
    authority = universe.target_authority
    if authority is None:
        gaps.append(
            ExperimentBlueprintGap(
                "missing-target-purpose-authority",
                universe.universe_id,
                "independent owner/request/input/target/tool authority required",
            )
        )
    else:
        identity_checks = (
            (authority.member_id == "experimentguard", "target-authority-member-mismatch", authority.member_id),
            (authority.owner_id == EXPERIMENT_TARGET_AUTHORITY_OWNER, "target-authority-owner-mismatch", authority.owner_id),
            (authority.tool_id == EXPERIMENT_TARGET_AUTHORITY_TOOL, "target-authority-tool-mismatch", authority.tool_id),
            (authority.target_id == spec.task_id, "target-authority-target-mismatch", authority.target_id),
            (authority.target_revision == authority.target_fingerprint, "target-authority-revision-mismatch", authority.target_revision),
            (authority.request_fingerprint == target_request_fingerprint(spec), "target-authority-request-stale", authority.request_fingerprint),
            (
                authority.target_fingerprint == _digest(_experiment_target_inventory(spec)),
                "target-authority-target-stale",
                authority.target_fingerprint,
            ),
            (authority.purpose_fingerprint == target_purpose_fingerprint(spec), "target-authority-purpose-stale", authority.purpose_fingerprint),
            (authority.status == "current", "target-authority-not-current", authority.status),
            (authority.authority_fingerprint == authority.expected_fingerprint, "target-authority-fingerprint-mismatch", authority.authority_id),
        )
        for ok, code, detail in identity_checks:
            if not ok:
                gaps.append(ExperimentBlueprintGap(code, universe.universe_id, detail))
        for item in authority.unresolved_items:
            gaps.append(ExperimentBlueprintGap("target-authority-unresolved", item.object_id, item.reason))
        replay = replay_experiment_target_material(
            spec,
            authority.expected_target_anchor.material_locator
            if authority.native_attestation is not None
            else "",
        )
        for code, detail in verify_registered_target_authority(authority, replay):
            gaps.append(ExperimentBlueprintGap(code, universe.universe_id, detail))
    for kind, required, actual in (
        ("hypothesis", set(universe.required_hypothesis_ids), hypotheses),
        ("discrimination", set(universe.required_discrimination_ids), discrimination),
        ("candidate", set(universe.required_candidate_ids), block_candidates),
        ("port", set(universe.required_port_ids), ports),
        ("procedure-step", set(universe.required_procedure_step_ids), procedure_steps),
        ("constraint", set(universe.required_constraint_ids), constraints),
        ("input-binding", set(universe.required_input_binding_ids), input_bindings),
        ("child-output-binding", set(universe.required_child_output_binding_ids), child_output_bindings),
    ):
        if authority is not None:
            authoritative = authority.ids(kind)
            for object_id in sorted(authoritative - set(required)):
                gaps.append(ExperimentBlueprintGap(f"target-authority-omitted-{kind}", object_id, "missing from member universe"))
            for object_id in sorted(set(required) - authoritative):
                gaps.append(ExperimentBlueprintGap(f"target-authority-foreign-{kind}", object_id, "not owned by target authority"))
            for object_id in sorted(authority.ids(kind, "excluded") & set(actual)):
                gaps.append(ExperimentBlueprintGap(f"target-authority-excluded-{kind}", object_id, "excluded target item is present"))
        for object_id in sorted(required - actual):
            gaps.append(ExperimentBlueprintGap(f"omitted-universe-{kind}", object_id, "required by independent universe"))
        for object_id in sorted(actual - required):
            gaps.append(ExperimentBlueprintGap(f"undeclared-universe-{kind}", object_id, "current model object is absent from independent universe"))
    if not universe.known_good_case_ids:
        gaps.append(ExperimentBlueprintGap("missing-known-good", spec.task_id, "purpose needs a native good case"))
    if not universe.known_bad_case_ids:
        gaps.append(ExperimentBlueprintGap("missing-known-bad", spec.task_id, "purpose needs a native bad case"))
    if authority is not None:
        for kind, declared in (
            ("known-good-case", set(universe.known_good_case_ids)),
            ("known-bad-case", set(universe.known_bad_case_ids)),
        ):
            authoritative = authority.ids(kind)
            for object_id in sorted(authoritative - declared):
                gaps.append(ExperimentBlueprintGap(f"target-authority-omitted-{kind}", object_id, "missing from member universe"))
            for object_id in sorted(declared - authoritative):
                gaps.append(ExperimentBlueprintGap(f"target-authority-foreign-{kind}", object_id, "not owned by target authority"))
        if not authority.ids("failure-class"):
            gaps.append(ExperimentBlueprintGap("missing-target-failure-class", spec.task_id, "target owner declared no protected failure class"))
    return gaps


def _native_case_gaps(spec: ExperimentSpec) -> list[ExperimentBlueprintGap]:
    if spec.target_universe is None:
        return []
    universe = spec.target_universe
    evidence = {item.case_id: item for item in universe.native_case_evidence}
    gaps: list[ExperimentBlueprintGap] = []
    expected_ids = set(universe.known_good_case_ids) | set(universe.known_bad_case_ids)
    for case_id in sorted(expected_ids - set(evidence)):
        gaps.append(ExperimentBlueprintGap("missing-native-case-evidence", case_id, "case id has no current native receipt"))
    for case_id in sorted(set(evidence) - expected_ids):
        gaps.append(ExperimentBlueprintGap("foreign-native-case-evidence", case_id, "receipt is outside the independent case universe"))
    subject = experiment_design_subject_fingerprint(spec)
    matrix = prediction_matrix_fingerprint(spec)
    candidates = candidate_design_fingerprint(spec)
    authority = universe.target_authority
    for case_id in sorted(expected_ids & set(evidence)):
        item = evidence[case_id]
        expected_kind = "known_good" if case_id in universe.known_good_case_ids else "known_bad"
        expected_terminal = "passed" if expected_kind == "known_good" else "rejected"
        failure_class_id = item.failure_class_id
        expected_failure_class = (
            "valid-design"
            if expected_kind == "known_good"
            else (next(iter(sorted(authority.ids("failure-class"))), "") if authority else "")
        )
        try:
            execution = _native_case_execution(spec, expected_kind, failure_class_id)
        except ValueError as exc:
            gaps.append(ExperimentBlueprintGap("native-case-failure-class-mismatch", case_id, str(exc)))
            continue
        checks = (
            (item.case_kind == expected_kind, "native-case-kind-mismatch", f"expected {expected_kind}"),
            (item.owner_id == "researchguard.experiment", "native-case-owner-mismatch", item.owner_id),
            (item.native_check_id == EXPERIMENT_NATIVE_CASE_CHECK, "native-case-check-mismatch", item.native_check_id),
            (item.task_id == spec.task_id, "native-case-task-mismatch", item.task_id),
            (item.subject_model_fingerprint == subject, "stale-native-case-subject", item.subject_model_fingerprint),
            (item.prediction_matrix_fingerprint == matrix, "stale-native-case-matrix", item.prediction_matrix_fingerprint),
            (item.candidate_design_fingerprint == candidates, "stale-native-case-candidates", item.candidate_design_fingerprint),
            (authority is not None and item.target_authority_fingerprint == authority.authority_fingerprint, "stale-native-case-target-authority", item.target_authority_fingerprint),
            (failure_class_id == expected_failure_class, "native-case-failure-class-mismatch", failure_class_id),
            (item.case_input_fingerprint == execution["fixture_fingerprint"], "native-case-input-mismatch", item.case_input_fingerprint),
            (item.expected_terminal == expected_terminal, "native-case-oracle-mismatch", item.expected_terminal),
            (item.observed_terminal == execution["terminal"], "native-case-terminal-mismatch", item.observed_terminal),
            (item.result_fingerprint == execution["result_fingerprint"], "native-case-result-mismatch", item.result_fingerprint),
            (item.oracle_id == "experiment-blueprint-validation", "native-case-oracle-owner-mismatch", item.oracle_id),
            (item.status == "current", "native-case-not-current", item.status),
            (item.receipt_fingerprint == item.expected_receipt_fingerprint, "native-case-receipt-mismatch", item.receipt_id),
        )
        for ok, code, detail in checks:
            if not ok:
                gaps.append(ExperimentBlueprintGap(code, case_id, detail))
    return gaps


def _native_receipt_gaps(spec: ExperimentSpec) -> list[ExperimentBlueprintGap]:
    universe = spec.target_universe
    authority = universe.target_authority if universe else None
    if universe is None or authority is None:
        return []
    anchor = authority.expected_target_anchor
    expectations: list[NativeReceiptExpectation] = []
    for block in spec.design_blocks:
        for binding in block.child_output_bindings:
            expectations.append(
                native_receipt_expectation(
                    receipt_id=binding.receipt_id,
                    member_id="experimentguard",
                    native_owner_id="experimentguard.child-output-interface",
                    checker_id="researchguard.experiment.child-output-binding",
                    checker_version="1",
                    checker_entrypoint="researchguard.experiment.blueprint:_candidate_gaps",
                    task_id=spec.task_id,
                    expected_target_anchor_id=anchor.anchor_id,
                    expected_target_anchor_fingerprint=anchor.anchor_fingerprint,
                    native_model_id=binding.child_block_id,
                    model_fingerprint=binding.producer_model_fingerprint,
                    request_fingerprint=_digest(
                        {
                            "task_id": spec.task_id,
                            "binding_id": binding.binding_id,
                            "parent_block_id": binding.parent_block_id,
                            "parent_input_port_id": binding.parent_input_port_id,
                            "payload_schema_id": binding.payload_schema_id,
                            "refinement_id": binding.refinement_id,
                            "expected_target_anchor_id": anchor.anchor_id,
                        }
                    ),
                    input_fingerprint=binding.payload_fingerprint,
                    result_fingerprint=binding.producer_result_fingerprint,
                    status="passed",
                )
            )
    for evidence in universe.native_case_evidence:
        expectations.append(
            native_receipt_expectation(
                receipt_id=evidence.receipt_id,
                member_id="experimentguard",
                native_owner_id="experimentguard.native-case",
                checker_id=evidence.native_check_id,
                checker_version="1",
                checker_entrypoint="researchguard.experiment.blueprint:_native_case_gaps",
                task_id=spec.task_id,
                expected_target_anchor_id=anchor.anchor_id,
                expected_target_anchor_fingerprint=anchor.anchor_fingerprint,
                native_model_id=f"experiment-native-case:{evidence.case_id}",
                model_fingerprint=evidence.subject_model_fingerprint,
                request_fingerprint=_digest(
                    {
                        "task_id": spec.task_id,
                        "case_id": evidence.case_id,
                        "case_kind": evidence.case_kind,
                        "failure_class_id": evidence.failure_class_id,
                        "oracle_id": evidence.oracle_id,
                        "expected_target_anchor_id": anchor.anchor_id,
                    }
                ),
                input_fingerprint=evidence.case_input_fingerprint,
                result_fingerprint=evidence.result_fingerprint,
                status="passed",
            )
        )
    return [
        ExperimentBlueprintGap(code, detail.split(":", 1)[0], detail)
        for code, detail in resolve_expected_native_receipts(
            universe.native_receipt_refs, expectations
        )
    ]


def validate_design_identities(spec: ExperimentSpec) -> tuple[ExperimentBlueprintGap, ...]:
    if not spec.design_blocks:
        return ()
    # Recommendation validates the design it consumes. Audit-case receipts are
    # a higher blueprint-proof layer and must not recursively gate the solver
    # whose result they bind.
    gaps = _hierarchy_gaps(spec) + _candidate_gaps(spec) + _universe_gaps(spec)
    return tuple(sorted(gaps, key=lambda item: (item.code, item.object_id, item.detail)))


def check_blueprint(spec: ExperimentSpec) -> ExperimentBlueprintResult:
    hierarchy_gaps = tuple(_hierarchy_gaps(spec))
    interface_gaps = tuple(_candidate_gaps(spec))
    universe_gaps = tuple(_universe_gaps(spec))
    native_case_gaps = tuple((*_native_case_gaps(spec), *_native_receipt_gaps(spec)))
    gaps = tuple(
        sorted(
            (*hierarchy_gaps, *interface_gaps, *universe_gaps, *native_case_gaps),
            key=lambda item: (item.code, item.object_id, item.detail),
        )
    )
    if not spec.design_blocks:
        missing = ExperimentBlueprintGap("missing-design-blueprint", spec.task_id, "blueprint operation requires design material")
        hierarchy_gaps = (missing,)
        gaps = (missing,)
    layer_definitions = (
        ("hierarchy", hierarchy_gaps),
        ("typed-interfaces", interface_gaps),
        ("independent-universe", universe_gaps),
        ("native-recommendation-bound", native_case_gaps),
    )
    layer_statuses: list[dict[str, object]] = []
    deepest = "purpose"
    first = ""
    prior_passed = True
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
    return ExperimentBlueprintResult(
        status="complete" if not gaps else "incomplete",
        model_id=f"experiment-design:{spec.task_id}",
        model_fingerprint=blueprint_fingerprint(spec),
        target_universe_fingerprint=target_universe_fingerprint(spec),
        deepest_proven_layer=deepest,
        first_unresolved_gap=first,
        gaps=gaps,
        layer_statuses=tuple(layer_statuses),
    )


def impact_blueprint(spec: ExperimentSpec, changed_ids: Iterable[str]) -> dict[str, object]:
    changed = set(changed_ids)
    qualification = check_blueprint(spec)
    authority = spec.target_universe.target_authority if spec.target_universe else None
    if qualification.status != "complete":
        return {
            "query_status": "blocked",
            "qualification_status": qualification.status,
            "qualification_model_fingerprint": qualification.model_fingerprint,
            "qualification_gaps": [item.to_dict() for item in qualification.gaps],
            "target_authority_status": authority.status if authority else "not_run",
            "target_material_status": (
                authority.native_attestation.status
                if authority and authority.native_attestation
                else "not_run"
            ),
            "changed_ids": sorted(changed),
            "affected_design_block_ids": [],
            "affected_discrimination_ids": [],
            "affected_candidate_ids": [],
            "affected_hypothesis_ids": [],
            "affected_prediction_ids": [],
            "affected_hypothesis_pairs": [],
            "affected_observation_ids": [],
            "affected_holdout_ids": [],
            "affected_receipt_ids": [],
            "affected_native_case_receipt_ids": [],
            "unknown_dependency_ids": [],
            "unknown_ownership": False,
            "partial_result_suppressed": True,
        }
    blocks = {item.block_id: item for item in spec.design_blocks}
    all_candidates = set(spec.candidate_experiment_ids)
    all_hypotheses = {item.hypothesis_id for item in spec.hypothesis_predictions}
    affected_candidates = set(changed) & all_candidates
    affected_hypotheses = set(changed) & all_hypotheses
    directly_affected_hypotheses = set(affected_hypotheses)
    directly_affected_blocks: set[str] = set()
    stable_global_ids = {
        spec.task_id,
        spec.design_root_id,
        blueprint_fingerprint(spec),
        experiment_design_subject_fingerprint(spec),
        prediction_matrix_fingerprint(spec),
        candidate_design_fingerprint(spec),
        spec.prior_receipt_fingerprint,
        *spec.prior_open_gap_ids,
    }
    stable_global_ids.discard("")
    known_ids = set(stable_global_ids) | all_candidates | all_hypotheses
    if changed & stable_global_ids:
        directly_affected_blocks.update(blocks)
        affected_candidates.update(all_candidates)
        affected_hypotheses.update(all_hypotheses)
        directly_affected_hypotheses.update(all_hypotheses)

    if spec.target_universe:
        universe = spec.target_universe
        universe_global_ids = {
            universe.universe_id,
            target_universe_fingerprint(spec),
        }
        known_ids.update(universe_global_ids)
        known_ids.update(universe.known_good_case_ids)
        known_ids.update(universe.known_bad_case_ids)
        known_ids.update(universe.required_child_output_binding_ids)
        if changed & universe_global_ids:
            directly_affected_blocks.update(blocks)
            affected_candidates.update(all_candidates)
            affected_hypotheses.update(all_hypotheses)
            directly_affected_hypotheses.update(all_hypotheses)
        for evidence in universe.native_case_evidence:
            evidence_ids = {
                evidence.case_id,
                evidence.owner_id,
                evidence.native_check_id,
                evidence.task_id,
                evidence.subject_model_fingerprint,
                evidence.prediction_matrix_fingerprint,
                evidence.candidate_design_fingerprint,
                evidence.case_input_fingerprint,
                evidence.oracle_id,
                evidence.result_fingerprint,
                evidence.receipt_id,
                evidence.receipt_fingerprint,
            }
            known_ids.update(evidence_ids)
            if changed & evidence_ids:
                directly_affected_blocks.update(blocks)
                affected_candidates.update(all_candidates)
                affected_hypotheses.update(all_hypotheses)
                directly_affected_hypotheses.update(all_hypotheses)
    for block in spec.design_blocks:
        block_ids = {
            block.block_id,
            block.candidate_experiment_id,
            block.external_execution_owner,
        }
        block_ids.update(
            value
            for port in block.ports
            for value in (port.port_id, port.schema_id)
        )
        block_ids.update(
            value
            for step in block.procedure_steps
            for value in (step.step_id, *step.input_port_ids, *step.output_port_ids)
        )
        block_ids.update(item.constraint_id for item in block.constraints)
        block_ids.update(value for value, _disposition in block.output_dispositions)
        for binding in block.input_bindings:
            block_ids.update(
                {
                    binding.binding_id,
                    binding.consumer_port_id,
                    binding.producer_id,
                    binding.producer_port_id,
                    binding.payload_schema_id,
                    binding.owner_id,
                }
            )
        for binding in block.child_output_bindings:
            block_ids.update(
                {
                    binding.binding_id,
                    binding.parent_block_id,
                    binding.parent_input_port_id,
                    binding.payload_schema_id,
                    binding.refinement_id,
                    binding.receipt_id,
                    binding.receipt_fingerprint,
                }
            )
        for parent in spec.design_blocks:
            for binding in parent.child_output_bindings:
                if binding.child_block_id == block.block_id:
                    block_ids.update(
                        {
                            binding.child_output_port_id,
                            binding.payload_fingerprint,
                            binding.producer_model_fingerprint,
                            binding.producer_result_fingerprint,
                            binding.producer_task_id,
                        }
                    )
        block_ids.discard("")
        known_ids.update(block_ids)
        if changed & block_ids:
            directly_affected_blocks.add(block.block_id)
    affected_blocks = set(directly_affected_blocks)
    pending = list(directly_affected_blocks)
    while pending:
        block_id = pending.pop()
        block = blocks.get(block_id)
        if block is None:
            continue
        for child_id in block.child_ids:
            if child_id not in affected_blocks:
                affected_blocks.add(child_id)
                pending.append(child_id)
    for block_id in affected_blocks:
        candidate_id = blocks[block_id].candidate_experiment_id
        if candidate_id:
            affected_candidates.add(candidate_id)

    if directly_affected_hypotheses:
        for row in spec.hypothesis_predictions:
            if row.hypothesis_id in directly_affected_hypotheses:
                affected_candidates.update(row.outcomes_by_experiment)

    # Candidate designs, ports, procedures, constraints, and bindings feed the
    # prediction rows that compare every hypothesis referencing that candidate.
    for row in spec.hypothesis_predictions:
        if affected_candidates & set(row.outcomes_by_experiment):
            affected_hypotheses.add(row.hypothesis_id)

    for block in spec.design_blocks:
        if block.candidate_experiment_id in affected_candidates:
            affected_blocks.add(block.block_id)
    pending = list(affected_blocks)
    while pending:
        block = blocks.get(pending.pop())
        if block and block.parent_id and block.parent_id not in affected_blocks:
            affected_blocks.add(block.parent_id)
            pending.append(block.parent_id)
    pairs = []
    hypothesis_ids = sorted(item.hypothesis_id for item in spec.hypothesis_predictions)
    for index, left in enumerate(hypothesis_ids):
        for right in hypothesis_ids[index + 1 :]:
            if left in affected_hypotheses or right in affected_hypotheses:
                pairs.append((left, right))
    unknown_dependency_ids = sorted(changed - known_ids)
    native_receipt_ids = (
        sorted(item.receipt_id for item in spec.target_universe.native_case_evidence)
        if spec.target_universe and (affected_candidates or affected_hypotheses or affected_blocks)
        else []
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
        "model_fingerprint": blueprint_fingerprint(spec),
        "target_universe_fingerprint": target_universe_fingerprint(spec),
        "changed_ids": sorted(changed),
        "affected_design_block_ids": sorted(affected_blocks),
        "affected_discrimination_ids": sorted(
            block_id
            for block_id in affected_blocks
            if blocks[block_id].kind == "discrimination_obligation"
        ),
        "affected_candidate_ids": sorted(affected_candidates),
        "affected_hypothesis_ids": sorted(affected_hypotheses),
        "affected_prediction_ids": sorted(affected_hypotheses),
        "affected_hypothesis_pairs": [list(item) for item in sorted(set(pairs))],
        "affected_observation_ids": [f"observation:{item}" for item in sorted(affected_candidates)],
        "affected_holdout_ids": [f"holdout:{item}" for item in sorted(affected_candidates)],
        "affected_receipt_ids": [f"recommendation:{spec.task_id}"] if affected_candidates or affected_hypotheses else [],
        "affected_native_case_receipt_ids": native_receipt_ids,
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


def reverse_trace_experiment(spec: ExperimentSpec, experiment_id: str) -> dict[str, object]:
    qualification = check_blueprint(spec)
    authority = spec.target_universe.target_authority if spec.target_universe else None
    target_material_status = (
        authority.native_attestation.status
        if authority and authority.native_attestation
        else "not_run"
    )
    if qualification.status != "complete":
        return {
            "query_status": "blocked",
            "qualification_status": qualification.status,
            "qualification_model_fingerprint": qualification.model_fingerprint,
            "trace_status": "incomplete",
            "trace_gaps": [item.to_dict() for item in qualification.gaps],
            "blueprint_status": qualification.status,
            "target_authority_status": authority.status if authority else "not_run",
            "target_material_status": target_material_status,
            "target_authority_fingerprint": "",
            "model_fingerprint": qualification.model_fingerprint,
            "experiment_id": "",
            "design_block_id": "",
            "discriminated_hypothesis_pairs": [],
            "differing_outcomes": {},
            "input_port_ids": [],
            "manipulation_port_ids": [],
            "observation_port_ids": [],
            "outcome_port_ids": [],
            "constraint_ids": [],
            "input_bindings": [],
            "child_output_to_parent_input_bindings": [],
            "terminal_input_sources": [],
            "procedure_step_ids": [],
            "design_path_to_root": [],
            "discrimination_block_ids": [],
            "external_execution_owner": "",
            "external_observation_refs": [],
            "external_execution_status": "not_run",
            "partial_result_suppressed": True,
            "claim_boundary": qualification.claim_boundary,
        }
    blocks = [item for item in spec.design_blocks if item.candidate_experiment_id == experiment_id]
    if len(blocks) != 1:
        raise ValueError(f"experiment {experiment_id!r} must resolve to exactly one candidate block")
    block = blocks[0]
    blocks_by_id = {item.block_id: item for item in spec.design_blocks}
    ancestry: list[str] = []
    current_id = block.block_id
    seen: set[str] = set()
    while current_id and current_id not in seen:
        seen.add(current_id)
        ancestry.append(current_id)
        current = blocks_by_id.get(current_id)
        current_id = current.parent_id if current else ""
    predictions = {item.hypothesis_id: item.outcomes_by_experiment[experiment_id] for item in spec.hypothesis_predictions}
    ids = sorted(predictions)
    pairs = [
        [left, right]
        for index, left in enumerate(ids)
        for right in ids[index + 1 :]
        if predictions[left] != predictions[right]
    ]
    child_bindings = [
        binding.to_dict()
        for parent in spec.design_blocks
        for binding in parent.child_output_bindings
        if binding.child_block_id == block.block_id
    ]
    return {
        "query_status": "complete",
        "qualification_status": qualification.status,
        "qualification_model_fingerprint": qualification.model_fingerprint,
        "trace_status": "complete",
        "trace_gaps": [],
        "blueprint_status": qualification.status,
        "target_authority_status": authority.status if authority else "not_run",
        "target_material_status": target_material_status,
        "target_authority_fingerprint": (
            authority.authority_fingerprint
            if authority
            else ""
        ),
        "model_fingerprint": blueprint_fingerprint(spec),
        "experiment_id": experiment_id,
        "design_block_id": block.block_id,
        "discriminated_hypothesis_pairs": pairs,
        "differing_outcomes": dict(sorted(predictions.items())),
        "input_port_ids": sorted(port.port_id for port in block.ports if port.kind == "input"),
        "manipulation_port_ids": sorted(port.port_id for port in block.ports if port.kind == "manipulation"),
        "observation_port_ids": sorted(port.port_id for port in block.ports if port.kind == "observation"),
        "outcome_port_ids": sorted(port.port_id for port in block.ports if port.kind == "outcome"),
        "constraint_ids": sorted(item.constraint_id for item in block.constraints),
        "input_bindings": [
            item.to_dict()
            for item in sorted(block.input_bindings, key=lambda item: item.binding_id)
        ],
        "child_output_to_parent_input_bindings": child_bindings,
        "terminal_input_sources": [
            {
                "producer_kind": item.producer_kind,
                "producer_id": item.producer_id,
                "producer_port_id": item.producer_port_id,
                "consumer_port_id": item.consumer_port_id,
                "payload_schema_id": item.payload_schema_id,
                "cardinality": item.cardinality,
                "owner_id": item.owner_id,
            }
            for item in sorted(block.input_bindings, key=lambda item: item.binding_id)
            if item.producer_kind in {"external", "state"}
        ],
        "procedure_step_ids": [item.step_id for item in sorted(block.procedure_steps, key=lambda item: (item.order, item.step_id))],
        "design_path_to_root": ancestry,
        "discrimination_block_ids": [
            block_id
            for block_id in ancestry
            if blocks_by_id[block_id].kind == "discrimination_obligation"
        ],
        "external_execution_owner": block.external_execution_owner,
        "external_observation_refs": [],
        "external_execution_status": "not_run",
        "partial_result_suppressed": False,
        "claim_boundary": qualification.claim_boundary,
    }


def export_blueprint(spec: ExperimentSpec) -> dict[str, object]:
    return {
        "schema_version": EXPERIMENT_BLUEPRINT_SCHEMA,
        "spec": spec.to_dict(),
        "check": check_blueprint(spec).to_dict(),
    }


__all__ = [
    "EXPERIMENT_BLUEPRINT_SCHEMA",
    "ExperimentBlueprintGap",
    "ExperimentBlueprintResult",
    "blueprint_fingerprint",
    "child_output_payload_fingerprint",
    "child_output_result_fingerprint",
    "check_blueprint",
    "export_blueprint",
    "impact_blueprint",
    "replay_experiment_target_material",
    "reverse_trace_experiment",
    "target_universe_fingerprint",
    "target_purpose_fingerprint",
    "target_request_fingerprint",
    "validate_design_identities",
]
