"""Shared, read-only predict/observe/revise lifecycle rules for native routes."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, NamedTuple

COMMON_TERMINALS = frozenset({"continue_iteration", "model_closed_for_task", "progress_stalled", "iteration_limit", "external_input_required", "scope_excluded"})
SOURCE_TERMINALS = frozenset({"provider_access_required", "finite_action_exhausted"})
TERMINALS = COMMON_TERMINALS | SOURCE_TERMINALS


def baseline_identity(plain: Any) -> str:
    body = json.dumps(plain, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def source_identity(plain: dict) -> str:
    stable = copy.deepcopy(plain)
    stable.pop("generated_at", None)
    if isinstance(stable.get("metadata"), dict):
        stable["metadata"].pop("updated_at", None)
    return baseline_identity(stable)


def require_prediction_identity(expected: str, actual: str) -> None:
    if expected != actual:
        raise ValueError("stale_prediction: re-freeze (baseline model changed)")


def select_terminal(*, closed=False, iteration=0, max_iterations=8, stalled=False,
                    external=False, scope_excluded=False, provider_unavailable=False,
                    finite_action_exhausted=False, limit_reached=False):
    """Use one order; routes supply their existing domain-specific predicates."""
    if scope_excluded:
        return "scope_excluded"
    if limit_reached or iteration >= max_iterations:
        return "iteration_limit"
    if closed:
        return "model_closed_for_task"
    if stalled:
        return "progress_stalled"
    if provider_unavailable:
        return "provider_access_required"
    if finite_action_exhausted:
        return "finite_action_exhausted"
    if external:
        return "external_input_required"
    return "continue_iteration"


def validate_candidate(baseline_path, candidate_path, baseline, candidate):
    if Path(baseline_path).resolve() == Path(candidate_path).resolve():
        raise ValueError("candidate model path must differ from baseline")
    if baseline_identity(baseline) == baseline_identity(candidate):
        raise ValueError("candidate model content must differ from baseline")


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
