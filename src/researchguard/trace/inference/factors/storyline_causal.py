"""Competing-storyline and bounded qualitative-causal factors."""

from __future__ import annotations

from collections import defaultdict

from ...schema import TraceGuardModel, clamp01
from ...temporal import allen_relation
from ..policy import InferencePolicy
from ..types import HardConstraint, HingeFactor, LatentAtom, LinearExpression, ObservedAtom
from .evidence_trace import evidence_quality


def _chronology_score(model: TraceGuardModel, cause_ids: list[str], effect_ids: list[str]) -> float:
    events = model.event_by_id()
    scores: list[float] = []
    for cause_id in cause_ids:
        for effect_id in effect_ids:
            cause = events[cause_id]
            effect = events[effect_id]
            if cause.time_interval is None or effect.time_interval is None:
                scores.append(0.0)
                continue
            relation = allen_relation(cause.time_interval, effect.time_interval)
            scores.append(1.0 if relation in {"before", "meets"} else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


def build_storyline_causal_factors(
    model: TraceGuardModel,
    policy: InferencePolicy,
) -> dict[str, object]:
    sources = model.source_by_id()
    evidence = model.evidence_by_id()
    observed: list[ObservedAtom] = []
    latent: list[LatentAtom] = []
    factors: list[HingeFactor] = []
    constraints: list[HardConstraint] = []
    metadata: dict[str, object] = {"causal_atoms": {}, "hypothesis_atoms": {}}

    links_by_hypothesis: dict[str, list[object]] = defaultdict(list)
    for link in model.hypothesis_evidence_links:
        links_by_hypothesis[link.hypothesis_id].append(link)

    for hypothesis in model.storyline_hypotheses:
        hypothesis_atom = f"hypothesis_support:{hypothesis.hypothesis_id}"
        metadata["hypothesis_atoms"][hypothesis.hypothesis_id] = hypothesis_atom
        latent.append(
            LatentAtom(
                atom_id=hypothesis_atom,
                kind="hypothesis_support",
                object_id=hypothesis.hypothesis_id,
            )
        )
        factors.append(
            HingeFactor(
                factor_id=f"hypothesis-sparsity:{hypothesis.hypothesis_id}",
                family="sparsity",
                description="A storyline remains weak without typed support.",
                expression=LinearExpression(((hypothesis_atom, 1.0),)),
                weight=policy.sparsity_weight,
                affected_object_ids=(hypothesis.hypothesis_id,),
                direction="oppose",
            )
        )
        for trace_id in hypothesis.trace_ids:
            factors.append(
                HingeFactor(
                    factor_id=f"trace-supports-hypothesis:{trace_id}:{hypothesis.hypothesis_id}",
                    family="storyline",
                    description="A supported trace supports its declared storyline.",
                    expression=LinearExpression(
                        (
                            (f"trace_support:{trace_id}", 0.8),
                            (hypothesis_atom, -1.0),
                        )
                    ),
                    weight=policy.hypothesis_support_weight,
                    affected_object_ids=(hypothesis.hypothesis_id, trace_id),
                    direction="support",
                )
            )
        for link in links_by_hypothesis[hypothesis.hypothesis_id]:
            item = evidence[link.evidence_id]
            quality = evidence_quality(item, sources[item.source_id], policy)
            value = clamp01(quality * link.declared_relevance)
            atom_id = f"hypothesis_link:{link.link_id}"
            observed.append(
                ObservedAtom(
                    atom_id=atom_id,
                    value=value,
                    kind=f"hypothesis_{link.polarity}",
                    object_id=hypothesis.hypothesis_id,
                    evidence_ids=(link.evidence_id,),
                    lineage_ids=(sources[item.source_id].lineage_id,),
                )
            )
            if link.polarity == "support":
                expression = LinearExpression(
                    ((atom_id, 1.0), (hypothesis_atom, -1.0))
                )
                direction = "support"
                weight = policy.hypothesis_support_weight
            else:
                expression = LinearExpression(
                    ((hypothesis_atom, 1.0), (atom_id, 1.0)),
                    constant=-1.0,
                )
                direction = "oppose"
                weight = policy.hypothesis_opposition_weight
            factors.append(
                HingeFactor(
                    factor_id=f"hypothesis-{link.polarity}:{link.link_id}",
                    family="storyline",
                    description=(
                        f"Typed {link.polarity} evidence shapes hypothesis support."
                    ),
                    expression=expression,
                    weight=weight,
                    affected_object_ids=(hypothesis.hypothesis_id,),
                    evidence_ids=(link.evidence_id,),
                    direction=direction,
                )
            )

    for relation in model.hypothesis_relations:
        if relation.relation not in {"alternative", "competes_with"}:
            continue
        left = f"hypothesis_support:{relation.left_hypothesis_id}"
        right = f"hypothesis_support:{relation.right_hypothesis_id}"
        factors.append(
            HingeFactor(
                factor_id=f"alternative-competition:{relation.relation_id}",
                family="storyline_alternative",
                description="Competing storylines cannot both receive unqualified support.",
                expression=LinearExpression(((left, 1.0), (right, 1.0)), constant=-1.0),
                weight=policy.alternative_competition_weight,
                affected_object_ids=(
                    relation.left_hypothesis_id,
                    relation.right_hypothesis_id,
                ),
                evidence_ids=tuple(relation.evidence_ids),
                direction="oppose",
            )
        )

    mechanisms = {item.mechanism_id: item for item in model.causal_mechanisms}
    confounders = {item.confounder_id: item for item in model.confounder_reviews}
    scopes = {item.scope_id: item for item in model.causal_scopes}
    for candidate in model.causal_candidates:
        causal_atom = f"causal_support:{candidate.hypothesis_id}"
        metadata["causal_atoms"][candidate.hypothesis_id] = causal_atom
        latent.append(
            LatentAtom(
                atom_id=causal_atom,
                kind="qualitative_causal_support",
                object_id=candidate.hypothesis_id,
            )
        )
        constraints.append(
            HardConstraint(
                constraint_id=f"causal-bounded-by-hypothesis:{candidate.causal_id}",
                description="Causal support cannot exceed storyline support.",
                expression=LinearExpression(
                    (
                        (causal_atom, 1.0),
                        (f"hypothesis_support:{candidate.hypothesis_id}", -1.0),
                    )
                ),
                upper=0.0,
                affected_object_ids=(candidate.hypothesis_id,),
            )
        )
        factors.append(
            HingeFactor(
                factor_id=f"causal-sparsity:{candidate.causal_id}",
                family="sparsity",
                description="Causal language remains weak without all required factors.",
                expression=LinearExpression(((causal_atom, 1.0),)),
                weight=policy.sparsity_weight,
                affected_object_ids=(candidate.hypothesis_id,),
                direction="oppose",
            )
        )

        mechanism_values: list[float] = []
        mechanism_evidence: list[str] = []
        for mechanism_id in candidate.mechanism_ids:
            mechanism = mechanisms[mechanism_id]
            mechanism_evidence.extend(mechanism.evidence_ids)
            qualities = [
                evidence_quality(evidence[item], sources[evidence[item].source_id], policy)
                for item in mechanism.evidence_ids
            ]
            mechanism_values.append(
                clamp01(
                    (sum(qualities) / len(qualities) if qualities else 0.0)
                    * mechanism.declared_relevance
                )
            )
        mechanism_score = (
            sum(mechanism_values) / len(mechanism_values)
            if mechanism_values
            else 0.0
        )
        mechanism_atom = f"causal_mechanism:{candidate.causal_id}"
        observed.append(
            ObservedAtom(
                atom_id=mechanism_atom,
                value=mechanism_score,
                kind="causal_mechanism",
                object_id=candidate.hypothesis_id,
                evidence_ids=tuple(sorted(set(mechanism_evidence))),
            )
        )
        factors.append(
            HingeFactor(
                factor_id=f"mechanism-supports-causal:{candidate.causal_id}",
                family="qualitative_causal",
                description="Evidence-backed mechanism is required for causal support.",
                expression=LinearExpression(
                    ((mechanism_atom, 1.0), (causal_atom, -1.0))
                ),
                weight=policy.mechanism_weight,
                affected_object_ids=(candidate.hypothesis_id,),
                evidence_ids=tuple(sorted(set(mechanism_evidence))),
                direction="support",
            )
        )

        chronology_score = _chronology_score(
            model,
            candidate.cause_event_ids,
            candidate.effect_event_ids,
        )
        chronology_atom = f"causal_chronology:{candidate.causal_id}"
        observed.append(
            ObservedAtom(
                atom_id=chronology_atom,
                value=chronology_score,
                kind="causal_chronology",
                object_id=candidate.hypothesis_id,
            )
        )
        factors.append(
            HingeFactor(
                factor_id=f"chronology-supports-causal:{candidate.causal_id}",
                family="qualitative_causal",
                description="Declared causes must precede declared effects.",
                expression=LinearExpression(
                    ((chronology_atom, 1.0), (causal_atom, -1.0))
                ),
                weight=policy.chronology_weight,
                affected_object_ids=(candidate.hypothesis_id,),
                direction="support",
            )
        )
        if chronology_score == 0.0:
            constraints.append(
                HardConstraint(
                    constraint_id=f"causal-chronology-gate:{candidate.causal_id}",
                    description="Missing or reversed chronology blocks causal support.",
                    expression=LinearExpression(((causal_atom, 1.0),)),
                    upper=max(0.0, policy.causal_contested_threshold - 0.01),
                    affected_object_ids=(candidate.hypothesis_id,),
                )
            )

        unresolved = [
            confounders[item]
            for item in candidate.confounder_ids
            if confounders[item].status
            in {"unresolved", "partially_addressed"}
        ]
        confounder_score = (
            1.0
            if candidate.confounder_ids and not unresolved
            else (0.45 if candidate.confounder_ids else 0.0)
        )
        confounder_atom = f"confounder_disposition:{candidate.causal_id}"
        observed.append(
            ObservedAtom(
                atom_id=confounder_atom,
                value=confounder_score,
                kind="confounder_disposition",
                object_id=candidate.hypothesis_id,
                evidence_ids=tuple(
                    evidence_id
                    for confounder_id in candidate.confounder_ids
                    for evidence_id in confounders[confounder_id].evidence_ids
                ),
            )
        )
        factors.append(
            HingeFactor(
                factor_id=f"confounders-bound-causal:{candidate.causal_id}",
                family="qualitative_causal",
                description="Addressed confounders support a bounded causal license.",
                expression=LinearExpression(
                    ((confounder_atom, 1.0), (causal_atom, -1.0))
                ),
                weight=policy.confounder_weight,
                affected_object_ids=(candidate.hypothesis_id,),
                direction="support",
            )
        )
        if unresolved or not candidate.confounder_ids:
            constraints.append(
                HardConstraint(
                    constraint_id=f"unresolved-confounder-cap:{candidate.causal_id}",
                    description="Missing or unresolved confounder review blocks supported causal wording.",
                    expression=LinearExpression(((causal_atom, 1.0),)),
                    upper=max(0.0, policy.causal_supported_threshold - 0.01),
                    affected_object_ids=(candidate.hypothesis_id,),
                )
            )

        has_alternative = bool(candidate.alternative_hypothesis_ids)
        scope = scopes.get(candidate.scope_id or "")
        scope_complete = bool(
            scope
            and scope.description
            and (scope.time_window or scope.location_ids or scope.boundary_conditions)
        )
        boundary_atom = f"causal_boundary:{candidate.causal_id}"
        observed.append(
            ObservedAtom(
                atom_id=boundary_atom,
                value=1.0 if has_alternative and scope_complete else 0.0,
                kind="causal_alternative_scope_boundary",
                object_id=candidate.hypothesis_id,
            )
        )
        factors.append(
            HingeFactor(
                factor_id=f"scope-alternative-supports-causal:{candidate.causal_id}",
                family="qualitative_causal",
                description="Alternative comparison and explicit scope bound causal wording.",
                expression=LinearExpression(
                    ((boundary_atom, 1.0), (causal_atom, -1.0))
                ),
                weight=policy.causal_scope_weight,
                affected_object_ids=(candidate.hypothesis_id,),
                direction="support",
            )
        )
        if not has_alternative or not scope_complete:
            constraints.append(
                HardConstraint(
                    constraint_id=f"causal-boundary-cap:{candidate.causal_id}",
                    description="Absent alternative comparison or scope blocks supported causal wording.",
                    expression=LinearExpression(((causal_atom, 1.0),)),
                    upper=max(0.0, policy.causal_supported_threshold - 0.01),
                    affected_object_ids=(candidate.hypothesis_id,),
                )
            )

    return {
        "observed_atoms": observed,
        "latent_atoms": latent,
        "factors": factors,
        "hard_constraints": constraints,
        "diagnostics": [],
        "gaps": [],
        "contradictions": [],
        "metadata": metadata,
    }
