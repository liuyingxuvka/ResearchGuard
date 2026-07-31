from __future__ import annotations

from researchguard import MEMBER_IDS, SUITE_ID, __version__
from researchguard.experiment.admission import author_admission_evidence as experiment_evidence
from researchguard.logic.admission import author_admission_evidence as logic_evidence
from researchguard.source.admission import author_admission_evidence as source_evidence
from researchguard.trace.admission import author_admission_evidence as trace_evidence
from researchguard.routing import (
    ADMISSION_SET_SCHEMA,
    RouteBinding,
    TypedGap,
    bind_member_request,
    create_handoff,
    request_fingerprint,
    select_member_request,
)
from researchguard.suite import suite_identity


def test_suite_identity_is_single_and_complete() -> None:
    identity = suite_identity()
    assert identity["suite_id"] == SUITE_ID
    assert identity["version"] == __version__ == "0.4.0"
    assert identity["members"] == list(MEMBER_IDS)
    assert identity["distribution"] == "researchguard"
    assert identity["console_script"] == "researchguard"
    assert identity["fingerprint"].startswith("sha256:")


def test_direct_and_umbrella_bind_the_same_native_request() -> None:
    direct = bind_member_request(
        "logicguard",
        ["validate", "argument.yaml"],
    )
    umbrella = bind_member_request(
        "logicguard",
        ["validate", "argument.yaml"],
    )
    assert isinstance(direct, RouteBinding)
    assert direct == umbrella
    assert direct.native_owner_id == "logicguard"
    assert direct.machine_path == "researchguard.logic.cli:main"


def test_ambiguous_request_blocks_before_execution() -> None:
    result = bind_member_request(None, [])
    assert isinstance(result, TypedGap)
    assert result.code == "member-selection-required"


def test_selected_member_has_no_alternate_binding() -> None:
    result = bind_member_request("sourceguard", ["plan", "source.yaml"])
    assert isinstance(result, RouteBinding)
    assert result.member_id == "sourceguard"
    assert result.primary_path_id == "primary:researchguard:source"


def test_experiment_member_is_recommendation_owner() -> None:
    result = bind_member_request(
        "experimentguard",
        ["recommend", "experiment.json"],
    )
    assert isinstance(result, RouteBinding)
    assert result.primary_path_id == "primary:researchguard:experiment"
    assert result.machine_path == "researchguard.experiment.cli:main"


def test_routed_request_cannot_reenter_umbrella() -> None:
    result = bind_member_request(
        "traceguard",
        ["evaluate", "trace.yaml"],
        active_request_id="request:already-routed",
    )
    assert isinstance(result, TypedGap)
    assert result.code == "researchguard-recursion"


def test_handoff_waits_for_explicit_outer_owner() -> None:
    binding = bind_member_request("sourceguard", ["plan", "source.yaml"])
    assert isinstance(binding, RouteBinding)
    handoff = create_handoff(
        binding,
        target_member_id="traceguard",
        handoff_kind="evidence-anchor-to-trace-seed",
        payload={"artifact": "source.yaml"},
    )
    assert handoff.status == "awaiting_owner"
    assert handoff.target_member_id == "traceguard"


def _admission_set(*, admitted: tuple[str, ...] = ("sourceguard",)):
    argv = ["plan", "source.yaml"]
    intent = "intent:source-discovery"
    digest = request_fingerprint(argv, business_intent_id=intent)
    builders = {
        "logicguard": logic_evidence,
        "sourceguard": source_evidence,
        "traceguard": trace_evidence,
        "experimentguard": experiment_evidence,
    }
    rows = []
    for member, builder in builders.items():
        rows.append(
            builder(
                request_fingerprint=digest,
                applicability="applicable" if member in admitted else "not_applicable",
                forbidden_status="clear",
                applicability_evidence_refs=(f"native:{member}:applicability",),
                forbidden_evidence_refs=(f"native:{member}:forbidden-review",),
            )
        )
    return {"schema_version": ADMISSION_SET_SCHEMA, "member_evidence": rows}, argv, intent


def test_member_authored_admission_selects_exactly_one() -> None:
    payload, argv, intent = _admission_set()
    result = select_member_request(payload, argv, business_intent_id=intent)
    assert isinstance(result, RouteBinding)
    assert result.member_id == "sourceguard"


def test_two_admitted_members_block_without_list_order_fallback() -> None:
    payload, argv, intent = _admission_set(admitted=("sourceguard", "logicguard"))
    result = select_member_request(payload, argv, business_intent_id=intent)
    assert isinstance(result, TypedGap)
    assert result.code == "member-admission-ambiguous"


def test_stale_or_missing_member_admission_blocks() -> None:
    payload, argv, intent = _admission_set()
    payload["member_evidence"][0]["request_fingerprint"] = "sha256:" + "0" * 64
    result = select_member_request(payload, argv, business_intent_id=intent)
    assert isinstance(result, TypedGap)
    assert result.code == "admission-request-stale"
