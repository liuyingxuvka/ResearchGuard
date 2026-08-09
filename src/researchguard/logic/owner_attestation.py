"""LogicGuard-owned native replay for opaque composition attestations.

The caller transports bytes only.  LogicGuard reconstructs the exact current
model/inventory/depth inputs, executes its blueprint checker, and derives the
terminal result before the shared envelope carrier is allowed to attest it.
"""

from __future__ import annotations

import hashlib
import json
from typing import Iterable, Mapping

from .artifact_inventory import ArtifactInventory
from .blueprint import (
    ArtifactRealizationBinding,
    LogicNativeDepthEvidence,
    check_blueprint,
)
from .loader import load_model_from_dict
from ..native_receipts import NativeReceiptReference
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


NATIVE_OWNER_REPLAY_SCHEMA = "researchguard.logic.native-owner-replay.v1"
NATIVE_OWNER_ID = "logicguard"
NATIVE_CHECKER_ID = "researchguard.logic.blueprint-check"
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
        raise ValueError(f"LogicGuard {label} is not exact-current")
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
            "LogicGuard external projection requires its exact replayed native blueprint"
        )
    return {
        "member_id": NATIVE_OWNER_ID,
        "blueprint_replay": "passed",
        "binding": _canonical(binding),
        "portable_result_fingerprint": str(replay["portable_result_fingerprint"]),
    }


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"LogicGuard {label} must be an object")
    return value


def evaluate_external_object_transition(
    model: Mapping[str, object], context: Mapping[str, object]
) -> dict[str, object]:
    """Derive one bounded external-object conclusion at LogicGuard.

    The owner derives whether the admitted anchors are consistent or divergent;
    ResearchGuard never supplies a conflict mode or a desired conclusion.
    """

    native_blueprint = _require_external_native_replay(model, context)
    request = _exact_mapping(
        model.get("input"),
        {"claim_specs", "summary_claim_id", "uncertainty_gap_id", "scope_limits"},
        "external-object input",
    )
    outputs = context.get("member_outputs")
    source = outputs.get("sourceguard") if isinstance(outputs, Mapping) else None
    trace = outputs.get("traceguard") if isinstance(outputs, Mapping) else None
    if not isinstance(source, Mapping) or not isinstance(trace, Mapping):
        raise ValueError("LogicGuard external-object replay requires source and trace outputs")
    scope_limits = request["scope_limits"]
    if not isinstance(scope_limits, list) or not scope_limits or any(
        not str(item).strip() for item in scope_limits
    ):
        raise ValueError("LogicGuard external-object scope limits are required")
    anchor_rows = source.get("claim_anchors")
    if not isinstance(anchor_rows, list):
        raise ValueError("LogicGuard external-object replay has no SourceGuard anchors")
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
            or anchor["status"] != "located"
            or any(
                not str(anchor[field]).strip()
                for field in ("claim_id", "source_id", "locator", "value")
            )
        ):
            raise ValueError("LogicGuard SourceGuard claim anchor is invalid")
        anchors[anchor_id] = anchor
    event_rows = trace.get("ordered_events")
    if not isinstance(event_rows, list) or not event_rows:
        raise ValueError("LogicGuard external-object trace event denominator is empty")
    events: dict[str, Mapping[str, object]] = {}
    ordered_event_ids: list[str] = []
    consumed_upstream_ids: set[str] = set()
    previous_event_id: str | None = None
    for raw_event in event_rows:
        event = _exact_mapping(
            raw_event,
            {"event_id", "stage", "predecessor_ids", "evidence_ids", "output_ids"},
            "TraceGuard ordered event",
        )
        event_id = str(event["event_id"])
        predecessor_ids = event["predecessor_ids"]
        evidence_ids = event["evidence_ids"]
        output_ids = event["output_ids"]
        expected_predecessors = [] if previous_event_id is None else [previous_event_id]
        if (
            not event_id
            or event_id in events
            or not str(event["stage"]).strip()
            or predecessor_ids != expected_predecessors
            or not isinstance(evidence_ids, list)
            or len(evidence_ids) != 1
            or not isinstance(output_ids, list)
            or len(output_ids) != 1
        ):
            raise ValueError("LogicGuard TraceGuard event chain is invalid")
        anchor_id = str(evidence_ids[0])
        anchor = anchors.get(anchor_id)
        if anchor is None or output_ids != [f"observed-value:{anchor['value']}"]:
            raise ValueError(
                "LogicGuard TraceGuard event is rebound from its SourceGuard observation"
            )
        events[event_id] = event
        ordered_event_ids.append(event_id)
        consumed_upstream_ids.add(event_id)
        previous_event_id = event_id
    trace_gaps = trace.get("gaps")
    if not isinstance(trace_gaps, list):
        raise ValueError("LogicGuard TraceGuard gap denominator is unavailable")
    trace_gap_ids: list[str] = []
    for raw_gap in trace_gaps:
        gap = _exact_mapping(
            raw_gap, {"gap_id", "code", "detail"}, "TraceGuard gap"
        )
        gap_id = str(gap["gap_id"])
        if (
            not gap_id
            or gap_id in trace_gap_ids
            or not str(gap["code"]).strip()
            or not str(gap["detail"]).strip()
        ):
            raise ValueError("LogicGuard TraceGuard gap is invalid")
        trace_gap_ids.append(gap_id)
        consumed_upstream_ids.add(gap_id)
    storyline_rows = trace.get("storylines")
    if not isinstance(storyline_rows, list) or len(storyline_rows) != 1:
        raise ValueError("LogicGuard requires one exact TraceGuard storyline")
    storyline = _exact_mapping(
        storyline_rows[0],
        {"storyline_id", "event_ids", "status", "unresolved_gap_ids"},
        "TraceGuard storyline",
    )
    expected_storyline_status = "variance_open" if trace_gap_ids else "consistent"
    if (
        not str(storyline["storyline_id"]).strip()
        or storyline["event_ids"] != ordered_event_ids
        or storyline["status"] != expected_storyline_status
        or storyline["unresolved_gap_ids"] != trace_gap_ids
    ):
        raise ValueError(
            "LogicGuard TraceGuard storyline status or denominator is inconsistent"
        )
    consumed_upstream_ids.add(str(storyline["storyline_id"]))
    specs = request["claim_specs"]
    if not isinstance(specs, list) or not specs:
        raise ValueError("LogicGuard external-object claim denominator is empty")
    if (
        len({str(item.get("event_id", "")) for item in specs if isinstance(item, Mapping)})
        != len(specs)
        or {str(item.get("event_id", "")) for item in specs if isinstance(item, Mapping)}
        != set(ordered_event_ids)
    ):
        raise ValueError(
            "LogicGuard claim specs do not consume the complete TraceGuard event denominator"
        )
    claims: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    values: set[str] = set()
    evidence_ids: list[str] = []
    for raw in specs:
        spec = _exact_mapping(raw, {"event_id", "claim_id", "edge_id"}, "external-object claim")
        event = events.get(str(spec["event_id"]))
        if event is None or not isinstance(event.get("evidence_ids"), list) or len(event["evidence_ids"]) != 1:
            raise ValueError("LogicGuard claim references an unknown or ambiguous trace event")
        anchor_id = str(event["evidence_ids"][0])
        anchor = anchors.get(anchor_id)
        if anchor is None:
            raise ValueError("LogicGuard claim cannot resolve its SourceGuard anchor")
        value = str(anchor["value"])
        values.add(value)
        evidence_ids.append(anchor_id)
        claim_id = str(spec["claim_id"])
        claims.append({
            "claim_id": claim_id,
            "text": f"Frozen source occurrence {anchor['locator']} reports {value}.",
            "status": "source_anchored",
            "premise_ids": [],
            "evidence_ids": [anchor_id],
            "scope": str(anchor["locator"]),
        })
        edges.append({
            "edge_id": str(spec["edge_id"]),
            "from_claim_id": claim_id,
            "to_claim_id": str(request["summary_claim_id"]),
            "relation": "supports_bounded_summary",
        })
    divergent = len(values) > 1
    summary_claim_id = str(request["summary_claim_id"])
    premise_ids = [str(item["claim_id"]) for item in claims]
    summary_text = (
        "Frozen target contains divergent reported values: " + ", ".join(sorted(values)) + "."
        if divergent
        else "Frozen target consistently reports the observed value " + next(iter(values)) + "."
    )
    claims.append({
        "claim_id": summary_claim_id,
        "text": summary_text,
        "status": "licensed_bounded_variance" if divergent else "licensed_bounded_consistency",
        "premise_ids": premise_ids,
        "evidence_ids": evidence_ids,
        "scope": "reported-value consistency only; not factual truth or undocumented intent",
    })
    gap_id = str(request["uncertainty_gap_id"])
    gaps = ([{
        "gap_id": gap_id,
        "code": "authoritative-resolution-not-licensed",
        "detail": "The native argument licenses the observed variance, not one value as authoritative.",
    }] if divergent else [])
    output = {
        "claims": claims,
        "argument_edges": edges,
        "scope_limits": list(scope_limits),
        "gaps": gaps,
    }
    return {
        "output": output,
        "transition_contract": {
            "pre_state": {"licensed_claim_ids": [], "open_rebuttal_ids": []},
            "post_state": {
                "licensed_claim_ids": [str(item["claim_id"]) for item in claims],
                "open_gap_ids": [gap_id] if divergent else [],
            },
            "effect": [
                "license_bounded_variance" if divergent else "license_bounded_consistency",
                "enforce_scope_limits",
            ],
            "protected_failure": "licensing truth or undocumented intent beyond the declared premises and scope",
            "claim_boundary": (
                "LogicGuard licenses only the bounded conclusion supported by declared premises; "
                "factual truth and undocumented intent remain outside the model."
            ),
        },
        "native_result": {
            "member_native_blueprint": native_blueprint,
            "consumed_upstream_object_ids": sorted(consumed_upstream_ids),
            "storyline_fingerprint": _digest(storyline),
            "licensed_conclusion": "variance_observed" if divergent else "consistency_observed",
            "value_denominator": sorted(values),
            "premise_claim_ids": premise_ids,
            "scope_limits": list(scope_limits),
        },
    }


def build_external_object_bad_case(
    model: Mapping[str, object], context: Mapping[str, object]
) -> tuple[Mapping[str, object], Mapping[str, object]]:
    """Build LogicGuard's target-native protected-failure replay case."""

    bad_context = dict(context)
    outputs = _canonical(context.get("member_outputs"))
    if not isinstance(outputs, dict):
        raise ValueError("LogicGuard external-object bad upstream state is unavailable")
    trace = outputs.get("traceguard")
    if not isinstance(trace, dict):
        raise ValueError("LogicGuard external-object bad TraceGuard output is unavailable")
    storylines = trace.get("storylines")
    if not isinstance(storylines, list) or not storylines or not isinstance(storylines[0], dict):
        raise ValueError("LogicGuard external-object bad storyline is unavailable")
    storylines[0]["status"] = (
        "consistent" if storylines[0].get("status") != "consistent" else "variance_open"
    )
    bad_context["member_outputs"] = outputs
    return model, bad_context


def _replay_blueprint(material: object) -> dict[str, object]:
    payload = _exact_mapping(
        material,
        {"model", "artifact_inventory", "realizations", "native_depth_evidence"},
        "native blueprint input",
    )
    model_raw = _mapping(payload["model"], "model")
    inventory_raw = _mapping(payload["artifact_inventory"], "artifact inventory")
    realization_rows = payload["realizations"]
    depth_raw = _exact_mapping(
        payload["native_depth_evidence"],
        {"target_root", "guard_contract", "budget", "receipt", "receipt_fingerprint", "status", "native_receipt_ref"},
        "native depth evidence",
    )
    if not isinstance(realization_rows, list):
        raise ValueError("LogicGuard realizations must be a list")
    model = load_model_from_dict(model_raw, validate=False)
    inventory = ArtifactInventory.from_dict(inventory_raw)
    realizations = tuple(
        ArtifactRealizationBinding(
            artifact_unit_id=str(row["artifact_unit_id"]),
            argument_block_id=str(row["argument_block_id"]),
            node_ids=tuple(str(value) for value in row["node_ids"]),
            resource_ids=tuple(str(value) for value in row.get("resource_ids", [])),
            disposition=str(row.get("disposition", "bound")),  # type: ignore[arg-type]
            consumed_content_fingerprint=str(row.get("consumed_content_fingerprint", "")),
        )
        for row in realization_rows
        if isinstance(row, Mapping)
    )
    if len(realizations) != len(realization_rows):
        raise ValueError("LogicGuard realization row is not an object")
    receipt = depth_raw["receipt"]
    if not isinstance(receipt, Mapping):
        raise ValueError("LogicGuard native depth receipt must be an object")
    depth = LogicNativeDepthEvidence(
        target_root=str(depth_raw["target_root"]),
        guard_contract=str(depth_raw["guard_contract"]),
        budget=int(depth_raw["budget"]),
        receipt=dict(receipt),
        receipt_fingerprint=str(depth_raw["receipt_fingerprint"]),
        status=str(depth_raw["status"]),  # type: ignore[arg-type]
        native_receipt_ref=(
            NativeReceiptReference.from_dict(depth_raw["native_receipt_ref"])
            if isinstance(depth_raw.get("native_receipt_ref"), Mapping)
            else None
        ),
    )
    return _canonical(check_blueprint(model, inventory, realizations, depth).to_dict())  # type: ignore[return-value]


def _expected_anchor(material: object):
    payload = _exact_mapping(
        material,
        {"model", "artifact_inventory", "realizations", "native_depth_evidence"},
        "native blueprint input",
    )
    inventory = ArtifactInventory.from_dict(_mapping(payload["artifact_inventory"], "artifact inventory"))
    if inventory.target_authority is None:
        raise ValueError("LogicGuard native input has no expected target anchor")
    return inventory.target_authority.expected_target_anchor


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
    """Derive LogicGuard's current behavior denominator from native objects."""

    payload = _exact_mapping(
        native_input_material,
        {"model", "artifact_inventory", "realizations", "native_depth_evidence"},
        "native blueprint input",
    )
    anchor = _expected_anchor(payload)
    hierarchy = {
        native_model_id,
        *_declared_ids(payload["model"]),
        *_declared_ids(payload["artifact_inventory"]),
        *_declared_ids(replayed_result),
    }
    interfaces = {
        "logicguard.interface:argument-model-to-blueprint-result",
        *_declared_ids(payload["realizations"]),
        *_named_declared_ids(payload["model"], ("interface", "binding", "edge")),
    }
    targets = {anchor.anchor_id, *_declared_ids(payload["artifact_inventory"])}
    receipt_ids = tuple(sorted(set(str(item) for item in native_receipt_ids)))
    if not receipt_ids:
        raise ValueError("LogicGuard domain behavior manifest requires a native receipt")
    common = {
        "owner": NATIVE_OWNER_ID,
        "checker_entrypoint": f"{__name__}:evaluate_domain_behavior_transition",
        "checker_id": NATIVE_CHECKER_ID,
        "checker_version": NATIVE_CHECKER_VERSION,
        "result_fingerprint": result_fingerprint,
        "native_receipt_id": receipt_ids[0],
    }
    model = payload["model"]
    inventory = payload["artifact_inventory"]
    realizations = payload["realizations"]
    depth = payload["native_depth_evidence"]
    if not all(isinstance(item, Mapping) for item in (model, inventory, depth)) or not isinstance(realizations, list):
        raise ValueError("LogicGuard domain behavior inputs are invalid")
    depth_receipt = depth.get("receipt")  # type: ignore[union-attr]
    proof = (
        depth_receipt.get("target_proof_receipt")
        if isinstance(depth_receipt, Mapping)
        else None
    )
    proofs = proof.get("failure_proofs", []) if isinstance(proof, Mapping) else []
    if not isinstance(proofs, list) or not proofs or not isinstance(proofs[0], Mapping):
        raise ValueError("LogicGuard domain behavior has no native good/bad proof")
    failure_proof = proofs[0]
    finding = failure_proof.get("oracle")
    failure_code = (
        str(finding.get("finding_code", "logic-native-failure"))
        if isinstance(finding, Mapping)
        else "logic-native-failure"
    )
    evaluation = depth_receipt.get("evaluation", {}) if isinstance(depth_receipt, Mapping) else {}
    coverage = depth_receipt.get("coverage", {}) if isinstance(depth_receipt, Mapping) else {}
    tournament = depth_receipt.get("tournament", {}) if isinstance(depth_receipt, Mapping) else {}
    domain_cases = (
        build_behavior_transition_case(
            case_id="case:logicguard.argument-artifact-qualification",
            behavior_id="logicguard.argument-artifact-qualification",
            input={
                "root_claim_id": str(
                    model.get("model", {}).get("root_claim", "")  # type: ignore[union-attr]
                    if isinstance(model.get("model"), Mapping)  # type: ignore[union-attr]
                    else ""
                ),
                "argument_node_ids": sorted(
                    str(item) for item in model.get("nodes", {})  # type: ignore[union-attr]
                ),
                "argument_block_ids": sorted(
                    str(item) for item in model.get("blocks", {})  # type: ignore[union-attr]
                ),
                "artifact_unit_ids": sorted(_declared_ids(inventory)),
                "artifact_realizations": [dict(item) for item in realizations if isinstance(item, Mapping)],
            },
            pre_state={
                "native_depth_status": str(depth.get("status", "")),  # type: ignore[union-attr]
                "open_native_depth_gaps": list(
                    depth_receipt.get("unresolved_gaps", [])
                    if isinstance(depth_receipt, Mapping)
                    else []
                ),
            },
            permitted_output={
                "evaluated_nodes": dict(
                    evaluation.get("nodes", {}) if isinstance(evaluation, Mapping) else {}
                ),
                "argument_summary": str(
                    evaluation.get("summary", "") if isinstance(evaluation, Mapping) else ""
                ),
                "coverage": dict(coverage) if isinstance(coverage, Mapping) else {},
                "tournament": dict(tournament) if isinstance(tournament, Mapping) else {},
                "structural_reconstruction": str(replayed_result.get("structural_reconstruction", "")),
                "content_reconstruction": str(replayed_result.get("content_reconstruction", "")),
                "gaps": list(replayed_result.get("gaps", [])),
                "layer_statuses": list(replayed_result.get("layer_statuses", [])),
            },
            post_state={
                "deepest_proven_layer": str(replayed_result.get("deepest_proven_layer", "")),
                "first_unresolved_gap": str(replayed_result.get("first_unresolved_gap", "")),
                "claim_boundary": str(replayed_result.get("claim_boundary", "")),
            },
            effect=(
                "license_only_supported_argument_claims",
                "bind_argument_blocks_to_artifact_units",
                "separate_structural_from_content_reconstruction",
                "preserve_rebuttal_scope_and_resource_gaps",
            ),
            protected_failure=failure_code,
            bad_mutation_path="permitted_output.evaluated_nodes",
            failure_class_id=str(failure_proof.get("failure_id", failure_code)),
            good_native_evidence={
                "known_good_sha256": str(failure_proof.get("known_good_sha256", "")),
                "known_good_status": str(failure_proof.get("known_good_status", "")),
                "finding_absent": bool(failure_proof.get("finding_absent_from_good_and_candidate", False)),
                "proof_receipt_fingerprint": str(
                    proof.get("receipt_fingerprint", depth.get("receipt_fingerprint", ""))  # type: ignore[union-attr]
                    if isinstance(proof, Mapping)
                    else depth.get("receipt_fingerprint", "")  # type: ignore[union-attr]
                ),
            },
            bad_native_evidence={
                "known_bad_sha256": str(failure_proof.get("known_bad_sha256", "")),
                "known_bad_status": str(failure_proof.get("known_bad_status", "")),
                "finding_observed": bool(failure_proof.get("finding_observed_in_bad", False)),
                "oracle": dict(finding) if isinstance(finding, Mapping) else {},
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
    """Rerun LogicGuard and compare one argument/artifact projection."""

    if envelope.member_id != NATIVE_OWNER_ID or envelope.opaque_payload is None:
        raise ValueError("LogicGuard domain evaluation requires its opaque payload")
    raw = _exact_mapping(
        json.loads(envelope.opaque_payload.decode("utf-8")),
        {"schema_version", "argument_request", "argument_artifact_input", "qualification_result"},
        "native-owner replay material",
    )
    native_input = _exact_mapping(
        raw["argument_artifact_input"],
        {"native_model_id", "model_fingerprint", "input_id", "material"},
        "replay input",
    )
    replayed = _replay_blueprint(native_input["material"])
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
        native_model_id=str(replayed.get("model_id", "")),
        model_fingerprint=str(replayed.get("model_fingerprint", "")),
        native_input_material=native_input["material"],
        replayed_result=replayed,
        native_receipt_ids=(item.receipt_id for item in envelope.native_receipt_refs),
        result_fingerprint=_digest(expected_result),
        terminal_status=terminal,
    )
    if canonical_manifest.to_dict() != envelope.behavior_manifest.to_dict():
        raise ValueError("LogicGuard behavior manifest differs from native replay")
    canonical = next(
        (item for item in canonical_manifest.domain_behavior_cases if item.behavior_id == behavior_id),
        None,
    )
    if canonical is None:
        raise ValueError("LogicGuard domain behavior id is outside the denominator")
    return _compare_native_domain_transition(canonical, candidate_transition)


def replay_native_owner_attestation(
    envelope: MemberModelEnvelope, *, registry_identity: str
) -> NativeOwnerAttestation:
    if envelope.member_id != NATIVE_OWNER_ID or envelope.opaque_payload is None:
        raise ValueError("LogicGuard native-owner replay requires its opaque payload")
    from ..routing import native_owner_registry_identity

    if registry_identity != native_owner_registry_identity(NATIVE_OWNER_ID):
        raise ValueError("LogicGuard native-owner registry identity is stale or foreign")
    raw = _exact_mapping(
        json.loads(envelope.opaque_payload.decode("utf-8")),
        {"schema_version", "argument_request", "argument_artifact_input", "qualification_result"},
        "native-owner replay material",
    )
    if raw["schema_version"] != NATIVE_OWNER_REPLAY_SCHEMA:
        raise ValueError("LogicGuard native-owner replay schema is not current")
    request = _exact_mapping(
        raw["argument_request"],
        {"task_id", "operation", "claim_boundary", "material"},
        "replay request",
    )
    native_input = _exact_mapping(
        raw["argument_artifact_input"],
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

    replayed_result = _replay_blueprint(native_input["material"])
    derived_terminal = "passed" if replayed_result.get("status") == "complete" else "blocked"
    derived_model_id = str(replayed_result.get("model_id", ""))
    derived_model_fingerprint = str(replayed_result.get("model_fingerprint", ""))
    derived_gap_refs = tuple(
        sorted(
            f"{item.get('code', '')}:{item.get('object_id', '')}"
            for item in replayed_result.get("gaps", [])
            if isinstance(item, Mapping)
        )
    )
    expected_input_id = f"logicguard-input:{_digest(native_input['material'])}"
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
        or native_input["input_id"] != expected_input_id
        or envelope.expected_target_anchor_id != anchor.anchor_id
        or envelope.expected_target_anchor_fingerprint != anchor.anchor_fingerprint
        or dict(submitted_result) != expected_result
        or envelope.terminal_status != derived_terminal
        or tuple(sorted(envelope.open_gap_refs)) != (() if derived_terminal == "passed" else derived_gap_refs)
    ):
        raise ValueError("LogicGuard replay differs from the current native blueprint execution")

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
        raise ValueError("LogicGuard request does not bind its current behavior manifest")
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
            raise ValueError("LogicGuard native receipt does not replay exactly")
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
