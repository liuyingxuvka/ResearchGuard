"""LogicGuard-owned native binding registry and instance validators.

The registry is deliberately target-specific and fully owns its validation
semantics.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
from typing import Any, Callable, Mapping


Validator = Callable[[Mapping[str, Any]], tuple[str, ...]]


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return True


def _require(fields: Mapping[str, Any], *field_paths: str) -> list[str]:
    return [
        f"missing_or_empty:{field_path}"
        for field_path in field_paths
        if field_path not in fields or not _present(fields[field_path])
    ]


def validate_base_profile(fields: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(_require(fields, "purpose.scope"))


def validate_purpose_profile(fields: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        _require(
            fields,
            "purpose.guarded_purpose",
            "purpose.protected_failure_ids",
            "purpose.claim_boundary",
        )
    )


def validate_argument_profile(fields: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        _require(
            fields,
            "argument.root_claim",
            "argument.acceptance",
            "argument.claim_boundary",
        )
    )


def validate_structured_artifact_profile(fields: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        _require(
            fields,
            "structure.artifact_kind",
            "structure.boundaries",
            "structure.claim_boundary",
        )
    )


def validate_source_library_profile(fields: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        _require(
            fields,
            "source.registry",
            "source.provenance",
            "source.claim_boundary",
        )
    )


def validate_deepening_profile(fields: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        _require(
            fields,
            "deepening.queue",
            "deepening.stop_rules",
            "deepening.claim_boundary",
        )
    )


def validate_synthesis_profile(fields: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        _require(
            fields,
            "synthesis.goal",
            "synthesis.delivery_profile",
            "synthesis.claim_boundary",
        )
    )


def validate_execution_package_profile(fields: Mapping[str, Any]) -> tuple[str, ...]:
    findings = _require(
        fields,
        "execution.declared_checks",
        "execution.closure",
        "execution.claim_boundary",
    )
    if fields.get("execution.closure") != "enforced":
        findings.append("execution_closure_not_enforced")
    return tuple(findings)


ALLOWED_BINDINGS: dict[str, dict[str, Any]] = {
    "base": {
        "route_id": "route:logicguard-authoritative-depth",
        "owner_callable": "researchguard.logic.validator:validate_model",
        "validators": {
            "logicguard-template-pack:base": "researchguard.logic_template_packs.native_validators:validate_base_profile",
        },
    },
    "purpose": {
        "route_id": "route:logicguard-authoritative-depth",
        "owner_callable": "researchguard.logic.validator:validate_model",
        "validators": {
            "logicguard-template-pack:purpose": "researchguard.logic_template_packs.native_validators:validate_purpose_profile",
        },
    },
    "argument": {
        "route_id": "route:logicguard-authoritative-depth",
        "owner_callable": "researchguard.logic.argument_modeling:create_argument_model",
        "validators": {
            "logicguard-template-pack:argument": "researchguard.logic_template_packs.native_validators:validate_argument_profile",
        },
    },
    "structured-artifact": {
        "route_id": "route:researchguard.logic:structured-artifact",
        "owner_callable": "researchguard.logic.structured_artifact:build_artifact_map",
        "validators": {
            "logicguard-template-pack:structured-artifact": "researchguard.logic_template_packs.native_validators:validate_structured_artifact_profile",
        },
    },
    "source-library": {
        "route_id": "route:researchguard.logic:source-library",
        "owner_callable": "researchguard.logic.source_library:SourceLibrary",
        "validators": {
            "logicguard-template-pack:source-library": "researchguard.logic_template_packs.native_validators:validate_source_library_profile",
        },
    },
    "deepening": {
        "route_id": "route:researchguard.logic:model-deepening",
        "owner_callable": "researchguard.logic.importance:summarize_importance",
        "validators": {
            "logicguard-template-pack:deepening": "researchguard.logic_template_packs.native_validators:validate_deepening_profile",
        },
    },
    "synthesis": {
        "route_id": "route:researchguard.logic:artifact-synthesis",
        "owner_callable": "researchguard.logic.synthesis:synthesize_artifact_plan",
        "validators": {
            "logicguard-template-pack:synthesis": "researchguard.logic_template_packs.native_validators:validate_synthesis_profile",
        },
    },
    "execution-package": {
        "route_id": "route:logicguard-authoritative-depth",
        "owner_callable": "researchguard.logic.execution_depth:build_logic_depth_receipt",
        "validators": {
            "logicguard-template-pack:execution-package": "researchguard.logic_template_packs.native_validators:validate_execution_package_profile",
        },
    },
}


def resolve_callable(callable_ref: str) -> Callable[..., Any]:
    if callable_ref.count(":") != 1:
        raise ValueError(f"callable reference must use module:attribute: {callable_ref}")
    module_name, attribute_name = callable_ref.split(":", 1)
    if not module_name or not attribute_name or "." in attribute_name:
        raise ValueError(f"callable reference must name one public module attribute: {callable_ref}")
    module = importlib.import_module(module_name)
    value = getattr(module, attribute_name)
    if not callable(value):
        raise TypeError(f"bound native target is not callable: {callable_ref}")
    return value


def callable_fingerprint(value: Callable[..., Any]) -> str:
    try:
        source = inspect.getsource(value)
    except (OSError, TypeError):
        module = inspect.getmodule(value)
        module_file = getattr(module, "__file__", "") if module else ""
        source = f"{module_file}:{getattr(value, '__qualname__', repr(value))}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def allowed_binding(family: str) -> dict[str, Any]:
    try:
        return ALLOWED_BINDINGS[family]
    except KeyError as exc:
        raise KeyError(f"no current native binding is registered for family {family}") from exc
