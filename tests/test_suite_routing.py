from __future__ import annotations

from copy import deepcopy

from admission_fixtures import composition, member_task_facts, task_facts
from researchguard import MEMBER_IDS, SUITE_ID, __version__
from researchguard.routing import (
    RouteBinding,
    RouteComposition,
    TypedGap,
    bind_member_request,
    build_admission_set,
    create_handoff,
    select_member_request,
)
from researchguard.suite import suite_identity


def test_suite_identity_is_single_and_complete() -> None:
    identity = suite_identity()
    assert identity["suite_id"] == SUITE_ID
    assert identity["version"] == __version__ == "0.4.1"
    assert identity["members"] == list(MEMBER_IDS)
    assert identity["distribution"] == "researchguard"
    assert identity["console_script"] == "researchguard"
    assert identity["fingerprint"].startswith("sha256:")


def test_direct_member_binding_skips_umbrella() -> None:
    direct = bind_member_request("logicguard", ["validate", "argument.yaml"])
    assert isinstance(direct, RouteBinding)
    assert direct.native_owner_id == "logicguard"
    assert direct.machine_path == "researchguard.logic.cli:main"


def test_ambiguous_request_blocks_before_execution() -> None:
    result = bind_member_request(None, [])
    assert isinstance(result, TypedGap)
    assert result.code == "member-selection-required"


def test_selected_member_has_no_alternate_binding() -> None:
    result = bind_member_request("sourceguard", ["plan", "source.yaml"])
    assert isinstance(result, RouteBinding)
    assert result.primary_path_id == "primary:researchguard:source"


def test_routed_request_cannot_reenter_umbrella() -> None:
    result = bind_member_request(
        "traceguard", ["evaluate", "trace.yaml"], active_request_id="request:already-routed"
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


def test_source_bound_facts_select_each_exact_member() -> None:
    for member in MEMBER_IDS:
        argv = ["--help"]
        intent = f"intent:test:{member}"
        facts = member_task_facts(member, argv=argv, intent=intent)
        result = select_member_request(facts, argv, business_intent_id=intent)
        assert isinstance(result, RouteBinding)
        assert result.member_id == member


def test_program_derives_member_rows_without_caller_applicability() -> None:
    argv = ["plan", "source.yaml"]
    intent = "intent:source-discovery"
    facts = member_task_facts("sourceguard", argv=argv, intent=intent)
    payload = build_admission_set(facts, argv, business_intent_id=intent)
    rows = {row["member_id"]: row for row in payload["member_evidence"]}
    assert rows["sourceguard"]["applicability"] == "applicable"
    assert rows["sourceguard"]["matching_task_fact_ids"] == ["fact:0"]
    assert rows["logicguard"]["applicability"] == "not_applicable"
    assert all("applicability_evidence_refs" not in row for row in rows.values())


def test_context_does_not_create_second_primary_owner() -> None:
    argv = ["plan", "source.yaml"]
    intent = "intent:source-then-trace"
    facts = task_facts(
        argv=argv,
        intent=intent,
        primary_kind="source.primary_discovery",
        context_kinds=("trace.temporal_reconstruction",),
    )
    result = select_member_request(facts, argv, business_intent_id=intent)
    assert isinstance(result, RouteBinding)
    assert result.member_id == "sourceguard"


def test_irreducible_pair_requires_and_accepts_declarative_composition() -> None:
    argv = ["plan", "mixed-task.json"]
    intent = "intent:source-then-trace"
    plan = composition(
        ("sourceguard", ("source.primary.discovery",)),
        ("traceguard", ("trace.primary.reconstruction",)),
    )
    facts = task_facts(
        argv=argv,
        intent=intent,
        primary_kind="source.primary_discovery",
        additional_primary_kinds=("trace.temporal_reconstruction",),
        composition=plan,
    )
    result = select_member_request(facts, argv, business_intent_id=intent)
    assert isinstance(result, RouteComposition)
    assert result.member_ids == ("sourceguard", "traceguard")
    assert result.status == "composition_ready"


def test_irreducible_three_member_set_is_supported_without_run_all() -> None:
    argv = ["plan", "three-owner-task.json"]
    intent = "intent:source-trace-logic"
    plan = composition(
        ("sourceguard", ("source.primary.discovery",)),
        ("traceguard", ("trace.primary.reconstruction",)),
        ("logicguard", ("logic.primary.general-argument",)),
    )
    facts = task_facts(
        argv=argv,
        intent=intent,
        primary_kind="source.primary_discovery",
        additional_primary_kinds=(
            "trace.temporal_reconstruction",
            "logic.argument_structure",
        ),
        composition=plan,
    )
    result = select_member_request(facts, argv, business_intent_id=intent)
    assert isinstance(result, RouteComposition)
    assert result.member_ids == ("sourceguard", "traceguard", "logicguard")


def test_multiple_irreducible_responsibilities_without_plan_block() -> None:
    argv = ["plan", "mixed-task.json"]
    intent = "intent:missing-composition"
    facts = task_facts(
        argv=argv,
        intent=intent,
        primary_kind="source.primary_discovery",
        additional_primary_kinds=("trace.temporal_reconstruction",),
    )
    result = select_member_request(facts, argv, business_intent_id=intent)
    assert isinstance(result, TypedGap)
    assert result.code == "member-composition-required"


def test_composition_over_selection_blocks_when_one_member_suffices() -> None:
    argv = ["validate", "argument.yaml"]
    intent = "intent:logic-only"
    plan = composition(
        ("logicguard", ("logic.primary.general-argument",)),
        ("sourceguard", ("source.primary.discovery",)),
    )
    facts = task_facts(
        argv=argv,
        intent=intent,
        primary_kind="logic.argument_structure",
        composition=plan,
    )
    result = select_member_request(facts, argv, business_intent_id=intent)
    assert isinstance(result, TypedGap)
    assert result.code == "member-over-selection"


def test_composition_responsibility_conflict_blocks() -> None:
    argv = ["plan", "mixed-task.json"]
    intent = "intent:responsibility-conflict"
    plan = composition(
        ("sourceguard", ("source.primary.discovery",)),
        ("traceguard", ("source.primary.discovery",)),
    )
    facts = task_facts(
        argv=argv,
        intent=intent,
        primary_kind="source.primary_discovery",
        additional_primary_kinds=("trace.temporal_reconstruction",),
        composition=plan,
    )
    result = select_member_request(facts, argv, business_intent_id=intent)
    assert isinstance(result, TypedGap)
    assert result.code == "member-composition-invalid"
    assert "responsibility" in result.message


def test_composition_missing_order_dependency_blocks() -> None:
    argv = ["plan", "mixed-task.json"]
    intent = "intent:missing-order"
    plan = composition(
        ("sourceguard", ("source.primary.discovery",)),
        ("traceguard", ("trace.primary.reconstruction",)),
    )
    plan["steps"][1]["depends_on_step_ids"] = []
    facts = task_facts(
        argv=argv,
        intent=intent,
        primary_kind="source.primary_discovery",
        additional_primary_kinds=("trace.temporal_reconstruction",),
        composition=plan,
    )
    result = select_member_request(facts, argv, business_intent_id=intent)
    assert isinstance(result, TypedGap)
    assert result.code == "member-composition-invalid"
    assert "dependency" in result.message


def test_composition_field_owner_conflict_blocks() -> None:
    argv = ["plan", "mixed-task.json"]
    intent = "intent:field-owner-conflict"
    plan = composition(
        ("sourceguard", ("source.primary.discovery",)),
        ("traceguard", ("trace.primary.reconstruction",)),
    )
    plan["field_owners"].append(
        {"field_id": "field:1:2:artifact", "owner_step_id": "step:2:traceguard"}
    )
    facts = task_facts(
        argv=argv,
        intent=intent,
        primary_kind="source.primary_discovery",
        additional_primary_kinds=("trace.temporal_reconstruction",),
        composition=plan,
    )
    result = select_member_request(facts, argv, business_intent_id=intent)
    assert isinstance(result, TypedGap)
    assert result.code == "member-composition-invalid"
    assert "exactly one owner" in result.message


def test_placeholder_source_span_blocks() -> None:
    argv = ["plan", "source.yaml"]
    intent = "intent:placeholder"
    facts = member_task_facts("sourceguard", argv=argv, intent=intent)
    facts["facts"][0]["source_span"] = {
        "source_id": "placeholder",
        "start": 0,
        "end": 11,
        "quote": "placeholder",
    }
    result = select_member_request(facts, argv, business_intent_id=intent)
    assert isinstance(result, TypedGap)
    assert result.code == "task-facts-invalid"
    assert "actual request source" in result.message


def test_generic_forbidden_clearance_is_not_a_current_field() -> None:
    argv = ["plan", "source.yaml"]
    intent = "intent:generic-clear"
    facts = member_task_facts("sourceguard", argv=argv, intent=intent)
    facts["forbidden_status"] = "clear"
    result = select_member_request(facts, argv, business_intent_id=intent)
    assert isinstance(result, TypedGap)
    assert result.code == "task-facts-invalid"
    assert "unknown fields" in result.message


def test_missing_forbidden_condition_review_blocks() -> None:
    argv = ["plan", "source.yaml"]
    intent = "intent:missing-review"
    facts = member_task_facts("sourceguard", argv=argv, intent=intent)
    facts["forbidden_reviews"].pop()
    result = select_member_request(facts, argv, business_intent_id=intent)
    assert isinstance(result, TypedGap)
    assert result.code == "task-facts-invalid"
    assert "inventory mismatch" in result.message


def test_contradictory_forbidden_review_blocks() -> None:
    argv = ["plan", "source.yaml"]
    intent = "intent:contradictory-review"
    facts = task_facts(
        argv=argv,
        intent=intent,
        primary_kind="source.primary_discovery",
        context_kinds=("logic.silent_external_search",),
    )
    bad = deepcopy(facts)
    row = next(
        row
        for row in bad["forbidden_reviews"]
        if row["member_id"] == "logicguard"
        and row["condition_id"] == "logic.forbidden.silent-external-search"
    )
    row["disposition"] = "absent"
    result = select_member_request(bad, argv, business_intent_id=intent)
    assert isinstance(result, TypedGap)
    assert result.code == "task-facts-invalid"
    assert "contradicts task facts" in result.message


def test_stale_task_facts_block() -> None:
    argv = ["plan", "source.yaml"]
    intent = "intent:stale"
    facts = member_task_facts("sourceguard", argv=argv, intent=intent)
    facts["request_fingerprint"] = "sha256:" + "0" * 64
    result = select_member_request(facts, argv, business_intent_id=intent)
    assert isinstance(result, TypedGap)
    assert result.code == "task-facts-invalid"
    assert "exact current request" in result.message


def test_unknown_primary_kind_blocks_without_lexical_fallback() -> None:
    argv = ["do", "something"]
    intent = "intent:unknown"
    facts = task_facts(
        argv=argv,
        intent=intent,
        primary_kind="source.primary_discovery",
    )
    facts["facts"][0]["kind"] = "unknown.keyword.guess"
    result = select_member_request(facts, argv, business_intent_id=intent)
    assert isinstance(result, TypedGap)
    assert result.code == "task-facts-invalid"
    assert "unknown kinds" in result.message


def test_known_but_unowned_primary_responsibility_has_zero_match() -> None:
    argv = ["recommend", "tests.json"]
    intent = "intent:software-test-selection"
    facts = task_facts(
        argv=argv,
        intent=intent,
        primary_kind="software.test_selection",
    )
    result = select_member_request(facts, argv, business_intent_id=intent)
    assert isinstance(result, TypedGap)
    assert result.code == "member-admission-no-match"
