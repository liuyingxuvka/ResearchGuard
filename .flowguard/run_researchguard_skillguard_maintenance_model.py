"""Run the ResearchGuard SkillGuard-maintenance FlowGuard model."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from flowguard.review import review_scenarios


MODEL_PATH = Path(__file__).with_name("researchguard_skillguard_maintenance_model.py")


def _load_model():
    spec = importlib.util.spec_from_file_location("researchguard_skillguard_maintenance_model", MODEL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load model from {MODEL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    sys.path.insert(0, str(MODEL_PATH.parent))
    spec.loader.exec_module(module)
    return module


def _review_mesh(model) -> list[str]:
    findings: list[str] = []
    members = set(model.MEMBERS)
    structure_children = model.STRUCTURE_MESH["children"]
    test_children = model.TEST_MESH["child_suites"]
    if {row["member_id"] for row in structure_children} != members:
        findings.append("StructureMesh does not cover exactly four members")
    if {row["member_id"] for row in test_children} != members:
        findings.append("TestMesh does not cover exactly four members")
    if len(model.DECLARED_CHECKS) != 8 or len(set(model.DECLARED_CHECKS)) != 8:
        findings.append("declared check inventory is not exactly eight unique ids")
    owned_checks = [check_id for row in test_children for check_id in row["owned_check_ids"]]
    if set(owned_checks) != set(model.DECLARED_CHECKS) or len(owned_checks) != 8:
        findings.append("TestMesh child ownership is incomplete or duplicated")
    if model.TEST_MESH["cross_unit_receipt_reuse"]:
        findings.append("cross-unit receipt reuse must remain disabled")
    if model.TEST_MESH["open_spec_is_test_evidence"]:
        findings.append("OpenSpec cannot be test evidence")
    if model.STRUCTURE_MESH["dependency_cycles"]:
        findings.append("maintenance structure contains a dependency cycle")
    if model.STRUCTURE_MESH["alternate_success_paths"]:
        findings.append("maintenance structure contains an alternate success path")
    return findings


def main() -> int:
    model = _load_model()
    scenario_report = review_scenarios(model.scenarios())
    mesh_findings = _review_mesh(model)
    print(scenario_report.format_text(max_counterexamples=5))
    print(
        json.dumps(
            {
                "artifact_kind": "researchguard_skillguard_maintenance_model_report",
                "status": "pass" if scenario_report.ok and not mesh_findings else "blocked",
                "scenario_count": len(model.scenarios()),
                "member_count": len(model.MEMBERS),
                "declared_check_count": len(model.DECLARED_CHECKS),
                "mesh_findings": mesh_findings,
                "claim_boundary": (
                    "This proves the modeled author-maintenance structure, order, and exact check inventory only. "
                    "Native check execution, consumer installation, publication, and predecessor retirement remain separate evidence domains."
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if scenario_report.ok and not mesh_findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
