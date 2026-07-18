"""Strict, content-addressed LogicGuard template-pack catalog loader."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Iterable, Mapping

from .canonical import canonical_json, canonical_sha256
from .models import (
    Finding,
    NativeBinding,
    Selector,
    TemplateCatalog,
    TemplateProfile,
    ValidatorBinding,
)
from .native_validators import (
    allowed_binding,
    callable_fingerprint,
    resolve_callable,
)


MANIFEST_SCHEMA = "researchguard.logic.template-pack-manifest.v1"
PROFILE_SCHEMA = "researchguard.logic.template-pack-profile.v1"
REQUIRED_FAMILIES = tuple(
    sorted(
        (
            "argument",
            "deepening",
            "execution-package",
            "purpose",
            "source-library",
            "structured-artifact",
            "synthesis",
        )
    )
)
MANIFEST_KEYS = {
    "schema",
    "catalog_id",
    "catalog_version",
    "base_profile_id",
    "required_families",
    "profiles",
    "catalog_digest",
}
MANIFEST_ENTRY_KEYS = {"profile_id", "family", "path", "sha256"}
PROFILE_KEYS = {
    "schema",
    "profile_id",
    "profile_version",
    "family",
    "is_base",
    "selector",
    "strictly_dominates",
    "composable_with",
    "emitted_fields",
    "field_owners",
    "native_binding",
    "required_instance_fields",
    "claim_boundary",
}
SELECTOR_KEYS = {"purposes", "required_capabilities", "context_tags_any"}
NATIVE_BINDING_KEYS = {
    "route_id",
    "owner_callable",
    "owner_fingerprint",
    "validators",
}
VALIDATOR_BINDING_KEYS = {
    "validator_id",
    "callable",
    "callable_fingerprint",
}
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")
FIELD_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$")


class CatalogValidationError(ValueError):
    def __init__(self, findings: Iterable[Finding]):
        self.findings = tuple(findings)
        message = "; ".join(f"{item.code}: {item.message}" for item in self.findings)
        super().__init__(message or "catalog validation failed")


class _DuplicateKeyError(ValueError):
    pass


def default_catalog_root() -> Path:
    return Path(__file__).resolve().parent / "catalog"


def load_catalog(root: str | Path | None = None) -> TemplateCatalog:
    catalog_root = Path(root) if root is not None else default_catalog_root()
    catalog_root = catalog_root.resolve()
    manifest_path = catalog_root / "manifest.json"
    if not manifest_path.is_file():
        raise CatalogValidationError(
            (Finding("manifest_missing", "catalog manifest.json does not exist"),)
        )
    manifest = _load_json_object(manifest_path, code="manifest_invalid_json")
    _require_exact_keys(manifest, MANIFEST_KEYS, "manifest")
    if manifest["schema"] != MANIFEST_SCHEMA:
        _raise("manifest_schema_unsupported", "manifest schema is not current")
    catalog_id = _required_id(manifest["catalog_id"], "catalog_id")
    catalog_version = _required_text(manifest["catalog_version"], "catalog_version")
    base_profile_id = _required_id(manifest["base_profile_id"], "base_profile_id")
    required_families = _canonical_declared_list(
        manifest["required_families"], "required_families"
    )
    if required_families != REQUIRED_FAMILIES:
        _raise(
            "required_family_inventory_mismatch",
            f"required_families must equal {list(REQUIRED_FAMILIES)}",
        )

    raw_entries = manifest["profiles"]
    if not isinstance(raw_entries, list) or not raw_entries:
        _raise("manifest_profiles_invalid", "profiles must be a non-empty list")
    entries: list[dict[str, str]] = []
    for index, raw_entry in enumerate(raw_entries):
        if not isinstance(raw_entry, dict):
            _raise("manifest_profile_entry_invalid", f"profile entry {index} is not an object")
        _require_exact_keys(raw_entry, MANIFEST_ENTRY_KEYS, f"profile entry {index}")
        entry = {
            "profile_id": _required_id(raw_entry["profile_id"], "profile_id"),
            "family": _required_id(raw_entry["family"], "family"),
            "path": _required_text(raw_entry["path"], "path"),
            "sha256": _required_sha256(raw_entry["sha256"], "sha256"),
        }
        entries.append(entry)
    if [entry["profile_id"] for entry in entries] != sorted(
        entry["profile_id"] for entry in entries
    ):
        _raise("manifest_profiles_not_canonical", "profile entries must be sorted by profile_id")
    _require_unique((entry["profile_id"] for entry in entries), "duplicate_profile_id")
    _require_unique((entry["path"] for entry in entries), "duplicate_profile_path")

    declared_paths = {entry["path"] for entry in entries}
    actual_paths = {
        path.relative_to(catalog_root).as_posix()
        for path in (catalog_root / "profiles").rglob("*.json")
        if path.is_file()
    }
    if declared_paths != actual_paths:
        missing = sorted(declared_paths - actual_paths)
        undeclared = sorted(actual_paths - declared_paths)
        _raise(
            "profile_inventory_mismatch",
            f"missing={missing}; undeclared={undeclared}",
        )

    profiles: list[TemplateProfile] = []
    for entry in entries:
        relative = PurePosixPath(entry["path"])
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            _raise("profile_path_escape", f"unsafe profile path: {entry['path']}")
        profile_path = (catalog_root / Path(*relative.parts)).resolve()
        try:
            profile_path.relative_to(catalog_root)
        except ValueError:
            _raise("profile_path_escape", f"profile escapes catalog root: {entry['path']}")
        raw_profile = _load_json_object(profile_path, code="profile_invalid_json")
        observed_digest = canonical_sha256(raw_profile)
        if observed_digest != entry["sha256"]:
            _raise(
                "stale_profile_digest",
                f"{entry['profile_id']} expected {entry['sha256']} but observed {observed_digest}",
                profile_id=entry["profile_id"],
            )
        profile = _parse_profile(raw_profile, observed_digest)
        if profile.profile_id != entry["profile_id"] or profile.family != entry["family"]:
            _raise(
                "manifest_profile_identity_mismatch",
                f"manifest identity does not match {entry['path']}",
                profile_id=entry["profile_id"],
            )
        profiles.append(profile)

    _validate_profile_set(profiles, base_profile_id)
    declared_catalog_digest = _required_sha256(
        manifest["catalog_digest"], "catalog_digest"
    )
    digest_payload = dict(manifest)
    digest_payload.pop("catalog_digest", None)
    observed_catalog_digest = canonical_sha256(digest_payload)
    if observed_catalog_digest != declared_catalog_digest:
        _raise(
            "stale_catalog_digest",
            f"expected {declared_catalog_digest} but observed {observed_catalog_digest}",
        )
    return TemplateCatalog(
        schema=MANIFEST_SCHEMA,
        catalog_id=catalog_id,
        catalog_version=catalog_version,
        base_profile_id=base_profile_id,
        required_families=required_families,
        profiles=tuple(profiles),
        catalog_digest=declared_catalog_digest,
        root=catalog_root,
    )


def catalog_digest_payload(manifest: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(manifest)
    payload.pop("catalog_digest", None)
    return payload


def _parse_profile(raw: Mapping[str, Any], content_digest: str) -> TemplateProfile:
    _require_exact_keys(raw, PROFILE_KEYS, "profile")
    if raw["schema"] != PROFILE_SCHEMA:
        _raise("profile_schema_unsupported", "profile schema is not current")
    profile_id = _required_id(raw["profile_id"], "profile_id")
    profile_version = _required_text(raw["profile_version"], "profile_version")
    family = _required_id(raw["family"], "family")
    if family not in {*REQUIRED_FAMILIES, "base"}:
        _raise("profile_family_unknown", f"unsupported profile family: {family}", profile_id)
    if not isinstance(raw["is_base"], bool):
        _raise("profile_is_base_invalid", "is_base must be boolean", profile_id)

    raw_selector = raw["selector"]
    if not isinstance(raw_selector, dict):
        _raise("selector_invalid", "selector must be an object", profile_id)
    _require_exact_keys(raw_selector, SELECTOR_KEYS, "selector", profile_id)
    selector = Selector(
        purposes=_canonical_declared_list(raw_selector["purposes"], "purposes", profile_id),
        required_capabilities=_canonical_declared_list(
            raw_selector["required_capabilities"],
            "required_capabilities",
            profile_id,
        ),
        context_tags_any=_canonical_declared_list(
            raw_selector["context_tags_any"],
            "context_tags_any",
            profile_id,
        ),
    )
    strictly_dominates = _canonical_declared_list(
        raw["strictly_dominates"], "strictly_dominates", profile_id
    )
    composable_with = _canonical_declared_list(
        raw["composable_with"], "composable_with", profile_id
    )
    if profile_id in {*strictly_dominates, *composable_with}:
        _raise("profile_self_relation", "profile cannot dominate or compose with itself", profile_id)

    emitted = raw["emitted_fields"]
    owners = raw["field_owners"]
    if not isinstance(emitted, dict) or not emitted:
        _raise("emitted_fields_invalid", "emitted_fields must be a non-empty object", profile_id)
    if not isinstance(owners, dict):
        _raise("field_owners_invalid", "field_owners must be an object", profile_id)
    emitted_rows: list[tuple[str, str]] = []
    for field_path, value in emitted.items():
        _validate_field_path(field_path, profile_id)
        _validate_template_value(value, profile_id, field_path)
        emitted_rows.append((field_path, canonical_json(value)))
    emitted_rows.sort()
    owner_rows: list[tuple[str, str]] = []
    for field_path, owner_id in owners.items():
        _validate_field_path(field_path, profile_id)
        owner_id = _required_id(owner_id, "field owner", profile_id)
        owner_rows.append((field_path, owner_id))
    owner_rows.sort()
    if {field for field, _value in emitted_rows} != {field for field, _owner in owner_rows}:
        _raise(
            "field_owner_inventory_mismatch",
            "field_owners must match emitted_fields exactly",
            profile_id,
        )
    for field_path, owner_id in owner_rows:
        if owner_id != profile_id:
            _raise(
                "field_owner_not_profile",
                f"{field_path} is owned by {owner_id}, expected {profile_id}",
                profile_id,
                field_path,
            )

    required_instance_fields = _canonical_declared_list(
        raw["required_instance_fields"], "required_instance_fields", profile_id
    )
    unknown_required = set(required_instance_fields) - {
        field for field, _value in emitted_rows
    }
    if unknown_required:
        _raise(
            "required_field_not_emitted",
            f"required fields are not emitted: {sorted(unknown_required)}",
            profile_id,
        )
    for field in required_instance_fields:
        _validate_field_path(field, profile_id)

    native_binding = _parse_native_binding(raw["native_binding"], family, profile_id)
    claim_boundary = _required_text(raw["claim_boundary"], "claim_boundary", profile_id)
    if raw["is_base"]:
        if family != "base" or any(selector.to_dict().values()):
            _raise(
                "base_profile_selector_invalid",
                "base profile must use family base and an empty selector",
                profile_id,
            )
    elif family == "base":
        _raise("non_base_profile_family_invalid", "only is_base profile may use family base", profile_id)
    return TemplateProfile(
        profile_id=profile_id,
        profile_version=profile_version,
        family=family,
        is_base=raw["is_base"],
        selector=selector,
        strictly_dominates=strictly_dominates,
        composable_with=composable_with,
        emitted_fields=tuple(emitted_rows),
        field_owners=tuple(owner_rows),
        native_binding=native_binding,
        required_instance_fields=required_instance_fields,
        claim_boundary=claim_boundary,
        content_digest=content_digest,
    )


def _parse_native_binding(raw: Any, family: str, profile_id: str) -> NativeBinding:
    if not isinstance(raw, dict):
        _raise("native_binding_invalid", "native_binding must be an object", profile_id)
    _require_exact_keys(raw, NATIVE_BINDING_KEYS, "native_binding", profile_id)
    route_id = _required_text(raw["route_id"], "route_id", profile_id)
    owner_callable = _required_text(raw["owner_callable"], "owner_callable", profile_id)
    owner_fingerprint = _required_sha256(
        raw["owner_fingerprint"], "owner_fingerprint", profile_id
    )
    try:
        allowed = allowed_binding(family)
    except KeyError as exc:
        _raise("native_family_unregistered", str(exc), profile_id)
    if route_id != allowed["route_id"] or owner_callable != allowed["owner_callable"]:
        _raise(
            "unknown_native_binding",
            f"route/owner binding is not current for family {family}",
            profile_id,
        )
    try:
        owner = resolve_callable(owner_callable)
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        _raise("native_owner_unavailable", str(exc), profile_id)
    observed_owner_fingerprint = callable_fingerprint(owner)
    if owner_fingerprint != observed_owner_fingerprint:
        _raise(
            "stale_native_owner_binding",
            f"{owner_callable} fingerprint changed",
            profile_id,
        )

    raw_validators = raw["validators"]
    if not isinstance(raw_validators, list) or not raw_validators:
        _raise("native_validators_invalid", "validators must be a non-empty list", profile_id)
    validator_rows: list[ValidatorBinding] = []
    for index, item in enumerate(raw_validators):
        if not isinstance(item, dict):
            _raise("native_validator_invalid", f"validator {index} is not an object", profile_id)
        _require_exact_keys(item, VALIDATOR_BINDING_KEYS, "native validator", profile_id)
        validator_id = _required_text(item["validator_id"], "validator_id", profile_id)
        callable_ref = _required_text(item["callable"], "callable", profile_id)
        declared_fingerprint = _required_sha256(
            item["callable_fingerprint"], "callable_fingerprint", profile_id
        )
        expected_ref = allowed["validators"].get(validator_id)
        if expected_ref != callable_ref:
            _raise(
                "unknown_native_validator",
                f"{validator_id} is not the current validator for family {family}",
                profile_id,
            )
        try:
            validator = resolve_callable(callable_ref)
        except (ImportError, AttributeError, TypeError, ValueError) as exc:
            _raise("native_validator_unavailable", str(exc), profile_id)
        observed_fingerprint = callable_fingerprint(validator)
        if declared_fingerprint != observed_fingerprint:
            _raise(
                "stale_native_validator_binding",
                f"{callable_ref} fingerprint changed",
                profile_id,
            )
        validator_rows.append(
            ValidatorBinding(validator_id, callable_ref, declared_fingerprint)
        )
    if [item.validator_id for item in validator_rows] != sorted(
        item.validator_id for item in validator_rows
    ):
        _raise("native_validators_not_canonical", "validators must be sorted by validator_id", profile_id)
    _require_unique(
        (item.validator_id for item in validator_rows),
        "duplicate_native_validator",
        profile_id,
    )
    if set(allowed["validators"]) != {item.validator_id for item in validator_rows}:
        _raise(
            "native_validator_inventory_mismatch",
            "profile validator inventory does not equal the current family inventory",
            profile_id,
        )
    return NativeBinding(
        route_id=route_id,
        owner_callable=owner_callable,
        owner_fingerprint=owner_fingerprint,
        validators=tuple(validator_rows),
    )


def _validate_profile_set(
    profiles: list[TemplateProfile], base_profile_id: str
) -> None:
    profile_ids = {profile.profile_id for profile in profiles}
    base_profiles = [profile for profile in profiles if profile.is_base]
    if len(base_profiles) != 1 or base_profiles[0].profile_id != base_profile_id:
        _raise(
            "base_profile_identity_mismatch",
            "manifest base_profile_id must identify the sole base profile",
        )
    families: dict[str, list[str]] = {}
    for profile in profiles:
        if not profile.is_base:
            families.setdefault(profile.family, []).append(profile.profile_id)
        for related in (*profile.strictly_dominates, *profile.composable_with):
            if related not in profile_ids:
                _raise(
                    "profile_relation_unknown",
                    f"{profile.profile_id} references unknown profile {related}",
                    profile.profile_id,
                )
            if related == base_profile_id:
                _raise(
                    "base_profile_relation_invalid",
                    "base profile cannot participate in dominance or composition",
                    profile.profile_id,
                )
    if set(families) != set(REQUIRED_FAMILIES):
        _raise(
            "required_family_inventory_mismatch",
            f"observed families={sorted(families)}",
        )
    duplicates = {family: ids for family, ids in families.items() if len(ids) != 1}
    if duplicates:
        _raise("required_family_duplicate", f"families must be singular: {duplicates}")
    by_id = {profile.profile_id: profile for profile in profiles}
    for profile in profiles:
        for peer_id in profile.composable_with:
            if profile.profile_id not in by_id[peer_id].composable_with:
                _raise(
                    "composition_not_symmetric",
                    f"{profile.profile_id} and {peer_id} must name each other",
                    profile.profile_id,
                )


def _load_json_object(path: Path, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON constant: {value}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        _raise(code, f"{path.name}: {exc}")
    if not isinstance(value, dict):
        _raise(code, f"{path.name}: root must be an object")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _require_exact_keys(
    value: Mapping[str, Any],
    expected: set[str],
    label: str,
    profile_id: str = "",
) -> None:
    observed = set(value)
    if observed != expected:
        _raise(
            "unknown_or_missing_fields",
            f"{label} missing={sorted(expected - observed)} unknown={sorted(observed - expected)}",
            profile_id,
        )


def _canonical_declared_list(
    value: Any, label: str, profile_id: str = ""
) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        _raise("declared_list_invalid", f"{label} must be a string list", profile_id)
    normalized = tuple(item.strip() for item in value)
    if any(not item for item in normalized):
        _raise("declared_list_invalid", f"{label} contains an empty item", profile_id)
    if normalized != tuple(sorted(set(normalized))):
        _raise(
            "declared_list_not_canonical",
            f"{label} must be sorted and duplicate-free",
            profile_id,
        )
    return normalized


def _required_text(value: Any, label: str, profile_id: str = "") -> str:
    if not isinstance(value, str) or not value.strip():
        _raise("required_text_missing", f"{label} is required", profile_id)
    return value.strip()


def _required_id(value: Any, label: str, profile_id: str = "") -> str:
    text = _required_text(value, label, profile_id)
    if not ID_PATTERN.fullmatch(text):
        _raise("portable_id_invalid", f"{label} is not a portable id: {text}", profile_id)
    return text


def _required_sha256(value: Any, label: str, profile_id: str = "") -> str:
    text = _required_text(value, label, profile_id)
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        _raise("sha256_invalid", f"{label} must be 64 lowercase hex characters", profile_id)
    return text


def _require_unique(
    values: Iterable[str], code: str, profile_id: str = ""
) -> None:
    rows = list(values)
    if len(rows) != len(set(rows)):
        _raise(code, "declared values must be unique", profile_id)


def _validate_field_path(field_path: Any, profile_id: str) -> None:
    if not isinstance(field_path, str) or not FIELD_PATTERN.fullmatch(field_path):
        _raise(
            "field_path_invalid",
            f"invalid canonical field path: {field_path!r}",
            profile_id,
            str(field_path),
        )


def _validate_template_value(
    value: Any, profile_id: str, field_path: str
) -> None:
    if isinstance(value, dict):
        if "$request" in value:
            if set(value) != {"$request"} or not isinstance(value["$request"], str) or not value["$request"].strip():
                _raise(
                    "request_marker_invalid",
                    "request marker must be exactly {'$request': '<key>'}",
                    profile_id,
                    field_path,
                )
            return
        for child in value.values():
            _validate_template_value(child, profile_id, field_path)
    elif isinstance(value, list):
        for child in value:
            _validate_template_value(child, profile_id, field_path)
    else:
        canonical_json(value)


def _raise(
    code: str,
    message: str,
    profile_id: str = "",
    field_path: str = "",
) -> None:
    raise CatalogValidationError(
        (Finding(code, message, profile_id=profile_id, field_path=field_path),)
    )
