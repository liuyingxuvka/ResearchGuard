"""ResearchGuard public package."""

from __future__ import annotations

__version__ = "0.5.1"

SUITE_ID = "researchguard-suite"
MEMBER_IDS = ("logicguard", "sourceguard", "traceguard", "experimentguard")

from .model_envelope import (  # noqa: E402
    BehaviorTransitionCase,
    HandoffConsumerAcknowledgement,
    HandoffConsumerRequirement,
    HandoffFieldContract,
    MemberModelEnvelope,
    MemberBehaviorManifest,
    NativeOwnerAttestation,
    NativeReceiptReference,
    ResponsibilitySpan,
)
from .domain_dna import (  # noqa: E402
    EXTERNAL_DOMAIN_DNA_SCHEMA,
    EXTERNAL_DOMAIN_DNA_SPEC_SCHEMA,
    build_external_domain_parent_function_block,
    derive_external_domain_native_bindings,
    external_domain_dna_impact,
    external_domain_dna_reverse,
    qualify_external_domain_dna,
)
from .external_scope_authority import (  # noqa: E402
    EXTERNAL_SCOPE_AUTHORITY_SCHEMA,
    ExternalScopeAuthorityError,
    assemble_external_scope_authority_record,
    external_scope_authority_signing_payload,
    validate_external_scope_authority_record,
)

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
