"""ResearchGuard public package."""

from __future__ import annotations

__version__ = "0.5.1"

SUITE_ID = "researchguard-suite"
MEMBER_IDS = ("logicguard", "sourceguard", "traceguard", "experimentguard")

_LAZY_EXPORTS = {
    name: (module, name)
    for module, names in (
        ("model_envelope", ("BehaviorTransitionCase", "HandoffConsumerAcknowledgement", "HandoffConsumerRequirement", "HandoffFieldContract", "MemberModelEnvelope", "MemberBehaviorManifest", "NativeOwnerAttestation", "NativeReceiptReference", "ResponsibilitySpan")),
        ("domain_dna", ("EXTERNAL_DOMAIN_DNA_SCHEMA", "EXTERNAL_DOMAIN_DNA_SPEC_SCHEMA", "build_external_domain_parent_function_block", "derive_external_domain_native_bindings", "external_domain_dna_impact", "external_domain_dna_reverse", "qualify_external_domain_dna")),
        ("external_scope_authority", ("EXTERNAL_SCOPE_AUTHORITY_SCHEMA", "ExternalScopeAuthorityError", "assemble_external_scope_authority_record", "external_scope_authority_signing_payload", "validate_external_scope_authority_record")),
    ) for name in names
}


def __getattr__(name: str):
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    from importlib import import_module
    value = getattr(import_module(f"{__name__}.{module_name}"), attribute)
    globals()[name] = value
    return value

__all__ = [
    "BehaviorTransitionCase",
    "EXTERNAL_DOMAIN_DNA_SCHEMA",
    "EXTERNAL_DOMAIN_DNA_SPEC_SCHEMA",
    "EXTERNAL_SCOPE_AUTHORITY_SCHEMA",
    "ExternalScopeAuthorityError",
    "HandoffConsumerAcknowledgement",
    "HandoffConsumerRequirement",
    "HandoffFieldContract",
    "MEMBER_IDS",
    "MemberModelEnvelope",
    "MemberBehaviorManifest",
    "NativeOwnerAttestation",
    "NativeReceiptReference",
    "ResponsibilitySpan",
    "SUITE_ID",
    "__version__",
    "build_external_domain_parent_function_block",
    "assemble_external_scope_authority_record",
    "derive_external_domain_native_bindings",
    "external_domain_dna_impact",
    "external_domain_dna_reverse",
    "external_scope_authority_signing_payload",
    "qualify_external_domain_dna",
    "validate_external_scope_authority_record",
]
