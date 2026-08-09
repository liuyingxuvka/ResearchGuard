"""ExperimentGuard-owned native replay for opaque composition attestations."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping

from .blueprint import check_blueprint
from .cli import _load_spec, _load_spec_payload
from .engine import recommend_experiments
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
from ..portable_material import portable_native_material_bytes


NATIVE_OWNER_REPLAY_SCHEMA = "researchguard.experiment.native-owner-replay.v1"
NATIVE_OWNER_ID = "experimentguard"
NATIVE_CHECKER_ID = "researchguard.experiment.blueprint-check"
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
        raise ValueError(f"ExperimentGuard {label} is not exact-current")
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
            "ExperimentGuard external projection requires its exact replayed native blueprint"
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
    """Derive a finite recommendation from member-native upstream outputs.

    A consistent target remains on this path and yields no fabricated conflict
    or external experiment execution.
    """

    native_blueprint = _require_external_native_replay(model, context)
    request = _exact_mapping(
        model.get("input"),
        {
            "hypothesis_ids_by_value", "comparison_experiment_id",
            "resolution_experiment_id", "uncertainty_gap_id",
        },
        "external-object input",
    )
    outputs = context.get("member_outputs")
    logic = outputs.get("logicguard") if isinstance(outputs, Mapping) else None
    if not isinstance(logic, Mapping):
        raise ValueError("ExperimentGuard external-object replay requires LogicGuard output")
    hypothesis_map = request["hypothesis_ids_by_value"]
    if (
        not isinstance(hypothesis_map, Mapping)
        or not hypothesis_map
        or any(not str(key).strip() or not str(value).strip() for key, value in hypothesis_map.items())
        or len({str(value) for value in hypothesis_map.values()}) != len(hypothesis_map)
    ):
        raise ValueError("ExperimentGuard hypothesis denominator is invalid")
    claims = logic.get("claims")
    if not isinstance(claims, list) or len(claims) < 2:
        raise ValueError("ExperimentGuard has no complete LogicGuard claim denominator")
    consumed_upstream_ids: set[str] = set()
    premise_claims: list[Mapping[str, object]] = []
    summary_claims: list[Mapping[str, object]] = []
    values_by_claim: dict[str, str] = {}
    anchor_ids: list[str] = []
    observed: dict[str, str] = {}
    for raw_claim in claims:
        claim = _exact_mapping(
            raw_claim,
            {"claim_id", "text", "status", "premise_ids", "evidence_ids", "scope"},
            "LogicGuard claim",
        )
        claim_id = str(claim["claim_id"])
        if not claim_id or claim_id in consumed_upstream_ids:
            raise ValueError("ExperimentGuard LogicGuard claim identity is invalid")
        consumed_upstream_ids.add(claim_id)
        if claim["status"] in {
            "licensed_bounded_variance",
            "licensed_bounded_consistency",
        }:
            summary_claims.append(claim)
            continue
        if (
            claim["status"] != "source_anchored"
            or claim["premise_ids"] != []
            or not isinstance(claim["evidence_ids"], list)
            or len(claim["evidence_ids"]) != 1
            or not str(claim["scope"]).strip()
        ):
            raise ValueError("ExperimentGuard LogicGuard premise claim is invalid")
        matching_values = [
            str(value)
            for value in hypothesis_map
            if claim["text"]
            == f"Frozen source occurrence {claim['scope']} reports {value}."
        ]
        if len(matching_values) != 1:
            raise ValueError(
                "ExperimentGuard LogicGuard premise does not bind one declared observed value"
            )
        value = matching_values[0]
        locator = str(claim["scope"])
        anchor_id = str(claim["evidence_ids"][0])
        if not anchor_id or (
            locator in observed and observed[locator] != value
        ):
            raise ValueError(
                "ExperimentGuard LogicGuard premise occurrence is duplicated inconsistently"
            )
        values_by_claim[claim_id] = value
        anchor_ids.append(anchor_id)
        observed[locator] = value
        premise_claims.append(claim)
    if len(summary_claims) != 1 or not premise_claims:
        raise ValueError("ExperimentGuard requires one bounded LogicGuard summary")
    summary = summary_claims[0]
    values = sorted(set(values_by_claim.values()))
    if set(hypothesis_map) != set(values):
        raise ValueError("ExperimentGuard hypothesis denominator differs from LogicGuard values")
    divergent = len(values) > 1
    premise_ids = [str(item["claim_id"]) for item in premise_claims]
    expected_summary_text = (
        "Frozen target contains divergent reported values: " + ", ".join(values) + "."
        if divergent
        else "Frozen target consistently reports the observed value " + values[0] + "."
    )
    if (
        summary["status"]
        != ("licensed_bounded_variance" if divergent else "licensed_bounded_consistency")
        or summary["premise_ids"] != premise_ids
        or summary["evidence_ids"] != anchor_ids
        or summary["text"] != expected_summary_text
        or not str(summary["scope"]).strip()
    ):
        raise ValueError(
            "ExperimentGuard LogicGuard bounded summary is inconsistent with its premises"
        )
    edges = logic.get("argument_edges")
    if not isinstance(edges, list) or len(edges) != len(premise_claims):
        raise ValueError("ExperimentGuard LogicGuard argument edge denominator is incomplete")
    expected_edge_pairs = {
        (claim_id, str(summary["claim_id"])) for claim_id in premise_ids
    }
    actual_edge_pairs: set[tuple[str, str]] = set()
    for raw_edge in edges:
        edge = _exact_mapping(
            raw_edge,
            {"edge_id", "from_claim_id", "to_claim_id", "relation"},
            "LogicGuard argument edge",
        )
        edge_id = str(edge["edge_id"])
        if (
            not edge_id
            or edge_id in consumed_upstream_ids
            or edge["relation"] != "supports_bounded_summary"
        ):
            raise ValueError("ExperimentGuard LogicGuard argument edge is invalid")
        consumed_upstream_ids.add(edge_id)
        actual_edge_pairs.add((str(edge["from_claim_id"]), str(edge["to_claim_id"])))
    if actual_edge_pairs != expected_edge_pairs or len(actual_edge_pairs) != len(edges):
        raise ValueError(
            "ExperimentGuard LogicGuard argument edges do not close the premise denominator"
        )
    scope_limits = logic.get("scope_limits")
    if (
        not isinstance(scope_limits, list)
        or not scope_limits
        or any(not str(item).strip() for item in scope_limits)
    ):
        raise ValueError("ExperimentGuard LogicGuard scope limits are unavailable")
    logic_gaps = logic.get("gaps")
    if not isinstance(logic_gaps, list):
        raise ValueError("ExperimentGuard LogicGuard gap denominator is unavailable")
    logic_gap_ids: list[str] = []
    for raw_gap in logic_gaps:
        gap = _exact_mapping(
            raw_gap, {"gap_id", "code", "detail"}, "LogicGuard gap"
        )
        gap_id = str(gap["gap_id"])
        if (
            not gap_id
            or gap_id in consumed_upstream_ids
            or not str(gap["code"]).strip()
            or not str(gap["detail"]).strip()
        ):
            raise ValueError("ExperimentGuard LogicGuard gap is invalid")
        logic_gap_ids.append(gap_id)
        consumed_upstream_ids.add(gap_id)
    if bool(logic_gap_ids) != divergent:
        raise ValueError(
            "ExperimentGuard LogicGuard gaps disagree with the licensed summary"
        )
    comparison_id = str(request["comparison_experiment_id"])
    resolution_id = str(request["resolution_experiment_id"])
    hypotheses = [{
        "hypothesis_id": str(hypothesis_map[value]),
        "text": f"The intended reported value is {value}.",
        "predictions": {
            comparison_id: "frozen occurrences preserve the observed value pattern",
            resolution_id: f"authoritative external resolution favors {value}",
        },
    } for value in values]
    comparison = {
        "experiment_id": comparison_id,
        "purpose": "Compare every frozen anchor without changing or selecting its value.",
        "input_ids": anchor_ids,
        "output_ids": ["observation:divergent-values" if divergent else "observation:consistent-value"],
        "observed_outcomes": observed,
        "locator": ";".join(sorted(observed)),
        "status": "completed_variance_preserved" if divergent else "completed_consistency_preserved",
    }
    resolution = {
        "experiment_id": resolution_id,
        "purpose": "Seek an authoritative resolution outside the frozen target when variance exists.",
        "input_ids": [],
        "output_ids": ["observation:resolution-not-run" if divergent else "observation:resolution-not-required"],
        "observed_outcomes": {"frozen_target": "no_external_resolution" if divergent else "consistent"},
        "locator": "outside-frozen-target",
        "status": "not_run_outside_frozen_target" if divergent else "not_applicable_no_variance",
    }
    unresolved_pairs = [
        [str(hypothesis_map[left]), str(hypothesis_map[right])]
        for index, left in enumerate(values) for right in values[index + 1:]
    ]
    gap_id = str(request["uncertainty_gap_id"])
    output = {
        "hypotheses": hypotheses,
        "experiments": [comparison, resolution],
        "recommendation": {
            "selected_experiment_ids": [comparison_id],
            "alternative_minimal_sets": [[resolution_id]] if divergent else [],
            "unresolved_hypothesis_pairs": unresolved_pairs,
            "reason": (
                "The comparison preserves observed variance but cannot distinguish undocumented intent."
                if divergent else
                "The comparison confirms consistency inside the frozen target; it does not establish external truth."
            ),
        },
        "gaps": ([{
            "gap_id": gap_id,
            "code": "resolution-experiment-not-run",
            "detail": "No authoritative resolution evidence exists inside the frozen target.",
        }] if divergent else []),
    }
    return {
        "output": output,
        "transition_contract": {
            "pre_state": {"resolved_hypothesis_ids": [], "variance_status": "open" if divergent else "absent"},
            "post_state": {
                "variance_status": "open" if divergent else "absent",
                "unresolved_hypothesis_pairs": unresolved_pairs,
            },
            "effect": [
                "compare_declared_values",
                "preserve_unresolved_hypotheses" if divergent else "record_no_discrimination_needed",
            ],
            "protected_failure": "inventing an executed experiment, probability, or resolved truth",
            "claim_boundary": (
                "ExperimentGuard recommends from the declared finite hypotheses and outcomes; "
                "it does not execute external experiments or choose factual truth."
            ),
        },
        "native_result": {
            "member_native_blueprint": native_blueprint,
            "consumed_upstream_object_ids": sorted(consumed_upstream_ids),
            "argument_edge_fingerprint": _digest(edges),
            "hypothesis_value_denominator": values,
            "comparison_distinguishes": False,
            "resolution_required": divergent,
        },
    }


def build_external_object_bad_case(
    model: Mapping[str, object], context: Mapping[str, object]
) -> tuple[Mapping[str, object], Mapping[str, object]]:
    """Build ExperimentGuard's target-native protected-failure replay case."""

    bad_context = dict(context)
    outputs = _canonical(context.get("member_outputs"))
    if not isinstance(outputs, dict):
        raise ValueError("ExperimentGuard external-object bad upstream state is unavailable")
    logic = outputs.get("logicguard")
    if not isinstance(logic, dict):
        raise ValueError("ExperimentGuard external-object bad LogicGuard output is unavailable")
    edges = logic.get("argument_edges")
    if not isinstance(edges, list) or not edges or not isinstance(edges[0], dict):
        raise ValueError("ExperimentGuard external-object bad argument edge is unavailable")
    edges[0]["relation"] = "asserts_unlicensed_truth"
    bad_context["member_outputs"] = outputs
    return model, bad_context


def _replay_blueprint(material: object) -> tuple[str, dict[str, object]]:
    payload = _exact_mapping(
        material,
        {"spec_path", "spec_fingerprint"},
        "native blueprint input",
    )
    spec_path = Path(str(payload["spec_path"])).resolve()
    body = portable_native_material_bytes(
        member_id=NATIVE_OWNER_ID,
        material_fingerprint=str(payload["spec_fingerprint"]),
    )
    if body is None:
        if not spec_path.is_file():
            raise ValueError("ExperimentGuard frozen spec material is unavailable")
        body = spec_path.read_bytes()
    fingerprint = "sha256:" + hashlib.sha256(body).hexdigest()
    if fingerprint != payload["spec_fingerprint"]:
        raise ValueError("ExperimentGuard frozen spec material changed")
    spec = _load_spec_payload(json.loads(body.decode("utf-8")))
    result = check_blueprint(spec)
    return result.model_id, _canonical(result.to_dict())  # type: ignore[return-value]


def _expected_anchor(material: object):
    payload = _exact_mapping(
        material, {"spec_path", "spec_fingerprint"}, "native blueprint input"
    )
    body = portable_native_material_bytes(
        member_id=NATIVE_OWNER_ID,
        material_fingerprint=str(payload["spec_fingerprint"]),
    )
    spec = (
        _load_spec_payload(json.loads(body.decode("utf-8")))
        if body is not None
        else _load_spec(Path(str(payload["spec_path"])).resolve())
    )
    universe = spec.target_universe
    if universe is None or universe.target_authority is None:
        raise ValueError("ExperimentGuard native input has no expected target anchor")
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
    """Derive ExperimentGuard's current behavior denominator from its spec."""

    payload = _exact_mapping(
        native_input_material,
        {"spec_path", "spec_fingerprint"},
        "native blueprint input",
    )
    body = portable_native_material_bytes(
        member_id=NATIVE_OWNER_ID,
        material_fingerprint=str(payload["spec_fingerprint"]),
    )
    spec = (
        _load_spec_payload(json.loads(body.decode("utf-8")))
        if body is not None
        else _load_spec(Path(str(payload["spec_path"])).resolve())
    )
    spec_raw = spec.to_dict()
    anchor = _expected_anchor(payload)
    target_universe = (
        spec_raw.get("target_universe", {})
        if isinstance(spec_raw, Mapping)
        else {}
    )
    hierarchy = {
        native_model_id,
        *_declared_ids(spec_raw),
        *_declared_ids(replayed_result),
    }
    interfaces = {
        "experimentguard.interface:experiment-spec-to-blueprint-result",
        *_named_declared_ids(spec_raw, ("interface", "binding", "signal", "parameter")),
    }
    targets = {anchor.anchor_id, *_declared_ids(target_universe)}
    receipt_ids = tuple(sorted(set(str(item) for item in native_receipt_ids)))
    if not receipt_ids:
        raise ValueError("ExperimentGuard domain behavior manifest requires a native receipt")
    common = {
        "owner": NATIVE_OWNER_ID,
        "checker_entrypoint": f"{__name__}:evaluate_domain_behavior_transition",
        "checker_id": NATIVE_CHECKER_ID,
        "checker_version": NATIVE_CHECKER_VERSION,
        "result_fingerprint": result_fingerprint,
        "native_receipt_id": receipt_ids[0],
    }
    recommendation = recommend_experiments(spec)
    if not isinstance(target_universe, Mapping):
        raise ValueError("ExperimentGuard domain target universe is invalid")
    native_cases = target_universe.get("native_case_evidence", [])
    if not isinstance(native_cases, list):
        raise ValueError("ExperimentGuard native case evidence is invalid")
    good_rows = [
        item for item in native_cases
        if isinstance(item, Mapping) and item.get("case_kind") == "known_good"
    ]
    bad_rows = [
        item for item in native_cases
        if isinstance(item, Mapping) and item.get("case_kind") == "known_bad"
    ]
    if len(good_rows) != 1 or len(bad_rows) != 1:
        raise ValueError("ExperimentGuard domain behavior requires one exact good/bad case")
    good_evidence = good_rows[0]
    bad_evidence = bad_rows[0]
    predictions = list(spec_raw.get("hypothesis_predictions", []))
    design_blocks = list(spec_raw.get("design_blocks", []))
    domain_cases = (
        build_behavior_transition_case(
            case_id="case:experimentguard.finite-discriminating-recommendation",
            behavior_id="experimentguard.finite-discriminating-recommendation",
            input={
                "hypothesis_predictions": predictions,
                "candidate_experiment_ids": list(spec_raw.get("candidate_experiment_ids", [])),
                "candidate_conditions": [
                    {
                        "block_id": str(item.get("block_id", "")),
                        "candidate_experiment_id": str(item.get("candidate_experiment_id", "")),
                        "constraints": list(item.get("constraints", [])),
                        "procedure_steps": list(item.get("procedure_steps", [])),
                        "ports": list(item.get("ports", [])),
                    }
                    for item in design_blocks
                    if isinstance(item, Mapping)
                    and item.get("kind") == "candidate_experiment"
                ],
            },
            pre_state={
                "prior_open_gap_ids": list(spec_raw.get("prior_open_gap_ids", [])),
                "external_execution_status": "not_run",
            },
            permitted_output={
                "recommendation": recommendation.to_dict(),
                "prediction_matrix": {
                    str(item.get("hypothesis_id", "")): dict(item.get("outcomes_by_experiment", {}))
                    for item in predictions
                    if isinstance(item, Mapping)
                },
                "blueprint_gaps": list(replayed_result.get("gaps", [])),
                "layer_statuses": list(replayed_result.get("layer_statuses", [])),
            },
            post_state={
                "deepest_proven_layer": str(replayed_result.get("deepest_proven_layer", "")),
                "external_execution_status": str(replayed_result.get("external_execution_status", "not_run")),
                "claim_boundary": str(replayed_result.get("claim_boundary", "")),
            },
            effect=(
                "compare_declared_hypothesis_outcomes",
                "select_minimum_finite_discriminating_set",
                "preserve_undistinguished_hypothesis_pairs",
                "separate_recommendation_from_external_execution",
            ),
            protected_failure=str(bad_evidence.get("failure_class_id", "experiment-native-failure")),
            bad_mutation_path="permitted_output.recommendation",
            failure_class_id=str(bad_evidence.get("failure_class_id", "experiment-native-failure")),
            good_native_evidence=dict(good_evidence),
            bad_native_evidence=dict(bad_evidence),
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
    """Rerun ExperimentGuard and compare one finite recommendation projection."""

    if envelope.member_id != NATIVE_OWNER_ID or envelope.opaque_payload is None:
        raise ValueError("ExperimentGuard domain evaluation requires its opaque payload")
    raw = _exact_mapping(
        json.loads(envelope.opaque_payload.decode("utf-8")),
        {"schema_version", "experiment_request", "experiment_input", "blueprint_result"},
        "native-owner replay material",
    )
    native_input = _exact_mapping(
        raw["experiment_input"],
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
        raise ValueError("ExperimentGuard behavior manifest differs from native replay")
    canonical = next(
        (item for item in canonical_manifest.domain_behavior_cases if item.behavior_id == behavior_id),
        None,
    )
    if canonical is None:
        raise ValueError("ExperimentGuard domain behavior id is outside the denominator")
    return _compare_native_domain_transition(canonical, candidate_transition)


def replay_native_owner_attestation(
    envelope: MemberModelEnvelope, *, registry_identity: str
) -> NativeOwnerAttestation:
    if envelope.member_id != NATIVE_OWNER_ID or envelope.opaque_payload is None:
        raise ValueError("ExperimentGuard native-owner replay requires its opaque payload")
    from ..routing import native_owner_registry_identity

    if registry_identity != native_owner_registry_identity(NATIVE_OWNER_ID):
        raise ValueError("ExperimentGuard native-owner registry identity is stale or foreign")
    raw = _exact_mapping(
        json.loads(envelope.opaque_payload.decode("utf-8")),
        {"schema_version", "experiment_request", "experiment_input", "blueprint_result"},
        "native-owner replay material",
    )
    if raw["schema_version"] != NATIVE_OWNER_REPLAY_SCHEMA:
        raise ValueError("ExperimentGuard native-owner replay schema is not current")
    request = _exact_mapping(
        raw["experiment_request"],
        {"task_id", "operation", "claim_boundary", "material"},
        "replay request",
    )
    native_input = _exact_mapping(
        raw["experiment_input"],
        {"native_model_id", "model_fingerprint", "input_id", "material"},
        "replay input",
    )
    submitted_result = _exact_mapping(
        raw["blueprint_result"],
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
        or native_input["input_id"] != f"experimentguard-input:{_digest(native_input['material'])}"
        or envelope.expected_target_anchor_id != anchor.anchor_id
        or envelope.expected_target_anchor_fingerprint != anchor.anchor_fingerprint
        or dict(submitted_result) != expected_result
        or envelope.terminal_status != derived_terminal
        or tuple(sorted(envelope.open_gap_refs)) != (() if derived_terminal == "passed" else derived_gap_refs)
    ):
        raise ValueError("ExperimentGuard replay differs from the current native blueprint execution")

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
        raise ValueError("ExperimentGuard request does not bind its current behavior manifest")
    request_fingerprint = _digest(dict(request))
    input_fingerprint = _digest(dict(native_input))
    for receipt in envelope.native_receipt_refs:
        gaps = resolve_native_receipt_reference(receipt)
        if gaps or any(
            (
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
            )
        ):
            raise ValueError("ExperimentGuard native receipt does not replay exactly")
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
