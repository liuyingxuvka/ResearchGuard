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
from collections.abc import Mapping, Sequence
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


def _load_owner_models(root: Path, model) -> dict[str, Any]:
    """Load the registered owner modules used to define native contracts.

    The case mapping is intentionally derived from the checked-in model
    declarations.  This helper does not read a result and never promotes a
    result row into a declaration.
    """

    owners: dict[str, Any] = {str(model.MODEL_ID): model}
    for owner_id in model.CHILD_MODEL_IDS:
        owner_path = root / ".flowguard/models/owners" / owner_id / "model.py"
        spec = importlib.util.spec_from_file_location(
            f"rg_mapping_contract_{owner_id}", owner_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load owner model: {owner_path}")
        owner = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = owner
        spec.loader.exec_module(owner)
        owners[str(owner_id)] = owner
    return owners


def _strict_native_contracts(
    root: Path,
    model: Any,
    declared_cases: Sequence[tuple[str, str, str]],
) -> dict[str, tuple[Any, ...]]:
    """Materialize the exact native contracts used by strict verification.

    ``build_mapping`` remains coverage-only.  The strict path has a separate
    native contract so it can call FlowGuard's official native result oracle.
    Root cases are aggregate policy checks: a root runner passes when it
    observes a protected failure, while recursively registered child model
    runners report those bad cases as ``rejected``/``blocked``.  That
    distinction is declared here from the owner model, never inferred from a
    result row.
    """

    from flowguard.native_case_protocol import CASE_DIMENSIONS, NativeModelCaseContract

    owners = _load_owner_models(root, model)
    by_owner: dict[str, list[Any]] = {str(owner): [] for owner in owners}
    declared_owner_case_ids = {
        (str(owner_id), str(case_id))
        for owner_id, _parent_id, case_id in declared_cases
    }
    for owner_id, _parent_id, case_id in declared_cases:
        owner = owners.get(str(owner_id))
        if owner is None:
            raise ValueError(f"declared native case has unknown owner: {owner_id}")
        known_good = str(owner.KNOWN_GOOD_CASE_ID)
        boundary = f"boundary:{owner.MODEL_ID}"
        bad_to_failure = {
            str(case_id): str(failure_id)
            for case_id, failure_id in zip(
                owner.KNOWN_BAD_CASE_IDS,
                owner.PROTECTED_FAILURE_IDS,
            )
        }
        if case_id == known_good:
            case_kind = "good"
            expected_status = "pass"
            expected_observed_status = "pass"
        elif case_id == boundary:
            case_kind = "boundary"
            expected_status = "pass"
            expected_observed_status = "pass"
        elif case_id in bad_to_failure:
            case_kind = "bad"
            # The root runner's oracle records a successful observation of a
            # protected failure.  Native child runners instead expose the
            # rejected/blocked case directly.
            if str(owner_id) == str(model.MODEL_ID):
                expected_status = "pass"
                expected_observed_status = "pass"
            else:
                expected_status = "rejected"
                expected_observed_status = "blocked"
        else:
            raise ValueError(
                f"declared native case is not owned by its model: {owner_id}:{case_id}"
            )
        by_owner.setdefault(str(owner_id), []).append(
            NativeModelCaseContract(
                owner_id=f"model:{owner_id}",
                source_case_id=str(case_id),
                case_kind=case_kind,
                protected_failure_ids=(
                    (bad_to_failure[str(case_id)],)
                    if str(case_id) in bad_to_failure
                    else ()
                ),
                callable_ref=f"flowguard.model:{owner_id}.run_model",
                result_selector=f"native-case:{owner_id}:{case_id}",
                expected_status=expected_status,
                expected_observed_status=expected_observed_status,
                expected_finding_codes=(
                    (bad_to_failure[str(case_id)],)
                    if str(case_id) in bad_to_failure
                    else ()
                ),
                covered_dimensions=tuple(CASE_DIMENSIONS[case_kind]),
                oracle_member_ids=(f"{owner_id}:oracle",),
                evidence_scope="model_policy",
            )
        )
    if set(declared_owner_case_ids) != {
        (owner_id, contract.source_case_id)
        for owner_id, contracts in by_owner.items()
        for contract in contracts
    }:
        raise ValueError("strict native contract inventory does not match declarations")
    return {owner_id: tuple(contracts) for owner_id, contracts in by_owner.items()}


def _native_result_rows_from_payload(
    payload: Mapping[str, Any],
    *,
    context: str,
) -> tuple[tuple[Any, ...], tuple[str, ...]]:
    """Decode inline rows with the official FlowGuard row type.

    Strict verification accepts current protocol rows only.  In particular,
    the historical ``model_instance_*``/``receipt_*`` test doubles are not a
    compatible native result envelope.
    """

    from flowguard.native_case_protocol import (
        NATIVE_CASE_RESULT_SCHEMA,
        NativeModelCaseResult,
        NativeCaseProtocolError,
    )

    raw_rows = payload.get("results")
    if not isinstance(raw_rows, list):
        return (), ("results_not_list",)
    rows: list[Any] = []
    gaps: list[str] = []
    for index, raw_row in enumerate(raw_rows):
        if isinstance(raw_row, NativeModelCaseResult):
            rows.append(raw_row)
            continue
        if not isinstance(raw_row, Mapping):
            gaps.append(f"result_row_not_object:{index}")
            continue
        row_payload = dict(raw_row)
        if row_payload.pop("schema_version", None) != NATIVE_CASE_RESULT_SCHEMA:
            gaps.append(f"native_result_schema_invalid:{context}:{index}")
            continue
        try:
            rows.append(NativeModelCaseResult(**row_payload))
        except (NativeCaseProtocolError, TypeError, ValueError):
            gaps.append(f"native_result_row_invalid:{context}:{index}")
    return tuple(rows), tuple(gaps)


def _normalise_owner_id(value: object) -> str:
    text = str(value).strip()
    if text.startswith("validation-owner:model:"):
        return text.removeprefix("validation-owner:model:")
    if text.startswith("validation-owner:"):
        return text.removeprefix("validation-owner:")
    return text.removeprefix("model:")


def _native_result_rows_from_paths(
    native_result_paths: Mapping[str, str | Path],
    *,
    expected_owner_ids: Sequence[str],
    contracts_by_owner: Mapping[str, Sequence[Any]],
) -> tuple[tuple[Any, ...], dict[str, Any], tuple[str, ...]]:
    """Load and verify one official native envelope per declared owner."""

    from flowguard.native_case_protocol import (
        NativeCaseProtocolError,
        load_native_model_case_results,
        verify_native_model_cases,
    )

    expected = {str(item) for item in expected_owner_ids}
    normalised_paths: dict[str, Path] = {}
    gaps: list[str] = []
    for raw_owner, raw_path in native_result_paths.items():
        owner = _normalise_owner_id(raw_owner)
        if owner in normalised_paths:
            gaps.append(f"duplicate_native_result_owner:{owner}")
            continue
        normalised_paths[owner] = Path(raw_path).expanduser()
    foreign = sorted(set(normalised_paths) - expected)
    gaps.extend(f"foreign_native_result_owner:{owner}" for owner in foreign)
    missing = sorted(expected - set(normalised_paths))
    gaps.extend(f"native_result_artifact_missing:model:{owner}" for owner in missing)
    rows: list[Any] = []
    verification_by_owner: dict[str, Any] = {}
    for owner in sorted(expected & set(normalised_paths)):
        path = normalised_paths[owner]
        try:
            loaded = tuple(load_native_model_case_results(path))
        except (NativeCaseProtocolError, OSError, ValueError):
            gaps.append(f"native_result_artifact_invalid:model:{owner}")
            continue
        verification = verify_native_model_cases(
            tuple(contracts_by_owner[owner]),
            loaded,
            raw_artifact_root=path.resolve().parent,
            require_current_inputs=True,
        )
        verification_by_owner[owner] = verification.to_dict()
        gaps.extend(
            f"native:{owner}:{finding}"
            for finding in verification.findings
        )
        rows.extend(loaded)
    return tuple(rows), verification_by_owner, tuple(sorted(set(gaps)))


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
    root: str | Path | None = None,
    native_result_paths: Mapping[str, str | Path] | None = None,
) -> dict[str, Any]:
    """Verify native case results without changing the coverage mapping.

    ``build_mapping`` deliberately remains a coverage registry.  This
    separate gate consumes the official FlowGuard native result protocol and
    its raw artifacts/oracles.  A path map is the preferred input because it
    preserves each producer's raw-artifact boundary; inline rows are accepted
    only when they already carry the current protocol schema and an explicit
    shared raw-artifact root.  No receipt id, fingerprint, or terminal flag is
    filled in by this function.
    """

    from flowguard.native_case_protocol import (
        NativeCaseProtocolError,
        verify_native_model_cases,
    )

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

    # ``root`` is an explicit project boundary for the registered declarations
    # and is never read from the result payload.  Inline rows therefore cannot
    # redirect strict verification to a caller-selected model source.
    model_root = (
        Path(root).expanduser().resolve()
        if root is not None
        else Path(__file__).resolve().parents[1]
    )
    model = _load_model(model_root)
    declared_by_owner: dict[str, list[tuple[str, str]]] = {}
    for owner_id, parent_id, case_id in declared_cases:
        declared_by_owner.setdefault(str(owner_id), []).append(
            (str(parent_id), str(case_id))
        )
    contracts_by_owner = _strict_native_contracts(
        model_root,
        model,
        declared_cases,
    )
    expected_owners = tuple(sorted(declared_by_owner))
    rows: tuple[Any, ...] = ()
    native_verification: dict[str, Any] = {}
    if native_result_paths is not None:
        if not isinstance(native_result_paths, Mapping):
            gaps.append("native_result_paths_not_mapping")
        else:
            rows, native_verification, path_gaps = _native_result_rows_from_paths(
                native_result_paths,
                expected_owner_ids=expected_owners,
                contracts_by_owner=contracts_by_owner,
            )
            gaps.extend(path_gaps)
    else:
        rows, inline_gaps = _native_result_rows_from_payload(
            payload,
            context="inline",
        )
        gaps.extend(inline_gaps)
        raw_root_value = payload.get("raw_artifact_root")
        if not raw_root_value:
            gaps.append("native_raw_artifact_root_missing")
        else:
            raw_root = Path(str(raw_root_value)).expanduser().resolve()
            grouped: dict[str, list[Any]] = {}
            for row in rows:
                grouped.setdefault(_normalise_owner_id(row.owner_id), []).append(row)
            foreign_owners = sorted(set(grouped) - set(expected_owners))
            gaps.extend(
                f"foreign_native_result_owner:{owner}" for owner in foreign_owners
            )
            for owner in expected_owners:
                owner_rows = tuple(grouped.get(owner, ()))
                if not owner_rows:
                    gaps.append(f"native_result_missing:model:{owner}")
                    continue
                verification = verify_native_model_cases(
                    tuple(contracts_by_owner[owner]),
                    owner_rows,
                    raw_artifact_root=raw_root,
                    require_current_inputs=True,
                )
                native_verification[owner] = verification.to_dict()
                gaps.extend(
                    f"native:{owner}:{finding}"
                    for finding in verification.findings
                )

    expected_keys = {
        (f"model:{owner_id}", case_id)
        for owner_id, owner_cases in declared_by_owner.items()
        for _parent_id, case_id in owner_cases
    }
    actual_keys = {(str(row.owner_id), str(row.source_case_id)) for row in rows}
    gaps.extend(
        f"native_case_missing:{owner}:{case_id}"
        for owner, case_id in sorted(expected_keys - actual_keys)
    )
    gaps.extend(
        f"foreign_native_case:{owner}:{case_id}"
        for owner, case_id in sorted(actual_keys - expected_keys)
    )
    if expected_source_revision is not None and payload.get("source_revision") != expected_source_revision:
        gaps.append("source_revision_mismatch")
    child_ids = payload.get("child_receipt_ids")
    expected_children = sorted(
        {owner for owner, _parent, _case in declared_cases if owner != "researchguard_suite"}
    )
    normalised_child_ids = (
        [_normalise_owner_id(value) for value in child_ids]
        if isinstance(child_ids, list)
        else []
    )
    if (
        not isinstance(child_ids, list)
        or len(normalised_child_ids) != len(set(normalised_child_ids))
        or sorted(normalised_child_ids) != expected_children
    ):
        gaps.append("parent_child_closure_mismatch")
    return {
        "status": "pass" if not gaps else "blocked",
        "strict_self_dna_status": "pass" if not gaps else "blocked",
        "gaps": sorted(set(gaps)),
        "native_verification": native_verification,
        "verified_native_case_count": len(rows),
        "claim_boundary": "Strict local execution envelope identity, oracle, and parent closure only; native model semantics remain owner-scoped.",
    }


def verify_strict_parent_execution(
    parent: dict[str, Any],
    children: list[dict[str, Any]],
    expected_child_model_ids: list[str],
    *,
    repository_root: str | Path | None = None,
    receipt_root: str | Path | None = None,
) -> dict[str, Any]:
    """Verify a parent/child envelope against FlowGuard's current receipt API.

    The compact parent artifact is only a locator for the official immutable
    receipts.  A set of non-empty ids/fingerprints is therefore never enough
    for a pass: callers must supply the repository and receipt roots so
    ``resolve_current_full_model_regression_parent`` can reopen and verify the
    exact current parent and every child.  This keeps a resigned caller
    envelope visibly blocked instead of treating its self-hashes as evidence.
    """

    from flowguard.model_regressions import (
        resolve_current_full_model_regression_parent,
    )

    gaps: list[str] = []
    if not isinstance(parent, Mapping):
        return {
            "status": "blocked",
            "strict_self_dna_status": "blocked",
            "gaps": ["parent_not_mapping"],
            "claim_boundary": "Official current FlowGuard parent/child receipt closure only; case-level oracle semantics remain native-owner evidence.",
        }
    if not isinstance(children, list):
        gaps.append("children_not_list")
        children = []
    expected_list = [_normalise_owner_id(item) for item in expected_child_model_ids]
    expected = set(expected_list)
    if len(expected_list) != len(expected):
        gaps.append("expected_child_model_ids_duplicate")

    wrapper_parent = bool(parent.get("execution_receipt_id"))
    if wrapper_parent:
        if parent.get("status") != "pass":
            gaps.append("parent_status_not_pass")
        if not parent.get("execution_receipt_id"):
            gaps.append("parent_execution_receipt_id_missing")
        if not parent.get("execution_receipt_fingerprint"):
            gaps.append("parent_execution_receipt_fingerprint_missing")
    else:
        if parent.get("result_status") != "pass":
            gaps.append("parent_result_status_not_pass")
        if parent.get("exit_code") != 0:
            gaps.append("parent_exit_code_not_zero")
        if not parent.get("receipt_id"):
            gaps.append("parent_receipt_id_missing")
        if not parent.get("result_fingerprint"):
            gaps.append("parent_result_fingerprint_missing")
        if not parent.get("proof_artifact_fingerprint"):
            gaps.append("parent_proof_fingerprint_missing")

    seen: set[str] = set()
    for child in children:
        if not isinstance(child, Mapping):
            gaps.append("child_not_mapping")
            continue
        subject = str(child.get("subject_id", child.get("model_id", "")))
        model_id = _normalise_owner_id(subject)
        if not model_id or model_id not in expected:
            gaps.append(f"foreign_child:{model_id}")
        if model_id in seen:
            gaps.append(f"duplicate_child:{model_id}")
        seen.add(model_id)
        if "result_status" in child and child.get("result_status") != "pass":
            gaps.append(f"child_result_status_not_pass:{model_id}")
        if "exit_code" in child and child.get("exit_code") != 0:
            gaps.append(f"child_exit_code_not_zero:{model_id}")
        for field in ("receipt_id", "receipt_fingerprint"):
            if not child.get(field):
                gaps.append(f"child_{field}_missing:{model_id}")
        # A direct EvidenceReceipt projection may carry these fields.  The
        # model-parent artifact intentionally omits them; official resolution
        # below obtains them from the immutable store in that form.
        if not wrapper_parent:
            for field in ("producer_id", "producer_version"):
                if not child.get(field):
                    gaps.append(f"child_{field}_missing:{model_id}")
    if seen != expected: gaps.append("child_model_closure_mismatch")

    if "required_child_receipts" in parent or "consumed_child_receipts" in parent:
        required_rows = parent.get("required_child_receipts", ())
        consumed_rows = parent.get("consumed_child_receipts", ())
        if not isinstance(required_rows, list) or not isinstance(consumed_rows, list):
            gaps.append("parent_child_receipt_lists_invalid")
        else:
            listed = {
                str(row.get("receipt_id", ""))
                for row in required_rows
                if isinstance(row, Mapping)
            }
            actual = {
                str(row.get("receipt_id", ""))
                for row in consumed_rows
                if isinstance(row, Mapping)
            }
            child_ids = {
                str(row.get("receipt_id", ""))
                for row in children
                if isinstance(row, Mapping)
            }
            if listed != actual or listed != child_ids:
                gaps.append("parent_consumed_required_receipts_mismatch")

    official_parent: dict[str, Any] = {"status": "not_run"}
    if repository_root is None or receipt_root is None:
        gaps.append("official_current_receipt_store_required")
    elif not gaps:
        try:
            resolved = resolve_current_full_model_regression_parent(
                Path(repository_root).expanduser().resolve(),
                receipt_dir=Path(receipt_root).expanduser().resolve(),
            )
        except Exception as exc:  # FlowGuard exposes typed errors by version.
            official_parent = {
                "status": "blocked",
                "error": f"{type(exc).__name__}: {exc}",
            }
            gaps.append("official_current_parent_resolution_blocked")
        else:
            resolved_children = {
                item.model_id: item
                for item in resolved.children
            }
            official_parent = {
                "status": "pass",
                "manifest_fingerprint": resolved.manifest_fingerprint,
                "parent_execution_receipt_id": resolved.parent_execution_receipt_id,
                "parent_execution_receipt_fingerprint": resolved.parent_execution_receipt_fingerprint,
                "child_model_ids": sorted(resolved_children),
            }
            if set(resolved_children) != expected:
                gaps.append("official_child_model_closure_mismatch")
            declared_parent_id = str(
                parent.get("execution_receipt_id", parent.get("receipt_id", ""))
            )
            declared_parent_fingerprint = str(
                parent.get(
                    "execution_receipt_fingerprint",
                    parent.get("receipt_fingerprint", ""),
                )
            )
            if declared_parent_id and declared_parent_id != resolved.parent_execution_receipt_id:
                gaps.append("parent_receipt_identity_mismatch")
            if (
                declared_parent_fingerprint
                and declared_parent_fingerprint
                != resolved.parent_execution_receipt_fingerprint
            ):
                gaps.append("parent_receipt_fingerprint_mismatch")
            for child in children:
                if not isinstance(child, Mapping):
                    continue
                model_id = _normalise_owner_id(
                    child.get("subject_id", child.get("model_id", ""))
                )
                current = resolved_children.get(model_id)
                if current is None:
                    continue
                if child.get("receipt_id") != current.receipt_id:
                    gaps.append(f"child_receipt_identity_mismatch:{model_id}")
                if child.get("receipt_fingerprint") != current.receipt_fingerprint:
                    gaps.append(f"child_receipt_fingerprint_mismatch:{model_id}")

    return {
        "status": "pass" if not gaps else "blocked",
        "strict_self_dna_status": "pass" if not gaps else "blocked",
        "gaps": sorted(set(gaps)),
        "official_parent": official_parent,
        "claim_boundary": "Official current FlowGuard parent/child receipt closure only; case-level oracle semantics remain native-owner evidence.",
    }


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
