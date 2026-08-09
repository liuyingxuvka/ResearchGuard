"""Executable root of the researchguard repository software-DNA model.

This model checks the repository's own model, code, test, and evidence
denominator. It reports readiness from current files; it does not recreate
the target software and it does not delegate the check to another agent.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"

REQUIRED_DEFINITION_FIELDS = (
    "schema_version",
    "blueprint_id",
    "inventory_id",
    "boundary",
    "scan_python_patterns",
    "scoped_out_patterns",
    "bounded_dynamic_prefixes",
    "dynamic_allowances",
    "dynamic_selector_contracts",
    "composite_behavior_contracts",
    "owner_overrides",
    "resource_groups",
    "claim_boundary",
)


@dataclass(frozen=True)
class SelfDnaInput:
    manifest_current: bool
    definition_current: bool
    mesh_current: bool
    owner_bindings_current: bool
    evidence_paths_current: bool


@dataclass(frozen=True)
class SelfDnaState:
    phase: str = "unverified"
    ready: bool = False


def evaluate_self_dna(inputs: SelfDnaInput) -> SelfDnaState:
    ready = all(
        (
            inputs.manifest_current,
            inputs.definition_current,
            inputs.mesh_current,
            inputs.owner_bindings_current,
            inputs.evidence_paths_current,
        )
    )
    return SelfDnaState(phase="ready" if ready else "blocked", ready=ready)


def _load_object(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain an object")
    return value


def check_blueprint_inputs(root: str | Path) -> dict[str, Any]:
    root_path = Path(root).resolve()
    manifest_path = root_path / ".flowguard/model-regression-manifest.json"
    definition_path = root_path / ".flowguard/authoritative_model_system/software_blueprint_definition.json"
    mesh_path = root_path / ".flowguard/authoritative_model_system/semantic_model_mesh.json"
    manifest = _load_object(manifest_path)
    definition = _load_object(definition_path)
    mesh = _load_object(mesh_path)
    rows = tuple(row for row in manifest.get("models", ()) if isinstance(row, Mapping))
    model_ids = tuple(str(row.get("model_id", "")) for row in rows)
    definition_current = tuple(definition) == REQUIRED_DEFINITION_FIELDS and definition.get("dynamic_selector_contracts") == []
    mesh_ids = tuple(str(row.get("model_id", "")) for row in mesh.get("models", ()) if isinstance(row, Mapping))
    manifest_current = bool(model_ids) and len(model_ids) == len(set(model_ids)) and "authoritative_model_system" in model_ids and "compositional_verification_kernel" in model_ids
    mesh_current = set(mesh_ids) == set(model_ids) and len(mesh_ids) == len(set(mesh_ids))
    owner_bindings_current = all(
        str(row.get("model_path", "")).startswith(".flowguard/")
        and str(row.get("runner", ("",))[-1]).endswith(".py")
        and isinstance(row.get("purpose_closure"), Mapping)
        for row in rows
    )
    evidence_paths_current = all(
        (root_path / str(row.get("model_path", ""))).is_file()
        and (root_path / str(row.get("runner", ("",))[-1])).is_file()
        for row in rows
    )
    state = evaluate_self_dna(
        SelfDnaInput(
            manifest_current=manifest_current,
            definition_current=definition_current,
            mesh_current=mesh_current,
            owner_bindings_current=owner_bindings_current,
            evidence_paths_current=evidence_paths_current,
        )
    )
    return {
        "status": state.phase,
        "ready": state.ready,
        "model_count": len(model_ids),
        "checks": {
            "manifest_current": manifest_current,
            "definition_current": definition_current,
            "mesh_current": mesh_current,
            "owner_bindings_current": owner_bindings_current,
            "evidence_paths_current": evidence_paths_current,
        },
    }


def run_model() -> None:
    good = evaluate_self_dna(SelfDnaInput(True, True, True, True, True))
    assert good.ready and good.phase == "ready"
    for index in range(5):
        values = [True] * 5
        values[index] = False
        candidate = evaluate_self_dna(SelfDnaInput(*values))
        assert not candidate.ready and candidate.phase == "blocked"


if __name__ == "__main__":
    run_model()
    print("authoritative_model_system: pass")
