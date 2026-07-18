"""LogicGuard target-local prevented-failure contracts.

The current interface binds only the direct LogicGuard owner. Internal routes
use ``route_execution_depth`` and other Guards use their own native contracts;
there is no cross-Skill reader or alternate runtime root.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

import yaml


TARGET_DECLARATION_SCHEMA = (
    "researchguard.logic.target_model_purpose_declaration.v1"
)
TARGET_CONTRACT_SCHEMA = "researchguard.logic.target_model_purpose_contract.v1"
TARGET_BINDING_SCHEMA = "researchguard.logic.target_model_purpose_binding.v1"
TARGET_PROOF_SCHEMA = "researchguard.logic.target_model_purpose_proof.v1"
TARGET_ROLE = "target_model_instance"
TARGET_SKILL_ID = "logicguard"
TARGET_AUTHORING_ORDER = [
    "declare_target_model_purpose",
    "freeze_target_model_purpose",
    "build_candidate",
    "bind_candidate_to_frozen_purpose",
    "prove_every_declared_failure",
    "issue_guarded_native_receipt",
]
SUPPORTED_ORACLES = {
    "primary_depth_gap_prefix",
    "primary_diagnostic_code",
}


class GuardModelContractError(ValueError):
    """The LogicGuard target declaration or proof is invalid."""


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n"
    ).encode("utf-8")


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest().upper()


def _load_document(path: Path) -> dict[str, Any]:
    try:
        if path.suffix.lower() in {".yaml", ".yml"}:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
        else:
            value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise GuardModelContractError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GuardModelContractError(f"{path} must contain one object")
    return value


def _write_document_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if path.suffix.lower() in {".yaml", ".yml"}:
        body = yaml.safe_dump(
            dict(value),
            allow_unicode=True,
            sort_keys=False,
            width=120,
        )
    else:
        body = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    temporary.write_text(body, encoding="utf-8")
    os.replace(temporary, path)


def _inside(
    root: Path,
    relative_or_absolute: str | Path,
    *,
    must_exist: bool,
) -> Path:
    candidate = Path(relative_or_absolute)
    path = (
        candidate.resolve()
        if candidate.is_absolute()
        else (root / candidate).resolve()
    )
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise GuardModelContractError(
            f"logicguard_blocked:target-path-escape:{relative_or_absolute}"
        ) from exc
    if must_exist and not path.is_file():
        raise GuardModelContractError(f"required target file is missing: {path}")
    return path


def _file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise GuardModelContractError(f"cannot hash {path}: {exc}") from exc


def _require_text(
    value: Mapping[str, Any],
    field: str,
    *,
    where: str,
) -> str:
    text = str(value.get(field, "")).strip()
    if not text:
        raise GuardModelContractError(f"{where} field is required: {field}")
    return text


def _target_contract_fingerprint(contract: Mapping[str, Any]) -> str:
    payload = dict(contract)
    payload.pop("contract_fingerprint", None)
    return _fingerprint(payload)


def _candidate_without_target_binding(
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    value = deepcopy(dict(candidate))
    guard_contract = value.get("guard_contract")
    if isinstance(guard_contract, dict):
        guard_contract.pop("target_purpose_binding", None)
        if not guard_contract:
            value.pop("guard_contract", None)
    return value


def _candidate_model_fingerprint(candidate: Mapping[str, Any]) -> str:
    return _fingerprint(_candidate_without_target_binding(candidate))


def _model_document(candidate: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = candidate.get("model")
    if (
        isinstance(nested, Mapping)
        and isinstance(nested.get("nodes"), Mapping)
        and isinstance(nested.get("model"), Mapping)
    ):
        return nested
    if isinstance(candidate.get("nodes"), Mapping) and isinstance(
        candidate.get("model"), Mapping
    ):
        return candidate
    raise GuardModelContractError(
        "target candidate has no LogicGuard model document"
    )


def _candidate_declared_model_id(candidate: Mapping[str, Any]) -> str:
    model = candidate.get("model")
    if isinstance(model, Mapping):
        if isinstance(model.get("model"), Mapping):
            return str(model["model"].get("id", ""))
        return str(model.get("id", ""))
    return ""


def _require_logicguard_target(target: str) -> None:
    if target != TARGET_SKILL_ID:
        raise GuardModelContractError(
            "logicguard target contracts cannot bind another Skill or internal route"
        )


def freeze_target_contract(
    *,
    target_root: str | Path,
    declaration_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Freeze the AI purpose declaration before the candidate exists."""

    root = Path(target_root).resolve(strict=True)
    declaration_file = _inside(root, declaration_path, must_exist=True)
    output_file = _inside(root, output_path, must_exist=False)
    declaration = _load_document(declaration_file)
    if declaration.get("schema_version") != TARGET_DECLARATION_SCHEMA:
        raise GuardModelContractError(
            "target purpose declaration schema is invalid"
        )
    if declaration.get("contract_role") not in {None, TARGET_ROLE}:
        raise GuardModelContractError(
            "baseline or foreign material cannot be frozen as target authority"
        )
    if declaration.get("declared_by") != "ai":
        raise GuardModelContractError(
            "target model purpose must be explicitly declared_by=ai"
        )
    if declaration.get("selectable_modes", []) != []:
        raise GuardModelContractError(
            "target model purpose has one enforced route and no selectable modes"
        )

    contract_id = _require_text(
        declaration, "contract_id", where="target declaration"
    )
    model_id = _require_text(
        declaration, "model_id", where="target declaration"
    )
    target = _require_text(
        declaration, "target_skill_id", where="target declaration"
    )
    _require_logicguard_target(target)
    owner = _require_text(
        declaration, "native_owner_id", where="target declaration"
    )
    route = _require_text(
        declaration, "native_route_id", where="target declaration"
    )
    purpose = _require_text(
        declaration,
        "prevented_failure_purpose",
        where="target declaration",
    )
    boundary = _require_text(
        declaration, "claim_boundary", where="target declaration"
    )
    candidate_relative = _require_text(
        declaration, "candidate_relative_path", where="target declaration"
    )
    candidate_file = _inside(root, candidate_relative, must_exist=False)
    if candidate_file.exists():
        raise GuardModelContractError(
            "logicguard_blocked:purpose-not-frozen-before-candidate: "
            "target candidate already exists"
        )

    raw_failures = declaration.get("prevented_failure_classes")
    if not isinstance(raw_failures, list) or not raw_failures:
        raise GuardModelContractError(
            "at least one current target failure is required"
        )
    failures: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_failures):
        where = f"target failure[{index}]"
        if not isinstance(raw, Mapping):
            raise GuardModelContractError(f"{where} must be an object")
        failure_id = _require_text(raw, "failure_id", where=where)
        if failure_id in seen:
            raise GuardModelContractError("target failure ids must be unique")
        seen.add(failure_id)
        title = _require_text(raw, "title", where=where)
        block_when = _require_text(raw, "block_when", where=where)
        oracle = raw.get("oracle")
        if not isinstance(oracle, Mapping):
            raise GuardModelContractError(
                f"{where} requires one LogicGuard-native oracle"
            )
        kind = _require_text(oracle, "kind", where=f"{where}.oracle")
        finding_code = _require_text(
            oracle, "finding_code", where=f"{where}.oracle"
        )
        if kind not in SUPPORTED_ORACLES:
            raise GuardModelContractError(
                f"unsupported target oracle kind: {kind}"
            )
        good_file = _inside(
            root,
            _require_text(raw, "known_good_relative_path", where=where),
            must_exist=True,
        )
        bad_file = _inside(
            root,
            _require_text(raw, "known_bad_relative_path", where=where),
            must_exist=True,
        )
        for document in (_load_document(good_file), _load_document(bad_file)):
            if document.get("contract_role") == "family_baseline_regression":
                raise GuardModelContractError(
                    "packaged baseline material cannot substitute for "
                    "target-owned proof cases"
                )
        failures.append(
            {
                "failure_id": failure_id,
                "title": title,
                "block_when": block_when,
                "oracle": {
                    "kind": kind,
                    "finding_code": finding_code,
                },
                "known_good_relative_path": good_file.relative_to(
                    root
                ).as_posix(),
                "known_good_sha256": _file_sha256(good_file),
                "known_bad_relative_path": bad_file.relative_to(
                    root
                ).as_posix(),
                "known_bad_sha256": _file_sha256(bad_file),
            }
        )

    contract: dict[str, Any] = {
        "schema_version": TARGET_CONTRACT_SCHEMA,
        "contract_role": TARGET_ROLE,
        "contract_id": contract_id,
        "model_id": model_id,
        "target_skill_id": target,
        "native_owner_id": owner,
        "native_route_id": route,
        "declared_by": "ai",
        "declaration_status": "frozen",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "prevented_failure_purpose": purpose,
        "claim_boundary": boundary,
        "candidate_relative_path": candidate_file.relative_to(root).as_posix(),
        "candidate_requires_contract_fingerprint": True,
        "authoring_order": TARGET_AUTHORING_ORDER,
        "selectable_modes": [],
        "prevented_failure_classes": failures,
    }
    contract["contract_fingerprint"] = _target_contract_fingerprint(contract)
    _write_document_atomic(output_file, contract)
    return contract


def load_target_contract(
    *,
    target_root: str | Path,
    contract_path: str | Path,
) -> tuple[Path, dict[str, Any]]:
    root = Path(target_root).resolve(strict=True)
    path = _inside(root, contract_path, must_exist=True)
    contract = _load_document(path)
    if (
        contract.get("schema_version") != TARGET_CONTRACT_SCHEMA
        or contract.get("contract_role") != TARGET_ROLE
    ):
        raise GuardModelContractError(
            "logicguard_blocked:wrong-contract-role: current target authority "
            "is not a target-model contract"
        )
    if (
        contract.get("declared_by") != "ai"
        or contract.get("declaration_status") != "frozen"
    ):
        raise GuardModelContractError(
            "target purpose contract is not an AI-authored frozen authority"
        )
    if contract.get("candidate_requires_contract_fingerprint") is not True:
        raise GuardModelContractError(
            "target candidate must bind the frozen contract fingerprint"
        )
    if contract.get("authoring_order") != TARGET_AUTHORING_ORDER:
        raise GuardModelContractError(
            "target purpose-before-candidate authoring order is invalid"
        )
    if contract.get("selectable_modes") != []:
        raise GuardModelContractError(
            "target model purpose has no selectable mode"
        )
    for field in (
        "contract_id",
        "model_id",
        "target_skill_id",
        "native_owner_id",
        "native_route_id",
        "prevented_failure_purpose",
        "claim_boundary",
        "candidate_relative_path",
    ):
        _require_text(contract, field, where="target contract")
    _require_logicguard_target(str(contract["target_skill_id"]))
    fingerprint = str(contract.get("contract_fingerprint", ""))
    if not fingerprint or fingerprint != _target_contract_fingerprint(contract):
        raise GuardModelContractError(
            "logicguard_blocked:target-contract-stale: target contract "
            "fingerprint differs from current content"
        )
    failures = contract.get("prevented_failure_classes")
    if not isinstance(failures, list) or not failures:
        raise GuardModelContractError(
            "target contract requires one or more failures"
        )
    seen: set[str] = set()
    for index, raw in enumerate(failures):
        where = f"target contract failure[{index}]"
        if not isinstance(raw, Mapping):
            raise GuardModelContractError(f"{where} must be an object")
        failure_id = _require_text(raw, "failure_id", where=where)
        if failure_id in seen:
            raise GuardModelContractError("target failure ids must be unique")
        seen.add(failure_id)
        _require_text(raw, "title", where=where)
        _require_text(raw, "block_when", where=where)
        oracle = raw.get("oracle")
        if not isinstance(oracle, Mapping):
            raise GuardModelContractError(
                f"{where} requires one native oracle"
            )
        kind = _require_text(oracle, "kind", where=f"{where}.oracle")
        if kind not in SUPPORTED_ORACLES:
            raise GuardModelContractError(
                f"unsupported target oracle kind: {kind}"
            )
        _require_text(oracle, "finding_code", where=f"{where}.oracle")
        for prefix in ("known_good", "known_bad"):
            case_file = _inside(
                root,
                _require_text(
                    raw, f"{prefix}_relative_path", where=where
                ),
                must_exist=True,
            )
            expected_hash = _require_text(
                raw, f"{prefix}_sha256", where=where
            )
            if _file_sha256(case_file) != expected_hash:
                raise GuardModelContractError(
                    "logicguard_blocked:target-proof-case-stale:"
                    f"{failure_id}:{prefix}"
                )
    _inside(
        root,
        str(contract["candidate_relative_path"]),
        must_exist=False,
    )
    return path, contract


def bind_target_candidate(
    *,
    target_root: str | Path,
    contract_path: str | Path,
) -> dict[str, Any]:
    root = Path(target_root).resolve(strict=True)
    _path, contract = load_target_contract(
        target_root=root,
        contract_path=contract_path,
    )
    candidate_file = _inside(
        root,
        str(contract["candidate_relative_path"]),
        must_exist=True,
    )
    candidate = _load_document(candidate_file)
    if _candidate_declared_model_id(candidate) != contract["model_id"]:
        raise GuardModelContractError(
            "logicguard_blocked:candidate-model-id-mismatch: candidate "
            "differs from declared current model"
        )
    guard_contract = candidate.get("guard_contract")
    if guard_contract is None:
        guard_contract = {}
        candidate["guard_contract"] = guard_contract
    if not isinstance(guard_contract, dict):
        raise GuardModelContractError(
            "candidate guard_contract must be an object"
        )
    binding = {
        "schema_version": TARGET_BINDING_SCHEMA,
        "contract_role": TARGET_ROLE,
        "contract_id": contract["contract_id"],
        "contract_fingerprint": contract["contract_fingerprint"],
        "candidate_model_fingerprint": _candidate_model_fingerprint(candidate),
        "target_skill_id": contract["target_skill_id"],
        "native_owner_id": contract["native_owner_id"],
        "native_route_id": contract["native_route_id"],
        "purpose": contract["prevented_failure_purpose"],
        "claim_boundary": contract["claim_boundary"],
        "prevented_failure_ids": [
            row["failure_id"]
            for row in contract["prevented_failure_classes"]
        ],
        "purpose_contract_status": "frozen_before_candidate",
        "candidate_authoring_order": TARGET_AUTHORING_ORDER[:4],
    }
    prior = guard_contract.get("target_purpose_binding")
    if prior is not None and prior != binding:
        raise GuardModelContractError(
            "logicguard_blocked:candidate-contract-fingerprint-stale: "
            "candidate already carries foreign target authority"
        )
    guard_contract["target_purpose_binding"] = binding
    _write_document_atomic(candidate_file, candidate)
    return binding


def _validate_target_candidate_binding(
    contract: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> Mapping[str, Any]:
    guard_contract = candidate.get("guard_contract")
    binding = (
        guard_contract.get("target_purpose_binding")
        if isinstance(guard_contract, Mapping)
        else None
    )
    if not isinstance(binding, Mapping):
        raise GuardModelContractError(
            "logicguard_blocked:candidate-contract-fingerprint-missing: "
            "target candidate has no dynamic purpose binding"
        )
    expected = {
        "schema_version": TARGET_BINDING_SCHEMA,
        "contract_role": TARGET_ROLE,
        "contract_id": contract["contract_id"],
        "contract_fingerprint": contract["contract_fingerprint"],
        "candidate_model_fingerprint": _candidate_model_fingerprint(candidate),
        "target_skill_id": contract["target_skill_id"],
        "native_owner_id": contract["native_owner_id"],
        "native_route_id": contract["native_route_id"],
        "purpose": contract["prevented_failure_purpose"],
        "claim_boundary": contract["claim_boundary"],
        "prevented_failure_ids": [
            row["failure_id"]
            for row in contract["prevented_failure_classes"]
        ],
        "purpose_contract_status": "frozen_before_candidate",
        "candidate_authoring_order": TARGET_AUTHORING_ORDER[:4],
    }
    for field, expected_value in expected.items():
        if binding.get(field) != expected_value:
            raise GuardModelContractError(
                "logicguard_blocked:candidate-contract-fingerprint-stale: "
                f"target candidate binding differs: {field}"
            )
    if _candidate_declared_model_id(candidate) != contract["model_id"]:
        raise GuardModelContractError(
            "logicguard_blocked:candidate-model-id-mismatch: candidate "
            "differs from declared current model"
        )
    return binding


def _evaluate_document(
    document: Mapping[str, Any],
) -> tuple[str, list[str], str]:
    from .diagnostics import diagnose_model
    from .execution_depth import _build_native_depth_analysis, model_fingerprint
    from .loader import load_model_from_dict

    model = load_model_from_dict(_model_document(document))
    receipt = _build_native_depth_analysis(model, budget=8)
    findings = [str(value) for value in receipt.unresolved_gaps]
    diagnostics = diagnose_model(model, receipt.evaluation)
    findings.extend(str(row.code) for row in diagnostics.findings)
    return (
        str(receipt.status),
        list(dict.fromkeys(findings)),
        model_fingerprint(model),
    )


def verify_target_contract(
    *,
    target_root: str | Path,
    contract_path: str | Path,
    expected_target_skill_id: str | None = None,
) -> dict[str, Any]:
    root = Path(target_root).resolve(strict=True)
    _path, contract = load_target_contract(
        target_root=root,
        contract_path=contract_path,
    )
    target = str(contract["target_skill_id"])
    if (
        expected_target_skill_id is not None
        and target != expected_target_skill_id
    ):
        raise GuardModelContractError(
            "logicguard_blocked:foreign-target-identity: target contract "
            "belongs to another skill"
        )
    candidate_file = _inside(
        root,
        str(contract["candidate_relative_path"]),
        must_exist=True,
    )
    candidate = _load_document(candidate_file)
    binding = _validate_target_candidate_binding(contract, candidate)
    candidate_status, candidate_findings, native_fingerprint = (
        _evaluate_document(candidate)
    )

    proofs: list[dict[str, Any]] = []
    for failure in contract["prevented_failure_classes"]:
        failure_id = str(failure["failure_id"])
        oracle = failure["oracle"]
        finding_code = str(oracle["finding_code"])
        good_file = _inside(
            root,
            str(failure["known_good_relative_path"]),
            must_exist=True,
        )
        bad_file = _inside(
            root,
            str(failure["known_bad_relative_path"]),
            must_exist=True,
        )
        good_status, good_findings, _ = _evaluate_document(
            _load_document(good_file)
        )
        bad_status, bad_findings, _ = _evaluate_document(
            _load_document(bad_file)
        )

        def fires(findings: list[str]) -> bool:
            return any(
                value == finding_code or value.startswith(finding_code)
                for value in findings
            )

        if good_status != "pass" or fires(good_findings):
            raise GuardModelContractError(
                "logicguard_blocked:target-known-good-failed:"
                f"{failure_id}: status={good_status}; findings={good_findings}"
            )
        if bad_status != "blocked" or not fires(bad_findings):
            raise GuardModelContractError(
                "logicguard_blocked:target-known-bad-did-not-block:"
                f"{failure_id}: status={bad_status}; findings={bad_findings}"
            )
        if candidate_status != "pass" or fires(candidate_findings):
            raise GuardModelContractError(
                "logicguard_blocked:target-candidate-exposes-declared-failure:"
                f"{failure_id}: status={candidate_status}; "
                f"findings={candidate_findings}"
            )
        proofs.append(
            {
                "failure_id": failure_id,
                "oracle": dict(oracle),
                "known_good_sha256": failure["known_good_sha256"],
                "known_bad_sha256": failure["known_bad_sha256"],
                "known_good_status": good_status,
                "known_bad_status": bad_status,
                "candidate_status": candidate_status,
                "finding_observed_in_bad": True,
                "finding_absent_from_good_and_candidate": True,
            }
        )

    return {
        "schema_version": TARGET_PROOF_SCHEMA,
        "status": "pass",
        "contract_role": TARGET_ROLE,
        "contract_id": contract["contract_id"],
        "contract_fingerprint": contract["contract_fingerprint"],
        "model_id": contract["model_id"],
        "candidate_relative_path": contract["candidate_relative_path"],
        "candidate_model_fingerprint": binding[
            "candidate_model_fingerprint"
        ],
        "native_model_fingerprint": native_fingerprint,
        "target_skill_id": target,
        "native_owner_id": contract["native_owner_id"],
        "native_route_id": contract["native_route_id"],
        "prevented_failure_purpose": contract[
            "prevented_failure_purpose"
        ],
        "claim_boundary": contract["claim_boundary"],
        "failure_proofs": proofs,
        "proofed_failure_count": len(proofs),
        "selectable_modes": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=("freeze-target", "bind-target", "verify-target"),
    )
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--declaration")
    parser.add_argument("--contract", required=True)
    parser.add_argument("--target-skill-id")
    args = parser.parse_args(argv)
    try:
        if args.action == "freeze-target":
            if not args.declaration:
                raise GuardModelContractError(
                    "freeze-target requires --declaration"
                )
            detail = freeze_target_contract(
                target_root=args.target_root,
                declaration_path=args.declaration,
                output_path=args.contract,
            )
        elif args.action == "bind-target":
            detail = bind_target_candidate(
                target_root=args.target_root,
                contract_path=args.contract,
            )
        else:
            detail = verify_target_contract(
                target_root=args.target_root,
                contract_path=args.contract,
                expected_target_skill_id=args.target_skill_id,
            )
        result = {
            "schema_version": "researchguard.logic.guard-contract-command.v1",
            "status": "pass",
            "action": args.action,
            "detail": detail,
        }
    except (GuardModelContractError, KeyError, TypeError, ValueError) as exc:
        result = {
            "schema_version": "researchguard.logic.guard-contract-command.v1",
            "status": "blocked",
            "action": args.action,
            "error": str(exc),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
