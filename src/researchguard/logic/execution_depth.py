"""Native execution-depth receipts built from LogicGuard-owned evaluation results."""

from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
from collections import Counter, deque
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .diagnostics import diagnose_model
from .evaluator import evaluate_model
from .importance import importance_for_node
from .model import (
    ArgumentCoverageUniverse,
    ClaimPerturbationCoverage,
    ClaimRoleCoverage,
    ClaimScopeCoverage,
    ConclusionCandidate,
    ConclusionTournament,
    DepthCoverageItem,
    DepthCoverageSummary,
    EvaluationResult,
    ImportancePolicy,
    LogicDepthReceipt,
    LogicModel,
    PerturbationEffectiveness,
    PerturbationPlanItem,
    RoleCoverage,
)
from .schema import STATE_IN, STATE_UNDECIDED
from .simulator import apply_default_perturbation


SUPPORT_TYPES = {"supports", "depends_on", "refines", "derives", "aggregates", "explains"}
OPPOSITION_TYPES = {"attacks", "undercuts", "contradicts"}
RISK_NODE_TYPES = {"Assumption", "Rebuttal", "Undercutter", "Qualifier", "Limitation", "Warrant"}
CONCLUSION_ROLES = {"conclusion", "alternative", "competing_conclusion", "preferred_conclusion"}
COVERAGE_DISPOSITIONS = {"answered", "bounded", "accepted", "rejected", "unresolved", "human_review"}
TOURNAMENT_RESOLVED_DISPOSITIONS = {"answered", "bounded", "accepted", "rejected"}
NATIVE_BROAD_THRESHOLD = 0.6
CRITICAL_IMPORTANCE_THRESHOLD = 0.85
VALID_THRESHOLD_RANGE = (0.0, 1.0)
ROLE_GROUPS: dict[str, set[str]] = {
    "claim": {"Claim"},
    "support": {"Evidence", "Premise", "Method", "Result"},
    "warrant": {"Warrant"},
    "assumption": {"Assumption"},
    "boundary": {"Qualifier", "Limitation"},
    "opposition": {"Rebuttal", "Undercutter"},
    # A broad conclusion must show that competing conclusions were considered.
    # The root argument may close this role with an explicit target-authored
    # disposition such as ``not_applicable``; silence is not coverage.
    "competition": {"Claim"},
}
REQUIRED_ROLE_GROUPS = tuple(ROLE_GROUPS)
CARD_REQUIRED_ROLE_GROUPS = tuple(
    role for role in REQUIRED_ROLE_GROUPS if role != "competition"
)
CLAIM_REQUIRED_ROLE_GROUPS = (
    "support",
    "warrant",
    "assumption",
    "boundary",
    "opposition",
)
ROLE_CLOSED_DISPOSITIONS = {
    "answered",
    "bounded",
    "accepted",
    "rejected",
    "not_applicable",
    "covered_elsewhere",
}
ROLE_OPEN_DISPOSITIONS = {"unresolved", "source_gap", "trace_gap", "human_review", "missing"}
UNIT_METADATA_KEYS = ("target_unit_id", "artifact_unit_id", "structure_unit_id", "task_unit_id")


def model_fingerprint(model: LogicModel) -> str:
    payload = json.dumps(model.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _reachable_nodes(model: LogicModel, roots: Iterable[str | None]) -> set[str]:
    queue = deque(root for root in roots if root and root in model.nodes)
    seen = set(queue)
    while queue:
        current = queue.popleft()
        for edge in model.incoming(current):
            if edge.source not in seen:
                seen.add(edge.source)
                queue.append(edge.source)
    return seen


def _string_tuple(value: object) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)


def derive_importance_policy() -> ImportancePolicy:
    """Return LogicGuard's single target-owned enforcement policy.

    The caller cannot select a lighter profile or change the threshold.  A
    model that cannot satisfy this policy is blocked and may only support a
    narrower *claim statement*; that boundary is a result, not a mode.
    """

    return ImportancePolicy(
        profile="enforced",
        requested_threshold=None,
        effective_threshold=NATIVE_BROAD_THRESHOLD,
        threshold_origin="logicguard_native_enforced",
        native_broad_threshold=NATIVE_BROAD_THRESHOLD,
        valid_range=VALID_THRESHOLD_RANGE,
        passed=True,
        gaps=(),
    )


def _records(value: object) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        if any(key in value for key in ("id", "card_id", "unit_id", "model_card_id")):
            return [dict(value)]
        rows: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, Mapping):
                row = dict(item)
                row.setdefault("id", str(key))
            else:
                row = {"id": str(key), "value": item}
            rows.append(row)
        return rows
    if isinstance(value, (list, tuple, set)):
        rows = []
        for item in value:
            if isinstance(item, Mapping):
                rows.append(dict(item))
            elif str(item):
                rows.append({"id": str(item)})
        return rows
    if value not in (None, ""):
        return [{"id": str(value)}]
    return []


def _record_id(record: Mapping[str, Any]) -> str:
    for key in ("id", "card_id", "unit_id", "model_card_id", "structure_unit_id"):
        if record.get(key) not in (None, ""):
            return str(record[key])
    return ""


def _node_ids_from_record(record: Mapping[str, Any]) -> set[str]:
    values: list[str] = []
    for key in ("node_ids", "nodes", "member_node_ids", "members"):
        values.extend(_string_tuple(record.get(key)))
    return set(values)


def _boolish(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "excluded"}
    return bool(value)


def _target_unit_inventory(model: LogicModel) -> tuple[tuple[str, ...], tuple[str, ...]]:
    target_ids: set[str] = set()
    modeled_ids: set[str] = set()
    for key in ("target_unit_ids", "artifact_unit_ids", "structure_unit_ids", "task_unit_ids"):
        target_ids.update(_string_tuple(model.metadata.get(key)))
    for key in ("target_units", "artifact_units", "structure_units", "task_units"):
        for record in _records(model.metadata.get(key)):
            unit_id = _record_id(record)
            if not unit_id:
                continue
            target_ids.add(unit_id)
            if _node_ids_from_record(record).intersection(model.nodes):
                modeled_ids.add(unit_id)
    for node in model.nodes.values():
        for key in UNIT_METADATA_KEYS:
            for unit_id in _string_tuple(node.get(key)):
                target_ids.add(unit_id)
                modeled_ids.add(unit_id)
    return tuple(sorted(target_ids)), tuple(sorted(modeled_ids))


def _card_inventory(
    model: LogicModel,
    important_node_ids: set[str],
) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {
        "root_argument": {
            "node_ids": set(important_node_ids),
            "importance": 1.0,
            "role_dispositions": {},
            "origins": {"synthetic_root"},
            "explicit": False,
            "excluded": False,
            "exclusion_reason": "",
            "exclusion_disposition": "",
        }
    }

    def ensure(
        card_id: str,
        *,
        origin: str = "",
        explicit: bool = False,
    ) -> dict[str, Any]:
        card = cards.setdefault(
            card_id,
            {
                "node_ids": set(),
                "importance": None,
                "role_dispositions": {},
                "origins": set(),
                "explicit": False,
                "excluded": False,
                "exclusion_reason": "",
                "exclusion_disposition": "",
            },
        )
        if origin:
            card["origins"].add(origin)
        if explicit:
            card["explicit"] = True
        return card

    for card_id in _string_tuple(model.metadata.get("model_card_ids")):
        ensure(card_id, origin="declared_card_id", explicit=True)
    for record in _records(model.metadata.get("model_cards")):
        card_id = _record_id(record)
        if not card_id:
            continue
        card = ensure(card_id, origin="declared_card_record", explicit=True)
        card["node_ids"].update(_node_ids_from_record(record))
        if record.get("importance") is not None:
            try:
                card["importance"] = float(record["importance"])
            except (TypeError, ValueError):
                card["importance"] = 1.0
        dispositions = record.get("role_dispositions") or {}
        if isinstance(dispositions, Mapping):
            card["role_dispositions"].update(
                {str(key): str(value).strip().lower() for key, value in dispositions.items()}
            )
        card["excluded"] = _boolish(
            record.get("excluded", record.get("coverage_excluded", False))
        )
        card["exclusion_reason"] = str(
            record.get("exclusion_reason", record.get("reason", "")) or ""
        ).strip()
        card["exclusion_disposition"] = str(
            record.get(
                "exclusion_disposition",
                record.get("coverage_disposition", record.get("disposition", "")),
            )
            or ""
        ).strip().lower()
    for record in _records(model.metadata.get("excluded_model_cards")):
        card_id = _record_id(record)
        if not card_id:
            continue
        card = ensure(card_id, origin="declared_exclusion", explicit=True)
        card["node_ids"].update(_node_ids_from_record(record))
        card["excluded"] = True
        card["exclusion_reason"] = str(
            record.get("exclusion_reason", record.get("reason", "")) or ""
        ).strip()
        card["exclusion_disposition"] = str(
            record.get(
                "exclusion_disposition",
                record.get("coverage_disposition", record.get("disposition", "")),
            )
            or ""
        ).strip().lower()
    for node_id, node in model.nodes.items():
        for card_id in _string_tuple(node.get("model_card_id", node.get("card_id", ()))):
            ensure(card_id, origin="node_card_binding", explicit=True)["node_ids"].add(node_id)
    for block_id, block in model.blocks.items():
        card = ensure(block_id, origin="native_argument_block", explicit=True)
        card["node_ids"].update(
            block.input_nodes
            + block.internal_nodes
            + block.output_claims
            + block.local_assumptions
            + block.local_rebuttals
        )
    global_dispositions = model.metadata.get("role_dispositions") or {}
    if isinstance(global_dispositions, Mapping):
        if set(global_dispositions).intersection(REQUIRED_ROLE_GROUPS):
            cards["root_argument"]["role_dispositions"].update(
                {str(key): str(value).strip().lower() for key, value in global_dispositions.items()}
            )
        else:
            for card_id, dispositions in global_dispositions.items():
                if isinstance(dispositions, Mapping):
                    ensure(
                        str(card_id),
                        origin="declared_role_disposition",
                        explicit=True,
                    )["role_dispositions"].update(
                        {str(key): str(value).strip().lower() for key, value in dispositions.items()}
                    )
    return cards


def _structural_card_importance(
    model: LogicModel,
    node_ids: tuple[str, ...],
) -> float:
    """Derive importance from structural use, not only caller metadata."""

    if not node_ids:
        return 0.0
    members = set(node_ids)
    values = [importance_for_node(model, node_id).importance for node_id in node_ids]
    if model.root_claim in members:
        values.append(1.0)
    for edge in model.edges:
        if edge.source in members and edge.target in model.nodes:
            values.append(importance_for_node(model, edge.target).importance)
        if edge.target in members and edge.source in model.nodes and edge.type in OPPOSITION_TYPES:
            values.append(importance_for_node(model, edge.source).importance)
    return max(values, default=0.0)


def _explicit_card_inventory_present(model: LogicModel) -> bool:
    """Return whether the target supplied a real card/block denominator.

    ``root_argument`` is a useful aggregate view, but it is synthetic.  A
    broad receipt therefore also needs at least one target-authored card or
    native block so a rich aggregate cannot hide a shallow important unit.
    """

    return bool(
        _string_tuple(model.metadata.get("model_card_ids"))
        or _records(model.metadata.get("model_cards"))
        or model.blocks
        or any(
            _string_tuple(node.get("model_card_id", node.get("card_id", ())))
            for node in model.nodes.values()
        )
    )


def _node_covers_role(
    model: LogicModel,
    node_id: str,
    role: str,
) -> bool:
    node = model.nodes[node_id]
    if role != "competition":
        return node.type in ROLE_GROUPS[role]
    if node_id == model.root_claim or node.type != "Claim":
        return False
    return bool(
        node.role in CONCLUSION_ROLES
        or node.get_bool("conclusion_candidate")
        or str(node.get("alternative_to", "")) == str(model.root_claim or "")
    )


def _role_coverage(
    model: LogicModel,
    important_node_ids: set[str],
    policy: ImportancePolicy,
    *,
    card_inventory: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[RoleCoverage, ...]:
    rows: list[RoleCoverage] = []
    inventory = card_inventory or _card_inventory(model, important_node_ids)
    for card_id, raw in sorted(inventory.items()):
        node_ids = tuple(sorted(set(raw["node_ids"]).intersection(model.nodes)))
        member_importance = max(
            (importance_for_node(model, node_id).importance for node_id in node_ids),
            default=0.0,
        )
        declared_importance = raw.get("importance")
        try:
            declared_numeric = (
                None
                if declared_importance is None
                else max(0.0, min(1.0, float(declared_importance)))
            )
        except (TypeError, ValueError):
            declared_numeric = 0.0
        structural_importance = _structural_card_importance(model, node_ids)
        importance = max(
            member_importance,
            structural_importance,
            declared_numeric if declared_numeric is not None else 0.0,
        )
        explicit = bool(raw.get("explicit"))
        excluded = bool(raw.get("excluded"))
        exclusion_reason = str(raw.get("exclusion_reason", "") or "").strip()
        exclusion_disposition = str(
            raw.get("exclusion_disposition", "") or ""
        ).strip().lower()
        exclusion_closed = bool(
            excluded
            and exclusion_reason
            and exclusion_disposition in ROLE_CLOSED_DISPOSITIONS
        )
        if excluded:
            rows.append(
                RoleCoverage(
                    card_id=card_id,
                    node_ids=node_ids,
                    importance=importance,
                    required_roles=(),
                    covered_roles=(),
                    terminal_dispositions={},
                    missing_roles=(),
                    unresolved_disposition_roles=(),
                    status="excluded_closed" if exclusion_closed else "blocked",
                    declared_importance=declared_numeric,
                    member_node_importance=member_importance,
                    structural_importance=structural_importance,
                    inventory_origins=tuple(sorted(raw.get("origins", ()))),
                    explicit=explicit,
                    excluded=True,
                    exclusion_reason=exclusion_reason,
                    exclusion_disposition=exclusion_disposition,
                    exclusion_closed=exclusion_closed,
                )
            )
            continue
        # The single enforced route keeps every explicit card visible.  Low
        # caller-declared importance cannot remove a target-owned obligation.
        required_roles = (
            REQUIRED_ROLE_GROUPS
            if card_id == "root_argument"
            else CARD_REQUIRED_ROLE_GROUPS
        )
        covered = {
            role
            for role in required_roles
            if any(_node_covers_role(model, node_id, role) for node_id in node_ids)
        }
        dispositions = {
            role: str(value).strip().lower()
            for role, value in dict(raw.get("role_dispositions") or {}).items()
            if role in required_roles and str(value).strip()
        }
        missing: list[str] = []
        unresolved: list[str] = []
        terminal: dict[str, str] = {}
        for role in required_roles:
            if role in covered:
                continue
            disposition = dispositions.get(role, "")
            if disposition in ROLE_CLOSED_DISPOSITIONS:
                terminal[role] = disposition
            elif disposition:
                unresolved.append(role)
                terminal[role] = disposition
            else:
                missing.append(role)
        status = "pass" if not missing and not unresolved else "blocked"
        rows.append(
            RoleCoverage(
                card_id=card_id,
                node_ids=node_ids,
                importance=importance,
                required_roles=required_roles,
                covered_roles=tuple(sorted(covered)),
                terminal_dispositions=terminal,
                missing_roles=tuple(missing),
                unresolved_disposition_roles=tuple(unresolved),
                status=status,
                declared_importance=declared_numeric,
                member_node_importance=member_importance,
                structural_importance=structural_importance,
                inventory_origins=tuple(sorted(raw.get("origins", ()))),
                explicit=explicit,
            )
        )
    return tuple(rows)


def _claim_role_dispositions(model: LogicModel, claim_id: str) -> dict[str, str]:
    dispositions: dict[str, str] = {}
    raw_global = model.metadata.get("claim_role_dispositions") or {}
    if isinstance(raw_global, Mapping):
        raw_claim = raw_global.get(claim_id) or {}
        if isinstance(raw_claim, Mapping):
            dispositions.update(
                {
                    str(role): str(value).strip().lower()
                    for role, value in raw_claim.items()
                    if str(value).strip()
                }
            )
    raw_node = model.nodes[claim_id].get("role_dispositions", {})
    if isinstance(raw_node, Mapping):
        dispositions.update(
            {
                str(role): str(value).strip().lower()
                for role, value in raw_node.items()
                if str(value).strip()
            }
        )
    return dispositions


def _acceptance_dependency_ids(model: LogicModel, claim_id: str) -> set[str]:
    condition = model.acceptance.get(claim_id, {})
    values: set[str] = set()
    if not isinstance(condition, Mapping):
        return values
    for key in ("all_of", "any_of", "none_of", "requires", "requires_not_out"):
        values.update(_string_tuple(condition.get(key)))
    at_least = condition.get("at_least_k")
    if isinstance(at_least, Mapping):
        values.update(_string_tuple(at_least.get("nodes")))
    return values.intersection(model.nodes)


def _connected_claim_roles(model: LogicModel, claim_id: str) -> dict[str, set[str]]:
    connected = {role: set() for role in CLAIM_REQUIRED_ROLE_GROUPS}
    for edge in model.incoming(claim_id):
        if edge.source not in model.nodes:
            continue
        node_type = model.nodes[edge.source].type
        if node_type in ROLE_GROUPS["support"] and edge.type in SUPPORT_TYPES:
            connected["support"].add(edge.source)
        elif node_type == "Warrant" and edge.type in SUPPORT_TYPES:
            connected["warrant"].add(edge.source)
        elif node_type == "Assumption" and edge.type in SUPPORT_TYPES:
            connected["assumption"].add(edge.source)
        elif node_type in ROLE_GROUPS["boundary"] and edge.type in {
            *SUPPORT_TYPES,
            "qualifies",
            "contextualizes",
        }:
            connected["boundary"].add(edge.source)
        elif node_type in ROLE_GROUPS["opposition"] and edge.type in OPPOSITION_TYPES:
            connected["opposition"].add(edge.source)
    for node_id in _acceptance_dependency_ids(model, claim_id):
        node_type = model.nodes[node_id].type
        for role in CLAIM_REQUIRED_ROLE_GROUPS:
            if node_type in ROLE_GROUPS[role]:
                connected[role].add(node_id)
    return connected


def _sharing_is_explicit(
    model: LogicModel,
    node_id: str,
    consumer_claim_ids: set[str],
) -> bool:
    node = model.nodes[node_id]
    declared = set(
        _string_tuple(
            node.get("shared_claim_ids", node.get("shared_for_claim_ids", ()))
        )
    )
    if consumer_claim_ids <= declared:
        return True
    related_edges = [
        edge
        for edge in model.edges
        if edge.source == node_id and edge.target in consumer_claim_ids
    ]
    return bool(related_edges) and all(
        edge.metadata.get("shared") is True
        or consumer_claim_ids
        <= set(_string_tuple(edge.metadata.get("shared_claim_ids", ())))
        for edge in related_edges
    )


def _claim_role_coverage(
    model: LogicModel,
    important_node_ids: set[str],
    card_inventory: Mapping[str, Mapping[str, Any]],
    *,
    excluded_node_ids: set[str] | None = None,
) -> tuple[ClaimRoleCoverage, ...]:
    excluded_nodes = excluded_node_ids or set()
    claim_ids = tuple(
        sorted(
            node_id
            for node_id in important_node_ids
            if node_id in model.nodes
            and model.nodes[node_id].type == "Claim"
            and node_id not in excluded_nodes
        )
    )
    raw_by_claim = {
        claim_id: _connected_claim_roles(model, claim_id) for claim_id in claim_ids
    }
    consumers_by_role_node: dict[str, set[str]] = {}
    for claim_id, roles in raw_by_claim.items():
        for node_ids in roles.values():
            for node_id in node_ids:
                consumers_by_role_node.setdefault(node_id, set()).add(claim_id)

    rows: list[ClaimRoleCoverage] = []
    raw_claim_sets = model.metadata.get("claim_perturbation_sets") or {}
    for claim_id in claim_ids:
        connected = raw_by_claim[claim_id]
        dispositions = _claim_role_dispositions(model, claim_id)
        missing: list[str] = []
        unresolved: list[str] = []
        terminal: dict[str, str] = {}
        for role in CLAIM_REQUIRED_ROLE_GROUPS:
            if connected[role]:
                continue
            disposition = dispositions.get(role, "")
            if disposition in ROLE_CLOSED_DISPOSITIONS:
                terminal[role] = disposition
            elif disposition:
                unresolved.append(role)
                terminal[role] = disposition
            else:
                missing.append(role)
        implicit_shared = tuple(
            sorted(
                node_id
                for node_id in {
                    item for values in connected.values() for item in values
                }
                if len(consumers_by_role_node.get(node_id, ())) > 1
                and not _sharing_is_explicit(
                    model,
                    node_id,
                    consumers_by_role_node[node_id],
                )
            )
        )
        applicable = {
            item for values in connected.values() for item in values
        }
        claim_node = model.nodes[claim_id]
        applicable.update(
            _string_tuple(claim_node.get("applicable_perturbation_node_ids", ()))
        )
        if isinstance(raw_claim_sets, Mapping):
            applicable.update(_string_tuple(raw_claim_sets.get(claim_id, ())))
        applicable = {
            node_id
            for node_id in applicable
            if node_id in model.nodes
            and node_id != claim_id
            and node_id not in excluded_nodes
        }
        perturbation_disposition = str(
            claim_node.get("perturbation_disposition", "") or ""
        ).strip().lower()
        if not applicable and perturbation_disposition not in ROLE_CLOSED_DISPOSITIONS:
            missing.append("applicable_perturbation")
        card_ids = tuple(
            sorted(
                card_id
                for card_id, raw in card_inventory.items()
                if claim_id in set(raw.get("node_ids", ()))
                and not bool(raw.get("excluded"))
            )
        )
        status = (
            "pass"
            if not missing and not unresolved and not implicit_shared
            else "blocked"
        )
        rows.append(
            ClaimRoleCoverage(
                claim_id=claim_id,
                card_ids=card_ids,
                importance=importance_for_node(model, claim_id).importance,
                required_roles=CLAIM_REQUIRED_ROLE_GROUPS,
                connected_role_node_ids={
                    role: tuple(sorted(node_ids))
                    for role, node_ids in connected.items()
                },
                terminal_dispositions=terminal,
                missing_roles=tuple(dict.fromkeys(missing)),
                unresolved_disposition_roles=tuple(unresolved),
                implicit_shared_role_node_ids=implicit_shared,
                applicable_perturbation_node_ids=tuple(sorted(applicable)),
                perturbation_disposition=perturbation_disposition,
                status=status,
            )
        )
    return tuple(rows)


def _is_critical(model: LogicModel, node_id: str) -> bool:
    node = model.nodes[node_id]
    disposition = str(node.get("disposition", "") or "").strip().lower()
    if disposition in ROLE_CLOSED_DISPOSITIONS:
        return False
    return bool(
        importance_for_node(model, node_id).importance >= CRITICAL_IMPORTANCE_THRESHOLD
        or str(node.impact or "").strip().lower() in {"high", "critical"}
        or node.get_bool("critical")
    )


def _requested_claim_nodes(
    model: LogicModel,
    requested_claim_scope_ids: Iterable[str] | None,
) -> tuple[str, ...]:
    if requested_claim_scope_ids is not None:
        requested = tuple(str(item) for item in requested_claim_scope_ids if str(item))
    else:
        requested = _string_tuple(
            model.metadata.get(
                "requested_claim_scope_ids",
                model.metadata.get("claim_scope_node_ids", ()),
            )
        )
    if not requested:
        requested = tuple(
            item
            for item in (model.root_claim, *_conclusion_candidate_ids(model))
            if item
        )
    return tuple(dict.fromkeys(requested))


def build_argument_coverage_universe(
    model: LogicModel,
    result: EvaluationResult | None = None,
    *,
    importance_policy: ImportancePolicy | None = None,
    requested_claim_scope_ids: Iterable[str] | None = None,
) -> ArgumentCoverageUniverse:
    """Derive LogicGuard's authoritative current argument/card coverage denominator."""

    result = result or evaluate_model(model)
    policy = importance_policy or derive_importance_policy()
    requested_scope = _requested_claim_nodes(model, requested_claim_scope_ids)
    conclusion_ids = _conclusion_candidate_ids(model)
    reachable = _reachable_nodes(model, (model.root_claim, *conclusion_ids))
    important_ids = {
        node_id
        for node_id in model.nodes
        if importance_for_node(model, node_id).importance >= policy.effective_threshold
    }
    important_ids.update(node_id for node_id in requested_scope if node_id in model.nodes)
    if model.root_claim and model.root_claim in model.nodes:
        important_ids.add(model.root_claim)

    # Card reconciliation happens before role or perturbation credit.  Every
    # explicit card remains visible in broad mode.  A closed exclusion can
    # remove only nodes that belong exclusively to excluded cards; if those
    # nodes still participate in the active argument, the exclusion is a gap.
    card_inventory = _card_inventory(model, important_ids)
    excluded_card_ids = {
        card_id
        for card_id, raw in card_inventory.items()
        if bool(raw.get("excluded"))
    }
    closed_excluded_card_ids = {
        card_id
        for card_id in excluded_card_ids
        if str(card_inventory[card_id].get("exclusion_reason", "") or "").strip()
        and str(
            card_inventory[card_id].get("exclusion_disposition", "") or ""
        ).strip().lower()
        in ROLE_CLOSED_DISPOSITIONS
    }
    unresolved_excluded_card_ids = excluded_card_ids.difference(
        closed_excluded_card_ids
    )
    nonexcluded_explicit_nodes = {
        node_id
        for card_id, raw in card_inventory.items()
        if card_id != "root_argument"
        and bool(raw.get("explicit"))
        and not bool(raw.get("excluded"))
        for node_id in set(raw.get("node_ids", ()))
    }
    excluded_node_ids = {
        node_id
        for card_id in closed_excluded_card_ids
        for node_id in set(card_inventory[card_id].get("node_ids", ()))
        if node_id not in nonexcluded_explicit_nodes
    }
    active_excluded_node_ids = {
        node_id
        for node_id in excluded_node_ids
        if node_id in reachable or node_id in requested_scope
    }
    important_ids.difference_update(excluded_node_ids)

    # Connected role nodes and target-declared applicable perturbations are
    # part of the important claim's child universe even when their own caller
    # importance is low.  Iterate to a fixed point in case a declared
    # applicable node introduces another important claim.
    for _ in range(max(1, len(model.nodes))):
        card_inventory = _card_inventory(model, important_ids)
        card_inventory["root_argument"]["node_ids"].difference_update(
            excluded_node_ids
        )
        claim_roles = _claim_role_coverage(
            model,
            important_ids,
            card_inventory,
            excluded_node_ids=excluded_node_ids,
        )
        expanded_ids = {
            node_id
            for row in claim_roles
            for node_id in row.applicable_perturbation_node_ids
        }
        expanded_ids.difference_update(excluded_node_ids)
        new_ids = expanded_ids.difference(important_ids)
        if not new_ids:
            break
        important_ids.update(new_ids)

    card_inventory = _card_inventory(model, important_ids)
    card_inventory["root_argument"]["node_ids"].difference_update(
        excluded_node_ids
    )
    roles = _role_coverage(
        model,
        important_ids,
        policy,
        card_inventory=card_inventory,
    )
    claim_roles = _claim_role_coverage(
        model,
        important_ids,
        card_inventory,
        excluded_node_ids=excluded_node_ids,
    )
    disconnected = important_ids.difference(reachable)
    terminally_disposed: set[str] = set()
    unresolved_disconnected: set[str] = set()
    for node_id in disconnected:
        disposition = str(model.nodes[node_id].get("disposition", "") or "").strip().lower()
        if disposition in ROLE_CLOSED_DISPOSITIONS:
            terminally_disposed.add(node_id)
        else:
            unresolved_disconnected.add(node_id)
    target_unit_ids, modeled_target_unit_ids = _target_unit_inventory(model)
    unmodeled_target_unit_ids = set(target_unit_ids).difference(modeled_target_unit_ids)
    covered_scope = tuple(
        node_id
        for node_id in requested_scope
        if node_id in important_ids and node_id in result.node_results
    )
    missing_scope = tuple(node_id for node_id in requested_scope if node_id not in covered_scope)
    scope = ClaimScopeCoverage(
        requested_node_ids=requested_scope,
        covered_node_ids=covered_scope,
        missing_node_ids=missing_scope,
        coverage_ratio=(len(covered_scope) / len(requested_scope)) if requested_scope else 0.0,
        passed=bool(requested_scope) and not missing_scope,
    )
    critical = {
        node_id for node_id in important_ids if node_id != model.root_claim and _is_critical(model, node_id)
    }
    findings: list[str] = []
    if not important_ids:
        findings.append("authoritative_node_universe_empty")
    if not target_unit_ids:
        findings.append("target_unit_inventory_empty")
    if not _explicit_card_inventory_present(model):
        findings.append("model_card_inventory_empty")
    findings.extend(
        f"model_card_exclusion_unresolved:{card_id}"
        for card_id in sorted(unresolved_excluded_card_ids)
    )
    findings.extend(
        f"excluded_model_card_still_structurally_active:{node_id}"
        for node_id in sorted(active_excluded_node_ids)
    )
    findings.extend(f"importance_policy:{gap}" for gap in policy.gaps)
    findings.extend(f"unmodeled_target_unit:{unit_id}" for unit_id in sorted(unmodeled_target_unit_ids))
    findings.extend(
        f"disconnected_important:{node_id}" for node_id in sorted(unresolved_disconnected)
    )
    for row in roles:
        findings.extend(f"missing_role:{row.card_id}:{role}" for role in row.missing_roles)
        findings.extend(
            f"unresolved_role_disposition:{row.card_id}:{role}"
            for role in row.unresolved_disposition_roles
        )
    for row in claim_roles:
        findings.extend(
            f"claim_role_missing:{row.claim_id}:{role}"
            for role in row.missing_roles
        )
        findings.extend(
            f"claim_role_disposition_unresolved:{row.claim_id}:{role}"
            for role in row.unresolved_disposition_roles
        )
        findings.extend(
            f"implicit_shared_role_node:{node_id}:{row.claim_id}"
            for node_id in row.implicit_shared_role_node_ids
        )
    findings.extend(f"claim_scope_missing:{node_id}" for node_id in missing_scope)
    fingerprint_payload = {
        "owner_id": "researchguard.logic.authoritative-argument-coverage",
        "model_fingerprint": model_fingerprint(model),
        "target_unit_ids": target_unit_ids,
        "modeled_target_unit_ids": modeled_target_unit_ids,
        "model_card_ids": [row.card_id for row in roles],
        "important_node_ids": sorted(important_ids),
        "reachable_node_ids": sorted(reachable),
        "critical_perturbable_node_ids": sorted(critical),
        "role_coverage": [row.to_dict() for row in roles],
        "claim_role_coverage": [row.to_dict() for row in claim_roles],
        "discovered_model_card_ids": sorted(card_inventory),
        "declared_model_card_ids": sorted(
            card_id
            for card_id, raw in card_inventory.items()
            if bool(raw.get("explicit"))
        ),
        "excluded_model_card_ids": sorted(excluded_card_ids),
        "unresolved_excluded_model_card_ids": sorted(
            unresolved_excluded_card_ids
        ),
        "active_excluded_node_ids": sorted(active_excluded_node_ids),
        "importance_policy": policy.to_dict(),
        "claim_scope": scope.to_dict(),
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ArgumentCoverageUniverse(
        owner_id="researchguard.logic.authoritative-argument-coverage",
        universe_fingerprint=fingerprint,
        target_unit_ids=target_unit_ids,
        modeled_target_unit_ids=modeled_target_unit_ids,
        unmodeled_target_unit_ids=tuple(sorted(unmodeled_target_unit_ids)),
        model_card_ids=tuple(row.card_id for row in roles),
        important_node_ids=tuple(sorted(important_ids)),
        reachable_node_ids=tuple(sorted(reachable)),
        disconnected_important_node_ids=tuple(sorted(disconnected)),
        terminally_disposed_disconnected_node_ids=tuple(sorted(terminally_disposed)),
        unresolved_disconnected_node_ids=tuple(sorted(unresolved_disconnected)),
        critical_perturbable_node_ids=tuple(sorted(critical)),
        role_coverage=roles,
        claim_role_coverage=claim_roles,
        importance_policy=policy,
        claim_scope=scope,
        discovered_model_card_ids=tuple(sorted(card_inventory)),
        declared_model_card_ids=tuple(
            sorted(
                card_id
                for card_id, raw in card_inventory.items()
                if bool(raw.get("explicit"))
            )
        ),
        excluded_model_card_ids=tuple(sorted(excluded_card_ids)),
        unresolved_excluded_model_card_ids=tuple(
            sorted(unresolved_excluded_card_ids)
        ),
        card_reconciliation_passed=not (
            unresolved_excluded_card_ids or active_excluded_node_ids
        ),
        findings=tuple(dict.fromkeys(findings)),
    )


def _response_nodes(model: LogicModel, objection_id: str, result: EvaluationResult) -> tuple[str, ...]:
    responses = []
    for edge in model.incoming(objection_id):
        if edge.type in OPPOSITION_TYPES and edge.source in result.node_results:
            responses.append(edge.source)
    return tuple(dict.fromkeys(responses))


def compute_depth_coverage(
    model: LogicModel,
    result: EvaluationResult | None = None,
    *,
    important_threshold: float = 0.6,
    authoritative_node_ids: Iterable[str] | None = None,
) -> DepthCoverageSummary:
    result = result or evaluate_model(model)
    conclusion_ids = _conclusion_candidate_ids(model)
    reachable = _reachable_nodes(model, (model.root_claim, *conclusion_ids))
    if authoritative_node_ids is None:
        required_ids = {
            node_id
            for node_id in model.nodes
            if importance_for_node(model, node_id).importance >= important_threshold
        }
        required_ids.update(conclusion_ids)
    else:
        required_ids = {node_id for node_id in authoritative_node_ids if node_id in model.nodes}
    if model.root_claim:
        required_ids.add(model.root_claim)

    items: list[DepthCoverageItem] = []
    role_counts: Counter[str] = Counter()
    uncovered: list[str] = []
    for node_id in sorted(required_ids, key=lambda value: (-importance_for_node(model, value).importance, value)):
        node = model.nodes[node_id]
        evaluation = result.node_results.get(node_id)
        importance = importance_for_node(model, node_id).importance
        responses = _response_nodes(model, node_id, result) if node.type in {"Rebuttal", "Undercutter"} else ()
        disposition = str(node.get("disposition", "") or "").strip().lower()
        consumers = _string_tuple(node.get("downstream_consumers", node.get("downstream_consumer", ())))
        evaluated = evaluation is not None
        status = "covered" if evaluated else "not_evaluated"
        reason = "The native evaluator produced a current node result." if evaluated else "No native evaluation result exists."
        active_objection = node.type in {"Rebuttal", "Undercutter"} and bool(node.active)
        if node_id not in reachable and disposition not in ROLE_CLOSED_DISPOSITIONS:
            status = "disconnected_important"
            reason = "Important node is outside every requested conclusion path and lacks a closed disposition."
        if active_objection and not responses and disposition not in COVERAGE_DISPOSITIONS:
            status = "unresolved_objection"
            reason = "Active important objection has neither an evaluated response nor an explicit disposition."
        if status != "covered":
            uncovered.append(node_id)
        role_counts[node.type] += 1
        items.append(
            DepthCoverageItem(
                node_id=node_id,
                node_type=node.type,
                importance=importance,
                state=evaluation.state if evaluation else "NOT_RUN",
                confidence=evaluation.confidence if evaluation else 0.0,
                reachable=node_id in reachable,
                evaluated=evaluated,
                coverage_status=status,
                response_node_ids=responses,
                downstream_consumers=consumers,
                disposition=disposition,
                reason=reason,
            )
        )

    edge_counts: Counter[str] = Counter()
    for edge in model.edges:
        if edge.source in required_ids and edge.target in required_ids:
            if edge.type in SUPPORT_TYPES:
                edge_counts["support"] += 1
            elif edge.type in OPPOSITION_TYPES:
                edge_counts["opposition"] += 1
            else:
                edge_counts[edge.type] += 1
    return DepthCoverageSummary(
        important_threshold=important_threshold,
        required_count=len(items),
        covered_count=len(items) - len(uncovered),
        uncovered_node_ids=tuple(uncovered),
        role_counts=dict(sorted(role_counts.items())),
        edge_role_counts=dict(sorted(edge_counts.items())),
        semantic_coverage_passed=bool(items) and not uncovered,
        items=tuple(items),
    )


def _conclusion_candidate_ids(model: LogicModel) -> tuple[str, ...]:
    candidates: list[str] = []
    if model.root_claim and model.root_claim in model.nodes:
        candidates.append(model.root_claim)
    for node_id, node in model.nodes.items():
        if node_id == model.root_claim or node.type != "Claim":
            continue
        if (
            node.role in CONCLUSION_ROLES
            or node.get_bool("conclusion_candidate")
            or str(node.get("alternative_to", "")) == str(model.root_claim or "")
        ):
            candidates.append(node_id)
    return tuple(dict.fromkeys(candidates))


def _candidate_sort_key(candidate: ConclusionCandidate) -> tuple[int, float, float, str]:
    state_rank = {STATE_IN: 2, STATE_UNDECIDED: 1}.get(candidate.state, 0)
    return (-state_rank, -candidate.confidence, -candidate.importance, candidate.node_id)


def build_conclusion_tournament(
    model: LogicModel,
    result: EvaluationResult | None = None,
    *,
    comparable_margin: float = 0.15,
) -> ConclusionTournament:
    result = result or evaluate_model(model)
    raw: list[ConclusionCandidate] = []
    for node_id in _conclusion_candidate_ids(model):
        evaluation = result.node_results[node_id]
        objections = []
        for edge in model.incoming(node_id):
            if edge.type not in OPPOSITION_TYPES:
                continue
            objection_eval = result.node_results.get(edge.source)
            objection = model.nodes[edge.source]
            disposition = str(objection.get("disposition", "") or "").strip().lower()
            if (
                objection_eval
                and objection_eval.state == STATE_IN
                and not _response_nodes(model, edge.source, result)
                and disposition not in TOURNAMENT_RESOLVED_DISPOSITIONS
            ):
                objections.append(edge.source)
        raw.append(
            ConclusionCandidate(
                node_id=node_id,
                state=evaluation.state,
                confidence=evaluation.confidence,
                importance=importance_for_node(model, node_id).importance,
                rank=0,
                is_root=node_id == model.root_claim,
                unresolved_objection_ids=tuple(objections),
            )
        )
    ordered = sorted(raw, key=_candidate_sort_key)
    candidates = tuple(
        ConclusionCandidate(
            node_id=item.node_id,
            state=item.state,
            confidence=item.confidence,
            importance=item.importance,
            rank=index,
            is_root=item.is_root,
            unresolved_objection_ids=item.unresolved_objection_ids,
        )
        for index, item in enumerate(ordered, start=1)
    )
    root = next((item for item in candidates if item.is_root), None)
    unresolved = []
    if root:
        for item in candidates:
            if item.is_root or item.state == "OUT":
                continue
            if item.rank < root.rank or item.confidence >= max(0.0, root.confidence - comparable_margin):
                unresolved.append(item.node_id)
    preferred = candidates[0].node_id if candidates else None
    if not root:
        status = "blocked"
        wording = "No root conclusion is available."
    elif unresolved or preferred != root.node_id or root.unresolved_objection_ids:
        status = "bounded"
        wording = "The root conclusion remains qualified because live competitors or objections remain unresolved."
    else:
        status = "preferred"
        wording = "The root conclusion is structurally preferred under the declared model and tested boundaries."
    return ConclusionTournament(
        root_claim=model.root_claim,
        preferred_conclusion=preferred,
        candidates=candidates,
        unresolved_competitor_ids=tuple(unresolved),
        status=status,
        allowed_wording=wording,
    )


def _uncertainty(confidence: float) -> float:
    return max(0.0, 1.0 - abs(confidence - 0.5) * 2.0)


def _mutation_for(node_type: str) -> str:
    if node_type == "Evidence":
        return "remove_evidence"
    if node_type in {"Rebuttal", "Undercutter"}:
        return "activate_opposition"
    if node_type == "Assumption":
        return "flip_assumption"
    return "force_out"


def select_perturbation_plan(
    model: LogicModel,
    result: EvaluationResult | None = None,
    *,
    budget: int = 6,
    candidate_node_ids: Iterable[str] | None = None,
) -> tuple[PerturbationPlanItem, ...]:
    result = result or evaluate_model(model)
    candidate_ids = (
        {node_id for node_id in candidate_node_ids if node_id in model.nodes}
        if candidate_node_ids is not None
        else _reachable_nodes(model, (model.root_claim, *_conclusion_candidate_ids(model)))
    )
    ranked: list[PerturbationPlanItem] = []
    for node_id in candidate_ids:
        if node_id == model.root_claim:
            continue
        node = model.nodes[node_id]
        evaluation = result.node_results.get(node_id)
        if not evaluation:
            continue
        importance = importance_for_node(model, node_id).importance
        uncertainty = _uncertainty(evaluation.confidence)
        centrality = min(1.0, (len(model.incoming(node_id)) + len(model.outgoing(node_id))) / 4.0)
        opposition_bonus = 1.0 if node.type in {"Rebuttal", "Undercutter"} else 0.0
        priority = 0.5 * importance + 0.3 * uncertainty + 0.15 * centrality + 0.05 * opposition_bonus
        reasons = [f"importance={importance:.2f}", f"uncertainty={uncertainty:.2f}", f"centrality={centrality:.2f}"]
        if opposition_bonus:
            reasons.append("untested opposition")
        critical = _is_critical(model, node_id)
        if critical:
            reasons.append("target-owned critical perturbation")
        ranked.append(
            PerturbationPlanItem(
                node_id=node_id,
                node_type=node.type,
                mutation=_mutation_for(node.type),
                importance=importance,
                uncertainty=uncertainty,
                centrality=centrality,
                priority=priority,
                reasons=tuple(reasons),
                critical=critical,
            )
        )
    ranked.sort(key=lambda item: (not item.critical, -item.priority, -item.importance, item.node_id))
    critical_items = [item for item in ranked if item.critical]
    noncritical_items = [item for item in ranked if not item.critical]
    target_count = max(max(0, budget), len(critical_items))
    return tuple([*critical_items, *noncritical_items[: max(0, target_count - len(critical_items))]])


def _support_signature(model: LogicModel, result: EvaluationResult) -> tuple[tuple[str, str, int], ...]:
    reachable = _reachable_nodes(model, (model.root_claim, *_conclusion_candidate_ids(model)))
    return tuple(
        sorted(
            (node_id, result.node_results[node_id].state, int(result.node_results[node_id].confidence * 10000))
            for node_id in reachable
            if node_id in result.node_results
        )
    )


def evaluate_perturbation_effectiveness(
    model: LogicModel,
    plan: Iterable[PerturbationPlanItem],
    result: EvaluationResult | None = None,
) -> tuple[PerturbationEffectiveness, ...]:
    result = result or evaluate_model(model)
    baseline_root = result.root()
    baseline_diagnostics = diagnose_model(model, result)
    baseline_codes = {finding.code for finding in baseline_diagnostics.findings}
    baseline_tournament = build_conclusion_tournament(model, result)
    baseline_ranking = tuple(item.node_id for item in baseline_tournament.candidates)
    baseline_signature = _support_signature(model, result)
    effects: list[PerturbationEffectiveness] = []
    for item in plan:
        variant = copy.deepcopy(model)
        apply_default_perturbation(variant, item.node_id)
        variant_result = evaluate_model(variant)
        variant_root = variant_result.root()
        variant_codes = {finding.code for finding in diagnose_model(variant, variant_result).findings}
        variant_ranking = tuple(candidate.node_id for candidate in build_conclusion_tournament(variant, variant_result).candidates)
        state_changed = (baseline_root.state if baseline_root else None) != (variant_root.state if variant_root else None)
        baseline_confidence = baseline_root.confidence if baseline_root else None
        result_confidence = variant_root.confidence if variant_root else None
        confidence_changed = (
            baseline_confidence is not None
            and result_confidence is not None
            and abs(baseline_confidence - result_confidence) > 0.0001
        )
        support_path_changed = baseline_signature != _support_signature(variant, variant_result)
        diagnostics_changed = baseline_codes != variant_codes
        ranking_changed = baseline_ranking != variant_ranking
        effective = any((state_changed, confidence_changed, support_path_changed, diagnostics_changed, ranking_changed))
        effects.append(
            PerturbationEffectiveness(
                node_id=item.node_id,
                mutation=item.mutation,
                baseline_state=baseline_root.state if baseline_root else None,
                result_state=variant_root.state if variant_root else None,
                baseline_confidence=baseline_confidence,
                result_confidence=result_confidence,
                state_changed=state_changed,
                confidence_changed=confidence_changed,
                support_path_changed=support_path_changed,
                diagnostics_changed=diagnostics_changed,
                ranking_changed=ranking_changed,
                effective=effective,
                changed_diagnostic_codes=tuple(sorted(baseline_codes ^ variant_codes)),
            )
        )
    return tuple(effects)


def _claim_perturbation_coverage(
    universe: ArgumentCoverageUniverse,
    plan: Iterable[PerturbationPlanItem],
    effectiveness: Iterable[PerturbationEffectiveness],
) -> tuple[ClaimPerturbationCoverage, ...]:
    selected = {item.node_id for item in plan}
    effects = {item.node_id: item for item in effectiveness}
    rows: list[ClaimPerturbationCoverage] = []
    for claim_row in universe.claim_role_coverage:
        applicable = set(claim_row.applicable_perturbation_node_ids)
        selected_ids = applicable.intersection(selected)
        executed_ids = applicable.intersection(effects)
        effective_ids = {
            node_id
            for node_id in applicable
            if effects.get(node_id) and effects[node_id].effective
        }
        uncovered = applicable.difference(executed_ids)
        ineffective = executed_ids.difference(effective_ids)
        terminal = claim_row.perturbation_disposition
        passed = bool(
            (applicable and not uncovered and not ineffective)
            or (
                not applicable
                and terminal in ROLE_CLOSED_DISPOSITIONS
            )
        )
        rows.append(
            ClaimPerturbationCoverage(
                claim_id=claim_row.claim_id,
                applicable_node_ids=tuple(sorted(applicable)),
                selected_node_ids=tuple(sorted(selected_ids)),
                executed_node_ids=tuple(sorted(executed_ids)),
                effective_node_ids=tuple(sorted(effective_ids)),
                uncovered_node_ids=tuple(sorted(uncovered)),
                ineffective_node_ids=tuple(sorted(ineffective)),
                terminal_disposition=terminal,
                status="pass" if passed else "blocked",
            )
        )
    return tuple(rows)


def _native_obligation_observations(
    model: LogicModel,
    universe: ArgumentCoverageUniverse,
    coverage: DepthCoverageSummary,
    plan: tuple[PerturbationPlanItem, ...],
    effectiveness: tuple[PerturbationEffectiveness, ...],
    claim_perturbations: tuple[ClaimPerturbationCoverage, ...],
) -> tuple[dict[str, Any], ...]:
    """Project exact LogicGuard-owned evidence for every depth obligation."""

    coverage_by_node = {item.node_id: item.to_dict() for item in coverage.items}
    plan_by_node = {item.node_id: item.to_dict() for item in plan}
    effect_by_node = {item.node_id: item.to_dict() for item in effectiveness}
    claim_perturbation_by_id = {
        item.claim_id: item.to_dict() for item in claim_perturbations
    }
    observations: list[dict[str, Any]] = []

    def add(
        native_object_id: str,
        obligation_id: str,
        content: dict[str, Any],
    ) -> None:
        observations.append(
            {
                "native_object_id": native_object_id,
                "target_obligation_ids": [obligation_id],
                "evidence_ref": f"logicguard:{native_object_id}",
                "evidence_sha256": _canonical_sha256(content),
                "content": content,
            }
        )

    for unit_id in universe.target_unit_ids:
        member_nodes = []
        for node in model.nodes.values():
            declared_units = {
                unit
                for key in UNIT_METADATA_KEYS
                for unit in _string_tuple(node.metadata.get(key))
            }
            if unit_id in declared_units:
                member_nodes.append(node.to_dict())
        add(
            f"target-unit:{unit_id}",
            "obligation:logicguard-authoritative-universe",
            {
                "target_unit_id": unit_id,
                "modeled": unit_id in universe.modeled_target_unit_ids,
                "member_nodes": member_nodes,
                "universe_fingerprint": universe.universe_fingerprint,
            },
        )

    for node_id in universe.important_node_ids:
        node = model.nodes.get(node_id)
        add(
            f"important-node:{node_id}",
            "obligation:logicguard-authoritative-universe",
            {
                "node": node.to_dict() if node else None,
                "coverage": coverage_by_node.get(node_id),
                "reachable": node_id in universe.reachable_node_ids,
                "universe_fingerprint": universe.universe_fingerprint,
            },
        )

    for card in universe.role_coverage:
        for role in card.required_roles:
            role_node_ids = [
                node_id
                for node_id in card.node_ids
                if node_id in model.nodes and model.nodes[node_id].type in ROLE_GROUPS[role]
            ]
            add(
                f"card-role:{card.card_id}:{role}",
                "obligation:logicguard-role-completeness",
                {
                    "card": card.to_dict(),
                    "role": role,
                    "role_nodes": [model.nodes[node_id].to_dict() for node_id in role_node_ids],
                    "terminal_disposition": card.terminal_dispositions.get(role, ""),
                },
            )

    for claim in universe.claim_role_coverage:
        for role in claim.required_roles:
            role_node_ids = list(claim.connected_role_node_ids.get(role, ()))
            add(
                f"claim-role:{claim.claim_id}:{role}",
                "obligation:logicguard-claim-role-completeness",
                {
                    "claim": claim.to_dict(),
                    "role": role,
                    "role_nodes": [
                        model.nodes[node_id].to_dict()
                        for node_id in role_node_ids
                        if node_id in model.nodes
                    ],
                    "terminal_disposition": claim.terminal_dispositions.get(role, ""),
                },
            )

    for node_id in universe.critical_perturbable_node_ids:
        add(
            f"critical-perturbation:{node_id}",
            "obligation:logicguard-critical-perturbations",
            {
                "node": model.nodes[node_id].to_dict() if node_id in model.nodes else None,
                "plan": plan_by_node.get(node_id),
                "effect": effect_by_node.get(node_id),
            },
        )

    for claim in universe.claim_role_coverage:
        claim_coverage = claim_perturbation_by_id.get(claim.claim_id)
        for node_id in claim.applicable_perturbation_node_ids:
            add(
                f"claim-perturbation:{claim.claim_id}:{node_id}",
                "obligation:logicguard-claim-perturbations",
                {
                    "claim_id": claim.claim_id,
                    "node": model.nodes[node_id].to_dict() if node_id in model.nodes else None,
                    "plan": plan_by_node.get(node_id),
                    "effect": effect_by_node.get(node_id),
                    "claim_coverage": claim_coverage,
                },
            )

    for claim_id in universe.claim_scope.requested_node_ids:
        add(
            f"claim-scope:{claim_id}",
            "obligation:logicguard-claim-scope",
            {
                "claim_node": model.nodes[claim_id].to_dict() if claim_id in model.nodes else None,
                "claim_scope": universe.claim_scope.to_dict(),
            },
        )
    return tuple(observations)


def _build_native_depth_analysis(
    model: LogicModel,
    *,
    budget: int = 6,
    requested_claim_scope_ids: Iterable[str] | None = None,
) -> LogicDepthReceipt:
    result = evaluate_model(model)
    policy = derive_importance_policy()
    universe = build_argument_coverage_universe(
        model,
        result,
        importance_policy=policy,
        requested_claim_scope_ids=requested_claim_scope_ids,
    )
    coverage = compute_depth_coverage(
        model,
        result,
        important_threshold=policy.effective_threshold,
        authoritative_node_ids=universe.important_node_ids,
    )
    tournament = build_conclusion_tournament(model, result)
    plan = select_perturbation_plan(
        model,
        result,
        budget=budget,
        candidate_node_ids=universe.important_node_ids,
    )
    effectiveness = evaluate_perturbation_effectiveness(model, plan, result)
    claim_perturbations = _claim_perturbation_coverage(
        universe,
        plan,
        effectiveness,
    )
    selected_ids = {item.node_id for item in plan}
    untested = tuple(
        sorted(
            node_id
            for node_id in universe.important_node_ids
            if node_id != model.root_claim
            and node_id not in selected_ids
        )
    )
    critical_ids = set(universe.critical_perturbable_node_ids)
    effect_by_id = {item.node_id: item for item in effectiveness}
    critical_executed = critical_ids.intersection(selected_ids)
    critical_effective = {
        node_id for node_id in critical_ids if effect_by_id.get(node_id) and effect_by_id[node_id].effective
    }
    critical_uncovered = critical_ids.difference(critical_executed)
    critical_ineffective = critical_executed.difference(critical_effective)
    critical_coverage = {
        "eligible_count": len(critical_ids),
        "selected_count": len(critical_executed),
        "executed_count": len(critical_executed),
        "effective_count": len(critical_effective),
        "uncovered_ids": sorted(critical_uncovered),
        "ineffective_ids": sorted(critical_ineffective),
        "effective_coverage_ratio": (
            len(critical_effective) / len(critical_ids) if critical_ids else 1.0
        ),
    }
    gaps: list[str] = list(universe.findings)
    if not coverage.semantic_coverage_passed:
        gaps.append("semantic_coverage_incomplete")
    if tournament.unresolved_competitor_ids or tournament.status == "bounded":
        gaps.append("unresolved_competing_conclusions")
    if not plan:
        gaps.append("no_model_derived_perturbations")
    if plan and not any(item.effective for item in effectiveness):
        gaps.append("no_effective_perturbations")
    gaps.extend(f"critical_perturbation_uncovered:{node_id}" for node_id in sorted(critical_uncovered))
    gaps.extend(
        f"ineffective_critical_perturbation:{node_id}" for node_id in sorted(critical_ineffective)
    )
    gaps.extend(f"untested_high_impact:{node_id}" for node_id in untested)
    for row in claim_perturbations:
        gaps.extend(
            f"claim_perturbation_uncovered:{row.claim_id}:{node_id}"
            for node_id in row.uncovered_node_ids
        )
        gaps.extend(
            f"claim_perturbation_ineffective:{row.claim_id}:{node_id}"
            for node_id in row.ineffective_node_ids
        )
        if not row.applicable_node_ids and row.status != "pass":
            gaps.append(f"claim_perturbation_set_missing:{row.claim_id}")
    gaps = list(dict.fromkeys(gaps))
    status = "blocked" if gaps else "pass"
    broad_claim_licensed = status == "pass"
    covered_claim_scope = (
        "broad"
        if broad_claim_licensed
        else ("bounded" if universe.claim_scope.covered_node_ids else "not_run")
    )
    return LogicDepthReceipt(
        receipt_version="researchguard.logic.depth.v2",
        model_id=model.id,
        model_fingerprint=model_fingerprint(model),
        generated_at=datetime.now(timezone.utc).isoformat(),
        evaluation=result,
        coverage=coverage,
        tournament=tournament,
        perturbation_plan=plan,
        perturbation_effectiveness=effectiveness,
        untested_high_impact_node_ids=untested,
        unresolved_gaps=tuple(gaps),
        status=status,
        broad_claim_licensed=broad_claim_licensed,
        claim_boundary=(
            "LogicGuard depth receipts license only the current target-owned task/artifact/card universe, "
            "its covered claim scope, role-complete important cards, and effective critical perturbations. "
            "They do not establish factual truth or alternatives absent from the supplied artifact inventory."
        ),
        native_obligation_evidence=_native_obligation_observations(
            model,
            universe,
            coverage,
            plan,
            effectiveness,
            claim_perturbations,
        ),
        profile="enforced",
        coverage_universe=universe,
        critical_perturbation_coverage=critical_coverage,
        claim_perturbation_coverage=claim_perturbations,
        requested_claim_scope="complete",
        covered_claim_scope=covered_claim_scope,
    )


def build_logic_depth_receipt(
    model: LogicModel,
    *,
    target_root: str | Path,
    guard_contract: str | Path,
    budget: int = 6,
    requested_claim_scope_ids: Iterable[str] | None = None,
) -> LogicDepthReceipt:
    """Issue the public receipt only after current target-purpose proof passes."""

    from .guard_model_contract import verify_target_contract

    proof = verify_target_contract(
        target_root=target_root,
        contract_path=guard_contract,
        expected_target_skill_id="logicguard",
    )
    comparison_model = copy.deepcopy(model)
    comparison_model.metadata.pop("source_path", None)
    if model_fingerprint(comparison_model) != proof["native_model_fingerprint"]:
        raise ValueError(
            "logicguard_blocked:guarded-depth-model-mismatch: supplied model is not the contract-bound candidate"
        )
    native = _build_native_depth_analysis(
        model,
        budget=budget,
        requested_claim_scope_ids=requested_claim_scope_ids,
    )
    return replace(
        native,
        receipt_version="researchguard.logic.depth.v3",
        target_contract_id=str(proof["contract_id"]),
        target_contract_fingerprint=str(proof["contract_fingerprint"]),
        target_purpose=str(proof["prevented_failure_purpose"]),
        target_proof_receipt=dict(proof),
        claim_boundary=(
            f"{proof['claim_boundary']} "
            "This guarded receipt also remains bounded by LogicGuard structural licensing and does not establish factual truth."
        ),
    )
