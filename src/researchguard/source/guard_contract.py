"""Execute target-authored SourceGuard purpose contracts with native evidence.

The fixed oracle catalog describes capabilities SourceGuard can execute.  It
does not prescribe what every target model must prevent.  Each target contract
chooses one or more capabilities and supplies its own observable good/bad
cases before the model can be used.
"""

from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from .depth import build_source_depth_receipt, model_fingerprint
from .schema import (
    BeliefState,
    Observation,
    SchemaError,
    SourceGuardModelContract,
    SourceGuardPreventedFailure,
)


TARGET_PURPOSE_RESULT_SCHEMA = "researchguard.source.target_model_purpose_proof.v1"
PORTABLE_TARGET_PROOF_MATERIAL_SCHEMA = (
    "researchguard.source.portable_target_proof_material.v1"
)
PORTABLE_TARGET_PROOF_MATERIAL_ID = "sourceguard:target-proof-material"


def load_target_contract(path: str | Path) -> SourceGuardModelContract:
    contract_path = Path(path)
    if not contract_path.is_file():
        raise SchemaError(f"explicit model contract does not exist: {contract_path}")
    raw = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    return SourceGuardModelContract.from_dict(raw)


def _resolve_target_input(contract_path: Path, relative_path: str) -> Path:
    if not relative_path or Path(relative_path).is_absolute():
        raise SchemaError("purpose proof observation_path must be target-relative")
    root = contract_path.parent.resolve()
    resolved = (root / relative_path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SchemaError("purpose proof input escapes the target contract root") from exc
    if not resolved.is_file():
        raise SchemaError(f"purpose proof input does not exist: {relative_path}")
    return resolved


def target_contract_input_paths(
    contract: SourceGuardModelContract,
    contract_path: str | Path,
) -> list[Path]:
    contract_path = Path(contract_path).resolve()
    paths = {contract_path}
    for failure in contract.prevented_failures:
        paths.add(_resolve_target_input(contract_path, failure.known_good.observation_path))
        paths.add(_resolve_target_input(contract_path, failure.known_bad.observation_path))
    return sorted(paths, key=lambda item: str(item).casefold())


def target_contract_input_fingerprint(
    contract: SourceGuardModelContract,
    contract_path: str | Path,
) -> str:
    contract_path = Path(contract_path).resolve()
    rows = []
    for path in target_contract_input_paths(contract, contract_path):
        rows.append(
            {
                "path": path.relative_to(contract_path.parent).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(),
            }
        )
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


def _load_observation(path: Path) -> Observation:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Observation.from_dict(raw or {})


def _load_observation_bytes(body: bytes, relative_path: str) -> Observation:
    try:
        raw = yaml.safe_load(body.decode("utf-8"))
    except (UnicodeError, yaml.YAMLError) as exc:
        raise SchemaError(f"portable observation is unreadable: {relative_path}") from exc
    return Observation.from_dict(raw or {})


def _remove_sources_by_role(observation: Observation, roles: set[str]) -> None:
    removed = {
        source.source_id
        for source in observation.observed_sources
        if source.source_role in roles
    }
    observation.observed_sources = [
        source for source in observation.observed_sources if source.source_id not in removed
    ]
    observation.observed_anchors = [
        anchor for anchor in observation.observed_anchors if anchor.source_id not in removed
    ]


def apply_native_oracle_mutation(
    model: BeliefState,
    observation: Observation,
    mutation_id: str,
) -> None:
    if mutation_id == "make-all-anchors-unusable":
        for anchor in observation.observed_anchors:
            anchor.usable_for_claim = False
    elif mutation_id == "remove-direct-source":
        _remove_sources_by_role(observation, {"primary_source", "official_claim"})
    elif mutation_id == "remove-independent-source":
        _remove_sources_by_role(observation, {"independent_report"})
    elif mutation_id == "remove-limiting-source":
        _remove_sources_by_role(observation, {"counter_evidence", "limiting_evidence"})
    elif mutation_id == "collapse-source-lineages":
        for source in observation.observed_sources:
            source.lineage_id = "lineage:collapsed-by-purpose-proof"
    elif mutation_id == "remove-anchor-content":
        for anchor in observation.observed_anchors:
            anchor.text = ""
            anchor.normalized_summary = ""
    elif mutation_id == "shrink-target-unit-inventory":
        model.depth_policy.target_unit_inventory_ids = []
        model.depth_policy.required_target_unit_ids = []
    else:
        raise SchemaError(f"unsupported SourceGuard native mutation: {mutation_id}")


def _native_findings(receipt: Any) -> set[str]:
    findings = {str(value) for value in receipt.coverage_universe.findings}
    findings.update(str(value) for value in receipt.critical_uncovered_ids)
    for row in receipt.coverage_universe.object_depth_rows:
        findings.update(str(value) for value in row.findings)
    return findings


def _evaluate_case(
    model: BeliefState,
    contract_path: Path,
    failure: SourceGuardPreventedFailure,
    *,
    bad: bool,
    portable_documents: dict[str, bytes] | None = None,
) -> tuple[Any, set[str], Path]:
    case = failure.known_bad if bad else failure.known_good
    if portable_documents is None:
        observation_path = _resolve_target_input(contract_path, case.observation_path)
        observation = _load_observation(observation_path)
    else:
        relative = Path(case.observation_path).as_posix()
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise SchemaError("portable purpose proof input escapes the contract root")
        body = portable_documents.get(relative)
        if body is None:
            raise SchemaError(f"portable purpose proof input is missing: {relative}")
        observation_path = contract_path.parent / relative
        observation = _load_observation_bytes(body, relative)
    candidate = deepcopy(model)
    if bad:
        apply_native_oracle_mutation(candidate, observation, case.mutation_id)
    receipt = build_source_depth_receipt(
        candidate,
        observation,
        provider_status="OBSERVATION_SUPPLIED",
    )
    return receipt, _native_findings(receipt), observation_path


def build_portable_target_contract_material(
    model: BeliefState, *, contract_path: str | Path
) -> bytes:
    """Freeze SourceGuard's exact contract/observation proof denominator."""

    contract = model.guard_contract
    if contract is None:
        raise SchemaError("target model purpose proof requires a current contract")
    resolved = Path(contract_path).resolve(strict=True)
    rows = []
    for path in target_contract_input_paths(contract, resolved):
        body = path.read_bytes()
        rows.append(
            {
                "relative_path": path.relative_to(resolved.parent).as_posix(),
                "sha256": hashlib.sha256(body).hexdigest(),
                "body_b64": base64.b64encode(body).decode("ascii"),
            }
        )
    return (
        json.dumps(
            {
                "schema_version": PORTABLE_TARGET_PROOF_MATERIAL_SCHEMA,
                # Portable material must describe the target's logical layout,
                # not the exporter machine's temporary absolute directory.
                "contract_locator": resolved.name,
                "files": rows,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _portable_target_documents(
    model: BeliefState, material: bytes, *, contract_path: str | Path
) -> dict[str, bytes]:
    try:
        raw = json.loads(material.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SchemaError("portable SourceGuard target proof material is not JSON") from exc
    if not isinstance(raw, dict) or set(raw) != {
        "schema_version",
        "contract_locator",
        "files",
    }:
        raise SchemaError("portable SourceGuard target proof denominator is invalid")
    if raw["schema_version"] != PORTABLE_TARGET_PROOF_MATERIAL_SCHEMA:
        raise SchemaError("portable SourceGuard target proof schema is not current")
    resolved = Path(contract_path).resolve()
    locator = Path(str(raw["contract_locator"]))
    if (
        locator.is_absolute()
        or ".." in locator.parts
        or locator.as_posix() != resolved.name
    ):
        raise SchemaError("portable SourceGuard contract locator differs")
    rows = raw["files"]
    if not isinstance(rows, list):
        raise SchemaError("portable SourceGuard target proof files are invalid")
    documents: dict[str, bytes] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "relative_path",
            "sha256",
            "body_b64",
        }:
            raise SchemaError("portable SourceGuard target proof file is invalid")
        relative = Path(str(row["relative_path"])).as_posix()
        if Path(relative).is_absolute() or ".." in Path(relative).parts or relative in documents:
            raise SchemaError("portable SourceGuard target proof path is invalid")
        try:
            body = base64.b64decode(str(row["body_b64"]).encode("ascii"), validate=True)
        except (UnicodeError, ValueError) as exc:
            raise SchemaError("portable SourceGuard target proof bytes are invalid") from exc
        if hashlib.sha256(body).hexdigest() != str(row["sha256"]):
            raise SchemaError("portable SourceGuard target proof fingerprint differs")
        documents[relative] = body
    contract = model.guard_contract
    if contract is None:
        raise SchemaError("target model purpose proof requires a current contract")
    required = {resolved.name}
    for failure in contract.prevented_failures:
        required.add(Path(failure.known_good.observation_path).as_posix())
        required.add(Path(failure.known_bad.observation_path).as_posix())
    if set(documents) != required:
        raise SchemaError("portable SourceGuard target proof file denominator is not closed")
    return documents


def prove_target_model_contract(
    model: BeliefState,
    contract_path: str | Path,
) -> dict[str, Any]:
    contract = model.guard_contract
    if contract is None:
        raise SchemaError("target model purpose proof requires a current contract")
    contract_path = Path(contract_path).resolve()
    from ..portable_material import portable_native_material_bytes_by_id

    portable_material = portable_native_material_bytes_by_id(
        member_id="sourceguard",
        material_id=PORTABLE_TARGET_PROOF_MATERIAL_ID,
    )
    portable_documents = (
        None
        if portable_material is None
        else _portable_target_documents(
            model, portable_material, contract_path=contract_path
        )
    )
    results: list[dict[str, Any]] = []
    for failure in contract.prevented_failures:
        _, good_findings, good_path = _evaluate_case(
            model,
            contract_path,
            failure,
            bad=False,
            portable_documents=portable_documents,
        )
        expected = failure.known_bad.expected_native_finding
        if expected in good_findings:
            raise SchemaError(
                f"known-good did not pass mapped native oracle for {failure.failure_id}: {expected}"
            )
        _, bad_findings, bad_path = _evaluate_case(
            model,
            contract_path,
            failure,
            bad=True,
            portable_documents=portable_documents,
        )
        if expected not in bad_findings:
            raise SchemaError(
                f"known-bad did not trigger mapped native oracle for {failure.failure_id}: "
                f"expected {expected}; observed {sorted(bad_findings)}"
            )
        results.append(
            {
                "failure_id": failure.failure_id,
                "oracle_id": failure.oracle_id,
                "known_good": {
                    "status": "pass",
                    "observation_path": good_path.relative_to(contract_path.parent).as_posix(),
                },
                "known_bad": {
                    "status": "blocked",
                    "observation_path": bad_path.relative_to(contract_path.parent).as_posix(),
                    "native_finding": expected,
                },
            }
        )
    payload = {
        "schema_version": TARGET_PURPOSE_RESULT_SCHEMA,
        "status": "pass",
        "model_id": contract.model_id,
        "model_fingerprint": f"sha256:{model_fingerprint(model)}",
        "model_contract_fingerprint": model.candidate_contract_fingerprint,
        "contract_input_fingerprint": (
            target_contract_input_fingerprint(contract, contract_path)
            if portable_documents is None
            else hashlib.sha256(
                json.dumps(
                    [
                        {
                            "path": relative,
                            "sha256": hashlib.sha256(body).hexdigest().upper(),
                        }
                        for relative, body in sorted(portable_documents.items())
                    ],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest().upper()
        ),
        "failure_results": results,
        "claim_boundary": (
            "This proves only the target-declared SourceGuard-native good/bad contrasts; "
            "it does not prove source truth or final argument support."
        ),
    }
    payload["receipt_fingerprint"] = "sha256:" + hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return payload


__all__ = [
    "TARGET_PURPOSE_RESULT_SCHEMA",
    "apply_native_oracle_mutation",
    "build_portable_target_contract_material",
    "load_target_contract",
    "prove_target_model_contract",
    "target_contract_input_fingerprint",
    "target_contract_input_paths",
]
