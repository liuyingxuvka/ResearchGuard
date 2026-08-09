from __future__ import annotations

from dataclasses import replace
import base64
import hashlib
import json
from pathlib import Path

import pytest

from researchguard.admission import _admit_expected_target_anchor
from researchguard.target_authority import (
    ExpectedTargetAnchor,
    _CURRENT_EXPECTED_TARGET_ADMISSION_PRODUCERS,
    _expected_target_authority_root,
    _expected_target_binding_key,
    _expected_target_binding_material,
    _expected_target_receipt_payload,
    _expected_target_result_material,
    content_addressed_request_id,
    expected_target_admission_signing_payload,
    verify_expected_target_anchor,
    verify_registered_target_authority,
)
from target_material_fixtures import (
    _TEST_ADMISSION_KEY_ID,
    _TEST_PRODUCER,
    _digest,
    _sign_expected_target_admission,
    _task_packet,
    file_backed_expected_target_anchor,
    information_expected_target_anchor,
)


def _inline(value: object) -> tuple[str, str]:
    body = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return (
        "data:application/json;base64," + base64.b64encode(body).decode("ascii"),
        "sha256:" + hashlib.sha256(body).hexdigest(),
    )


def _materials(*, producer: tuple[str, str, str], scope: str):
    packet = _task_packet("task:authority-negative", "experimentguard", scope)
    target = {"target": scope, "items": ["a", "b"]}
    locator, material_fingerprint = _inline(target)
    target_request_fingerprint = _digest(
        {"task_id": "task:authority-negative", "scope": scope}
    )
    result = _expected_target_result_material(
        member_id="experimentguard",
        task_id="task:authority-negative",
        task_request_fingerprint=packet.request_fingerprint,
        target_request_id=content_addressed_request_id(target_request_fingerprint),
        target_request_fingerprint=target_request_fingerprint,
        target_id="target:authority-negative",
        target_revision=_digest(target),
        material_locator=locator,
        material_media_type="application/json",
        material_fingerprint=material_fingerprint,
        admission_owner_id=producer[0],
        admission_producer_id=producer[1],
        admission_producer_version=producer[2],
    )
    result_fingerprint = _digest(result)
    anchor_id = "expected-target-anchor:" + result_fingerprint[7:]
    input_fingerprint = _digest(
        {"task_facts_fingerprint": packet.fingerprint(), "result_material": result}
    )
    return (
        packet,
        result,
        anchor_id,
        input_fingerprint,
        result_fingerprint,
        target_request_fingerprint,
    )


def test_repository_fixture_key_cannot_forge_a_production_anchor() -> None:
    production = (
        "researchguard",
        "researchguard.admission.expected-target-anchor",
        "1",
    )
    assert production not in _CURRENT_EXPECTED_TARGET_ADMISSION_PRODUCERS
    packet, result, anchor_id, input_fp, result_fp, request_fp = _materials(
        producer=production,
        scope="test-key-production-forgery",
    )
    signing = expected_target_admission_signing_payload(
        anchor_id=anchor_id,
        result_material=result,
        admission_input_fingerprint=input_fp,
        admission_result_fingerprint=result_fp,
        admission_key_id=_TEST_ADMISSION_KEY_ID,
    )
    with pytest.raises(ValueError, match="producer signature is invalid"):
        _admit_expected_target_anchor(
            packet,
            task_id=result["task_id"],
            member_id=result["member_id"],
            target_request_id=result["target_request_id"],
            target_request_fingerprint=request_fp,
            target_id=result["target_id"],
            target_revision=result["target_revision"],
            material_locator=result["material_locator"],
            material_fingerprint=result["material_fingerprint"],
            admission_owner_id=production[0],
            admission_producer_id=production[1],
            admission_producer_version=production[2],
            admission_key_id=_TEST_ADMISSION_KEY_ID,
            admission_signature=_sign_expected_target_admission(signing),
        )


def test_self_written_authority_root_bytes_do_not_replace_producer_authentication() -> None:
    packet, result, anchor_id, input_fp, result_fp, _request_fp = _materials(
        producer=_TEST_PRODUCER,
        scope="manual-root-forgery-v1",
    )
    invalid_signature = "rsa-pkcs1v15-sha256:" + "00" * 256
    payload = _expected_target_receipt_payload(
        anchor_id=anchor_id,
        result_material=result,
        admission_input_fingerprint=input_fp,
        admission_result_fingerprint=result_fp,
        admission_key_id=_TEST_ADMISSION_KEY_ID,
        admission_signature=invalid_signature,
    )
    body = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    receipt_fp = "sha256:" + hashlib.sha256(body).hexdigest()
    receipt_id = "expected-target-admission:" + receipt_fp[7:]
    root = _expected_target_authority_root()
    receipt_path = root / "receipts" / f"{receipt_fp[7:]}.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_bytes(body)
    binding = _expected_target_binding_material(
        result, anchor_id=anchor_id, receipt_id=receipt_id
    )
    binding_path = root / "bindings" / f"{_expected_target_binding_key(result)}.json"
    binding_path.parent.mkdir(parents=True, exist_ok=True)
    binding_path.write_text(
        json.dumps(binding, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    value = ExpectedTargetAnchor(
        anchor_id=anchor_id,
        **result,
        admission_input_fingerprint=input_fp,
        admission_result_fingerprint=result_fp,
        admission_key_id=_TEST_ADMISSION_KEY_ID,
        admission_signature=invalid_signature,
        receipt_id=receipt_id,
        receipt_locator=(
            "researchguard-authority:expected-target-admission/" + receipt_fp[7:]
        ),
        receipt_fingerprint=receipt_fp,
    )
    anchor = replace(value, anchor_fingerprint=value.expected_fingerprint)
    assert "expected-target-admission-signature-invalid" in {
        code for code, _detail in verify_expected_target_anchor(anchor)
    }


@pytest.mark.parametrize(
    "member", ["experimentguard", "logicguard", "sourceguard", "traceguard"]
)
def test_member_adapter_rejects_changed_raw_bytes_under_frozen_anchor(
    member: str, tmp_path: Path
) -> None:
    """Each closed member adapter must reopen the anchor's current file bytes."""

    if member == "experimentguard":
        from experiment.test_blueprint_design import _spec
        from researchguard.experiment.blueprint import (
            _bind_experiment_target_authority,
            replay_experiment_target_material,
        )

        value = _spec()
        old = value.target_universe.target_authority.expected_target_anchor
        anchor = file_backed_expected_target_anchor(old, tmp_path / "experiment.json")
        value = _bind_experiment_target_authority(
            value, expected_target_anchor=anchor
        )
        authority = value.target_universe.target_authority
        replay = lambda: replay_experiment_target_material(value, anchor.material_locator)
        shrink_path = ("target_inventory", "constraint_ids")
    elif member == "logicguard":
        from logic.test_blueprint_interfaces import _inventory
        from researchguard.logic.artifact_inventory import (
            _bind_artifact_inventory_authority,
            replay_artifact_target_material,
        )

        value = _inventory()
        old = value.target_authority.expected_target_anchor
        anchor = file_backed_expected_target_anchor(old, tmp_path / "logic.json")
        value = _bind_artifact_inventory_authority(
            value, expected_target_anchor=anchor
        )
        authority = value.target_authority
        replay = lambda: replay_artifact_target_material(value, anchor.material_locator)
        shrink_path = ("artifact_subject", "units")
    elif member == "sourceguard":
        from source.test_blueprint_graph import _state, _universe
        from researchguard.source.blueprint import (
            _bind_information_target_authority,
            replay_information_target_material,
        )

        state = _state()
        value = _universe()
        value = _bind_information_target_authority(
            state,
            value,
            expected_target_anchor=information_expected_target_anchor(state, value),
        )
        old = value.target_authority.expected_target_anchor
        anchor = file_backed_expected_target_anchor(old, tmp_path / "source.json")
        value = _bind_information_target_authority(
            state, value, expected_target_anchor=anchor
        )
        authority = value.target_authority
        replay = lambda: replay_information_target_material(
            state, value, anchor.material_locator
        )
        shrink_path = ("target_snapshot", "target_units")
    else:
        from trace.test_blueprint_hierarchy import _current_model, _universe
        from researchguard.trace.blueprint import (
            _bind_trace_target_authority,
            replay_trace_target_material,
        )

        model = _current_model()
        value = _universe()
        old = value.target_authority.expected_target_anchor
        anchor = file_backed_expected_target_anchor(old, tmp_path / "trace.json")
        value = _bind_trace_target_authority(
            model, value, expected_target_anchor=anchor
        )
        authority = value.target_authority
        replay = lambda: replay_trace_target_material(model, anchor.material_locator)
        shrink_path = ("native_subject", "native_objects", "sensitivity")

    assert authority is not None
    assert verify_registered_target_authority(authority, replay()) == ()
    # Resolve the exact Windows file URI instead of guessing escaping rules.
    from urllib.parse import unquote, urlparse
    from urllib.request import url2pathname

    parsed = urlparse(anchor.material_locator)
    raw_path = url2pathname(unquote(parsed.path))
    if raw_path.startswith("/") and len(raw_path) > 2 and raw_path[2] == ":":
        raw_path = raw_path[1:]
    material_path = Path(raw_path)
    raw = json.loads(material_path.read_text(encoding="utf-8"))
    cursor = raw
    for key in shrink_path[:-1]:
        cursor = cursor[key]
    cursor[shrink_path[-1]].pop()
    material_path.write_text(
        json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    codes = {code for code, _detail in verify_registered_target_authority(authority, replay())}
    assert "expected-target-material-mismatch" in codes
