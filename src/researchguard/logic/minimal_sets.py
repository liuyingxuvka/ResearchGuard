"""Minimal support and attack evidence for LogicGuard conclusions."""

from __future__ import annotations

import copy
from collections import deque
from dataclasses import asdict, dataclass, replace
from typing import Callable, Literal, Sequence

from .evaluator import evaluate_model
from .model import LogicModel
from .schema import STATE_IN
from .simulator import apply_default_perturbation


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

    reason: str = ""

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
            reason="No declared support set licenses this conclusion.",
        )
    if attack is not None:
        return ConclusionLicense(
            wording_license="qualify",
            support=support,
            attack=attack,
            reason_code="supported_but_unresolved_attack_exists",
            reason="A support set exists, but a declared attack can defeat the conclusion.",
        )
    return ConclusionLicense(
        wording_license="assert",
        support=support,
        attack=None,
        reason_code="supported_without_declared_defeating_set",
        reason="A support set exists without a declared defeating attack.",
    )


def _candidate_sides(model: LogicModel, claim_id: str) -> tuple[list[str], list[str]]:
    """Classify each dependency by its edge entering the target claim.

    Carry that edge's side upstream, even across differently typed inner edges.
    A dependency with both kinds of path has support precedence; the target is
    never its own candidate, including in a cyclic graph.
    """

    support_types = {"supports", "depends_on", "refines", "derives", "aggregates", "qualifies", "contextualizes"}
    attack_types = {"attacks", "undercuts", "contradicts"}
    queue = deque((edge.source, "support" if edge.type in support_types else "attack")
                  for edge in model.incoming(claim_id) if edge.type in support_types | attack_types)
    seen: set[tuple[str, str]] = set()
    sides: dict[str, set[str]] = {}
    while queue:
        node_id, side = queue.popleft()
        if node_id == claim_id or (node_id, side) in seen:
            continue
        seen.add((node_id, side))
        sides.setdefault(node_id, set()).add(side)
        queue.extend((edge.source, side) for edge in model.incoming(node_id))
    supports = sorted(node_id for node_id, paths in sides.items() if "support" in paths)
    attacks = sorted(node_id for node_id, paths in sides.items() if "support" not in paths and "attack" in paths)
    return supports, attacks


def license_model_claim(model: LogicModel, claim_id: str) -> ConclusionLicense:
    """Minimal support and attack sets of one model claim, judged by the model's evaluator.

    Candidates follow the edge that enters the claim, carrying its side up the
    dependency path. Support wins if both sides reach the same dependency.
    Existing deletion minimization still uses the native evaluator. If no
    support set licenses the claim, report its actual native blockers instead
    of claiming an empty or deletion-minimal attack core.
    """

    node = model.nodes.get(claim_id)
    if node is None or node.type != "Claim":
        raise ValueError(f"claim is missing or not a Claim: {claim_id}")
    supports, attacks = _candidate_sides(model, claim_id)
    active = {item for item in attacks if model.nodes[item].active}

    def claim_state(kept_support: set[str], active_attacks: set[str]) -> str:
        variant = copy.deepcopy(model)
        for item in supports:
            if item not in kept_support:
                apply_default_perturbation(variant, item)
        for item in attacks:
            variant.nodes[item].active = item in active_attacks
        return evaluate_model(variant).node_results[claim_id].state

    license = license_conclusion(
        supports,
        attacks,
        supports_conclusion=lambda ids: claim_state(set(ids), active) == STATE_IN,
        defeats_conclusion=lambda ids: claim_state(set(supports), set(ids)) != STATE_IN,
    )
    native = evaluate_model(model).node_results[claim_id]
    if license.support is None and native.blockers:
        blockers = tuple(sorted(set(native.blockers)))
        names = "; ".join(f"{item} ({model.nodes[item].type}) blocks it" for item in blockers)
        return replace(license, attack=MinimalArgumentSet("attack", blockers, (), False),
                       reason_code="blocked_by_attack", reason=f"{claim_id} is {native.state}: {names}.")
    return replace(license, reason=f"{claim_id} is {native.state}; wording license {license.wording_license}. {license.reason}")


__all__ = [
    "ConclusionLicense",
    "MinimalArgumentSet",
    "SetOracle",
    "WordingLicense",
    "license_conclusion",
    "license_model_claim",
]
