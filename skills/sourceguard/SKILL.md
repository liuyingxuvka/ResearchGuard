---
name: sourceguard
description: Plan and execute evidence/source discovery for a claim with explicit source roles, retrieval evidence, provenance, gaps, and bounded claim-use decisions. It does not license arguments or reconstruct storylines.
---

# SourceGuard

## Purpose

SourceGuard owns one current evidence-discovery and source-qualification route. First declare the target claim, desired strength, source roles, and current gaps; then build or inspect the current source model before choosing a search action.

Read `references/source-model-protocol.md` under `route:source-model` for every admitted SourceGuard task.

## Entrypoint Scope

SourceGuard owns source-role planning, evidence discovery, retrieval, provenance, lineage, semantic fit, counter or limiting search, and bounded claim-use qualification. It decides whether a source observation can support the declared claim use; argument licensing and temporal or causal reconstruction remain typed handoffs.

## Local Material Routing

Read `references/source-model-protocol.md` before every admitted task, then read only the reference declared by each active route or trigger. Keep provider observations, source candidates, and immutable evidence references separate inside the SourceGuard material boundary.

## Entrypoint Acceptance Map

- Accept the entrypoint only after the target claim, desired strength, source roles, and current gaps are frozen.
- Accept a retrieval or qualification action only after its route reference and source or provider boundary are declared.
- Accept iteration, depth, command, or safe-output work only after its conditional reference is loaded.
- If a source anchor, source role, or critical gap is missing, keep the result visibly unresolved rather than promoting a candidate.

## Conditional depth map

- `trigger:retrieval-workflow`: plan or execute retrieval, qualify provider observations, update semantic state, or export a handoff → read `references/retrieval-workflow.md`.
- `trigger:task-iteration`: a real observation will test a predicted search action, a model miss appears, or an addressable gap remains → read `references/task-iteration.md`.
- `trigger:broad-depth-closure`: broad, complete, deep, final, high-impact, or gap-closure wording → read `references/broad-depth-and-closure.md`.
- `trigger:commands`: actual CLI construction or execution → read `references/commands.md`.
- `trigger:safe-output`: reader-facing qualification, downgrade, access-gap, or handoff wording → read `references/safe-output.md`.

The small first read is not a weak mode. When a deep trigger fires, continue the existing native search-model loop until all covered native gaps close or a visible terminal stops it.

## Use When

Use SourceGuard for source-role planning, evidence discovery, retrieval, provenance, lineage, counter/limiting search, semantic fit, key-number provenance, bridge evidence, and claim-use qualification.

## Do Not Use When

Do not use SourceGuard to assert factual truth, promote a search result or candidate into evidence, reconstruct a trace, license a final argument, fake external search/OCR/multimodal analysis, or silently invoke another Guard.

## Required Workflow

1. Freeze the target claim, desired strength, source roles, target artifact, and current gap universe.
2. Read the source-model protocol and the references selected by active route and triggers.
3. Plan or execute bounded retrieval, record provider observations, and qualify candidates without treating search results as evidence.
4. Cite each source by the anchor id and locator the tool reports (`source depth` computes evidence references itself); record direct, independent, counter, lineage, and content-bearing coverage where required.
5. Iterate through the native search-model loop until `model_closed_for_task` or a visible terminal such as `provider_access_required`, `finite_action_exhausted`, or `progress_stalled`.
6. Return safe claim use, unresolved gaps, typed handoffs, and the complete claim boundary.

## Hard Gates

- A search result, source candidate, locator, utility score, or aggregate is never individual evidence by itself.
- Missing, stale, inaccessible, skipped, or provider-unavailable work remains visible.
- Broad closure requires current depth results, the complete target-unit and gap universe, per-gap direct/independent/counter coverage, lineage, content-bearing anchors, and no unresolved critical native gap.
- SourceGuard cannot invent external retrieval, OCR, multimodal analysis, or truth probability.

## Native closure

Search result is not evidence; source candidate is not evidence; locator is not semantic support; utility is not truth probability. Broad closure requires the current depth result, the complete target-unit/gap universe, per-gap direct/independent/counter coverage, lineage and content-bearing anchors, and no unresolved critical native gap. Planning-only, provider-unavailable, bounded, stale, skipped, or inaccessible work remains visible.

Task-local closure is only `model_closed_for_task`. Other current terminals include `continue_iteration`, `progress_stalled`, `iteration_limit`, `external_input_required`, `provider_access_required`, and `finite_action_exhausted`. AI cannot close by reporting that it understands the source problem.

## Output Requirements

Return the native result, evidence and claim boundary, blockers and next action.
Include full JSON only when it is needed or requested.
