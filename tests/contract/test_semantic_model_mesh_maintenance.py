"""Contract tests for the governed semantic mesh maintenance utility.

The tests copy the current mesh and manifest into a temporary repository.  No
test writes the canonical ResearchGuard mesh or any FlowGuard source file.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest


RESEARCHGUARD_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = RESEARCHGUARD_ROOT / "scripts" / "maintain_semantic_model_mesh.py"
FLOWGUARD_SOURCE = Path(r"D:\FlowGuard_20260427\flowguard\self_blueprint.py")
SOURCE_MESH = (
    RESEARCHGUARD_ROOT
    / ".flowguard"
    / "models"
    / "owners"
    / "authoritative_model_system"
    / "semantic_model_mesh.json"
)
SOURCE_MANIFEST = RESEARCHGUARD_ROOT / ".flowguard" / "models" / "regression-manifest.json"


def _load_maintenance_module():
    spec = importlib.util.spec_from_file_location("researchguard_semantic_mesh_maintenance", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


maintenance = _load_maintenance_module()


def _copy_repository(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "ResearchGuard"
    mesh_path = root / maintenance.SEMANTIC_MESH_RELATIVE_PATH
    manifest_path = root / maintenance.MANIFEST_RELATIVE_PATH
    mesh_path.parent.mkdir(parents=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE_MESH, mesh_path)
    shutil.copyfile(SOURCE_MANIFEST, manifest_path)
    return root, mesh_path


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _raw_fingerprint(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_candidate(root: Path, payload: dict, name: str = "candidate.json") -> Path:
    path = root / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def test_current_mesh_check_is_read_only_and_exposes_private_helper_boundary(tmp_path: Path) -> None:
    root, mesh_path = _copy_repository(tmp_path)
    before = mesh_path.read_bytes()

    result = maintenance.maintain_semantic_mesh(
        root,
        flowguard_source=FLOWGUARD_SOURCE,
        write=False,
    )

    assert result["ok"] is True
    assert result["mode"] == "check"
    assert result["relation_fingerprint_matches"] is True
    assert result["recomputed_relation_fingerprint"] == (
        "sha256:6ed39ee7657c505f22979d436171e40d58a4c82a800fe2b2389846473d6d5a78"
    )
    assert result["semantic_model_status"] == "candidate_defined_not_verified"
    assert result["whole_system_completion_claim"] == "not_licensed_until_current_terminal_evidence"
    assert result["flowguard_relation_hash_provenance"]["api_status"] == "private_non_public"
    assert result["flowguard_relation_hash_provenance"]["public_flowguard_writer_available"] is False
    assert result["output_path"] is None
    assert result["receipt_path"] is None
    assert mesh_path.read_bytes() == before
    assert not (mesh_path.parent / "semantic_model_mesh.maintained.json").exists()


def test_write_refreshes_relation_atomically_without_promoting_status(tmp_path: Path) -> None:
    root, mesh_path = _copy_repository(tmp_path)
    before_mesh = mesh_path.read_bytes()
    before_payload = _read_json(mesh_path)
    stale_payload = copy.deepcopy(before_payload)
    stale_payload["semantic_relation_fingerprint"] = (
        "sha256:cc7254b002b812aff4503744fd40d15605b9da20a4ab3e964261c1a0694e8ad9"
    )
    candidate_path = _write_candidate(root, stale_payload, name="stale-candidate.json")
    before_candidate = candidate_path.read_bytes()
    output_path = root / "out" / "semantic_model_mesh.json"
    receipt_path = root / "out" / "semantic_model_mesh.receipt.json"

    result = maintenance.maintain_semantic_mesh(
        root,
        candidate_mesh=candidate_path,
        flowguard_source=FLOWGUARD_SOURCE,
        output_mesh=output_path,
        receipt=receipt_path,
        expected_old_fingerprint=_raw_fingerprint(mesh_path),
        write=True,
    )

    assert result["ok"] is True
    # ``changed_fields`` is defined relative to the current mesh.  The current
    # mesh already carries the recomputed relation, so the repaired output is
    # semantically unchanged relative to it even though the explicit stale
    # candidate is repaired below.
    assert result["changed_fields"] == []
    assert result["status_transition"] is None
    assert mesh_path.read_bytes() == before_mesh
    assert candidate_path.read_bytes() == before_candidate
    output_payload = _read_json(output_path)
    receipt_payload = _read_json(receipt_path)
    assert stale_payload["semantic_relation_fingerprint"] == (
        "sha256:cc7254b002b812aff4503744fd40d15605b9da20a4ab3e964261c1a0694e8ad9"
    )
    assert output_payload["semantic_relation_fingerprint"] == result["recomputed_relation_fingerprint"]
    assert output_payload["semantic_relation_fingerprint"] != stale_payload["semantic_relation_fingerprint"]
    assert sorted(
        key for key in stale_payload if stale_payload[key] != output_payload[key]
    ) == ["semantic_relation_fingerprint"]
    assert output_payload["semantic_model_status"] == before_payload["semantic_model_status"]
    assert output_payload["whole_system_completion_claim"] == before_payload["whole_system_completion_claim"]
    assert receipt_payload["schema_version"] == maintenance.RECEIPT_SCHEMA
    assert receipt_payload["before_mesh_fingerprint"] == _raw_fingerprint(mesh_path)
    assert receipt_payload["after_output_fingerprint"] == _raw_fingerprint(output_path)
    assert receipt_payload["after_semantic_relation_fingerprint"] == result[
        "recomputed_relation_fingerprint"
    ]
    assert receipt_payload["status_transition"] is None
    assert receipt_payload["write_atomic"] is True
    assert receipt_payload["flowguard_relation_hash_provenance"]["api_status"] == "private_non_public"


def test_expected_old_fingerprint_mismatch_writes_nothing(tmp_path: Path) -> None:
    root, mesh_path = _copy_repository(tmp_path)
    output_path = root / "maintained.json"
    result = maintenance.maintain_semantic_mesh(
        root,
        flowguard_source=FLOWGUARD_SOURCE,
        output_mesh=output_path,
        expected_old_fingerprint="sha256:" + "0" * 64,
        write=True,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "expected_old_fingerprint_mismatch"
    assert not output_path.exists()


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("missing", "missing_model_ids"),
        ("foreign", "foreign_model_ids"),
        ("duplicate", "duplicate_model_id"),
    ],
)
def test_membership_and_identity_errors_fail_closed(
    tmp_path: Path,
    mutation: str,
    expected_code: str,
) -> None:
    root, mesh_path = _copy_repository(tmp_path)
    candidate = _read_json(mesh_path)
    if mutation == "missing":
        candidate["models"] = candidate["models"][:-1]
    elif mutation == "foreign":
        candidate["models"].append(copy.deepcopy(candidate["models"][0]))
        candidate["models"][-1]["model_id"] = "foreign_model"
        candidate["declared_model_count"] = len(candidate["models"])
    else:
        candidate["models"].append(copy.deepcopy(candidate["models"][0]))
        candidate["declared_model_count"] = len(candidate["models"])
    candidate_path = _write_candidate(root, candidate)

    with pytest.raises(maintenance.SemanticMeshMaintenanceError) as exc_info:
        maintenance.maintain_semantic_mesh(
            root,
            candidate_mesh=candidate_path,
            flowguard_source=FLOWGUARD_SOURCE,
            write=False,
        )

    assert exc_info.value.code == expected_code


def test_status_mutation_is_rejected_before_any_write(tmp_path: Path) -> None:
    root, mesh_path = _copy_repository(tmp_path)
    candidate = _read_json(mesh_path)
    candidate["semantic_model_status"] = "current"
    candidate_path = _write_candidate(root, candidate)
    output_path = root / "out.json"

    with pytest.raises(maintenance.SemanticMeshMaintenanceError) as exc_info:
        maintenance.maintain_semantic_mesh(
            root,
            candidate_mesh=candidate_path,
            output_mesh=output_path,
            flowguard_source=FLOWGUARD_SOURCE,
            expected_old_fingerprint=_raw_fingerprint(mesh_path),
            write=True,
        )

    assert exc_info.value.code == "status_mutation_not_allowed"
    assert not output_path.exists()
