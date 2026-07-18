"""TraceGuard schema reference validation.

Purpose: Validate local references between sources, evidence, events, traces, entities, and locations.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: TraceGuard
Math boundary: Reference checks are hard structural gates, not probabilistic inference.
CLI: researchguard trace validate <model.yaml>
Boundary: Valid references do not prove the trace is true.
"""

from __future__ import annotations

from .schema import SchemaError, TraceGuardModel


def validate_references(model: TraceGuardModel) -> None:
    source_ids = set(model.source_by_id())
    evidence_ids = set(model.evidence_by_id())
    event_ids = set(model.event_by_id())
    entity_ids = set(model.entity_by_id())
    location_ids = set(model.location_by_id())
    trace_ids = {trace.trace_id for trace in model.traces}
    hypothesis_ids = {
        hypothesis.hypothesis_id for hypothesis in model.storyline_hypotheses
    }
    mechanism_ids = {
        mechanism.mechanism_id for mechanism in model.causal_mechanisms
    }
    confounder_ids = {
        confounder.confounder_id for confounder in model.confounder_reviews
    }
    ablation_ids = {item.ablation_id for item in model.evidence_ablations}
    scenario_ids = {
        item.perturbation_id for item in model.scenario_perturbations
    }
    perturbation_ids = ablation_ids | scenario_ids
    scope_ids = {item.scope_id for item in model.causal_scopes}

    for evidence in model.evidence:
        if evidence.source_id not in source_ids:
            raise SchemaError(f"evidence {evidence.evidence_id} references missing source {evidence.source_id}")

    for entity in model.entities:
        if entity.evidence_id and entity.evidence_id not in evidence_ids:
            raise SchemaError(f"entity {entity.mention_id} references missing evidence {entity.evidence_id}")

    for resolution in model.entity_resolutions:
        if resolution.left_id not in entity_ids:
            raise SchemaError(f"entity resolution references missing left entity {resolution.left_id}")
        if resolution.right_id not in entity_ids:
            raise SchemaError(f"entity resolution references missing right entity {resolution.right_id}")

    for event in model.events:
        for evidence_id in event.evidence_ids:
            if evidence_id not in evidence_ids:
                raise SchemaError(f"event {event.event_id} references missing evidence {evidence_id}")
        for entity_id in event.actor_ids + event.object_ids + event.technology_ids:
            if entity_id not in entity_ids:
                raise SchemaError(f"event {event.event_id} references missing entity {entity_id}")
        for location_id in event.location_ids:
            if location_id not in location_ids:
                raise SchemaError(f"event {event.event_id} references missing location {location_id}")

    for trace in model.traces:
        for event_id in trace.event_ids:
            if event_id not in event_ids:
                raise SchemaError(f"trace {trace.trace_id} references missing event {event_id}")
        for entity_id in trace.entity_ids:
            if entity_id not in entity_ids:
                raise SchemaError(f"trace {trace.trace_id} references missing entity {entity_id}")
        for location_id in trace.location_ids:
            if location_id not in location_ids:
                raise SchemaError(f"trace {trace.trace_id} references missing location {location_id}")

    for hypothesis in model.storyline_hypotheses:
        for trace_id in hypothesis.trace_ids:
            if trace_id not in trace_ids:
                raise SchemaError(
                    f"hypothesis {hypothesis.hypothesis_id} references missing trace {trace_id}"
                )
        for event_id in hypothesis.event_ids:
            if event_id not in event_ids:
                raise SchemaError(
                    f"hypothesis {hypothesis.hypothesis_id} references missing event {event_id}"
                )
        for evidence_id in hypothesis.evidence_ids + hypothesis.contradicting_evidence_ids:
            if evidence_id not in evidence_ids:
                raise SchemaError(
                    f"hypothesis {hypothesis.hypothesis_id} references missing evidence {evidence_id}"
                )
        for alternative_id in hypothesis.alternative_to:
            if alternative_id not in hypothesis_ids:
                raise SchemaError(
                    f"hypothesis {hypothesis.hypothesis_id} references missing alternative {alternative_id}"
                )
        for mechanism_id in hypothesis.mechanism_ids:
            if mechanism_id not in mechanism_ids:
                raise SchemaError(
                    f"hypothesis {hypothesis.hypothesis_id} references missing mechanism {mechanism_id}"
                )
        for confounder_id in hypothesis.confounder_ids:
            if confounder_id not in confounder_ids:
                raise SchemaError(
                    f"hypothesis {hypothesis.hypothesis_id} references missing confounder {confounder_id}"
                )

    for link in model.hypothesis_evidence_links:
        if link.hypothesis_id not in hypothesis_ids:
            raise SchemaError(
                f"hypothesis evidence link {link.link_id} references missing "
                f"hypothesis {link.hypothesis_id}"
            )
        if link.evidence_id not in evidence_ids:
            raise SchemaError(
                f"hypothesis evidence link {link.link_id} references missing "
                f"evidence {link.evidence_id}"
            )

    for relation in model.hypothesis_relations:
        if relation.left_hypothesis_id not in hypothesis_ids:
            raise SchemaError(
                f"hypothesis relation {relation.relation_id} references missing "
                f"left hypothesis {relation.left_hypothesis_id}"
            )
        if relation.right_hypothesis_id not in hypothesis_ids:
            raise SchemaError(
                f"hypothesis relation {relation.relation_id} references missing "
                f"right hypothesis {relation.right_hypothesis_id}"
            )
        for evidence_id in relation.evidence_ids:
            if evidence_id not in evidence_ids:
                raise SchemaError(
                    f"hypothesis relation {relation.relation_id} references "
                    f"missing evidence {evidence_id}"
                )

    for mechanism in model.causal_mechanisms:
        if mechanism.hypothesis_id not in hypothesis_ids:
            raise SchemaError(
                f"mechanism {mechanism.mechanism_id} references missing hypothesis {mechanism.hypothesis_id}"
            )
        for evidence_id in mechanism.evidence_ids:
            if evidence_id not in evidence_ids:
                raise SchemaError(
                    f"mechanism {mechanism.mechanism_id} references missing evidence {evidence_id}"
                )

    for confounder in model.confounder_reviews:
        if confounder.hypothesis_id not in hypothesis_ids:
            raise SchemaError(
                f"confounder {confounder.confounder_id} references missing hypothesis {confounder.hypothesis_id}"
            )
        for evidence_id in confounder.evidence_ids:
            if evidence_id not in evidence_ids:
                raise SchemaError(
                    f"confounder {confounder.confounder_id} references missing evidence {evidence_id}"
                )

    for candidate in model.causal_candidates:
        if candidate.hypothesis_id not in hypothesis_ids:
            raise SchemaError(
                f"causal candidate {candidate.causal_id} references missing "
                f"hypothesis {candidate.hypothesis_id}"
            )
        for event_id in candidate.cause_event_ids + candidate.effect_event_ids:
            if event_id not in event_ids:
                raise SchemaError(
                    f"causal candidate {candidate.causal_id} references "
                    f"missing event {event_id}"
                )
        for mechanism_id in candidate.mechanism_ids:
            if mechanism_id not in mechanism_ids:
                raise SchemaError(
                    f"causal candidate {candidate.causal_id} references "
                    f"missing mechanism {mechanism_id}"
                )
        for confounder_id in candidate.confounder_ids:
            if confounder_id not in confounder_ids:
                raise SchemaError(
                    f"causal candidate {candidate.causal_id} references "
                    f"missing confounder {confounder_id}"
                )
        for alternative_id in candidate.alternative_hypothesis_ids:
            if alternative_id not in hypothesis_ids:
                raise SchemaError(
                    f"causal candidate {candidate.causal_id} references "
                    f"missing alternative {alternative_id}"
                )
        if candidate.scope_id and candidate.scope_id not in scope_ids:
            raise SchemaError(
                f"causal candidate {candidate.causal_id} references missing "
                f"scope {candidate.scope_id}"
            )

    for ablation in model.evidence_ablations:
        if ablation.hypothesis_id and ablation.hypothesis_id not in hypothesis_ids:
            raise SchemaError(
                f"ablation {ablation.ablation_id} references missing hypothesis "
                f"{ablation.hypothesis_id}"
            )
        if ablation.trace_id and ablation.trace_id not in trace_ids:
            raise SchemaError(
                f"ablation {ablation.ablation_id} references missing trace "
                f"{ablation.trace_id}"
            )
        for evidence_id in ablation.remove_evidence_ids:
            if evidence_id not in evidence_ids:
                raise SchemaError(
                    f"ablation {ablation.ablation_id} references missing "
                    f"evidence {evidence_id}"
                )
        for event_id in ablation.remove_event_ids:
            if event_id not in event_ids:
                raise SchemaError(
                    f"ablation {ablation.ablation_id} references missing event "
                    f"{event_id}"
                )

    for scenario in model.scenario_perturbations:
        if scenario.hypothesis_id and scenario.hypothesis_id not in hypothesis_ids:
            raise SchemaError(
                f"scenario {scenario.perturbation_id} references missing "
                f"hypothesis {scenario.hypothesis_id}"
            )
        if scenario.trace_id and scenario.trace_id not in trace_ids:
            raise SchemaError(
                f"scenario {scenario.perturbation_id} references missing trace "
                f"{scenario.trace_id}"
            )
        for evidence_id in (
            scenario.remove_evidence_ids + scenario.add_evidence_ids
        ):
            if evidence_id not in evidence_ids:
                raise SchemaError(
                    f"scenario {scenario.perturbation_id} references missing "
                    f"evidence {evidence_id}"
                )
        for event_id in scenario.remove_event_ids + scenario.add_event_ids:
            if event_id not in event_ids:
                raise SchemaError(
                    f"scenario {scenario.perturbation_id} references missing "
                    f"event {event_id}"
                )

    for sensitivity in model.expected_sensitivities:
        if sensitivity.perturbation_id not in perturbation_ids:
            raise SchemaError(
                f"expected sensitivity {sensitivity.sensitivity_id} references "
                f"missing perturbation {sensitivity.perturbation_id}"
            )
        if (
            sensitivity.target_kind == "hypothesis"
            and sensitivity.target_id not in hypothesis_ids
        ):
            raise SchemaError(
                f"expected sensitivity {sensitivity.sensitivity_id} references "
                f"missing hypothesis {sensitivity.target_id}"
            )
        if (
            sensitivity.target_kind == "trace"
            and sensitivity.target_id not in trace_ids
        ):
            raise SchemaError(
                f"expected sensitivity {sensitivity.sensitivity_id} references "
                f"missing trace {sensitivity.target_id}"
            )
