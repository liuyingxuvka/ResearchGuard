from __future__ import annotations

import json
from pathlib import Path

from researchguard.software_dna import (
    READINESS_LAYERS,
    _readiness,
    build_provider_neutral_inventory,
    check_software_dna_contract,
    software_dna_affected_closure,
    software_dna_reverse_trace,
)


def test_repository_software_dna_contract() -> None:
    report = check_software_dna_contract(".")

    assert report["status"] == "ready"
    assert report["ready"] is True
    assert report["counts"]["top_level_models"] == 5
    assert report["counts"]["recursive_models"] == 12
    assert report["counts"]["models"] == 17
    assert report["counts"]["function_blocks"] == 20
    assert report["counts"]["code_bindings"] == 20
    assert report["counts"]["test_bindings"] == 20
    assert report["counts"]["child_interface_bindings"] == 16
    assert report["counts"]["target_adapters"] == 4
    assert report["counts"]["inventory_adapters"] == 7
    assert report["readiness"]["deepest_proven_layer"] == "static_blueprint_readiness"
    assert report["readiness"]["first_gap"] == ""


def test_provider_neutral_denominator_includes_non_python_surface() -> None:
    inventory = build_provider_neutral_inventory(".")

    assert inventory["ready"] is True
    assert {row["adapter_id"] for row in inventory["rows"]} == {
        "python",
        "json",
        "toml",
        "yaml",
        "markdown",
        "text",
        "binary_resource",
    }
    assert any(row["path"].endswith("workflow.yml") for row in inventory["rows"])
    assert inventory["counts"]["blocked"] == 0


def test_generated_runtime_outputs_cannot_enter_the_denominator() -> None:
    inventory = build_provider_neutral_inventory(".")
    paths = {row["path"] for row in inventory["rows"]}

    assert not any(path.startswith(".flowguard/evidence/") for path in paths)
    assert not any(path.startswith(".flowguard/model-mesh/") for path in paths)
    assert not any("/__pycache__/" in f"/{path}/" for path in paths)
    assert "models/software_dna/researchguard.json" in paths


def test_canonical_pointer_is_external_and_not_self_fingerprinted() -> None:
    payload = json.loads(Path("models/software_dna/researchguard.json").read_text(encoding="utf-8"))

    boundary = payload["canonical_boundary"]
    assert boundary["model_and_bindings"] == "native_repository_model_directory"
    assert boundary["current_pointer"] == "external_content_addressed_projection"
    assert boundary["generated_outputs_in_denominator"] is False
    assert boundary["self_fingerprint_cycle"] == "blocked"
    assert boundary["archive_self_authentication"] == "external_receipt_only"
    assert boundary["transport_evidence"] == "content_addressed_external"


def test_indexes_are_bidirectional_and_affected_only() -> None:
    report = check_software_dna_contract(".")
    indexes = report["indexes"]
    code_id = "code:src/researchguard/self_dna.py#check"

    assert indexes["reverse"][code_id] == ["block:researchguard-suite:check"]
    closure = software_dna_affected_closure(indexes, [code_id])
    assert closure["status"] == "ready"
    assert closure["mode"] == "affected_only"
    assert closure["full_denominator_materialized"] is False
    assert "block:researchguard-suite:check" in closure["affected_ids"]
    assert "logicguard" in closure["affected_ids"]
    assert "logicguard:blueprint" in closure["affected_ids"]


def test_unknown_affected_identity_blocks_without_widening() -> None:
    report = check_software_dna_contract(".")

    closure = software_dna_affected_closure(report["indexes"], ["unknown:surface"])

    assert closure["status"] == "blocked"
    assert closure["gap"]["code"] == "unknown_affected_identity"
    assert closure["affected_ids"] == []
    assert closure["full_denominator_materialized"] is False


def test_reverse_trace_rejects_unknown_identity() -> None:
    report = check_software_dna_contract(".")

    trace = software_dna_reverse_trace(report["indexes"], "unknown:surface")

    assert trace["status"] == "blocked"
    assert trace["gap"]["code"] == "unknown_reverse_identity"


def test_recursive_member_subtrees_are_not_a_fifth_sibling() -> None:
    payload = json.loads(Path("models/software_dna/researchguard.json").read_text(encoding="utf-8"))

    top = payload["models"]
    assert [row["model_id"] for row in top if not row.get("parent_model_id")] == ["researchguard-suite"]
    assert set(payload["models"][0]["child_model_ids"]) == {
        "logicguard",
        "sourceguard",
        "traceguard",
        "experimentguard",
    }
    assert all(row["children"] for row in payload["member_subtrees"])


def test_complete_logic_blueprint_is_current() -> None:
    # This is a model binding oracle; native semantic ownership stays in LogicGuard.
    report = check_software_dna_contract(".")
    assert report["indexes"]["reverse"]["native:logicguard"]


def test_readiness_reports_longest_prefix_and_stops_after_first_gap() -> None:
    statuses = {layer: (True, "") for layer in READINESS_LAYERS}
    statuses["traceability"] = (False, "binding_index_incomplete")

    readiness = _readiness(statuses)

    assert readiness["status"] == "blocked"
    assert readiness["deepest_proven_layer"] == "implementation_inventory"
    assert readiness["first_gap"] == "binding_index_incomplete"
    assert [row["status"] for row in readiness["layers"]] == [
        "pass",
        "pass",
        "blocked",
        "not_run",
        "not_run",
        "not_run",
        "not_run",
    ]
