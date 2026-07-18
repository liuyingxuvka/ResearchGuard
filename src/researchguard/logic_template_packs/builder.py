"""Deterministic LogicGuard template-pack instantiation and validation."""

from __future__ import annotations

from typing import Any, Mapping

from .canonical import canonical_json, canonical_sha256, decode_canonical
from .models import (
    BuildResult,
    Finding,
    NativeBinding,
    TemplateCatalog,
    TemplateInstance,
    TemplateProfile,
    TemplateSelection,
    ValidationObservation,
)
from .native_validators import (
    callable_fingerprint,
    resolve_callable,
)


EFFECTIVE_BOUNDARY = (
    "This instance validates deterministic template selection, materialized "
    "field ownership, declared LogicGuard-native bindings, and target-owned "
    "validator results for the exact catalog and request identities. It does "
    "not prove factual truth, final prose quality, production conformance, "
    "skill installation, release readiness, or future AI behavior."
)


def build_template_instance(
    catalog: TemplateCatalog,
    selection: TemplateSelection,
) -> BuildResult:
    if selection.catalog_digest != catalog.catalog_digest:
        finding = Finding(
            "selection_catalog_mismatch",
            "The selection was not made from the supplied current catalog.",
        )
        return BuildResult("blocked", selection, None, (finding,))
    if not selection.successful:
        finding = Finding(
            "selection_not_instantiable",
            f"Decision {selection.decision} cannot produce a template instance.",
        )
        return BuildResult(
            "blocked",
            selection,
            None,
            tuple((*selection.findings, finding)),
        )

    profiles = tuple(catalog.profile(profile_id) for profile_id in selection.selected_profile_ids)
    fields: dict[str, Any] = {}
    owners: dict[str, str] = {}
    findings: list[Finding] = []
    for profile in profiles:
        declared_owners = dict(profile.field_owners)
        for field_path, value_json in profile.emitted_fields:
            if field_path in fields:
                findings.append(
                    Finding(
                        "field_owner_conflict",
                        f"Field {field_path} is emitted by both {owners[field_path]} and {profile.profile_id}.",
                        profile_id=profile.profile_id,
                        field_path=field_path,
                    )
                )
                continue
            try:
                value = _resolve_request_values(
                    decode_canonical(value_json),
                    selection.request,
                )
            except KeyError as exc:
                findings.append(
                    Finding(
                        "request_parameter_missing",
                        f"Required request value {exc.args[0]} is absent.",
                        profile_id=profile.profile_id,
                        field_path=field_path,
                    )
                )
                continue
            fields[field_path] = value
            owner = declared_owners.get(field_path, "")
            if owner != profile.profile_id:
                findings.append(
                    Finding(
                        "field_owner_invalid",
                        f"Field {field_path} does not have exactly one selected profile owner.",
                        profile_id=profile.profile_id,
                        field_path=field_path,
                    )
                )
            else:
                owners[field_path] = owner

    structural_findings = _structural_findings(profiles, fields, owners)
    findings.extend(structural_findings)
    observations: list[ValidationObservation] = [
        ValidationObservation(
            validator_id="logicguard-template-pack:structure",
            status="pass" if not structural_findings else "failed",
            callable_ref="researchguard.logic_template_packs.builder:_structural_findings",
            callable_fingerprint=callable_fingerprint(_structural_findings),
            finding_codes=tuple(item.code for item in structural_findings),
        )
    ]
    for profile in profiles:
        for binding in profile.native_binding.validators:
            try:
                validator = resolve_callable(binding.callable_ref)
                observed_fingerprint = callable_fingerprint(validator)
                if observed_fingerprint != binding.callable_fingerprint:
                    codes = ("stale_native_validator_binding",)
                else:
                    result = validator(fields)
                    if not isinstance(result, tuple) or any(
                        not isinstance(item, str) for item in result
                    ):
                        codes = ("native_validator_result_invalid",)
                    else:
                        codes = tuple(result)
            except Exception as exc:
                codes = (f"native_validator_error:{type(exc).__name__}",)
            observations.append(
                ValidationObservation(
                    validator_id=binding.validator_id,
                    status="pass" if not codes else "failed",
                    callable_ref=binding.callable_ref,
                    callable_fingerprint=binding.callable_fingerprint,
                    finding_codes=codes,
                )
            )
            findings.extend(
                Finding(
                    code,
                    f"Native validator {binding.validator_id} did not pass.",
                    profile_id=profile.profile_id,
                )
                for code in codes
            )

    ordered_findings = tuple(
        sorted(
            findings,
            key=lambda item: (
                item.code,
                item.profile_id,
                item.field_path,
                item.message,
            ),
        )
    )
    ordered_fields = tuple(
        sorted((field_path, canonical_json(value)) for field_path, value in fields.items())
    )
    ordered_owners = tuple(sorted(owners.items()))
    native_bindings = tuple(profile.native_binding for profile in profiles)
    boundaries = tuple(
        (profile.profile_id, profile.claim_boundary)
        for profile in profiles
    )
    status = "valid" if not ordered_findings and all(
        observation.status == "pass" for observation in observations
    ) else "blocked"
    fingerprint_payload = {
        "selection_fingerprint": selection.selection_fingerprint,
        "selected_profile_ids": list(selection.selected_profile_ids),
        "fields": {
            field: decode_canonical(value_json)
            for field, value_json in ordered_fields
        },
        "field_owners": dict(ordered_owners),
        "native_bindings": [binding.to_dict() for binding in native_bindings],
        "validator_observations": [
            observation.to_dict()
            for observation in observations
        ],
        "profile_claim_boundaries": dict(boundaries),
        "effective_claim_boundary": EFFECTIVE_BOUNDARY,
        "status": status,
        "findings": [item.to_dict() for item in ordered_findings],
    }
    instance = TemplateInstance(
        status=status,
        selection_fingerprint=selection.selection_fingerprint,
        selected_profile_ids=selection.selected_profile_ids,
        fields=ordered_fields,
        field_owners=ordered_owners,
        native_bindings=native_bindings,
        validator_observations=tuple(observations),
        profile_claim_boundaries=boundaries,
        effective_claim_boundary=EFFECTIVE_BOUNDARY,
        findings=ordered_findings,
        instance_fingerprint=canonical_sha256(fingerprint_payload),
    )
    return BuildResult(status, selection, instance, ordered_findings)


def _resolve_request_values(value: Any, request) -> Any:
    if isinstance(value, dict):
        if set(value) == {"$request"}:
            return request.parameter(value["$request"])
        return {
            key: _resolve_request_values(item, request)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_resolve_request_values(item, request) for item in value]
    return value


def _structural_findings(
    profiles: tuple[TemplateProfile, ...],
    fields: Mapping[str, Any],
    owners: Mapping[str, str],
) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    selected = {profile.profile_id for profile in profiles}
    declared_fields = {
        field_path
        for profile in profiles
        for field_path in profile.emitted_field_paths
    }
    if set(fields) != declared_fields:
        for field_path in sorted(declared_fields - set(fields)):
            findings.append(
                Finding(
                    "declared_field_not_materialized",
                    f"Declared field {field_path} was not materialized.",
                    field_path=field_path,
                )
            )
        for field_path in sorted(set(fields) - declared_fields):
            findings.append(
                Finding(
                    "undeclared_field_materialized",
                    f"Undeclared field {field_path} was materialized.",
                    field_path=field_path,
                )
            )
    if set(owners) != set(fields):
        for field_path in sorted(set(fields) - set(owners)):
            findings.append(
                Finding(
                    "materialized_field_owner_missing",
                    f"Materialized field {field_path} has no owner.",
                    field_path=field_path,
                )
            )
    for field_path, owner in owners.items():
        if owner not in selected:
            findings.append(
                Finding(
                    "materialized_field_owner_not_selected",
                    f"Field {field_path} owner {owner} is not selected.",
                    field_path=field_path,
                )
            )
    for profile in profiles:
        for required in profile.required_instance_fields:
            if required not in fields:
                findings.append(
                    Finding(
                        "required_instance_field_missing",
                        f"Profile {profile.profile_id} requires {required}.",
                        profile_id=profile.profile_id,
                        field_path=required,
                    )
                )
    return tuple(findings)
