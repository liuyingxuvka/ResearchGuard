from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from admission_fixtures import self_resign_target_authority, signed_native_receipt
from target_material_fixtures import (
    expected_target_anchor_from_material,
    experiment_expected_target_anchor,
)
import researchguard.target_authority as target_authority_transport
import researchguard.experiment.blueprint as blueprint_module

from researchguard.experiment import (
    ExperimentConstraint,
    ExperimentDesignBlock,
    ExperimentInputBinding,
    ExperimentNativeCaseEvidence,
    ExperimentObservation,
    ExperimentPort,
    ExperimentSpec,
    ExperimentTargetUniverse,
    HypothesisPrediction,
    ProcedureStep,
    check_blueprint,
    export_blueprint,
    impact_blueprint,
    observe_experiments,
    recommend_experiments,
    reverse_trace_experiment,
    target_purpose_fingerprint,
    target_request_fingerprint,
)
from researchguard.experiment.blueprint import (
    _build_child_output_binding as create_child_output_binding,
    _bind_experiment_target_authority as issue_experiment_target_authority,
    _run_native_case_evidence as create_native_case_evidence,
)
from researchguard.target_authority import TargetAuthorityItem, TargetPurposeAuthority


def _candidate(candidate_id: str, parent_id: str) -> ExperimentDesignBlock:
    return ExperimentDesignBlock(
        block_id=f"candidate:{candidate_id}",
        kind="candidate_experiment",
        parent_id=parent_id,
        candidate_experiment_id=candidate_id,
        ports=(
            ExperimentPort(f"{candidate_id}:input", "input", "example.environment.v1"),
            ExperimentPort(f"{candidate_id}:manipulation", "manipulation", "example.scalar.v1"),
            ExperimentPort(f"{candidate_id}:observation", "observation", "example.scalar.v1"),
            ExperimentPort(f"{candidate_id}:outcome", "outcome", "example.outcome.v1", ("up", "down", "hot", "cold")),
        ),
        procedure_steps=(
            ProcedureStep(
                f"{candidate_id}:step",
                0,
                "apply the declared manipulation and record the declared observation",
                (f"{candidate_id}:input", f"{candidate_id}:manipulation"),
                (f"{candidate_id}:observation", f"{candidate_id}:outcome"),
            ),
        ),
        constraints=(ExperimentConstraint(f"{candidate_id}:constraint", "keep the declared environment fixed"),),
        external_execution_owner=f"laboratory:{candidate_id}",
        input_bindings=(
            ExperimentInputBinding(
                f"binding:{candidate_id}:input",
                f"{candidate_id}:input",
                "external",
                f"external:{candidate_id}:environment",
                "",
                "example.environment.v1",
                "one",
                f"laboratory:{candidate_id}",
            ),
            ExperimentInputBinding(
                f"binding:{candidate_id}:manipulation",
                f"{candidate_id}:manipulation",
                "external",
                f"external:{candidate_id}:controller",
                "",
                "example.scalar.v1",
                "one",
                f"laboratory:{candidate_id}",
            ),
        ),
    )


def _spec(**overrides: object) -> ExperimentSpec:
    candidates = (_candidate("e1", "discrimination:all"), _candidate("e2", "discrimination:all"))
    values: dict[str, object] = {
        "task_id": "blueprint-task",
        "purpose": "distinguish declared mechanisms",
        "coverage_ids": ("h1", "h2", "e1", "e2"),
        "assumptions": (),
        "unknowns": (),
        "iteration": 0,
        "max_iterations": 3,
        "hypothesis_predictions": (
            HypothesisPrediction(
                "h1",
                {"e1": "up", "e2": "hot"},
                {"e1": "e1:observation", "e2": "e2:observation"},
                {"e1": "e1:outcome", "e2": "e2:outcome"},
            ),
            HypothesisPrediction(
                "h2",
                {"e1": "down", "e2": "cold"},
                {"e1": "e1:observation", "e2": "e2:observation"},
                {"e1": "e1:outcome", "e2": "e2:outcome"},
            ),
        ),
        "candidate_experiment_ids": ("e1", "e2"),
        "design_root_id": "purpose:root",
        "design_blocks": (
            ExperimentDesignBlock("purpose:root", "purpose", "", ("discrimination:all",)),
            ExperimentDesignBlock(
                "discrimination:all",
                "discrimination_obligation",
                "purpose:root",
                ("candidate:e1", "candidate:e2"),
                ports=(
                    ExperimentPort("discrimination:all:input:e1:observation", "input", "example.scalar.v1"),
                    ExperimentPort("discrimination:all:input:e1:outcome", "input", "example.outcome.v1"),
                    ExperimentPort("discrimination:all:input:e2:observation", "input", "example.scalar.v1"),
                    ExperimentPort("discrimination:all:input:e2:outcome", "input", "example.outcome.v1"),
                ),
                consumed_child_output_port_ids=("e1:observation", "e1:outcome", "e2:observation", "e2:outcome"),
            ),
            *candidates,
        ),
        "target_universe": ExperimentTargetUniverse(
            universe_id="experiment-universe:blueprint-task",
            required_hypothesis_ids=("h1", "h2"),
            required_discrimination_ids=("discrimination:all",),
            required_candidate_ids=("e1", "e2"),
            required_port_ids=(
                "e1:manipulation",
                "e1:input",
                "e1:observation",
                "e1:outcome",
                "e2:manipulation",
                "e2:input",
                "e2:observation",
                "e2:outcome",
                "discrimination:all:input:e1:observation",
                "discrimination:all:input:e1:outcome",
                "discrimination:all:input:e2:observation",
                "discrimination:all:input:e2:outcome",
            ),
            required_procedure_step_ids=("e1:step", "e2:step"),
            required_constraint_ids=("e1:constraint", "e2:constraint"),
            required_input_binding_ids=(
                "binding:e1:input",
                "binding:e1:manipulation",
                "binding:e2:input",
                "binding:e2:manipulation",
            ),
            required_child_output_binding_ids=(
                "child-output:e1:observation",
                "child-output:e1:outcome",
                "child-output:e2:observation",
                "child-output:e2:outcome",
            ),
            known_good_case_ids=("case:complete",),
            known_bad_case_ids=("case:missing-port",),
        ),
    }
    values.update(overrides)
    spec = ExperimentSpec(**values)
    if "target_universe" in overrides:
        return spec
    if "design_blocks" not in overrides:
        blocks = list(spec.design_blocks)
        parent = blocks[1]
        bindings = tuple(
            create_child_output_binding(
                spec,
                binding_id=f"child-output:{candidate_id}:{port_kind}",
                child_block_id=f"candidate:{candidate_id}",
                child_output_port_id=f"{candidate_id}:{port_kind}",
                parent_block_id=parent.block_id,
                parent_input_port_id=f"{parent.block_id}:input:{candidate_id}:{port_kind}",
            )
            for candidate_id in ("e1", "e2")
            for port_kind in ("observation", "outcome")
        )
        blocks[1] = replace(parent, child_output_bindings=bindings)
        spec = replace(spec, design_blocks=tuple(blocks))
    spec = issue_experiment_target_authority(
        spec,
        expected_target_anchor=experiment_expected_target_anchor(spec),
    )
    evidence = (
        create_native_case_evidence(spec, case_id="case:complete", case_kind="known_good"),
        create_native_case_evidence(spec, case_id="case:missing-port", case_kind="known_bad"),
    )
    spec = replace(spec, target_universe=replace(spec.target_universe, native_case_evidence=evidence))
    authority = spec.target_universe.target_authority
    assert authority is not None
    anchor = authority.expected_target_anchor
    receipts = []
    for block in spec.design_blocks:
        for binding in block.child_output_bindings:
            receipts.append(
                signed_native_receipt(
                    receipt_id=binding.receipt_id,
                    member_id="experimentguard",
                    native_owner_id="experimentguard.child-output-interface",
                    checker_id="researchguard.experiment.child-output-binding",
                    checker_version="1",
                    checker_entrypoint="researchguard.experiment.blueprint:_candidate_gaps",
                    task_id=spec.task_id,
                    anchor=anchor,
                    native_model_id=binding.child_block_id,
                    model_fingerprint=binding.producer_model_fingerprint,
                    request_fingerprint=blueprint_module._digest(
                        {
                            "task_id": spec.task_id,
                            "binding_id": binding.binding_id,
                            "parent_block_id": binding.parent_block_id,
                            "parent_input_port_id": binding.parent_input_port_id,
                            "payload_schema_id": binding.payload_schema_id,
                            "refinement_id": binding.refinement_id,
                            "expected_target_anchor_id": anchor.anchor_id,
                        }
                    ),
                    input_fingerprint=binding.payload_fingerprint,
                    result_fingerprint=binding.producer_result_fingerprint,
                )
            )
    for item in evidence:
        receipts.append(
            signed_native_receipt(
                receipt_id=item.receipt_id,
                member_id="experimentguard",
                native_owner_id="experimentguard.native-case",
                checker_id=item.native_check_id,
                checker_version="1",
                checker_entrypoint="researchguard.experiment.blueprint:_native_case_gaps",
                task_id=spec.task_id,
                anchor=anchor,
                native_model_id=f"experiment-native-case:{item.case_id}",
                model_fingerprint=item.subject_model_fingerprint,
                request_fingerprint=blueprint_module._digest(
                    {
                        "task_id": spec.task_id,
                        "case_id": item.case_id,
                        "case_kind": item.case_kind,
                        "failure_class_id": item.failure_class_id,
                        "oracle_id": item.oracle_id,
                        "expected_target_anchor_id": anchor.anchor_id,
                    }
                ),
                input_fingerprint=item.case_input_fingerprint,
                result_fingerprint=item.result_fingerprint,
            )
        )
    return replace(
        spec,
        target_universe=replace(spec.target_universe, native_receipt_refs=tuple(receipts)),
    )


def test_complete_blueprint_is_rooted_deterministic_and_external() -> None:
    spec = _spec()
    result = check_blueprint(spec)
    assert result.status == "complete"
    assert result.deepest_proven_layer == "native-recommendation-bound"
    assert result.external_execution_status == "not_run"
    assert export_blueprint(spec) == export_blueprint(spec)
    assert recommend_experiments(spec).selected_experiment_ids == ("e1",)


@pytest.mark.parametrize(
    ("defect", "expected_gap"),
    (
        ("entry-port-produced", "procedure-output-kind-mismatch"),
        ("result-used-too-early", "procedure-input-before-production"),
        ("entry-port-unused", "unconsumed-procedure-input"),
        ("result-produced-twice", "duplicate-procedure-output-producer"),
    ),
)
def test_procedure_dataflow_cannot_pass_on_port_names_alone(
    defect: str,
    expected_gap: str,
) -> None:
    spec = _spec()
    blocks = list(spec.design_blocks)
    candidate_index = next(
        index for index, block in enumerate(blocks) if block.candidate_experiment_id == "e1"
    )
    candidate = blocks[candidate_index]
    base = candidate.procedure_steps[0]
    if defect == "entry-port-produced":
        steps = (
            replace(base, output_port_ids=(*base.output_port_ids, "e1:input")),
        )
    elif defect == "result-used-too-early":
        steps = (
            replace(
                base,
                input_port_ids=(*base.input_port_ids, "e1:observation"),
                output_port_ids=("e1:outcome",),
            ),
            ProcedureStep(
                "e1:late-observation",
                1,
                "record the observation after it was already requested",
                (),
                ("e1:observation",),
            ),
        )
    elif defect == "entry-port-unused":
        steps = (
            replace(base, input_port_ids=("e1:input",)),
        )
    else:
        steps = (
            base,
            ProcedureStep(
                "e1:duplicate-observation",
                1,
                "record the same observation a second time",
                (),
                ("e1:observation",),
            ),
        )
    blocks[candidate_index] = replace(candidate, procedure_steps=steps)
    result = check_blueprint(replace(spec, design_blocks=tuple(blocks)))
    assert result.status == "incomplete"
    assert expected_gap in {item.code for item in result.gaps}


def test_serialized_experiment_authority_replays_without_process_registry() -> None:
    spec = _spec()
    universe = spec.target_universe
    assert universe is not None and universe.target_authority is not None
    reloaded = TargetPurposeAuthority.from_dict(
        json.loads(json.dumps(universe.target_authority.to_dict()))
    )
    result = check_blueprint(
        replace(spec, target_universe=replace(universe, target_authority=reloaded))
    )
    assert result.status == "complete"
    assert not hasattr(target_authority_transport, "_FROZEN_NATIVE_RESULTS")


def test_fresh_process_alternate_current_experiment_target_is_not_fixture_locked(
    tmp_path: Path,
) -> None:
    alternate = _spec(
        task_id="alternate-blueprint-task",
        purpose="distinguish a different current target",
    )
    assert check_blueprint(alternate).status == "complete"
    assert alternate.target_universe.target_authority.target_id == "alternate-blueprint-task"
    path = tmp_path / "alternate-experiment.json"
    path.write_text(json.dumps(alternate.to_dict()), encoding="utf-8")
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
from researchguard.experiment import check_blueprint, reverse_trace_experiment
from researchguard.experiment.cli import _load_spec

spec = _load_spec(Path(sys.argv[1]))
result = check_blueprint(spec)
trace = reverse_trace_experiment(spec, 'e1')
authority = spec.target_universe.target_authority
print(json.dumps({
    'status': result.status,
    'trace_status': trace['trace_status'],
    'trace_experiment_id': trace['experiment_id'],
    'target_id': authority.target_id,
    'request_id': authority.request_id,
    'target_revision': authority.target_revision,
    'target_fingerprint': authority.target_fingerprint,
}))
""",
            str(path),
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
    assert result["trace_experiment_id"] == "e1"
    assert result["target_id"] == "alternate-blueprint-task"
    assert result["request_id"].startswith("request:")
    assert result["target_revision"] == result["target_fingerprint"]


def test_experiment_queries_each_consume_one_blueprint_qualification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _spec()
    original = blueprint_module.check_blueprint
    calls = 0

    def counted(candidate):
        nonlocal calls
        calls += 1
        return original(candidate)

    monkeypatch.setattr(blueprint_module, "check_blueprint", counted)
    blueprint_module.impact_blueprint(spec, ("e1",))
    assert calls == 1
    blueprint_module.reverse_trace_experiment(spec, "e1")
    assert calls == 2


def test_experiment_queries_preserve_authority_gap_and_suppress_impact() -> None:
    spec = _spec()
    broken = replace(
        spec,
        target_universe=replace(spec.target_universe, target_authority=None),
    )
    impact = impact_blueprint(broken, ("e1",))
    assert impact["query_status"] == "blocked"
    assert impact["qualification_status"] == "incomplete"
    assert impact["target_authority_status"] == "not_run"
    assert impact["target_material_status"] == "not_run"
    assert {item["code"] for item in impact["qualification_gaps"]} >= {
        "missing-target-purpose-authority"
    }
    assert impact["affected_candidate_ids"] == []
    assert impact["partial_result_suppressed"] is True
    trace = reverse_trace_experiment(broken, "e1")
    assert trace["trace_status"] == "incomplete"
    assert {item["code"] for item in trace["trace_gaps"]} >= {
        "missing-target-purpose-authority"
    }


def test_external_experiment_target_material_remains_unverified() -> None:
    spec = _spec()
    universe = replace(
        spec.target_universe,
        target_authority=None,
        native_case_evidence=(),
    )
    current_anchor = spec.target_universe.target_authority.expected_target_anchor
    external_anchor = expected_target_anchor_from_material(
        member_id="experimentguard",
        task_id=current_anchor.task_id,
        target_request_fingerprint=current_anchor.target_request_fingerprint,
        target_id=current_anchor.target_id,
        target_revision=current_anchor.target_revision,
        material_locator="https://example.invalid/experiment-target.json",
        material_fingerprint=current_anchor.material_fingerprint,
        admission_request_scope="external-unavailable",
    )
    unverified = issue_experiment_target_authority(
        replace(spec, target_universe=universe),
        expected_target_anchor=external_anchor,
    )
    result = check_blueprint(unverified)
    assert unverified.target_universe.target_authority.status == "unverified"
    assert any(item.code == "native-target-material-unverified" for item in result.gaps)
    trace = reverse_trace_experiment(unverified, "experiment:missing")
    assert trace["query_status"] == "blocked"
    assert trace["target_material_status"] == "unverified"
    assert trace["experiment_id"] == ""
    assert trace["design_path_to_root"] == []
    assert trace["partial_result_suppressed"] is True


def test_child_output_listing_without_parent_input_receipt_cannot_complete() -> None:
    spec = _spec()
    blocks = list(spec.design_blocks)
    blocks[1] = replace(blocks[1], child_output_bindings=())
    result = check_blueprint(replace(spec, design_blocks=tuple(blocks)))
    assert result.status == "incomplete"
    assert any(item.code == "missing-child-output-binding" for item in result.gaps)


def test_simultaneous_model_universe_authority_shrink_cannot_self_sign_complete() -> None:
    spec = _spec()
    universe = spec.target_universe
    assert universe is not None and universe.target_authority is not None
    blocks = tuple(
        replace(block, constraints=()) if block.block_id == "candidate:e1" else block
        for block in spec.design_blocks
    )
    authority = self_resign_target_authority(
        universe.target_authority,
        (
            item
            for item in universe.target_authority.items
            if not (item.kind == "constraint" and item.object_id == "e1:constraint")
        ),
    )
    shrunk_universe = replace(
        universe,
        required_constraint_ids=("e2:constraint",),
        target_authority=authority,
    )
    result = check_blueprint(
        replace(spec, design_blocks=blocks, target_universe=shrunk_universe)
    )
    assert result.status == "incomplete"
    assert any(item.code == "native-target-denominator-mismatch" for item in result.gaps)


def test_fresh_process_first_issue_replays_original_experiment_target_material(
    tmp_path: Path,
) -> None:
    spec = _spec()
    universe = spec.target_universe
    assert universe is not None
    blocks = tuple(
        replace(block, constraints=()) if block.block_id == "candidate:e1" else block
        for block in spec.design_blocks
    )
    shrunk = replace(
        spec,
        design_blocks=blocks,
        target_universe=replace(
            universe,
            required_constraint_ids=("e2:constraint",),
            native_case_evidence=(),
            target_authority=None,
        ),
    )
    rebuilt_blocks = list(shrunk.design_blocks)
    parent = rebuilt_blocks[1]
    rebuilt_blocks[1] = replace(
        parent,
        child_output_bindings=tuple(
            create_child_output_binding(
                shrunk,
                binding_id=f"child-output:{candidate_id}:{port_kind}",
                child_block_id=f"candidate:{candidate_id}",
                child_output_port_id=f"{candidate_id}:{port_kind}",
                parent_block_id=parent.block_id,
                parent_input_port_id=f"{parent.block_id}:input:{candidate_id}:{port_kind}",
            )
            for candidate_id in ("e1", "e2")
            for port_kind in ("observation", "outcome")
        ),
    )
    shrunk = replace(shrunk, design_blocks=tuple(rebuilt_blocks))
    assert universe.target_authority is not None
    assert universe.target_authority.native_attestation is not None
    spec_path = tmp_path / "shrunk-experiment.json"
    spec_path.write_text(json.dumps(shrunk.to_dict()), encoding="utf-8")
    context_path = tmp_path / "experiment-child-context.json"
    context_path.write_text(
        json.dumps(
            {
                "spec_path": str(spec_path),
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
from dataclasses import replace
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path.cwd() / 'tests'))
from target_material_fixtures import install_test_expected_target_producer
install_test_expected_target_producer()
from admission_fixtures import install_test_native_receipt_producers
install_test_native_receipt_producers()
from researchguard.experiment import check_blueprint
from researchguard.experiment.blueprint import _bind_experiment_target_authority as issue_experiment_target_authority, _run_native_case_evidence as create_native_case_evidence
from researchguard.experiment.cli import _load_spec
from researchguard.target_authority import ExpectedTargetAnchor

context = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
spec = _load_spec(Path(context['spec_path']))
spec = issue_experiment_target_authority(
    spec,
    expected_target_anchor=ExpectedTargetAnchor.from_dict(context['expected_target_anchor']),
)
evidence = (
    create_native_case_evidence(spec, case_id='case:complete', case_kind='known_good'),
    create_native_case_evidence(spec, case_id='case:missing-port', case_kind='known_bad'),
)
spec = replace(spec, target_universe=replace(spec.target_universe, native_case_evidence=evidence))
result = check_blueprint(spec)
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
    assert ["target-authority-omitted-constraint", "e1:constraint"] in payload["gaps"]


@pytest.mark.parametrize(
    ("changes", "gap_code"),
    [
        ({"payload_fingerprint": "sha256:" + "8" * 64}, "child-output-payload-stale"),
        ({"producer_model_fingerprint": "sha256:" + "9" * 64}, "child-output-model-stale"),
        ({"producer_result_fingerprint": "sha256:" + "a" * 64}, "child-output-result-stale"),
        ({"receipt_status": "stale"}, "child-output-receipt-not-current"),
        ({"receipt_fingerprint": "sha256:" + "b" * 64}, "child-output-receipt-mismatch"),
    ],
)
def test_child_output_parent_binding_replays_current_payload_and_receipt(
    changes: dict[str, str], gap_code: str
) -> None:
    spec = _spec()
    blocks = list(spec.design_blocks)
    parent = blocks[1]
    bindings = list(parent.child_output_bindings)
    bindings[0] = replace(bindings[0], **changes)
    blocks[1] = replace(parent, child_output_bindings=tuple(bindings))
    result = check_blueprint(replace(spec, design_blocks=tuple(blocks)))
    assert result.status == "incomplete"
    assert any(item.code == gap_code for item in result.gaps)


def test_reverse_trace_exposes_current_child_output_parent_input_receipts() -> None:
    trace = reverse_trace_experiment(_spec(), "e1")
    bindings = trace["child_output_to_parent_input_bindings"]
    assert len(bindings) == 2
    assert {item["receipt_status"] for item in bindings} == {"current"}
    assert {item["parent_block_id"] for item in bindings} == {"discrimination:all"}
    assert all(item["payload_fingerprint"].startswith("sha256:") for item in bindings)


def test_naked_case_ids_cannot_complete_native_layer() -> None:
    spec = _spec()
    universe = replace(spec.target_universe, native_case_evidence=())
    result = check_blueprint(replace(spec, target_universe=universe))
    assert result.status == "incomplete"
    assert {item.object_id for item in result.gaps if item.code == "missing-native-case-evidence"} == {
        "case:complete",
        "case:missing-port",
    }
    assert result.layer_statuses[-1]["status"] == "failed"


@pytest.mark.parametrize(
    ("changes", "gap_code"),
    [
        ({"status": "stale"}, "native-case-not-current"),
        ({"case_kind": "known_bad"}, "native-case-kind-mismatch"),
        ({"subject_model_fingerprint": "sha256:" + "1" * 64}, "stale-native-case-subject"),
        ({"candidate_design_fingerprint": "sha256:" + "2" * 64}, "stale-native-case-candidates"),
        ({"result_fingerprint": "sha256:" + "3" * 64}, "native-case-result-mismatch"),
        ({"receipt_fingerprint": "sha256:" + "4" * 64}, "native-case-receipt-mismatch"),
    ],
)
def test_native_case_receipt_is_replayed_not_trusted(changes: dict[str, str], gap_code: str) -> None:
    spec = _spec()
    rows = list(spec.target_universe.native_case_evidence)
    rows[0] = replace(rows[0], **changes)
    universe = replace(spec.target_universe, native_case_evidence=tuple(rows))
    result = check_blueprint(replace(spec, target_universe=universe))
    assert result.status == "incomplete"
    assert any(item.code == gap_code and item.object_id == "case:complete" for item in result.gaps)


def test_hierarchy_cycle_and_unconsumed_output_are_exact_gaps() -> None:
    spec = _spec()
    blocks = list(spec.design_blocks)
    blocks[0] = replace(blocks[0], parent_id="candidate:e1")
    blocks[1] = replace(blocks[1], consumed_child_output_port_ids=())
    result = check_blueprint(replace(spec, design_blocks=tuple(blocks)))
    codes = {item.code for item in result.gaps}
    assert "invalid-root" in codes or "cycle" in codes
    assert "unconsumed-child-output" in codes
    assert result.deepest_proven_layer == "purpose"
    assert result.layer_statuses[0]["status"] == "failed"
    assert all(item["status"] == "not_run" for item in result.layer_statuses[1:])


def test_missing_manipulation_port_and_independent_universe_omission_block() -> None:
    spec = _spec()
    blocks = list(spec.design_blocks)
    candidate = blocks[2]
    blocks[2] = replace(candidate, ports=tuple(item for item in candidate.ports if item.kind != "manipulation"))
    universe = replace(spec.target_universe, required_hypothesis_ids=("h1", "h2", "h3"))
    result = check_blueprint(replace(spec, design_blocks=tuple(blocks), target_universe=universe))
    assert any(item.code == "missing-manipulation-port" for item in result.gaps)
    assert any(item.object_id == "h3" for item in result.gaps)
    assert result.first_unresolved_gap


def test_impact_and_reverse_trace_follow_same_design_identities() -> None:
    spec = _spec()
    impact = impact_blueprint(spec, ("e1:outcome",))
    assert impact["affected_candidate_ids"] == ["e1"]
    assert impact["affected_hypothesis_pairs"] == [["h1", "h2"]]
    trace = reverse_trace_experiment(spec, "e1")
    assert trace["design_block_id"] == "candidate:e1"
    assert trace["external_execution_status"] == "not_run"
    assert trace["external_observation_refs"] == []
    assert trace["input_port_ids"] == ["e1:input"]
    assert trace["manipulation_port_ids"] == ["e1:manipulation"]
    assert trace["constraint_ids"] == ["e1:constraint"]
    assert [item["consumer_port_id"] for item in trace["terminal_input_sources"]] == [
        "e1:input",
        "e1:manipulation",
    ]
    assert trace["design_path_to_root"] == ["candidate:e1", "discrimination:all", "purpose:root"]
    assert trace["discriminated_hypothesis_pairs"] == [["h1", "h2"]]
    with pytest.raises(ValueError, match="must resolve to exactly one candidate block"):
        reverse_trace_experiment(spec, "experiment:missing")


def test_observation_ports_are_checked_without_executing_experiment() -> None:
    spec = _spec()
    observation = ExperimentObservation(
        experiment_id="e1",
        observed_outcome="up",
        evidence_id="evidence:e1",
        evidence_fingerprint="sha256:" + "a" * 64,
        source_ref="external:run:e1",
        observed_at="2026-08-04T00:00:00+00:00",
        role="construction",
        observation_port_id="wrong-port",
        outcome_port_id="e1:outcome",
    )
    receipt = observe_experiments(spec, (observation,))
    assert "observation-port-mismatch:e1" in receipt.introduced_gap_ids
    assert receipt.terminal_reason == "external_input_required"


def test_blueprint_cannot_shrink_its_own_target_denominator() -> None:
    spec = _spec()
    root, parent, first_candidate, _second_candidate = spec.design_blocks
    reduced_parent = replace(
        parent,
        child_ids=(first_candidate.block_id,),
        consumed_child_output_port_ids=("e1:observation", "e1:outcome"),
    )
    reduced_predictions = tuple(
        replace(
            row,
            outcomes_by_experiment={"e1": row.outcomes_by_experiment["e1"]},
            observation_port_by_experiment={"e1": row.observation_port_by_experiment["e1"]},
            outcome_port_by_experiment={"e1": row.outcome_port_by_experiment["e1"]},
        )
        for row in spec.hypothesis_predictions
    )
    reduced_universe = replace(
        spec.target_universe,
        required_candidate_ids=("e1",),
        required_port_ids=("e1:manipulation", "e1:input", "e1:observation", "e1:outcome"),
        required_procedure_step_ids=("e1:step",),
        required_constraint_ids=("e1:constraint",),
        required_input_binding_ids=("binding:e1:input", "binding:e1:manipulation"),
        native_case_evidence=(),
    )
    reduced = replace(
        spec,
        coverage_ids=("h1", "h2", "e1"),
        hypothesis_predictions=reduced_predictions,
        candidate_experiment_ids=("e1",),
        design_blocks=(root, reduced_parent, first_candidate),
        target_universe=reduced_universe,
    )
    reduced = replace(
        reduced,
        target_universe=replace(
            reduced_universe,
            native_case_evidence=(
                create_native_case_evidence(reduced, case_id="case:complete", case_kind="known_good"),
                create_native_case_evidence(reduced, case_id="case:missing-port", case_kind="known_bad"),
            ),
        ),
    )
    assert check_blueprint(reduced).status == "incomplete"


def test_reverse_trace_reports_invalid_blueprint_before_emitting_success_chain() -> None:
    spec = _spec()
    parent = replace(spec.design_blocks[1], parent_id="candidate:e1")
    broken = replace(spec, design_blocks=(spec.design_blocks[0], parent, *spec.design_blocks[2:]))
    trace = reverse_trace_experiment(broken, "e1")
    assert trace["trace_status"] == "incomplete"
    assert trace["trace_gaps"]


def test_input_port_and_output_disposition_are_validated_at_runtime() -> None:
    spec = _spec()
    blocks = list(spec.design_blocks)
    candidate = blocks[2]
    blocks[2] = replace(candidate, ports=tuple(item for item in candidate.ports if item.kind != "input"))
    parent = blocks[1]
    blocks[1] = replace(parent, output_dispositions=(("foreign:port", "unexpected"),))
    result = check_blueprint(replace(spec, design_blocks=tuple(blocks)))
    codes = {item.code for item in result.gaps}
    assert "missing-input-port" in codes
    assert "invalid-output-disposition" in codes


def test_candidate_input_requires_one_typed_owned_producer() -> None:
    spec = _spec()
    blocks = list(spec.design_blocks)
    candidate = blocks[2]
    blocks[2] = replace(
        candidate,
        input_bindings=tuple(
            item for item in candidate.input_bindings if item.consumer_port_id != "e1:input"
        ),
    )
    result = check_blueprint(replace(spec, design_blocks=tuple(blocks)))
    assert any(
        item.code == "missing-input-binding" and item.detail == "e1:input"
        for item in result.gaps
    )


def test_input_binding_change_affects_owner_and_ancestors_not_sibling() -> None:
    impact = impact_blueprint(_spec(), ("binding:e1:input",))
    assert impact["affected_candidate_ids"] == ["e1"]
    assert impact["affected_design_block_ids"] == [
        "candidate:e1",
        "discrimination:all",
        "purpose:root",
    ]


def test_parent_and_hypothesis_changes_propagate_to_all_candidate_evidence() -> None:
    spec = _spec()
    parent_impact = impact_blueprint(spec, ("purpose:root",))
    assert parent_impact["affected_candidate_ids"] == ["e1", "e2"]
    assert parent_impact["affected_observation_ids"] == ["observation:e1", "observation:e2"]
    hypothesis_impact = impact_blueprint(spec, ("h1",))
    assert hypothesis_impact["affected_candidate_ids"] == ["e1", "e2"]
    assert hypothesis_impact["affected_holdout_ids"] == ["holdout:e1", "holdout:e2"]
    assert hypothesis_impact["affected_receipt_ids"] == ["recommendation:blueprint-task"]


def test_leaf_change_reaches_ancestors_without_unrelated_sibling() -> None:
    impact = impact_blueprint(_spec(), ("e1:outcome",))
    assert impact["affected_design_block_ids"] == [
        "candidate:e1",
        "discrimination:all",
        "purpose:root",
    ]
    assert impact["affected_candidate_ids"] == ["e1"]


def test_mixed_known_and_unknown_change_remains_blocked() -> None:
    impact = impact_blueprint(_spec(), ("e1:outcome", "foreign:unowned"))
    assert impact["affected_candidate_ids"] == []
    assert impact["affected_hypothesis_ids"] == []
    assert impact["unknown_dependency_ids"] == ["foreign:unowned"]
    assert impact["unknown_ownership"] is True
    assert impact["partial_result_suppressed"] is True


@pytest.mark.parametrize(
    "changed_id",
    (
        "e1",
        "e1:outcome",
        "e1:step",
        "e1:constraint",
        "binding:e1:input",
    ),
)
def test_every_candidate_design_identity_reaches_predictions_pairs_and_receipt(
    changed_id: str,
) -> None:
    impact = impact_blueprint(_spec(), (changed_id,))
    assert impact["affected_candidate_ids"] == ["e1"]
    assert impact["affected_hypothesis_ids"] == ["h1", "h2"]
    assert impact["affected_hypothesis_pairs"] == [["h1", "h2"]]
    assert impact["affected_receipt_ids"] == ["recommendation:blueprint-task"]


def test_universe_and_native_case_receipt_are_stable_global_impact_seeds() -> None:
    spec = _spec()
    for changed_id in (
        spec.target_universe.universe_id,
        check_blueprint(spec).target_universe_fingerprint,
        spec.target_universe.native_case_evidence[0].receipt_id,
        spec.target_universe.native_case_evidence[0].receipt_fingerprint,
    ):
        impact = impact_blueprint(spec, (changed_id,))
        assert impact["affected_candidate_ids"] == ["e1", "e2"]
        assert impact["affected_hypothesis_ids"] == ["h1", "h2"]
        assert impact["affected_native_case_receipt_ids"] == [
            "experiment-native-case:blueprint-task:case:complete",
            "experiment-native-case:blueprint-task:case:missing-port",
        ]


def test_blueprint_cli_has_one_grouped_surface_and_no_flat_alias(tmp_path, capsys) -> None:
    from researchguard.experiment.cli import main

    spec_path = tmp_path / "experiment.json"
    spec_path.write_text(json.dumps(_spec().to_dict()), encoding="utf-8")
    assert main(["blueprint", "check", str(spec_path)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "complete"
    assert main(["blueprint", "impact", str(spec_path), "e1:step"]) == 0
    assert json.loads(capsys.readouterr().out)["affected_candidate_ids"] == ["e1"]
    assert main(["blueprint", "impact", str(spec_path), "e1:step", "foreign:unowned"]) == 3
    blocked = json.loads(capsys.readouterr().out)
    assert blocked["partial_result_suppressed"] is True
    assert blocked["affected_candidate_ids"] == []
    assert main(["blueprint", "trace", str(spec_path), "e1"]) == 0
    assert json.loads(capsys.readouterr().out)["experiment_id"] == "e1"
    assert main(["blueprint", "export", str(spec_path)]) == 0
    assert json.loads(capsys.readouterr().out)["check"]["status"] == "complete"
    with pytest.raises(SystemExit) as exc:
        main(["blueprint-check", str(spec_path)])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc:
        main(["blueprint", "unknown", str(spec_path)])
    assert exc.value.code == 2
    unknown = _spec().to_dict()
    unknown["design_blocks"][0]["legacy_alias"] = "forbidden"
    spec_path.write_text(json.dumps(unknown), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown current-blueprint fields"):
        main(["blueprint", "check", str(spec_path)])

    malformed = _spec().to_dict()
    malformed["target_universe"]["required_port_ids"] = "e1:input"
    spec_path.write_text(json.dumps(malformed), encoding="utf-8")
    with pytest.raises(ValueError, match="target_universe.required_port_ids must be a list"):
        main(["blueprint", "check", str(spec_path)])

    malformed["target_universe"] = []
    spec_path.write_text(json.dumps(malformed), encoding="utf-8")
    with pytest.raises(ValueError, match="target_universe must be an object"):
        main(["blueprint", "check", str(spec_path)])


def test_observation_with_invalid_candidate_blueprint_fails_closed_without_stop_iteration() -> None:
    spec = _spec()
    invalid = replace(
        spec,
        design_blocks=tuple(
            block for block in spec.design_blocks if block.candidate_experiment_id != "e1"
        ),
    )
    observation = ExperimentObservation(
        experiment_id="e1",
        observed_outcome="up",
        evidence_id="evidence:e1:invalid-blueprint",
        evidence_fingerprint="sha256:" + "d" * 64,
        source_ref="external:run:e1",
        observed_at="2026-08-04T00:00:00+00:00",
        role="construction",
        observation_port_id="e1:observation",
        outcome_port_id="e1:outcome",
    )
    receipt = observe_experiments(invalid, (observation,))
    assert "observation-blueprint-candidate-missing:e1" in receipt.introduced_gap_ids
    assert any(
        item.startswith("experiment-blueprint-")
        for item in receipt.introduced_gap_ids
    )
    assert receipt.terminal_reason == "external_input_required"
