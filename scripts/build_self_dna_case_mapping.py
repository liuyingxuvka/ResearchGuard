"""Build the deterministic ResearchGuard self-DNA case mapping registry.

The registry is derived from the registered suite model and its native case
result envelope.  It intentionally does not infer coverage from a static
blueprint: every mapped case must have a native result row, and every result
row must map back to exactly one declared case.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
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


_MODEL_EXECUTION_EVIDENCE_SCHEMA = "flowguard.model_execution_evidence.v1"


def _is_sha256(value: object) -> bool:
    """Return whether a value is one canonical content fingerprint."""

    if not isinstance(value, str) or len(value) != len("sha256:") + 64:
        return False
    return value.startswith("sha256:") and all(
        character in "0123456789abcdef"
        for character in value.removeprefix("sha256:")
    )


def _load_json_mapping(path: Path, *, description: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{description} is unreadable: {path}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"{description} must contain a JSON object: {path}")
    return payload


def _execution_evidence_from_payload(
    payload: Mapping[str, Any],
) -> Mapping[str, Any]:
    if payload.get("status") in {"blocked", "invalid", "incomplete"} or (
        payload.get("ok") is False
    ):
        findings = payload.get("findings")
        raw_findings = findings if isinstance(findings, list) else ()
        detail = ", ".join(
            str(item.get("code", item)) if isinstance(item, Mapping) else str(item)
            for item in raw_findings
        )
        raise ValueError(
            "self-blueprint output is blocked/incomplete"
            + (f": {detail}" if detail else "")
        )
    execution = payload.get("execution_evidence")
    if not isinstance(execution, Mapping):
        raise ValueError("self-blueprint evidence lacks execution_evidence")
    if execution.get("schema_version") != _MODEL_EXECUTION_EVIDENCE_SCHEMA:
        raise ValueError(
            "self-blueprint execution_evidence has unsupported schema: "
            f"{execution.get('schema_version')!r}"
        )
    return execution


def _current_manifest_fingerprint(root: Path) -> str:
    from flowguard.source_identity import source_file_fingerprint

    return source_file_fingerprint(
        root / ".flowguard" / "models" / "regression-manifest.json"
    )


def _current_manifest_functional_fingerprint(root: Path) -> str:
    """Return FlowGuard's functional identity for the model manifest.

    The official model-regression/self-blueprint path deliberately excludes
    execution-budget fields such as ``timeout_seconds`` from its functional
    input identity.  The native mapping registry, however, stores the raw
    source-file identity so its loader can detect byte-level drift.  Both
    identities must be checked at this boundary: accepting only the raw hash
    rejects an otherwise valid official self-blueprint, while accepting only
    the functional hash would make the registry unable to bind its source.
    """

    from flowguard.source_identity import functional_source_fingerprint

    return functional_source_fingerprint(
        root,
        ".flowguard/models/regression-manifest.json",
    )


def _assert_execution_manifest_alignment(
    root: Path,
    execution: Mapping[str, Any],
) -> str:
    """Reject evidence produced from a different regression manifest.

    The official self-blueprint keeps the parent manifest identity in its
    execution package, while the typed native mapping stores the current
    source manifest identity.  They are one freshness edge and must agree
    before a mapping can be emitted or loaded.
    """

    observed = execution.get("manifest_fingerprint")
    current = _current_manifest_fingerprint(root)
    functional_current = _current_manifest_functional_fingerprint(root)
    if not _is_sha256(observed) or observed not in {current, functional_current}:
        raise ValueError(
            "source/manifest mismatch: "
            f"execution_evidence={observed!r}; current_manifest={current!r}; "
            f"functional_manifest={functional_current!r}"
        )
    return current


def _assert_execution_summary(
    execution: Mapping[str, Any],
    *,
    expected_owner_ids: Sequence[str],
    expected_case_count: int,
) -> None:
    expected_owners = {str(item) for item in expected_owner_ids}
    if execution.get("status") != "passed" or execution.get("complete") is not True:
        raise ValueError(
            "execution_evidence is blocked: status/complete is not passed/true"
        )
    if execution.get("owner_count") != len(expected_owners):
        raise ValueError("execution_evidence owner_count does not match declarations")
    if execution.get("planned_case_count") != expected_case_count:
        raise ValueError("execution_evidence planned_case_count does not match declarations")
    if execution.get("executed_case_count") != expected_case_count:
        raise ValueError("execution_evidence executed_case_count does not match declarations")
    if execution.get("coverage_edge_count") != 6 * expected_case_count:
        raise ValueError("execution_evidence coverage_edge_count does not match six dimensions per case")
    for field in ("missing_case_ids", "foreign_case_ids"):
        values = execution.get(field)
        if not isinstance(values, list) or values:
            raise ValueError(f"execution_evidence {field} is not empty")
    if execution.get("receipt_gap_count") != 0:
        raise ValueError("execution_evidence receipt gaps are present")
    if execution.get("native_case_protocol_gap_count") != 0:
        raise ValueError("execution_evidence native protocol gaps are present")


def _validate_owner_execution_rows(
    owner_rows: Sequence[Mapping[str, Any]],
    *,
    expected_owner_ids: Sequence[str],
    declared_case_ids_by_owner: Mapping[str, Sequence[str]],
    blueprint_cases: Mapping[str, Sequence[str]],
) -> None:
    """Validate the official owner projection before opening raw artifacts."""

    expected = {str(item) for item in expected_owner_ids}
    seen: set[str] = set()
    for index, item in enumerate(owner_rows):
        raw_owner = item.get("model_id")
        if raw_owner is None:
            raw_owner = item.get("owner_id")
        if not isinstance(raw_owner, str) or not raw_owner.strip():
            raise ValueError(f"self-blueprint owner row {index} lacks owner identity")
        owner = _normalise_owner_id(raw_owner)
        if owner in seen:
            raise ValueError(f"duplicate self-blueprint owner: {owner}")
        seen.add(owner)
        if owner not in expected:
            raise ValueError(f"foreign self-blueprint owner: {owner}")

        required = item.get("required_case_ids")
        if not isinstance(required, list) or not required or not all(
            isinstance(case_id, str) and case_id.strip() == case_id and case_id
            for case_id in required
        ):
            raise ValueError(f"self-blueprint required_case_ids invalid for {owner}")
        if tuple(required) != tuple(blueprint_cases[owner]):
            raise ValueError(f"self-blueprint required case projection changed for {owner}")
        if set(required) != set(item.get("executed_behavior_case_ids", ())):
            raise ValueError(
                f"self-blueprint executed_behavior_case_ids mismatch for {owner}"
            )
        if len(required) != len(declared_case_ids_by_owner[owner]):
            raise ValueError(f"self-blueprint case count mismatch for {owner}")

        for field in ("receipt_id", "receipt_fingerprint"):
            value = item.get(field)
            if not value or (field.endswith("fingerprint") and not _is_sha256(value)):
                raise ValueError(f"self-blueprint owner {owner} lacks valid {field}")
        for field in (
            "complete",
            "receipt_is_direct_leaf",
            "receipt_is_current_pass",
            "native_case_results_required",
        ):
            if item.get(field) is not True:
                raise ValueError(f"self-blueprint owner {owner} is not a complete direct leaf")
        # ``build_flowguard_self_blueprint`` consumes the exact current full
        # parent and therefore projects each already-verified direct child as
        # ``reuse_current``.  That is still execution evidence: the supplied
        # receipt store is reopened below and its supervised producer proof is
        # checked byte-for-byte.  A marker-only or no-store reuse remains
        # blocked by ``_validate_owner_runner_and_cleanup``.
        if item.get("execution_disposition") not in {"execute", "reuse_current"}:
            raise ValueError(f"self-blueprint owner {owner} was not executed or current-reused")
        if item.get("finding_codes") not in ([], ()):
            raise ValueError(f"self-blueprint owner {owner} has finding codes")
        for field in ("missing_case_ids", "foreign_case_ids"):
            values = item.get(field)
            if values not in ([], ()):
                raise ValueError(f"self-blueprint owner {owner} has {field}")

        native_results = item.get("native_case_results")
        if not isinstance(native_results, list):
            raise ValueError(f"self-blueprint owner {owner} lacks native case rows")
        result_path = item.get("native_case_result_artifact_path")
        if not isinstance(result_path, str) or not result_path.strip():
            raise ValueError(f"self-blueprint owner {owner} lacks native result artifact path")
        if not _is_sha256(item.get("native_case_result_artifact_fingerprint")):
            raise ValueError(f"self-blueprint owner {owner} lacks native artifact fingerprint")
        verification = item.get("native_case_verification")
        if not isinstance(verification, Mapping) or verification.get("ok") is not True:
            raise ValueError(f"self-blueprint owner {owner} native verification is not passing")
        if any(
            verification.get(field) not in ([], ())
            for field in (
                "findings",
                "missing_case_ids",
                "foreign_case_ids",
                "duplicate_case_ids",
                "unasserted_dimensions",
            )
        ):
            raise ValueError(f"self-blueprint owner {owner} native verification has gaps")
        binding_verification = item.get("native_case_binding_verification")
        if binding_verification is not None and (
            not isinstance(binding_verification, Mapping)
            or binding_verification.get("ok") is not True
            or binding_verification.get("findings") not in ([], ())
        ):
            raise ValueError(f"self-blueprint owner {owner} binding verification is blocked")

    if seen != expected:
        missing = sorted(expected - seen)
        foreign = sorted(seen - expected)
        detail = []
        if missing:
            detail.append("missing=" + ",".join(missing))
        if foreign:
            detail.append("foreign=" + ",".join(foreign))
        raise ValueError("self-blueprint owner closure mismatch: " + "; ".join(detail))


def _infer_receipt_directory(native_result_paths: Mapping[str, Path]) -> Path | None:
    candidates = {
        path.resolve().parents[2] / "receipt-store"
        for path in native_result_paths.values()
    }
    if len(candidates) == 1:
        candidate = next(iter(candidates))
        if candidate.is_dir():
            return candidate
    return None


def _assert_native_artifact_identities(
    owner_rows: Sequence[Mapping[str, Any]],
    *,
    native_result_paths: Mapping[str, Path],
) -> None:
    """Require each evidence row to name the exact native envelope bytes."""

    for item in owner_rows:
        raw_owner = item.get("model_id")
        if raw_owner is None:
            raw_owner = item.get("owner_id")
        owner = _normalise_owner_id(raw_owner)
        path = native_result_paths.get(owner)
        if path is None or path.is_symlink() or not path.is_file():
            raise ValueError(f"native result artifact is unavailable for {owner}")
        actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != item.get("native_case_result_artifact_fingerprint"):
            raise ValueError(f"native result artifact fingerprint mismatch for {owner}")


def _assert_owner_receipt_proof(
    root: Path,
    *,
    owner: str,
    owner_row: Mapping[str, Any],
    native_result_path: Path,
    receipt_root: Path,
) -> None:
    """Reopen the exact leaf receipt and prove runner/cleanup identity."""

    from flowguard.validation_ownership import load_evidence_receipt

    try:
        receipt = load_evidence_receipt(
            str(owner_row["receipt_id"]),
            root,
            output_directory=receipt_root,
        )
    except (OSError, ValueError) as exc:
        raise ValueError(f"owner receipt cannot be reopened for {owner}: {exc}") from exc
    if receipt.fingerprint != owner_row.get("receipt_fingerprint"):
        raise ValueError(f"owner receipt fingerprint mismatch for {owner}")
    if (
        receipt.result_status != "pass"
        or receipt.exit_code != 0
        or receipt.required_child_receipts
        or receipt.consumed_child_receipts
        or receipt.skipped_checks
        or receipt.blockers
    ):
        raise ValueError(f"owner receipt is not a direct terminal pass for {owner}")
    proof_relpath = str(receipt.metadata.get("proof_relpath", ""))
    if not proof_relpath:
        raise ValueError(f"owner receipt proof locator is missing for {owner}")
    proof_path = (receipt_root / proof_relpath).resolve()
    if receipt_root not in proof_path.parents or not proof_path.is_file():
        raise ValueError(f"owner receipt proof is unavailable for {owner}")
    proof_fingerprint = "sha256:" + hashlib.sha256(proof_path.read_bytes()).hexdigest()
    if proof_fingerprint != receipt.proof_artifact_fingerprint:
        raise ValueError(f"owner proof fingerprint mismatch for {owner}")
    proof = _load_json_mapping(proof_path, description="owner proof")
    child = proof.get("child")
    if not isinstance(child, Mapping):
        raise ValueError(f"owner proof child is invalid for {owner}")
    payload = child.get("payload")
    if not isinstance(payload, Mapping):
        raise ValueError(f"owner proof payload is invalid for {owner}")
    supervised = payload.get("supervised_execution")
    if not isinstance(supervised, Mapping) or any(
        (
            supervised.get("cleanup_confirmed") is not True,
            supervised.get("status") not in (None, "pass"),
            supervised.get("exit_code") != 0,
            supervised.get("root_process_running") is not False,
            supervised.get("descendant_process_ids") not in ([], ()),
            supervised.get("containment_query_succeeded") is not True,
            supervised.get("cancelled") is True,
            supervised.get("interrupted") is True,
            supervised.get("timed_out") is True,
        )
    ):
        raise ValueError(f"owner supervised cleanup is not confirmed for {owner}")
    model_result = payload.get("model_result")
    if not isinstance(model_result, Mapping):
        raise ValueError(f"owner proof model result is invalid for {owner}")
    if (
        model_result.get("model_id") != owner
        or model_result.get("status") != "pass"
        or model_result.get("ok") is not True
        or model_result.get("exit_code") != 0
    ):
        raise ValueError(f"owner proof model result is not a terminal pass for {owner}")
    if (
        Path(str(model_result.get("native_case_result_artifact_path", ""))).resolve()
        != native_result_path.resolve()
        or model_result.get("native_case_result_artifact_fingerprint")
        != owner_row.get("native_case_result_artifact_fingerprint")
    ):
        raise ValueError(f"owner proof native artifact identity mismatch for {owner}")
    expected_runner = f".flowguard/verification/owners/{owner}/run_checks.py"
    command = model_result.get("command")
    if not isinstance(command, list) or not any(
        str(token).replace("\\", "/").endswith(expected_runner)
        for token in command
    ):
        raise ValueError(f"owner proof runner identity is missing for {owner}")
    inventory = model_result.get("input_inventory")
    if not isinstance(inventory, list):
        raise ValueError(f"owner proof input inventory is missing for {owner}")
    runner_entries = [
        row
        for row in inventory
        if isinstance(row, Mapping)
        and str(row.get("path", "")).replace("\\", "/") == expected_runner
    ]
    if len(runner_entries) != 1:
        raise ValueError(f"owner proof runner input is not unique for {owner}")
    runner_path = root / expected_runner
    from flowguard.source_identity import source_file_fingerprint

    if runner_entries[0].get("sha256") != source_file_fingerprint(runner_path):
        raise ValueError(f"owner proof runner fingerprint is stale for {owner}")


def _validate_owner_runner_and_cleanup(
    root: Path,
    *,
    owner_rows_by_owner: Mapping[str, Mapping[str, Any]],
    native_result_paths: Mapping[str, Path],
    receipt_dir: str | Path | None,
) -> None:
    receipt_root = (
        Path(receipt_dir).expanduser().resolve()
        if receipt_dir is not None
        else _infer_receipt_directory(native_result_paths)
    )
    if receipt_root is not None:
        if not receipt_root.is_dir():
            raise ValueError(f"owner receipt directory is unavailable: {receipt_root}")
        for owner in sorted(owner_rows_by_owner):
            _assert_owner_receipt_proof(
                root,
                owner=owner,
                owner_row=owner_rows_by_owner[owner],
                native_result_path=native_result_paths[owner],
                receipt_root=receipt_root,
            )
        return
    missing = [
        owner
        for owner, row in sorted(owner_rows_by_owner.items())
        if not row.get("runner") or row.get("cleanup_confirmed") is not True
    ]
    if missing:
        raise ValueError(
            "owner runner/cleanup evidence is unavailable; exact receipt store required: "
            + ",".join(missing)
        )


def load_current_native_case_mapping(
    root: Path,
    evidence_path: Path,
    *,
    mapping_path: Path | None = None,
    receipt_dir: str | Path | None = None,
) -> Any:
    """Load the official typed mapping only when its parent evidence is current."""

    from flowguard.native_case_mapping import load_native_case_mapping

    registry = load_native_case_mapping(mapping_path or root)
    payload = _load_json_mapping(evidence_path, description="self-blueprint evidence")
    execution = _execution_evidence_from_payload(payload)
    current = _assert_execution_manifest_alignment(root, execution)
    model = _load_model(root)
    declared_cases = _declared_cases(root, model)
    declared_by_owner: dict[str, list[str]] = {}
    for owner_id, _parent_id, case_id in declared_cases:
        declared_by_owner.setdefault(str(owner_id), []).append(str(case_id))
    expected_owner_ids = tuple(sorted(declared_by_owner))
    owner_rows = execution.get("owners")
    if not isinstance(owner_rows, list):
        raise ValueError("self-blueprint execution_evidence lacks owners")
    blueprint_cases: dict[str, tuple[str, ...]] = {}
    for item in owner_rows:
        if not isinstance(item, Mapping):
            raise ValueError("self-blueprint execution owner row is not an object")
        raw_owner = item.get("model_id")
        if raw_owner is None:
            raw_owner = item.get("owner_id")
        owner = _normalise_owner_id(raw_owner)
        required = item.get("required_case_ids")
        if not isinstance(required, list):
            raise ValueError(f"self-blueprint required_case_ids invalid for {owner}")
        blueprint_cases[owner] = tuple(required)
    _assert_execution_summary(
        execution,
        expected_owner_ids=expected_owner_ids,
        expected_case_count=len(declared_cases),
    )
    _validate_owner_execution_rows(
        owner_rows,
        expected_owner_ids=expected_owner_ids,
        declared_case_ids_by_owner=declared_by_owner,
        blueprint_cases=blueprint_cases,
    )
    result_paths = _native_result_paths_from_evidence(
        evidence_path,
        expected_owner_ids=expected_owner_ids,
    )
    owner_rows_by_owner = {
        _normalise_owner_id(
            item.get("model_id")
            if item.get("model_id") is not None
            else item.get("owner_id")
        ): item
        for item in owner_rows
        if isinstance(item, Mapping)
    }
    _assert_native_artifact_identities(
        owner_rows,
        native_result_paths=result_paths,
    )
    contracts_by_owner = _strict_native_contracts(root, model, declared_cases)
    _rows, _native_verification, native_gaps = _native_result_rows_from_paths(
        result_paths,
        expected_owner_ids=expected_owner_ids,
        contracts_by_owner=contracts_by_owner,
    )
    if native_gaps:
        raise ValueError("native result verification blocked: " + "; ".join(native_gaps))
    for owner in expected_owner_ids:
        for contract in contracts_by_owner[owner]:
            matches = [
                case_id
                for case_id in blueprint_cases[owner]
                if case_id.endswith(f":{contract.case_kind}:{contract.source_case_id}")
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"typed loader cannot resolve exact blueprint binding for "
                    f"{owner}:{contract.source_case_id}"
                )
    from flowguard.native_case_protocol import (
        load_native_model_case_results,
        verify_native_case_bindings,
    )

    expected_native_binding_keys = {
        (f"model:{owner_id}", case_id)
        for owner_id, case_ids in declared_by_owner.items()
        for case_id in case_ids
    }
    actual_binding_keys = {
        (binding.owner_id, binding.blueprint_source_case_id)
        for binding in registry.bindings
    }
    if len(registry.bindings) != len(declared_cases) or actual_binding_keys != expected_native_binding_keys:
        raise ValueError("typed loader owner/source projection is not the declared 63-case inventory")
    if set(registry.blueprint_case_ids) != {
        case_id for case_ids in blueprint_cases.values() for case_id in case_ids
    }:
        raise ValueError("typed loader blueprint case projection does not match execution evidence")
    _validate_owner_runner_and_cleanup(
        root,
        owner_rows_by_owner=owner_rows_by_owner,
        native_result_paths=result_paths,
        receipt_dir=receipt_dir,
    )
    for owner in expected_owner_ids:
        rows = tuple(load_native_model_case_results(result_paths[owner]))
        owner_bindings = registry.bindings_by_owner.get(f"model:{owner}", ())
        projection = verify_native_case_bindings(
            owner_bindings,
            rows,
            mapping_fingerprint=registry.mapping_fingerprint,
        )
        if not projection.ok:
            raise ValueError(
                f"typed loader native binding projection blocked for {owner}: "
                + "; ".join(projection.findings)
            )
    if registry.source_manifest_fingerprint != current:
        raise ValueError(
            "source/manifest mismatch: "
            f"mapping={registry.source_manifest_fingerprint!r}; current_manifest={current!r}"
        )
    return registry


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
        by_source = {str(row.source_case_id): row for row in loaded}
        for contract in contracts_by_owner[owner]:
            result = by_source.get(str(contract.source_case_id))
            if result is None:
                continue
            if any(
                not isinstance(oracle, Mapping) or oracle.get("ok") is not True
                for oracle in result.oracle_results
            ):
                gaps.append(
                    f"native:{owner}:oracle_not_passing:{contract.source_case_id}"
                )
        rows.extend(loaded)
    return tuple(rows), verification_by_owner, tuple(sorted(set(gaps)))


def _native_result_paths_from_evidence(
    evidence_path: Path,
    *,
    expected_owner_ids: Sequence[str],
) -> dict[str, Path]:
    """Read exact owner result paths from a current evidence report.

    The self-blueprint report is the authoritative input for blueprint case
    IDs.  A simulator report is accepted as a convenience when it carries the
    same ``model_id``/``native_case_result_artifact_path`` records.  This
    parser never searches a directory or chooses the newest artifact.
    """

    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"native evidence input is unreadable: {evidence_path}") from exc
    owner_rows: Any = None
    if isinstance(payload, Mapping):
        execution = payload.get("execution_evidence")
        if isinstance(execution, Mapping):
            owner_rows = execution.get("owners")
        if owner_rows is None:
            owner_rows = payload.get("owners")
        if owner_rows is None:
            owner_rows = payload.get("results")
    elif isinstance(payload, list):
        owner_rows = payload
    if not isinstance(owner_rows, list):
        raise ValueError(
            "native evidence input must contain execution_evidence.owners or owners"
        )

    expected = {str(item) for item in expected_owner_ids}
    paths: dict[str, Path] = {}
    for index, item in enumerate(owner_rows):
        if not isinstance(item, Mapping):
            raise ValueError(f"native evidence owner row {index} is not an object")
        raw_owner = item.get("model_id")
        if raw_owner is None:
            raw_owner = item.get("owner_id")
        owner = _normalise_owner_id(raw_owner)
        raw_path = item.get("native_case_result_artifact_path")
        if not owner or not isinstance(raw_path, str) or not raw_path.strip():
            # A simulator report can contain summary rows without a native
            # artifact.  Those rows cannot participate in this registry.
            if item.get("native_case_result_artifact_path") is None:
                continue
            raise ValueError(f"native evidence owner row {index} lacks an exact result path")
        if owner in paths:
            raise ValueError(f"duplicate native evidence owner: {owner}")
        paths[owner] = Path(raw_path).expanduser().resolve()

    foreign = sorted(set(paths) - expected)
    missing = sorted(expected - set(paths))
    if foreign or missing:
        detail = []
        if foreign:
            detail.append("foreign=" + ",".join(foreign))
        if missing:
            detail.append("missing=" + ",".join(missing))
        raise ValueError("native evidence owner closure mismatch: " + "; ".join(detail))
    return paths


def build_native_case_mapping(
    root: Path,
    evidence_path: Path,
    *,
    receipt_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Compile the official FlowGuard native-to-blueprint registry.

    Blueprint IDs come from the current self-blueprint execution evidence;
    native rows and their contracts come from the registered model owners.  A
    registry is emitted only after the parent manifest, all 10 owner rows,
    exact leaf receipt/cleanup evidence, all 63 native rows, and the binding
    projection verifier agree.  A manifest mismatch leaves the caller with a
    visible blocked error and never rewrites the current registry.
    """

    from flowguard.native_case_mapping import (
        NativeCaseMappingRegistry,
        compute_native_case_mapping_fingerprint,
    )
    from flowguard.native_case_protocol import (
        NativeCaseBinding,
        verify_native_case_bindings,
    )
    from flowguard.source_identity import source_file_fingerprint

    model = _load_model(root)
    declared_cases = _declared_cases(root, model)
    # Keep the owner order and parent information from the checked-in model,
    # while validating each native source row against its exact contract.
    declared_by_owner = {}
    for owner_id, _parent_id, case_id in declared_cases:
        declared_by_owner.setdefault(str(owner_id), []).append(str(case_id))
    expected_owner_ids = tuple(sorted(declared_by_owner))
    contracts_by_owner = _strict_native_contracts(root, model, declared_cases)

    blueprint_payload = _load_json_mapping(
        evidence_path,
        description="self-blueprint evidence",
    )
    execution = _execution_evidence_from_payload(blueprint_payload)
    _assert_execution_manifest_alignment(root, execution)
    owner_rows = execution.get("owners")
    if not isinstance(owner_rows, list):
        raise ValueError("self-blueprint execution_evidence lacks owners")
    blueprint_cases: dict[str, tuple[str, ...]] = {}
    for index, item in enumerate(owner_rows):
        if not isinstance(item, Mapping):
            raise ValueError(f"self-blueprint owner row {index} is not an object")
        raw_owner = item.get("model_id")
        if raw_owner is None:
            raw_owner = item.get("owner_id")
        owner = _normalise_owner_id(raw_owner)
        required = item.get("required_case_ids")
        if owner in blueprint_cases:
            raise ValueError(f"duplicate self-blueprint owner: {owner}")
        if not isinstance(required, list) or not required or not all(
            isinstance(case_id, str) and case_id.strip() == case_id and case_id
            for case_id in required
        ):
            raise ValueError(f"self-blueprint required_case_ids invalid for {owner}")
        blueprint_cases[owner] = tuple(required)
    if set(blueprint_cases) != set(expected_owner_ids):
        raise ValueError("self-blueprint owner closure does not match registered owners")
    all_blueprint_ids = [case_id for values in blueprint_cases.values() for case_id in values]
    if len(all_blueprint_ids) != len(set(all_blueprint_ids)):
        raise ValueError("self-blueprint required case IDs are not unique")
    _assert_execution_summary(
        execution,
        expected_owner_ids=expected_owner_ids,
        expected_case_count=len(declared_cases),
    )
    _validate_owner_execution_rows(
        owner_rows,
        expected_owner_ids=expected_owner_ids,
        declared_case_ids_by_owner=declared_by_owner,
        blueprint_cases=blueprint_cases,
    )

    result_paths = _native_result_paths_from_evidence(
        evidence_path,
        expected_owner_ids=expected_owner_ids,
    )
    _rows, _native_verification, native_gaps = _native_result_rows_from_paths(
        result_paths,
        expected_owner_ids=expected_owner_ids,
        contracts_by_owner=contracts_by_owner,
    )
    if native_gaps:
        raise ValueError("native result verification blocked: " + "; ".join(native_gaps))
    rows_by_owner_from_payload = {
        _normalise_owner_id(
            item.get("model_id")
            if item.get("model_id") is not None
            else item.get("owner_id")
        ): item
        for item in owner_rows
        if isinstance(item, Mapping)
    }
    _assert_native_artifact_identities(
        owner_rows,
        native_result_paths=result_paths,
    )
    _validate_owner_runner_and_cleanup(
        root,
        owner_rows_by_owner=rows_by_owner_from_payload,
        native_result_paths=result_paths,
        receipt_dir=receipt_dir,
    )

    bindings: list[Any] = []
    rows_by_owner: dict[str, tuple[Any, ...]] = {}
    from flowguard.native_case_protocol import load_native_model_case_results

    for owner in expected_owner_ids:
        loaded = tuple(load_native_model_case_results(result_paths[owner]))
        rows_by_owner[owner] = loaded
        by_source = {
            str(row.source_case_id): row
            for row in loaded
        }
        if len(by_source) != len(loaded):
            raise ValueError(f"duplicate native source case IDs for {owner}")
        payload_rows = rows_by_owner_from_payload[owner].get("native_case_results")
        payload_by_source = {
            str(row.get("source_case_id")): row
            for row in payload_rows
            if isinstance(row, Mapping)
        }
        if payload_by_source.keys() != by_source.keys() or len(payload_rows) != len(loaded):
            raise ValueError(f"execution_evidence native rows mismatch for {owner}")
        for source_case_id, row in by_source.items():
            raw_row = payload_by_source[source_case_id]
            if json.dumps(raw_row, sort_keys=True) != json.dumps(
                row.to_dict(),
                sort_keys=True,
            ):
                raise ValueError(
                    f"execution_evidence native row content mismatch for {owner}:{source_case_id}"
                )
        for contract in contracts_by_owner[owner]:
            matches = [
                case_id
                for case_id in blueprint_cases[owner]
                if case_id.endswith(f":{contract.case_kind}:{contract.source_case_id}")
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"cannot resolve exact blueprint binding for {owner}:{contract.source_case_id}"
                )
            if contract.source_case_id not in by_source:
                raise ValueError(
                    f"native result row missing for {owner}:{contract.source_case_id}"
                )
            bindings.append(
                NativeCaseBinding(
                    owner_id=contract.owner_id,
                    blueprint_case_id=matches[0],
                    blueprint_source_case_id=contract.source_case_id,
                    native_case_ids=(contract.source_case_id,),
                    case_kind=contract.case_kind,
                    evidence_scope=contract.evidence_scope,
                    covered_dimensions=contract.covered_dimensions,
                    expected_status=contract.expected_status,
                    expected_observed_status=contract.expected_observed_status,
                    protected_failure_ids=contract.protected_failure_ids,
                    expected_finding_codes=contract.expected_finding_codes,
                )
            )

    if len(bindings) != len(all_blueprint_ids):
        raise ValueError(
            f"native binding count mismatch: bindings={len(bindings)} planned={len(all_blueprint_ids)}"
        )
    manifest = root / ".flowguard" / "models" / "regression-manifest.json"
    source_manifest_fingerprint = source_file_fingerprint(manifest)
    source_paths = tuple(
        sorted(
            {
                ".flowguard/models/regression-manifest.json",
                *(
                    f".flowguard/models/owners/{owner}/model.py"
                    for owner in expected_owner_ids
                ),
                *(
                    f".flowguard/verification/owners/{owner}/run_checks.py"
                    for owner in expected_owner_ids
                ),
            }
        )
    )
    mapping_fingerprint = compute_native_case_mapping_fingerprint(
        source_manifest_fingerprint=source_manifest_fingerprint,
        source_paths=source_paths,
        bindings=bindings,
    )
    bound_bindings = tuple(
        replace(binding, mapping_fingerprint=mapping_fingerprint)
        for binding in bindings
    )
    registry = NativeCaseMappingRegistry(
        mapping_fingerprint=mapping_fingerprint,
        source_manifest_fingerprint=source_manifest_fingerprint,
        source_paths=source_paths,
        bindings=bound_bindings,
        diagnostic_native_case_ids=(),
    )
    registry.assert_current_manifest(root)
    for owner in expected_owner_ids:
        owner_bindings = tuple(
            binding for binding in registry.bindings if binding.owner_id == f"model:{owner}"
        )
        projection = verify_native_case_bindings(
            owner_bindings,
            rows_by_owner[owner],
            mapping_fingerprint=mapping_fingerprint,
        )
        if not projection.ok:
            raise ValueError(
                f"native binding projection blocked for {owner}: "
                + "; ".join(projection.findings)
            )
    return registry.to_dict()


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
    parser.add_argument(
        "--results",
        help=(
            "Current self-blueprint JSON containing execution_evidence.owners "
            "and each native_case_result_artifact_path. When supplied, compile "
            "the official flowguard.native_case_mapping.v1 registry."
        ),
    )
    parser.add_argument(
        "--output",
        help="Write the generated mapping JSON to this exact path.",
    )
    parser.add_argument(
        "--model-receipt-dir",
        help=(
            "Exact immutable FlowGuard model-owner receipt store used to "
            "reopen runner and supervised-cleanup evidence."
        ),
    )
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if args.results:
        try:
            mapping = build_native_case_mapping(
                root,
                Path(args.results).resolve(),
                receipt_dir=(
                    Path(args.model_receipt_dir).resolve()
                    if args.model_receipt_dir
                    else None
                ),
            )
        except (OSError, ValueError) as exc:
            # A failed compile must remain visible to the caller while the
            # official typed mapping path remains untouched.  This diagnostic
            # envelope is intentionally not loadable as a native mapping.
            diagnostic = {
                "schema_version": "researchguard.native_case_mapping_compile_result.v1",
                "status": "blocked",
                "blockers": [str(exc)],
                "mapping_path": ".flowguard/models/native-case-mapping.json",
                "claim_boundary": (
                    "Mapping compilation did not produce a typed registry; "
                    "the current registry and authority remain unchanged."
                ),
            }
            text = json.dumps(diagnostic, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
            print(text, end="")
            return 1
        # ``flowguard.native_case_mapping.v1`` is an official typed registry;
        # unlike the legacy compatibility mapping, it deliberately has no
        # top-level ``status`` field.  Keep the CLI exit decision aligned with
        # the schema instead of indexing a field that cannot be emitted.
        from flowguard.native_case_mapping import NATIVE_CASE_MAPPING_SCHEMA

        success = (
            mapping.get("schema_version") == NATIVE_CASE_MAPPING_SCHEMA
            and isinstance(mapping.get("bindings"), list)
        )
    else:
        mapping = build_mapping(root)
        success = mapping.get("status") == "pass"
    text = json.dumps(mapping, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        Path(args.output).resolve().write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
