---
name: researchguard
description: Route a genuinely ambiguous or cross-member research request to the minimum sufficient current ResearchGuard member set from source-bound task facts. Use direct LogicGuard, SourceGuard, TraceGuard, or ExperimentGuard entry when one native owner is already clear.
---

# ResearchGuard

## Purpose

ResearchGuard owns suite-level classification and explicit handoff for four complete members: `logicguard`, `sourceguard`, `traceguard`, and `experimentguard`. It never duplicates member work or silently tries another member.

## Narrow entry

Use a member directly when the first action is clear. Direct entry bypasses this umbrella and reaches the same native owner.

Use the umbrella only when the first action is genuinely ambiguous or the request mentions several member domains. Read `references/member-admission-index.md` under trigger `route:member-admission` before classification. Do not load the four member skills to decide the route.

AI extracts one or more `primary_action` responsibility facts and optional context facts. Every fact has a stable id, current fact kind, statement, role, and exact request source span. AI does not set `applicable` or choose members. Each member's current contract derives its own positive, required, forbidden, first-action, and first-reference result. The router then selects the unique smallest set covering every primary responsibility.

Run:

```powershell
researchguard run --business-intent-id <intent-id> --task-facts <task-facts.json> -- <member arguments>
```

If one member covers the whole request, use only that member; a larger composition is over-selection. If several irreducible responsibilities require several members, include one `researchguard.member-composition.v1` object declaring the exact member set, contiguous order, earlier-step dependencies, per-member condition responsibilities, input/output handoffs, one producing owner for every handed field, and an overall claim boundary. The umbrella emits `composition_ready`; it does not guess member arguments or claim that native work ran.

Missing or placeholder spans, stale fingerprints, unknown fact kinds, incomplete forbidden reviews, zero coverage, equal-minimum ambiguity, over-selection, or an incomplete composition block before member execution. There is no keyword, list-order, alias, `run all`, retry, or compatibility fallback.

## Member boundary

- LogicGuard owns argument structure, source-library work, structured artifacts, model deepening, synthesis, and its project-library viewer.
- SourceGuard owns evidence discovery, retrieval, provenance, source-role gaps, and claim-use qualification.
- TraceGuard owns temporal reconstruction, competing storylines, execution/effect chains, counter-scenarios, and bounded causal narratives.
- ExperimentGuard owns recommendation-only minimum finite experiment sets over declared hypotheses and outcomes.

Context alone does not create another responsibility. A source-bound primary responsibility does. Necessary multi-member work uses the declared composition and typed handoffs; a handoff never executes the target member automatically.

## Selected-member depth

The selected member—not the umbrella—owns task-local predictions, falsifiers, native observations, gap lineage, revision, holdout evidence, and closure. A statement that the model "understands" is never evidence. Open native gaps remain open or end visibly as stalled, limited, externally dependent, or scope-excluded.

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
