"""SourceGuard-owned native replay for opaque composition attestations."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Iterable, Mapping

from .blueprint import InformationTargetUniverse, check_blueprint
from .schema import BeliefState
from ..model_envelope import (
    MemberBehaviorManifest,
    MemberModelEnvelope,
    NativeOwnerAttestation,
    _compare_native_domain_transition,
    _issue_replayed_native_owner_attestation,
    build_behavior_transition_case,
    build_member_behavior_manifest as _build_member_behavior_manifest,
)
from ..native_receipts import resolve_native_receipt_reference


NATIVE_OWNER_REPLAY_SCHEMA = "researchguard.source.native-owner-replay.v1"
NATIVE_OWNER_ID = "sourceguard"
NATIVE_CHECKER_ID = "researchguard.source.blueprint-check"
NATIVE_CHECKER_VERSION = "1"
EXTERNAL_OBJECT_CHECKER_VERSION = "2"
_EXTERNAL_NATIVE_CONTEXT_FIELDS = {
    "member_id", "status", "qualification_level", "blueprint_replay",
    "binding", "portable_result_fingerprint",
}


def _digest(value: object) -> str:
    body = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _canonical(value: object) -> object:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _exact_mapping(value: object, keys: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError(f"SourceGuard {label} is not exact-current")
    return value


def _require_external_native_replay(
    model: Mapping[str, object], context: Mapping[str, object]
) -> dict[str, object]:
    replay = _exact_mapping(
        context.get("native_member_replay"),
        _EXTERNAL_NATIVE_CONTEXT_FIELDS,
        "external-object native replay",
    )
    binding = model.get("native_binding")
    if (
        replay["member_id"] != NATIVE_OWNER_ID
        or replay["status"] != "passed"
        or replay["blueprint_replay"] != "passed"
        or not isinstance(binding, Mapping)
        or _canonical(binding) != _canonical(replay["binding"])
    ):
        raise ValueError(
            "SourceGuard external projection requires its exact replayed native blueprint"
        )
    return {
        "member_id": NATIVE_OWNER_ID,
        "blueprint_replay": "passed",
        "binding": _canonical(binding),
        "portable_result_fingerprint": str(replay["portable_result_fingerprint"]),
    }


def _locator_contains(container: str, locator: str) -> bool:
    if container.replace("\\", "/") == locator.replace("\\", "/"):
        return True
    outer = re.fullmatch(r"(.+):(\d+)-(\d+)", container.replace("\\", "/"))
    inner = re.fullmatch(r"(.+):(\d+)", locator.replace("\\", "/"))
    return bool(
        outer
        and inner
        and outer.group(1) == inner.group(1)
        and int(outer.group(2)) <= int(inner.group(2)) <= int(outer.group(3))
    )


def evaluate_external_object_transition(
    model: Mapping[str, object], context: Mapping[str, object]
) -> dict[str, object]:
    """Replay one generic external-object source transition at SourceGuard.

    ResearchGuard owns only the parent topology.  Source role, coverage and
    anchor extraction stay here at the current SourceGuard owner.
    """

    native_blueprint = _require_external_native_replay(model, context)
    request = _exact_mapping(
        model.get("input"),
        {"target_id", "source_roles", "extraction_requests", "variance_gap_id"},
        "external-object input",
    )
    target = context.get("target")
    if (
        not isinstance(target, Mapping)
        or not isinstance(target.get("artifacts"), list)
        or not isinstance(target.get("source_authorities"), list)
    ):
        raise ValueError("SourceGuard external-object target inventory is unavailable")
    if str(request["target_id"]) != str(target.get("target_id", "")):
        raise ValueError("SourceGuard external-object request names another target")
    roles = request["source_roles"]
    rows = request["extraction_requests"]
    if not isinstance(roles, list) or not roles or not isinstance(rows, list) or not rows:
        raise ValueError("SourceGuard external-object roles and extractions are required")
    authority_rows = target["source_authorities"]
    if _canonical(roles) != _canonical(authority_rows):
        raise ValueError(
            "SourceGuard external-object roles differ from target source authorities"
        )
    source_authorities: dict[str, Mapping[str, object]] = {}
    consumed_authority_ids: set[str] = set()
    for raw_authority in authority_rows:
        authority = _exact_mapping(
            raw_authority,
            {"source_id", "role", "coverage_ids"},
            "external-object source authority",
        )
        source_id = str(authority["source_id"])
        coverage_ids = authority["coverage_ids"]
        if (
            not source_id
            or source_id in source_authorities
            or not str(authority["role"]).strip()
            or not isinstance(coverage_ids, list)
            or not coverage_ids
            or any(not str(item).strip() for item in coverage_ids)
            or len({str(item) for item in coverage_ids}) != len(coverage_ids)
        ):
            raise ValueError("SourceGuard target source authority is invalid")
        source_authorities[source_id] = authority
        consumed_authority_ids.update(str(item) for item in coverage_ids)
    expected_coverage = {
        str(target.get("target_id", "")),
        *(
            str(item.get("artifact_id", ""))
            for item in target["artifacts"]
            if isinstance(item, Mapping)
        ),
        *(
            str(item.get("node_id", ""))
            for item in context.get("structure_nodes", [])
            if isinstance(item, Mapping)
        ),
    }
    if consumed_authority_ids != expected_coverage:
        raise ValueError(
            "SourceGuard source authority does not close the target material and structure denominator"
        )
    artifacts = {
        str(item.get("artifact_id", "")): item
        for item in target["artifacts"]
        if isinstance(item, Mapping)
    }
    structure_rows = context.get("structure_nodes")
    if not isinstance(structure_rows, list):
        raise ValueError("SourceGuard external-object structure inventory is unavailable")
    structures = {
        str(item.get("node_id", "")): item
        for item in structure_rows
        if isinstance(item, Mapping)
    }
    material_root = context.get("material_root")
    root = material_root if isinstance(material_root, Path) else None
    anchors: list[dict[str, object]] = []
    evidence: list[dict[str, object]] = []
    values_by_claim: dict[str, set[str]] = {}
    for raw in rows:
        row = _exact_mapping(
            raw,
            {
                "anchor_id", "claim_id", "source_id", "role", "artifact_id", "selector",
                "expected_value", "structure_node_id", "expected_structure_kind",
            },
            "external-object extraction request",
        )
        selector = _exact_mapping(
            row["selector"],
            {"selector_kind", "occurrence_id", "locator", "fingerprint", "parameters"},
            "external-object extraction selector",
        )
        selector_kind = str(selector["selector_kind"])
        occurrence_id = str(selector["occurrence_id"])
        locator = str(selector["locator"])
        selector_fingerprint = str(selector["fingerprint"])
        parameters = selector["parameters"]
        if (
            not occurrence_id
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", selector_fingerprint)
            or not isinstance(parameters, Mapping)
        ):
            raise ValueError("SourceGuard extraction selector identity is invalid")
        artifact_id = str(row["artifact_id"])
        if str(row["source_id"]) not in source_authorities:
            raise ValueError(
                "SourceGuard extraction source id is outside target source authorities"
            )
        artifact = artifacts.get(artifact_id)
        if artifact is None:
            raise ValueError(f"SourceGuard extraction names unknown artifact {artifact_id}")
        structure = structures.get(str(row["structure_node_id"]))
        if (
            structure is None
            or str(structure.get("kind", "")) != str(row["expected_structure_kind"])
            or str(row["anchor_id"]) not in set(structure.get("bound_object_ids", []))
            or artifact_id not in set(structure.get("artifact_ids", []))
            or not _locator_contains(str(structure.get("locator", "")), locator)
        ):
            raise ValueError(
                "SourceGuard extraction is rebound from its declared structure role"
            )
        expected_value = str(row["expected_value"])
        if not str(row["role"]).strip():
            raise ValueError("SourceGuard extraction semantic role is required")
        candidate = None
        if root is not None:
            candidate = (root / str(artifact["relative_path"])).resolve()
            if candidate != root and root not in candidate.parents:
                raise ValueError("SourceGuard extraction path escapes material root")
        if selector_kind == "line_pattern":
            if set(parameters) != {"line_number", "value_pattern", "value_group"}:
                raise ValueError("SourceGuard line selector parameters are not exact-current")
            line_number = parameters["line_number"]
            if not isinstance(line_number, int) or line_number < 1:
                raise ValueError("SourceGuard extraction line number is invalid")
            expected_locator = f"{artifact['relative_path']}:{line_number}".replace("\\", "/")
            if locator.replace("\\", "/") != expected_locator:
                raise ValueError("SourceGuard extraction locator does not bind artifact and line")
            if root is not None and candidate is not None:
                try:
                    line = candidate.read_text(encoding="utf-8").splitlines()[line_number - 1]
                except (OSError, IndexError, UnicodeError) as exc:
                    raise ValueError("SourceGuard extraction source line is unavailable") from exc
                actual_fingerprint = "sha256:" + hashlib.sha256(line.encode("utf-8")).hexdigest()
                if actual_fingerprint != selector_fingerprint:
                    raise ValueError("SourceGuard extraction line changed")
                try:
                    match = re.search(str(parameters["value_pattern"]), line)
                    actual_value = match.group(str(parameters["value_group"])) if match else ""
                except (IndexError, re.error) as exc:
                    raise ValueError("SourceGuard extraction pattern is invalid") from exc
                if actual_value != expected_value:
                    raise ValueError("SourceGuard extracted value differs from frozen anchor")
        elif selector_kind == "json_pointer":
            if set(parameters) != {"pointer"}:
                raise ValueError("SourceGuard JSON-pointer selector parameters are not exact-current")
            pointer = str(parameters["pointer"])
            expected_locator = f"{artifact['relative_path']}#{pointer}".replace("\\", "/")
            if not pointer.startswith("/") or locator.replace("\\", "/") != expected_locator:
                raise ValueError("SourceGuard JSON-pointer locator does not bind its artifact")
            if root is not None and candidate is not None:
                try:
                    selected: object = json.loads(candidate.read_text(encoding="utf-8"))
                    for token in pointer.removeprefix("/").split("/"):
                        token = token.replace("~1", "/").replace("~0", "~")
                        if isinstance(selected, list):
                            selected = selected[int(token)]
                        elif isinstance(selected, Mapping):
                            selected = selected[token]
                        else:
                            raise KeyError(token)
                except (OSError, UnicodeError, json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
                    raise ValueError("SourceGuard JSON-pointer occurrence is unavailable") from exc
                selected_body = json.dumps(
                    selected, ensure_ascii=False, separators=(",", ":"), sort_keys=True
                ).encode("utf-8")
                actual_fingerprint = "sha256:" + hashlib.sha256(selected_body).hexdigest()
                if actual_fingerprint != selector_fingerprint:
                    raise ValueError("SourceGuard JSON-pointer occurrence changed")
                actual_value = (
                    selected
                    if isinstance(selected, str)
                    else json.dumps(selected, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
                )
                if str(actual_value) != expected_value:
                    raise ValueError("SourceGuard JSON-pointer value differs from frozen anchor")
        else:
            raise ValueError("SourceGuard extraction selector kind is not current")
        claim_id = str(row["claim_id"])
        values_by_claim.setdefault(claim_id, set()).add(expected_value)
        anchors.append(
            {
                "anchor_id": str(row["anchor_id"]), "claim_id": claim_id,
                "source_id": str(row["source_id"]), "locator": locator,
                "value": expected_value, "status": "located",
            }
        )
        evidence.append(
            {
                "anchor_id": str(row["anchor_id"]), "artifact_id": artifact_id,
                "structure_node_id": str(row["structure_node_id"]),
                "structure_kind": str(row["expected_structure_kind"]),
                "artifact_sha256": str(artifact["sha256"]), "locator": locator,
                "selector_kind": selector_kind,
                "occurrence_id": occurrence_id,
                "selector_fingerprint": selector_fingerprint,
                "value": expected_value,
            }
        )
    variance = {
        claim_id: sorted(values)
        for claim_id, values in values_by_claim.items()
        if len(values) > 1
    }
    gap_id = str(request["variance_gap_id"])
    gaps = (
        [{
            "gap_id": gap_id,
            "code": "inconsistent-primary-source-values",
            "detail": "Frozen anchor values differ: " + "; ".join(
                f"{claim_id}={','.join(values)}" for claim_id, values in sorted(variance.items())
            ),
        }]
        if variance else []
    )
    output = {
        "source_roles": roles,
        "claim_anchors": anchors,
        "unavailable_source_ids": [],
        "gaps": gaps,
    }
    return {
        "output": output,
        "transition_contract": {
            "pre_state": {"source_status": "frozen", "open_gap_ids": []},
            "post_state": {
                "source_status": "qualified_with_variance" if variance else "qualified_consistent",
                "open_gap_ids": [gap_id] if variance else [],
            },
            "effect": [
                "freeze_source_identity",
                "expose_value_variance" if variance else "preserve_consistent_locators",
            ],
            "protected_failure": "inventing source role, coverage, locator, or extracted value",
            "claim_boundary": (
                "SourceGuard identifies declared source roles, coverage, and exact locators; "
                "it does not decide factual truth or undocumented intent."
            ),
        },
        "native_result": {
            "member_native_blueprint": native_blueprint,
            "consumed_upstream_object_ids": sorted(consumed_authority_ids),
            "anchor_evidence": evidence,
            "values_by_claim": {key: sorted(value) for key, value in sorted(values_by_claim.items())},
            "variance_by_claim": variance,
            "material_replay": "verified_when_material_root_supplied",
        },
    }


def build_external_object_bad_case(
    model: Mapping[str, object], context: Mapping[str, object]
) -> tuple[Mapping[str, object], Mapping[str, object]]:
    """Build SourceGuard's target-native protected-failure replay case."""

    bad_model = _canonical(model)
    if not isinstance(bad_model, dict):
        raise ValueError("SourceGuard external-object bad model is invalid")
    request = bad_model.get("input")
    if not isinstance(request, dict):
        raise ValueError("SourceGuard external-object bad input is unavailable")
    extractions = request.get("extraction_requests")
    if not isinstance(extractions, list) or not extractions or not isinstance(extractions[0], dict):
        raise ValueError("SourceGuard external-object bad extraction is unavailable")
    extractions[0]["source_id"] = "source:foreign-target-authority"
    return bad_model, dict(context)


def _replay_blueprint(material: object) -> tuple[str, dict[str, object]]:
    payload = _exact_mapping(
        material,
        {"belief_state", "target_universe", "contract_path"},
        "native blueprint input",
    )
    if not isinstance(payload["belief_state"], Mapping) or not isinstance(
        payload["target_universe"], Mapping
    ):
        raise ValueError("SourceGuard blueprint state and universe must be objects")
    state = BeliefState.from_dict(dict(payload["belief_state"]))
    universe = InformationTargetUniverse.from_dict(payload["target_universe"])
    contract_path = str(payload["contract_path"])
    result = check_blueprint(state, universe, contract_path=contract_path)
    contract = state.guard_contract
    model_id = f"source-blueprint:{contract.model_id if contract is not None else universe.universe_id}"
    return model_id, _canonical(result.to_dict())  # type: ignore[return-value]


def _expected_anchor(material: object):
    payload = _exact_mapping(
        material,
        {"belief_state", "target_universe", "contract_path"},
        "native blueprint input",
    )
    universe = InformationTargetUniverse.from_dict(payload["target_universe"])
    if universe.target_authority is None:
        raise ValueError("SourceGuard native input has no expected target anchor")
    return universe.target_authority.expected_target_anchor


def _declared_ids(value: object) -> set[str]:
    result: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            name = str(key)
            if (name == "id" or name.endswith("_id")) and isinstance(item, str) and item.strip():
                result.add(item)
            elif name.endswith("_ids") and isinstance(item, list):
                result.update(str(entry) for entry in item if str(entry).strip())
            result.update(_declared_ids(item))
    elif isinstance(value, list):
        for item in value:
            result.update(_declared_ids(item))
    return result


def _named_declared_ids(value: object, markers: tuple[str, ...]) -> set[str]:
    result: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if any(marker in str(key).lower() for marker in markers):
                result.update(_declared_ids(item))
            result.update(_named_declared_ids(item, markers))
    elif isinstance(value, list):
        for item in value:
            result.update(_named_declared_ids(item, markers))
    return result


def build_native_behavior_manifest(
    *,
    native_model_id: str,
    model_fingerprint: str,
    native_input_material: object,
    replayed_result: Mapping[str, object],
    native_receipt_ids: Iterable[str],
    result_fingerprint: str,
    terminal_status: str,
) -> MemberBehaviorManifest:
    """Derive SourceGuard's current behavior denominator from native objects."""

    payload = _exact_mapping(
        native_input_material,
        {"belief_state", "target_universe", "contract_path"},
        "native blueprint input",
    )
    anchor = _expected_anchor(payload)
    hierarchy = {
        native_model_id,
        *_declared_ids(payload["belief_state"]),
        *_declared_ids(payload["target_universe"]),
        *_declared_ids(replayed_result),
    }
    interfaces = {
        "sourceguard.interface:belief-state-to-blueprint-result",
        *_named_declared_ids(payload, ("interface", "binding")),
    }
    targets = {anchor.anchor_id, *_declared_ids(payload["target_universe"])}
    receipt_ids = tuple(sorted(set(str(item) for item in native_receipt_ids)))
    if not receipt_ids:
        raise ValueError("SourceGuard domain behavior manifest requires a native receipt")
    common = {
        "owner": NATIVE_OWNER_ID,
        "checker_entrypoint": f"{__name__}:evaluate_domain_behavior_transition",
        "checker_id": NATIVE_CHECKER_ID,
        "checker_version": NATIVE_CHECKER_VERSION,
        "result_fingerprint": result_fingerprint,
        "native_receipt_id": receipt_ids[0],
    }
    universe = payload["target_universe"]
    belief = payload["belief_state"]
    if not isinstance(universe, Mapping) or not isinstance(belief, Mapping):
        raise ValueError("SourceGuard domain behavior inputs are not objects")
    purpose_receipt = universe.get("native_purpose_receipt")
    failure_rows = (
        purpose_receipt.get("failure_results", [])
        if isinstance(purpose_receipt, Mapping)
        else []
    )
    if not isinstance(failure_rows, list) or not failure_rows or not isinstance(failure_rows[0], Mapping):
        raise ValueError("SourceGuard domain behavior has no native good/bad evidence")
    failure = failure_rows[0]
    good_evidence = failure.get("known_good")
    bad_evidence = failure.get("known_bad")
    if not isinstance(good_evidence, Mapping) or not isinstance(bad_evidence, Mapping):
        raise ValueError("SourceGuard native good/bad evidence is invalid")
    source_rows = belief.get("sources", [])
    anchor_rows = belief.get("anchors", [])
    gap_rows = belief.get("gaps", [])
    domain_cases = (
        build_behavior_transition_case(
            case_id="case:sourceguard.information-blueprint-qualification",
            behavior_id="sourceguard.information-blueprint-qualification",
            input={
                "required_target_unit_ids": list(universe.get("required_target_unit_ids", [])),
                "required_source_role_ids": list(universe.get("required_source_role_ids", [])),
                "required_lineage_slot_ids": list(universe.get("required_lineage_slot_ids", [])),
                "required_anchor_requirement_ids": list(universe.get("required_anchor_requirement_ids", [])),
                "source_ids": sorted(
                    str(item.get("source_id", ""))
                    for item in source_rows
                    if isinstance(item, Mapping)
                ),
                "anchor_ids": sorted(
                    str(item.get("anchor_id", ""))
                    for item in anchor_rows
                    if isinstance(item, Mapping)
                ),
            },
            pre_state={
                "open_gap_ids": sorted(
                    str(item.get("gap_id", ""))
                    for item in gap_rows
                    if isinstance(item, Mapping)
                ),
                "layer_statuses": [],
            },
            permitted_output={
                "source_roles_by_source_id": {
                    str(item.get("source_id", "")): str(item.get("source_role", ""))
                    for item in source_rows
                    if isinstance(item, Mapping)
                },
                "qualified_anchor_ids": sorted(
                    str(item.get("anchor_id", ""))
                    for item in anchor_rows
                    if isinstance(item, Mapping)
                    and (item.get("usable_for_claim") or item.get("usable_for_trace"))
                ),
                "native_open_gap_ids": list(replayed_result.get("native_open_gap_ids", [])),
                "unconsumed_candidate_ids": list(replayed_result.get("unconsumed_candidate_ids", [])),
                "layer_statuses": list(replayed_result.get("layer_statuses", [])),
            },
            post_state={
                "deepest_proven_layer": str(replayed_result.get("deepest_proven_layer", "")),
                "first_unresolved_gap": str(replayed_result.get("first_unresolved_gap", "")),
                "claim_boundary": str(replayed_result.get("claim_boundary", "")),
            },
            effect=(
                "qualify_source_roles_lineage_and_anchors",
                "close_only_declared_information_targets",
                "preserve_open_information_gaps",
            ),
            protected_failure=str(bad_evidence.get("native_finding", "source-blueprint-native-failure")),
            bad_mutation_path="permitted_output.qualified_anchor_ids",
            failure_class_id=str(failure.get("failure_id", "source-blueprint-native-failure")),
            good_native_evidence={
                "case_id": str(next(iter(universe.get("known_good_case_ids", ["known-good"])), "known-good")),
                "oracle_id": str(failure.get("oracle_id", "")),
                "proof_receipt_fingerprint": str(
                    purpose_receipt.get("receipt_fingerprint", "")
                    if isinstance(purpose_receipt, Mapping)
                    else ""
                ),
                **dict(good_evidence),
            },
            bad_native_evidence={
                "case_id": str(next(iter(universe.get("known_bad_case_ids", ["known-bad"])), "known-bad")),
                "oracle_id": str(failure.get("oracle_id", "")),
                "proof_receipt_fingerprint": str(
                    purpose_receipt.get("receipt_fingerprint", "")
                    if isinstance(purpose_receipt, Mapping)
                    else ""
                ),
                **dict(bad_evidence),
            },
            **common,
        ),
    )
    return _build_member_behavior_manifest(
        member_id=NATIVE_OWNER_ID,
        native_model_id=native_model_id,
        model_fingerprint=model_fingerprint,
        expected_target_anchor_id=anchor.anchor_id,
        expected_target_anchor_fingerprint=anchor.anchor_fingerprint,
        hierarchy_node_ids=hierarchy,
        interface_binding_ids=interfaces,
        target_binding_ids=targets,
        native_receipt_ids=receipt_ids,
        domain_behavior_cases=domain_cases,
        checker_id=NATIVE_CHECKER_ID,
        checker_version=NATIVE_CHECKER_VERSION,
        checker_entrypoint=f"{__name__}:replay_native_owner_attestation",
        result_fingerprint=result_fingerprint,
        terminal_status=terminal_status,
    )


def evaluate_domain_behavior_transition(
    envelope: MemberModelEnvelope,
    behavior_id: str,
    candidate_transition: Mapping[str, object],
) -> dict[str, str]:
    """Rerun SourceGuard and compare one information behavior projection."""

    if envelope.member_id != NATIVE_OWNER_ID or envelope.opaque_payload is None:
        raise ValueError("SourceGuard domain evaluation requires its opaque payload")
    raw = _exact_mapping(
        json.loads(envelope.opaque_payload.decode("utf-8")),
        {"schema_version", "discovery_request", "information_input", "qualification_result"},
        "native-owner replay material",
    )
    native_input = _exact_mapping(
        raw["information_input"],
        {"native_model_id", "model_fingerprint", "input_id", "material"},
        "replay input",
    )
    derived_model_id, replayed = _replay_blueprint(native_input["material"])
    terminal = "passed" if replayed.get("status") == "complete" else "blocked"
    expected_result = {
        "checker_id": NATIVE_CHECKER_ID,
        "checker_version": NATIVE_CHECKER_VERSION,
        "model_fingerprint": str(replayed.get("model_fingerprint", "")),
        "terminal_status": terminal,
        "native_receipt_ids": [item.receipt_id for item in envelope.native_receipt_refs],
        "material": replayed,
    }
    canonical_manifest = build_native_behavior_manifest(
        native_model_id=derived_model_id,
        model_fingerprint=str(replayed.get("model_fingerprint", "")),
        native_input_material=native_input["material"],
        replayed_result=replayed,
        native_receipt_ids=(item.receipt_id for item in envelope.native_receipt_refs),
        result_fingerprint=_digest(expected_result),
        terminal_status=terminal,
    )
    if canonical_manifest.to_dict() != envelope.behavior_manifest.to_dict():
        raise ValueError("SourceGuard behavior manifest differs from native replay")
    canonical = next(
        (item for item in canonical_manifest.domain_behavior_cases if item.behavior_id == behavior_id),
        None,
    )
    if canonical is None:
        raise ValueError("SourceGuard domain behavior id is outside the denominator")
    return _compare_native_domain_transition(canonical, candidate_transition)


def replay_native_owner_attestation(
    envelope: MemberModelEnvelope, *, registry_identity: str
) -> NativeOwnerAttestation:
    if envelope.member_id != NATIVE_OWNER_ID or envelope.opaque_payload is None:
        raise ValueError("SourceGuard native-owner replay requires its opaque payload")
    from ..routing import native_owner_registry_identity

    if registry_identity != native_owner_registry_identity(NATIVE_OWNER_ID):
        raise ValueError("SourceGuard native-owner registry identity is stale or foreign")
    raw = _exact_mapping(
        json.loads(envelope.opaque_payload.decode("utf-8")),
        {"schema_version", "discovery_request", "information_input", "qualification_result"},
        "native-owner replay material",
    )
    if raw["schema_version"] != NATIVE_OWNER_REPLAY_SCHEMA:
        raise ValueError("SourceGuard native-owner replay schema is not current")
    request = _exact_mapping(
        raw["discovery_request"],
        {"task_id", "operation", "claim_boundary", "material"},
        "replay request",
    )
    native_input = _exact_mapping(
        raw["information_input"],
        {"native_model_id", "model_fingerprint", "input_id", "material"},
        "replay input",
    )
    submitted_result = _exact_mapping(
        raw["qualification_result"],
        {"checker_id", "checker_version", "model_fingerprint", "terminal_status", "native_receipt_ids", "material"},
        "replay result",
    )
    request_material = _exact_mapping(
        request["material"],
        {
            "member_id", "checker_id", "checker_version", "registry_identity",
            "expected_target_anchor_id", "expected_target_anchor_fingerprint",
            "behavior_manifest_fingerprint",
        },
        "request material",
    )
    anchor = _expected_anchor(native_input["material"])

    derived_model_id, replayed_result = _replay_blueprint(native_input["material"])
    derived_terminal = "passed" if replayed_result.get("status") == "complete" else "blocked"
    derived_model_fingerprint = str(replayed_result.get("model_fingerprint", ""))
    derived_gap_refs = tuple(
        sorted(
            f"{item.get('code', '')}:{item.get('object_id', '')}"
            for item in replayed_result.get("gaps", [])
            if isinstance(item, Mapping)
        )
    )
    expected_result = {
        "checker_id": NATIVE_CHECKER_ID,
        "checker_version": NATIVE_CHECKER_VERSION,
        "model_fingerprint": derived_model_fingerprint,
        "terminal_status": derived_terminal,
        "native_receipt_ids": [item.receipt_id for item in envelope.native_receipt_refs],
        "material": replayed_result,
    }
    if (
        request["task_id"] != envelope.task_id
        or request["operation"] != "blueprint-check"
        or request["claim_boundary"] != envelope.claim_boundary
        or native_input["native_model_id"] != derived_model_id
        or native_input["native_model_id"] != envelope.native_model_id
        or native_input["model_fingerprint"] != derived_model_fingerprint
        or native_input["model_fingerprint"] != envelope.model_fingerprint
        or native_input["input_id"] != f"sourceguard-input:{_digest(native_input['material'])}"
        or envelope.expected_target_anchor_id != anchor.anchor_id
        or envelope.expected_target_anchor_fingerprint != anchor.anchor_fingerprint
        or dict(submitted_result) != expected_result
        or envelope.terminal_status != derived_terminal
        or tuple(sorted(envelope.open_gap_refs)) != (() if derived_terminal == "passed" else derived_gap_refs)
    ):
        raise ValueError("SourceGuard replay differs from the current native blueprint execution")

    result_fingerprint = _digest(expected_result)
    manifest = build_native_behavior_manifest(
        native_model_id=derived_model_id,
        model_fingerprint=derived_model_fingerprint,
        native_input_material=native_input["material"],
        replayed_result=replayed_result,
        native_receipt_ids=(item.receipt_id for item in envelope.native_receipt_refs),
        result_fingerprint=result_fingerprint,
        terminal_status=derived_terminal,
    )
    if request_material != {
        "member_id": NATIVE_OWNER_ID,
        "checker_id": NATIVE_CHECKER_ID,
        "checker_version": NATIVE_CHECKER_VERSION,
        "registry_identity": registry_identity,
        "expected_target_anchor_id": anchor.anchor_id,
        "expected_target_anchor_fingerprint": anchor.anchor_fingerprint,
        "behavior_manifest_fingerprint": manifest.expected_fingerprint,
    } or envelope.behavior_manifest.to_dict() != manifest.to_dict():
        raise ValueError("SourceGuard request does not bind its current behavior manifest")
    request_fingerprint = _digest(dict(request))
    input_fingerprint = _digest(dict(native_input))
    for receipt in envelope.native_receipt_refs:
        gaps = resolve_native_receipt_reference(receipt)
        if gaps or any((
            receipt.member_id != NATIVE_OWNER_ID,
            receipt.native_owner_id != NATIVE_OWNER_ID,
            receipt.checker_id != NATIVE_CHECKER_ID,
            receipt.checker_version != NATIVE_CHECKER_VERSION,
            receipt.checker_entrypoint != f"{__name__}:replay_native_owner_attestation",
            receipt.task_id != envelope.task_id,
            receipt.expected_target_anchor_id != anchor.anchor_id,
            receipt.expected_target_anchor_fingerprint != anchor.anchor_fingerprint,
            receipt.native_model_id != envelope.native_model_id,
            receipt.model_fingerprint != envelope.model_fingerprint,
            receipt.request_fingerprint != request_fingerprint,
            receipt.input_fingerprint != input_fingerprint,
            receipt.result_fingerprint != result_fingerprint,
            receipt.behavior_manifest_fingerprint != manifest.expected_fingerprint,
            receipt.status != derived_terminal,
        )):
            raise ValueError("SourceGuard native receipt does not replay exactly")
    return _issue_replayed_native_owner_attestation(
        envelope,
        native_owner_id=NATIVE_OWNER_ID,
        checker_id=NATIVE_CHECKER_ID,
        checker_version=NATIVE_CHECKER_VERSION,
        registry_identity=registry_identity,
        request_fingerprint=request_fingerprint,
        input_fingerprint=input_fingerprint,
        result_fingerprint=result_fingerprint,
    )


__all__ = [
    "build_external_object_bad_case",
    "build_native_behavior_manifest",
    "evaluate_domain_behavior_transition",
    "evaluate_external_object_transition",
    "replay_native_owner_attestation",
]
