from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import replace
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

import researchguard.cli as root_cli
import researchguard.model_envelope as envelope_transport

from admission_fixtures import (
    composition,
    member_native_envelope,
    native_owner_attestations,
    task_facts,
)
from researchguard.model_envelope import (
    HandoffFieldContract,
    MemberModelEnvelope,
    NativeReceiptReference,
    ResponsibilitySpan,
    payload_fingerprint,
)
from researchguard.routing import (
    MEMBER_NATIVE_CHECKERS,
    RouteComposition,
    TypedGap,
    composition_impact,
    native_owner_registry_identity,
    reverse_trace_composition,
    select_member_request,
)


ARGV = ["plan", "mixed-task.json"]
INTENT = "intent:opaque-envelope-tests"


_RESULT_FIELD_BY_MEMBER = {
    "logicguard": "qualification_result",
    "sourceguard": "qualification_result",
    "traceguard": "inference_result",
    "experimentguard": "blueprint_result",
}


def _with_invented_native_receipt(
    raw: dict[str, object], receipt_id: str
) -> MemberModelEnvelope:
    envelope = MemberModelEnvelope.from_dict(raw)
    assert envelope.opaque_payload is not None
    payload = json.loads(envelope.opaque_payload.decode("utf-8"))
    result = payload[_RESULT_FIELD_BY_MEMBER[envelope.member_id]]
    result["native_receipt_ids"] = [receipt_id]
    result_body = json.dumps(
        result, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    result_fingerprint = "sha256:" + hashlib.sha256(result_body).hexdigest()
    native_input = next(
        value
        for key, value in payload.items()
        if key.endswith("_input") and isinstance(value, dict)
    )
    owner_module = importlib.import_module(MEMBER_NATIVE_CHECKERS[envelope.member_id][2])
    manifest = getattr(owner_module, "build_native_behavior_manifest")(
        native_model_id=envelope.native_model_id,
        model_fingerprint=envelope.model_fingerprint,
        native_input_material=native_input["material"],
        replayed_result=result["material"],
        native_receipt_ids=(receipt_id,),
        result_fingerprint=result_fingerprint,
        terminal_status=envelope.terminal_status,
    )
    request = next(
        value
        for key, value in payload.items()
        if key.endswith("_request") and isinstance(value, dict)
    )
    request["material"]["behavior_manifest_fingerprint"] = (
        manifest.expected_fingerprint
    )
    body = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    request_body = json.dumps(
        request, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    request_fingerprint = "sha256:" + hashlib.sha256(request_body).hexdigest()
    current_receipt = envelope.native_receipt_refs[0]
    invented = replace(
        current_receipt,
        receipt_id=receipt_id,
        request_fingerprint=request_fingerprint,
        result_fingerprint=result_fingerprint,
        behavior_manifest_fingerprint=manifest.expected_fingerprint,
    )
    invented_body = json.dumps(
        invented.receipt_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    invented_fingerprint = "sha256:" + hashlib.sha256(invented_body).hexdigest()
    locator_prefix = current_receipt.producer_locator.rsplit("/", 1)[0] + "/"
    invented = replace(
        invented,
        producer_locator=locator_prefix + invented_fingerprint.removeprefix("sha256:"),
        receipt_fingerprint=invented_fingerprint,
    )
    return replace(
        envelope,
        native_receipt_refs=(invented,),
        behavior_manifest=manifest,
        opaque_payload=body,
        payload_fingerprint=payload_fingerprint(body),
    )


def _plan(*members: tuple[str, tuple[str, ...]]) -> dict[str, object]:
    return composition(*members)


def _two_member_plan() -> dict[str, object]:
    return _plan(
        ("sourceguard", ("source.primary.discovery",)),
        ("traceguard", ("trace.primary.reconstruction",)),
    )


def _block_trace_envelope(plan: dict[str, object]) -> None:
    current = MemberModelEnvelope.from_dict(plan["member_envelopes"][1])
    assert current.opaque_payload is not None
    payload = json.loads(current.opaque_payload.decode("utf-8"))
    input_material = deepcopy(payload["trace_input"]["material"])
    # Make the member-native interface receipt incomplete.  The helper then
    # asks TraceGuard's real checker to derive the blocked result; it does not
    # manufacture a caller-selected terminal.
    input_material["model"]["interface_bindings"][0]["receipt_refs"] = []
    blocked = member_native_envelope(
        plan["member_envelopes"][1],
        receipt_id="receipt:traceguard:blocked:missing-interface-evidence",
        input_material=input_material,
    )
    plan["member_envelopes"][1] = blocked.to_dict()
    contract = HandoffFieldContract.from_dict(plan["handoff_field_contracts"][0])
    acknowledgement = replace(
        contract.acknowledgements[0],
        native_receipt_id=blocked.native_receipt_refs[0].receipt_id,
        native_receipt_fingerprint=blocked.native_receipt_refs[0].receipt_fingerprint,
    )
    plan["handoff_field_contracts"][0] = replace(
        contract, acknowledgements=(acknowledgement,)
    ).to_dict()


def _route(
    plan: dict[str, object], *, with_native_attestations: bool = True
) -> RouteComposition | TypedGap:
    facts = task_facts(
        argv=ARGV,
        intent=INTENT,
        primary_kind="source.primary_discovery",
        additional_primary_kinds=("trace.temporal_reconstruction",),
        composition=plan,
    )
    return select_member_request(
        facts,
        ARGV,
        business_intent_id=INTENT,
        native_owner_attestations=(
            native_owner_attestations(plan) if with_native_attestations else ()
        ),
    )


def _blocked_route_composition() -> RouteComposition:
    return RouteComposition(
        status="composition_blocked",
        request_id="request:blocked-test",
        business_intent_id=INTENT,
        task_id="task:blocked-test",
        member_ids=("sourceguard", "traceguard"),
        steps=(),
        handoffs=(),
        field_owners=(),
        member_envelopes=(),
        native_owner_attestations=(),
        handoff_field_contracts=(),
        stale_step_ids=("step:2:traceguard",),
        blocking_member_ids=("traceguard",),
        composition_gaps=(
            {
                "code": "member-terminal-blocked",
                "object_id": "step:2:traceguard",
                "detail": "missing-interface-native-receipt",
            },
        ),
        composition_fingerprint="sha256:" + ("1" * 64),
        overall_claim_boundary="Blocked composition transports no partial native result.",
        suite_version="test",
        suite_fingerprint="sha256:" + ("2" * 64),
    )


def test_opaque_envelope_accepts_non_json_bytes_and_can_omit_payload_transport() -> None:
    payload = b"\xff\x00{definitely-not-member-json"
    quote = "opaque member responsibility"
    current = MemberModelEnvelope.from_dict(
        _plan(("logicguard", ("logic.argument.structure",)))["member_envelopes"][0]
    )
    envelope = replace(
        current,
        envelope_id="envelope:logicguard:opaque",
        native_schema_id="logic-native-schema",
        native_schema_version="current",
        payload_fingerprint=payload_fingerprint(payload),
        input_field_ids=(),
        output_field_ids=(),
        open_gap_refs=(),
        terminal_status="passed",
        claim_boundary="LogicGuard alone owns interpretation of this payload.",
        responsibility_spans=(ResponsibilitySpan("request:user", 0, len(quote), quote),),
        opaque_payload=payload,
    )
    loaded = MemberModelEnvelope.from_dict(envelope.to_dict())
    assert loaded.opaque_payload == payload
    transport_only = envelope.to_dict(include_payload=False)
    assert "opaque_payload_b64" not in transport_only
    assert MemberModelEnvelope.from_dict(transport_only).opaque_payload is None
    assert MemberModelEnvelope.from_dict(transport_only).envelope_fingerprint == envelope.envelope_fingerprint


@pytest.mark.parametrize("defect", ("missing", "stale", "foreign", "payload"))
def test_missing_stale_foreign_or_digest_mismatched_envelope_blocks(defect: str) -> None:
    raw = deepcopy(_two_member_plan()["member_envelopes"][0])
    if defect == "missing":
        raw.pop("native_schema_version")
    elif defect == "stale":
        raw["envelope_fingerprint"] = "sha256:" + "0" * 64
    elif defect == "foreign":
        raw["member_id"] = "foreignguard"
    else:
        raw["opaque_payload_b64"] = base64.b64encode(b"changed").decode("ascii")
    with pytest.raises(ValueError):
        MemberModelEnvelope.from_dict(raw)


def test_duplicate_producer_contract_is_rejected_before_composition_ready() -> None:
    plan = _two_member_plan()
    contract = HandoffFieldContract.from_dict(plan["handoff_field_contracts"][0])
    duplicate = replace(contract, handoff_id="handoff:duplicate-owner")
    plan["handoff_field_contracts"].append(duplicate.to_dict())
    result = _route(plan)
    assert isinstance(result, TypedGap)
    assert result.code == "member-composition-invalid"
    assert "exactly one current contract" in result.message


def test_missing_consumer_acknowledgement_and_member_terminal_remain_visible() -> None:
    plan = _two_member_plan()
    contract = HandoffFieldContract.from_dict(plan["handoff_field_contracts"][0])
    plan["handoff_field_contracts"][0] = replace(contract, acknowledgements=()).to_dict()
    result = _route(plan)
    assert isinstance(result, RouteComposition)
    assert result.status == "composition_blocked"
    assert result.stale_step_ids == ("step:2:traceguard",)
    assert result.composition_gaps[0]["code"] == "consumer-acknowledgement-missing"

    terminal_plan = _two_member_plan()
    _block_trace_envelope(terminal_plan)
    terminal = _route(terminal_plan)
    assert isinstance(terminal, RouteComposition)
    assert terminal.status == "composition_blocked"
    assert terminal.blocking_member_ids == ("traceguard",)
    assert "missing-interface-native-receipt:interface:s1->e1" in terminal.composition_gaps[0]["detail"]


def test_composition_impact_is_exact_transitive_and_atomically_suppresses_unknown() -> None:
    plan = _plan(
        ("sourceguard", ("source.primary.discovery",)),
        ("traceguard", ("trace.primary.reconstruction",)),
        ("logicguard", ("logic.primary.general-argument",)),
    )
    facts = task_facts(
        argv=ARGV,
        intent=INTENT,
        primary_kind="source.primary_discovery",
        additional_primary_kinds=("trace.temporal_reconstruction", "logic.argument_structure"),
        composition=plan,
    )
    result = select_member_request(
        facts,
        ARGV,
        business_intent_id=INTENT,
        native_owner_attestations=native_owner_attestations(plan),
    )
    assert isinstance(result, RouteComposition)
    changed_field_fingerprint = result.handoff_field_contracts[0]["payload_fingerprint"]
    impact = composition_impact(result, [changed_field_fingerprint])
    assert impact["affected_step_ids"] == ["step:2:traceguard", "step:3:logicguard"]
    assert impact["unaffected_step_ids"] == ["step:1:sourceguard"]
    assert impact["run_all_selected"] is False

    blocked = composition_impact(result, [changed_field_fingerprint, "foreign:unowned"])
    assert blocked["unknown_ownership"] is True
    assert blocked["partial_result_suppressed"] is True
    assert blocked["affected_step_ids"] == []
    assert blocked["unaffected_step_ids"] == []


def test_reverse_trace_stops_at_native_receipts_and_rejects_empty_terminal() -> None:
    result = _route(_two_member_plan())
    assert isinstance(result, RouteComposition)
    trace = reverse_trace_composition(result, "overall")
    assert trace["payload_interpreted"] is False
    assert trace["native_semantics_interpreted"] is False
    assert {item["trace_stops_at"] for item in trace["steps"]} == {"native_receipt_boundary"}
    assert all("opaque_payload_b64" not in item["envelope"] for item in trace["steps"])
    assert all(item["envelope"]["native_receipt_refs"] for item in trace["steps"])
    with pytest.raises(ValueError, match="no declared owner"):
        reverse_trace_composition(result, "claim-boundary:missing")


def test_caller_self_reported_passed_envelopes_are_not_native_attestation() -> None:
    assert not hasattr(envelope_transport, "issue_native_owner_attestation")
    result = _route(_two_member_plan(), with_native_attestations=False)
    assert isinstance(result, RouteComposition)
    assert result.status == "composition_blocked"
    assert {item["code"] for item in result.composition_gaps} == {
        "native-owner-attestation-missing"
    }


@pytest.mark.parametrize(
    ("member_id", "responsibility"),
    (
        ("logicguard", "logic.primary.general-argument"),
        ("sourceguard", "source.primary.discovery"),
        ("traceguard", "trace.primary.reconstruction"),
        ("experimentguard", "experiment.primary.discrimination"),
    ),
)
def test_member_owner_replays_real_checker_and_rejects_resigned_fake_summary(
    member_id: str,
    responsibility: str,
) -> None:
    """A caller cannot replace the native result, even after re-signing it.

    ``member_native_envelope`` deliberately recomputes every transport and
    receipt hash around the submitted result.  The member owner must still
    execute its real blueprint checker over the declared input and compare the
    complete result, rather than trusting that internally consistent carrier.
    """

    raw = _plan((member_id, (responsibility,)))["member_envelopes"][0]
    with pytest.raises(
        ValueError,
        match="immutable native receipt identity is already bound",
    ):
        member_native_envelope(
            raw,
            result_material={"status": "complete", "gap_ids": []},
        )


@pytest.mark.parametrize(
    ("member_id", "responsibility"),
    (
        ("logicguard", "logic.primary.general-argument"),
        ("sourceguard", "source.primary.discovery"),
        ("traceguard", "trace.primary.reconstruction"),
        ("experimentguard", "experiment.primary.discrimination"),
    ),
)
def test_member_owner_rejects_resigned_caller_selected_incomplete_terminal(
    member_id: str,
    responsibility: str,
) -> None:
    raw = _plan((member_id, (responsibility,)))["member_envelopes"][0]
    with pytest.raises(
        ValueError,
        match="immutable native receipt identity is already bound",
    ):
        member_native_envelope(
            raw,
            terminal_status="blocked",
            open_gap_refs=("caller-selected:gap",),
            result_material={
                "status": "incomplete",
                "gaps": [{"code": "caller-selected", "object_id": "gap"}],
            },
        )


@pytest.mark.parametrize(
    ("member_id", "responsibility"),
    (
        ("logicguard", "logic.primary.general-argument"),
        ("sourceguard", "source.primary.discovery"),
        ("traceguard", "trace.primary.reconstruction"),
        ("experimentguard", "experiment.primary.discrimination"),
    ),
)
def test_member_owner_rejects_never_published_native_receipt_id(
    member_id: str,
    responsibility: str,
) -> None:
    raw = _plan((member_id, (responsibility,)))["member_envelopes"][0]
    invented = _with_invented_native_receipt(
        raw, f"receipt:caller-invented:{member_id}:never-published"
    )
    _checker_id, _checker_version, module_name, function_name = (
        MEMBER_NATIVE_CHECKERS[member_id]
    )
    checker = getattr(importlib.import_module(module_name), function_name)
    with pytest.raises(ValueError, match="native receipt does not replay exactly"):
        checker(
            invented,
            registry_identity=native_owner_registry_identity(member_id),
        )


def test_real_two_member_composition_blocks_never_published_receipt() -> None:
    plan = _two_member_plan()
    source = _with_invented_native_receipt(
        plan["member_envelopes"][0],
        "receipt:caller-invented:sourceguard:never-published",
    )
    plan["member_envelopes"][0] = source.to_dict()
    plan["steps"][1]["consumed_envelope_fingerprints"] = [
        {
            "envelope_id": source.envelope_id,
            "envelope_fingerprint": source.envelope_fingerprint,
        }
    ]
    contract = HandoffFieldContract.from_dict(plan["handoff_field_contracts"][0])
    plan["handoff_field_contracts"][0] = replace(
        contract,
        producer_envelope_fingerprint=source.envelope_fingerprint,
        producer_native_receipt_id=source.native_receipt_refs[0].receipt_id,
        producer_native_receipt_fingerprint=source.native_receipt_refs[0].receipt_fingerprint,
    ).to_dict()
    result = _route(plan, with_native_attestations=False)
    assert isinstance(result, RouteComposition)
    assert result.status == "composition_blocked"
    assert "sourceguard" in result.blocking_member_ids
    assert {
        item["code"] for item in result.composition_gaps
    } >= {"native-receipt-producer-signature-invalid"}


def test_fresh_process_rejects_all_caller_forged_self_hashed_attestations() -> None:
    """A structurally valid caller hash is not a member-native replay result."""

    repository = Path(__file__).resolve().parents[1]
    child = textwrap.dedent(
        """
        import json

        from admission_fixtures import composition, task_facts
        from researchguard.model_envelope import MemberModelEnvelope, NativeOwnerAttestation
        from researchguard.routing import (
            MEMBER_BINDINGS,
            MEMBER_NATIVE_CHECKERS,
            native_owner_registry_identity,
            select_member_request,
        )

        argv = ["plan", "mixed-task.json"]
        intent = "intent:fresh-process-forgery"
        plan = composition(
            ("sourceguard", ("source.primary.discovery",)),
            ("traceguard", ("trace.primary.reconstruction",)),
        )
        candidates = []
        for index, raw in enumerate(plan["member_envelopes"], start=1):
            envelope = MemberModelEnvelope.from_dict(raw)
            checker_id, checker_version, _module, _function = MEMBER_NATIVE_CHECKERS[
                envelope.member_id
            ]
            forged = NativeOwnerAttestation(
                attestation_id=f"attestation:caller-forged:{envelope.member_id}",
                member_id=envelope.member_id,
                native_owner_id=MEMBER_BINDINGS[envelope.member_id][0],
                checker_id=checker_id,
                checker_version=checker_version,
                registry_identity=native_owner_registry_identity(envelope.member_id),
                task_id=envelope.task_id,
                envelope_id=envelope.envelope_id,
                envelope_fingerprint=envelope.envelope_fingerprint,
                native_model_id=envelope.native_model_id,
                model_fingerprint=envelope.model_fingerprint,
                expected_target_anchor_id=envelope.expected_target_anchor_id,
                expected_target_anchor_fingerprint=envelope.expected_target_anchor_fingerprint,
                request_fingerprint="sha256:" + str(index) * 64,
                input_fingerprint="sha256:" + str(index + 2) * 64,
                result_fingerprint="sha256:" + str(index + 4) * 64,
                native_receipt_refs=envelope.native_receipt_refs,
                terminal_status=envelope.terminal_status,
            )
            candidates.append(forged.to_dict())
        facts = task_facts(
            argv=argv,
            intent=intent,
            primary_kind="source.primary_discovery",
            additional_primary_kinds=("trace.temporal_reconstruction",),
            composition=plan,
        )
        result = select_member_request(
            facts,
            argv,
            business_intent_id=intent,
            native_owner_attestations=candidates,
        )
        print(json.dumps({
            "status": result.status,
            "blocking_member_ids": list(result.blocking_member_ids),
            "gap_codes": sorted(item["code"] for item in result.composition_gaps),
        }))
        """
    )
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(repository / "src"), str(repository / "tests"))
    )
    completed = subprocess.run(
        [sys.executable, "-B", "-c", child],
        cwd=repository,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "composition_blocked"
    assert result["blocking_member_ids"] == ["sourceguard", "traceguard"]
    assert result["gap_codes"] == [
        "native-owner-attestation-not-current",
        "native-owner-attestation-not-current",
    ]


def test_blocked_composition_reverse_trace_preserves_top_level_terminal() -> None:
    plan = _two_member_plan()
    _block_trace_envelope(plan)
    result = _route(plan)
    assert isinstance(result, RouteComposition)
    assert result.status == "composition_blocked"
    trace = reverse_trace_composition(result, "overall")
    assert trace["composition_status"] == "composition_blocked"
    assert trace["blocking_member_ids"] == ["traceguard"]
    assert trace["composition_gaps"]
    assert trace["trace_status"] == "incomplete"
    assert trace["partial_result_suppressed"] is True
    assert trace["steps"] == []
    assert trace["handoff_fields"] == []


def test_blocked_composition_impact_is_atomic_before_dependency_projection() -> None:
    result = _blocked_route_composition()

    impact = composition_impact(
        result,
        ["field:changed-but-unqualified"],
    )

    assert impact["qualification_status"] == "composition_blocked"
    assert impact["blocking_member_ids"] == ["traceguard"]
    assert impact["composition_gaps"]
    assert impact["partial_result_suppressed"] is True
    assert impact["affected_step_ids"] == []
    assert impact["affected_handoff_field_ids"] == []
    assert impact["affected_claim_boundary_ids"] == []
    assert impact["unaffected_step_ids"] == []


@pytest.mark.parametrize(
    ("operation_args", "result_key"),
    [
        (("--changed-id", "field:any"), "affected_step_ids"),
        (("--reverse-trace-output", "unknown-before-qualification"), "steps"),
    ],
)
def test_blocked_composition_cli_returns_non_success_without_partial_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    operation_args: tuple[str, str],
    result_key: str,
) -> None:
    task_facts_path = tmp_path / "task-facts.json"
    task_facts_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        root_cli,
        "select_member_request",
        lambda *_args, **_kwargs: _blocked_route_composition(),
    )

    exit_code = root_cli._run_umbrella(
        [
            "--business-intent-id",
            INTENT,
            "--task-facts",
            str(task_facts_path),
            *operation_args,
            "--",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 3
    assert payload["composition_status"] == "composition_blocked"
    assert payload["partial_result_suppressed"] is True
    assert payload[result_key] == []
