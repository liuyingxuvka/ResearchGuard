"""ResearchGuard public package."""

from __future__ import annotations

__version__ = "0.5.9"

SUITE_ID = "researchguard-suite"
MEMBER_IDS = ("logicguard", "sourceguard", "traceguard", "experimentguard")

_LAZY_EXPORTS = {
    name: (module, name)
    for module, names in (
        ("model_envelope", ("BehaviorTransitionCase", "HandoffConsumerAcknowledgement", "HandoffConsumerRequirement", "HandoffFieldContract", "MemberModelEnvelope", "MemberBehaviorManifest", "NativeOwnerAttestation", "NativeReceiptReference", "ResponsibilitySpan")),
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
]
