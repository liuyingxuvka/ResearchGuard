from __future__ import annotations

from researchguard.software_dna import check_software_dna_contract


def test_repository_software_dna_contract() -> None:
    report = check_software_dna_contract(".")

    assert report["status"] == "ready"
    assert report["ready"] is True
    assert report["counts"] == {
        "models": 5,
        "function_blocks": 5,
        "code_bindings": 5,
        "test_bindings": 5,
        "evidence_bindings": 5,
        "child_interface_bindings": 4,
        "target_adapters": 4,
        "denominator_roots": 7,
    }
