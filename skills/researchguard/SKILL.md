---
name: researchguard
description: Route a genuinely ambiguous or cross-member research request to the minimum sufficient current ResearchGuard member set from source-bound task facts. Use direct LogicGuard, SourceGuard, TraceGuard, or ExperimentGuard entry when one native owner is already clear.
---

# ResearchGuard

## Purpose

ResearchGuard classifies and hands off across four independent native members: `logicguard`, `sourceguard`, `traceguard`, and `experimentguard`. It never duplicates work or silently tries another member.

## Narrow entry

Use a member directly when the first action is clear.

Use the umbrella only for an ambiguous first action or several member domains. Read `references/member-admission-index.md` under trigger `route:member-admission` before classification. Do not load the four member skills to decide the route.

Extract source-spanned `primary_action` facts and optional context facts; do not set `applicable` or choose members. Current member contracts derive admission, and the router selects the unique smallest set covering every primary responsibility.

Run:

```powershell
researchguard run --business-intent-id <intent-id> --task-facts <task-facts.json> -- <member arguments>
```

One sufficient member is the whole route. Otherwise declare `researchguard.member-composition.v2` with exact members, order, dependencies, responsibilities, typed handoffs, field owners, and claim boundary. The umbrella emits only `composition_ready` or visible `composition_blocked`.

For composed member blueprints, handoffs, affected impact, or reverse trace, trigger `route:member-model-envelope` and read `references/member-model-envelope.md`. This is transport between member-domain DNA, not repository software DNA; the sole ResearchGuard repository software-DNA root is FlowGuard-owned. Load no member blueprint unless that member is invoked.

For portable DNA of an external paper, model, test system, or workflow, trigger `route:external-domain-dna` and read `references/external-domain-dna.md`. It owns signed scope, current native replay, coverage, qualification, exclusions, and recursive frontier.

External admission fixes the target and denominator before member-native parsing. Replay persistent anchor and immutable-receipt hashes; cache is not authority. Direct use is unverified, and a different target needs a separate anchor. There is no generic issuer or inline candidate-authoring path.

Missing or placeholder spans, stale fingerprints, unknown fact kinds, incomplete forbidden reviews, zero coverage, equal-minimum ambiguity, over-selection, or an incomplete composition block before member execution. There is no keyword, list-order, alias, `run all`, retry, or compatibility fallback.

## Member boundary

- LogicGuard owns argument structure, source-library work, structured artifacts, model deepening, synthesis, and its project-library viewer.
- SourceGuard owns evidence discovery, retrieval, provenance, source-role gaps, and claim-use qualification.
- TraceGuard owns temporal reconstruction, competing storylines, execution/effect chains, counter-scenarios, and bounded causal narratives.
- ExperimentGuard owns recommendation-only minimum finite experiment sets over declared hypotheses and outcomes.

Context alone does not create another responsibility. A source-bound primary responsibility does. Necessary multi-member work uses the declared composition and typed handoffs; a handoff never executes the target member automatically.

## Selected-member depth

The selected member—not the umbrella—owns predictions, falsifiers, native observations, gap lineage, revision, holdout evidence, and closure. Claiming the model "understands" is not evidence. Native gaps stay open or end visibly as stalled, limited, externally dependent, or scope-excluded.

## Hard gates

- one exact member owns each native execution, while the umbrella may coordinate only the minimum sufficient set;
- direct and umbrella entry bind the same native owner and primary path;
- all four derived rows bind the same request and current contracts;
- every forbidden condition has an exact disposition;
- responsibilities and handed fields have exactly one owner;
- recursion, ambiguity, over-selection, unknown inputs, invalid composition, and member failure remain visible;
- no member result is upgraded by another member.

## Output

Report the selected member or minimum sufficient set, declared order and responsibilities, evidence, failures, blockers, skipped checks, loaded references, residual risk, typed handoffs, field owners, terminal reason, and claim boundary.
