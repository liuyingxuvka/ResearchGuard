from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import hashlib
import importlib
import json
import os
from pathlib import Path
import runpy
import tempfile
from typing import Any, Iterable, Mapping

from researchguard.admission import COMPOSITION_SCHEMA, TASK_FACTS_SCHEMA
from researchguard.routing import (
    MEMBER_ADMISSION_CONTRACTS,
    MEMBER_NATIVE_CHECKERS,
    native_owner_registry_identity,
    request_fingerprint,
)
from researchguard.model_envelope import (
    HandoffConsumerAcknowledgement,
    HandoffConsumerRequirement,
    HandoffFieldContract,
    MemberBehaviorManifest,
    MemberModelEnvelope,
    NativeReceiptReference,
    ResponsibilitySpan,
    payload_fingerprint,
)
import researchguard.native_receipts as native_receipt_transport
from researchguard.native_receipts import (
    _admit_signed_native_receipt,
    _receipt_core,
    native_receipt_signing_payload,
)
from researchguard.target_authority import ExpectedTargetAnchor
from target_material_fixtures import (
    _TEST_ADMISSION_KEY_ID,
    _TEST_ADMISSION_MODULUS_HEX,
    _sign_expected_target_admission,
)
from researchguard.target_authority import TargetAuthorityItem, TargetPurposeAuthority


MEMBER_PRIMARY_FACTS = {
    "logicguard": ("logic.argument_structure", ()),
    "sourceguard": ("source.primary_discovery", ()),
    "traceguard": ("trace.temporal_reconstruction", ()),
    "experimentguard": (
        "experiment.discriminating_set",
        (
            "experiment.explicit_hypotheses",
            "experiment.finite_candidates",
            "experiment.predicted_outcomes",
        ),
    ),
}

_NATIVE_REPLAY_FIELDS = {
    "logicguard": (
        "researchguard.logic.native-owner-replay.v1",
        "argument_request",
        "argument_artifact_input",
        "qualification_result",
    ),
    "sourceguard": (
        "researchguard.source.native-owner-replay.v1",
        "discovery_request",
        "information_input",
        "qualification_result",
    ),
    "traceguard": (
        "researchguard.trace.native-owner-replay.v1",
        "investigation_request",
        "trace_input",
        "inference_result",
    ),
    "experimentguard": (
        "researchguard.experiment.native-owner-replay.v1",
        "experiment_request",
        "experiment_input",
        "blueprint_result",
    ),
}

# Native composition fixtures are content-addressed portable DNA examples.
# Wall-clock creation time is audit metadata, not part of the target behavior,
# so freeze it in these fixtures instead of making identical compositions gain
# a new identity every time the compiler runs.
_FROZEN_NATIVE_GENERATED_AT = "2026-01-01T00:00:00+00:00"


def _digest(value: object) -> str:
    body = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


_NATIVE_FIXTURE_ROOT: Path | None = None
_NATIVE_FIXTURE_CACHE: dict[tuple[str, str], tuple[str, str, object, object]] = {}
_TEST_NATIVE_RECEIPT_PRODUCER_ID = "researchguard.tests.native-receipt"
_TEST_NATIVE_RECEIPT_PRODUCER_VERSION = "1"


def configure_test_native_fixture_root(root: Path) -> None:
    global _NATIVE_FIXTURE_ROOT
    resolved = root.resolve()
    if not resolved.is_absolute():
        raise ValueError("test native fixture root must be absolute")
    _NATIVE_FIXTURE_ROOT = resolved
    _NATIVE_FIXTURE_CACHE.clear()


def reset_test_native_fixture_root() -> None:
    global _NATIVE_FIXTURE_ROOT
    _NATIVE_FIXTURE_ROOT = None
    _NATIVE_FIXTURE_CACHE.clear()


@contextmanager
def isolated_test_native_fixture_cache():
    """Give a developer compiler one fresh relative-path fixture universe."""

    global _NATIVE_FIXTURE_ROOT
    prior_root = _NATIVE_FIXTURE_ROOT
    prior_cache = dict(_NATIVE_FIXTURE_CACHE)
    _NATIVE_FIXTURE_ROOT = None
    _NATIVE_FIXTURE_CACHE.clear()
    try:
        yield
    finally:
        _NATIVE_FIXTURE_CACHE.clear()
        _NATIVE_FIXTURE_CACHE.update(prior_cache)
        _NATIVE_FIXTURE_ROOT = prior_root


def _native_fixture_root() -> Path:
    if _NATIVE_FIXTURE_ROOT is not None:
        return _NATIVE_FIXTURE_ROOT
    supplied = os.environ.get("RESEARCHGUARD_TEST_FIXTURE_ROOT", "").strip()
    if supplied:
        requested = Path(supplied)
        if requested.is_absolute():
            return requested.resolve()
        if os.environ.get(
            "RESEARCHGUARD_TEST_FIXTURE_ROOT_RELATIVE", ""
        ).strip() == "1":
            if not requested.parts or any(
                part in {"", ".", ".."} for part in requested.parts
            ):
                raise RuntimeError(
                    "relative test native fixture root is not a safe child path"
                )
            return requested
    raise RuntimeError("test native fixture root was not explicitly configured")


def install_test_native_receipt_producers() -> None:
    for member, (checker_id, checker_version, module_name, function_name) in (
        MEMBER_NATIVE_CHECKERS.items()
    ):
        native_receipt_transport._CURRENT_NATIVE_RECEIPT_PRODUCERS[
            (
                member,
                member,
                _TEST_NATIVE_RECEIPT_PRODUCER_ID,
                _TEST_NATIVE_RECEIPT_PRODUCER_VERSION,
                checker_id,
                checker_version,
            )
        ] = {
            "key_id": _TEST_ADMISSION_KEY_ID,
            "algorithm": "rsa-pkcs1v15-sha256",
            "public_exponent": 65537,
            "public_modulus_hex": _TEST_ADMISSION_MODULUS_HEX,
            "checker_entrypoint": f"{module_name}:{function_name}",
        }
    for member, owner, checker, version, entrypoint in (
        (
            "experimentguard", "experimentguard.child-output-interface",
            "researchguard.experiment.child-output-binding", "1",
            "researchguard.experiment.blueprint:_candidate_gaps",
        ),
        (
            "experimentguard", "experimentguard.native-case",
            "researchguard.experiment.blueprint-case-check.v1", "1",
            "researchguard.experiment.blueprint:_native_case_gaps",
        ),
        (
            "logicguard", "logicguard.block-interface",
            "researchguard.logic.block-interface", "1",
            "researchguard.logic.blueprint:check_blueprint",
        ),
        (
            "logicguard", "logicguard.resource-leaf",
            "researchguard.logic.resource-leaf", "1",
            "researchguard.logic.blueprint:check_blueprint",
        ),
        (
            "logicguard", "logicguard.native-depth",
            "researchguard.logic.native-depth", "1",
            "researchguard.logic.blueprint:check_blueprint",
        ),
        (
            "sourceguard", "sourceguard.target-interface",
            "researchguard.source.target-interface", "1",
            "researchguard.source.blueprint:check_blueprint",
        ),
        (
            "sourceguard", "sourceguard.native-purpose",
            "researchguard.source.native-purpose", "1",
            "researchguard.source.blueprint:check_blueprint",
        ),
        (
            "traceguard", "traceguard.interface",
            "researchguard.trace.interface", "1",
            "researchguard.trace.blueprint:check_blueprint",
        ),
        (
            "traceguard", "traceguard.canonical-inference",
            "researchguard.trace.canonical-inference", "1",
            "researchguard.trace.blueprint:check_blueprint",
        ),
        (
            "traceguard", "traceguard.native-purpose",
            "researchguard.trace.native-purpose", "1",
            "researchguard.trace.blueprint:check_blueprint",
        ),
    ):
        native_receipt_transport._CURRENT_NATIVE_RECEIPT_PRODUCERS[
            (
                member,
                owner,
                _TEST_NATIVE_RECEIPT_PRODUCER_ID,
                _TEST_NATIVE_RECEIPT_PRODUCER_VERSION,
                checker,
                version,
            )
        ] = {
            "key_id": _TEST_ADMISSION_KEY_ID,
            "algorithm": "rsa-pkcs1v15-sha256",
            "public_exponent": 65537,
            "public_modulus_hex": _TEST_ADMISSION_MODULUS_HEX,
            "checker_entrypoint": entrypoint,
        }


def signed_native_receipt(
    *,
    receipt_id: str,
    member_id: str,
    native_owner_id: str,
    checker_id: str,
    checker_version: str,
    checker_entrypoint: str,
    task_id: str,
    anchor: ExpectedTargetAnchor,
    native_model_id: str,
    model_fingerprint: str,
    request_fingerprint: str,
    input_fingerprint: str,
    result_fingerprint: str,
    status: str = "passed",
) -> NativeReceiptReference:
    """Test-only external producer for an exact immutable native receipt."""

    install_test_native_receipt_producers()
    native_receipt_transport._CURRENT_NATIVE_RECEIPT_PRODUCERS[
        (
            member_id,
            native_owner_id,
            _TEST_NATIVE_RECEIPT_PRODUCER_ID,
            _TEST_NATIVE_RECEIPT_PRODUCER_VERSION,
            checker_id,
            checker_version,
        )
    ] = {
        "key_id": _TEST_ADMISSION_KEY_ID,
        "algorithm": "rsa-pkcs1v15-sha256",
        "public_exponent": 65537,
        "public_modulus_hex": _TEST_ADMISSION_MODULUS_HEX,
        "checker_entrypoint": checker_entrypoint,
    }
    core = _receipt_core(
        member_id=member_id,
        native_owner_id=native_owner_id,
        producer_id=_TEST_NATIVE_RECEIPT_PRODUCER_ID,
        producer_version=_TEST_NATIVE_RECEIPT_PRODUCER_VERSION,
        checker_id=checker_id,
        checker_version=checker_version,
        checker_entrypoint=checker_entrypoint,
        task_id=task_id,
        expected_target_anchor_id=anchor.anchor_id,
        expected_target_anchor_fingerprint=anchor.anchor_fingerprint,
        native_model_id=native_model_id,
        model_fingerprint=model_fingerprint,
        request_fingerprint=request_fingerprint,
        input_fingerprint=input_fingerprint,
        result_fingerprint=result_fingerprint,
        status=status,
    )
    payload = native_receipt_signing_payload(
        receipt_id=receipt_id,
        core=core,
        signing_key_id=_TEST_ADMISSION_KEY_ID,
    )
    return _admit_signed_native_receipt(
        receipt_id=receipt_id,
        core=core,
        signing_key_id=_TEST_ADMISSION_KEY_ID,
        producer_signature=_sign_expected_target_admission(payload),
    )


def attach_logic_inventory_receipts(model, inventory):
    """Attach fixture-only immutable interface and leaf receipts."""

    from dataclasses import replace
    import researchguard.logic.blueprint as logic_blueprint

    authority = inventory.target_authority
    if authority is None:
        raise ValueError("logic receipt fixture requires target authority")
    anchor = authority.expected_target_anchor
    refs = []
    interface_receipt_ids = {item.parent_receipt_id for item in model.block_interfaces}
    for interface in model.block_interfaces:
        refs.append(
            signed_native_receipt(
                receipt_id=interface.parent_receipt_id,
                member_id="logicguard",
                native_owner_id="logicguard.block-interface",
                checker_id="researchguard.logic.block-interface",
                checker_version="1",
                checker_entrypoint="researchguard.logic.blueprint:check_blueprint",
                task_id=interface.producer_task_id,
                anchor=anchor,
                native_model_id=interface.child_block_id,
                model_fingerprint=interface.producer_model_fingerprint,
                request_fingerprint=logic_blueprint._digest(
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
    for unit in inventory.units:
        for resource in unit.resources:
            if (
                resource.role != "receipt"
                or not resource.required
                or resource.resource_id in interface_receipt_ids
            ):
                continue
            refs.append(
                signed_native_receipt(
                    receipt_id=resource.resource_id,
                    member_id="logicguard",
                    native_owner_id="logicguard.resource-leaf",
                    checker_id="researchguard.logic.resource-leaf",
                    checker_version="1",
                    checker_entrypoint="researchguard.logic.blueprint:check_blueprint",
                    task_id=inventory.inventory_id,
                    anchor=anchor,
                    native_model_id=unit.unit_id,
                    model_fingerprint=unit.content_fingerprint,
                    request_fingerprint=logic_blueprint._digest(
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
    return replace(inventory, native_receipt_refs=tuple(refs))


def attach_logic_depth_receipt(model, inventory, bindings, evidence):
    """Attach the fixture-only immutable receipt for one current depth run."""

    from dataclasses import replace
    import researchguard.logic.blueprint as logic_blueprint
    from researchguard.logic.execution_depth import model_fingerprint

    authority = inventory.target_authority
    if authority is None:
        raise ValueError("logic depth receipt fixture requires target authority")
    anchor = authority.expected_target_anchor
    receipt = signed_native_receipt(
        receipt_id=f"logic-native-depth:{model.id}",
        member_id="logicguard",
        native_owner_id="logicguard.native-depth",
        checker_id="researchguard.logic.native-depth",
        checker_version="1",
        checker_entrypoint="researchguard.logic.blueprint:check_blueprint",
        task_id=inventory.inventory_id,
        anchor=anchor,
        native_model_id=model.id,
        model_fingerprint=f"sha256:{model_fingerprint(model)}",
        request_fingerprint=logic_blueprint._digest(
            {
                "target_root": evidence.target_root,
                "guard_contract": evidence.guard_contract,
                "budget": evidence.budget,
                "inventory_fingerprint": inventory.fingerprint,
                "realization_ids": sorted(item.artifact_unit_id for item in bindings),
                "expected_target_anchor_id": anchor.anchor_id,
            }
        ),
        input_fingerprint=logic_blueprint._digest(evidence.receipt),
        result_fingerprint=evidence.receipt_fingerprint,
    )
    return replace(evidence, native_receipt_ref=receipt)


def attach_source_receipts(state, universe):
    """Attach fixture-only immutable SourceGuard interface/purpose receipts."""

    from dataclasses import replace
    import researchguard.source.blueprint as source_blueprint

    authority = universe.target_authority
    if authority is None:
        raise ValueError("source receipt fixture requires target authority")
    anchor = authority.expected_target_anchor
    units = {item.unit_id: item for item in universe.target_units}
    refs = []
    for binding in universe.target_unit_interfaces:
        child = units[binding.child_unit_id]
        child_port = next(
            item
            for item in child.ports
            if item.port_id == binding.child_output_port_id
        )
        refs.append(
            signed_native_receipt(
                receipt_id=f"source-interface:{binding.binding_id}",
                member_id="sourceguard",
                native_owner_id="sourceguard.target-interface",
                checker_id="researchguard.source.target-interface",
                checker_version="1",
                checker_entrypoint="researchguard.source.blueprint:check_blueprint",
                task_id=universe.universe_id,
                anchor=anchor,
                native_model_id=binding.child_unit_id,
                model_fingerprint=source_blueprint._digest(child.to_dict()),
                request_fingerprint=source_blueprint._digest(
                    {
                        "binding_id": binding.binding_id,
                        "child_unit_id": binding.child_unit_id,
                        "parent_unit_id": binding.parent_unit_id,
                        "payload_schema_id": binding.payload_schema_id,
                        "expected_target_anchor_id": anchor.anchor_id,
                    }
                ),
                input_fingerprint=source_blueprint._digest(child_port.to_dict()),
                result_fingerprint=source_blueprint._digest(binding.to_dict()),
            )
        )
    receipt = universe.native_purpose_receipt
    if receipt is not None:
        model_id = str(receipt["model_id"])
        purpose_receipt_revision = str(receipt["receipt_fingerprint"]).removeprefix(
            "sha256:"
        )
        refs.append(
            signed_native_receipt(
                receipt_id=(
                    f"source-native-purpose:{model_id}:{purpose_receipt_revision}"
                ),
                member_id="sourceguard",
                native_owner_id="sourceguard.native-purpose",
                checker_id="researchguard.source.native-purpose",
                checker_version="1",
                checker_entrypoint="researchguard.source.blueprint:check_blueprint",
                task_id=universe.universe_id,
                anchor=anchor,
                native_model_id=model_id,
                model_fingerprint=str(receipt["model_fingerprint"]),
                request_fingerprint=source_blueprint._digest(
                    {
                        "universe_id": universe.universe_id,
                        "model_id": model_id,
                        "expected_target_anchor_id": anchor.anchor_id,
                    }
                ),
                input_fingerprint=source_blueprint._digest(
                    {
                        "model_contract_fingerprint": str(
                            receipt["model_contract_fingerprint"]
                        )
                    }
                ),
                result_fingerprint=str(receipt["receipt_fingerprint"]),
            )
        )
    return replace(universe, native_receipt_refs=tuple(refs))


def attach_trace_receipts(model, inference_receipt, universe):
    """Attach fixture-only immutable TraceGuard interface/inference receipts."""

    from dataclasses import replace
    import researchguard.trace.blueprint as trace_blueprint
    from researchguard.trace.schema import trace_model_fingerprint

    authority = universe.target_authority
    if authority is None:
        raise ValueError("trace receipt fixture requires target authority")
    anchor = authority.expected_target_anchor
    task_id = str(model.metadata.get("model_instance_id") or "traceguard-investigation")
    refs = []
    for binding in model.interface_bindings:
        for native in binding.receipt_refs:
            refs.append(
                signed_native_receipt(
                    receipt_id=native.receipt_id,
                    member_id="traceguard",
                    native_owner_id="traceguard.interface",
                    checker_id="researchguard.trace.interface",
                    checker_version="1",
                    checker_entrypoint="researchguard.trace.blueprint:check_blueprint",
                    task_id=task_id,
                    anchor=anchor,
                    native_model_id=binding.producer_id,
                    model_fingerprint=native.model_fingerprint,
                    request_fingerprint=trace_blueprint._digest(
                        {
                            "binding_id": binding.binding_id,
                            "producer_kind": binding.producer_kind,
                            "consumer_kind": binding.consumer_kind,
                            "payload_schema_id": binding.payload_schema_id,
                            "expected_target_anchor_id": anchor.anchor_id,
                        }
                    ),
                    input_fingerprint=trace_blueprint._digest(
                        {"result_fingerprint": native.result_fingerprint}
                    ),
                    result_fingerprint=trace_blueprint._digest(native.to_dict()),
                )
            )
    refs.append(
        signed_native_receipt(
            receipt_id=inference_receipt.receipt_id,
            member_id="traceguard",
            native_owner_id="traceguard.canonical-inference",
            checker_id="researchguard.trace.canonical-inference",
            checker_version="1",
            checker_entrypoint="researchguard.trace.blueprint:check_blueprint",
            task_id=task_id,
            anchor=anchor,
            native_model_id=task_id,
            model_fingerprint=f"sha256:{inference_receipt.model_fingerprint}",
            request_fingerprint=trace_blueprint._digest(
                {
                    "schema_id": inference_receipt.schema_id,
                    "policy_id": inference_receipt.policy_id,
                    "solver_id": inference_receipt.solver_id,
                    "expected_target_anchor_id": anchor.anchor_id,
                }
            ),
            input_fingerprint=trace_blueprint._digest(
                {"problem_fingerprint": inference_receipt.problem_fingerprint}
            ),
            result_fingerprint=trace_blueprint._digest(inference_receipt.to_dict()),
        )
    )
    purpose = model.metadata.get("guard_purpose_contract", {})
    refs.append(
        signed_native_receipt(
            receipt_id=f"trace-purpose:{universe.universe_id}",
            member_id="traceguard",
            native_owner_id="traceguard.native-purpose",
            checker_id="researchguard.trace.native-purpose",
            checker_version="1",
            checker_entrypoint="researchguard.trace.blueprint:check_blueprint",
            task_id=task_id,
            anchor=anchor,
            native_model_id=task_id,
            model_fingerprint=f"sha256:{trace_model_fingerprint(model)}",
            request_fingerprint=trace_blueprint._digest(
                {
                    "universe_id": universe.universe_id,
                    "expected_target_anchor_id": anchor.anchor_id,
                }
            ),
            input_fingerprint=trace_blueprint._digest(purpose),
            result_fingerprint=trace_blueprint._digest(
                {
                    "known_good_case_ids": list(universe.known_good_case_ids),
                    "known_bad_case_ids": list(universe.known_bad_case_ids),
                    "selected_failure_ids": sorted(
                        purpose.get("selected_failure_ids", [])
                        if isinstance(purpose, Mapping)
                        else []
                    ),
                }
            ),
        )
    )
    return replace(universe, native_receipt_refs=tuple(refs))


def _expected_anchor_from_native_input(
    member: str, material: object
) -> ExpectedTargetAnchor:
    if not isinstance(material, Mapping):
        raise ValueError("native receipt fixture input must be a mapping")
    owner_module = importlib.import_module(MEMBER_NATIVE_CHECKERS[member][2])
    expected_anchor = getattr(owner_module, "_expected_anchor", None)
    if not callable(expected_anchor):
        raise ValueError(f"{member} has no current native expected-target owner")
    anchor = expected_anchor(material)
    if not isinstance(anchor, ExpectedTargetAnchor):
        raise ValueError("native receipt fixture has no expected target anchor")
    return anchor


def _logic_native_blueprint_fixture(task_id: str) -> tuple[str, str, object, object]:
    """Build one real current LogicGuard qualification for composition tests."""

    from logic.test_dynamic_model_purpose_contract import _prepare
    from researchguard.logic import (
        ArtifactInventory,
        ArtifactRealizationBinding,
        ArtifactUnit,
        check_blueprint,
        load_model,
    )
    from researchguard.logic.artifact_inventory import (
        _bind_artifact_inventory_authority as issue_artifact_inventory_authority,
    )
    from researchguard.logic.blueprint import (
        _run_logic_native_depth_evidence as issue_logic_native_depth_evidence,
    )
    from target_material_fixtures import artifact_expected_target_anchor

    root = _native_fixture_root() / hashlib.sha256(task_id.encode()).hexdigest()[:10] / "logic"
    root.mkdir(parents=True, exist_ok=True)
    contract, candidate = _prepare(
        root,
        frozen_at=_FROZEN_NATIVE_GENERATED_AT,
    )
    model = load_model(candidate)
    unsigned = ArtifactInventory(
        inventory_id=f"inventory:{task_id}:logic",
        source_revision=f"revision:{task_id}:logic",
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
    inventory = attach_logic_inventory_receipts(model, inventory)
    bindings = (
        ArtifactRealizationBinding(
            "unit:central-argument",
            "B_MAIN",
            ("C0", "E1", "W1", "A1", "L1", "R1"),
            consumed_content_fingerprint="sha256:" + "7" * 64,
        ),
    )
    depth = issue_logic_native_depth_evidence(
        model,
        inventory,
        bindings,
        target_root=str(root),
        guard_contract=str(contract),
        budget=8,
    )
    depth = replace(
        depth,
        receipt={
            **depth.receipt,
            "generated_at": _FROZEN_NATIVE_GENERATED_AT,
        },
    )
    depth = attach_logic_depth_receipt(model, inventory, bindings, depth)
    result = check_blueprint(model, inventory, bindings, depth)
    assert result.status == "complete", [item.to_dict() for item in result.gaps]
    material = {
        "model": model.to_dict(),
        "artifact_inventory": inventory.to_dict(),
        "realizations": [item.to_dict() for item in bindings],
        "native_depth_evidence": depth.to_dict(),
    }
    return result.model_id, result.model_fingerprint, material, result.to_dict()


def _source_native_blueprint_fixture(task_id: str) -> tuple[str, str, object, object]:
    """Build one real current SourceGuard qualification for composition tests."""

    from source.test_blueprint_graph import _current_native_universe, _state
    from researchguard.source import check_blueprint
    from researchguard.source.schema import to_plain

    root = _native_fixture_root() / hashlib.sha256(task_id.encode()).hexdigest()[:10] / "source"
    root.mkdir(parents=True, exist_ok=True)
    state = _state()
    state.generated_at = _FROZEN_NATIVE_GENERATED_AT
    universe, contract_path = _current_native_universe(state, root)
    result = check_blueprint(state, universe, contract_path=str(contract_path))
    assert result.status == "complete"
    contract = state.guard_contract
    native_model_id = f"source-blueprint:{contract.model_id if contract is not None else universe.universe_id}"
    material = {
        "belief_state": to_plain(state),
        "target_universe": universe.to_dict(),
        "contract_path": str(contract_path),
    }
    return native_model_id, result.model_fingerprint, material, result.to_dict()


def _trace_native_blueprint_fixture(task_id: str) -> tuple[str, str, object, object]:
    """Build one real current TraceGuard qualification for composition tests."""

    from trace.test_blueprint_hierarchy import (
        _current_model,
        _payload,
        _purpose_bound_model,
        _raw_universe,
        _receipt,
    )
    from researchguard.trace import check_blueprint
    from researchguard.trace.blueprint import _bind_trace_target_authority as issue_trace_target_authority
    from target_material_fixtures import trace_expected_target_anchor

    root = _native_fixture_root() / hashlib.sha256(task_id.encode()).hexdigest()[:10] / "trace"
    root.mkdir(parents=True, exist_ok=True)
    instance_id = "blueprint-test"
    payload = _payload()
    model, candidate_path = _purpose_bound_model(
        _current_model(payload),
        root,
    )
    unsigned = _raw_universe()
    universe = issue_trace_target_authority(
        model,
        unsigned,
        expected_target_anchor=trace_expected_target_anchor(model, unsigned),
    )
    universe = attach_trace_receipts(model, _receipt(model), universe)
    result = check_blueprint(
        model,
        _receipt(model),
        universe,
        candidate_path=str(candidate_path),
    )
    assert result.status == "complete", [item.to_dict() for item in result.gaps]
    material = {
        "model": model.to_dict(),
        "target_universe": universe.to_dict(),
        "candidate_path": str(candidate_path),
    }
    return (
        f"trace-blueprint:{instance_id}",
        result.model_fingerprint,
        material,
        result.to_dict(),
    )


def _experiment_native_blueprint_fixture(task_id: str) -> tuple[str, str, object, object]:
    """Build one real current ExperimentGuard qualification for composition tests."""

    namespace = runpy.run_path(
        str(Path(__file__).resolve().parent / "experiment" / "test_blueprint_design.py")
    )
    spec = namespace["_spec"](task_id=task_id)
    result = namespace["check_blueprint"](spec)
    assert result.status == "complete", [item.to_dict() for item in result.gaps]
    root = _native_fixture_root() / hashlib.sha256(task_id.encode()).hexdigest()[:10] / "experiment"
    root.mkdir(parents=True, exist_ok=True)
    spec_path = root / "spec.json"
    body = json.dumps(spec.to_dict(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    spec_path.write_bytes(body)
    material = {
        "spec_path": str(spec_path),
        "spec_fingerprint": "sha256:" + hashlib.sha256(body).hexdigest(),
    }
    return result.model_id, result.model_fingerprint, material, result.to_dict()


def _native_blueprint_fixture(member: str, task_id: str) -> tuple[str, str, object, object]:
    key = (member, task_id)
    if key not in _NATIVE_FIXTURE_CACHE:
        if member == "logicguard":
            _NATIVE_FIXTURE_CACHE[key] = _logic_native_blueprint_fixture(task_id)
        elif member == "sourceguard":
            _NATIVE_FIXTURE_CACHE[key] = _source_native_blueprint_fixture(task_id)
        elif member == "traceguard":
            _NATIVE_FIXTURE_CACHE[key] = _trace_native_blueprint_fixture(task_id)
        elif member == "experimentguard":
            _NATIVE_FIXTURE_CACHE[key] = _experiment_native_blueprint_fixture(task_id)
        else:
            native_model_id = f"model:{member}:current"
            model_fingerprint = _digest({"member": member, "task_id": task_id})
            _NATIVE_FIXTURE_CACHE[key] = (
                native_model_id,
                model_fingerprint,
                {"fixture": f"current-{member}-native-input"},
                {"status": "complete", "gap_ids": []},
            )
    return _NATIVE_FIXTURE_CACHE[key]


def _recompute_native_blueprint(
    member: str,
    material: object,
) -> tuple[str, str, dict[str, object], str, tuple[str, ...]]:
    """Invoke the member-owned checker used by the production replay route."""

    _checker_id, _checker_version, module_name, _function_name = MEMBER_NATIVE_CHECKERS[member]
    module = importlib.import_module(module_name)
    replay = getattr(module, "_replay_blueprint", None)
    if not callable(replay):
        raise ValueError(f"{member} test fixture has no current native blueprint replay")
    native = replay(material)
    if isinstance(native, tuple):
        model_id, result = native
    else:
        result = native
        model_id = str(result.get("model_id", ""))
    if not isinstance(result, Mapping):
        raise ValueError(f"{member} native blueprint replay returned a foreign result")
    result_dict = dict(result)
    model_fingerprint = str(result_dict.get("model_fingerprint", ""))
    terminal = "passed" if result_dict.get("status") == "complete" else "blocked"
    gaps = tuple(
        sorted(
            f"{item.get('code', '')}:{item.get('object_id', '')}"
            for item in result_dict.get("gaps", [])
            if isinstance(item, Mapping)
        )
    )
    return str(model_id), model_fingerprint, result_dict, terminal, gaps


def _native_owner_material(
    *,
    member: str,
    task_id: str,
    native_model_id: str,
    model_fingerprint: str,
    claim_boundary: str,
    receipt_id: str,
    terminal_status: str = "passed",
    input_material: object | None = None,
    result_material: object | None = None,
) -> tuple[bytes, NativeReceiptReference, MemberBehaviorManifest]:
    schema, request_field, input_field, result_field = _NATIVE_REPLAY_FIELDS[member]
    checker_id, checker_version, _module, _function = MEMBER_NATIVE_CHECKERS[member]
    chosen_input_material = (
        input_material
        if input_material is not None
        else {"fixture": f"current-{member}-native-input"}
    )
    chosen_result_material = (
        result_material
        if result_material is not None
        else {"status": "complete", "gap_ids": []}
    )
    chosen_input_material = json.loads(
        json.dumps(chosen_input_material, ensure_ascii=False, sort_keys=True)
    )
    chosen_result_material = json.loads(
        json.dumps(chosen_result_material, ensure_ascii=False, sort_keys=True)
    )
    anchor = _expected_anchor_from_native_input(member, chosen_input_material)
    native_input = {
        "native_model_id": native_model_id,
        "model_fingerprint": model_fingerprint,
        "input_id": f"{member}-input:{_digest(chosen_input_material)}",
        "material": chosen_input_material,
    }
    result = {
        "checker_id": checker_id,
        "checker_version": checker_version,
        "model_fingerprint": model_fingerprint,
        "terminal_status": terminal_status,
        "native_receipt_ids": [receipt_id],
        "material": chosen_result_material,
    }
    checker_entrypoint = (
        f"{MEMBER_NATIVE_CHECKERS[member][2]}:{MEMBER_NATIVE_CHECKERS[member][3]}"
    )
    owner_module = importlib.import_module(MEMBER_NATIVE_CHECKERS[member][2])
    manifest_builder = getattr(owner_module, "build_native_behavior_manifest")
    manifest = manifest_builder(
        native_model_id=native_model_id,
        model_fingerprint=model_fingerprint,
        native_input_material=chosen_input_material,
        replayed_result=chosen_result_material,
        native_receipt_ids=(receipt_id,),
        result_fingerprint=_digest(result),
        terminal_status=terminal_status,
    )
    request = {
        "task_id": task_id,
        "operation": "blueprint-check",
        "claim_boundary": claim_boundary,
        "material": {
            "member_id": member,
            "checker_id": checker_id,
            "checker_version": checker_version,
            "registry_identity": native_owner_registry_identity(member),
            "expected_target_anchor_id": anchor.anchor_id,
            "expected_target_anchor_fingerprint": anchor.anchor_fingerprint,
            "behavior_manifest_fingerprint": manifest.expected_fingerprint,
        },
    }
    core = _receipt_core(
        member_id=member,
        native_owner_id=member,
        producer_id=_TEST_NATIVE_RECEIPT_PRODUCER_ID,
        producer_version=_TEST_NATIVE_RECEIPT_PRODUCER_VERSION,
        checker_id=checker_id,
        checker_version=checker_version,
        checker_entrypoint=checker_entrypoint,
        task_id=task_id,
        expected_target_anchor_id=anchor.anchor_id,
        expected_target_anchor_fingerprint=anchor.anchor_fingerprint,
        native_model_id=native_model_id,
        model_fingerprint=model_fingerprint,
        request_fingerprint=_digest(request),
        input_fingerprint=_digest(native_input),
        result_fingerprint=_digest(result),
        status=terminal_status,
        behavior_manifest_fingerprint=manifest.expected_fingerprint,
    )
    signing_payload = native_receipt_signing_payload(
        receipt_id=receipt_id,
        core=core,
        signing_key_id=_TEST_ADMISSION_KEY_ID,
    )
    receipt = _admit_signed_native_receipt(
        receipt_id=receipt_id,
        core=core,
        signing_key_id=_TEST_ADMISSION_KEY_ID,
        producer_signature=_sign_expected_target_admission(signing_payload),
    )
    payload = {
        "schema_version": schema,
        request_field: request,
        input_field: native_input,
        result_field: result,
    }
    payload_bytes = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return payload_bytes, receipt, manifest


def member_native_envelope(
    raw: dict[str, object],
    *,
    native_model_id: str | None = None,
    native_schema_id: str | None = None,
    model_fingerprint: str | None = None,
    receipt_id: str | None = None,
    terminal_status: str | None = None,
    open_gap_refs: tuple[str, ...] | None = None,
    input_material: object | None = None,
    result_material: object | None = None,
) -> MemberModelEnvelope:
    """Re-issue a test envelope through the exact member replay contract."""

    base = MemberModelEnvelope.from_dict(raw)
    if base.opaque_payload is None:
        raise ValueError("test member envelope requires its native input payload")
    base_payload = json.loads(base.opaque_payload.decode("utf-8"))
    _schema, _request_field, input_field, _result_field = _NATIVE_REPLAY_FIELDS[base.member_id]
    base_input_material = base_payload[input_field]["material"]
    chosen_input_material = (
        input_material if input_material is not None else base_input_material
    )
    derived_model_id, derived_model_fingerprint, derived_result, derived_terminal, derived_gaps = (
        _recompute_native_blueprint(base.member_id, chosen_input_material)
    )
    chosen_model_id = native_model_id or derived_model_id
    chosen_model_fingerprint = model_fingerprint or derived_model_fingerprint
    chosen_receipt_id = receipt_id or base.native_receipt_refs[0].receipt_id
    chosen_terminal = terminal_status or derived_terminal
    chosen_gaps = (
        open_gap_refs
        if open_gap_refs is not None
        else (() if chosen_terminal == "passed" else derived_gaps)
    )
    payload, receipt, manifest = _native_owner_material(
        member=base.member_id,
        task_id=base.task_id,
        native_model_id=chosen_model_id,
        model_fingerprint=chosen_model_fingerprint,
        claim_boundary=base.claim_boundary,
        receipt_id=chosen_receipt_id,
        terminal_status=chosen_terminal,
        input_material=chosen_input_material,
        result_material=result_material if result_material is not None else derived_result,
    )
    return MemberModelEnvelope(
        envelope_id=base.envelope_id,
        task_id=base.task_id,
        member_id=base.member_id,
        native_model_id=chosen_model_id,
        native_schema_id=native_schema_id or base.native_schema_id,
        native_schema_version=base.native_schema_version,
        model_fingerprint=chosen_model_fingerprint,
        expected_target_anchor_id=receipt.expected_target_anchor_id,
        expected_target_anchor_fingerprint=receipt.expected_target_anchor_fingerprint,
        payload_fingerprint=payload_fingerprint(payload),
        input_field_ids=base.input_field_ids,
        output_field_ids=base.output_field_ids,
        native_receipt_refs=(
            receipt,
        ),
        behavior_manifest=manifest,
        open_gap_refs=chosen_gaps,
        terminal_status=chosen_terminal,
        claim_boundary=base.claim_boundary,
        responsibility_spans=base.responsibility_spans,
        opaque_payload=payload,
    )


def _span(source_id: str, quote: str) -> dict[str, Any]:
    return {"source_id": source_id, "start": 0, "end": len(quote), "quote": quote}


def task_facts(
    *,
    argv: list[str] | tuple[str, ...],
    intent: str,
    primary_kind: str,
    additional_primary_kinds: Iterable[str] = (),
    context_kinds: Iterable[str] = (),
    composition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    primary_kinds = (primary_kind, *tuple(additional_primary_kinds))
    kinds = (*primary_kinds, *tuple(context_kinds))
    facts = []
    for index, kind in enumerate(kinds):
        quote = f"request fact {index}: {kind}"
        facts.append(
            {
                "fact_id": f"fact:{index}",
                "kind": kind,
                "role": "primary_action" if index < len(primary_kinds) else "context",
                "statement": quote,
                "source_span": _span(f"request:user:{index}", quote),
            }
        )
    all_kinds = set(kinds)
    primary_quote = str(facts[0]["source_span"]["quote"])
    reviews = []
    for member, contract in MEMBER_ADMISSION_CONTRACTS.items():
        for condition in contract["forbidden_conditions"]:
            present = bool(all_kinds.intersection(condition["any_fact_kinds"]))
            reviews.append(
                {
                    "member_id": member,
                    "condition_id": condition["condition_id"],
                    "disposition": "present" if present else "absent",
                    "source_span": _span("request:user:review", primary_quote),
                }
            )
    payload = {
        "schema_version": TASK_FACTS_SCHEMA,
        "request_fingerprint": request_fingerprint(argv, business_intent_id=intent),
        "facts": facts,
        "forbidden_reviews": reviews,
    }
    if composition is not None:
        payload["composition"] = composition
    return payload


def composition(
    *member_responsibilities: tuple[str, tuple[str, ...]],
) -> dict[str, Any]:
    install_test_native_receipt_producers()
    task_id = "task:test-composition"
    member_count = len(member_responsibilities)
    field_ids = {
        index: f"field:{index}:{index + 1}:artifact"
        for index in range(1, member_count)
    }
    envelopes: list[MemberModelEnvelope] = []
    expected_target_anchors: list[ExpectedTargetAnchor] = []
    for index, (member, _responsibilities) in enumerate(member_responsibilities, start=1):
        quote = f"declared responsibility for {member}"
        (
            native_model_id,
            model_fingerprint,
            native_input_material,
            native_result_material,
        ) = _native_blueprint_fixture(member, task_id)
        expected_target_anchors.append(
            _expected_anchor_from_native_input(member, native_input_material)
        )
        claim_boundary = f"{member} owns only its native declared result."
        receipt_id = f"receipt:{member}:current"
        opaque, receipt, manifest = _native_owner_material(
            member=member,
            task_id=task_id,
            native_model_id=native_model_id,
            model_fingerprint=model_fingerprint,
            claim_boundary=claim_boundary,
            receipt_id=receipt_id,
            input_material=native_input_material,
            result_material=native_result_material,
        )
        envelopes.append(
            MemberModelEnvelope(
                envelope_id=f"envelope:{member}",
                task_id=task_id,
                member_id=member,
                native_model_id=native_model_id,
                native_schema_id=f"researchguard.{member}.native-model",
                native_schema_version="1",
                model_fingerprint=model_fingerprint,
                expected_target_anchor_id=receipt.expected_target_anchor_id,
                expected_target_anchor_fingerprint=receipt.expected_target_anchor_fingerprint,
                payload_fingerprint=payload_fingerprint(opaque),
                input_field_ids=((field_ids[index - 1],) if index > 1 else ()),
                output_field_ids=((field_ids[index],) if index < member_count else ()),
                native_receipt_refs=(
                    receipt,
                ),
                behavior_manifest=manifest,
                open_gap_refs=(),
                terminal_status="passed",
                claim_boundary=claim_boundary,
                responsibility_spans=(
                    ResponsibilitySpan(
                        source_id=f"request:user:{index - 1}",
                        start=0,
                        end=len(quote),
                        quote=quote,
                    ),
                ),
                opaque_payload=opaque,
            )
        )
    envelope_by_member = {item.member_id: item for item in envelopes}
    steps = []
    handoffs = []
    owners = []
    contracts = []
    for index, (member, responsibilities) in enumerate(member_responsibilities, start=1):
        step_id = f"step:{index}:{member}"
        input_ids: list[str] = []
        output_ids: list[str] = []
        dependencies: list[str] = []
        if index > 1:
            previous_member = member_responsibilities[index - 2][0]
            previous_step = f"step:{index - 1}:{previous_member}"
            handoff_id = f"handoff:{index - 1}:{index}"
            field_id = f"field:{index - 1}:{index}:artifact"
            dependencies.append(previous_step)
            input_ids.append(handoff_id)
            handoffs.append(
                {
                    "handoff_id": handoff_id,
                    "from_step_id": previous_step,
                    "to_step_id": step_id,
                    "field_ids": [field_id],
                }
            )
            owners.append({"field_id": field_id, "owner_step_id": previous_step})
            steps[-1]["output_handoff_ids"].append(handoff_id)
            producer = envelope_by_member[previous_member]
            consumer = envelope_by_member[member]
            consumer_receipt = consumer.native_receipt_refs[0]
            field_fingerprint = payload_fingerprint(
                f"opaque field payload {field_id}".encode("utf-8")
            )
            contracts.append(
                HandoffFieldContract(
                    handoff_id=handoff_id,
                    task_id=task_id,
                    field_id=field_id,
                    field_schema_id="researchguard.handoff.opaque-artifact.v1",
                    payload_fingerprint=field_fingerprint,
                    producer_member_id=previous_member,
                    producer_step_id=previous_step,
                    producer_envelope_id=producer.envelope_id,
                    producer_envelope_fingerprint=producer.envelope_fingerprint,
                    producer_native_receipt_id=producer.native_receipt_refs[0].receipt_id,
                    producer_native_receipt_fingerprint=producer.native_receipt_refs[0].receipt_fingerprint,
                    consumers=(
                        HandoffConsumerRequirement(
                            member_id=member,
                            step_id=step_id,
                            requirement_id=f"requirement:{step_id}:{field_id}",
                        ),
                    ),
                    acknowledgements=(
                        HandoffConsumerAcknowledgement(
                            member_id=member,
                            step_id=step_id,
                            requirement_id=f"requirement:{step_id}:{field_id}",
                            status="consumed",
                            consumed_payload_fingerprint=field_fingerprint,
                            native_receipt_id=consumer_receipt.receipt_id,
                            native_receipt_fingerprint=consumer_receipt.receipt_fingerprint,
                            task_id=task_id,
                        ),
                    ),
                )
            )
        steps.append(
            {
                "step_id": step_id,
                "order": index,
                "member_id": member,
                "responsibility_condition_ids": list(responsibilities),
                "depends_on_step_ids": dependencies,
                "input_handoff_ids": input_ids,
                "output_handoff_ids": output_ids,
                "member_envelope_id": envelope_by_member[member].envelope_id,
                "consumed_envelope_fingerprints": (
                    [
                        {
                            "envelope_id": envelope_by_member[member_responsibilities[index - 2][0]].envelope_id,
                            "envelope_fingerprint": envelope_by_member[member_responsibilities[index - 2][0]].envelope_fingerprint,
                        }
                    ]
                    if index > 1
                    else []
                ),
                "claim_boundary_id": f"claim-boundary:{step_id}",
            }
        )
    return {
        "schema_version": COMPOSITION_SCHEMA,
        "task_id": task_id,
        "steps": steps,
        "handoffs": handoffs,
        "field_owners": owners,
        "member_envelopes": [item.to_dict() for item in envelopes],
        "expected_target_anchors": [
            item.to_dict() for item in expected_target_anchors
        ],
        "handoff_field_contracts": [item.to_dict() for item in contracts],
        "overall_claim_boundary": "Each member owns only its declared responsibility; the umbrella proves planning, not native completion.",
    }


def native_owner_attestations(plan: dict[str, Any]) -> list[dict[str, object]]:
    """Stand in for the four member-native attestation producers in unit tests."""

    result: list[dict[str, object]] = []
    for raw in plan["member_envelopes"]:
        envelope = MemberModelEnvelope.from_dict(raw)
        _checker_id, _checker_version, module_name, function_name = (
            MEMBER_NATIVE_CHECKERS[envelope.member_id]
        )
        checker = getattr(importlib.import_module(module_name), function_name)
        result.append(
            checker(
                envelope,
                registry_identity=native_owner_registry_identity(envelope.member_id),
            ).to_dict()
        )
    return result


def self_resign_target_authority(
    authority: TargetPurposeAuthority,
    items: Iterable[TargetAuthorityItem],
) -> TargetPurposeAuthority:
    """Adversarial helper: recompute every caller-controlled authority hash."""

    changed = replace(
        authority,
        items=tuple(items),
        authority_fingerprint="",
    )
    return replace(changed, authority_fingerprint=changed.expected_fingerprint)


def member_task_facts(
    member: str,
    *,
    argv: list[str] | tuple[str, ...],
    intent: str,
) -> dict[str, Any]:
    primary, context = MEMBER_PRIMARY_FACTS[member]
    return task_facts(
        argv=argv,
        intent=intent,
        primary_kind=primary,
        context_kinds=context,
    )
