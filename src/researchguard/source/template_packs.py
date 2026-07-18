"""Validated SourceGuard template-pack selection and native model assembly.

The adapter owns template selection only. Generated payloads remain ordinary
SourceGuard belief states: candidates are not evidence, anchors are not events,
and handoff is not downstream validation.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .schema import (
    BeliefState,
    SourceGuardModelContract,
    sourceguard_model_contract_fingerprint,
)


CATALOG_SCHEMA_ID = "guard-template-pack.catalog.v1"
SELECTION_RECEIPT_SCHEMA_ID = "guard-template-pack.selection-receipt.v1"
INSTANCE_RECEIPT_SCHEMA_ID = "guard-template-pack.instance-receipt.v1"
GUARD_FAMILY = "sourceguard"
EXPECTED_PROFILE_IDS = {
    "discovery",
    "gap",
    "citation",
    "disconfirming",
    "numeric-provenance",
    "multimodal-anchor",
    "lineage",
    "bridge-evidence",
}
CLAIM_BOUNDARY = (
    "SourceGuard template instances plan source discovery only; source candidates are not "
    "evidence, anchors are not events, and handoffs are not downstream validation."
)
NATIVE_BINDING = {
    "adapter_id": "researchguard.source.template_packs",
    "validator_id": "researchguard.source.template_packs.validate_native_payload",
    "schema_owner_id": "researchguard.source.schema.BeliefState.from_dict",
}


class TemplatePackError(ValueError):
    """Raised when template authority, selection, or native validation fails."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _without(mapping: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    blocked = set(keys)
    return {str(key): deepcopy(value) for key, value in mapping.items() if key not in blocked}


def seal_catalog(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy with canonical profile and catalog digests."""

    sealed = deepcopy(dict(data))
    profiles = sealed.get("profiles")
    if not isinstance(profiles, list):
        raise TemplatePackError("catalog profiles must be a list")
    for profile in profiles:
        if not isinstance(profile, dict):
            raise TemplatePackError("catalog profile must be a mapping")
        profile["profile_digest"] = _digest(_without(profile, "profile_digest"))
    sealed["catalog_digest"] = _digest(_without(sealed, "catalog_digest"))
    return sealed


def _catalog_path() -> Path:
    return Path(__file__).with_name("template_pack_catalog.json")


def load_catalog(path: str | Path | None = None) -> dict[str, Any]:
    catalog_path = Path(path) if path is not None else _catalog_path()
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TemplatePackError(f"cannot load template catalog: {exc}") from exc
    return validate_catalog_data(data)


def _as_string_tuple(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise TemplatePackError(f"{field} must be a list of non-empty strings")
    if len(value) != len(set(value)):
        raise TemplatePackError(f"{field} contains duplicates")
    return tuple(value)


def _validate_profile(profile: Mapping[str, Any], profile_ids: set[str]) -> None:
    profile_id = str(profile.get("profile_id", ""))
    if not profile_id:
        raise TemplatePackError("profile_id is required")
    selector = profile.get("selector")
    if not isinstance(selector, Mapping):
        raise TemplatePackError(f"{profile_id}: selector must be a mapping")
    required = set(_as_string_tuple(selector.get("required_intents", []), f"{profile_id}.required_intents"))
    excluded = set(_as_string_tuple(selector.get("excluded_intents", []), f"{profile_id}.excluded_intents"))
    if required & excluded:
        raise TemplatePackError(f"{profile_id}: required and excluded intents overlap")
    owned_fields = _as_string_tuple(profile.get("owned_fields"), f"{profile_id}.owned_fields")
    if not owned_fields:
        raise TemplatePackError(f"{profile_id}: at least one owned field is required")
    composition = profile.get("composition")
    if not isinstance(composition, Mapping) or not isinstance(composition.get("allowed"), bool):
        raise TemplatePackError(f"{profile_id}: composition contract is incomplete")
    compatible = set(_as_string_tuple(composition.get("compatible_with", []), f"{profile_id}.compatible_with"))
    if profile_id in compatible or not compatible <= profile_ids:
        raise TemplatePackError(f"{profile_id}: compatibility references an invalid profile")
    dominates = set(_as_string_tuple(profile.get("strict_dominates", []), f"{profile_id}.strict_dominates"))
    if profile_id in dominates or not dominates <= profile_ids:
        raise TemplatePackError(f"{profile_id}: strict dominance references an invalid profile")
    fragment = profile.get("fragment")
    if not isinstance(fragment, Mapping) or set(fragment) != {"lead", "gap", "action"}:
        raise TemplatePackError(f"{profile_id}: fragment must contain lead, gap, and action")


def _assert_acyclic_dominance(profiles: Mapping[str, Mapping[str, Any]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(profile_id: str) -> None:
        if profile_id in visiting:
            raise TemplatePackError("strict dominance graph contains a cycle")
        if profile_id in visited:
            return
        visiting.add(profile_id)
        for target in profiles[profile_id].get("strict_dominates", []):
            visit(str(target))
        visiting.remove(profile_id)
        visited.add(profile_id)

    for profile_id in sorted(profiles):
        visit(profile_id)


def validate_catalog_data(data: Mapping[str, Any]) -> dict[str, Any]:
    catalog = deepcopy(dict(data))
    if catalog.get("schema_id") != CATALOG_SCHEMA_ID:
        raise TemplatePackError("unsupported template catalog schema")
    if catalog.get("guard_family") != GUARD_FAMILY:
        raise TemplatePackError("template catalog has the wrong Guard family")
    if catalog.get("claim_boundary") != CLAIM_BOUNDARY:
        raise TemplatePackError("template catalog claim boundary drifted")
    if catalog.get("native_binding") != NATIVE_BINDING:
        raise TemplatePackError("template catalog native binding drifted")
    profiles_value = catalog.get("profiles")
    if not isinstance(profiles_value, list):
        raise TemplatePackError("catalog profiles must be a list")
    profile_ids = [str(item.get("profile_id", "")) for item in profiles_value if isinstance(item, Mapping)]
    if len(profile_ids) != len(profiles_value) or len(profile_ids) != len(set(profile_ids)):
        raise TemplatePackError("profile ids must be present and unique")
    if set(profile_ids) != EXPECTED_PROFILE_IDS:
        raise TemplatePackError("SourceGuard template profile inventory is incomplete or unexpected")
    if catalog.get("base_profile_id") not in EXPECTED_PROFILE_IDS:
        raise TemplatePackError("base profile does not resolve")
    for profile in profiles_value:
        if profile.get("profile_digest") != _digest(_without(profile, "profile_digest")):
            raise TemplatePackError(f"{profile.get('profile_id', '(unknown)')}: profile digest mismatch")
    if catalog.get("catalog_digest") != _digest(_without(catalog, "catalog_digest")):
        raise TemplatePackError("catalog digest mismatch")
    profiles = {str(item["profile_id"]): item for item in profiles_value}
    for profile in profiles_value:
        _validate_profile(profile, set(profiles))
    for profile_id, profile in profiles.items():
        for other in profile["composition"]["compatible_with"]:
            if profile_id not in set(profiles[other]["composition"]["compatible_with"]):
                raise TemplatePackError(f"compatibility must be mutual: {profile_id}/{other}")
        required = set(profile["selector"]["required_intents"])
        for target in profile["strict_dominates"]:
            target_required = set(profiles[target]["selector"]["required_intents"])
            if not required > target_required:
                raise TemplatePackError(
                    f"{profile_id}: strict dominance requires a strict selector superset of {target}"
                )
    _assert_acyclic_dominance(profiles)
    return catalog


def _normalize_request(request: Mapping[str, Any]) -> dict[str, Any]:
    request_id = str(request.get("request_id", "")).strip()
    if not request_id:
        raise TemplatePackError("request_id is required")
    raw_intents = request.get("intent_tags", [])
    if not isinstance(raw_intents, (list, tuple, set)):
        raise TemplatePackError("intent_tags must be a collection")
    intents = tuple(sorted({str(item).strip().lower() for item in raw_intents if str(item).strip()}))
    subject = str(request.get("subject", "requested subject")).strip() or "requested subject"
    return {
        "request_id": request_id,
        "intent_tags": list(intents),
        "subject": subject,
        "allow_base": bool(request.get("allow_base", False)),
        "allow_composition": bool(request.get("allow_composition", True)),
    }

def _profile_matches(profile: Mapping[str, Any], intents: set[str]) -> bool:
    selector = profile["selector"]
    return set(selector["required_intents"]) <= intents and not (set(selector["excluded_intents"]) & intents)


def select_template_pack(
    request: Mapping[str, Any],
    *,
    catalog: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    current = validate_catalog_data(catalog) if catalog is not None else load_catalog()
    normalized = _normalize_request(request)
    profiles = {item["profile_id"]: item for item in current["profiles"]}
    intents = set(normalized["intent_tags"])
    candidates = tuple(sorted(pid for pid, item in profiles.items() if _profile_matches(item, intents)))
    suppressed_by: dict[str, str] = {}
    for dominant in candidates:
        for target in profiles[dominant]["strict_dominates"]:
            if target in candidates:
                if target in suppressed_by and suppressed_by[target] != dominant:
                    raise TemplatePackError(f"multiple strict-dominance owners for {target}")
                suppressed_by[target] = dominant
    remaining = tuple(pid for pid in candidates if pid not in suppressed_by)

    disposition = ""
    selected: tuple[str, ...] = ()
    conflicts: list[str] = []
    if not remaining:
        if not candidates and normalized["allow_base"]:
            disposition = "base"
            selected = (str(current["base_profile_id"]),)
        elif not candidates:
            disposition = "no_match"
        else:
            disposition = "ambiguous"
            conflicts.append("dominance_removed_all_candidates")
    elif len(remaining) == 1:
        disposition = "selected"
        selected = remaining
    else:
        if not normalized["allow_composition"]:
            conflicts.append("request_disallows_composition")
        for index, left in enumerate(remaining):
            for right in remaining[index + 1 :]:
                left_contract = profiles[left]["composition"]
                right_contract = profiles[right]["composition"]
                if not left_contract["allowed"] or not right_contract["allowed"]:
                    conflicts.append(f"composition_not_allowed:{left}:{right}")
                if right not in left_contract["compatible_with"] or left not in right_contract["compatible_with"]:
                    conflicts.append(f"incompatible:{left}:{right}")
        owners: dict[str, str] = {}
        for profile_id in remaining:
            for field in profiles[profile_id]["owned_fields"]:
                prior = owners.get(field)
                if prior is not None:
                    conflicts.append(f"field_owner_conflict:{field}:{prior}:{profile_id}")
                else:
                    owners[field] = profile_id
        if conflicts:
            disposition = "ambiguous"
        else:
            disposition = "composed"
            selected = remaining

    field_owners = {field: pid for pid in selected for field in profiles[pid]["owned_fields"]}
    selected_profiles = [
        {"profile_id": pid, "profile_digest": profiles[pid]["profile_digest"]} for pid in selected
    ]
    receipt: dict[str, Any] = {
        "schema_id": SELECTION_RECEIPT_SCHEMA_ID,
        "guard_family": GUARD_FAMILY,
        "request": normalized,
        "request_fingerprint": _digest(normalized),
        "catalog_id": current["catalog_id"],
        "catalog_digest": current["catalog_digest"],
        "candidates": list(candidates),
        "suppressed_by": dict(sorted(suppressed_by.items())),
        "remaining_candidates": list(remaining),
        "disposition": disposition,
        "selected_profiles": selected_profiles,
        "field_owners": dict(sorted(field_owners.items())),
        "conflicts": sorted(set(conflicts)),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    receipt["selection_digest"] = _digest(receipt)
    return receipt


def _render(value: Any, subject: str) -> Any:
    if isinstance(value, str):
        return value.replace("{subject}", subject)
    if isinstance(value, list):
        return [_render(item, subject) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _render(item, subject) for key, item in value.items()}
    return deepcopy(value)


def _require_unique(rows: list[Mapping[str, Any]], key: str) -> set[str]:
    ids = [str(row.get(key, "")) for row in rows]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise TemplatePackError(f"{key} values must be non-empty and unique")
    return set(ids)


def _require_target_guard_contract(
    request: Mapping[str, Any],
    *,
    gap_ids: set[str],
    target_unit_ids: set[str],
) -> SourceGuardModelContract:
    raw_contract = request.get("guard_contract")
    if not isinstance(raw_contract, Mapping):
        raise TemplatePackError(
            "target-authored guard_contract is required before template candidate construction"
        )
    try:
        contract = SourceGuardModelContract.from_dict(deepcopy(dict(raw_contract)))
    except (TypeError, ValueError) as exc:
        raise TemplatePackError(f"target-authored guard_contract is invalid: {exc}") from exc
    if contract.model_id != str(request.get("request_id", "")).strip():
        raise TemplatePackError("guard_contract model_id must equal request_id")
    if contract.claim_boundary != CLAIM_BOUNDARY:
        raise TemplatePackError("guard_contract claim boundary must equal the template boundary")
    if contract.external_universe.get("gap_ids", []) != sorted(gap_ids):
        raise TemplatePackError("guard_contract gap universe does not match selected templates")
    if contract.external_universe.get("target_unit_ids", []) != sorted(target_unit_ids):
        raise TemplatePackError("guard_contract target-unit universe does not match selected templates")
    return contract


def validate_native_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    try:
        model = BeliefState.from_dict(deepcopy(dict(payload)))
    except (TypeError, ValueError) as exc:
        raise TemplatePackError(f"native SourceGuard schema validation failed: {exc}") from exc
    if model.metadata.get("boundary") != CLAIM_BOUNDARY:
        raise TemplatePackError("generated SourceGuard claim boundary drifted")
    lead_ids = _require_unique(list(payload.get("leads", [])), "lead_id")
    gap_ids = _require_unique(list(payload.get("gaps", [])), "gap_id")
    action_ids = _require_unique(list(payload.get("actions", [])), "action_id")
    for lead in payload.get("leads", []):
        missing = set(lead.get("gaps", [])) - gap_ids
        if missing:
            raise TemplatePackError(f"lead references missing gaps: {sorted(missing)}")
    for gap in payload.get("gaps", []):
        if gap.get("lead_id") and gap["lead_id"] not in lead_ids:
            raise TemplatePackError(f"gap references missing lead: {gap['lead_id']}")
    for action in payload.get("actions", []):
        if action.get("target_lead_id") and action["target_lead_id"] not in lead_ids:
            raise TemplatePackError(f"action references missing lead: {action['target_lead_id']}")
        if action.get("target_gap_id") and action["target_gap_id"] not in gap_ids:
            raise TemplatePackError(f"action references missing gap: {action['target_gap_id']}")
    return {
        "ok": True,
        "validator_id": NATIVE_BINDING["validator_id"],
        "schema_owner_id": NATIVE_BINDING["schema_owner_id"],
        "lead_count": len(lead_ids),
        "gap_count": len(gap_ids),
        "action_count": len(action_ids),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_template_instance(
    request: Mapping[str, Any],
    *,
    catalog: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    current = validate_catalog_data(catalog) if catalog is not None else load_catalog()
    selection = select_template_pack(request, catalog=current)
    if selection["disposition"] not in {"base", "selected", "composed"}:
        return {"selection_receipt": selection, "model": None, "instance_receipt": None}
    profiles = {item["profile_id"]: item for item in current["profiles"]}
    subject = selection["request"]["subject"]
    leads: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    for selected in selection["selected_profiles"]:
        fragment = _render(profiles[selected["profile_id"]]["fragment"], subject)
        leads.append(fragment["lead"])
        gaps.append(fragment["gap"])
        actions.append(fragment["action"])
    gap_ids = {str(item["gap_id"]) for item in gaps}
    target_unit_ids = {
        str(item["structure_unit_id"])
        for item in gaps
        if str(item.get("structure_unit_id", "")).strip()
    }
    contract = _require_target_guard_contract(
        request,
        gap_ids=gap_ids,
        target_unit_ids=target_unit_ids,
    )
    payload: dict[str, Any] = {
        "guard_contract": contract.to_dict(),
        "candidate_contract_fingerprint": sourceguard_model_contract_fingerprint(contract),
        "metadata": {
            "purpose": f"SourceGuard template-pack plan for {subject}",
            "repository": "https://github.com/liuyingxuvka/ResearchGuard",
            "skill": "SourceGuard",
            "math_boundary": "POMDP-inspired approximate planner; utility ranks source discovery value, not truth.",
            "cli": "researchguard source validate <model.yaml>",
            "boundary": CLAIM_BOUNDARY,
            "template_profile_ids": [item["profile_id"] for item in selection["selected_profiles"]],
            "template_catalog_digest": current["catalog_digest"],
            "template_selection_digest": selection["selection_digest"],
        },
        "leads": leads,
        "sources": [],
        "anchors": [],
        "gaps": gaps,
        "actions": actions,
        "observations": [],
        "graph_edges": [],
        "weights": {},
    }
    native_validation = validate_native_payload(payload)
    receipt: dict[str, Any] = {
        "schema_id": INSTANCE_RECEIPT_SCHEMA_ID,
        "guard_family": GUARD_FAMILY,
        "selection_digest": selection["selection_digest"],
        "catalog_digest": current["catalog_digest"],
        "selected_profile_digests": [item["profile_digest"] for item in selection["selected_profiles"]],
        "payload_digest": _digest(payload),
        "native_binding": deepcopy(NATIVE_BINDING),
        "native_validation": native_validation,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    receipt["instance_digest"] = _digest(receipt)
    return {"selection_receipt": selection, "model": payload, "instance_receipt": receipt}


def verify_template_instance(
    bundle: Mapping[str, Any],
    *,
    catalog: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    current = validate_catalog_data(catalog) if catalog is not None else load_catalog()
    selection = deepcopy(bundle.get("selection_receipt"))
    payload = deepcopy(bundle.get("model"))
    instance = deepcopy(bundle.get("instance_receipt"))
    if not isinstance(selection, dict) or not isinstance(payload, dict) or not isinstance(instance, dict):
        raise TemplatePackError("complete selection, model, and instance receipts are required")
    if selection.get("selection_digest") != _digest(_without(selection, "selection_digest")):
        raise TemplatePackError("selection receipt digest mismatch")
    if selection.get("catalog_digest") != current["catalog_digest"]:
        raise TemplatePackError("selection receipt catalog is stale")
    if instance.get("payload_digest") != _digest(payload):
        raise TemplatePackError("instance payload digest mismatch")
    if instance.get("selection_digest") != selection["selection_digest"]:
        raise TemplatePackError("instance selection binding mismatch")
    validate_native_payload(payload)
    if instance.get("instance_digest") != _digest(_without(instance, "instance_digest")):
        raise TemplatePackError("instance receipt digest mismatch")
    return {
        "ok": True,
        "selection_digest": selection["selection_digest"],
        "instance_digest": instance["instance_digest"],
        "claim_boundary": CLAIM_BOUNDARY,
    }
