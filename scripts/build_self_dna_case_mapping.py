"""Build the deterministic ResearchGuard self-DNA case mapping registry.

The registry is derived from the registered suite model and its native case
result envelope.  It intentionally does not infer coverage from a static
blueprint: every mapped case must have a native result row, and every result
row must map back to exactly one declared case.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


def _load_model(root: Path):
    path = root / ".flowguard/models/owners/researchguard_suite/model.py"
    spec = importlib.util.spec_from_file_location("rg_mapping_model", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load registered model: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _declared_cases(root: Path, model) -> list[tuple[str, str, str]]:
    """Return every parent and child case from the registered native owners."""
    owners = [(model.MODEL_ID, model.ROOT_STRUCTURAL_PARENT_ID)]
    owners.extend((child, model.SEMANTIC_PARENT_BY_CHILD.get(child, model.ROOT_STRUCTURAL_PARENT_ID)) for child in model.CHILD_MODEL_IDS)
    declared: list[tuple[str, str, str]] = []
    for owner_id, parent_id in owners:
        owner_path = root / ".flowguard/models/owners" / owner_id / "model.py"
        if owner_id == model.MODEL_ID:
            owner = model
        else:
            spec = importlib.util.spec_from_file_location(f"rg_mapping_{owner_id}", owner_path)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"cannot load owner model: {owner_path}")
            owner = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = owner
            spec.loader.exec_module(owner)
        cases = (owner.KNOWN_GOOD_CASE_ID, f"boundary:{owner.MODEL_ID}", *owner.KNOWN_BAD_CASE_IDS)
        declared.extend((owner_id, parent_id, case_id) for case_id in cases)
    return declared


def build_mapping(root: Path, result_path: Path | None = None) -> dict[str, Any]:
    model = _load_model(root)
    model.run_model()
    declared_cases = _declared_cases(root, model)
    case_ids = [case_id for _owner, _parent, case_id in declared_cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("declared self-DNA case IDs are not unique")
    nodes = (model.MODEL_ID, *model.CHILD_MODEL_IDS)
    if len(nodes) != 10 or len(nodes) != len(set(nodes)):
        raise ValueError("self-DNA node registry must contain ten unique owners")
    result_rows: list[dict[str, Any]] = []
    if result_path and result_path.exists():
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        result_rows = [row for row in payload.get("results", ()) if isinstance(row, dict)]
    by_case: dict[str, list[dict[str, Any]]] = {}
    for row in result_rows:
        by_case.setdefault(str(row.get("source_case_id", "")), []).append(row)
    cases = []
    for owner_id, parent_id, case_id in declared_cases:
        rows = by_case.get(case_id, [])
        cases.append({
            "behavior_id": f"behavior:{owner_id}:{case_id}",
            "case_id": case_id,
            "owner_id": f"model:{owner_id}",
            "parent_id": parent_id if str(parent_id).startswith("semantic-parent:") else f"semantic-parent:{parent_id}",
            "result_count": len(rows),
            "execution_status": "pass" if len(rows) == 1 and rows[0].get("observed_status") in {"pass", "blocked"} else "missing",
            "observed_statuses": sorted({str(row.get("observed_status", "")) for row in rows}),
        })
    result_case_ids = [str(row.get("source_case_id", "")) for row in result_rows]
    declared = set(case_ids)
    mapping = {
        "schema_version": "researchguard.self_dna_case_mapping.v1",
        "model_id": model.MODEL_ID,
        "nodes": [{"model_id": node, "parent_id": model.SEMANTIC_PARENT_BY_CHILD.get(node, model.ROOT_STRUCTURAL_PARENT_ID if node != model.MODEL_ID else model.ROOT_STRUCTURAL_PARENT_ID)} for node in nodes],
        "semantic_relations": [{"source_model_id": source, "target_model_id": target} for source, target in model.SEMANTIC_RELATION_EDGES],
        "cases": cases,
        "foreign_case_ids": sorted(set(result_case_ids) - declared),
        "orphan_case_ids": sorted(declared - set(result_case_ids)),
        "duplicate_case_ids": sorted(case_id for case_id, rows in by_case.items() if case_id in declared and len(rows) != 1),
        "claim_boundary": "Local deterministic mapping and native result reconciliation only; it does not qualify external-domain DNA.",
    }
    mapping["status"] = "pass" if not mapping["foreign_case_ids"] and not mapping["orphan_case_ids"] and not mapping["duplicate_case_ids"] and all(row["execution_status"] != "missing" for row in cases) else "blocked"
    return mapping


def verify_strict_execution(
    payload: dict[str, Any],
    declared_cases: list[tuple[str, str, str]],
    *,
    expected_source_revision: str | None = None,
) -> dict[str, Any]:
    """Verify an executed native envelope without changing coverage mapping.

    ``build_mapping`` deliberately remains a case-coverage registry.  This
    separate verifier consumes a native envelope and requires the identity
    and terminal fields that make an execution result admissible.  It does
    not manufacture or repair those fields.
    """
    gaps: list[str] = []
    if payload.get("status") != "pass":
        gaps.append("top_level_status_not_pass")
    if payload.get("ok") is not True:
        gaps.append("top_level_ok_not_true")
    if payload.get("exit_code") != 0:
        gaps.append("top_level_exit_code_not_zero")
    if payload.get("terminal") is not True:
        gaps.append("top_level_terminal_not_true")
    if payload.get("cleanup_confirmed") is not True:
        gaps.append("top_level_cleanup_not_confirmed")
    rows = payload.get("results")
    if not isinstance(rows, list):
        return {"status": "blocked", "gaps": [*gaps, "results_not_list"]}
    expected = {case_id: (owner, parent) for owner, parent, case_id in declared_cases}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if isinstance(row, dict):
            grouped.setdefault(str(row.get("source_case_id", "")), []).append(row)
        else:
            gaps.append("result_row_not_object")
    for case_id, (owner, _parent) in expected.items():
        matches = grouped.get(case_id, [])
        if len(matches) != 1:
            gaps.append(f"case_cardinality:{case_id}")
            continue
        row = matches[0]
        if row.get("owner_id") not in {owner, f"model:{owner}"}:
            gaps.append(f"owner_mismatch:{case_id}")
        for field in (
            "model_instance_id", "model_instance_fingerprint",
            "input_inventory_fingerprint", "result_fingerprint",
            "receipt_id", "receipt_fingerprint", "runner_fingerprint",
        ):
            if not row.get(field):
                gaps.append(f"missing_{field}:{case_id}")
        if row.get("observed_status") not in {"pass", "blocked"}:
            gaps.append(f"invalid_observed_status:{case_id}")
        expected_status = row.get("expected_observed_status")
        if expected_status is not None and row.get("observed_status") != expected_status:
            gaps.append(f"oracle_mismatch:{case_id}")
    foreign = sorted(set(grouped) - set(expected))
    gaps.extend(f"foreign_case:{case_id}" for case_id in foreign)
    if expected_source_revision is not None and payload.get("source_revision") != expected_source_revision:
        gaps.append("source_revision_mismatch")
    child_ids = payload.get("child_receipt_ids")
    expected_children = sorted({owner for owner, _parent, _case in declared_cases if owner != "researchguard_suite"})
    if not isinstance(child_ids, list) or sorted(set(child_ids)) != expected_children:
        gaps.append("parent_child_closure_mismatch")
    return {
        "status": "pass" if not gaps else "blocked",
        "strict_self_dna_status": "pass" if not gaps else "blocked",
        "gaps": sorted(set(gaps)),
        "claim_boundary": "Strict local execution envelope identity, oracle, and parent closure only; native model semantics remain owner-scoped.",
    }


def verify_strict_parent_execution(
    parent: dict[str, Any],
    children: list[dict[str, Any]],
    expected_child_model_ids: list[str],
) -> dict[str, Any]:
    """Adapt the native FlowGuard parent/child receipt envelope.

    Native receipts use ``result_status`` and ``consumed_child_receipts``;
    they do not expose the compact per-case fields consumed by the coverage
    mapping.  This adapter validates the native identity/terminal/closure
    contract without pretending that it is a case mapping.
    """
    gaps: list[str] = []
    if parent.get("result_status") != "pass": gaps.append("parent_result_status_not_pass")
    if parent.get("exit_code") != 0: gaps.append("parent_exit_code_not_zero")
    if not parent.get("receipt_id"): gaps.append("parent_receipt_id_missing")
    if not parent.get("result_fingerprint"): gaps.append("parent_result_fingerprint_missing")
    if not parent.get("proof_artifact_fingerprint"): gaps.append("parent_proof_fingerprint_missing")
    expected = set(expected_child_model_ids)
    seen: set[str] = set()
    for child in children:
        subject = str(child.get("subject_id", ""))
        model_id = subject.removeprefix("validation-owner:model:")
        if model_id not in expected: gaps.append(f"foreign_child:{model_id}")
        seen.add(model_id)
        if child.get("result_status") != "pass": gaps.append(f"child_result_status_not_pass:{model_id}")
        if child.get("exit_code") != 0: gaps.append(f"child_exit_code_not_zero:{model_id}")
        for field in ("receipt_id", "result_fingerprint", "proof_artifact_fingerprint", "producer_id", "producer_version"):
            if not child.get(field): gaps.append(f"child_{field}_missing:{model_id}")
    if seen != expected: gaps.append("child_model_closure_mismatch")
    listed = {str(x.get("receipt_id", "")) for x in parent.get("required_child_receipts", []) if isinstance(x, dict)}
    actual = {str(x.get("receipt_id", "")) for x in parent.get("consumed_child_receipts", []) if isinstance(x, dict)}
    if listed != actual: gaps.append("parent_consumed_required_receipts_mismatch")
    return {"status": "pass" if not gaps else "blocked", "strict_self_dna_status": "pass" if not gaps else "blocked", "gaps": sorted(set(gaps)), "claim_boundary": "Native FlowGuard parent/child receipt identity and closure only; case-level oracle semantics remain native-owner evidence."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--results")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    mapping = build_mapping(root, Path(args.results).resolve() if args.results else None)
    text = json.dumps(mapping, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        Path(args.output).resolve().write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if mapping["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
