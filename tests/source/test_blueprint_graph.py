from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

import pytest

from admission_fixtures import attach_source_receipts, self_resign_target_authority
from target_material_fixtures import (
    expected_target_anchor_from_material,
    information_expected_target_anchor,
)
import researchguard.target_authority as target_authority_transport
import researchguard.source.blueprint as blueprint_module

from researchguard.source.blueprint import (
    InformationTargetUniverse,
    TargetUnit,
    TargetUnitInterfaceBinding,
    TargetUnitPort,
    check_blueprint,
    export_blueprint,
    impact_blueprint as _impact_blueprint,
    reverse_trace_claim_use,
)
from researchguard.source.blueprint import (
    _bind_information_target_authority as issue_information_target_authority,
)
from researchguard.source.schema import (
    BeliefState,
    EvidenceAnchor,
    Gap,
    GapClosureBasis,
    GapQualification,
    GraphEdge,
    Lead,
    Observation,
    SchemaError,
    SearchAction,
    SourceGuardPreventedFailure,
    SourceGuardProofCase,
    SourceRecord,
    bind_sourceguard_model_contract,
    build_sourceguard_model_contract,
    to_plain,
)
from researchguard.source.guard_contract import prove_target_model_contract


SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64


def _universe() -> InformationTargetUniverse:
    return InformationTargetUniverse(
        universe_id="universe:source-blueprint",
        target_root_unit_id="unit:objective",
        target_units=(
            TargetUnit(
                "unit:objective",
                "",
                0,
                ("unit:claim-1",),
                (
                    TargetUnitPort("unit:objective:child-input", "input", "sourceguard.qualified-information.v1"),
                    TargetUnitPort("unit:objective:output", "output", "sourceguard.information-objective.v1"),
                ),
                (("unit:objective:output", "terminal"),),
            ),
            TargetUnit(
                "unit:claim-1",
                "unit:objective",
                1,
                (),
                (TargetUnitPort("unit:claim-1:output", "output", "sourceguard.qualified-information.v1"),),
            ),
        ),
        target_unit_interfaces=(
            TargetUnitInterfaceBinding(
                "target-interface:claim-1:objective",
                "unit:claim-1",
                "unit:claim-1:output",
                "unit:objective",
                "unit:objective:child-input",
                "sourceguard.qualified-information.v1",
                "consumed",
            ),
        ),
        required_target_unit_ids=("unit:objective", "unit:claim-1"),
        required_gap_ids=("gap:independent",),
        required_source_role_ids=(
            "source-role:gap:independent:independent_report",
        ),
        required_lineage_slot_ids=("lineage:independent-1",),
        required_anchor_requirement_ids=("anchor:1",),
        required_handoff_ids=(),
        known_good_case_ids=("good:source-blueprint",),
        known_bad_case_ids=("bad:source-blueprint",),
    )


def _state() -> BeliefState:
    anchor = EvidenceAnchor(
        anchor_id="anchor:1",
        source_id="source:1",
        anchor_type="paragraph",
        locator="section=results;paragraph=3",
        text="A bounded observation.",
        modality="text",
        observed_at="2026-08-04T10:00:00+00:00",
        extraction_confidence=0.9,
        specificity=0.9,
        supports=["gap:independent"],
        claim_use_ids=["claim-use:1"],
        usable_for_claim=True,
        anchor_content_fingerprint=SHA_B,
        source_content_fingerprint=SHA_A,
        extractor_id="extractor:test",
        extractor_revision="1",
        observation_fingerprint=SHA_C,
    )
    state = BeliefState(
        metadata={
            "handoff_ids": [],
            "stop_decisions_by_gap": {"gap:independent": "stop:1"},
            "member_handoffs_by_gap": {},
            "member_handoffs_by_claim_use": {},
        },
        leads=[Lead(lead_id="lead:1", question="Which source closes the target gap?")],
        sources=[
            SourceRecord(
                source_id="source:1",
                title="Independent result",
                source_type="paper",
                source_status="saved",
                source_reliability=0.9,
                source_role="independent_report",
                lineage_id="independent-1",
                access_status="public",
                content_fingerprint=SHA_A,
                retrieval_request_fingerprint=SHA_B,
                provider_id="provider:test",
                provider_revision="2026-08-04",
                retrieved_at="2026-08-04T09:55:00+00:00",
            )
        ],
        anchors=[anchor],
        gaps=[
            Gap(
                gap_id="gap:independent",
                lead_id="lead:1",
                gap_type="missing_independent_source",
                structure_unit_id="unit:claim-1",
                suggested_source_roles=["independent_report"],
                semantic_state="closed",
                qualification=GapQualification(
                    anchor_id="anchor:1",
                    source_id="source:1",
                    observation_id="observation:1",
                    locator_present=True,
                    source_accessible=True,
                    source_reliability=0.9,
                    extraction_confidence=0.9,
                    specificity=0.9,
                    supports_gap=True,
                    role_match=True,
                    modality_match=True,
                    target_match=True,
                    usable_for_claim=True,
                    decision="claim_usable",
                ),
                closure_basis=GapClosureBasis(
                    anchor_ids=["anchor:1"],
                    source_ids=["source:1"],
                    observation_ids=["observation:1"],
                    thresholds={
                        "source_reliability": 0.5,
                        "extraction_confidence": 0.5,
                        "specificity": 0.5,
                    },
                    target_match="exact",
                    claim_use_decision="claim_usable",
                    qualified=True,
                ),
            )
        ],
        actions=[
            SearchAction(
                action_id="action:1",
                action_type="text_search",
                target_lead_id="lead:1",
                target_gap_id="gap:independent",
                expected_source_role="independent_report",
                expected_modality="text",
            )
        ],
        observations=[
            Observation(
                observation_id="observation:1",
                action_id="action:1",
                observed_sources=[],
                observed_anchors=[deepcopy(anchor)],
                observation_fingerprint=SHA_C,
            )
        ],
        graph_edges=[
            GraphEdge("edge:lead-gap", "lead:1", "lead", "gap:independent", "gap", "opens_gap"),
            GraphEdge("edge:unit-gap", "unit:claim-1", "target_unit", "gap:independent", "gap", "opens_gap"),
            GraphEdge(
                "edge:gap-role",
                "gap:independent",
                "gap",
                "source-role:gap:independent:independent_report",
                "source_role",
                "requires_role",
            ),
            GraphEdge(
                "edge:role-action",
                "source-role:gap:independent:independent_report",
                "source_role",
                "action:1",
                "search_action",
                "addresses",
            ),
            GraphEdge(
                "edge:action-observation",
                "action:1",
                "search_action",
                "observation:1",
                "observation",
                "observation_from",
            ),
            GraphEdge(
                "edge:observation-anchor",
                "observation:1",
                "observation",
                "anchor:1",
                "anchor",
                "observation_from",
            ),
            GraphEdge("edge:action-source", "action:1", "search_action", "source:1", "source", "returns_source"),
            GraphEdge("edge:source-anchor", "source:1", "source", "anchor:1", "anchor", "contains_anchor"),
            GraphEdge("edge:anchor-gap", "anchor:1", "anchor", "gap:independent", "gap", "qualifies"),
            GraphEdge("edge:anchor-claim", "anchor:1", "anchor", "claim-use:1", "claim_use", "consumed_by"),
        ],
    )
    failure = SourceGuardPreventedFailure(
        failure_id="failure:source-blueprint:qualification",
        title="An unqualified source closes a gap",
        block_when="the anchor is not claim usable",
        oracle_id="oracle:sourceguard:source-qualification",
        known_good=SourceGuardProofCase("good:source-blueprint", "good.yaml", "pass"),
        known_bad=SourceGuardProofCase(
            "bad:source-blueprint",
            "good.yaml",
            "blocked",
            "make-all-anchors-unusable",
            "independent_lineages:independent_lineage_slot:1",
        ),
    )
    return bind_sourceguard_model_contract(
        state,
        contract=build_sourceguard_model_contract(
            model_id="source-blueprint-test",
            purpose="Prevent unsupported information-blueprint closure.",
            prevented_failures=[failure],
            gap_ids=["gap:independent"],
            target_unit_ids=["unit:claim-1"],
            source_role_ids=["source-role:gap:independent:independent_report"],
            lineage_slot_ids=["lineage:independent-1"],
            anchor_requirement_ids=["anchor:1"],
            handoff_ids=[],
            claim_boundary="Source and anchor qualification only.",
        ),
    )


def _current_native_universe(state: BeliefState, root: Path) -> tuple[InformationTargetUniverse, Path]:
    contract_path = root / "source-blueprint.contract.json"
    observation_path = root / "good.yaml"
    contract_path.write_text(json.dumps(state.guard_contract.to_dict(), indent=2), encoding="utf-8")
    observation_path.write_text(json.dumps(to_plain(state.observations[0]), indent=2), encoding="utf-8")
    receipt = prove_target_model_contract(state, contract_path)
    unsigned = _universe()
    universe = issue_information_target_authority(
        state,
        unsigned,
        expected_target_anchor=information_expected_target_anchor(state, unsigned),
    )
    universe = replace(universe, native_purpose_receipt=receipt)
    return attach_source_receipts(state, universe), contract_path


def test_closure_source_or_anchor_must_be_present_in_native_observation(
    tmp_path: Path,
) -> None:
    state = _state()
    universe, contract_path = _current_native_universe(state, tmp_path)
    state.observations[0].observed_sources = []
    state.observations[0].observed_anchors = []
    result = check_blueprint(state, universe, contract_path=str(contract_path))
    assert result.status == "incomplete"
    assert "missing-closure-observation" in {item.code for item in result.gaps}


def test_fresh_process_accepts_independently_authored_alternate_source_target(
    tmp_path: Path,
) -> None:
    state = _state()
    assert state.guard_contract is not None
    state = bind_sourceguard_model_contract(
        state,
        contract=replace(
            state.guard_contract,
            model_id="source-blueprint-alternate",
            purpose="Prevent unsupported closure for an alternate information target.",
        ),
    )
    universe, contract_path = _current_native_universe(state, tmp_path)
    assert check_blueprint(
        state, universe, contract_path=str(contract_path)
    ).status == "complete"
    context_path = tmp_path / "alternate-source-context.json"
    context_path.write_text(
        json.dumps(
            {
                "state": to_plain(state),
                "universe": universe.to_dict(),
                "contract_path": str(contract_path),
            }
        ),
        encoding="utf-8",
    )
    child = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            """
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path.cwd() / 'tests'))
from target_material_fixtures import install_test_expected_target_producer
install_test_expected_target_producer()
from admission_fixtures import install_test_native_receipt_producers
install_test_native_receipt_producers()
from researchguard.source.blueprint import InformationTargetUniverse, check_blueprint, reverse_trace_claim_use
from researchguard.source.schema import BeliefState

context = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
state = BeliefState.from_dict(context['state'])
universe = InformationTargetUniverse.from_dict(context['universe'])
result = check_blueprint(state, universe, contract_path=context['contract_path'])
trace = reverse_trace_claim_use(
    state,
    'claim-use:1',
    universe,
    contract_path=context['contract_path'],
)
authority = universe.target_authority
print(json.dumps({
    'status': result.status,
    'trace_status': trace['trace_status'],
    'trace_claim_use_id': trace['claim_use_id'],
    'target_id': authority.target_id,
    'request_id': authority.request_id,
    'target_revision': authority.target_revision,
    'target_fingerprint': authority.target_fingerprint,
}))
""",
            str(context_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(child.stdout)
    assert result["status"] == "complete"
    assert result["trace_status"] == "complete"
    assert result["trace_claim_use_id"] == "claim-use:1"
    assert result["target_id"] == "source-blueprint-alternate"
    assert result["request_id"].startswith("request:")
    assert result["target_revision"] == result["target_fingerprint"]


def test_source_queries_each_consume_one_blueprint_qualification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state()
    universe, contract_path = _current_native_universe(state, tmp_path)
    original = blueprint_module.check_blueprint
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(blueprint_module, "check_blueprint", counted)
    blueprint_module.impact_blueprint(
        state,
        ("anchor:1",),
        universe,
        contract_path=str(contract_path),
    )
    assert calls == 1
    blueprint_module.reverse_trace_claim_use(
        state,
        "claim-use:1",
        universe,
        contract_path=str(contract_path),
    )
    assert calls == 2


def impact_blueprint(
    state: BeliefState,
    changed_ids: list[str] | tuple[str, ...],
    universe: InformationTargetUniverse | None = None,
) -> dict[str, object]:
    """Run impact tests only through one current native qualification."""

    with TemporaryDirectory(prefix="researchguard-source-impact-") as root:
        current_universe, contract_path = _current_native_universe(
            state, Path(root)
        )
        return _impact_blueprint(
            state,
            changed_ids,
            current_universe,
            contract_path=str(contract_path),
        )


def test_source_impact_without_current_qualification_is_atomically_blocked() -> None:
    result = _impact_blueprint(_state(), ["anchor:1"], _universe())
    assert result["query_status"] == "blocked"
    assert result["qualification_status"] == "incomplete"
    assert result["target_authority_status"] == "not_run"
    assert result["target_material_status"] == "not_run"
    assert {item["code"] for item in result["qualification_gaps"]} >= {
        "missing-target-purpose-authority"
    }
    assert result["affected_anchor_ids"] == []
    assert result["partial_result_suppressed"] is True


def test_typed_edge_load_rejects_retired_raw_shape_and_missing_endpoint() -> None:
    raw = to_plain(_state())
    raw["graph_edges"][0] = {"source": "lead:1", "target": "gap:independent", "relation": "opens_gap"}
    with pytest.raises(SchemaError, match="unknown current-schema fields"):
        BeliefState.from_dict(raw)

    raw = to_plain(_state())
    raw["graph_edges"][0]["target_id"] = "gap:missing"
    with pytest.raises(SchemaError, match="references missing endpoint"):
        BeliefState.from_dict(raw)


def test_complete_information_blueprint_closes_every_typed_interface(tmp_path: Path) -> None:
    state = _state()
    universe, contract_path = _current_native_universe(state, tmp_path)
    result = check_blueprint(state, universe, contract_path=str(contract_path))
    assert result.status == "complete"
    assert result.deepest_proven_layer == "native-information-blueprint"
    assert result.first_unresolved_gap == ""
    assert result.unconsumed_candidate_ids == ()


def test_serialized_source_authority_replays_without_process_registry(
    tmp_path: Path,
) -> None:
    state = _state()
    universe, contract_path = _current_native_universe(state, tmp_path)
    reloaded = InformationTargetUniverse.from_dict(
        json.loads(json.dumps(universe.to_dict()))
    )
    assert check_blueprint(
        state,
        reloaded,
        contract_path=str(contract_path),
    ).status == "complete"
    assert not hasattr(target_authority_transport, "_FROZEN_NATIVE_RESULTS")


def test_external_source_target_material_remains_unverified() -> None:
    state = _state()
    universe = _universe()
    current_anchor = information_expected_target_anchor(state, universe)
    external_anchor = expected_target_anchor_from_material(
        member_id="sourceguard",
        task_id=current_anchor.task_id,
        target_request_fingerprint=current_anchor.target_request_fingerprint,
        target_id=current_anchor.target_id,
        target_revision=current_anchor.target_revision,
        material_locator="https://example.invalid/source-target.json",
        material_fingerprint=current_anchor.material_fingerprint,
        admission_request_scope="external-unavailable",
    )
    unverified = issue_information_target_authority(
        state,
        replace(universe, target_authority=None),
        expected_target_anchor=external_anchor,
    )
    result = check_blueprint(state, unverified)
    assert unverified.target_authority.status == "unverified"
    assert any(item.code == "native-target-material-unverified" for item in result.gaps)
    trace = reverse_trace_claim_use(state, "claim-use:missing", unverified)
    assert trace["query_status"] == "blocked"
    assert trace["target_material_status"] == "unverified"
    assert trace["claim_use_id"] == ""
    assert trace["source_revisions"] == []
    assert trace["partial_result_suppressed"] is True


def test_native_layer_requires_current_replayable_purpose_receipt() -> None:
    state = _state()
    result = check_blueprint(
        state,
        issue_information_target_authority(
            state,
            _universe(),
            expected_target_anchor=information_expected_target_anchor(state, _universe()),
        ),
    )
    assert result.status == "incomplete"
    assert any(item.code == "missing-native-purpose-receipt" for item in result.gaps)
    assert result.layer_statuses[-1]["status"] == "failed"


def test_simultaneous_information_blueprint_authority_shrink_cannot_self_sign_complete() -> None:
    state = _state()
    unsigned = _universe()
    universe = issue_information_target_authority(
        state,
        unsigned,
        expected_target_anchor=information_expected_target_anchor(state, unsigned),
    )
    authority = universe.target_authority
    assert authority is not None
    root = universe.target_units[0]
    shrunk_root = replace(
        root,
        child_unit_ids=(),
        ports=tuple(item for item in root.ports if item.port_id != "unit:objective:child-input"),
    )
    removed_ids = {
        "unit:claim-1",
        "unit:claim-1:output",
        "unit:objective:child-input",
        "target-interface:claim-1:objective",
    }
    resigned = self_resign_target_authority(
        authority,
        (item for item in authority.items if item.object_id not in removed_ids),
    )
    shrunk = replace(
        universe,
        target_units=(shrunk_root,),
        target_unit_interfaces=(),
        required_target_unit_ids=("unit:objective",),
        target_authority=resigned,
    )
    result = check_blueprint(state, shrunk)
    assert result.status == "incomplete"
    assert any(item.code == "native-target-denominator-mismatch" for item in result.gaps)


def test_fresh_process_first_issue_replays_original_source_target_material(
    tmp_path: Path,
) -> None:
    state = _state()
    universe, contract_path = _current_native_universe(state, tmp_path)
    root = universe.target_units[0]
    shrunk_root = replace(
        root,
        child_unit_ids=(),
        ports=tuple(
            item
            for item in root.ports
            if item.port_id != "unit:objective:child-input"
        ),
    )
    shrunk = replace(
        universe,
        target_units=(shrunk_root,),
        target_unit_interfaces=(),
        required_target_unit_ids=("unit:objective",),
        target_authority=None,
    )
    assert universe.target_authority is not None
    assert universe.target_authority.native_attestation is not None
    context_path = tmp_path / "source-child-context.json"
    context_path.write_text(
        json.dumps(
            {
                "state": to_plain(state),
                "universe": shrunk.to_dict(),
                "contract_path": str(contract_path),
                "expected_target_anchor": universe.target_authority.expected_target_anchor.to_dict(),
            }
        ),
        encoding="utf-8",
    )
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path.cwd() / 'tests'))
from target_material_fixtures import install_test_expected_target_producer
install_test_expected_target_producer()
from admission_fixtures import install_test_native_receipt_producers
install_test_native_receipt_producers()
from researchguard.source.blueprint import InformationTargetUniverse, check_blueprint, _bind_information_target_authority as issue_information_target_authority
from researchguard.source.schema import BeliefState
from researchguard.target_authority import ExpectedTargetAnchor

context = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
state = BeliefState.from_dict(context['state'])
universe = InformationTargetUniverse.from_dict(context['universe'])
universe = issue_information_target_authority(
    state,
    universe,
    expected_target_anchor=ExpectedTargetAnchor.from_dict(context['expected_target_anchor']),
)
result = check_blueprint(state, universe, contract_path=context['contract_path'])
print(json.dumps({'status': result.status, 'gaps': [[gap.code, gap.object_id] for gap in result.gaps]}))
""",
            str(context_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(child.stdout)
    assert payload["status"] == "incomplete"
    assert ["target-authority-omitted-target-unit", "unit:claim-1"] in payload["gaps"]


def test_native_purpose_receipt_detects_current_input_or_receipt_drift(tmp_path: Path) -> None:
    state = _state()
    universe, contract_path = _current_native_universe(state, tmp_path)
    receipt = dict(universe.native_purpose_receipt)
    receipt["model_fingerprint"] = SHA_A
    stale = replace(universe, native_purpose_receipt=receipt)
    result = check_blueprint(state, stale, contract_path=str(contract_path))
    assert any(item.code == "native-purpose-model-stale" for item in result.gaps)
    (tmp_path / "good.yaml").write_text("{}", encoding="utf-8")
    result = check_blueprint(state, universe, contract_path=str(contract_path))
    assert any(item.code == "native-purpose-replay-failed" for item in result.gaps)


@pytest.mark.parametrize(
    ("mutation", "gap_code"),
    [
        ("orphan", "target-parent-owner-count"),
        ("depth", "target-depth-jump"),
        ("missing_binding", "unconsumed-target-output"),
        ("schema", "target-interface-schema-mismatch"),
        ("unconsumed", "unconsumed-target-output"),
    ],
)
def test_target_unit_hierarchy_and_interfaces_fail_visibly(mutation: str, gap_code: str) -> None:
    universe = _universe()
    root, leaf = universe.target_units
    if mutation == "orphan":
        universe = replace(universe, target_units=(replace(root, child_unit_ids=()), leaf))
    elif mutation == "depth":
        universe = replace(universe, target_units=(root, replace(leaf, depth=3)))
    elif mutation == "missing_binding":
        universe = replace(universe, target_unit_interfaces=())
    elif mutation == "schema":
        universe = replace(
            universe,
            target_unit_interfaces=(replace(universe.target_unit_interfaces[0], payload_schema_id="foreign.v1"),),
        )
    else:
        universe = replace(
            universe,
            target_units=(
                root,
                replace(
                    leaf,
                    ports=(*leaf.ports, TargetUnitPort("unit:claim-1:extra", "output", "sourceguard.extra.v1")),
                ),
            ),
        )
    result = check_blueprint(_state(), universe)
    assert result.status == "incomplete"
    assert any(item.code == gap_code for item in result.gaps)
    failed = next(index for index, row in enumerate(result.layer_statuses) if row["status"] == "failed")
    assert all(row["status"] == "not_run" for row in result.layer_statuses[failed + 1 :])


def test_target_unit_leaf_change_reaches_ancestors_and_reverse_trace_terminal(
    tmp_path: Path,
) -> None:
    state = _state()
    universe, contract_path = _current_native_universe(state, tmp_path)
    impact = impact_blueprint(state, ["unit:claim-1:output"], universe)
    assert impact["affected_target_unit_ids"] == ["unit:claim-1", "unit:objective"]
    trace = reverse_trace_claim_use(
        state,
        "claim-use:1",
        universe,
        contract_path=str(contract_path),
    )
    assert trace["target_unit_paths_to_root"] == [["unit:claim-1", "unit:objective"]]
    assert trace["target_unit_interfaces"][0]["consumer_status"] == "consumed"
    assert "unread external bytes" in trace["terminal_capability_boundary"]


def test_gap_cannot_bind_to_foreign_target_unit() -> None:
    universe = _universe()
    root, leaf = universe.target_units
    foreign_leaf = replace(
        leaf,
        unit_id="unit:other",
        parent_unit_id=root.unit_id,
        ports=(TargetUnitPort("unit:other:output", "output", "sourceguard.qualified-information.v1"),),
    )
    foreign_root = replace(root, child_unit_ids=(foreign_leaf.unit_id,))
    interface = replace(
        universe.target_unit_interfaces[0],
        child_unit_id=foreign_leaf.unit_id,
        child_output_port_id="unit:other:output",
    )
    changed = replace(
        universe,
        target_units=(foreign_root, foreign_leaf),
        target_unit_interfaces=(interface,),
        required_target_unit_ids=(foreign_root.unit_id, foreign_leaf.unit_id),
    )
    result = check_blueprint(_state(), changed)
    assert any(item.code == "foreign-gap-target-unit" for item in result.gaps)


@pytest.mark.parametrize("level", ["root", "unit", "port", "interface"])
def test_information_universe_loader_rejects_unknown_fields(level: str) -> None:
    raw = _universe().to_dict()
    if level == "root":
        raw["future"] = True
    elif level == "unit":
        raw["target_units"][0]["future"] = True
    elif level == "port":
        raw["target_units"][0]["ports"][0]["future"] = True
    else:
        raw["target_unit_interfaces"][0]["future"] = True
    with pytest.raises(ValueError, match="unknown fields"):
        InformationTargetUniverse.from_dict(raw)


@pytest.mark.parametrize("field", ["target_units", "target_unit_interfaces"])
def test_information_universe_loader_rejects_non_object_rows(field: str) -> None:
    raw = _universe().to_dict()
    raw[field].append("not-an-object")
    with pytest.raises(ValueError, match="must be an object"):
        InformationTargetUniverse.from_dict(raw)


def test_independent_universe_omission_is_visible_before_identity_depth() -> None:
    universe = InformationTargetUniverse(
        **{
            **{key: value for key, value in _universe().__dict__.items()},
            "required_source_role_ids": (
                "source-role:gap:independent:independent_report",
                "source-role:gap:independent:primary_source",
            ),
        }
    )
    result = check_blueprint(_state(), universe)
    assert result.status == "incomplete"
    assert result.deepest_proven_layer == "typed-information-chain"
    assert any(
        item.code == "omitted-universe-source-role"
        and item.object_id == "source-role:gap:independent:primary_source"
        for item in result.gaps
    )


def test_content_or_extractor_change_changes_fingerprint_and_only_consumers() -> None:
    baseline = _state()
    baseline_result = check_blueprint(baseline, _universe())
    candidate = deepcopy(baseline)
    candidate.anchors[0].extractor_revision = "2"
    candidate.anchors[0].anchor_content_fingerprint = SHA_C
    candidate_result = check_blueprint(candidate, _universe())
    impact = impact_blueprint(candidate, ["anchor:1"], _universe())
    assert candidate_result.blueprint_fingerprint != baseline_result.blueprint_fingerprint
    assert impact["affected_gap_ids"] == ["gap:independent"]
    assert impact["affected_stop_decision_ids"] == ["stop:1"]
    assert impact["affected_claim_use_ids"] == ["claim-use:1"]
    assert impact["unaffected_gap_ids"] == []
    assert impact["unknown_ownership"] is False


def test_reverse_trace_and_export_round_trip_are_deterministic(tmp_path: Path) -> None:
    state = _state()
    universe, contract_path = _current_native_universe(state, tmp_path)
    trace = reverse_trace_claim_use(
        state,
        "claim-use:1",
        universe,
        contract_path=str(contract_path),
    )
    assert trace["target_unit_ids"] == ["unit:claim-1"]
    assert trace["gap_ids"] == ["gap:independent"]
    assert trace["search_action_ids"] == ["action:1"]
    assert trace["source_revisions"][0]["content_fingerprint"] == SHA_A
    assert trace["source_revisions"][0]["retrieval_request_fingerprint"] == SHA_B
    assert trace["source_revisions"][0]["lineage_id"] == "independent-1"
    assert trace["source_revisions"][0]["source_role"] == "independent_report"
    assert trace["observation_chain"] == [
        {
            "observation_id": "observation:1",
            "action_id": "action:1",
            "observation_fingerprint": SHA_C,
            "observed_source_ids": [],
            "observed_anchor_ids": ["anchor:1"],
        }
    ]
    first = export_blueprint(state, universe, contract_path=str(contract_path))
    reloaded = BeliefState.from_dict(first["model"])
    second = export_blueprint(
        reloaded,
        InformationTargetUniverse.from_dict(first["target_universe"]),
        contract_path=str(contract_path),
    )
    assert second == first
    with pytest.raises(ValueError, match="has no SourceGuard anchor"):
        reverse_trace_claim_use(
            state,
            "claim-use:missing",
            universe,
            contract_path=str(contract_path),
        )


def test_unknown_changed_identity_blocks_affected_confidence() -> None:
    impact = impact_blueprint(_state(), ["anchor:not-owned"], _universe())
    assert impact["unknown_ownership"] is True
    assert impact["unknown_dependency_ids"] == ["anchor:not-owned"]
    assert impact["partial_result_suppressed"] is True


@pytest.mark.parametrize(
    ("changed_id", "expected_key", "expected_id"),
    [
        ("unit:claim-1", "affected_gap_ids", "gap:independent"),
        ("gap:independent", "affected_source_role_ids", "source-role:gap:independent:independent_report"),
        ("source-role:gap:independent:independent_report", "affected_search_action_ids", "action:1"),
        ("action:1", "affected_observation_ids", "observation:1"),
        ("observation:1", "affected_anchor_ids", "anchor:1"),
        ("lineage:independent-1", "affected_source_ids", "source:1"),
        ("anchor:1", "affected_claim_use_ids", "claim-use:1"),
        ("claim-use:1", "affected_claim_use_ids", "claim-use:1"),
    ],
)
def test_every_information_blueprint_object_can_seed_exact_impact(
    changed_id: str,
    expected_key: str,
    expected_id: str,
) -> None:
    impact = impact_blueprint(_state(), [changed_id], _universe())
    assert expected_id in impact[expected_key]
    assert impact["unknown_ownership"] is False


def test_mixed_unknown_stays_blocked_and_unrelated_branch_is_not_selected() -> None:
    state = _state()
    state.leads.append(Lead(lead_id="lead:unrelated", question="unrelated"))
    impact = impact_blueprint(state, ["unit:claim-1", "foreign:unowned"], _universe())
    assert impact["affected_gap_ids"] == []
    assert impact["unaffected_gap_ids"] == []
    assert impact["unknown_dependency_ids"] == ["foreign:unowned"]
    assert impact["unknown_ownership"] is True
    assert impact["partial_result_suppressed"] is True


def test_reverse_trace_rejects_missing_or_wrong_action_chain() -> None:
    state = _state()
    state.graph_edges = [
        edge for edge in state.graph_edges if edge.relation_type != "returns_source"
    ]
    trace = reverse_trace_claim_use(state, "claim-use:1", _universe())
    assert trace["query_status"] == "blocked"
    assert trace["search_action_ids"] == []
    assert trace["partial_result_suppressed"] is True

    state = _state()
    state.observations[0] = Observation(
        observation_id="observation:1",
        action_id="action:not-declared",
        observed_anchors=[deepcopy(state.anchors[0])],
        observation_fingerprint=SHA_C,
    )
    trace = reverse_trace_claim_use(state, "claim-use:1", _universe())
    assert trace["observation_chain"] == []
    assert trace["search_action_ids"] == []
    assert trace["partial_result_suppressed"] is True


def test_reverse_trace_broken_observation_hop_is_not_silently_used() -> None:
    state = _state()
    state.graph_edges = [
        edge for edge in state.graph_edges if edge.edge_id != "edge:observation-anchor"
    ]
    trace = reverse_trace_claim_use(state, "claim-use:1", _universe())
    assert trace["observation_chain"] == []
    assert trace["reverse_trace_fingerprint"] == ""
    assert trace["partial_result_suppressed"] is True


def test_source_retrieval_identity_change_is_never_silently_reused(
    tmp_path: Path,
) -> None:
    state = _state()
    before_universe, before_contract = _current_native_universe(state, tmp_path)
    before = reverse_trace_claim_use(
        state,
        "claim-use:1",
        before_universe,
        contract_path=str(before_contract),
    )
    state.sources[0].url = "https://example.invalid/revised"
    state.sources[0].retrieval_request_fingerprint = SHA_C
    after_universe, after_contract = _current_native_universe(state, tmp_path)
    before_receipt_ids = {
        item.receipt_id for item in before_universe.native_receipt_refs
    }
    after_receipt_ids = {
        item.receipt_id for item in after_universe.native_receipt_refs
    }
    assert before_receipt_ids != after_receipt_ids
    after = reverse_trace_claim_use(
        state,
        "claim-use:1",
        after_universe,
        contract_path=str(after_contract),
    )
    assert after["source_revisions"] != before["source_revisions"]
    impact = impact_blueprint(state, ["source:1"], _universe())
    assert impact["affected_gap_ids"] == ["gap:independent"]
    assert impact["unknown_ownership"] is False


def test_source_blueprint_cli_uses_one_grouped_native_surface(tmp_path: Path, capsys) -> None:
    from researchguard.source.cli import main

    state = _state()
    universe, contract_path = _current_native_universe(state, tmp_path)
    model_path = tmp_path / "source-model.json"
    universe_path = tmp_path / "source-universe.json"
    export_path = tmp_path / "source-blueprint-export.json"
    model_path.write_text(json.dumps(to_plain(state)), encoding="utf-8")
    universe_path.write_text(json.dumps(universe.to_dict()), encoding="utf-8")
    common = [str(model_path), "--model-contract", str(contract_path), "--universe", str(universe_path)]

    assert main(["blueprint", "check", *common]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "complete"
    assert main(["blueprint", "impact", *common, "--changed-id", "anchor:1"]) == 0
    assert json.loads(capsys.readouterr().out)["affected_claim_use_ids"] == ["claim-use:1"]
    assert main(
        ["blueprint", "impact", *common, "--changed-id", "anchor:1", "--changed-id", "foreign:unowned"]
    ) == 3
    blocked = json.loads(capsys.readouterr().out)
    assert blocked["partial_result_suppressed"] is True
    assert blocked["affected_claim_use_ids"] == []
    assert main(["blueprint", "trace", *common, "--claim-use-id", "claim-use:1"]) == 0
    assert json.loads(capsys.readouterr().out)["claim_use_id"] == "claim-use:1"
    assert main(["blueprint", "export", *common, "--output", str(export_path)]) == 0
    export_notice = json.loads(capsys.readouterr().out)
    assert export_notice["ok"] is True
    assert json.loads(export_path.read_text(encoding="utf-8"))["check"]["status"] == "complete"


def test_information_blueprint_cannot_clear_its_own_required_denominator(tmp_path: Path) -> None:
    state = _state()
    universe, contract_path = _current_native_universe(state, tmp_path)
    shrunk = replace(
        universe,
        required_target_unit_ids=(),
        required_gap_ids=(),
        required_source_role_ids=(),
        required_lineage_slot_ids=(),
        required_anchor_requirement_ids=(),
        required_handoff_ids=(),
    )
    assert check_blueprint(state, shrunk, contract_path=str(contract_path)).status == "incomplete"


def test_source_reverse_trace_reports_current_blueprint_failure() -> None:
    trace = reverse_trace_claim_use(_state(), "claim-use:missing", _universe())
    assert trace["query_status"] == "blocked"
    assert trace["trace_status"] == "incomplete"
    assert trace["trace_gaps"]
    assert trace["claim_use_id"] == ""
    assert trace["gap_ids"] == []
    assert trace["partial_result_suppressed"] is True
