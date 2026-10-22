"""One deterministic set-based gap transition shared by the three model loops."""

from typing import Iterable, NamedTuple


class GapLineage(NamedTuple):
    resolved_gap_ids: tuple[str, ...]
    persisted_gap_ids: tuple[str, ...]
    introduced_gap_ids: tuple[str, ...]
    gap_transitions: dict[str, str]


def gap_lineage(before_open: Iterable[str], after_open: Iterable[str]) -> GapLineage:
    before, after = set(before_open), set(after_open)
    resolved = tuple(sorted(before - after))
    persisted = tuple(sorted(before & after))
    introduced = tuple(sorted(after - before))
    return GapLineage(resolved, persisted, introduced, {
        **dict.fromkeys(resolved, "resolved"),
        **dict.fromkeys(persisted, "persisted"),
        **dict.fromkeys(introduced, "introduced"),
    })
