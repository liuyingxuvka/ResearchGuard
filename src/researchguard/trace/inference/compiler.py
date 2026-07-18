"""Compile one schema-v2 model into one canonical inference problem."""

from __future__ import annotations

from typing import Any

from ..schema import SCHEMA_ID, TraceGuardModel
from ..validation import validate_references
from .factors import (
    build_entity_factors,
    build_evidence_trace_factors,
    build_storyline_causal_factors,
    build_temporal_stage_factors,
)
from .policy import InferencePolicy
from .types import CompiledProblem, CompilationError


def _unique(items: list[Any], id_attribute: str) -> tuple[Any, ...]:
    by_id: dict[str, Any] = {}
    for item in items:
        item_id = str(getattr(item, id_attribute))
        if item_id in by_id:
            raise CompilationError(f"duplicate {id_attribute} {item_id}")
        by_id[item_id] = item
    return tuple(by_id[item_id] for item_id in sorted(by_id))


def compile_model(
    model: TraceGuardModel,
    policy: InferencePolicy,
) -> CompiledProblem:
    """TraceGuardModel x Policy -> CompiledProblem."""

    if model.metadata.get("schema_version") != SCHEMA_ID:
        raise CompilationError(f"only {SCHEMA_ID} can enter the inference compiler")
    validate_references(model)
    builders = (
        build_evidence_trace_factors,
        build_entity_factors,
        build_temporal_stage_factors,
        build_storyline_causal_factors,
    )
    observed: list[Any] = []
    latent: list[Any] = []
    factors: list[Any] = []
    constraints: list[Any] = []
    diagnostics: list[Any] = []
    gaps: list[Any] = []
    contradictions: list[Any] = []
    metadata: dict[str, Any] = {
        "builder_order": [builder.__module__ for builder in builders],
        "model_instance_id": model.metadata.get("model_instance_id", ""),
    }
    for builder in builders:
        result = builder(model, policy)
        observed.extend(result["observed_atoms"])
        latent.extend(result["latent_atoms"])
        factors.extend(result["factors"])
        constraints.extend(result["hard_constraints"])
        diagnostics.extend(result["diagnostics"])
        gaps.extend(result["gaps"])
        contradictions.extend(result["contradictions"])
        metadata.update(result["metadata"])

    metadata.update(
        {
            "diagnostics": diagnostics,
            "gaps": gaps,
            "contradictions": contradictions,
            "policy_fingerprint": policy.policy_fingerprint,
            "model_schema_id": SCHEMA_ID,
        }
    )
    return CompiledProblem(
        schema_id=SCHEMA_ID,
        policy_id=policy.policy_id,
        factor_set_id=policy.factor_set_id,
        solver_id=policy.solver_id,
        observed_atoms=_unique(observed, "atom_id"),
        latent_atoms=_unique(latent, "atom_id"),
        factors=_unique(factors, "factor_id"),
        hard_constraints=_unique(constraints, "constraint_id"),
        metadata=metadata,
    )
