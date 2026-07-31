"""Minimal support and attack evidence for LogicGuard conclusions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable, Literal, Sequence


SetOracle = Callable[[tuple[str, ...]], bool]
WordingLicense = Literal["assert", "qualify", "withhold"]


@dataclass(frozen=True)
class MinimalArgumentSet:
    kind: Literal["support", "attack"]
    node_ids: tuple[str, ...]
    necessity_witnesses: tuple[tuple[str, bool], ...]
    deletion_minimal: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ConclusionLicense:
    wording_license: WordingLicense
    support: MinimalArgumentSet | None
    attack: MinimalArgumentSet | None
    reason_code: str
    claim_boundary: str = (
        "The license reflects only the supplied argument model and declared "
        "oracles. It does not independently establish factual truth."
    )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _minimize(
    node_ids: Sequence[str],
    *,
    oracle: SetOracle,
    kind: Literal["support", "attack"],
) -> MinimalArgumentSet | None:
    candidate = list(dict.fromkeys(sorted(str(item) for item in node_ids)))
    if not oracle(tuple(candidate)):
        return None
    for node_id in tuple(candidate):
        reduced = tuple(item for item in candidate if item != node_id)
        if oracle(reduced):
            candidate = list(reduced)
    minimal = tuple(candidate)
    witnesses = tuple(
        (
            node_id,
            not oracle(tuple(item for item in minimal if item != node_id)),
        )
        for node_id in minimal
    )
    return MinimalArgumentSet(
        kind=kind,
        node_ids=minimal,
        necessity_witnesses=witnesses,
        deletion_minimal=all(value for _, value in witnesses),
    )


def license_conclusion(
    support_node_ids: Sequence[str],
    attack_node_ids: Sequence[str],
    *,
    supports_conclusion: SetOracle,
    defeats_conclusion: SetOracle,
) -> ConclusionLicense:
    """Derive support/attack cores and a conservative wording license."""

    support = _minimize(
        support_node_ids,
        oracle=supports_conclusion,
        kind="support",
    )
    attack = _minimize(
        attack_node_ids,
        oracle=defeats_conclusion,
        kind="attack",
    )
    if support is None:
        return ConclusionLicense(
            wording_license="withhold",
            support=None,
            attack=attack,
            reason_code="no_declared_support_set",
        )
    if attack is not None:
        return ConclusionLicense(
            wording_license="qualify",
            support=support,
            attack=attack,
            reason_code="supported_but_unresolved_attack_exists",
        )
    return ConclusionLicense(
        wording_license="assert",
        support=support,
        attack=None,
        reason_code="supported_without_declared_defeating_set",
    )


__all__ = [
    "ConclusionLicense",
    "MinimalArgumentSet",
    "SetOracle",
    "WordingLicense",
    "license_conclusion",
]
