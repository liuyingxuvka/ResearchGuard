"""Immutable public records for the LogicGuard template-pack adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .canonical import canonical_json, canonical_string_list, decode_canonical


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    profile_id: str = ""
    field_path: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "code": self.code,
                "message": self.message,
                "profile_id": self.profile_id,
                "field_path": self.field_path,
            }.items()
            if value
        }


@dataclass(frozen=True)
class Selector:
    purposes: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    context_tags_any: tuple[str, ...]

    def matches(self, request: "TemplateRequest") -> bool:
        if self.purposes and request.purpose not in self.purposes:
            return False
        if not set(self.required_capabilities).issubset(request.capabilities):
            return False
        if self.context_tags_any and not set(self.context_tags_any).intersection(request.context_tags):
            return False
        return True

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "purposes": list(self.purposes),
            "required_capabilities": list(self.required_capabilities),
            "context_tags_any": list(self.context_tags_any),
        }


@dataclass(frozen=True)
class ValidatorBinding:
    validator_id: str
    callable_ref: str
    callable_fingerprint: str

    def to_dict(self) -> dict[str, str]:
        return {
            "validator_id": self.validator_id,
            "callable": self.callable_ref,
            "callable_fingerprint": self.callable_fingerprint,
        }


@dataclass(frozen=True)
class NativeBinding:
    route_id: str
    owner_callable: str
    owner_fingerprint: str
    validators: tuple[ValidatorBinding, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "owner_callable": self.owner_callable,
            "owner_fingerprint": self.owner_fingerprint,
            "validators": [item.to_dict() for item in self.validators],
        }


@dataclass(frozen=True)
class TemplateProfile:
    profile_id: str
    profile_version: str
    family: str
    is_base: bool
    selector: Selector
    strictly_dominates: tuple[str, ...]
    composable_with: tuple[str, ...]
    emitted_fields: tuple[tuple[str, str], ...]
    field_owners: tuple[tuple[str, str], ...]
    native_binding: NativeBinding
    required_instance_fields: tuple[str, ...]
    claim_boundary: str
    content_digest: str

    @property
    def emitted_field_paths(self) -> tuple[str, ...]:
        return tuple(field for field, _value_json in self.emitted_fields)

    def emitted_value(self, field_path: str) -> Any:
        for field, value_json in self.emitted_fields:
            if field == field_path:
                return decode_canonical(value_json)
        raise KeyError(field_path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "family": self.family,
            "is_base": self.is_base,
            "selector": self.selector.to_dict(),
            "strictly_dominates": list(self.strictly_dominates),
            "composable_with": list(self.composable_with),
            "emitted_fields": {
                field: decode_canonical(value_json)
                for field, value_json in self.emitted_fields
            },
            "field_owners": dict(self.field_owners),
            "native_binding": self.native_binding.to_dict(),
            "required_instance_fields": list(self.required_instance_fields),
            "claim_boundary": self.claim_boundary,
            "content_digest": self.content_digest,
        }


@dataclass(frozen=True)
class TemplateCatalog:
    schema: str
    catalog_id: str
    catalog_version: str
    base_profile_id: str
    required_families: tuple[str, ...]
    profiles: tuple[TemplateProfile, ...]
    catalog_digest: str
    root: Path

    def profile(self, profile_id: str) -> TemplateProfile:
        for profile in self.profiles:
            if profile.profile_id == profile_id:
                return profile
        raise KeyError(profile_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "catalog_id": self.catalog_id,
            "catalog_version": self.catalog_version,
            "base_profile_id": self.base_profile_id,
            "required_families": list(self.required_families),
            "profile_ids": [profile.profile_id for profile in self.profiles],
            "catalog_digest": self.catalog_digest,
        }


@dataclass(frozen=True)
class TemplateRequest:
    purpose: str
    capabilities: tuple[str, ...]
    context_tags: tuple[str, ...]
    allow_base: bool
    parameters: tuple[tuple[str, str], ...]

    @classmethod
    def create(
        cls,
        *,
        purpose: str,
        capabilities: tuple[str, ...] | list[str] = (),
        context_tags: tuple[str, ...] | list[str] = (),
        allow_base: bool = False,
        parameters: Mapping[str, Any] | None = None,
    ) -> "TemplateRequest":
        if not isinstance(purpose, str) or not purpose.strip():
            raise ValueError("purpose is required")
        purpose_value = purpose.strip()
        normalized_parameters: list[tuple[str, str]] = []
        for key, value in (parameters or {}).items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("request parameter keys must be non-empty strings")
            normalized_parameters.append((key.strip(), canonical_json(value)))
        parameter_rows = tuple(sorted(normalized_parameters))
        if len({key for key, _value in parameter_rows}) != len(parameter_rows):
            raise ValueError("request parameters contain duplicate keys")
        return cls(
            purpose=purpose_value,
            capabilities=canonical_string_list(capabilities),
            context_tags=canonical_string_list(context_tags),
            allow_base=bool(allow_base),
            parameters=parameter_rows,
        )

    def parameter(self, key: str) -> Any:
        if key == "purpose":
            return self.purpose
        if key == "capabilities":
            return list(self.capabilities)
        if key == "context_tags":
            return list(self.context_tags)
        for parameter_key, value_json in self.parameters:
            if parameter_key == key:
                return decode_canonical(value_json)
        raise KeyError(key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "purpose": self.purpose,
            "capabilities": list(self.capabilities),
            "context_tags": list(self.context_tags),
            "allow_base": self.allow_base,
            "parameters": {
                key: decode_canonical(value_json)
                for key, value_json in self.parameters
            },
        }


@dataclass(frozen=True)
class TemplateSelection:
    decision: str
    request: TemplateRequest
    catalog_digest: str
    candidate_ids: tuple[str, ...]
    selected_profile_ids: tuple[str, ...]
    findings: tuple[Finding, ...]
    selection_fingerprint: str

    @property
    def successful(self) -> bool:
        return self.decision in {"base", "selected", "composed"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "request": self.request.to_dict(),
            "catalog_digest": self.catalog_digest,
            "candidate_ids": list(self.candidate_ids),
            "selected_profile_ids": list(self.selected_profile_ids),
            "findings": [item.to_dict() for item in self.findings],
            "selection_fingerprint": self.selection_fingerprint,
        }


@dataclass(frozen=True)
class ValidationObservation:
    validator_id: str
    status: str
    callable_ref: str
    callable_fingerprint: str
    finding_codes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "validator_id": self.validator_id,
            "status": self.status,
            "callable_ref": self.callable_ref,
            "callable_fingerprint": self.callable_fingerprint,
            "finding_codes": list(self.finding_codes),
        }


@dataclass(frozen=True)
class TemplateInstance:
    status: str
    selection_fingerprint: str
    selected_profile_ids: tuple[str, ...]
    fields: tuple[tuple[str, str], ...]
    field_owners: tuple[tuple[str, str], ...]
    native_bindings: tuple[NativeBinding, ...]
    validator_observations: tuple[ValidationObservation, ...]
    profile_claim_boundaries: tuple[tuple[str, str], ...]
    effective_claim_boundary: str
    findings: tuple[Finding, ...]
    instance_fingerprint: str

    def field_value(self, field_path: str) -> Any:
        for field, value_json in self.fields:
            if field == field_path:
                return decode_canonical(value_json)
        raise KeyError(field_path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "selection_fingerprint": self.selection_fingerprint,
            "selected_profile_ids": list(self.selected_profile_ids),
            "fields": {
                field: decode_canonical(value_json)
                for field, value_json in self.fields
            },
            "field_owners": dict(self.field_owners),
            "native_bindings": [binding.to_dict() for binding in self.native_bindings],
            "validator_observations": [
                observation.to_dict()
                for observation in self.validator_observations
            ],
            "profile_claim_boundaries": dict(self.profile_claim_boundaries),
            "effective_claim_boundary": self.effective_claim_boundary,
            "findings": [item.to_dict() for item in self.findings],
            "instance_fingerprint": self.instance_fingerprint,
        }


@dataclass(frozen=True)
class BuildResult:
    status: str
    selection: TemplateSelection
    instance: TemplateInstance | None
    findings: tuple[Finding, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "selection": self.selection.to_dict(),
            "instance": self.instance.to_dict() if self.instance else None,
            "findings": [item.to_dict() for item in self.findings],
        }
