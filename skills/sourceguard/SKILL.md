---
name: sourceguard
description: Plan and execute evidence/source discovery for a claim with explicit source roles, retrieval evidence, provenance, gaps, and bounded claim-use decisions. It does not license arguments or reconstruct storylines.
---

# SourceGuard

## Purpose and first action

SourceGuard owns one current evidence-discovery and source-qualification route. First declare the target claim, desired strength, source roles, and current gaps; then build or inspect the current source model before choosing a search action.

Read `references/source-model-protocol.md` under `route:source-model` for every admitted SourceGuard task.

## Conditional depth map

- `trigger:retrieval-workflow`: plan or execute retrieval, qualify provider observations, update semantic state, or export a handoff → read `references/retrieval-workflow.md`.
- `trigger:task-iteration`: a real observation will test a predicted search action, a model miss appears, or an addressable gap remains → read `references/task-iteration.md`.
- `trigger:broad-depth-closure`: broad, complete, deep, final, high-impact, or gap-closure wording → read `references/broad-depth-and-closure.md`.
- `trigger:commands`: actual CLI construction or execution → read `references/commands.md`.
- `trigger:safe-output`: reader-facing qualification, downgrade, access-gap, or handoff wording → read `references/safe-output.md`.
- `trigger:template-pack`: template selection, preview, construction, validation, or harvest → read `references/validated-template-pack.md`.

The small first read is not a weak mode. When a deep trigger fires, continue the existing native search-model loop until all covered native gaps close or a visible terminal stops it.

## Use and non-use boundary

Use for source-role planning, evidence discovery, retrieval, provenance, lineage, counter/limiting search, semantic fit, key-number provenance, bridge evidence, and claim-use qualification. Do not assert factual truth, promote a search result or candidate into evidence, reconstruct a trace, license a final argument, fake external search/OCR/multimodal analysis, or silently invoke another Guard.

## Native closure

Search result is not evidence; source candidate is not evidence; locator is not semantic support; utility is not truth probability. An aggregate or neighboring receipt is not proof of an individual SourceGuard obligation. Each obligation needs its exact `evidence_ref`, bound to the current artifact with a lowercase content hash. Broad closure requires the current SourceGuard-owned purpose proof, depth receipt, complete target-unit/gap universe, per-gap direct/independent/counter coverage, lineage and content-bearing anchors, and no unresolved critical native gap. Planning-only, provider-unavailable, bounded, stale, skipped, or inaccessible work remains visible.

Task-local closure is only `model_closed_for_task`. Other current terminals include `continue_iteration`, `progress_stalled`, `iteration_limit`, `external_input_required`, `provider_access_required`, and `finite_action_exhausted`. AI cannot close by reporting that it understands the source problem.

## Output

Return source roles, selected action, loaded references and triggers, evidence, failures, blockers, skipped checks, unresolved gaps, search-stop decision, residual risk, safe claim use, typed handoffs, terminal reason, and claim boundary.
