"""Run the executable ResearchGuard FlowGuard model and topology checks."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from flowguard.review import review_scenarios


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = Path(__file__).with_name("researchguard_suite_model.py")
TOPOLOGY_PATH = Path(__file__).with_name("researchguard_suite_model.json")


def _load_model():
    spec = importlib.util.spec_from_file_location(
        "researchguard_suite_model",
        MODEL_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load model from {MODEL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _check_topology() -> list[str]:
    payload = json.loads(TOPOLOGY_PATH.read_text(encoding="utf-8"))
    findings: list[str] = []
    intents = payload.get("business_intents", [])
    if len(intents) != 5:
        findings.append("business intent inventory must contain exactly five rows")
    paths = [row.get("primary_path_id") for row in intents]
    if len(paths) != len(set(paths)):
        findings.append("primary paths must be unique")
    blocks = payload.get("function_blocks", [])
    if not blocks or any(row.get("alternate_success") is not False for row in blocks):
        findings.append("every FunctionBlock must forbid alternate success")
    invariants = set(payload.get("hard_invariants", []))
    required = {
        "one_distribution",
        "five_skill_surfaces_four_native_members",
        "same_suite_fingerprint",
        "source_bound_task_facts_do_not_set_applicability",
        "exact_four_current_member_derived_admissions",
        "exact_forbidden_condition_dispositions",
        "minimum_sufficient_member_set_covers_every_primary_responsibility",
        "one_sufficient_member_forbids_over_selection",
        "necessary_composition_has_exact_members_order_dependencies_responsibilities_handoffs_field_owners_and_claim_boundary",
        "zero_coverage_or_equal_minimum_ambiguity_blocks_without_lexical_fallback",
        "direct_member_bypasses_umbrella",
        "selected_member_only_prompt_load",
        "triggered_reference_required",
        "untriggered_reference_not_loaded",
        "direct_and_umbrella_same_primary_path",
        "selected_route_failure_is_terminal",
        "typed_handoff_requires_explicit_owner",
        "no_old_package",
        "no_old_cli",
        "no_old_skill_id",
        "no_forwarding_stub",
        "no_compatibility_reader",
        "no_fallback_route",
        "no_dual_output",
        "one_repository_software_dna_root",
        "four_recursive_member_subtrees",
        "provider_neutral_denominator",
        "seven_readiness_layers",
        "bidirectional_affected_indexes",
        "unknown_impact_blocks_without_full_scan",
        "mesh_store_uses_researchguard_package_identity",
        "predecessor_distribution_state_cannot_change_fingerprint",
        "no_predecessor_distribution_query",
    }
    missing = sorted(required - invariants)
    if missing:
        findings.append(f"missing hard invariants: {missing}")
    return findings


def _check_software_dna() -> dict[str, object]:
    sys.path.insert(0, str(ROOT / "src"))
    from researchguard.software_dna import check_software_dna_contract

    report = check_software_dna_contract(ROOT)
    return {
        "status": report.get("status"),
        "ready": report.get("ready"),
        "readiness": report.get("readiness", {}),
        "counts": report.get("counts", {}),
        "claim_boundary": "The runner consumes the native repository self-DNA report read-only; FlowGuard remains the canonical projection owner.",
    }


def main() -> int:
    model = _load_model()
    report = review_scenarios(model.scenarios())
    findings = _check_topology()
    software_dna = _check_software_dna()
    if not software_dna.get("ready"):
        findings.append("native software-DNA contract is not ready")
    print(report.format_text(max_counterexamples=3))
    print(
        json.dumps(
            {
                "artifact_kind": "researchguard_flowguard_model_report",
                "status": "pass" if report.ok and not findings else "blocked",
                "scenario_count": len(model.scenarios()),
                "topology_findings": findings,
                "software_dna": software_dna,
                "claim_boundary": (
                    "This proves the declared route/topology scenarios over the "
                    "current model only; native member tests remain required."
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.ok and not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
