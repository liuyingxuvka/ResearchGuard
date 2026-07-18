"""Per-model TraceGuard purpose declarations and native proof bindings.

The repository ``guard-model`` artifacts are a family oracle catalog and
regression baseline only.  Every real candidate must bind an explicit
task-model-instance contract whose own good/bad model files pass TraceGuard's
native reactions.
"""

from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import yaml


class GuardPurposeContractError(ValueError):
    """Fail-closed candidate/purpose binding error with a stable code."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _canonical_fingerprint(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def canonical_guard_contract_fingerprint(contract: Mapping[str, Any]) -> str:
    return _canonical_fingerprint(contract)


def canonical_candidate_fingerprint(model_data: Mapping[str, Any]) -> str:
    payload = deepcopy(dict(model_data))
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        metadata.pop("guard_purpose_contract", None)
    return _canonical_fingerprint(payload)


def _json_mapping(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GuardPurposeContractError(code, path.as_posix()) from exc
    if not isinstance(value, dict):
        raise GuardPurposeContractError(code, path.as_posix())
    return value


def load_family_guard_catalog(
    catalog_path: str | Path | None = None,
) -> dict[str, Any]:
    candidate = (
        Path(catalog_path).resolve()
        if catalog_path is not None
        else Path(__file__).resolve().parent / "guard_model" / "contract.json"
    )
    if not candidate.is_file():
        raise GuardPurposeContractError(
            "traceguard_family_guard_catalog_missing",
            candidate.as_posix(),
        )
    return _json_mapping(
        candidate,
        "traceguard_family_guard_catalog_unreadable",
    )


def load_task_guard_contract(path: str | Path) -> dict[str, Any]:
    contract_path = Path(path).resolve()
    if not contract_path.is_file():
        raise GuardPurposeContractError(
            "traceguard_task_purpose_contract_missing",
            contract_path.as_posix(),
        )
    return _json_mapping(
        contract_path,
        "traceguard_task_purpose_contract_unreadable",
    )


def _safe_case_path(contract_path: Path, row: Mapping[str, Any]) -> Path:
    relative = row.get("model_path")
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise GuardPurposeContractError(
            "traceguard_task_purpose_case_path_invalid",
            str(relative),
        )
    resolved = (contract_path.parent / relative).resolve()
    try:
        resolved.relative_to(contract_path.parent.resolve())
    except ValueError as exc:
        raise GuardPurposeContractError(
            "traceguard_task_purpose_case_path_outside_root",
            relative,
        ) from exc
    if not resolved.is_file():
        raise GuardPurposeContractError(
            "traceguard_task_purpose_case_missing",
            relative,
        )
    expected_hash = row.get("model_sha256")
    observed_hash = canonical_candidate_fingerprint(load_model_mapping(resolved))
    if expected_hash != observed_hash:
        raise GuardPurposeContractError(
            "traceguard_task_purpose_case_stale",
            relative,
        )
    return resolved


def _normalize_task_contract(
    contract: Mapping[str, Any],
    *,
    family_catalog: Mapping[str, Any],
) -> dict[str, Any]:
    required_text = {
        "contract_id": contract.get("contract_id"),
        "model_instance_id": contract.get("model_instance_id"),
        "purpose": contract.get("purpose"),
        "claim_boundary": contract.get("claim_boundary"),
    }
    if (
        contract.get("schema_version") != "researchguard.trace.task_model_purpose.v1"
        or contract.get("contract_kind") != "task_model_instance"
        or contract.get("target_skill_id") != "traceguard"
        or contract.get("enforcement") != "enforced"
        or contract.get("declaration_sequence") != 1
        or any(not isinstance(value, str) or not value.strip() for value in required_text.values())
    ):
        raise GuardPurposeContractError(
            "traceguard_task_purpose_contract_invalid",
            "identity, purpose, boundary, or declaration order is incomplete",
        )
    selected = contract.get("selected_failure_ids")
    if (
        not isinstance(selected, list)
        or not selected
        or any(not isinstance(item, str) or not item for item in selected)
        or len(selected) != len(set(selected))
    ):
        raise GuardPurposeContractError(
            "traceguard_task_purpose_failure_universe_empty_or_duplicate",
            str(selected),
        )
    family_rows = {
        str(row.get("failure_class_id")): row
        for row in family_catalog.get("failure_classes", [])
        if isinstance(row, Mapping)
    }
    unknown = [item for item in selected if item not in family_rows]
    if unknown:
        raise GuardPurposeContractError(
            "traceguard_task_purpose_native_oracle_unknown",
            ",".join(unknown),
        )
    good = contract.get("known_good")
    if not isinstance(good, Mapping):
        raise GuardPurposeContractError(
            "traceguard_task_purpose_good_case_missing",
            str(required_text["contract_id"]),
        )
    if (
        not isinstance(good.get("case_id"), str)
        or not str(good.get("case_id")).strip()
        or good.get("native_oracle_id") != "oracle:traceguard:known-good"
        or not isinstance(good.get("model_path"), str)
        or not isinstance(good.get("model_sha256"), str)
    ):
        raise GuardPurposeContractError(
            "traceguard_task_purpose_good_case_invalid",
            str(required_text["contract_id"]),
        )
    bad_rows = contract.get("known_bad_cases")
    if not isinstance(bad_rows, list):
        bad_rows = []
    by_failure: dict[str, list[Mapping[str, Any]]] = {item: [] for item in selected}
    extras: list[str] = []
    for row in bad_rows:
        if not isinstance(row, Mapping):
            extras.append("<non-object>")
            continue
        failure_id = str(row.get("failure_id", ""))
        if failure_id not in by_failure:
            extras.append(failure_id)
        else:
            by_failure[failure_id].append(row)
    if extras or any(len(rows) != 1 for rows in by_failure.values()):
        raise GuardPurposeContractError(
            "traceguard_task_purpose_bad_case_cardinality_invalid",
            json.dumps(
                {
                    "counts": {key: len(value) for key, value in by_failure.items()},
                    "extras": extras,
                },
                sort_keys=True,
            ),
        )
    normalized_bad: list[dict[str, Any]] = []
    for failure_id in selected:
        row = by_failure[failure_id][0]
        family = family_rows[failure_id]
        if (
            not isinstance(row.get("case_id"), str)
            or not str(row.get("case_id")).strip()
            or row.get("native_oracle_id") != family.get("native_oracle_id")
            or not isinstance(row.get("model_path"), str)
            or not isinstance(row.get("model_sha256"), str)
        ):
            raise GuardPurposeContractError(
                "traceguard_task_purpose_bad_case_invalid",
                failure_id,
            )
        normalized_bad.append(
            {
                "case_id": str(row["case_id"]),
                "failure_id": failure_id,
                "prevents": str(row.get("prevents", family.get("prevents", ""))),
                "native_oracle_id": str(family["native_oracle_id"]),
                "model_path": str(row["model_path"]),
                "model_sha256": str(row["model_sha256"]),
            }
        )
    return {
        "schema_version": "researchguard.trace.task_model_purpose.v1",
        "contract_kind": "task_model_instance",
        "contract_id": str(contract["contract_id"]),
        "model_instance_id": str(contract["model_instance_id"]),
        "target_skill_id": "traceguard",
        "enforcement": "enforced",
        "purpose": str(contract["purpose"]),
        "claim_boundary": str(contract["claim_boundary"]),
        "selected_failure_ids": list(selected),
        "known_good": {
            "case_id": str(good["case_id"]),
            "native_oracle_id": "oracle:traceguard:known-good",
            "model_path": str(good["model_path"]),
            "model_sha256": str(good["model_sha256"]),
        },
        "known_bad_cases": normalized_bad,
        "declaration_sequence": 1,
    }


def _evaluation(path: Path):
    from .evaluator import evaluate_model
    from .loader import load_model

    model = load_model(path)
    return model, evaluate_model(model)


def _known_good_passes(path: Path) -> bool:
    _, result = _evaluation(path)
    receipt = result.storyline_depth
    return bool(
        result.ok
        and receipt
        and receipt.closure_status == "PASS"
        and receipt.broad_claim_licensed
        and not receipt.critical_uncovered_ids
        and not receipt.critical_ineffective_ids
        and not receipt.sensitivity_mismatch_ids
        and not receipt.predictive_claim_licensed
    )


def _bad_oracle_passes(failure_id: str, path: Path) -> bool:
    from .evaluator import evaluate_model
    from .storyline_depth import evaluate_storyline_depth

    model, result = _evaluation(path)
    receipt = result.storyline_depth
    payload = result.to_dict()
    if not receipt:
        return False
    if failure_id == "missing-event-evidence":
        diagnostics = list(payload.get("diagnostics", [])) + [
            row
            for trace in payload.get("traces", [])
            for row in trace.get("diagnostics", [])
            if isinstance(row, dict)
        ]
        return bool(
            receipt.closure_status == "BLOCKED"
            and not receipt.broad_claim_licensed
            and any(
                row.get("diagnostic_id")
                in {
                    "invalid_source_not_validation_evidence",
                    "no_evidence_no_event",
                    "no_evidence_no_trace",
                }
                for row in diagnostics
            )
        )
    if failure_id == "hidden-temporal-contradiction":
        contradictions = [
            row
            for trace in payload.get("traces", [])
            for row in trace.get("contradictions", [])
            if isinstance(row, dict)
        ]
        return bool(
            receipt.closure_status == "BLOCKED"
            and any(row.get("blocking") is True for row in contradictions)
        )
    if failure_id == "chronology-promoted-to-causality":
        gap_ids = {row.get("gap_id") for row in receipt.unresolved_gaps}
        return receipt.closure_status == "BLOCKED" and {
            "missing_causal_mechanism",
            "missing_confounder_review",
        } <= gap_ids
    if failure_id == "untested-critical-perturbation":
        baseline = evaluate_model(model, include_storyline_depth=False)
        value = evaluate_storyline_depth(model, baseline, max_perturbations=1)
        return bool(value.closure_status == "GAP" and value.critical_uncovered_ids)
    if failure_id == "shallow-trace-temporal-depth":
        return receipt.closure_status == "BLOCKED" and any(
            row.get("object_type") == "trace"
            and "trace_event_count_below_native_floor" in row.get("findings", [])
            for row in receipt.object_depth_rows
        )
    if failure_id == "unresolved-causal-confounder":
        return "unresolved_confounder_review" in {
            row.get("gap_id") for row in receipt.unresolved_gaps
        }
    if failure_id == "expected-sensitivity-mismatch":
        return bool(receipt.sensitivity_mismatch_ids and not receipt.broad_claim_licensed)
    if failure_id == "internal-perturbation-promoted-to-prediction":
        return bool(
            receipt.closure_status == "BLOCKED"
            and receipt.predictive_holdout_status
            == "unsupported_without_native_future_holdout"
            and not receipt.predictive_claim_licensed
        )
    if failure_id == "bounded-scope-promoted-to-broad":
        baseline = evaluate_model(model, include_storyline_depth=False)
        value = evaluate_storyline_depth(
            model,
            baseline,
            requested_claim_scope="bounded",
        )
        return value.closure_status == "PASS" and not value.broad_claim_licensed
    return False


def prove_task_guard_contract(
    contract_path: str | Path,
    *,
    family_catalog_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(contract_path).resolve()
    raw = load_task_guard_contract(path)
    family = load_family_guard_catalog(family_catalog_path)
    contract = _normalize_task_contract(raw, family_catalog=family)
    good_path = _safe_case_path(path, contract["known_good"])
    observations = [
        {
            "case_id": contract["known_good"]["case_id"],
            "case_kind": "known_good",
            "native_oracle_id": "oracle:traceguard:known-good",
            "passed": _known_good_passes(good_path),
        }
    ]
    for row in contract["known_bad_cases"]:
        bad_path = _safe_case_path(path, row)
        observations.append(
            {
                "case_id": row["case_id"],
                "case_kind": "known_bad",
                "failure_id": row["failure_id"],
                "native_oracle_id": row["native_oracle_id"],
                "passed": _bad_oracle_passes(row["failure_id"], bad_path),
            }
        )
    passed = all(row["passed"] for row in observations)
    receipt = {
        "schema_version": "researchguard.trace.task_model_purpose_proof.v1",
        "status": "passed" if passed else "blocked",
        "contract_id": contract["contract_id"],
        "model_instance_id": contract["model_instance_id"],
        "contract_fingerprint": _canonical_fingerprint(contract),
        "family_catalog_fingerprint": _canonical_fingerprint(family),
        "selected_failure_ids": list(contract["selected_failure_ids"]),
        "known_good_count": 1,
        "known_bad_count": len(contract["known_bad_cases"]),
        "observations": observations,
        "claim_boundary": contract["claim_boundary"],
    }
    if not passed:
        raise GuardPurposeContractError(
            "traceguard_task_purpose_native_proof_failed",
            json.dumps(receipt, sort_keys=True),
        )
    return receipt


def build_guard_purpose_binding(
    contract: Mapping[str, Any],
    proof_receipt: Mapping[str, Any],
    model_data: Mapping[str, Any],
    *,
    contract_ref: str,
) -> dict[str, Any]:
    if proof_receipt.get("status") != "passed":
        raise GuardPurposeContractError(
            "traceguard_task_purpose_native_proof_failed",
            str(contract.get("contract_id", "")),
        )
    return {
        "schema_version": "researchguard.trace.guard_purpose_binding.v2",
        "contract_kind": "task_model_instance",
        "contract_id": str(contract["contract_id"]),
        "model_instance_id": str(contract["model_instance_id"]),
        "purpose": str(contract["purpose"]),
        "claim_boundary": str(contract["claim_boundary"]),
        "selected_failure_ids": list(contract["selected_failure_ids"]),
        "contract_ref": contract_ref,
        "contract_fingerprint": str(proof_receipt["contract_fingerprint"]),
        "proof_receipt_fingerprint": _canonical_fingerprint(proof_receipt),
        "candidate_fingerprint": canonical_candidate_fingerprint(model_data),
        "purpose_declared_sequence": 1,
        "proof_completed_sequence": 2,
        "candidate_bound_sequence": 3,
    }


def bind_task_guard_purpose(
    model_data: Mapping[str, Any],
    *,
    contract_path: str | Path,
    candidate_path: str | Path,
) -> dict[str, Any]:
    resolved_contract = Path(contract_path).resolve()
    resolved_candidate = Path(candidate_path).resolve()
    raw = load_task_guard_contract(resolved_contract)
    family = load_family_guard_catalog()
    contract = _normalize_task_contract(raw, family_catalog=family)
    proof = prove_task_guard_contract(resolved_contract)
    contract_ref = Path(
        os.path.relpath(resolved_contract, start=resolved_candidate.parent)
    ).as_posix()
    output = deepcopy(dict(model_data))
    metadata = output.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        raise GuardPurposeContractError(
            "traceguard_candidate_metadata_invalid",
            "metadata must be an object",
        )
    existing_instance_id = metadata.get("model_instance_id")
    if existing_instance_id not in (None, contract["model_instance_id"]):
        raise GuardPurposeContractError(
            "traceguard_task_purpose_model_instance_mismatch",
            str(existing_instance_id),
        )
    metadata["model_instance_id"] = contract["model_instance_id"]
    expected = build_guard_purpose_binding(
        contract,
        proof,
        output,
        contract_ref=contract_ref,
    )
    existing = metadata.get("guard_purpose_contract")
    if existing is not None and existing != expected:
        raise GuardPurposeContractError(
            "traceguard_guard_purpose_binding_stale_or_mismatched",
            expected["contract_fingerprint"],
        )
    metadata["guard_purpose_contract"] = expected
    return output


def require_current_guard_purpose_binding(
    model_data: Mapping[str, Any],
    *,
    candidate_path: str | Path,
) -> dict[str, Any]:
    metadata = model_data.get("metadata")
    actual = metadata.get("guard_purpose_contract") if isinstance(metadata, Mapping) else None
    if not isinstance(actual, Mapping):
        raise GuardPurposeContractError(
            "traceguard_guard_purpose_binding_missing",
            Path(candidate_path).as_posix(),
        )
    if not isinstance(metadata, Mapping) or metadata.get("model_instance_id") != actual.get(
        "model_instance_id"
    ):
        raise GuardPurposeContractError(
            "traceguard_task_purpose_model_instance_mismatch",
            Path(candidate_path).as_posix(),
        )
    if actual.get("schema_version") != "researchguard.trace.guard_purpose_binding.v2":
        raise GuardPurposeContractError(
            "traceguard_guard_purpose_binding_stale_or_mismatched",
            str(actual.get("schema_version", "")),
        )
    contract_ref = actual.get("contract_ref")
    if (
        not isinstance(contract_ref, str)
        or not contract_ref
        or Path(contract_ref).is_absolute()
    ):
        raise GuardPurposeContractError(
            "traceguard_task_purpose_contract_ref_invalid",
            str(contract_ref),
        )
    candidate = Path(candidate_path).resolve()
    contract_path = (candidate.parent / contract_ref).resolve()
    raw = load_task_guard_contract(contract_path)
    family = load_family_guard_catalog()
    contract = _normalize_task_contract(raw, family_catalog=family)
    proof = prove_task_guard_contract(contract_path)
    expected = build_guard_purpose_binding(
        contract,
        proof,
        model_data,
        contract_ref=contract_ref,
    )
    if dict(actual) != expected:
        raise GuardPurposeContractError(
            "traceguard_guard_purpose_binding_stale_or_mismatched",
            expected["contract_fingerprint"],
        )
    return expected


def required_task_guard_input_paths(
    model_data: Mapping[str, Any],
    *,
    candidate_path: str | Path,
) -> list[Path]:
    metadata = model_data.get("metadata")
    binding = metadata.get("guard_purpose_contract") if isinstance(metadata, Mapping) else None
    if not isinstance(binding, Mapping):
        raise GuardPurposeContractError(
            "traceguard_guard_purpose_binding_missing",
            Path(candidate_path).as_posix(),
        )
    contract_ref = binding.get("contract_ref")
    if (
        not isinstance(contract_ref, str)
        or not contract_ref
        or Path(contract_ref).is_absolute()
    ):
        raise GuardPurposeContractError(
            "traceguard_task_purpose_contract_ref_invalid",
            str(contract_ref),
        )
    candidate = Path(candidate_path).resolve()
    contract_path = (candidate.parent / contract_ref).resolve()
    raw = load_task_guard_contract(contract_path)
    family = load_family_guard_catalog()
    contract = _normalize_task_contract(raw, family_catalog=family)
    paths = [contract_path, _safe_case_path(contract_path, contract["known_good"])]
    paths.extend(
        _safe_case_path(contract_path, row) for row in contract["known_bad_cases"]
    )
    return paths


def load_model_mapping(path: str | Path) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GuardPurposeContractError(
            "traceguard_candidate_model_invalid",
            Path(path).as_posix(),
        )
    return value


__all__ = [
    "GuardPurposeContractError",
    "bind_task_guard_purpose",
    "build_guard_purpose_binding",
    "canonical_candidate_fingerprint",
    "canonical_guard_contract_fingerprint",
    "load_family_guard_catalog",
    "load_model_mapping",
    "load_task_guard_contract",
    "prove_task_guard_contract",
    "require_current_guard_purpose_binding",
    "required_task_guard_input_paths",
]
