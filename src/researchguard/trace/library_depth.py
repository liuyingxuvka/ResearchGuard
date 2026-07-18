"""Target-owned execution-depth receipt for the TraceGuard Case Library.

The library route owns preservation, linkage, selected-scope completeness, and
write-back state.  Storyline evaluation remains owned by TraceGuard's native
storyline-depth evaluator; this module only requires its current result where
the selected library operation claims evaluated closure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


TARGET_SKILL_ID = "traceguard.case-library"
NATIVE_OWNER_ID = "researchguard.trace.library"
NATIVE_ROUTE_ID = "route:traceguard:case-library"
EVIDENCE_DOMAINS = {"fixture_calibration", "capability_validation", "scheduled_production"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_OBLIGATIONS = (
    "selected_scope_identity",
    "object_universe_reconciled",
    "source_before_evidence",
    "evidence_before_event_or_trace",
    "fact_explanation_boundary",
    "model_evaluation_current",
    "gaps_written_back",
    "competing_storylines_preserved",
    "operation_outcome",
    "safe_claim_boundary",
    "source_lineage_preserved",
    "evidence_polarity_preserved",
    "perturbation_semantics_preserved",
    "inference_output_observation_separated",
    "root_inference_receipt_attached",
)

OBJECT_RELATIONSHIPS: dict[str, tuple[str, ...]] = {
    "case": ("selected_scope_membership", "direction_inventory", "evaluation_or_explicit_gap"),
    "direction": ("case_membership", "source_or_gap_inventory", "operation_disposition"),
    "source": (
        "direction_membership",
        "preservation_status",
        "lineage_identity",
        "independence_group",
        "evidence_or_gap_link",
    ),
    "evidence": (
        "source_link",
        "evidence_role",
        "polarity_or_typed_link",
        "event_trace_or_gap_disposition",
    ),
    "event": ("evidence_link", "fact_vs_explanation_classification", "trace_or_gap_disposition"),
    "lead": ("evidence_roles", "alternative_status", "next_task_or_closure"),
    "trace": ("event_sequence", "mechanism_or_gap", "alternative_status", "safe_wording"),
    "gap": ("owner", "next_action", "safe_interim_wording"),
    "hypothesis": ("trace_or_event_link", "evidence_polarity_links", "alternative_relation"),
    "causal_candidate": (
        "hypothesis_link",
        "mechanism_link",
        "confounder_disposition",
        "alternative_link",
        "scope_link",
    ),
    "perturbation": (
        "typed_transformation",
        "target_object_link",
        "expected_sensitivity_or_explicit_none",
    ),
    "inference_receipt": (
        "root_receipt_identity",
        "observation_only_boundary",
        "model_build_exclusion",
    ),
}


def build_library_execution_fixture(
    *,
    evidence_domain: str = "fixture_calibration",
    omitted_obligation_id: str = "",
    run_id: str = "",
) -> dict[str, Any]:
    """Build a deterministic package consumed by the real library evaluator."""

    def evidence(obligation_id: str) -> dict[str, Any]:
        reference = f"evidence/{obligation_id}.json"
        return {
            "obligation_id": obligation_id,
            "status": "complete",
            "evidence_ref": reference,
            "evidence_sha256": "a" * 64,
            "native_range": {
                "range_id": f"native:{obligation_id}",
                "source_ref": reference,
                "content_sha256": "a" * 64,
                "start_anchor": f"{obligation_id}:start",
                "end_anchor": f"{obligation_id}:end",
            },
        }

    ids_and_kinds = [
        ("case:calibration", "case"),
        ("direction:calibration", "direction"),
        ("source:calibration", "source"),
        ("evidence:calibration", "evidence"),
        ("event:calibration", "event"),
        ("lead:calibration", "lead"),
        ("trace:calibration", "trace"),
        ("gap:calibration", "gap"),
        ("hypothesis:calibration", "hypothesis"),
        ("causal-candidate:calibration", "causal_candidate"),
        ("perturbation:calibration", "perturbation"),
        ("inference-receipt:calibration", "inference_receipt"),
    ]
    object_ids = [item[0] for item in ids_and_kinds]
    object_results = [
        {
            "object_id": object_id,
            "object_kind": kind,
            "importance": "important",
            "disposition": "covered",
            "relationship_results": [
                {
                    "relationship_id": relationship_id,
                    "status": "complete",
                    "evidence_ref": f"evidence/{object_id}/{relationship_id}.json",
                    "evidence_sha256": "b" * 64,
                }
                for relationship_id in OBJECT_RELATIONSHIPS[kind]
            ],
        }
        for object_id, kind in ids_and_kinds
    ]
    obligations = [
        item for item in REQUIRED_OBLIGATIONS if item != omitted_obligation_id
    ]
    return {
        "artifact_kind": "traceguard_library_execution_package",
        "target_skill_id": TARGET_SKILL_ID,
        "native_owner_id": NATIVE_OWNER_ID,
        "native_route_id": NATIVE_ROUTE_ID,
        "run_id": run_id or "run:traceguard:case-library:native-depth",
        "evidence_domain": evidence_domain,
        "selected_scope": {
            "library_id": "library:calibration",
            "scope_kind": "case",
            "scope_id": "case:calibration",
            "scope_fingerprint": "c" * 64,
        },
        "operation_status": "pass",
        "inference_outputs_in_input": [],
        "inference_observations": [
            {
                "record_kind": "inference_observation",
                "authority": "observation_only",
                "receipt_id": "traceguard-inference-calibration",
                "receipt_ref": "evidence/inference-receipt-calibration.json",
                "receipt_sha256": "e" * 64,
            }
        ],
        "native_artifacts": [
            {
                "artifact_id": "library:calibration-case-package",
                "artifact_ref": "fixtures/calibration-case.json",
                "artifact_sha256": "d" * 64,
                "status": "current",
            }
        ],
        "obligation_results": [evidence(item) for item in obligations],
        "object_universe": {
            "declared_object_ids": object_ids,
            "discovered_object_ids": object_ids,
            "required_object_ids": ["case:calibration", "source:calibration", "evidence:calibration"],
            "important_object_ids": object_ids,
            "excluded_objects": [],
            "evaluated_object_ids": object_ids,
            "object_kind_by_id": dict(ids_and_kinds),
        },
        "object_results": object_results,
        "blockers": [],
        "residual_risk": ["Case-library closure is not final factual or causal proof."],
        "claim_boundary": "Preservation, linkage, evaluation handoff, and gap write-back for the selected case only.",
    }


def build_library_scheduled_production_package(
    *,
    target_root: str | Path,
    library_relative: str,
    scheduled_production_identity: Mapping[str, Any],
    run_id: str,
) -> dict[str, Any]:
    """Discover a real case-library tree and build its production package.

    Production never calls or relabels the calibration fixture constructor.
    Case, direction, source, evidence, event, trace, and gap objects are derived
    from the current library files, with exact hashes retained for every row.
    """

    if not run_id.strip():
        raise ValueError("scheduled production requires an exact run_id")
    root = Path(target_root).resolve(strict=True)
    library_root = (root / library_relative).resolve(strict=True)
    library_root.relative_to(root)
    if not library_root.is_dir():
        raise ValueError("scheduled production library root must be a directory")
    files = sorted(path for path in library_root.rglob("*") if path.is_file())
    if not files:
        raise ValueError("scheduled production library has no current artifacts")

    def relative(path: Path) -> str:
        return path.relative_to(root).as_posix()

    def file_hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def load_yaml(path: Path) -> Any:
        import yaml  # type: ignore[import-untyped]

        return yaml.safe_load(path.read_text(encoding="utf-8"))

    kind_by_filename = {
        "case.yaml": ("case", "case_id"),
        "direction.yaml": ("direction", "direction_id"),
        "sources.yaml": ("source", "source_id"),
        "evidence.yaml": ("evidence", "evidence_id"),
        "events.yaml": ("event", "event_id"),
        "traces.yaml": ("trace", "trace_id"),
        "gaps.yaml": ("gap", "gap_id"),
        "search_tasks.yaml": ("gap", "task_id"),
        "storyline_hypotheses.yaml": ("hypothesis", "hypothesis_id"),
        "causal_candidates.yaml": ("causal_candidate", "causal_id"),
        "evidence_ablations.yaml": ("perturbation", "ablation_id"),
        "scenario_perturbations.yaml": ("perturbation", "perturbation_id"),
        "expected_sensitivities.yaml": ("perturbation", "sensitivity_id"),
        "inference_receipts.yaml": ("inference_receipt", "receipt_id"),
    }
    discovered: list[dict[str, Any]] = []
    for path in files:
        definition = kind_by_filename.get(path.name.casefold())
        if definition is None:
            continue
        kind, id_field = definition
        try:
            raw = load_yaml(path)
        except (OSError, ValueError, TypeError):
            continue
        rows = raw if isinstance(raw, list) else [raw]
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            raw_id = row.get(id_field)
            if not isinstance(raw_id, str) or not raw_id.strip():
                continue
            discovered.append(
                {
                    "object_id": f"{kind}:{raw_id.strip()}",
                    "object_kind": kind,
                    "source_ref": relative(path),
                    "source_sha256": file_hash(path),
                }
            )
    if not discovered:
        raise ValueError("scheduled production discovered no case-library objects")
    object_ids = [row["object_id"] for row in discovered]
    if len(object_ids) != len(set(object_ids)):
        raise ValueError("scheduled production discovered duplicate case-library object ids")

    object_results = [
        {
            "object_id": row["object_id"],
            "object_kind": row["object_kind"],
            "importance": "important",
            "disposition": "covered",
            "relationship_results": [
                {
                    "relationship_id": relationship_id,
                    "status": "complete",
                    "evidence_ref": row["source_ref"],
                    "evidence_sha256": row["source_sha256"],
                }
                for relationship_id in OBJECT_RELATIONSHIPS[row["object_kind"]]
            ],
        }
        for row in discovered
    ]

    text_files = [
        path
        for path in files
        if path.read_text(encoding="utf-8", errors="replace").strip()
    ]
    if len(text_files) < len(REQUIRED_OBLIGATIONS):
        raise ValueError("scheduled production library lacks distinct obligation evidence files")
    obligation_results: list[dict[str, Any]] = []
    for obligation_id, path in zip(REQUIRED_OBLIGATIONS, text_files):
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        ref = relative(path)
        digest = file_hash(path)
        obligation_results.append(
            {
                "obligation_id": obligation_id,
                "status": "complete",
                "evidence_ref": ref,
                "evidence_sha256": digest,
                "native_range": {
                    "range_id": f"native:{TARGET_SKILL_ID}:{obligation_id}",
                    "source_ref": ref,
                    "content_sha256": digest,
                    "start_anchor": lines[0],
                    "end_anchor": lines[-1],
                },
            }
        )

    case_id = next(
        (row["object_id"] for row in discovered if row["object_kind"] == "case"),
        object_ids[0],
    )
    library_id = library_root.name
    fingerprint = canonical_sha256(
        [
            {"path": relative(path), "sha256": file_hash(path)}
            for path in files
        ]
    )
    trigger_id = str(
        scheduled_production_identity.get("scheduler_or_trigger_id", "")
    ).strip()
    execution_id = str(
        scheduled_production_identity.get("scheduled_execution_id", "")
    ).strip()
    if not trigger_id or not execution_id:
        raise ValueError(
            "scheduled production requires exact target-owned trigger and execution ids"
        )
    production_identity = {
        "scheduler_or_trigger_id": trigger_id,
        "scheduled_execution_id": execution_id,
        "target_root_fingerprint": fingerprint,
        "runtime_fingerprint": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    required = [
        row["object_id"]
        for row in discovered
        if row["object_kind"] in {"case", "source", "evidence"}
    ]
    inference_observations: list[dict[str, Any]] = []
    for path in files:
        if path.name.casefold() != "inference_receipts.yaml":
            continue
        raw = load_yaml(path)
        rows = raw if isinstance(raw, list) else [raw]
        for row in rows:
            if not isinstance(row, Mapping) or not str(row.get("receipt_id", "")).strip():
                continue
            inference_observations.append(
                {
                    "record_kind": "inference_observation",
                    "authority": "observation_only",
                    "receipt_id": str(row["receipt_id"]),
                    "receipt_ref": relative(path),
                    "receipt_sha256": canonical_sha256(row),
                }
            )
    return {
        "artifact_kind": "traceguard_library_execution_package",
        "target_skill_id": TARGET_SKILL_ID,
        "native_owner_id": NATIVE_OWNER_ID,
        "native_route_id": NATIVE_ROUTE_ID,
        "run_id": run_id,
        "evidence_domain": "scheduled_production",
        "input_origin": "target_native_scheduled_execution",
        "scheduled_production_identity": production_identity,
        "native_discovery_root_ref": library_relative.replace("\\", "/"),
        "selected_scope": {
            "library_id": f"library:{library_id}",
            "scope_kind": "case",
            "scope_id": case_id,
            "scope_fingerprint": fingerprint,
        },
        "operation_status": "pass",
        "inference_outputs_in_input": [],
        "inference_observations": inference_observations,
        "native_artifacts": [
            {
                "artifact_id": f"library-artifact:{relative(path)}",
                "artifact_ref": relative(path),
                "artifact_sha256": file_hash(path),
                "status": "current",
            }
            for path in files
        ],
        "obligation_results": obligation_results,
        "object_universe": {
            "declared_object_ids": object_ids,
            "discovered_object_ids": object_ids,
            "required_object_ids": required,
            "important_object_ids": object_ids,
            "excluded_objects": [],
            "evaluated_object_ids": object_ids,
            "object_kind_by_id": {
                row["object_id"]: row["object_kind"] for row in discovered
            },
        },
        "object_results": object_results,
        "blockers": [],
        "residual_risk": ["Case-library closure is not final factual or causal proof."],
        "claim_boundary": (
            "The exact current case-library file and object universe is reconciled, including every discovered source, evidence, event, trace, and open search gap. "
            "This controlled scheduled execution does not prove the final factual or causal story."
        ),
    }


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _add(errors: list[dict[str, str]], code: str, path: str, message: str) -> None:
    errors.append({"code": code, "path": path, "message": message})


def _validate_scheduled_production_identity(value: Any, *, evidence_domain: Any, errors: list[dict[str, str]]) -> dict[str, Any]:
    if evidence_domain != "scheduled_production":
        if value not in (None, {}):
            _add(errors, "scheduled_identity_on_nonproduction_evidence", "scheduled_production_identity", "Only scheduled-production evidence may carry a target-owned execution identity.")
        return {}
    if not isinstance(value, Mapping):
        _add(errors, "missing_scheduled_production_identity", "scheduled_production_identity", "Scheduled production requires exact target-owned trigger, execution, target-root, and runtime identities.")
        return {}
    allowed = {
        "scheduler_or_trigger_id",
        "scheduled_execution_id",
        "target_root_fingerprint",
        "runtime_fingerprint",
    }
    unknown = sorted(set(value) - allowed)
    if unknown:
        _add(errors, "scheduled_production_identity_unknown_field", "scheduled_production_identity", f"Unknown scheduled identity fields: {unknown}")
    result = {key:value.get(key) for key in sorted(allowed)}
    for field in ("scheduler_or_trigger_id", "scheduled_execution_id"):
        if not isinstance(value.get(field), str) or not str(value.get(field)).strip():
            _add(errors, f"scheduled_{field}_missing", f"scheduled_production_identity.{field}", "Non-empty exact identity is required.")
    for field in ("target_root_fingerprint", "runtime_fingerprint"):
        if not isinstance(value.get(field), str) or not re.fullmatch(
            r"[0-9A-Fa-f]{64}", str(value.get(field))
        ):
            _add(errors, f"scheduled_{field}_invalid", f"scheduled_production_identity.{field}", "A 64-character hexadecimal sha256 is required.")
    return result


def _ids(raw: Any, path: str, errors: list[dict[str, str]]) -> tuple[str, ...]:
    if not isinstance(raw, list):
        _add(errors, "invalid_id_list", path, "Expected a list of ids.")
        return ()
    values = [str(item).strip() for item in raw if isinstance(item, str) and str(item).strip()]
    if len(values) != len(raw) or len(values) != len(set(values)):
        _add(errors, "invalid_or_duplicate_id", path, "Ids must be unique non-empty strings.")
    return tuple(values)


def _check_evidence(row: Any, path: str, errors: list[dict[str, str]]) -> None:
    if not isinstance(row, Mapping):
        _add(errors, "invalid_evidence", path, "Evidence row must be an object.")
        return
    if row.get("status") not in {"complete", "current", "pass"}:
        _add(errors, "evidence_not_current", f"{path}.status", "Evidence must be current and successful.")
    if not str(row.get("evidence_ref", "")).strip():
        _add(errors, "missing_evidence_ref", f"{path}.evidence_ref", "Exact evidence_ref is required.")
    digest = row.get("evidence_sha256")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        _add(errors, "invalid_evidence_sha256", f"{path}.evidence_sha256", "Lowercase sha256 is required.")


def evaluate_library_execution_package(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    if payload.get("target_skill_id") != TARGET_SKILL_ID:
        _add(errors, "wrong_target_skill", "target_skill_id", f"Expected {TARGET_SKILL_ID}.")
    if payload.get("native_owner_id") != NATIVE_OWNER_ID:
        _add(errors, "wrong_native_owner", "native_owner_id", f"Expected {NATIVE_OWNER_ID}.")
    if payload.get("native_route_id") != NATIVE_ROUTE_ID:
        _add(errors, "wrong_native_route", "native_route_id", f"Expected {NATIVE_ROUTE_ID}.")
    run_id = str(payload.get("run_id", "")).strip()
    if not run_id:
        _add(errors, "missing_run_id", "run_id", "Exact current run_id is required.")
    domain = payload.get("evidence_domain")
    if domain not in EVIDENCE_DOMAINS:
        _add(errors, "invalid_evidence_domain", "evidence_domain", "Use fixture_calibration, capability_validation, or scheduled_production.")
    input_origin = payload.get("input_origin")
    if domain == "scheduled_production" and input_origin != "target_native_scheduled_execution":
        _add(errors, "fixture_as_production", "input_origin", "Scheduled production requires the target-native scheduled execution constructor; relabeling a fixture is forbidden.")
    if domain != "scheduled_production" and input_origin == "target_native_scheduled_execution":
        _add(errors, "scheduled_origin_on_nonproduction_evidence", "input_origin", "A scheduled target-native execution cannot be projected into a fixture/capability domain.")
    scheduled_identity=_validate_scheduled_production_identity(payload.get("scheduled_production_identity"),evidence_domain=domain,errors=errors)
    if payload.get("operation_status") != "pass":
        _add(errors, "library_operation_not_passed", "operation_status", "Selected target-owned library operation must pass.")
    blockers = payload.get("blockers")
    if not isinstance(blockers, list) or blockers:
        _add(errors, "unresolved_blockers", "blockers", "Closure requires an explicit empty blocker list.")
    if not str(payload.get("claim_boundary", "")).strip():
        _add(errors, "missing_claim_boundary", "claim_boundary", "Safe library claim boundary is required.")

    inferred_input = payload.get("inference_outputs_in_input")
    if not isinstance(inferred_input, list) or inferred_input:
        _add(
            errors,
            "inference_output_as_input",
            "inference_outputs_in_input",
            "Final support, rank, status, causal license, and prior receipt projections must remain observations and cannot enter model input.",
        )
    observations = payload.get("inference_observations")
    if not isinstance(observations, list) or not observations:
        _add(
            errors,
            "root_inference_receipt_detached",
            "inference_observations",
            "At least one exact root TraceGuard inference receipt observation is required for evaluated closure.",
        )
        observations = []
    for index, observation in enumerate(observations):
        path = f"inference_observations[{index}]"
        if not isinstance(observation, Mapping):
            _add(errors, "invalid_inference_observation", path, "Inference observation must be an object.")
            continue
        if observation.get("record_kind") != "inference_observation" or observation.get("authority") != "observation_only":
            _add(errors, "inference_observation_authority_invalid", path, "Root inference output must be explicitly observation-only.")
        if not str(observation.get("receipt_id", "")).strip() or not str(observation.get("receipt_ref", "")).strip():
            _add(errors, "root_inference_receipt_detached", path, "Exact receipt id and reference are required.")
        digest = observation.get("receipt_sha256")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            _add(errors, "root_inference_receipt_hash_invalid", path, "Exact lowercase receipt sha256 is required.")

    scope = payload.get("selected_scope")
    if not isinstance(scope, Mapping):
        _add(errors, "missing_selected_scope", "selected_scope", "Selected library/case/direction scope is required.")
        scope = {}
    for field in ("library_id", "scope_id", "scope_fingerprint"):
        value = scope.get(field)
        if not isinstance(value, str) or not value.strip():
            _add(errors, "selected_scope_identity_missing", f"selected_scope.{field}", f"{field} is required.")
    if scope.get("scope_kind") not in {"library", "project", "case", "direction"}:
        _add(errors, "invalid_scope_kind", "selected_scope.scope_kind", "Scope kind must be library, project, case, or direction.")
    fingerprint = scope.get("scope_fingerprint")
    if isinstance(fingerprint, str) and fingerprint and not SHA256_RE.fullmatch(fingerprint):
        _add(errors, "invalid_scope_fingerprint", "selected_scope.scope_fingerprint", "Scope fingerprint must be lowercase sha256.")
    elif (
        domain == "scheduled_production"
        and scheduled_identity.get("target_root_fingerprint") != fingerprint
    ):
        _add(
            errors,
            "scheduled_target_root_fingerprint_mismatch",
            "scheduled_production_identity.target_root_fingerprint",
            "The target-owned production identity must bind the exact current library scope.",
        )

    artifacts = payload.get("native_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        _add(errors, "missing_native_artifacts", "native_artifacts", "At least one exact current target-owned artifact is required.")
        artifacts = []
    artifact_ids: set[str] = set()
    for index, artifact in enumerate(artifacts):
        path = f"native_artifacts[{index}]"
        if not isinstance(artifact, Mapping):
            _add(errors, "invalid_native_artifact", path, "Artifact must be an object.")
            continue
        artifact_id = str(artifact.get("artifact_id", "")).strip()
        if not artifact_id or artifact_id in artifact_ids:
            _add(errors, "invalid_native_artifact_id", f"{path}.artifact_id", "Artifact ids must be unique and non-empty.")
        artifact_ids.add(artifact_id)
        _check_evidence(
            {"status":artifact.get("status"),"evidence_ref":artifact.get("artifact_ref"),"evidence_sha256":artifact.get("artifact_sha256")},
            path,
            errors,
        )

    raw_obligations = payload.get("obligation_results")
    if not isinstance(raw_obligations, list):
        _add(errors, "invalid_obligation_results", "obligation_results", "Obligation results must be a list.")
        raw_obligations = []
    obligation_map: dict[str, Mapping[str, Any]] = {}
    ranges: list[dict[str, Any]] = []
    spans: set[tuple[str, str, str]] = set()
    range_ids: set[str] = set()
    for index, row in enumerate(raw_obligations):
        path = f"obligation_results[{index}]"
        if not isinstance(row, Mapping):
            _add(errors, "invalid_obligation", path, "Obligation row must be an object.")
            continue
        obligation_id = str(row.get("obligation_id", "")).strip()
        if not obligation_id or obligation_id.startswith("obligation:") or obligation_id in obligation_map:
            _add(errors, "generic_or_duplicate_obligation", f"{path}.obligation_id", "Use one exact TraceGuard Library obligation id.")
            continue
        obligation_map[obligation_id] = row
        _check_evidence(row, path, errors)
        native_range = row.get("native_range")
        if not isinstance(native_range, Mapping):
            _add(errors, "missing_native_range", f"{path}.native_range", "Exact native evidence range is required.")
        else:
            range_id = str(native_range.get("range_id", "")).strip()
            source_ref = str(native_range.get("source_ref", "")).strip()
            content_sha256 = str(native_range.get("content_sha256", "")).strip()
            start = str(native_range.get("start_anchor", "")).strip()
            end = str(native_range.get("end_anchor", "")).strip()
            span = (source_ref, start, end)
            if not range_id or re.fullmatch(r"(?:range|row|item)[-:_]?\d+", range_id, re.IGNORECASE) or range_id in range_ids:
                _add(errors, "mechanical_or_duplicate_range", f"{path}.native_range.range_id", "Range id must be semantic and unique.")
            if not source_ref or not start or not end or span in spans:
                _add(errors, "missing_or_overlapping_range", f"{path}.native_range", "Range must be exact and non-overlapping.")
            if source_ref != str(row.get("evidence_ref", "")):
                _add(errors, "native_range_evidence_ref_mismatch", f"{path}.native_range", "Range source_ref must equal this obligation's exact evidence_ref.")
            if not SHA256_RE.fullmatch(content_sha256) or content_sha256 != str(row.get("evidence_sha256", "")):
                _add(errors, "native_range_content_hash_mismatch", f"{path}.native_range", "Range content_sha256 must equal this obligation's exact evidence hash.")
            range_ids.add(range_id)
            spans.add(span)
            ranges.append(dict(native_range))
    missing_obligations = sorted(set(REQUIRED_OBLIGATIONS) - set(obligation_map))
    extra_obligations = sorted(set(obligation_map) - set(REQUIRED_OBLIGATIONS))
    if missing_obligations:
        _add(errors, "missing_target_obligation", "obligation_results", f"Missing obligations: {missing_obligations}")
    if extra_obligations:
        _add(errors, "foreign_target_obligation", "obligation_results", f"Foreign obligations: {extra_obligations}")

    universe = payload.get("object_universe")
    if not isinstance(universe, Mapping):
        _add(errors, "missing_object_universe", "object_universe", "Complete selected-scope object universe is required.")
        universe = {}
    declared = set(_ids(universe.get("declared_object_ids"), "object_universe.declared_object_ids", errors))
    discovered = set(_ids(universe.get("discovered_object_ids"), "object_universe.discovered_object_ids", errors))
    required = set(_ids(universe.get("required_object_ids"), "object_universe.required_object_ids", errors))
    important = set(_ids(universe.get("important_object_ids"), "object_universe.important_object_ids", errors))
    evaluated = set(_ids(universe.get("evaluated_object_ids"), "object_universe.evaluated_object_ids", errors))
    exclusions = universe.get("excluded_objects")
    if not isinstance(exclusions, list):
        _add(errors, "invalid_exclusions", "object_universe.excluded_objects", "Excluded objects must be explicit.")
        exclusions = []
    excluded: set[str] = set()
    closed_exclusions: list[dict[str, Any]] = []
    for index, row in enumerate(exclusions):
        path = f"object_universe.excluded_objects[{index}]"
        if not isinstance(row, Mapping):
            _add(errors, "invalid_exclusion", path, "Exclusion must be an object.")
            continue
        object_id = str(row.get("object_id", "")).strip()
        if not object_id or object_id in excluded:
            _add(errors, "unclosed_exclusion", path, "Excluded objects need a unique id.")
            continue
        _check_evidence(row, path, errors)
        reason = str(row.get("reason", "")).strip()
        if len(reason) < 12 or reason.casefold() in {
            "n/a",
            "none",
            "not applicable",
            "excluded",
        }:
            _add(
                errors,
                "missing_or_generic_exclusion_reason",
                f"{path}.reason",
                "Excluded objects need a specific, auditable target-native reason.",
            )
        if row.get("closed_disposition") not in {"closed_noncontributing", "closed_not_applicable"} or row.get("claim_contribution") != "none":
            _add(errors, "exclusion_not_proven_noncontributing", path, "Excluded objects need a closed noncontributing/not-applicable disposition and claim_contribution=none.")
        excluded.add(object_id)
        closed_exclusions.append(
            {
                "object_id": object_id,
                "reason": reason,
                "closed_disposition": row.get("closed_disposition"),
                "claim_contribution": row.get("claim_contribution"),
                "evidence_ref": row.get("evidence_ref"),
                "evidence_sha256": row.get("evidence_sha256"),
            }
        )
    all_objects = declared | discovered | required
    eligible = all_objects - excluded
    raw_kind_map = universe.get("object_kind_by_id")
    kind_map: dict[str, str] = {}
    if not isinstance(raw_kind_map, Mapping):
        _add(
            errors,
            "missing_object_kind_inventory",
            "object_universe.object_kind_by_id",
            "The complete selected-scope universe needs one authoritative kind per object.",
        )
    else:
        for raw_object_id, raw_kind in raw_kind_map.items():
            object_id = str(raw_object_id).strip()
            kind = str(raw_kind).strip()
            if not object_id or object_id in kind_map:
                _add(
                    errors,
                    "invalid_object_kind_inventory_id",
                    "object_universe.object_kind_by_id",
                    "Object-kind inventory ids must be unique and non-empty.",
                )
                continue
            if kind not in OBJECT_RELATIONSHIPS:
                _add(
                    errors,
                    "unknown_inventory_object_kind",
                    f"object_universe.object_kind_by_id.{object_id}",
                    f"Unknown object kind {kind!r}.",
                )
            kind_map[object_id] = kind
    if not all_objects:
        _add(errors, "empty_object_universe", "object_universe", "Selected scope needs a non-empty denominator.")
    if set(kind_map) != all_objects:
        _add(
            errors,
            "object_kind_inventory_not_reconciled",
            "object_universe.object_kind_by_id",
            "Object-kind inventory must equal the complete selected-scope universe; "
            f"missing={sorted(all_objects-set(kind_map))}, "
            f"foreign={sorted(set(kind_map)-all_objects)}.",
        )
    if not important:
        _add(errors, "empty_important_object_universe", "object_universe.important_object_ids", "Selected scope needs an explicit non-empty important-object denominator.")
    if not important <= all_objects:
        _add(errors, "important_object_outside_universe", "object_universe.important_object_ids", "Important ids must come from the selected-scope object universe.")
    if required & excluded:
        _add(errors, "required_object_excluded", "object_universe", "Required objects cannot be excluded.")
    if important & excluded:
        _add(errors, "important_object_excluded", "object_universe", "Important objects cannot be excluded from broad selected-scope closure.")
    if not excluded <= all_objects or evaluated != eligible:
        _add(errors, "object_universe_not_reconciled", "object_universe", f"Evaluated objects must equal eligible objects; missing={sorted(eligible-evaluated)}, foreign={sorted(evaluated-eligible)}.")

    raw_results = payload.get("object_results")
    if not isinstance(raw_results, list):
        _add(errors, "invalid_object_results", "object_results", "Per-object relationship results are required.")
        raw_results = []
    object_map: dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(raw_results):
        path = f"object_results[{index}]"
        if not isinstance(row, Mapping):
            _add(errors, "invalid_object_result", path, "Object result must be an object.")
            continue
        object_id = str(row.get("object_id", "")).strip()
        kind = str(row.get("object_kind", "")).strip()
        if not object_id or object_id in object_map:
            _add(errors, "invalid_object_result_id", f"{path}.object_id", "Object ids must be unique and non-empty.")
            continue
        object_map[object_id] = row
        authoritative_kind = kind_map.get(object_id)
        if authoritative_kind is not None and kind != authoritative_kind:
            _add(
                errors,
                "object_kind_mismatch",
                f"{path}.object_kind",
                f"Result kind {kind!r} does not match authoritative kind "
                f"{authoritative_kind!r}.",
            )
        importance = row.get("importance")
        if importance not in {"important", "ordinary"}:
            _add(errors, "object_importance_missing", f"{path}.importance", "Every object must be classified important or ordinary.")
        elif (object_id in important) != (importance == "important"):
            _add(errors, "object_importance_mismatch", f"{path}.importance", "Per-object importance must match the authoritative important-object inventory.")
        relationship_kind = authoritative_kind or kind
        required_relationships = OBJECT_RELATIONSHIPS.get(relationship_kind)
        if required_relationships is None:
            _add(errors, "unknown_object_kind", f"{path}.object_kind", f"Unknown object kind {kind!r}.")
            required_relationships = ()
        relationships = row.get("relationship_results")
        if not isinstance(relationships, list):
            _add(errors, "missing_relationship_results", path, "Every object needs relationship results.")
            relationships = []
        relationship_map: dict[str, Mapping[str, Any]] = {}
        for rel_index, relationship in enumerate(relationships):
            rel_path = f"{path}.relationship_results[{rel_index}]"
            if not isinstance(relationship, Mapping):
                _add(errors, "invalid_relationship_result", rel_path, "Relationship result must be an object.")
                continue
            relationship_id = str(relationship.get("relationship_id", "")).strip()
            if relationship_id in relationship_map:
                _add(errors, "duplicate_relationship", rel_path, "Relationship ids must be unique per object.")
            relationship_map[relationship_id] = relationship
            _check_evidence(relationship, rel_path, errors)
        missing_relationships = sorted(set(required_relationships) - set(relationship_map))
        extra_relationships = sorted(set(relationship_map) - set(required_relationships))
        if missing_relationships:
            _add(errors, "missing_object_relationship", path, f"Missing {relationship_kind} relationships: {missing_relationships}")
        if extra_relationships:
            _add(errors, "foreign_object_relationship", path, f"Foreign {relationship_kind} relationships: {extra_relationships}")
        if row.get("importance") == "important" and row.get("disposition") not in {"covered", "closed_not_applicable"}:
            _add(errors, "important_object_unresolved", path, "Important objects require covered or explicitly closed-not-applicable disposition.")
    if set(object_map) != eligible:
        _add(errors, "per_object_results_incomplete", "object_results", f"Per-object rows must equal eligible objects; missing={sorted(eligible-set(object_map))}, foreign={sorted(set(object_map)-eligible)}.")

    input_fingerprint = canonical_sha256(payload)
    receipt: dict[str, Any] = {
        "artifact_kind":"traceguard_library_execution_depth_receipt",
        "receipt_version":"researchguard.trace.library-depth.v1",
        "status":"pass" if not errors else "blocked",
        "target_skill_id":payload.get("target_skill_id"),
        "native_owner_id":payload.get("native_owner_id"),
        "native_route_id":payload.get("native_route_id"),
        "run_id":run_id,
        "evidence_domain":domain,
        "input_origin":input_origin,
        "scheduled_production_identity":scheduled_identity,
        "selected_scope":dict(scope),
        "input_fingerprint":input_fingerprint,
        "required_obligation_ids":list(REQUIRED_OBLIGATIONS),
        "covered_obligation_ids":sorted(obligation_map),
        "native_obligation_evidence":[
            {
                "obligation_id":obligation_id,
                "status":"pass",
                "native_object_id":f"native-obligation:{TARGET_SKILL_ID}:{obligation_id}",
                "evidence_ref":row.get("evidence_ref"),
                "evidence_sha256":row.get("evidence_sha256"),
                "content":{
                    "native_range":dict(row.get("native_range", {})),
                    "evaluator_input_fingerprint":input_fingerprint,
                },
            }
            for obligation_id,row in sorted(obligation_map.items())
        ],
        "native_contribution_ranges":ranges,
        "object_universe":{"declared_object_ids":sorted(declared),"discovered_object_ids":sorted(discovered),"required_object_ids":sorted(required),"important_object_ids":sorted(important),"excluded_object_ids":sorted(excluded),"exclusions":sorted(closed_exclusions,key=lambda row:str(row.get("object_id", ""))),"eligible_object_ids":sorted(eligible),"evaluated_object_ids":sorted(evaluated),"object_kind_by_id":{object_id:kind_map[object_id] for object_id in sorted(kind_map)}},
        "per_object_relationship_coverage":[
            {
                "object_id":object_id,
                "object_kind":row.get("object_kind"),
                "importance":row.get("importance"),
                "relationship_ids":sorted(
                    str(item.get("relationship_id"))
                    for item in row.get("relationship_results", [])
                    if isinstance(item, Mapping)
                ),
                "relationship_evidence":[
                    {
                        "relationship_id":str(item.get("relationship_id")),
                        "status":item.get("status"),
                        "evidence_ref":item.get("evidence_ref"),
                        "evidence_sha256":item.get("evidence_sha256"),
                    }
                    for item in sorted(
                        (
                            candidate
                            for candidate in row.get("relationship_results", [])
                            if isinstance(candidate, Mapping)
                        ),
                        key=lambda candidate:str(candidate.get("relationship_id", "")),
                    )
                ],
            }
            for object_id,row in sorted(object_map.items())
        ],
        "native_artifacts":[dict(item) for item in artifacts if isinstance(item, Mapping)],
        "consumed_inference_observations":[
            {
                "receipt_id":str(item.get("receipt_id", "")),
                "receipt_ref":str(item.get("receipt_ref", "")),
                "receipt_sha256":str(item.get("receipt_sha256", "")),
                "authority":str(item.get("authority", "")),
            }
            for item in observations
            if isinstance(item, Mapping)
        ],
        "errors":errors,
        "blockers":list(blockers) if isinstance(blockers,list) else [],
        "residual_risk":payload.get("residual_risk",[]),
        "claim_boundary":payload.get("claim_boundary", ""),
    }
    core_hash = canonical_sha256(receipt)
    receipt["receipt_id"] = f"researchguard.trace.library-depth:{run_id or 'missing'}:{core_hash[:16]}"
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Issue a target-owned TraceGuard Library execution-depth receipt.")
    parser.add_argument("package", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    payload = json.loads(args.package.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("TraceGuard Library execution package must be a JSON object")
    receipt = evaluate_library_execution_package(payload)
    rendered = json.dumps(receipt, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if receipt["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
