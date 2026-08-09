"""Strict, current-only ExperimentGuard task and receipt schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Literal

from ..native_receipts import NativeReceiptReference
from ..target_authority import TargetPurposeAuthority


EXPERIMENT_SPEC_SCHEMA = "researchguard.experiment.task-spec.v3"
EXPERIMENT_ITERATION_SCHEMA = "researchguard.experiment.iteration-receipt.v2"
EXPERIMENT_NATIVE_CASE_CHECK = "researchguard.experiment.blueprint-case-check.v1"
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def _digest(value: object) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(body.encode('utf-8')).hexdigest()}"


def _unique(values: tuple[str, ...], field: str, *, allow_empty: bool = True) -> None:
    if (not allow_empty and not values) or any(not item.strip() for item in values):
        raise ValueError(f"{field} requires non-empty strings")
    if len(set(values)) != len(values):
        raise ValueError(f"{field} must not contain duplicates")


@dataclass(frozen=True)
class HypothesisPrediction:
    hypothesis_id: str
    outcomes_by_experiment: dict[str, str]
    observation_port_by_experiment: dict[str, str] | None = None
    outcome_port_by_experiment: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if not self.hypothesis_id.strip():
            raise ValueError("hypothesis_id is required")
        if any(not str(key).strip() or not str(value).strip() for key, value in self.outcomes_by_experiment.items()):
            raise ValueError("experiment predictions require non-empty ids and outcomes")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentPort:
    port_id: str
    kind: Literal["input", "manipulation", "observation", "outcome"]
    schema_id: str
    allowed_values: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.port_id.strip() or not self.schema_id.strip():
            raise ValueError("experiment ports require port_id and schema_id")
        _unique(self.allowed_values, "allowed_values")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProcedureStep:
    step_id: str
    order: int
    action: str
    input_port_ids: tuple[str, ...]
    output_port_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.step_id.strip() or not self.action.strip() or self.order < 0:
            raise ValueError("procedure steps require id, action, and non-negative order")
        _unique(self.input_port_ids, "input_port_ids")
        _unique(self.output_port_ids, "output_port_ids", allow_empty=False)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentConstraint:
    constraint_id: str
    description: str

    def __post_init__(self) -> None:
        if not self.constraint_id.strip() or not self.description.strip():
            raise ValueError("experiment constraints require id and description")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentInputBinding:
    binding_id: str
    consumer_port_id: str
    producer_kind: Literal["parent", "external", "state", "sibling"]
    producer_id: str
    producer_port_id: str
    payload_schema_id: str
    cardinality: Literal["one", "many", "optional"]
    owner_id: str

    def __post_init__(self) -> None:
        required = (
            self.binding_id,
            self.consumer_port_id,
            self.producer_id,
            self.payload_schema_id,
            self.owner_id,
        )
        if any(not value.strip() for value in required):
            raise ValueError("experiment input bindings require stable endpoint, schema, and owner identities")
        if self.producer_kind in {"parent", "sibling"} and not self.producer_port_id.strip():
            raise ValueError("parent and sibling input bindings require producer_port_id")
        if self.producer_kind not in {"parent", "external", "state", "sibling"}:
            raise ValueError("experiment input binding producer_kind is not current")
        if self.cardinality not in {"one", "many", "optional"}:
            raise ValueError("experiment input binding cardinality is not current")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentChildOutputBinding:
    binding_id: str
    child_block_id: str
    child_output_port_id: str
    parent_block_id: str
    parent_input_port_id: str
    payload_schema_id: str
    refinement_id: str
    payload_fingerprint: str
    producer_model_fingerprint: str
    producer_result_fingerprint: str
    producer_task_id: str
    receipt_id: str
    receipt_fingerprint: str
    receipt_status: Literal["current", "stale", "failed", "not_run"] = "current"

    def __post_init__(self) -> None:
        required = (
            self.binding_id,
            self.child_block_id,
            self.child_output_port_id,
            self.parent_block_id,
            self.parent_input_port_id,
            self.payload_schema_id,
            self.refinement_id,
            self.producer_task_id,
            self.receipt_id,
        )
        if any(not value.strip() for value in required):
            raise ValueError("child-output bindings require exact endpoints, schema, refinement, task, and receipt")
        for value in (
            self.payload_fingerprint,
            self.producer_model_fingerprint,
            self.producer_result_fingerprint,
            self.receipt_fingerprint,
        ):
            if not _SHA256.fullmatch(value):
                raise ValueError("child-output binding fingerprints must be exact sha256 values")
        if self.receipt_status not in {"current", "stale", "failed", "not_run"}:
            raise ValueError("child-output binding receipt status is not current")

    @property
    def expected_receipt_fingerprint(self) -> str:
        return _digest(
            {
                "binding_id": self.binding_id,
                "child_block_id": self.child_block_id,
                "child_output_port_id": self.child_output_port_id,
                "parent_block_id": self.parent_block_id,
                "parent_input_port_id": self.parent_input_port_id,
                "payload_schema_id": self.payload_schema_id,
                "refinement_id": self.refinement_id,
                "payload_fingerprint": self.payload_fingerprint,
                "producer_model_fingerprint": self.producer_model_fingerprint,
                "producer_result_fingerprint": self.producer_result_fingerprint,
                "producer_task_id": self.producer_task_id,
                "receipt_id": self.receipt_id,
                "receipt_status": self.receipt_status,
            }
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentDesignBlock:
    block_id: str
    kind: Literal[
        "purpose",
        "hypothesis_family",
        "discrimination_obligation",
        "candidate_experiment",
        "procedure",
    ]
    parent_id: str
    child_ids: tuple[str, ...] = ()
    candidate_experiment_id: str = ""
    ports: tuple[ExperimentPort, ...] = ()
    procedure_steps: tuple[ProcedureStep, ...] = ()
    constraints: tuple[ExperimentConstraint, ...] = ()
    external_execution_owner: str = ""
    consumed_child_output_port_ids: tuple[str, ...] = ()
    output_dispositions: tuple[tuple[str, Literal["unresolved", "excluded", "terminal"]], ...] = ()
    input_bindings: tuple[ExperimentInputBinding, ...] = ()
    child_output_bindings: tuple[ExperimentChildOutputBinding, ...] = ()

    def __post_init__(self) -> None:
        if not self.block_id.strip():
            raise ValueError("design block_id is required")
        _unique(self.child_ids, "child_ids")
        _unique(tuple(port.port_id for port in self.ports), "ports")
        _unique(tuple(step.step_id for step in self.procedure_steps), "procedure_steps")
        _unique(tuple(item.constraint_id for item in self.constraints), "constraints")
        _unique(self.consumed_child_output_port_ids, "consumed_child_output_port_ids")
        _unique(tuple(item[0] for item in self.output_dispositions), "output_dispositions")
        _unique(tuple(item.binding_id for item in self.input_bindings), "input_bindings")
        _unique(tuple(item.binding_id for item in self.child_output_bindings), "child_output_bindings")
        if self.kind == "candidate_experiment":
            if not self.candidate_experiment_id.strip() or not self.external_execution_owner.strip():
                raise ValueError("candidate blocks require candidate_experiment_id and external_execution_owner")

    def to_dict(self) -> dict[str, object]:
        return {
            "block_id": self.block_id,
            "kind": self.kind,
            "parent_id": self.parent_id,
            "child_ids": list(self.child_ids),
            "candidate_experiment_id": self.candidate_experiment_id,
            "ports": [item.to_dict() for item in self.ports],
            "procedure_steps": [item.to_dict() for item in self.procedure_steps],
            "constraints": [item.to_dict() for item in self.constraints],
            "external_execution_owner": self.external_execution_owner,
            "consumed_child_output_port_ids": list(self.consumed_child_output_port_ids),
            "output_dispositions": [list(item) for item in self.output_dispositions],
            "input_bindings": [item.to_dict() for item in self.input_bindings],
            "child_output_bindings": [item.to_dict() for item in self.child_output_bindings],
        }


@dataclass(frozen=True)
class ExperimentTargetUniverse:
    universe_id: str
    required_hypothesis_ids: tuple[str, ...]
    required_discrimination_ids: tuple[str, ...]
    required_candidate_ids: tuple[str, ...]
    required_port_ids: tuple[str, ...]
    required_procedure_step_ids: tuple[str, ...]
    required_constraint_ids: tuple[str, ...]
    required_input_binding_ids: tuple[str, ...]
    required_child_output_binding_ids: tuple[str, ...]
    known_good_case_ids: tuple[str, ...]
    known_bad_case_ids: tuple[str, ...]
    native_case_evidence: tuple["ExperimentNativeCaseEvidence", ...] = ()
    native_receipt_refs: tuple[NativeReceiptReference, ...] = ()
    target_authority: TargetPurposeAuthority | None = None

    def __post_init__(self) -> None:
        if not self.universe_id.strip():
            raise ValueError("experiment target universe requires universe_id")
        for field in (
            "required_hypothesis_ids",
            "required_discrimination_ids",
            "required_candidate_ids",
            "required_port_ids",
            "required_procedure_step_ids",
            "required_constraint_ids",
            "required_input_binding_ids",
            "required_child_output_binding_ids",
            "known_good_case_ids",
            "known_bad_case_ids",
        ):
            _unique(getattr(self, field), field, allow_empty=field.startswith("known_"))
        _unique(tuple(item.case_id for item in self.native_case_evidence), "native_case_evidence")
        _unique(tuple(item.receipt_id for item in self.native_receipt_refs), "native_receipt_refs")

    def to_dict(self) -> dict[str, object]:
        return {
            "universe_id": self.universe_id,
            "required_hypothesis_ids": list(self.required_hypothesis_ids),
            "required_discrimination_ids": list(self.required_discrimination_ids),
            "required_candidate_ids": list(self.required_candidate_ids),
            "required_port_ids": list(self.required_port_ids),
            "required_procedure_step_ids": list(self.required_procedure_step_ids),
            "required_constraint_ids": list(self.required_constraint_ids),
            "required_input_binding_ids": list(self.required_input_binding_ids),
            "required_child_output_binding_ids": list(self.required_child_output_binding_ids),
            "known_good_case_ids": list(self.known_good_case_ids),
            "known_bad_case_ids": list(self.known_bad_case_ids),
            "native_case_evidence": [item.to_dict() for item in self.native_case_evidence],
            "native_receipt_refs": [item.to_dict() for item in self.native_receipt_refs],
            "target_authority": self.target_authority.to_dict() if self.target_authority else None,
        }


@dataclass(frozen=True)
class ExperimentNativeCaseEvidence:
    case_id: str
    case_kind: Literal["known_good", "known_bad"]
    owner_id: str
    native_check_id: str
    task_id: str
    subject_model_fingerprint: str
    prediction_matrix_fingerprint: str
    candidate_design_fingerprint: str
    target_authority_fingerprint: str
    failure_class_id: str
    case_input_fingerprint: str
    expected_terminal: Literal["passed", "rejected"]
    observed_terminal: Literal["passed", "rejected"]
    oracle_id: str
    result_fingerprint: str
    receipt_id: str
    receipt_fingerprint: str
    status: Literal["current", "stale", "failed", "not_run"] = "current"

    def __post_init__(self) -> None:
        required = (
            self.case_id,
            self.owner_id,
            self.native_check_id,
            self.task_id,
            self.oracle_id,
            self.receipt_id,
            self.failure_class_id,
        )
        if any(not value.strip() for value in required):
            raise ValueError("experiment native case evidence requires stable owner and receipt identities")
        for value in (
            self.subject_model_fingerprint,
            self.prediction_matrix_fingerprint,
            self.candidate_design_fingerprint,
            self.target_authority_fingerprint,
            self.case_input_fingerprint,
            self.result_fingerprint,
            self.receipt_fingerprint,
        ):
            if not _SHA256.fullmatch(value):
                raise ValueError("experiment native case evidence fingerprints must be exact sha256 values")
        if self.case_kind not in {"known_good", "known_bad"}:
            raise ValueError("experiment native case kind is not current")
        if self.expected_terminal not in {"passed", "rejected"} or self.observed_terminal not in {"passed", "rejected"}:
            raise ValueError("experiment native case terminal is not current")
        if self.status not in {"current", "stale", "failed", "not_run"}:
            raise ValueError("experiment native case status is not current")

    @property
    def expected_receipt_fingerprint(self) -> str:
        return _digest(
            {
                "case_id": self.case_id,
                "case_kind": self.case_kind,
                "owner_id": self.owner_id,
                "native_check_id": self.native_check_id,
                "task_id": self.task_id,
                "subject_model_fingerprint": self.subject_model_fingerprint,
                "prediction_matrix_fingerprint": self.prediction_matrix_fingerprint,
                "candidate_design_fingerprint": self.candidate_design_fingerprint,
                "target_authority_fingerprint": self.target_authority_fingerprint,
                "failure_class_id": self.failure_class_id,
                "case_input_fingerprint": self.case_input_fingerprint,
                "expected_terminal": self.expected_terminal,
                "observed_terminal": self.observed_terminal,
                "oracle_id": self.oracle_id,
                "result_fingerprint": self.result_fingerprint,
                "receipt_id": self.receipt_id,
                "status": self.status,
            }
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentSpec:
    task_id: str
    purpose: str
    coverage_ids: tuple[str, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    iteration: int
    max_iterations: int
    hypothesis_predictions: tuple[HypothesisPrediction, ...]
    candidate_experiment_ids: tuple[str, ...]
    design_root_id: str = ""
    design_blocks: tuple[ExperimentDesignBlock, ...] = ()
    target_universe: ExperimentTargetUniverse | None = None
    maximum_experiment_count: int | None = None
    prior_receipt_fingerprint: str = ""
    prior_open_gap_ids: tuple[str, ...] = ()
    schema_version: str = EXPERIMENT_SPEC_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != EXPERIMENT_SPEC_SCHEMA:
            raise ValueError("ExperimentGuard task spec requires the current schema")
        if not self.task_id.strip() or not self.purpose.strip():
            raise ValueError("task_id and purpose are required")
        _unique(self.coverage_ids, "coverage_ids", allow_empty=False)
        _unique(self.assumptions, "assumptions")
        _unique(self.unknowns, "unknowns")
        _unique(self.candidate_experiment_ids, "candidate_experiment_ids", allow_empty=False)
        _unique(self.prior_open_gap_ids, "prior_open_gap_ids")
        if self.iteration < 0 or self.max_iterations < 1:
            raise ValueError("iteration must be non-negative and max_iterations positive")
        if self.iteration and not self.prior_receipt_fingerprint.startswith("sha256:"):
            raise ValueError("later iterations require prior_receipt_fingerprint")
        hypothesis_ids = tuple(item.hypothesis_id for item in self.hypothesis_predictions)
        _unique(hypothesis_ids, "hypothesis_predictions", allow_empty=False)
        if len(hypothesis_ids) < 2:
            raise ValueError("at least two hypotheses are required")
        candidates = set(self.candidate_experiment_ids)
        for row in self.hypothesis_predictions:
            if not candidates.issubset(row.outcomes_by_experiment):
                raise ValueError("every hypothesis prediction must cover the candidate universe")
        if self.design_blocks or self.design_root_id or self.target_universe is not None:
            if not self.design_root_id or not self.design_blocks or self.target_universe is None:
                raise ValueError("blueprint-aware specs require root, blocks, and independent target universe")
            _unique(tuple(item.block_id for item in self.design_blocks), "design_blocks", allow_empty=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "purpose": self.purpose,
            "coverage_ids": list(self.coverage_ids),
            "assumptions": list(self.assumptions),
            "unknowns": list(self.unknowns),
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "hypothesis_predictions": [item.to_dict() for item in self.hypothesis_predictions],
            "candidate_experiment_ids": list(self.candidate_experiment_ids),
            "design_root_id": self.design_root_id,
            "design_blocks": [item.to_dict() for item in self.design_blocks],
            "target_universe": self.target_universe.to_dict() if self.target_universe else None,
            "maximum_experiment_count": self.maximum_experiment_count,
            "prior_receipt_fingerprint": self.prior_receipt_fingerprint,
            "prior_open_gap_ids": list(self.prior_open_gap_ids),
        }


@dataclass(frozen=True)
class ExperimentObservation:
    experiment_id: str
    observed_outcome: str
    evidence_id: str
    evidence_fingerprint: str
    source_ref: str
    observed_at: str
    role: Literal["construction", "holdout"]
    status: Literal["valid", "invalid", "not_run"] = "valid"
    observation_port_id: str = ""
    outcome_port_id: str = ""

    def __post_init__(self) -> None:
        required = (
            self.experiment_id,
            self.evidence_id,
            self.evidence_fingerprint,
            self.source_ref,
            self.observed_at,
        )
        if any(not value.strip() for value in required):
            raise ValueError("experiment observation identity fields are required")
        if not self.evidence_fingerprint.startswith("sha256:"):
            raise ValueError("evidence_fingerprint must be sha256-bound")
        if self.status == "valid" and not self.observed_outcome.strip():
            raise ValueError("valid observations require observed_outcome")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class HypothesisDisposition:
    hypothesis_id: str
    status: Literal["consistent", "eliminated", "underdetermined", "model_miss"]
    matched_experiment_ids: tuple[str, ...] = ()
    contradicted_experiment_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PredictionMatrixRevisionCandidate:
    candidate_id: str
    base_matrix_fingerprint: str
    unexpected_observation_ids: tuple[str, ...]
    required_actions: tuple[str, ...]
    disposition: Literal["not_applied"] = "not_applied"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentRecommendation:
    status: Literal["recommended", "indistinguishable", "blocked_invalid_input"]
    selected_experiment_ids: tuple[str, ...]
    alternative_minimal_sets: tuple[tuple[str, ...], ...]
    unresolved_hypothesis_pairs: tuple[tuple[str, str], ...]
    reason_code: str
    claim_boundary: str = (
        "ExperimentGuard recommends a minimum-cardinality distinguishing set "
        "for the caller-declared predictions. It does not execute experiments, "
        "invent probabilities, or decide which hypothesis is true."
    )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentIterationReceipt:
    task_id: str
    iteration: int
    base_matrix_fingerprint: str
    candidate_matrix_fingerprint: str
    recommendation: ExperimentRecommendation
    observations: tuple[ExperimentObservation, ...]
    hypothesis_dispositions: tuple[HypothesisDisposition, ...]
    input_gap_ids: tuple[str, ...]
    resolved_gap_ids: tuple[str, ...]
    persisted_gap_ids: tuple[str, ...]
    introduced_gap_ids: tuple[str, ...]
    open_hypothesis_pairs: tuple[tuple[str, str], ...]
    next_experiment_ids: tuple[str, ...]
    native_receipt_id: str
    revision_candidate: PredictionMatrixRevisionCandidate | None
    holdout_evidence_ids: tuple[str, ...]
    rollback_matrix_fingerprint: str
    terminal_reason: Literal[
        "continue_iteration",
        "model_closed_for_task",
        "external_input_required",
        "progress_stalled",
        "iteration_limit",
    ]
    progressed: bool
    receipt_fingerprint: str
    design_fingerprint: str = ""
    affected_obligation_ids: tuple[str, ...] = ()
    deepest_proven_layer: str = "native-recommendation"
    first_unresolved_gap: str = ""
    schema_version: str = EXPERIMENT_ITERATION_SCHEMA

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "iteration": self.iteration,
            "base_matrix_fingerprint": self.base_matrix_fingerprint,
            "candidate_matrix_fingerprint": self.candidate_matrix_fingerprint,
            "recommendation": self.recommendation.to_dict(),
            "observations": [item.to_dict() for item in self.observations],
            "hypothesis_dispositions": [item.to_dict() for item in self.hypothesis_dispositions],
            "input_gap_ids": list(self.input_gap_ids),
            "resolved_gap_ids": list(self.resolved_gap_ids),
            "persisted_gap_ids": list(self.persisted_gap_ids),
            "introduced_gap_ids": list(self.introduced_gap_ids),
            "open_hypothesis_pairs": [list(item) for item in self.open_hypothesis_pairs],
            "next_experiment_ids": list(self.next_experiment_ids),
            "native_receipt_id": self.native_receipt_id,
            "revision_candidate": self.revision_candidate.to_dict() if self.revision_candidate else None,
            "holdout_evidence_ids": list(self.holdout_evidence_ids),
            "rollback_matrix_fingerprint": self.rollback_matrix_fingerprint,
            "terminal_reason": self.terminal_reason,
            "progressed": self.progressed,
            "receipt_fingerprint": self.receipt_fingerprint,
            "design_fingerprint": self.design_fingerprint,
            "affected_obligation_ids": list(self.affected_obligation_ids),
            "deepest_proven_layer": self.deepest_proven_layer,
            "first_unresolved_gap": self.first_unresolved_gap,
        }


__all__ = [
    "EXPERIMENT_NATIVE_CASE_CHECK",
    "EXPERIMENT_ITERATION_SCHEMA",
    "EXPERIMENT_SPEC_SCHEMA",
    "ExperimentIterationReceipt",
    "ExperimentConstraint",
    "ExperimentDesignBlock",
    "ExperimentInputBinding",
    "ExperimentNativeCaseEvidence",
    "ExperimentObservation",
    "ExperimentPort",
    "ExperimentRecommendation",
    "ExperimentSpec",
    "ExperimentTargetUniverse",
    "HypothesisPrediction",
    "HypothesisDisposition",
    "PredictionMatrixRevisionCandidate",
    "ProcedureStep",
]
