from __future__ import annotations

from researchguard import MEMBER_IDS, SUITE_ID, __version__
from researchguard.routing import RouteBinding, TypedGap, bind_member_request, create_handoff
from researchguard.suite import suite_identity


def test_suite_identity_is_single_and_complete() -> None:
    identity = suite_identity()
    assert identity["suite_id"] == SUITE_ID
    assert identity["version"] == __version__ == "0.1.0"
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

