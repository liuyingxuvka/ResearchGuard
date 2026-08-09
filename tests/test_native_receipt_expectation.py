from __future__ import annotations

from copy import deepcopy

import pytest

import researchguard.native_receipts as native_receipts
from admission_fixtures import _TEST_NATIVE_RECEIPT_PRODUCER_ID
from target_material_fixtures import (
    _TEST_ADMISSION_KEY_ID,
    _TEST_ADMISSION_MODULUS_HEX,
    _sign_expected_target_admission,
)


SHA_A = "sha256:" + ("a" * 64)
SHA_B = "sha256:" + ("b" * 64)
SHA_C = "sha256:" + ("c" * 64)
SHA_D = "sha256:" + ("d" * 64)
SHA_E = "sha256:" + ("e" * 64)


def _descriptor(*, key_id: str = _TEST_ADMISSION_KEY_ID) -> dict[str, object]:
    return {
        "key_id": key_id,
        "algorithm": "rsa-pkcs1v15-sha256",
        "public_exponent": 65537,
        "public_modulus_hex": _TEST_ADMISSION_MODULUS_HEX,
        "checker_entrypoint": "researchguard.tests:exact_producer_check",
    }


def _admit(
    *,
    producer_id: str,
    producer_version: str,
    key_id: str = _TEST_ADMISSION_KEY_ID,
):
    core = native_receipts._receipt_core(
        member_id="logicguard",
        native_owner_id="logicguard.test-exact-producer",
        producer_id=producer_id,
        producer_version=producer_version,
        checker_id="researchguard.tests.exact-producer",
        checker_version="1",
        checker_entrypoint="researchguard.tests:exact_producer_check",
        task_id="task:exact-producer",
        expected_target_anchor_id="anchor:exact-producer",
        expected_target_anchor_fingerprint=SHA_A,
        native_model_id="logic-model:exact-producer",
        model_fingerprint=SHA_B,
        request_fingerprint=SHA_C,
        input_fingerprint=SHA_D,
        result_fingerprint=SHA_E,
        status="passed",
    )
    payload = native_receipts.native_receipt_signing_payload(
        receipt_id="receipt:exact-producer",
        core=core,
        signing_key_id=key_id,
    )
    return native_receipts._admit_signed_native_receipt(
        receipt_id="receipt:exact-producer",
        core=core,
        signing_key_id=key_id,
        producer_signature=_sign_expected_target_admission(payload),
    )


def _expectation():
    return native_receipts.native_receipt_expectation(
        receipt_id="receipt:exact-producer",
        member_id="logicguard",
        native_owner_id="logicguard.test-exact-producer",
        checker_id="researchguard.tests.exact-producer",
        checker_version="1",
        checker_entrypoint="researchguard.tests:exact_producer_check",
        task_id="task:exact-producer",
        expected_target_anchor_id="anchor:exact-producer",
        expected_target_anchor_fingerprint=SHA_A,
        native_model_id="logic-model:exact-producer",
        model_fingerprint=SHA_B,
        request_fingerprint=SHA_C,
        input_fingerprint=SHA_D,
        result_fingerprint=SHA_E,
        status="passed",
    )


def test_immutable_identity_rejects_another_registered_producer_and_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_key = (
        "logicguard",
        "logicguard.test-exact-producer",
        _TEST_NATIVE_RECEIPT_PRODUCER_ID,
        "1",
        "researchguard.tests.exact-producer",
        "1",
    )
    monkeypatch.setitem(
        native_receipts._CURRENT_NATIVE_RECEIPT_PRODUCERS,
        original_key,
        _descriptor(),
    )
    original = _admit(
        producer_id=_TEST_NATIVE_RECEIPT_PRODUCER_ID,
        producer_version="1",
    )
    expectation = _expectation()
    assert expectation.producer_expectation_status == "current"
    assert expectation.producer_id == _TEST_NATIVE_RECEIPT_PRODUCER_ID
    assert expectation.producer_version == "1"
    assert expectation.signature_algorithm == "rsa-pkcs1v15-sha256"
    assert expectation.signing_key_id == _TEST_ADMISSION_KEY_ID
    assert native_receipts.resolve_expected_native_receipts(
        (original,), (expectation,)
    ) == ()

    alternate_key_id = "researchguard-test-alternate-key"
    alternate_key = (
        "logicguard",
        "logicguard.test-exact-producer",
        "researchguard.tests.alternate-native-receipt",
        "2",
        "researchguard.tests.exact-producer",
        "1",
    )
    monkeypatch.setitem(
        native_receipts._CURRENT_NATIVE_RECEIPT_PRODUCERS,
        alternate_key,
        _descriptor(key_id=alternate_key_id),
    )
    with pytest.raises(
        ValueError, match="immutable native receipt identity is already bound"
    ):
        _admit(
            producer_id="researchguard.tests.alternate-native-receipt",
            producer_version="2",
            key_id=alternate_key_id,
        )


@pytest.mark.parametrize(
    ("field", "value", "expected_gap"),
    [
        (
            "algorithm",
            "rsa-pkcs1v15-sha512",
            "native-receipt-signature-algorithm-mismatch",
        ),
        (
            "public_modulus_hex",
            "f" + _TEST_ADMISSION_MODULUS_HEX[1:],
            "native-receipt-public-key-fingerprint-mismatch",
        ),
    ],
)
def test_expectation_rejects_descriptor_drift(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
    expected_gap: str,
) -> None:
    producer_key = (
        "logicguard",
        "logicguard.test-exact-producer",
        _TEST_NATIVE_RECEIPT_PRODUCER_ID,
        "1",
        "researchguard.tests.exact-producer",
        "1",
    )
    descriptor = _descriptor()
    monkeypatch.setitem(
        native_receipts._CURRENT_NATIVE_RECEIPT_PRODUCERS,
        producer_key,
        descriptor,
    )
    receipt = _admit(
        producer_id=_TEST_NATIVE_RECEIPT_PRODUCER_ID,
        producer_version="1",
    )
    expectation = _expectation()
    drifted = deepcopy(descriptor)
    drifted[field] = value
    monkeypatch.setitem(
        native_receipts._CURRENT_NATIVE_RECEIPT_PRODUCERS,
        producer_key,
        drifted,
    )

    gap_codes = {
        code
        for code, _detail in native_receipts.resolve_expected_native_receipts(
            (receipt,), (expectation,)
        )
    }
    assert expected_gap in gap_codes
    assert "native-receipt-producer-descriptor-fingerprint-mismatch" in gap_codes
