"""Deterministic deletion-minimal contradiction cores for TraceGuard."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable, Literal, Sequence


ContradictionCoreStatus = Literal[
    "consistent",
    "core_found",
    "blocked_invalid_oracle",
]
ConsistencyOracle = Callable[[tuple[str, ...]], bool]


@dataclass(frozen=True)
class ContradictionCore:
    status: ContradictionCoreStatus
    constraint_ids: tuple[str, ...]
    necessity_witnesses: tuple[tuple[str, bool], ...]
    oracle_calls: int
    claim_boundary: str = (
        "The returned set is deletion-minimal for the supplied deterministic "
        "consistency oracle. It is not claimed to be the only or globally "
        "smallest contradiction."
    )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def find_deletion_minimal_contradiction_core(
    constraint_ids: Sequence[str],
    *,
    is_consistent: ConsistencyOracle,
) -> ContradictionCore:
    """Minimize an inconsistent constraint set without guessing semantics."""

    candidate = list(dict.fromkeys(sorted(str(item) for item in constraint_ids)))
    calls = 1
    if is_consistent(tuple(candidate)):
        return ContradictionCore(
            status="consistent",
            constraint_ids=(),
            necessity_witnesses=(),
            oracle_calls=calls,
        )

    for constraint_id in tuple(candidate):
        reduced = tuple(
            item for item in candidate if item != constraint_id
        )
        calls += 1
        if not is_consistent(reduced):
            candidate = list(reduced)

    witnesses: list[tuple[str, bool]] = []
    core = tuple(candidate)
    for constraint_id in core:
        without = tuple(item for item in core if item != constraint_id)
        calls += 1
        witnesses.append((constraint_id, is_consistent(without)))

    if not all(necessary for _, necessary in witnesses):
        return ContradictionCore(
            status="blocked_invalid_oracle",
            constraint_ids=core,
            necessity_witnesses=tuple(witnesses),
            oracle_calls=calls,
        )
    return ContradictionCore(
        status="core_found",
        constraint_ids=core,
        necessity_witnesses=tuple(witnesses),
        oracle_calls=calls,
    )


__all__ = [
    "ConsistencyOracle",
    "ContradictionCore",
    "ContradictionCoreStatus",
    "find_deletion_minimal_contradiction_core",
]
