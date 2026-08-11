---
name: researchguard
description: Route a genuinely ambiguous or cross-member research request to the minimum sufficient current ResearchGuard member set from source-bound task facts. Use direct LogicGuard, SourceGuard, TraceGuard, or ExperimentGuard entry when one native owner is already clear.
---

# ResearchGuard

## Purpose

ResearchGuard routes across four independent native members—`logicguard`,
`sourceguard`, `traceguard`, and `experimentguard`—without duplicate work or
silent retries.

## Entrypoint Scope

Use a member directly when its first action is clear. Use the umbrella only for
an ambiguous first action or several domains. Read
`references/member-admission-index.md` at `route:member-admission`; do not load
member skills to classify.

Extract source-spanned `primary_action` and context facts only. Contracts derive
admission and the router selects the unique smallest set covering each primary
responsibility.

## Use When

Use the umbrella for an ambiguous first action or several member
responsibilities.

## Do Not Use When

Use a direct member route when one native owner is clear; never use the umbrella
as a retry or broad scan.

## Required Workflow

Run the suite console:

```powershell
researchguard run --business-intent-id <intent-id> --task-facts <task-facts.json> -- <member arguments>
```

One sufficient member is the whole route. Otherwise declare
`researchguard.member-composition.v2` with exact members, order, dependencies,
responsibilities, typed handoffs, field owners, and one claim boundary. Emit
only `composition_ready` or visible `composition_blocked`.

For composed blueprints, handoffs, impact, or reverse trace, trigger
`route:member-model-envelope` and read
`references/member-model-envelope.md`. This is transport between
member-domain DNA, not repository software DNA; the sole ResearchGuard
ResearchGuard repository software-DNA root is FlowGuard-owned. Load no member blueprint
unless invoked.

For portable DNA of an external paper, model, test system, or workflow, trigger
`route:external-domain-dna` and read
`references/external-domain-dna.md`. It owns signed scope,
current replay, coverage, qualification, exclusions, and recursive frontier.

External admission fixes the target and denominator before member parsing. Replay
the persistent anchor and immutable-receipt hashes; cache is not authority. A
different target needs a separate anchor; there is no generic issuer or inline
candidate-authoring path.

There are two DNA layers: member-domain DNA for an external paper, model, test
system, or workflow, and the separate ResearchGuard repository software-DNA
root owned by FlowGuard. Member output is not software-DNA evidence until it is
bound to exact current code and test owners. External qualification is target
neutral and adapter-selected; self-DNA exposes static, semantic, code-binding,
and test-binding states, with stale FlowGuard qualification shown as a blocker.

Missing spans, stale fingerprints, unknown facts, incomplete forbidden reviews,
zero coverage, equal minima, over-selection, or incomplete composition block
before execution. No keyword, list-order, alias, `run all`, retry, or fallback.

## Member boundary

- LogicGuard owns argument structure, source-library work, structured artifacts, model deepening, synthesis, and its project-library viewer.
- SourceGuard owns evidence discovery, retrieval, provenance, source-role gaps, and claim-use qualification.
- TraceGuard owns temporal reconstruction, competing storylines, execution/effect chains, counter-scenarios, and bounded causal narratives.
- ExperimentGuard owns recommendation-only minimum finite experiment sets over declared hypotheses and outcomes.

Context alone does not create another responsibility. A source-bound primary responsibility does. Necessary multi-member work uses the declared composition and typed handoffs; a handoff never executes the target member automatically.

## Selected-member depth

The selected member—not the umbrella—owns predictions, falsifiers, native observations, gap lineage, revision, holdout evidence, and closure. Claiming the model "understands" is not evidence. Native gaps stay open or end visibly as stalled, limited, externally dependent, or scope-excluded.

## Hard Gates

- one exact member owns each native execution, while the umbrella may coordinate only the minimum sufficient set;
- direct and umbrella entry bind the same native owner and primary path;
- all four derived rows bind the same request and current contracts;
- every forbidden condition has an exact disposition;
- responsibilities and handed fields have exactly one owner;
- recursion, ambiguity, over-selection, unknown inputs, invalid composition, and member failure remain visible;
- no member result is upgraded by another member.

## Output Requirements

Report the selected set, order, responsibilities, evidence, failures, blockers,
skips, loaded references, residual risk, typed handoffs, field owners, terminal
reason, and claim boundary.
