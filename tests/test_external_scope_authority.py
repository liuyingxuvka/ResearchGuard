from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from researchguard.external_scope_authority import (
    ExternalScopeAuthorityError,
    validate_external_scope_authority_record,
)


REPOSITORY = Path(__file__).resolve().parents[1]
AUTHORITY_PATH = (
    REPOSITORY
    / "models"
    / "external_domain_dna"
    / "attention-is-all-you-need-v7.authority.json"
)


def _record() -> dict[str, object]:
    return json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))


def test_canonical_scope_authority_is_signed_but_not_implicitly_trusted() -> None:
    checked = validate_external_scope_authority_record(_record())
    assert checked["authority_fingerprint"] == _record()["authority_fingerprint"]
    assert checked["required_trust"] == {
        "authority_fingerprint": _record()["authority_fingerprint"],
        "producer_descriptor_fingerprint": _record()[
            "producer_descriptor_fingerprint"
        ],
    }
    assert "licensed" not in checked


@pytest.mark.parametrize("attack", ("signature", "authority", "descriptor"))
def test_scope_authority_rejects_rebound_or_unsigned_material(attack: str) -> None:
    record = _record()
    if attack == "signature":
        record["authority_signature"] = "rsa-pkcs1v15-sha256:" + "00" * 256
    elif attack == "authority":
        record["authority"]["scope"]["purpose"] += " Rebound."
    else:
        record["producer_descriptor"]["producer_version"] = "rebound"
    with pytest.raises(ExternalScopeAuthorityError):
        validate_external_scope_authority_record(record)


@pytest.mark.parametrize("attack", ("zero-structures", "duplicate-occurrence"))
def test_scope_authority_itself_requires_a_nonempty_unique_semantic_denominator(
    attack: str,
) -> None:
    record = _record()
    authority = deepcopy(record["authority"])
    if attack == "zero-structures":
        authority["scope"]["included_structure_node_ids"] = []
        authority["scope"]["structure_obligations"] = []
    else:
        anchors = authority["scope"]["anchor_obligations"]
        anchors[1]["selector"]["occurrence_id"] = anchors[0]["selector"][
            "occurrence_id"
        ]
    record["authority"] = authority
    # Even if an attacker updates the ordinary content fingerprint, the old
    # external signature cannot authorize the changed denominator.
    import hashlib

    body = json.dumps(
        authority, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    record["authority_fingerprint"] = "sha256:" + hashlib.sha256(body).hexdigest()
    with pytest.raises(ExternalScopeAuthorityError):
        validate_external_scope_authority_record(record)


def test_runtime_and_packaged_resources_contain_no_scope_authority_private_key() -> None:
    searchable = [
        *(REPOSITORY / "src" / "researchguard").rglob("*.py"),
        *(REPOSITORY / "src" / "researchguard" / "resources").rglob("*.json"),
        *(REPOSITORY / "models" / "external_domain_dna").rglob("*.json"),
    ]
    body = "\n".join(path.read_text(encoding="utf-8") for path in searchable)
    assert "private_exponent" not in body.lower()
    assert "_TEST_ADMISSION_PRIVATE_EXPONENT_HEX" not in body
