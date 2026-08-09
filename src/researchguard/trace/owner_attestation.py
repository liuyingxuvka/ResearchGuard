"""TraceGuard-owned native replay for opaque composition attestations."""

from __future__ import annotations

import hashlib
import json
from typing import Iterable, Mapping

from .blueprint import TraceTargetUniverse, check_blueprint
from .evaluator import evaluate_model
from .schema import TraceGuardModel
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


NATIVE_OWNER_REPLAY_SCHEMA = "researchguard.trace.native-owner-replay.v1"
NATIVE_OWNER_ID = "traceguard"
NATIVE_CHECKER_ID = "researchguard.trace.blueprint-check"
NATIVE_CHECKER_VERSION = "1"
EXTERNAL_OBJECT_CHECKER_VERSION = "1"
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
        raise ValueError(f"TraceGuard {label} is not exact-current")
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
            "TraceGuard external projection requires its exact replayed native blueprint"
        )
    return {
        "member_id": NATIVE_OWNER_ID,
        "blueprint_replay": "passed",
        "binding": _canonical(binding),
        "portable_result_fingerprint": str(replay["portable_result_fingerprint"]),
    }


def evaluate_external_object_transition(
    model: Mapping[str, object], context: Mapping[str, object]
) -> dict[str, object]:
    """Replay external-object ordering through the TraceGuard native owner."""

    native_blueprint = _require_external_native_replay(model, context)
    request = _exact_mapping(
        model.get("input"),
        {"event_specs", "storyline_id", "uncertainty_gap_id"},
        "external-object input",
    )
    outputs = context.get("member_outputs")
    source = outputs.get("sourceguard") if isinstance(outputs, Mapping) else None
    if not isinstance(source, Mapping):
        raise ValueError("TraceGuard external-object replay requires SourceGuard output")
    target = context.get("target")
    if not isinstance(target, Mapping) or not isinstance(
        target.get("source_authorities"), list
    ):
        raise ValueError("TraceGuard external-object target authority is unavailable")
    source_roles = source.get("source_roles")
    if (
        not isinstance(source_roles, list)
        or _canonical(source_roles) != _canonical(target["source_authorities"])
    ):
        raise ValueError(
            "TraceGuard SourceGuard roles differ from target source authorities"
        )
    source_ids: set[str] = set()
    consumed_upstream_ids: set[str] = set()
    for raw_role in source_roles:
        role = _exact_mapping(
            raw_role,
            {"source_id", "role", "coverage_ids"},
            "SourceGuard source role",
        )
        source_id = str(role["source_id"])
        coverage_ids = role["coverage_ids"]
        if (
            not source_id
            or source_id in source_ids
            or not str(role["role"]).strip()
            or not isinstance(coverage_ids, list)
            or not coverage_ids
        ):
            raise ValueError("TraceGuard SourceGuard source role is invalid")
        source_ids.add(source_id)
        consumed_upstream_ids.add(source_id)
    anchor_rows = source.get("claim_anchors")
    if not isinstance(anchor_rows, list):
        raise ValueError("TraceGuard external-object replay has no source anchors")
    anchors: dict[str, Mapping[str, object]] = {}
    for raw_anchor in anchor_rows:
        anchor = _exact_mapping(
            raw_anchor,
            {"anchor_id", "claim_id", "source_id", "locator", "value", "status"},
            "SourceGuard claim anchor",
        )
        anchor_id = str(anchor["anchor_id"])
        if (
            not anchor_id
            or anchor_id in anchors
            or str(anchor["source_id"]) not in source_ids
            or anchor["status"] != "located"
            or any(
                not str(anchor[field]).strip()
                for field in ("claim_id", "locator", "value")
            )
        ):
            raise ValueError("TraceGuard SourceGuard claim anchor is invalid")
        anchors[anchor_id] = anchor
        consumed_upstream_ids.add(anchor_id)
    source_gaps = source.get("gaps")
    if not isinstance(source_gaps, list):
        raise ValueError("TraceGuard SourceGuard gap denominator is unavailable")
    source_gap_ids: set[str] = set()
    for raw_gap in source_gaps:
        gap = _exact_mapping(
            raw_gap, {"gap_id", "code", "detail"}, "SourceGuard gap"
        )
        gap_id = str(gap["gap_id"])
        if (
            not gap_id
            or gap_id in source_gap_ids
            or not str(gap["code"]).strip()
            or not str(gap["detail"]).strip()
        ):
            raise ValueError("TraceGuard SourceGuard gap is invalid")
        source_gap_ids.add(gap_id)
        consumed_upstream_ids.add(gap_id)
    unavailable_source_ids = source.get("unavailable_source_ids")
    if not isinstance(unavailable_source_ids, list) or unavailable_source_ids:
        raise ValueError(
            "TraceGuard current external-object path requires all admitted SourceGuard sources"
        )
    specs = request["event_specs"]
    if not isinstance(specs, list) or not specs:
        raise ValueError("TraceGuard external-object event denominator is empty")
    events: list[dict[str, object]] = []
    for index, raw in enumerate(specs):
        spec = _exact_mapping(raw, {"event_id", "anchor_id", "stage"}, "external-object event")
        anchor = anchors.get(str(spec["anchor_id"]))
        if anchor is None:
            raise ValueError("TraceGuard event references an unknown SourceGuard anchor")
        events.append({
            "event_id": str(spec["event_id"]),
            "stage": str(spec["stage"]),
            "predecessor_ids": [] if index == 0 else [str(specs[index - 1]["event_id"])],
            "evidence_ids": [str(spec["anchor_id"])],
            "output_ids": [f"observed-value:{anchor['value']}"],
        })
    uncertainty_open = bool(source_gaps)
    gap_id = str(request["uncertainty_gap_id"])
    gaps = ([{
        "gap_id": gap_id,
        "code": "trace-does-not-establish-undocumented-resolution",
        "detail": "The ordered occurrences do not establish an undocumented correction or intent.",
    }] if uncertainty_open else [])
    output = {
        "ordered_events": events,
        "storylines": [{
            "storyline_id": str(request["storyline_id"]),
            "event_ids": [str(item["event_id"]) for item in events],
            "status": "variance_open" if uncertainty_open else "consistent",
            "unresolved_gap_ids": [gap_id] if uncertainty_open else [],
        }],
        "gaps": gaps,
    }
    return {
        "output": output,
        "transition_contract": {
            "pre_state": {
                "ordered_event_ids": [],
                "open_gap_ids": [
                    str(item.get("gap_id", "")) for item in (source_gaps or [])
                    if isinstance(item, Mapping)
                ],
            },
            "post_state": {
                "storyline_status": "variance_open" if uncertainty_open else "consistent",
                "latest_event_id": str(events[-1]["event_id"]),
            },
            "effect": [
                "order_declared_occurrences",
                "preserve_unresolved_variance" if uncertainty_open else "preserve_consistent_sequence",
            ],
            "protected_failure": "turning chronology into undocumented causality, correction, or intent",
            "claim_boundary": (
                "TraceGuard reconstructs the declared evidence-bound sequence; it does not "
                "infer undocumented causality, correction, or intent."
            ),
        },
        "native_result": {
            "member_native_blueprint": native_blueprint,
            "consumed_upstream_object_ids": sorted(consumed_upstream_ids),
            "source_role_fingerprint": _digest(source_roles),
            "ordered_anchor_ids": [str(item["evidence_ids"][0]) for item in events],
            "uncertainty_open": uncertainty_open,
        },
    }


def build_external_object_bad_case(
    model: Mapping[str, object], context: Mapping[str, object]
) -> tuple[Mapping[str, object], Mapping[str, object]]:
    """Build TraceGuard's target-native protected-failure replay case."""

    bad_context = dict(context)
    outputs = _canonical(context.get("member_outputs"))
    if not isinstance(outputs, dict):
        raise ValueError("TraceGuard external-object bad upstream state is unavailable")
    source = outputs.get("sourceguard")
    if not isinstance(source, dict):
        raise ValueError("TraceGuard external-object bad SourceGuard output is unavailable")
    roles = source.get("source_roles")
    if not isinstance(roles, list) or not roles or not isinstance(roles[0], dict):
        raise ValueError("TraceGuard external-object bad source role is unavailable")
    roles[0]["role"] = "foreign_source_role"
    bad_context["member_outputs"] = outputs
    return model, bad_context


def _replay_blueprint(material: object) -> tuple[str, dict[str, object]]:
    payload = _exact_mapping(
        material,
        {"model", "target_universe", "candidate_path"},
        "native blueprint input",
    )
    if not isinstance(payload["model"], Mapping) or not isinstance(
        payload["target_universe"], Mapping
    ):
        raise ValueError("TraceGuard blueprint model and universe must be objects")
    model = TraceGuardModel.from_dict(dict(payload["model"]))
    universe = TraceTargetUniverse.from_dict(payload["target_universe"])
    receipt = evaluate_model(model, include_storyline_depth=False).inference_receipt
    result = check_blueprint(
        model,
        receipt,
        universe,
        candidate_path=str(payload["candidate_path"]),
    )
    model_id = f"trace-blueprint:{model.metadata.get('model_instance_id') or 'traceguard-investigation'}"
    return model_id, _canonical(result.to_dict())  # type: ignore[return-value]


def _expected_anchor(material: object):
    payload = _exact_mapping(
        material,
        {"model", "target_universe", "candidate_path"},
        "native blueprint input",
    )
    universe = TraceTargetUniverse.from_dict(payload["target_universe"])
    if universe.target_authority is None:
        raise ValueError("TraceGuard native input has no expected target anchor")
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
    """Derive TraceGuard's current behavior denominator from native objects."""

    payload = _exact_mapping(
        native_input_material,
        {"model", "target_universe", "candidate_path"},
        "native blueprint input",
    )
    anchor = _expected_anchor(payload)
    hierarchy = {
        native_model_id,
        *_declared_ids(payload["model"]),
        *_declared_ids(payload["target_universe"]),
        *_declared_ids(replayed_result),
    }
    interfaces = {
        "traceguard.interface:trace-model-to-blueprint-result",
        *_named_declared_ids(payload, ("interface", "binding", "handoff")),
    }
    targets = {anchor.anchor_id, *_declared_ids(payload["target_universe"])}
    receipt_ids = tuple(sorted(set(str(item) for item in native_receipt_ids)))
    if not receipt_ids:
        raise ValueError("TraceGuard domain behavior manifest requires a native receipt")
    common = {
        "owner": NATIVE_OWNER_ID,
        "checker_entrypoint": f"{__name__}:evaluate_domain_behavior_transition",
        "checker_id": NATIVE_CHECKER_ID,
        "checker_version": NATIVE_CHECKER_VERSION,
        "result_fingerprint": result_fingerprint,
        "native_receipt_id": receipt_ids[0],
    }
    model = payload["model"]
    universe = payload["target_universe"]
    if not isinstance(model, Mapping) or not isinstance(universe, Mapping):
        raise ValueError("TraceGuard domain behavior inputs are not objects")
    metadata = model.get("metadata")
    purpose = (
        metadata.get("guard_purpose_contract")
        if isinstance(metadata, Mapping)
        else None
    )
    if not isinstance(purpose, Mapping):
        raise ValueError("TraceGuard domain behavior has no native purpose evidence")
    good_ids = list(purpose.get("known_good_case_ids", []))
    bad_ids = list(purpose.get("known_bad_case_ids", []))
    selected_failures = list(purpose.get("selected_failure_ids", []))
    hierarchy_rows = replayed_result.get("hierarchy", [])
    interface_rows = replayed_result.get("interface_receipt_refs", [])
    domain_cases = (
        build_behavior_transition_case(
            case_id="case:traceguard.investigation-reconstruction",
            behavior_id="traceguard.investigation-reconstruction",
            input={
                "required_source_ids": list(universe.get("required_source_ids", [])),
                "required_evidence_ids": list(universe.get("required_evidence_ids", [])),
                "required_event_ids": list(universe.get("required_event_ids", [])),
                "required_trace_ids": list(universe.get("required_trace_ids", [])),
                "required_hypothesis_ids": list(universe.get("required_hypothesis_ids", [])),
                "required_interface_binding_ids": list(universe.get("required_interface_binding_ids", [])),
            },
            pre_state={
                "candidate_path": str(payload["candidate_path"]),
                "declared_hypothesis_ids": sorted(
                    str(item.get("hypothesis_id", ""))
                    for item in model.get("storyline_hypotheses", [])
                    if isinstance(item, Mapping)
                ),
                "declared_event_ids": sorted(
                    str(item.get("event_id", ""))
                    for item in model.get("events", [])
                    if isinstance(item, Mapping)
                ),
            },
            permitted_output={
                "live_alternative_ids": list(replayed_result.get("live_alternative_ids", [])),
                "ordered_trace_projection": [
                    dict(item)
                    for item in hierarchy_rows
                    if isinstance(item, Mapping)
                    and item.get("kind") in {"event", "sequence_stage", "trace", "storyline_hypothesis"}
                ],
                "causal_boundaries": list(replayed_result.get("causal_boundaries", [])),
                "interface_binding_ids": sorted(
                    str(item.get("binding_id", ""))
                    for item in interface_rows
                    if isinstance(item, Mapping)
                ),
                "gaps": list(replayed_result.get("gaps", [])),
            },
            post_state={
                "deepest_proven_layer": str(replayed_result.get("deepest_proven_layer", "")),
                "first_unresolved_gap": str(replayed_result.get("first_unresolved_gap", "")),
                "claim_boundary": str(replayed_result.get("claim_boundary", "")),
            },
            effect=(
                "reconstruct_evidence_bound_temporal_storylines",
                "compare_live_alternatives",
                "project_bounded_causal_status",
                "preserve_unresolved_trace_gaps",
            ),
            protected_failure=str(next(iter(selected_failures), "trace-native-failure")),
            bad_mutation_path="permitted_output.ordered_trace_projection",
            failure_class_id=str(next(iter(selected_failures), "trace-native-failure")),
            good_native_evidence={
                "case_ids": good_ids,
                "proof_receipt_fingerprint": str(purpose.get("proof_receipt_fingerprint", "")),
                "candidate_fingerprint": str(purpose.get("candidate_fingerprint", "")),
                "observed_terminal": "passed",
            },
            bad_native_evidence={
                "case_ids": bad_ids,
                "proof_receipt_fingerprint": str(purpose.get("proof_receipt_fingerprint", "")),
                "selected_failure_ids": selected_failures,
                "observed_terminal": "rejected",
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
    """Rerun TraceGuard and compare one investigation projection."""

    if envelope.member_id != NATIVE_OWNER_ID or envelope.opaque_payload is None:
        raise ValueError("TraceGuard domain evaluation requires its opaque payload")
    raw = _exact_mapping(
        json.loads(envelope.opaque_payload.decode("utf-8")),
        {"schema_version", "investigation_request", "trace_input", "inference_result"},
        "native-owner replay material",
    )
    native_input = _exact_mapping(
        raw["trace_input"],
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
        raise ValueError("TraceGuard behavior manifest differs from native replay")
    canonical = next(
        (item for item in canonical_manifest.domain_behavior_cases if item.behavior_id == behavior_id),
        None,
    )
    if canonical is None:
        raise ValueError("TraceGuard domain behavior id is outside the denominator")
    return _compare_native_domain_transition(canonical, candidate_transition)


def replay_native_owner_attestation(
    envelope: MemberModelEnvelope, *, registry_identity: str
) -> NativeOwnerAttestation:
    if envelope.member_id != NATIVE_OWNER_ID or envelope.opaque_payload is None:
        raise ValueError("TraceGuard native-owner replay requires its opaque payload")
    from ..routing import native_owner_registry_identity

    if registry_identity != native_owner_registry_identity(NATIVE_OWNER_ID):
        raise ValueError("TraceGuard native-owner registry identity is stale or foreign")
    raw = _exact_mapping(
        json.loads(envelope.opaque_payload.decode("utf-8")),
        {"schema_version", "investigation_request", "trace_input", "inference_result"},
        "native-owner replay material",
    )
    if raw["schema_version"] != NATIVE_OWNER_REPLAY_SCHEMA:
        raise ValueError("TraceGuard native-owner replay schema is not current")
    request = _exact_mapping(
        raw["investigation_request"],
        {"task_id", "operation", "claim_boundary", "material"},
        "replay request",
    )
    native_input = _exact_mapping(
        raw["trace_input"],
        {"native_model_id", "model_fingerprint", "input_id", "material"},
        "replay input",
    )
    submitted_result = _exact_mapping(
        raw["inference_result"],
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
        or native_input["input_id"] != f"traceguard-input:{_digest(native_input['material'])}"
        or envelope.expected_target_anchor_id != anchor.anchor_id
        or envelope.expected_target_anchor_fingerprint != anchor.anchor_fingerprint
        or dict(submitted_result) != expected_result
        or envelope.terminal_status != derived_terminal
        or tuple(sorted(envelope.open_gap_refs)) != (() if derived_terminal == "passed" else derived_gap_refs)
    ):
        raise ValueError("TraceGuard replay differs from the current native blueprint execution")

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
        raise ValueError("TraceGuard request does not bind its current behavior manifest")
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
            raise ValueError("TraceGuard native receipt does not replay exactly")
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
