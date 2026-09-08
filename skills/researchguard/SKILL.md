---
name: researchguard
description: Route a genuinely ambiguous or cross-member research request to the minimum sufficient current ResearchGuard member set from source-bound task facts. Use direct LogicGuard, SourceGuard, TraceGuard, or ExperimentGuard entry when one native owner is already clear.
---

# ResearchGuard

## Purpose

ResearchGuard routes ambiguity across four native members—`logicguard`,
`sourceguard`, `traceguard`, and `experimentguard`—without duplicate work or
retries.

## Entrypoint Scope

Use a member directly when its action is clear. Use the umbrella only for
ambiguity or several domains. Read
`references/member-admission-index.md` at `route:member-admission`; do not load
member skills to classify.

Extract `primary_action` and context facts only. Contracts derive admission;
the router selects the unique smallest set covering each responsibility.

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
`references/member-model-envelope.md`. This transports member-domain DNA, not
repository software DNA; the ResearchGuard software-DNA root is FlowGuard-owned.
Load no member blueprint
unless invoked.

For directory-native DNA of an external paper, model, test system, or workflow, trigger
`route:external-domain-dna` and read
`references/external-domain-dna.md`. It owns signed scope,
current replay, coverage, qualification, exclusions, and recursive frontier.

External admission fixes the target and denominator before member parsing. Replay
the persistent anchor and immutable-receipt hashes; cache is not authority. A
different target needs a separate anchor; there is no generic issuer or inline
candidate-authoring path.

Member-domain DNA is conditional. The separate ResearchGuard repository software-DNA root is FlowGuard-owned; only exact current code and test-owner
bindings can qualify member output. The target's native directory remains the
DNA authority, and a composition is only an in-memory working projection.

Missing spans, stale fingerprints, unknown facts, incomplete forbidden reviews,
zero coverage, equal minima, over-selection, or incomplete composition block
execution. No keyword, list-order, alias, `run all`, retry, or fallback.

## Member boundary

- LogicGuard owns argument structure, source-library work, structured artifacts, model deepening, synthesis, and its project-library viewer.
- SourceGuard owns evidence discovery, retrieval, provenance, source-role gaps, and claim-use qualification.
- TraceGuard owns temporal reconstruction, competing storylines, execution/effect chains, counter-scenarios, and bounded causal narratives.
- ExperimentGuard owns recommendation-only minimum finite experiment sets over declared hypotheses and outcomes.

Context alone creates no responsibility; a source-bound primary responsibility does. Multi-member work uses the declared composition and typed handoffs; a handoff never executes a member automatically.

## Selected-member depth

The selected member—not the umbrella—owns predictions, falsifiers, observations,
gap lineage, revision, holdouts, and closure. “Understands” is not evidence;
native gaps stay open or end visibly as stalled, limited, external, or excluded.

## Hard Gates

- one exact member owns each native execution, while the umbrella may coordinate only the minimum sufficient set;
- direct and umbrella entry bind the same native owner and primary path;
- all four derived rows bind the same request and current contracts;
- every forbidden condition has an exact disposition;
- responsibilities and handed fields have exactly one owner;
- recursion, ambiguity, over-selection, unknown inputs, invalid composition, and member failure remain visible;
- no member result is upgraded by another member.

## Output Requirements

Report the selected set/order, responsibilities, evidence, failures, blockers,
skips, references, risk, typed handoffs, field owners, terminal reason, and claim boundary.
