from __future__ import annotations

from typing import Any, Iterable

from researchguard.admission import COMPOSITION_SCHEMA, TASK_FACTS_SCHEMA
from researchguard.routing import MEMBER_ADMISSION_CONTRACTS, request_fingerprint


MEMBER_PRIMARY_FACTS = {
    "logicguard": ("logic.argument_structure", ()),
    "sourceguard": ("source.primary_discovery", ()),
    "traceguard": ("trace.temporal_reconstruction", ()),
    "experimentguard": (
        "experiment.discriminating_set",
        (
            "experiment.explicit_hypotheses",
            "experiment.finite_candidates",
            "experiment.predicted_outcomes",
        ),
    ),
}


def _span(source_id: str, quote: str) -> dict[str, Any]:
    return {"source_id": source_id, "start": 0, "end": len(quote), "quote": quote}


def task_facts(
    *,
    argv: list[str] | tuple[str, ...],
    intent: str,
    primary_kind: str,
    additional_primary_kinds: Iterable[str] = (),
    context_kinds: Iterable[str] = (),
    composition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    primary_kinds = (primary_kind, *tuple(additional_primary_kinds))
    kinds = (*primary_kinds, *tuple(context_kinds))
    facts = []
    for index, kind in enumerate(kinds):
        quote = f"request fact {index}: {kind}"
        facts.append(
            {
                "fact_id": f"fact:{index}",
                "kind": kind,
                "role": "primary_action" if index < len(primary_kinds) else "context",
                "statement": quote,
                "source_span": _span(f"request:user:{index}", quote),
            }
        )
    all_kinds = set(kinds)
    primary_quote = str(facts[0]["source_span"]["quote"])
    reviews = []
    for member, contract in MEMBER_ADMISSION_CONTRACTS.items():
        for condition in contract["forbidden_conditions"]:
            present = bool(all_kinds.intersection(condition["any_fact_kinds"]))
            reviews.append(
                {
                    "member_id": member,
                    "condition_id": condition["condition_id"],
                    "disposition": "present" if present else "absent",
                    "source_span": _span("request:user:review", primary_quote),
                }
            )
    payload = {
        "schema_version": TASK_FACTS_SCHEMA,
        "request_fingerprint": request_fingerprint(argv, business_intent_id=intent),
        "facts": facts,
        "forbidden_reviews": reviews,
    }
    if composition is not None:
        payload["composition"] = composition
    return payload


def composition(
    *member_responsibilities: tuple[str, tuple[str, ...]],
) -> dict[str, Any]:
    steps = []
    handoffs = []
    owners = []
    for index, (member, responsibilities) in enumerate(member_responsibilities, start=1):
        step_id = f"step:{index}:{member}"
        input_ids: list[str] = []
        output_ids: list[str] = []
        dependencies: list[str] = []
        if index > 1:
            previous_member = member_responsibilities[index - 2][0]
            previous_step = f"step:{index - 1}:{previous_member}"
            handoff_id = f"handoff:{index - 1}:{index}"
            field_id = f"field:{index - 1}:{index}:artifact"
            dependencies.append(previous_step)
            input_ids.append(handoff_id)
            handoffs.append(
                {
                    "handoff_id": handoff_id,
                    "from_step_id": previous_step,
                    "to_step_id": step_id,
                    "field_ids": [field_id],
                }
            )
            owners.append({"field_id": field_id, "owner_step_id": previous_step})
            steps[-1]["output_handoff_ids"].append(handoff_id)
        steps.append(
            {
                "step_id": step_id,
                "order": index,
                "member_id": member,
                "responsibility_condition_ids": list(responsibilities),
                "depends_on_step_ids": dependencies,
                "input_handoff_ids": input_ids,
                "output_handoff_ids": output_ids,
            }
        )
    return {
        "schema_version": COMPOSITION_SCHEMA,
        "steps": steps,
        "handoffs": handoffs,
        "field_owners": owners,
        "overall_claim_boundary": "Each member owns only its declared responsibility; the umbrella proves planning, not native completion.",
    }


def member_task_facts(
    member: str,
    *,
    argv: list[str] | tuple[str, ...],
    intent: str,
) -> dict[str, Any]:
    primary, context = MEMBER_PRIMARY_FACTS[member]
    return task_facts(
        argv=argv,
        intent=intent,
        primary_kind=primary,
        context_kinds=context,
    )
