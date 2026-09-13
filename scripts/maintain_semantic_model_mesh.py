#!/usr/bin/env python3
"""Maintain a ResearchGuard semantic self-mesh under explicit evidence gates.

The checked-in semantic mesh is a candidate structural declaration.  This tool
provides the small, controlled authoring operation that the FlowGuard package
does not currently expose: load the current mesh, validate its exact manifest
membership and relation contracts, recompute the relation fingerprint with
FlowGuard's private helper, and optionally write a corrected candidate and an
immutable before/after receipt.

The write path is deliberately opt-in (``--write``), preserves every authority
and status field, and never promotes ``semantic_model_status``.  The relation
hash function is private in FlowGuard; the tool loads that private source
function without importing the package and records that provenance explicitly.
It must not be described as a public FlowGuard API.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping


SEMANTIC_MESH_SCHEMA = "flowguard.semantic_self_mesh.v3"
SEMANTIC_MESH_RELATIVE_PATH = Path(
    ".flowguard/models/owners/authoritative_model_system/semantic_model_mesh.json"
)
MANIFEST_RELATIVE_PATH = Path(".flowguard/models/regression-manifest.json")
RECEIPT_SCHEMA = "researchguard.semantic_model_mesh_maintenance_receipt.v1"

TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "mesh_id",
        "claim_scope",
        "derivation_base_snapshot_path",
        "derivation_base_snapshot_fingerprint",
        "current_manifest_path",
        "observed_base_added_model_ids",
        "observed_base_removed_model_ids",
        "declared_model_count",
        "semantic_universe_fingerprint",
        "semantic_disposition_fingerprint",
        "semantic_relation_fingerprint",
        "semantic_model_status",
        "whole_system_completion_claim",
        "currentness_owner",
        "claim_boundary",
        "allowed_dispositions",
        "semantic_parents",
        "required_terminal_evidence",
        "models",
        "feedback_progress_contracts",
    }
)
MODEL_REQUIRED_FIELDS = frozenset(
    {
        "model_id",
        "disposition",
        "consumer_ids",
        "rationale",
        "structural_parent_id",
        "cross_boundary_parent_ids",
    }
)
MODEL_ALLOWED_FIELDS = MODEL_REQUIRED_FIELDS | {"scope_rationale"}
FEEDBACK_FIELDS = frozenset(
    {
        "relation_id",
        "contract_id",
        "contract_kind",
        "evidence_source_kind",
        "evidence_model_ids",
        "rationale",
    }
)
TOPOLOGY_MUTABLE_FIELDS = frozenset(
    {
        "declared_model_count",
        "semantic_parents",
        "models",
        "feedback_progress_contracts",
        "semantic_relation_fingerprint",
    }
)
STATUS_FIELDS = frozenset({"semantic_model_status", "whole_system_completion_claim"})


class SemanticMeshMaintenanceError(ValueError):
    """A fail-closed input, contract, or write-gate error."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            **self.details,
        }


class _DuplicateJsonKey(ValueError):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def _no_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(key)
        result[key] = value
    return result


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )


def _local_fingerprint_value(value: Any) -> str:
    """The exact canonical bridge used by FlowGuard's evidence receipts.

    The actual relation calculation is loaded from the FlowGuard source below;
    this bridge is supplied to that private function so package import side
    effects cannot turn maintenance into a broad project operation.
    """

    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _file_fingerprint(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _read_bytes(path: Path, *, missing_code: str = "missing_file") -> bytes:
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise SemanticMeshMaintenanceError(
            missing_code,
            f"required file is missing: {path}",
            path=str(path),
        ) from exc
    except OSError as exc:
        raise SemanticMeshMaintenanceError(
            "read_failed",
            f"could not read required file: {path}",
            path=str(path),
            reason=str(exc),
        ) from exc


def _load_json_object(raw: bytes, *, path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_no_duplicate_json_keys,
        )
    except UnicodeDecodeError as exc:
        raise SemanticMeshMaintenanceError(
            "invalid_utf8",
            f"JSON file is not UTF-8: {path}",
            path=str(path),
        ) from exc
    except (_DuplicateJsonKey, json.JSONDecodeError) as exc:
        duplicate = (
            f"duplicate JSON key {exc.key!r}"
            if isinstance(exc, _DuplicateJsonKey)
            else str(exc)
        )
        raise SemanticMeshMaintenanceError(
            "invalid_json",
            f"JSON file is invalid: {path} ({duplicate})",
            path=str(path),
        ) from exc
    if not isinstance(value, dict):
        raise SemanticMeshMaintenanceError(
            "invalid_json_object",
            f"JSON root must be an object: {path}",
            path=str(path),
        )
    return value


def _resolve_inside(root: Path, value: str | Path | None, default: Path) -> Path:
    raw = Path(value) if value is not None else default
    path = raw if raw.is_absolute() else root / raw
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise SemanticMeshMaintenanceError(
            "path_outside_root",
            "managed mesh, candidate, output, and receipt paths must remain inside the repository root",
            path=str(resolved_path),
            root=str(resolved_root),
        ) from exc
    return resolved_path


def _relative_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise SemanticMeshMaintenanceError(
            "path_outside_root",
            f"path is outside repository root: {path}",
            path=str(path),
            root=str(root.resolve()),
        ) from exc


def _nonempty_string(value: Any, *, code: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SemanticMeshMaintenanceError(code, f"{label} must be a non-empty string")
    return value.strip()


def _string_list(value: Any, *, code: str, label: str, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise SemanticMeshMaintenanceError(code, f"{label} must be a JSON array")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise SemanticMeshMaintenanceError(code, f"{label} contains an empty/non-string value")
        result.append(item.strip())
    if len(result) != len(set(result)):
        raise SemanticMeshMaintenanceError(
            "duplicate_contract_value",
            f"{label} contains duplicate values",
            label=label,
        )
    if nonempty and not result:
        raise SemanticMeshMaintenanceError(code, f"{label} must not be empty")
    return result


def _load_manifest_model_ids(root: Path, manifest_path: Path) -> tuple[set[str], bytes]:
    raw = _read_bytes(manifest_path, missing_code="manifest_missing")
    manifest = _load_json_object(raw, path=manifest_path)
    rows = manifest.get("models")
    if not isinstance(rows, list) or not rows:
        raise SemanticMeshMaintenanceError(
            "manifest_models_invalid",
            "current regression manifest must contain a non-empty models array",
            path=str(manifest_path),
        )
    ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise SemanticMeshMaintenanceError(
                "manifest_model_row_invalid",
                "current regression manifest model rows must be objects",
                path=str(manifest_path),
            )
        model_id = _nonempty_string(
            row.get("model_id"),
            code="manifest_model_id_invalid",
            label="manifest model_id",
        )
        ids.append(model_id)
    if len(ids) != len(set(ids)):
        raise SemanticMeshMaintenanceError(
            "duplicate_manifest_model_id",
            "current regression manifest contains duplicate model IDs",
            duplicates=sorted({item for item in ids if ids.count(item) > 1}),
        )
    return set(ids), raw


def _validate_mesh(payload: Mapping[str, Any], *, manifest_ids: set[str], label: str) -> None:
    if not isinstance(payload, Mapping):
        raise SemanticMeshMaintenanceError("mesh_not_object", f"{label} mesh must be an object")
    unknown = sorted(set(payload) - TOP_LEVEL_FIELDS)
    missing = sorted(TOP_LEVEL_FIELDS - set(payload))
    if missing or unknown:
        raise SemanticMeshMaintenanceError(
            "mesh_top_level_schema_invalid",
            f"{label} mesh top-level schema is not current",
            missing=missing,
            unknown=unknown,
        )
    if payload.get("schema_version") != SEMANTIC_MESH_SCHEMA:
        raise SemanticMeshMaintenanceError(
            "mesh_schema_not_current",
            f"{label} mesh schema is not current",
            expected=SEMANTIC_MESH_SCHEMA,
            actual=payload.get("schema_version"),
        )
    if payload.get("current_manifest_path") != MANIFEST_RELATIVE_PATH.as_posix():
        raise SemanticMeshMaintenanceError(
            "manifest_path_not_canonical",
            f"{label} mesh does not point at the canonical current regression manifest",
            actual=payload.get("current_manifest_path"),
        )

    raw_models = payload.get("models")
    if not isinstance(raw_models, list) or not raw_models:
        raise SemanticMeshMaintenanceError(
            "models_missing",
            f"{label} mesh requires a non-empty models array",
        )
    model_ids: list[str] = []
    for row in raw_models:
        if not isinstance(row, Mapping):
            raise SemanticMeshMaintenanceError(
                "model_row_invalid",
                f"{label} mesh model rows must be objects",
            )
        model_ids.append(
            _nonempty_string(
                row.get("model_id"),
                code="model_id_missing",
                label=f"{label} model_id",
            )
        )
    duplicates = sorted({item for item in model_ids if model_ids.count(item) > 1})
    if duplicates:
        raise SemanticMeshMaintenanceError(
            "duplicate_model_id",
            f"{label} mesh contains duplicate model IDs",
            duplicates=duplicates,
        )
    declared_ids = set(model_ids)
    missing_models = sorted(manifest_ids - declared_ids)
    foreign_models = sorted(declared_ids - manifest_ids)
    if missing_models:
        raise SemanticMeshMaintenanceError(
            "missing_model_ids",
            f"{label} mesh is missing current manifest model IDs",
            missing=missing_models,
        )
    if foreign_models:
        raise SemanticMeshMaintenanceError(
            "foreign_model_ids",
            f"{label} mesh declares model IDs outside the current manifest",
            foreign=foreign_models,
        )
    declared_count = payload.get("declared_model_count")
    if isinstance(declared_count, bool) or not isinstance(declared_count, int):
        raise SemanticMeshMaintenanceError(
            "declared_model_count_invalid",
            f"{label} declared_model_count must be an integer",
        )
    if declared_count != len(manifest_ids):
        raise SemanticMeshMaintenanceError(
            "declared_model_count_mismatch",
            f"{label} declared_model_count does not equal the current manifest",
            declared=declared_count,
            expected=len(manifest_ids),
        )

    allowed_dispositions = _string_list(
        payload.get("allowed_dispositions"),
        code="allowed_dispositions_invalid",
        label=f"{label} allowed_dispositions",
        nonempty=True,
    )
    parent_rows = payload.get("semantic_parents")
    if not isinstance(parent_rows, list) or not parent_rows:
        raise SemanticMeshMaintenanceError(
            "semantic_parents_missing",
            f"{label} mesh requires semantic parents",
        )
    parent_ids: list[str] = []
    for row in parent_rows:
        if not isinstance(row, Mapping) or set(row) != {"parent_id", "purpose"}:
            raise SemanticMeshMaintenanceError(
                "parent_schema_invalid",
                f"{label} semantic parent schema is not current",
            )
        parent_id = _nonempty_string(
            row.get("parent_id"),
            code="parent_id_missing",
            label=f"{label} parent_id",
        )
        purpose = _nonempty_string(
            row.get("purpose"),
            code="parent_purpose_missing",
            label=f"{label} purpose",
        )
        if len(purpose) < 24:
            raise SemanticMeshMaintenanceError(
                "parent_purpose_too_short",
                f"{label} semantic parent purpose must explain its boundary",
                parent_id=parent_id,
            )
        parent_ids.append(parent_id)
    duplicate_parents = sorted({item for item in parent_ids if parent_ids.count(item) > 1})
    if duplicate_parents:
        raise SemanticMeshMaintenanceError(
            "duplicate_parent_id",
            f"{label} semantic parents contain duplicate IDs",
            duplicates=duplicate_parents,
        )
    parent_id_set = set(parent_ids)

    row_by_id: dict[str, Mapping[str, Any]] = {}
    for raw_row in raw_models:
        assert isinstance(raw_row, Mapping)
        model_id = str(raw_row["model_id"]).strip()
        if set(raw_row) - MODEL_ALLOWED_FIELDS or not MODEL_REQUIRED_FIELDS.issubset(raw_row):
            raise SemanticMeshMaintenanceError(
                "model_schema_invalid",
                f"{label} model row schema is not current: {model_id}",
                model_id=model_id,
            )
        disposition = _nonempty_string(
            raw_row.get("disposition"),
            code="model_disposition_missing",
            label=f"{label} disposition for {model_id}",
        )
        if disposition not in allowed_dispositions:
            raise SemanticMeshMaintenanceError(
                "model_disposition_foreign",
                f"{label} model disposition is not declared in allowed_dispositions: {model_id}",
                model_id=model_id,
                disposition=disposition,
            )
        _nonempty_string(
            raw_row.get("rationale"),
            code="model_rationale_missing",
            label=f"{label} rationale for {model_id}",
        )
        structural_parent = _nonempty_string(
            raw_row.get("structural_parent_id"),
            code="structural_parent_missing",
            label=f"{label} structural_parent_id for {model_id}",
        )
        if structural_parent not in parent_id_set:
            raise SemanticMeshMaintenanceError(
                "foreign_structural_parent",
                f"{label} model points at an undeclared structural parent: {model_id}",
                model_id=model_id,
                parent_id=structural_parent,
            )
        cross = _string_list(
            raw_row.get("cross_boundary_parent_ids"),
            code="cross_boundary_parent_invalid",
            label=f"{label} cross_boundary_parent_ids for {model_id}",
        )
        if structural_parent in cross:
            raise SemanticMeshMaintenanceError(
                "cross_boundary_parent_duplicates_structural",
                f"{label} cross-boundary parents repeat the structural parent: {model_id}",
                model_id=model_id,
            )
        foreign_cross = sorted(set(cross) - parent_id_set)
        if foreign_cross:
            raise SemanticMeshMaintenanceError(
                "foreign_cross_boundary_parent",
                f"{label} cross-boundary parents contain foreign IDs: {model_id}",
                model_id=model_id,
                foreign=foreign_cross,
            )
        consumers = _string_list(
            raw_row.get("consumer_ids"),
            code="consumer_ids_invalid",
            label=f"{label} consumer_ids for {model_id}",
            nonempty=True,
        )
        foreign_consumers = sorted(
            {
                consumer.removeprefix("model:")
                for consumer in consumers
                if consumer.startswith("model:")
                and consumer.removeprefix("model:") not in manifest_ids
            }
        )
        if foreign_consumers:
            raise SemanticMeshMaintenanceError(
                "foreign_consumer_id",
                f"{label} consumers contain foreign model IDs: {model_id}",
                model_id=model_id,
                foreign=foreign_consumers,
            )
        row_by_id[model_id] = raw_row

    feedback_rows = payload.get("feedback_progress_contracts")
    if not isinstance(feedback_rows, list) or not feedback_rows:
        raise SemanticMeshMaintenanceError(
            "feedback_contracts_missing",
            f"{label} mesh requires feedback progress contracts",
        )
    if len(feedback_rows) != len(manifest_ids):
        raise SemanticMeshMaintenanceError(
            "feedback_contract_count_mismatch",
            f"{label} mesh must carry exactly one structural progress contract per model",
            actual=len(feedback_rows),
            expected=len(manifest_ids),
        )

    # FlowGuard's self-blueprint relation set includes parent, claim, child,
    # cross-boundary, and model-consumer relations.  Feedback declarations are
    # required for each structural child relation in the current mesh; every
    # declared relation still has to be in that complete known set.
    topology_root_id = "topology-root:flowguard-self"
    known_relation_ids: set[str] = {
        f"topology:{parent_id}:{topology_root_id}" for parent_id in parent_id_set
    }
    structural_relation_ids: set[str] = set()
    external_consumers = {
        consumer
        for row in row_by_id.values()
        for consumer in _string_list(
            row.get("consumer_ids"),
            code="consumer_ids_invalid",
            label="consumer_ids",
        )
        if consumer.startswith("claim:")
    }
    known_relation_ids.update(
        f"topology:{consumer}:{topology_root_id}" for consumer in external_consumers
    )
    for model_id, row in row_by_id.items():
        structural_parent = str(row["structural_parent_id"])
        structural_relation_id = f"topology:{model_id}:{structural_parent}"
        structural_relation_ids.add(structural_relation_id)
        known_relation_ids.add(structural_relation_id)
        for parent_id in _string_list(
            row["cross_boundary_parent_ids"],
            code="cross_boundary_parent_invalid",
            label="cross_boundary_parent_ids",
        ):
            known_relation_ids.add(f"topology:{model_id}:{parent_id}")
        for consumer in _string_list(
            row["consumer_ids"],
            code="consumer_ids_invalid",
            label="consumer_ids",
        ):
            target = (
                "model-obligation:" + consumer.removeprefix("model:")
                if consumer.startswith("model:")
                else consumer
            )
            known_relation_ids.add(f"topology:{model_id}:{target}")

    relation_ids: list[str] = []
    contract_ids: list[str] = []
    observed_structural_relation_ids: set[str] = set()
    for row in feedback_rows:
        if not isinstance(row, Mapping) or set(row) != FEEDBACK_FIELDS:
            raise SemanticMeshMaintenanceError(
                "feedback_schema_invalid",
                f"{label} feedback progress contract schema is not current",
            )
        relation_id = _nonempty_string(
            row.get("relation_id"),
            code="feedback_relation_missing",
            label=f"{label} feedback relation_id",
        )
        contract_id = _nonempty_string(
            row.get("contract_id"),
            code="feedback_contract_missing",
            label=f"{label} feedback contract_id",
        )
        _nonempty_string(
            row.get("contract_kind"),
            code="feedback_kind_missing",
            label=f"{label} feedback contract_kind",
        )
        source_kind = _nonempty_string(
            row.get("evidence_source_kind"),
            code="feedback_source_missing",
            label=f"{label} feedback evidence_source_kind",
        )
        _nonempty_string(
            row.get("rationale"),
            code="feedback_rationale_missing",
            label=f"{label} feedback rationale",
        )
        evidence_ids = _string_list(
            row.get("evidence_model_ids"),
            code="feedback_evidence_invalid",
            label=f"{label} evidence_model_ids for {relation_id}",
        )
        if relation_id not in known_relation_ids:
            raise SemanticMeshMaintenanceError(
                "foreign_feedback_relation",
                f"{label} feedback relation is not declared by the topology: {relation_id}",
                relation_id=relation_id,
            )
        foreign_evidence = sorted(set(evidence_ids) - manifest_ids)
        if foreign_evidence:
            raise SemanticMeshMaintenanceError(
                "foreign_feedback_evidence_model",
                f"{label} feedback evidence names foreign model IDs: {relation_id}",
                relation_id=relation_id,
                foreign=foreign_evidence,
            )
        if source_kind == "accepted_model_authority_activation" and evidence_ids:
            raise SemanticMeshMaintenanceError(
                "authority_feedback_borrows_child_evidence",
                f"{label} authority activation feedback cannot borrow child model receipts",
                relation_id=relation_id,
            )
        if source_kind == "current_child_model_receipts" and not evidence_ids:
            raise SemanticMeshMaintenanceError(
                "child_feedback_evidence_missing",
                f"{label} child receipt feedback requires evidence_model_ids",
                relation_id=relation_id,
            )
        relation_ids.append(relation_id)
        contract_ids.append(contract_id)
        if relation_id in structural_relation_ids:
            observed_structural_relation_ids.add(relation_id)

    duplicate_relations = sorted({item for item in relation_ids if relation_ids.count(item) > 1})
    if duplicate_relations:
        raise SemanticMeshMaintenanceError(
            "duplicate_feedback_relation",
            f"{label} feedback relations contain duplicates",
            duplicates=duplicate_relations,
        )
    duplicate_contracts = sorted({item for item in contract_ids if contract_ids.count(item) > 1})
    if duplicate_contracts:
        raise SemanticMeshMaintenanceError(
            "duplicate_feedback_contract",
            f"{label} feedback contract IDs contain duplicates",
            duplicates=duplicate_contracts,
        )
    missing_structural = sorted(structural_relation_ids - observed_structural_relation_ids)
    if missing_structural:
        raise SemanticMeshMaintenanceError(
            "missing_feedback_relation",
            f"{label} feedback contracts omit structural model relations",
            missing=missing_structural,
        )

    derivation_fingerprint = payload.get("derivation_base_snapshot_fingerprint")
    if not isinstance(derivation_fingerprint, str) or not derivation_fingerprint.strip():
        raise SemanticMeshMaintenanceError(
            "derivation_fingerprint_missing",
            f"{label} derivation base snapshot fingerprint is empty",
        )
    for field in ("mesh_id", "claim_scope", "currentness_owner", "claim_boundary"):
        _nonempty_string(payload.get(field), code="mesh_identity_missing", label=f"{label} {field}")


def _find_function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            if isinstance(node, ast.AsyncFunctionDef):
                raise SemanticMeshMaintenanceError(
                    "flowguard_helper_invalid",
                    f"FlowGuard helper is unexpectedly async: {name}",
                )
            return node
    raise SemanticMeshMaintenanceError(
        "flowguard_helper_missing",
        f"FlowGuard source does not define required private helper: {name}",
    )


def _source_candidates(explicit: str | Path | None) -> list[Path]:
    candidates: list[Path] = []
    if explicit is not None:
        supplied = Path(explicit)
        candidates.append(
            supplied / "flowguard" / "self_blueprint.py"
            if supplied.is_dir()
            else supplied
        )
    for env_name in ("FLOWGUARD_SELF_BLUEPRINT_PATH", "FLOWGUARD_SOURCE_ROOT"):
        env_value = os.environ.get(env_name)
        if env_value:
            supplied = Path(env_value)
            candidates.append(
                supplied / "flowguard" / "self_blueprint.py"
                if supplied.is_dir()
                else supplied
            )
    # Editable installs are common in this workspace.  Read their finder
    # metadata instead of importing flowguard.__init__, whose broad exports can
    # execute unrelated project setup during a small maintenance operation.
    for entry in list(sys.path):
        if not entry or not Path(entry).is_dir():
            continue
        for finder in Path(entry).glob("__editable___flowguard_*_finder.py"):
            try:
                text = finder.read_text(encoding="utf-8")
            except OSError:
                continue
            match = re.search(r"['\"]flowguard['\"]\s*:\s*['\"]([^'\"]+)", text)
            if match:
                candidates.append(Path(match.group(1)) / "self_blueprint.py")
    for entry in list(sys.path):
        if entry:
            candidates.append(Path(entry) / "flowguard" / "self_blueprint.py")
    result: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        key = os.path.normcase(str(resolved))
        if key not in seen and resolved.is_file():
            seen.add(key)
            result.append(resolved)
    return result


def _load_private_flowguard_helper(
    explicit_source: str | Path | None,
) -> tuple[Any, dict[str, Any], dict[Path, bytes]]:
    candidates = _source_candidates(explicit_source)
    if not candidates:
        raise SemanticMeshMaintenanceError(
            "flowguard_source_unavailable",
            "the FlowGuard self_blueprint.py source is unavailable; refuse a non-official relation hash",
            requested=str(explicit_source) if explicit_source is not None else None,
        )
    relation_path = candidates[0]
    relation_raw = _read_bytes(relation_path, missing_code="flowguard_source_missing")
    try:
        relation_tree = ast.parse(relation_raw.decode("utf-8"), filename=str(relation_path))
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise SemanticMeshMaintenanceError(
            "flowguard_source_invalid",
            f"FlowGuard self_blueprint.py cannot be parsed: {relation_path}",
        ) from exc
    relation_node = _find_function(relation_tree, "_semantic_relation_fingerprint")

    receipt_path = relation_path.with_name("evidence_receipts.py")
    receipt_raw = _read_bytes(receipt_path, missing_code="flowguard_canonicalizer_missing")
    try:
        receipt_tree = ast.parse(receipt_raw.decode("utf-8"), filename=str(receipt_path))
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise SemanticMeshMaintenanceError(
            "flowguard_canonicalizer_invalid",
            f"FlowGuard evidence_receipts.py cannot be parsed: {receipt_path}",
        ) from exc
    sha_node = _find_function(receipt_tree, "_sha256")
    canonical_node = _find_function(receipt_tree, "_canonical_json")
    fingerprint_node = _find_function(receipt_tree, "fingerprint_value")

    namespace: dict[str, Any] = {
        "__builtins__": __builtins__,
        "hashlib": hashlib,
        "json": json,
        "Any": Any,
        "Mapping": Mapping,
    }
    module = ast.Module(
        body=[
            ast.ImportFrom(
                module="__future__",
                names=[ast.alias(name="annotations", asname=None)],
                level=0,
            ),
            sha_node,
            canonical_node,
            fingerprint_node,
            relation_node,
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(module)
    try:
        exec(compile(module, str(relation_path), "exec"), namespace, namespace)
    except Exception as exc:  # pragma: no cover - source failure is environment-specific
        raise SemanticMeshMaintenanceError(
            "flowguard_helper_load_failed",
            "could not load the private FlowGuard relation helper from source",
            path=str(relation_path),
            reason=str(exc),
        ) from exc
    helper = namespace.get("_semantic_relation_fingerprint")
    if not callable(helper):
        raise SemanticMeshMaintenanceError(
            "flowguard_helper_invalid",
            "loaded FlowGuard private relation helper is not callable",
            path=str(relation_path),
        )
    source_bytes = {relation_path: relation_raw, receipt_path: receipt_raw}
    provenance = {
        "api_status": "private_non_public",
        "relation_helper": "flowguard.self_blueprint._semantic_relation_fingerprint",
        "relation_helper_source": relation_path.name,
        "relation_helper_source_fingerprint": _file_fingerprint(relation_raw),
        "canonicalizer_source": receipt_path.name,
        "canonicalizer_source_fingerprint": _file_fingerprint(receipt_raw),
        "loading_method": "source_ast_without_flowguard_package_import",
        "public_flowguard_writer_available": False,
    }
    return helper, provenance, source_bytes


def _assert_flowguard_sources_unchanged(source_bytes: Mapping[Path, bytes]) -> None:
    for path, before in source_bytes.items():
        current = _read_bytes(path, missing_code="flowguard_source_drift_detected")
        if current != before:
            raise SemanticMeshMaintenanceError(
                "flowguard_source_drift_detected",
                "FlowGuard source changed while the maintenance transaction was preparing",
                path=str(path),
                before_fingerprint=_file_fingerprint(before),
                after_fingerprint=_file_fingerprint(current),
            )


@contextlib.contextmanager
def _path_lock(path: Path) -> Iterator[None]:
    """Acquire a non-blocking per-output lock without touching the mesh body."""

    # A lock is runtime coordination state, not a source surface.  Keeping it
    # beside the canonical mesh would make ResearchGuard's provider-neutral
    # denominator discover ``*.maintenance.lock`` as an unknown adapter after
    # every successful write.  Put FlowGuard-owned locks under the excluded
    # evidence tree while retaining a stable, path-specific identity.  Outputs
    # outside ``.flowguard`` keep the local sibling lock for callers that use
    # this utility with a temporary non-source directory.
    resolved = path.resolve()
    flowguard_root: Path | None = None
    for index, part in enumerate(resolved.parts):
        if part.casefold() == ".flowguard":
            flowguard_root = Path(*resolved.parts[: index + 1])
            break
    if flowguard_root is not None:
        lock_id = hashlib.sha256(str(resolved).casefold().encode("utf-8")).hexdigest()
        lock_path = flowguard_root / "evidence" / "maintenance-locks" / f"{lock_id}.lock"
    else:
        lock_path = resolved.with_name(resolved.name + ".maintenance.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    try:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise SemanticMeshMaintenanceError(
                    "maintenance_lock_busy",
                    f"maintenance lock is already held: {lock_path}",
                    lock_path=str(lock_path),
                ) from exc
        else:  # pragma: no cover - exercised on POSIX CI only
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise SemanticMeshMaintenanceError(
                    "maintenance_lock_busy",
                    f"maintenance lock is already held: {lock_path}",
                    lock_path=str(lock_path),
                ) from exc
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:  # pragma: no cover - exercised on POSIX CI only
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


@contextlib.contextmanager
def _path_locks(paths: list[Path]) -> Iterator[None]:
    ordered: list[Path] = []
    seen: set[str] = set()
    for path in sorted(paths, key=lambda item: os.path.normcase(str(item.resolve()))):
        key = os.path.normcase(str(path.resolve()))
        if key not in seen:
            seen.add(key)
            ordered.append(path)

    def acquire(index: int) -> Iterator[None]:
        if index >= len(ordered):
            return contextlib.nullcontext()
        return _path_lock(ordered[index])

    with contextlib.ExitStack() as stack:
        for path in ordered:
            stack.enter_context(_path_lock(path))
        yield


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    try:
        return (
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SemanticMeshMaintenanceError(
            "json_serialization_failed",
            "output payload is not JSON serializable",
            reason=str(exc),
        ) from exc


def _atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise SemanticMeshMaintenanceError(
            "atomic_write_failed",
            f"atomic write failed: {path}",
            path=str(path),
            reason=str(exc),
        ) from exc
    finally:
        if temporary is not None:
            with contextlib.suppress(OSError):
                temporary.unlink()


def _changed_fields(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    return sorted(field for field in TOP_LEVEL_FIELDS if before.get(field) != after.get(field))


def _default_output_path(mesh_path: Path) -> Path:
    return mesh_path.with_name(mesh_path.stem + ".maintained.json")


def _default_receipt_path(output_path: Path) -> Path:
    return output_path.with_name(output_path.stem + ".maintenance-receipt.json")


def maintain_semantic_mesh(
    root: str | Path,
    *,
    mesh: str | Path | None = None,
    candidate_mesh: str | Path | None = None,
    output_mesh: str | Path | None = None,
    receipt: str | Path | None = None,
    expected_old_fingerprint: str | None = None,
    flowguard_source: str | Path | None = None,
    write: bool = False,
) -> dict[str, Any]:
    """Validate and optionally maintain one semantic mesh.

    ``write=False`` is a pure check.  ``write=True`` requires the caller to
    supply the exact raw-byte fingerprint of the mesh that was read, and emits
    the maintained output plus a receipt atomically.  The source candidate is
    never edited in place unless ``output_mesh`` explicitly equals ``mesh``.
    """

    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        raise SemanticMeshMaintenanceError(
            "root_missing",
            f"repository root is not a directory: {root_path}",
            root=str(root_path),
        )
    mesh_path = _resolve_inside(root_path, mesh, SEMANTIC_MESH_RELATIVE_PATH)
    candidate_path = (
        _resolve_inside(root_path, candidate_mesh, SEMANTIC_MESH_RELATIVE_PATH)
        if candidate_mesh is not None
        else None
    )
    if output_mesh is not None:
        output_path = _resolve_inside(root_path, output_mesh, _default_output_path(mesh_path))
    else:
        output_path = _default_output_path(mesh_path)
    if receipt is not None:
        receipt_path = _resolve_inside(root_path, receipt, _default_receipt_path(output_path))
    else:
        receipt_path = _default_receipt_path(output_path)
    if output_path == receipt_path:
        raise SemanticMeshMaintenanceError(
            "path_collision",
            "output mesh and receipt must be different paths",
            path=str(output_path),
        )

    mesh_raw = _read_bytes(mesh_path, missing_code="mesh_missing")
    mesh_payload = _load_json_object(mesh_raw, path=mesh_path)
    manifest_path = root_path / MANIFEST_RELATIVE_PATH
    manifest_ids, manifest_raw = _load_manifest_model_ids(root_path, manifest_path)
    _validate_mesh(mesh_payload, manifest_ids=manifest_ids, label="current")

    if candidate_path is None:
        candidate_raw = mesh_raw
        candidate_payload = copy.deepcopy(mesh_payload)
    else:
        candidate_raw = _read_bytes(candidate_path, missing_code="candidate_missing")
        candidate_payload = _load_json_object(candidate_raw, path=candidate_path)
        _validate_mesh(candidate_payload, manifest_ids=manifest_ids, label="candidate")
        status_changes = sorted(
            field for field in STATUS_FIELDS if mesh_payload.get(field) != candidate_payload.get(field)
        )
        if status_changes:
            raise SemanticMeshMaintenanceError(
                "status_mutation_not_allowed",
                "maintenance cannot change semantic status or completion claim",
                fields=status_changes,
            )
        immutable_changes = sorted(
            field
            for field in TOP_LEVEL_FIELDS - TOPOLOGY_MUTABLE_FIELDS
            if mesh_payload.get(field) != candidate_payload.get(field)
        )
        if immutable_changes:
            raise SemanticMeshMaintenanceError(
                "immutable_mesh_fields_changed",
                "candidate may change topology contracts only; authority and identity fields must stay byte-for-value equivalent",
                fields=immutable_changes,
            )

    helper, helper_provenance, flowguard_source_bytes = _load_private_flowguard_helper(
        flowguard_source
    )
    try:
        recomputed_relation_fingerprint = str(helper(candidate_payload))
    except Exception as exc:  # pragma: no cover - FlowGuard source-specific failure
        raise SemanticMeshMaintenanceError(
            "relation_fingerprint_failed",
            "FlowGuard private relation helper failed for the validated candidate",
            reason=str(exc),
        ) from exc
    if not recomputed_relation_fingerprint.startswith("sha256:"):
        raise SemanticMeshMaintenanceError(
            "relation_fingerprint_invalid",
            "FlowGuard private relation helper did not return a sha256 fingerprint",
            value=recomputed_relation_fingerprint,
        )

    candidate_relation_fingerprint = str(candidate_payload.get("semantic_relation_fingerprint", ""))
    candidate_matches = candidate_relation_fingerprint == recomputed_relation_fingerprint
    report: dict[str, Any] = {
        "ok": candidate_matches,
        "mode": "write" if write else "check",
        "mesh_path": _relative_path(root_path, mesh_path),
        "candidate_path": _relative_path(root_path, candidate_path) if candidate_path else None,
        "current_mesh_fingerprint": _file_fingerprint(mesh_raw),
        "candidate_input_fingerprint": _file_fingerprint(candidate_raw),
        "expected_old_fingerprint": expected_old_fingerprint,
        "stored_relation_fingerprint": candidate_relation_fingerprint,
        "recomputed_relation_fingerprint": recomputed_relation_fingerprint,
        "relation_fingerprint_matches": candidate_matches,
        "flowguard_relation_hash_provenance": helper_provenance,
        "semantic_model_status": mesh_payload.get("semantic_model_status"),
        "whole_system_completion_claim": mesh_payload.get("whole_system_completion_claim"),
    }
    if expected_old_fingerprint is not None and expected_old_fingerprint != report["current_mesh_fingerprint"]:
        report["ok"] = False
        report["error"] = SemanticMeshMaintenanceError(
            "expected_old_fingerprint_mismatch",
            "expected_old_fingerprint does not match the current mesh bytes",
            expected=expected_old_fingerprint,
            actual=report["current_mesh_fingerprint"],
        ).as_dict()
        return report
    if not candidate_matches and not write:
        report["error"] = SemanticMeshMaintenanceError(
            "relation_fingerprint_mismatch",
            "candidate semantic_relation_fingerprint does not match FlowGuard's private helper",
            expected=recomputed_relation_fingerprint,
            actual=candidate_relation_fingerprint,
        ).as_dict()
        return report
    if not write:
        report["output_path"] = None
        report["receipt_path"] = None
        return report
    if not expected_old_fingerprint:
        raise SemanticMeshMaintenanceError(
            "expected_old_fingerprint_required",
            "--write requires the exact current raw-byte fingerprint via --expected-old-fingerprint",
        )

    output_payload = copy.deepcopy(candidate_payload)
    output_payload["semantic_relation_fingerprint"] = recomputed_relation_fingerprint
    if output_payload.get("semantic_model_status") != mesh_payload.get("semantic_model_status"):
        raise SemanticMeshMaintenanceError(
            "status_mutation_not_allowed",
            "maintenance cannot change semantic status",
            fields=["semantic_model_status"],
        )
    if output_payload.get("whole_system_completion_claim") != mesh_payload.get(
        "whole_system_completion_claim"
    ):
        raise SemanticMeshMaintenanceError(
            "status_mutation_not_allowed",
            "maintenance cannot change whole-system completion claim",
            fields=["whole_system_completion_claim"],
        )
    _validate_mesh(output_payload, manifest_ids=manifest_ids, label="output")
    output_raw = _json_bytes(output_payload)
    changed_fields = _changed_fields(mesh_payload, output_payload)
    if any(field not in TOPOLOGY_MUTABLE_FIELDS for field in changed_fields):
        raise SemanticMeshMaintenanceError(
            "unexpected_output_change",
            "output changes exceed the governed topology maintenance surface",
            fields=changed_fields,
        )

    lock_paths = [mesh_path, output_path, receipt_path]
    if candidate_path is not None:
        lock_paths.append(candidate_path)
    with _path_locks(lock_paths):
        current_again = _read_bytes(mesh_path, missing_code="source_drift_detected")
        if current_again != mesh_raw:
            raise SemanticMeshMaintenanceError(
                "source_drift_detected",
                "current mesh changed after validation and before the maintenance write",
                before_fingerprint=_file_fingerprint(mesh_raw),
                after_fingerprint=_file_fingerprint(current_again),
            )
        if candidate_path is not None and candidate_path != mesh_path:
            candidate_again = _read_bytes(candidate_path, missing_code="source_drift_detected")
            if candidate_again != candidate_raw:
                raise SemanticMeshMaintenanceError(
                    "source_drift_detected",
                    "candidate mesh changed after validation and before the maintenance write",
                    path=str(candidate_path),
                    before_fingerprint=_file_fingerprint(candidate_raw),
                    after_fingerprint=_file_fingerprint(candidate_again),
                )
        _assert_flowguard_sources_unchanged(flowguard_source_bytes)

        prior_output_raw: bytes | None = None
        output_existed = output_path.is_file()
        if output_existed:
            prior_output_raw = _read_bytes(output_path)
        try:
            _atomic_write(output_path, output_raw)
            if output_path == mesh_path:
                current_after = _read_bytes(mesh_path, missing_code="source_drift_detected")
            else:
                current_after = _read_bytes(mesh_path, missing_code="source_drift_detected")
                if current_after != mesh_raw:
                    raise SemanticMeshMaintenanceError(
                        "source_drift_detected",
                        "current mesh changed during the maintenance write",
                        before_fingerprint=_file_fingerprint(mesh_raw),
                        after_fingerprint=_file_fingerprint(current_after),
                    )
            _assert_flowguard_sources_unchanged(flowguard_source_bytes)
            receipt_core: dict[str, Any] = {
                "schema_version": RECEIPT_SCHEMA,
                "operation": "semantic_mesh_relation_fingerprint_maintenance",
                "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "mesh_path": _relative_path(root_path, mesh_path),
                "candidate_path": _relative_path(root_path, candidate_path)
                if candidate_path
                else None,
                "output_path": _relative_path(root_path, output_path),
                "receipt_path": _relative_path(root_path, receipt_path),
                "before_mesh_fingerprint": _file_fingerprint(mesh_raw),
                "after_output_fingerprint": _file_fingerprint(output_raw),
                "after_current_mesh_fingerprint": _file_fingerprint(current_after),
                "candidate_input_fingerprint": _file_fingerprint(candidate_raw),
                "expected_old_fingerprint": expected_old_fingerprint,
                "before_semantic_relation_fingerprint": mesh_payload.get(
                    "semantic_relation_fingerprint"
                ),
                "after_semantic_relation_fingerprint": recomputed_relation_fingerprint,
                "changed_fields": changed_fields,
                "semantic_model_status": mesh_payload.get("semantic_model_status"),
                "whole_system_completion_claim": mesh_payload.get(
                    "whole_system_completion_claim"
                ),
                "flowguard_relation_hash_provenance": helper_provenance,
                "manifest_fingerprint": _file_fingerprint(manifest_raw),
                "status_transition": None,
                "write_atomic": True,
            }
            receipt_payload = {
                **receipt_core,
                "receipt_fingerprint": _local_fingerprint_value(receipt_core),
            }
            _atomic_write(receipt_path, _json_bytes(receipt_payload))
        except Exception:
            # If receipt creation fails, restore the prior output so a caller
            # never mistakes a mesh without its matching receipt for a commit.
            try:
                if output_existed and prior_output_raw is not None:
                    _atomic_write(output_path, prior_output_raw)
                elif output_path.exists():
                    output_path.unlink()
            except OSError as rollback_exc:
                raise SemanticMeshMaintenanceError(
                    "rollback_failed",
                    "maintenance failed and restoring the prior output also failed",
                    output_path=str(output_path),
                    reason=str(rollback_exc),
                ) from rollback_exc
            raise

    final_output_raw = _read_bytes(output_path, missing_code="output_missing")
    final_receipt_raw = _read_bytes(receipt_path, missing_code="receipt_missing")
    report.update(
        {
            "ok": True,
            "candidate_matches_after_recompute": True,
            "output_path": _relative_path(root_path, output_path),
            "receipt_path": _relative_path(root_path, receipt_path),
            "output_mesh_fingerprint": _file_fingerprint(final_output_raw),
            "receipt_fingerprint": _file_fingerprint(final_receipt_raw),
            "changed_fields": changed_fields,
            "status_transition": None,
        }
    )
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and explicitly maintain a ResearchGuard semantic model mesh."
    )
    parser.add_argument("--root", default=".", help="ResearchGuard repository root")
    parser.add_argument("--mesh", help="current mesh path, relative to --root by default")
    parser.add_argument("--candidate-mesh", help="optional draft mesh to validate and maintain")
    parser.add_argument("--output-mesh", help="output mesh path; defaults to *.maintained.json")
    parser.add_argument("--receipt", help="before/after receipt path")
    parser.add_argument(
        "--expected-old-fingerprint",
        help="raw-byte sha256 of the current mesh; required with --write",
    )
    parser.add_argument(
        "--flowguard-source",
        help="FlowGuard source root or flowguard/self_blueprint.py path",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the maintained mesh and receipt atomically (otherwise check only)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        result = maintain_semantic_mesh(
            args.root,
            mesh=args.mesh,
            candidate_mesh=args.candidate_mesh,
            output_mesh=args.output_mesh,
            receipt=args.receipt,
            expected_old_fingerprint=args.expected_old_fingerprint,
            flowguard_source=args.flowguard_source,
            write=args.write,
        )
    except SemanticMeshMaintenanceError as exc:
        print(json.dumps({"ok": False, "error": exc.as_dict()}, ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":  # pragma: no cover - exercised by CLI smoke tests
    raise SystemExit(main())
