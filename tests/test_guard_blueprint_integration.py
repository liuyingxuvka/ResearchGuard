from __future__ import annotations

import inspect
from admission_fixtures import (
    composition,
    native_owner_attestations,
    task_facts,
)
from experiment.test_blueprint_design import _spec
from logic.test_blueprint_interfaces import _bindings, _inventory, _model
from source.test_blueprint_graph import _current_native_universe, _state
from trace.test_blueprint_hierarchy import (
    _current_model,
    _purpose_bound_model,
    _qualified_universe,
    _receipt,
)
from researchguard.experiment import check_blueprint as check_experiment_blueprint
from researchguard.logic import check_blueprint as check_logic_blueprint
from researchguard.model_envelope import HandoffFieldContract, MemberModelEnvelope
from researchguard.source.blueprint import check_blueprint as check_source_blueprint
from researchguard.trace.blueprint import check_blueprint as check_trace_blueprint
from researchguard.routing import (
    RouteComposition,
    composition_impact,
    reverse_trace_composition,
    select_member_request,
)
import researchguard.model_envelope as envelope_module
import researchguard.routing as routing_module

def test_all_four_native_blueprints_feed_opaque_transport_without_shared_solver(tmp_path) -> None:
    experiment = _spec()
    experiment_result = check_experiment_blueprint(experiment)
    assert experiment_result.status == "complete"

    logic_model = _model()
    logic_inventory = _inventory()
    logic_result = check_logic_blueprint(
        logic_model, logic_inventory, _bindings(logic_inventory)
    )
    assert logic_result.status == "incomplete"
    assert logic_result.native_depth_status == "not_run"
    assert any(item.code == "native-depth-not-run" for item in logic_result.gaps)

    source_root = tmp_path / "source"
    trace_root = tmp_path / "trace"
    source_root.mkdir()
    trace_root.mkdir()
    source_state = _state()
    source_universe, source_contract = _current_native_universe(source_state, source_root)
    source_result = check_source_blueprint(
        source_state, source_universe, contract_path=str(source_contract)
    )
    assert source_result.status == "complete"

    trace_model, trace_candidate = _purpose_bound_model(_current_model(), trace_root)
    trace_receipt = _receipt(trace_model)
    trace_result = check_trace_blueprint(
        trace_model,
        trace_receipt,
        _qualified_universe(trace_model),
        candidate_path=str(trace_candidate),
    )
    assert trace_result.status == "complete"

    # ResearchGuard's transport owner imports admission contracts but no member
    # blueprint, schema, inference, solver, or validator implementation.
    transport_source = inspect.getsource(envelope_module) + inspect.getsource(routing_module)
    for forbidden in (
            "from .experiment.blueprint", "from .logic.blueprint",
            "from .source.blueprint", "from .trace.blueprint",
            ".inference", "recommend_experiments(",
    ):
        assert forbidden not in transport_source


def test_current_source_to_trace_handoff_invalidates_only_declared_downstream(tmp_path) -> None:
    source_root = tmp_path / "source"
    trace_root = tmp_path / "trace"
    source_root.mkdir()
    trace_root.mkdir()
    source_state = _state()
    source_universe, source_contract = _current_native_universe(source_state, source_root)
    source_result = check_source_blueprint(
        source_state, source_universe, contract_path=str(source_contract)
    )
    trace_model, trace_candidate = _purpose_bound_model(_current_model(), trace_root)
    trace_receipt = _receipt(trace_model)
    trace_result = check_trace_blueprint(
        trace_model,
        trace_receipt,
        _qualified_universe(trace_model),
        candidate_path=str(trace_candidate),
    )

    plan = composition(
        ("sourceguard", ("source.primary.discovery",)),
        ("traceguard", ("trace.primary.reconstruction",)),
    )
    # The composition fixture now carries the exact member-owned raw inputs and
    # full native results.  Rewrapping a blueprint summary would reintroduce the
    # caller-authored authority that the owner replay contract forbids.
    source_envelope = MemberModelEnvelope.from_dict(plan["member_envelopes"][0])
    trace_envelope = MemberModelEnvelope.from_dict(plan["member_envelopes"][1])
    contract = HandoffFieldContract.from_dict(plan["handoff_field_contracts"][0])

    argv = ["plan", "mixed-task.json"]
    intent = "intent:current-source-trace-blueprint"
    facts = task_facts(
        argv=argv,
        intent=intent,
        primary_kind="source.primary_discovery",
        additional_primary_kinds=("trace.temporal_reconstruction",),
        composition=plan,
    )
    routed = select_member_request(
        facts,
        argv,
        business_intent_id=intent,
        native_owner_attestations=native_owner_attestations(plan),
    )
    assert isinstance(routed, RouteComposition)
    assert routed.status == "composition_ready"

    field_impact = composition_impact(routed, [contract.payload_fingerprint])
    assert field_impact["affected_step_ids"] == ["step:2:traceguard"]
    upstream_impact = composition_impact(routed, [source_envelope.model_fingerprint])
    assert upstream_impact["affected_step_ids"] == [
        "step:1:sourceguard",
        "step:2:traceguard",
    ]
    trace = reverse_trace_composition(routed, "overall")
    assert trace["payload_interpreted"] is False
    assert (
        trace["steps"][0]["envelope"]["native_receipt_refs"][0]["receipt_id"]
        == source_envelope.native_receipt_refs[0].receipt_id
    )
