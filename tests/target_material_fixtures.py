"""Test-only authors for independent replayable Guard target material.

Production deliberately exposes no candidate-to-target convenience path.  The
tests keep their raw target snapshots outside the package so adversarial cases
can hold the original bytes fixed while mutating candidate models.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from researchguard.admission import (
    TaskFactPacket,
    _admit_expected_target_anchor,
)
from researchguard.target_authority import content_addressed_request_id
import researchguard.target_authority as target_authority_transport
from researchguard.target_authority import (
    _expected_target_result_material,
    expected_target_admission_signing_payload,
    read_target_material_bytes,
)


_TEST_ADMISSION_KEY_ID = "researchguard-test-external-admission-2026-01"
_TEST_ADMISSION_MODULUS_HEX = (
    "b3d0315c2195f01b4b06d794f09951344498b7dfe7f652c97847ee5abab80904"
    "32179c5fa5e42f13843710ff63418f2ab6bb79c042870300658810f5ad7a8d8c"
    "5b434483b0482bcc27de962181c08e7fc87e924d21057752e3e7f4e71547d49c"
    "1b8b2dd6728695bb790490e8a4a56f628a5ba08d8a22fe2b8e31ee53b99312d"
    "55b1ac076dd8cd746bec9eaa9bea2ffca573c3d5584f1384f18b64a4878c7095"
    "730a952c3d0d63b963bb22837024cd6be82246fd8bf4f046f26f1b3019786a5e"
    "088a3163a39643dc1a7de1fb82caab0200b22663cf1305eef645c11fa4aa76fab"
    "07f4a8b5c0b908352d67e10442dfce0d33c41f3559a832fa8caa93da73596ddf"
)
_TEST_ADMISSION_PRIVATE_EXPONENT_HEX = (
    "6334209760dc351d09b69ba7cb59fae828544d55d5c71b8395bdb1ae12c7c809"
    "ad8d4333adf587577021655a512b714e32849a364d3de995056f1d543dc298677"
    "04e5b758003414ea04c786dc20537591e875e35f95ae7ab2e9be18cc03be1fbc"
    "26276069326d76317f041f66827f19cdf129030a69e89b603fc5e2d88fbb06e5"
    "f870e905b6822080aaff837454e7df2b672f920d305d9daee5db0d50de64726b"
    "5c3d5935da30b1e077fc4b7eb9e668cf2066eeb9549d20aeeddff59d70428651"
    "25b1ab81229b79c4299c624ef27d9761338785fd2bad582a5a6c728156ab1d291"
    "ffa5ea0431f07d711a034f894145770d4b7cb5fc5e9f4fad27d842fa13b7e1"
)
_TEST_PRODUCER = (
    "researchguard-test-fixture",
    "researchguard.tests.expected-target-anchor",
    "1",
)


def install_test_expected_target_producer() -> None:
    """Install only the test fixture verifier; production keeps its own key."""

    target_authority_transport._CURRENT_EXPECTED_TARGET_ADMISSION_PRODUCERS[
        _TEST_PRODUCER
    ] = {
        "key_id": _TEST_ADMISSION_KEY_ID,
        "algorithm": "rsa-pkcs1v15-sha256",
        "public_exponent": 65537,
        "public_modulus_hex": _TEST_ADMISSION_MODULUS_HEX,
    }


def _sign_expected_target_admission(payload: bytes) -> str:
    modulus = int(_TEST_ADMISSION_MODULUS_HEX, 16)
    private_exponent = int(_TEST_ADMISSION_PRIVATE_EXPONENT_HEX, 16)
    width = (modulus.bit_length() + 7) // 8
    digest_info = bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(
        payload
    ).digest()
    encoded = (
        b"\x00\x01"
        + (b"\xff" * (width - len(digest_info) - 3))
        + b"\x00"
        + digest_info
    )
    signature = pow(int.from_bytes(encoded, "big"), private_exponent, modulus).to_bytes(
        width, "big"
    )
    return "rsa-pkcs1v15-sha256:" + signature.hex()


def _digest(value: object) -> str:
    body = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _inline_json_material_locator(value: object) -> str:
    body = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "data:application/json;base64," + base64.b64encode(body).decode("ascii")


def _task_packet(
    task_id: str, member_id: str, admission_request_scope: str = "current"
) -> TaskFactPacket:
    statement = f"Model {task_id} with {member_id} from the admitted target snapshot."
    return TaskFactPacket.from_dict(
        {
            "schema_version": "researchguard.task-facts.v1",
            "request_fingerprint": _digest(
                {
                    "task_id": task_id,
                    "member_id": member_id,
                    "statement": statement,
                    "admission_request_scope": admission_request_scope,
                }
            ),
            "facts": [
                {
                    "fact_id": f"fact:{member_id}:{task_id}",
                    "kind": "target_blueprint",
                    "role": "primary_action",
                    "statement": statement,
                    "source_span": {
                        "source_id": f"request:{task_id}",
                        "start": 0,
                        "end": len(statement),
                        "quote": statement,
                    },
                }
            ],
            "forbidden_reviews": [],
            "composition": None,
        }
    )


def expected_target_anchor_from_material(
    *,
    member_id: str,
    task_id: str,
    target_request_fingerprint: str,
    target_id: str,
    target_revision: str,
    material_locator: str,
    material_fingerprint: str = "",
    admission_request_scope: str = "current",
):
    install_test_expected_target_producer()
    body, replayed_fingerprint, _ = read_target_material_bytes(material_locator)
    exact_material_fingerprint = (
        replayed_fingerprint if body is not None else material_fingerprint
    )
    scope = (
        f"material:{exact_material_fingerprint}"
        if admission_request_scope == "current"
        else admission_request_scope
    )
    packet = _task_packet(task_id, member_id, scope)
    result_material = _expected_target_result_material(
        member_id=member_id,
        task_id=task_id,
        task_request_fingerprint=packet.request_fingerprint,
        target_request_id=content_addressed_request_id(target_request_fingerprint),
        target_request_fingerprint=target_request_fingerprint,
        target_id=target_id,
        target_revision=target_revision,
        material_locator=material_locator,
        material_media_type="application/json",
        material_fingerprint=exact_material_fingerprint,
        admission_owner_id=_TEST_PRODUCER[0],
        admission_producer_id=_TEST_PRODUCER[1],
        admission_producer_version="1",
    )
    admission_result_fingerprint = _digest(result_material)
    anchor_id = (
        "expected-target-anchor:"
        + admission_result_fingerprint.removeprefix("sha256:")
    )
    admission_input_fingerprint = _digest(
        {
            "task_facts_fingerprint": packet.fingerprint(),
            "result_material": result_material,
        }
    )
    signing_payload = expected_target_admission_signing_payload(
        anchor_id=anchor_id,
        result_material=result_material,
        admission_input_fingerprint=admission_input_fingerprint,
        admission_result_fingerprint=admission_result_fingerprint,
        admission_key_id=_TEST_ADMISSION_KEY_ID,
    )
    return _admit_expected_target_anchor(
        packet,
        task_id=task_id,
        member_id=member_id,
        target_request_id=content_addressed_request_id(target_request_fingerprint),
        target_request_fingerprint=target_request_fingerprint,
        target_id=target_id,
        target_revision=target_revision,
        material_locator=material_locator,
        material_fingerprint=material_fingerprint,
        admission_owner_id=_TEST_PRODUCER[0],
        admission_producer_id=_TEST_PRODUCER[1],
        admission_producer_version=_TEST_PRODUCER[2],
        admission_key_id=_TEST_ADMISSION_KEY_ID,
        admission_signature=_sign_expected_target_admission(signing_payload),
    )


def file_backed_expected_target_anchor(anchor, path: Path):
    """Re-admit the exact test snapshot through a mutable local-file locator."""

    body, _fingerprint, gap = read_target_material_bytes(anchor.material_locator)
    if body is None:
        raise ValueError(f"test anchor material cannot be copied: {gap}")
    path.write_bytes(body)
    return expected_target_anchor_from_material(
        member_id=anchor.member_id,
        task_id=anchor.task_id,
        target_request_fingerprint=anchor.target_request_fingerprint,
        target_id=anchor.target_id,
        target_revision=anchor.target_revision,
        material_locator=path.resolve().as_uri(),
        admission_request_scope=f"file-backed:{path.resolve()}",
    )


def experiment_target_material_locator(spec: object) -> str:
    from researchguard.experiment.blueprint import (
        EXPERIMENT_TARGET_MATERIAL_SCHEMA,
        _experiment_target_inventory,
    )

    request_material = {
        "task_id": spec.task_id,
        "purpose": spec.purpose,
        "coverage_ids": list(spec.coverage_ids),
        "assumptions": list(spec.assumptions),
        "unknowns": list(spec.unknowns),
    }
    inventory = _experiment_target_inventory(spec)
    material = {
        "schema_version": EXPERIMENT_TARGET_MATERIAL_SCHEMA,
        "request_contract": {
            "request_id": content_addressed_request_id(_digest(request_material)),
            **request_material,
        },
        "target_id": spec.task_id,
        "target_revision": _digest(inventory),
        "target_inventory": inventory,
    }
    return _inline_json_material_locator(material)


def experiment_expected_target_anchor(
    spec: object, *, admission_request_scope: str = "current"
):
    locator = experiment_target_material_locator(spec)
    request_fingerprint = _digest(
        {
            "task_id": spec.task_id,
            "purpose": spec.purpose,
            "coverage_ids": list(spec.coverage_ids),
            "assumptions": list(spec.assumptions),
            "unknowns": list(spec.unknowns),
        }
    )
    from researchguard.experiment.blueprint import _experiment_target_inventory

    return expected_target_anchor_from_material(
        member_id="experimentguard",
        task_id=spec.task_id,
        target_request_fingerprint=request_fingerprint,
        target_id=spec.task_id,
        target_revision=_digest(_experiment_target_inventory(spec)),
        material_locator=locator,
        admission_request_scope=admission_request_scope,
    )


def artifact_target_material_locator(inventory: object) -> str:
    from researchguard.logic.artifact_inventory import LOGIC_TARGET_MATERIAL_SCHEMA

    request_material = {
        "inventory_id": inventory.inventory_id,
        "root_unit_id": inventory.root_unit_id,
        "source_revision": inventory.source_revision,
    }
    material = {
        "schema_version": LOGIC_TARGET_MATERIAL_SCHEMA,
        "request_contract": {
            "request_id": content_addressed_request_id(_digest(request_material)),
            **request_material,
        },
        "artifact_subject": {
            "schema_version": inventory.schema_version,
            "inventory_id": inventory.inventory_id,
            "source_revision": inventory.source_revision,
            "root_unit_id": inventory.root_unit_id,
            "units": [
                item.to_dict()
                for item in sorted(inventory.units, key=lambda row: row.unit_id)
            ],
        },
    }
    return _inline_json_material_locator(material)


def artifact_expected_target_anchor(
    inventory: object, *, admission_request_scope: str = "current"
):
    request_fingerprint = _digest(
        {
            "inventory_id": inventory.inventory_id,
            "root_unit_id": inventory.root_unit_id,
            "source_revision": inventory.source_revision,
        }
    )
    subject = {
        "schema_version": inventory.schema_version,
        "inventory_id": inventory.inventory_id,
        "source_revision": inventory.source_revision,
        "root_unit_id": inventory.root_unit_id,
        "units": [
            item.to_dict() for item in sorted(inventory.units, key=lambda row: row.unit_id)
        ],
    }
    return expected_target_anchor_from_material(
        member_id="logicguard",
        task_id=inventory.inventory_id,
        target_request_fingerprint=request_fingerprint,
        target_id=inventory.inventory_id,
        target_revision=_digest(subject),
        material_locator=artifact_target_material_locator(inventory),
        admission_request_scope=admission_request_scope,
    )


def information_target_material_locator(state: object, universe: object) -> str:
    from researchguard.source.blueprint import SOURCE_TARGET_MATERIAL_SCHEMA

    contract = state.guard_contract
    if contract is None:
        raise ValueError("test target material requires a SourceGuard contract")
    request_material = {
        "model_id": contract.model_id,
        "purpose": contract.purpose,
        "claim_boundary": contract.claim_boundary,
        "candidate_contract_fingerprint": state.candidate_contract_fingerprint,
    }
    snapshot = {
        "universe_id": universe.universe_id,
        "target_root_unit_id": universe.target_root_unit_id,
        "target_units": [item.to_dict() for item in universe.target_units],
        "target_unit_interfaces": [item.to_dict() for item in universe.target_unit_interfaces],
        "required_target_unit_ids": list(universe.required_target_unit_ids),
        "required_gap_ids": list(contract.external_universe.get("gap_ids", [])),
        "required_source_role_ids": list(contract.external_universe.get("source_role_ids", [])),
        "required_lineage_slot_ids": list(contract.external_universe.get("lineage_slot_ids", [])),
        "required_anchor_requirement_ids": list(contract.external_universe.get("anchor_requirement_ids", [])),
        "required_handoff_ids": list(contract.external_universe.get("handoff_ids", [])),
        "known_good_case_ids": [item.known_good.case_id for item in contract.prevented_failures],
        "known_bad_case_ids": [item.known_bad.case_id for item in contract.prevented_failures],
        "failure_class_ids": [item.failure_id for item in contract.prevented_failures],
    }
    target_subject = {
        "model_id": contract.model_id,
        "candidate_contract_fingerprint": state.candidate_contract_fingerprint,
        **snapshot,
    }
    material = {
        "schema_version": SOURCE_TARGET_MATERIAL_SCHEMA,
        "request_contract": {
            "request_id": content_addressed_request_id(_digest(request_material)),
            **request_material,
        },
        "target_id": contract.model_id,
        "target_revision": _digest(target_subject),
        "target_snapshot": snapshot,
    }
    return _inline_json_material_locator(material)


def information_expected_target_anchor(
    state: object, universe: object, *, admission_request_scope: str = "current"
):
    contract = state.guard_contract
    if contract is None:
        raise ValueError("test target anchor requires a SourceGuard contract")
    request_fingerprint = _digest(
        {
            "model_id": contract.model_id,
            "purpose": contract.purpose,
            "claim_boundary": contract.claim_boundary,
            "candidate_contract_fingerprint": state.candidate_contract_fingerprint,
        }
    )
    snapshot = {
        "universe_id": universe.universe_id,
        "target_root_unit_id": universe.target_root_unit_id,
        "target_units": [item.to_dict() for item in universe.target_units],
        "target_unit_interfaces": [item.to_dict() for item in universe.target_unit_interfaces],
        "required_target_unit_ids": list(universe.required_target_unit_ids),
        "required_gap_ids": list(contract.external_universe.get("gap_ids", [])),
        "required_source_role_ids": list(contract.external_universe.get("source_role_ids", [])),
        "required_lineage_slot_ids": list(contract.external_universe.get("lineage_slot_ids", [])),
        "required_anchor_requirement_ids": list(contract.external_universe.get("anchor_requirement_ids", [])),
        "required_handoff_ids": list(contract.external_universe.get("handoff_ids", [])),
        "known_good_case_ids": [item.known_good.case_id for item in contract.prevented_failures],
        "known_bad_case_ids": [item.known_bad.case_id for item in contract.prevented_failures],
        "failure_class_ids": [item.failure_id for item in contract.prevented_failures],
    }
    target_subject = {
        "model_id": contract.model_id,
        "candidate_contract_fingerprint": state.candidate_contract_fingerprint,
        **snapshot,
    }
    return expected_target_anchor_from_material(
        member_id="sourceguard",
        task_id=contract.model_id,
        target_request_fingerprint=request_fingerprint,
        target_id=contract.model_id,
        target_revision=_digest(target_subject),
        material_locator=information_target_material_locator(state, universe),
        admission_request_scope=admission_request_scope,
    )


def trace_target_material_locator(
    model: object,
    universe: object,
    *,
    failure_class_ids: tuple[str, ...] | None = None,
) -> str:
    from researchguard.trace.blueprint import (
        TRACE_TARGET_MATERIAL_SCHEMA,
        _trace_actual_objects,
        trace_interface_model_fingerprint,
    )
    from researchguard.trace.schema import SCHEMA_ID

    model_instance_id = str(
        model.metadata.get("model_instance_id") or "traceguard-investigation"
    )
    request_material = {
        "model_instance_id": model_instance_id,
        "purpose": str(model.metadata.get("purpose", "")),
        "bounded_claim_ids": sorted(
            value for item in model.storyline_hypotheses for value in item.bounded_claim_ids
        ),
        "handoff_ids": sorted(
            value for item in model.storyline_hypotheses for value in item.handoff_ids
        ),
    }
    subject = {
        "model_instance_id": model_instance_id,
        "schema_id": SCHEMA_ID,
        "interface_model_fingerprint": trace_interface_model_fingerprint(model),
        "native_objects": {
            kind: sorted(values)
            for kind, values in sorted(_trace_actual_objects(model).items())
        },
    }
    purpose_binding = model.metadata.get("guard_purpose_contract", {})
    failure_class_ids = sorted(
        str(value)
        for value in (
            failure_class_ids
            if failure_class_ids is not None
            else purpose_binding.get("selected_failure_ids", [])
        )
    )
    target_denominator = {
        "native_subject": subject,
        "known_good_case_ids": sorted(universe.known_good_case_ids),
        "known_bad_case_ids": sorted(universe.known_bad_case_ids),
        "failure_class_ids": failure_class_ids,
    }
    material = {
        "schema_version": TRACE_TARGET_MATERIAL_SCHEMA,
        "request_contract": {
            "request_id": content_addressed_request_id(_digest(request_material)),
            **request_material,
        },
        "target_id": model_instance_id,
        "target_revision": _digest(target_denominator),
        "native_subject": subject,
        "known_good_case_ids": sorted(universe.known_good_case_ids),
        "known_bad_case_ids": sorted(universe.known_bad_case_ids),
        "failure_class_ids": failure_class_ids,
    }
    return _inline_json_material_locator(material)


def trace_expected_target_anchor(
    model: object,
    universe: object,
    *,
    failure_class_ids: tuple[str, ...] | None = None,
    admission_request_scope: str = "current",
):
    from researchguard.trace.blueprint import (
        _trace_actual_objects,
        trace_interface_model_fingerprint,
    )
    from researchguard.trace.schema import SCHEMA_ID

    model_instance_id = str(
        model.metadata.get("model_instance_id") or "traceguard-investigation"
    )
    request_fingerprint = _digest(
        {
            "model_instance_id": model_instance_id,
            "purpose": str(model.metadata.get("purpose", "")),
            "bounded_claim_ids": sorted(
                value for item in model.storyline_hypotheses for value in item.bounded_claim_ids
            ),
            "handoff_ids": sorted(
                value for item in model.storyline_hypotheses for value in item.handoff_ids
            ),
        }
    )
    subject = {
        "model_instance_id": model_instance_id,
        "schema_id": SCHEMA_ID,
        "interface_model_fingerprint": trace_interface_model_fingerprint(model),
        "native_objects": {
            kind: sorted(values)
            for kind, values in sorted(_trace_actual_objects(model).items())
        },
    }
    purpose_binding = model.metadata.get("guard_purpose_contract", {})
    failure_ids = sorted(
        str(value)
        for value in (
            failure_class_ids
            if failure_class_ids is not None
            else purpose_binding.get("selected_failure_ids", [])
        )
    )
    target_denominator = {
        "native_subject": subject,
        "known_good_case_ids": sorted(universe.known_good_case_ids),
        "known_bad_case_ids": sorted(universe.known_bad_case_ids),
        "failure_class_ids": failure_ids,
    }
    return expected_target_anchor_from_material(
        member_id="traceguard",
        task_id=model_instance_id,
        target_request_fingerprint=request_fingerprint,
        target_id=model_instance_id,
        target_revision=_digest(target_denominator),
        material_locator=trace_target_material_locator(
            model, universe, failure_class_ids=failure_class_ids
        ),
        admission_request_scope=admission_request_scope,
    )
