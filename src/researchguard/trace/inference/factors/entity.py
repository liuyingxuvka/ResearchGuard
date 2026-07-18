"""Entity-resolution factors inside the unified inference objective."""

from __future__ import annotations

from itertools import combinations

from ...diagnostics import Diagnostic
from ...entity_resolution import score_entities
from ...schema import TraceGuardModel
from ..policy import InferencePolicy
from ..types import HardConstraint, HingeFactor, LatentAtom, LinearExpression, ObservedAtom


def build_entity_factors(
    model: TraceGuardModel,
    policy: InferencePolicy,
) -> dict[str, object]:
    observed: list[ObservedAtom] = []
    latent: list[LatentAtom] = []
    factors: list[HingeFactor] = []
    constraints: list[HardConstraint] = []
    diagnostics: list[Diagnostic] = []
    score_metadata: list[dict[str, object]] = []

    explicit_pairs = {
        frozenset((item.left_id, item.right_id)): item
        for item in model.entity_resolutions
    }
    for left, right in combinations(model.entities, 2):
        heuristic = score_entities(left, right)
        pair_id = f"{left.mention_id}:{right.mention_id}"
        observed_id = f"entity_similarity_observed:{pair_id}"
        latent_id = f"entity_same:{pair_id}"
        observed.append(
            ObservedAtom(
                atom_id=observed_id,
                value=heuristic.score,
                kind="entity_similarity_observed",
                object_id=pair_id,
                evidence_ids=tuple(
                    item
                    for item in (left.evidence_id, right.evidence_id)
                    if item is not None
                ),
                metadata={
                    "reasons": heuristic.reasons,
                    "blockers": heuristic.blockers,
                },
            )
        )
        latent.append(
            LatentAtom(
                atom_id=latent_id,
                kind="entity_same",
                object_id=pair_id,
            )
        )
        factors.extend(
            (
                HingeFactor(
                    factor_id=f"entity-observation:{pair_id}",
                    family="entity_resolution",
                    description="Name, alias, country, and role observations support entity identity.",
                    expression=LinearExpression(
                        ((observed_id, 1.0), (latent_id, -1.0))
                    ),
                    weight=policy.entity_weight,
                    affected_object_ids=(left.mention_id, right.mention_id),
                    direction="support",
                ),
                HingeFactor(
                    factor_id=f"entity-sparsity:{pair_id}",
                    family="sparsity",
                    description="Unproved entity identity remains conservative.",
                    expression=LinearExpression(((latent_id, 1.0),)),
                    weight=policy.sparsity_weight,
                    affected_object_ids=(left.mention_id, right.mention_id),
                    direction="oppose",
                ),
            )
        )
        if heuristic.blockers:
            constraints.append(
                HardConstraint(
                    constraint_id=f"entity-blocker-cap:{pair_id}",
                    description="Country or role blockers prevent a same-as inference.",
                    expression=LinearExpression(((latent_id, 1.0),)),
                    upper=0.54,
                    affected_object_ids=(left.mention_id, right.mention_id),
                )
            )
        explicit = explicit_pairs.get(frozenset((left.mention_id, right.mention_id)))
        if explicit and explicit.relation == "same_as" and explicit.blockers:
            diagnostics.append(
                Diagnostic(
                    "overmerge_risk",
                    "warning",
                    "Explicit same_as relation has blocker reasons.",
                    (left.mention_id, right.mention_id),
                    False,
                    "Resolve blockers before treating the entities as identical.",
                    "entity_resolution",
                )
            )
        if (
            heuristic.relation == "possible_same_as"
            and frozenset((left.mention_id, right.mention_id)) not in explicit_pairs
        ):
            diagnostics.append(
                Diagnostic(
                    "undermerge_risk",
                    "info",
                    "Two entities should be reviewed for possible undermerge.",
                    (left.mention_id, right.mention_id),
                    False,
                    "Review aliases, country, role, and context before linking.",
                    "entity_resolution",
                )
            )
        score_metadata.append(
            {
                "left_id": left.mention_id,
                "right_id": right.mention_id,
                "atom_id": latent_id,
                "reasons": list(heuristic.reasons),
                "blockers": list(heuristic.blockers),
            }
        )

    return {
        "observed_atoms": observed,
        "latent_atoms": latent,
        "factors": factors,
        "hard_constraints": constraints,
        "diagnostics": diagnostics,
        "gaps": [],
        "contradictions": [],
        "metadata": {"entity_pairs": score_metadata},
    }
