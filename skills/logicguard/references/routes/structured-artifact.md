# Internal LogicGuard route: structured-artifact

This is an internal LogicGuard route for decks, papers, reports, and other artifacts whose structure matters. Use it when the user's question is about how sections, slides, pages, paragraphs, or blocks support the overall reasoning.

Use the LogicGuard CLI entrypoint:

```powershell
researchguard logic <args>
```

## Workflow

1. Identify natural boundaries before judging the writing: `Document -> Section -> ArgumentBlock -> local nodes`.
2. For non-trivial artifacts, build a model-card inventory before judging quality. Use cards for document, section, subsection, paragraph block, slide/page, figure/table reference block, conclusion block, transition block, and local argument units when relevant.
   For theses and dissertations, include chapter, section, subsection,
   paragraph block, heading, figure/table reference, validation block,
   limitation block, and conclusion block coverage before claiming the
   structure has been reviewed.
3. Reuse LogicGuard node types and add artifact metadata such as `artifact_kind`, `locator`, `order_index`, `role`, `importance`, `salience`, `source_date`, and `coverage_period` when useful.
4. Build or inspect a structural contribution graph before judging the whole artifact. Start with the smallest useful contribution note for each important unit: unit role, parent support, downstream use, and repair action. Use detailed rows such as `structure_unit_id`, parent goal, unit job, contribution type, child obligations, downstream consumers, conclusion recovery, local logic status, source status, trace status, structural status, and repair action when the artifact risk, source-backed claim, or an upper-level workflow requires auditable closure. For literature reviews and technology summaries, add same-level progression only when the items are meant to form a chain rather than explicit background.
5. Treat high-importance sections, slides, pages, paragraphs, or public-facing capability blocks as under-modeled until their internal support path is visible and their structural contribution is usable: local claim, support, warrant or mechanism, assumptions, rebuttal or undercutter, limitation, source need, next action, parent-goal support, downstream consumer, and conclusion recovery when relevant.
6. Keep a coverage summary for substantive artifacts: `total_units_detected`, `model_cards_created`, `deep_cards_created`, `shallow_cards_created`, `skeleton_cards`, `skipped_units`, `skipped_reason`, `structural_rows_created`, and `structural_rows_unresolved`.
7. For Markdown-like outlines, use `structure from-markdown` to convert headings and labeled fields into the existing hierarchy. Keep this narrow; it is not a PDF, DOCX, citation, or page-layout parser.
8. Run ordinary argument diagnostics for local claim support.
9. Run structure audit for cross-block flow and temporal misuse: missing handoff, missing sibling progression, late limitation, overloaded block, orphan block, duplicate claim, unsupported parent goal, missing child obligation, missing downstream consumer, unrecovered conclusion obligation, current-state claims with undated source material, and source dates that are later than covered periods.
10. Build or reuse the gap ledger when a structure issue or under-modeled block implies missing evidence, a missing bridge, an unanswered rebuttal, a missing downstream consumer, conclusion recovery, or source-backed support. Route source-backed gaps through `route:source-library` instead of resolving them as prose.
11. Track importance from the start so core claims, fragile bridges, dangerous limitations, structural bridges, and optional background stay distinct.
12. For source-backed artifacts, require a section, paragraph, page, or slide blueprint before treating structure as ready for final prose. Core artifact units should identify what the unit proves, claim, support, limitation or counterpoint, who says it or which source role supports it, source markers, claim-strength label, structural role supported, downstream use, and final treatment: main text, footnote, appendix, or omitted with reason. Use `logicguard citation matrix`, `logicguard citation audit`, and `outline --paragraph <claim> --with-citations` when a model is available.
    When an upper-level writing workflow is active, return this blueprint and
    structure diagnosis to that workflow for final prose integration.
13. Check that important artifact units have inline citation markers or a clear reason they are uncited framing. A final bibliography alone is not enough for source-backed claims.
14. If the upstream work has a source registry, check that artifact-unit markers resolve to registered sources and that source roles match the unit's claim wording and structural role. Undefined markers, duplicate ids, bibliography-only support, or execution/outcome claims citing only announcement/context sources mean the source-backed structure is not ready.
15. For Research Reasoning Atlas artifacts, check that central conclusion units have a visible tournament status: preferred conclusion, strongest opposition, live alternatives, selected model lens or warrant, expert stance role when relevant, and allowed wording. A unit that only states the preferred conclusion is under-modeled.
16. For long artifacts, check that the artifact has a reader route: first question answered, section/order rationale, downstream consumption, limitation placement, and forecast boundary.
17. For substantive source-backed artifacts, check that claim origin, direct facts, source statements, scope boundaries, execution or outcome evidence, context or motive evidence, interpretation, counter/limiting evidence, and forecast triggers are not collapsed into one unsupported section claim. These are coverage obligations, not mandatory visible headings.
18. For thesis and paper figures or tables, map the visual as an artifact unit:
    intended takeaway, caption status, source/provenance status, body
    explanation, argument role, visual clarity issue, and downstream consumer.
    Missing body explanation or unclear argument role is a structure problem,
    not only a formatting problem.
19. Check reader-facing artifact copy for internal workflow labels and move them to a methods appendix or local run record unless the user asked to show methodology.
20. Do not claim full structured-artifact coverage when only section order, cross-block handoff, marker presence, preferred-conclusion support, or a small sample of blocks was checked. Report the remaining citation, opposition, alternative, model-card coverage, structural-contribution, sibling-progression, figure/table, or conclusion-tournament depth gap explicitly.
21. After meaningful structure analysis or changes, usually show a selective AI-chosen Mermaid diagram or table. First identify whether the relationship is document structure, argument support, structural contribution, gap diagnosis, conclusion tournament, or source reuse; then choose the clearest structure map, argument-support map, contribution graph, gap table, tournament table, or source-path view. Use structure edges for contains, precedes, hands off, consumes, duplicates, or overloads only when the question is actually structural. Skip only tiny edits, grammar-only work, or final artifact-native copy.
22. For existing thesis or paper revision, preserve a visible revision plan for
    each structural repair: added, rewritten original, moved, deleted or
    omitted, source note, or human-review gap. Do not let later style polishing
    overwrite earlier provenance semantics.
23. For non-trivial artifacts, write the structure result into the main
    LogicGuard closure ledger: model-card coverage, structural rows unresolved,
    high-importance leaves, source/citation readiness, postwrite status, and
    skipped checks. The main logicguard_closure_check.py helper must be able
    to see these rows before a full structure or reasoning claim is made.

## Boundaries

- Return to the general LogicGuard route for broad or ambiguous LogicGuard requests.
- Use `route:source-library` first when the user provides concrete source materials that need preservation.
- Use `route:artifact-synthesis` when the task is to create a new target story plan after review.
- Do not paste internal diagnostic labels such as `missing_handoff` or `late_limitation` into final user-facing artifact copy.
- Do not treat local paragraph coherence, transition words, or citation-marker presence as proof that a unit structurally supports its parent or is consumed downstream.
- Do not require the full structural row shape for every task. Use detailed
  rows when risk or an upper-level workflow warrants them; otherwise keep the
  contribution note compact.
- Do not treat a literature/technology review item as useful merely because it
  relates to the chapter topic; it must either progress from neighboring items,
  feed a later unit, or be explicitly kept as background.
- Structured-artifact diagrams are a LogicGuard-specific view and must remain usable without FlowGuard diagram rules.

## Common Commands

```powershell
researchguard logic structure map examples\structured_artifact_deck.yaml
researchguard logic structure from-markdown examples\structured_report_outline.md --artifact-kind report --output report_model.yaml
researchguard logic structure audit examples\structured_artifact_deck.yaml
researchguard logic importance examples\structured_artifact_deck.yaml
researchguard logic diagnose examples\structured_artifact_deck.yaml
researchguard logic citation matrix examples\engineering_efficiency_argument.yaml
researchguard logic citation audit examples\engineering_efficiency_argument.yaml
```

## Native execution-depth receipt gate

Before claiming broad structured-artifact coverage or final argument readiness, run `researchguard logic depth <model.yaml> --output <logic-depth-receipt.json>` after the last meaningful model change. Require matching model and authoritative-universe fingerprints, the LogicGuard-owned threshold, complete requested claim scope, every explicit card/block reconciled regardless of low declared importance, only closed non-contributing exclusions, role-complete important cards, every important claim's own connected support/warrant/assumption/boundary/opposition universe, explicit sharing declarations for reused role nodes, no unresolved artifact unit or disconnected important node, resolved conclusion competition, every critical and claim-local applicable perturbation effective, no untested important node, and `broad_claim_licensed: true`. Sampling a few convenient sections or nodes is not broad coverage. LogicGuard exposes one enforced depth route; callers cannot select a lighter profile or threshold. Otherwise report the artifact as partial or narrow the conclusion to the receipt's boundary. The target-owned shallow-negative regression calibrates the gate but cannot replace current task evidence. This is the native LogicGuard route.

Then issue the structured-artifact binding with
`researchguard logic route-depth PACKAGE.json --output RECEIPT.json`
using target `route:structured-artifact`, owner
`logicguard.structured-artifact`, and route
`route:route:structured-artifact:audit`. Every eligible artifact unit must
show parent goal, structural contribution, support path, opposition or closed
disposition, downstream consumer, and limitation. Section-order sampling or a
few polished paragraphs cannot close the full artifact universe, and this
wrapper cannot promote a bounded native receipt.
Declare a non-empty authoritative `important_unit_ids` denominator. An important
or required artifact unit cannot be excluded or reclassified; another exclusion
needs current hashed evidence, a closed non-contributing/not-applicable disposition,
and no structural contribution.

Counts, role-name lists, catalog expansion, whole-receipt hashes, and ordinal
ranges are not per-obligation evidence. Every satisfied artifact obligation
must retain its exact target-native semantic object, `evidence_ref`, and
lowercase content hash; a missing, renamed, overlapping, mechanically generated,
or summary-only mapping blocks broad artifact closure.



<!-- BEGIN MANAGED VALIDATED TEMPLATE PACK -->
## Validated Template Pack Routing

- Target families: `family:logicguard-template-packs`; native owner: `owner:logicguard-template-packs`.
- Current catalogs: `catalog:logicguard-template-packs` revision `1.0.0`.
- Resolve the task through this Guard's native router first, then ask the target-owned adapter for a current neutral projection; never infer a template from wording or a skill name.
- Preserve the adapter's complete candidate and rejection accounting. Zero candidates may use only the declared validated base; one candidate gets a read-only preview; many candidates require complete dependencies, pairwise compatibility, one field owner, and target-authored dominance or must block as ambiguous.
- Recompute the projection immediately before applying a preview. A stale request, catalog, route, builder, validator, or content identity blocks all writes.
- Hand the selected preview to the target-declared builder and consume every target-native validator receipt. Template structure is not domain validity, completion, installation, release, or publication evidence.
- Record a harvest disposition after creating or materially deepening a reusable model, and keep no-match evidence visible.
- Declared validated bases: `logicguard.base`.
- Template inventory: `logicguard.argument`, `logicguard.base`, `logicguard.deepening`, `logicguard.execution-package`, `logicguard.purpose`, `logicguard.source-library`, `logicguard.structured-artifact`, `logicguard.synthesis`.
- Native validator inventory: `logicguard-template-pack:argument`, `logicguard-template-pack:base`, `logicguard-template-pack:deepening`, `logicguard-template-pack:execution-package`, `logicguard-template-pack:purpose`, `logicguard-template-pack:source-library`, `logicguard-template-pack:structured-artifact`, `logicguard-template-pack:synthesis`.
- Claim boundaries: This unsealed catalog spec projects current LogicGuard-owned templates for target-owned candidate accounting only. Catalog digests and receipts remain LogicGuard-owned derived records.
<!-- END MANAGED VALIDATED TEMPLATE PACK -->

<!-- BEGIN MANAGED PURPOSE AND BLOCKABILITY -->
## LogicGuard purpose and blockability contract

Packaged baseline purpose: Prevent a deck, paper, report, brief, section, or paragraph from being called structurally ready while its unit inventory, contributions, claim/source roles, opposition, handoffs, limitations, or licensed scope is incomplete.

Baseline claim boundary: A pass licenses only the structural readiness of the exact current artifact hierarchy and modeled support paths; it does not prove factual truth or visual/editorial quality.

The repository keeps these representative baseline failures only to prove that the native verifier can block them:

- `Artifact unit inventory is incomplete`: block when a governed page, section, paragraph, or other unit is missing.
- `Contribution or orphan structure is invalid`: block when a unit lacks a distinct structural job or remains orphaned/duplicated.
- `Claim/source roles are unsupported`: block when an important claim lacks current source/support role evidence.
- `Opposition or alternatives are absent`: block when material rebuttals or alternatives have no modeled treatment.
- `Handoff or limitation is missing`: block when downstream use, transition, limitation, or boundary is absent.
- `Licensed scope is overreached`: block when the readiness statement exceeds the checked artifact universe.

These packaged examples are not the purpose of a real target model and cannot authorize one. Before building every real model or route result, AI must write a target-local `logicguard.target_model_purpose_declaration.v1` under the explicit target root. AI declares what this exact model is meant to prevent, its bounded claim, the exact candidate path, and one or many current failure declarations. Every current failure binds one LogicGuard-native oracle plus one target-owned known-good and known-bad case. Then AI freezes `.logicguard/guard-purpose-contract.json` while the candidate path is still absent, builds the candidate, binds it to the frozen fingerprint, exhausts every declared proof, and only then requests native closure.

Missing declarations, late declarations, stale fingerprints, non-blocking bad cases, failing good cases, or a candidate that exposes any declared failure are non-pass. There is one enforced route and no selectable mode, threshold, compatibility reader, fallback, or lighter success path. Evidence insufficiency may narrow the final claim, but it does not select a weaker check.

`guard-model/verify.py` is the LogicGuard-native verifier. `guard-model/baseline-*.json` proves only family capability.
<!-- END MANAGED PURPOSE AND BLOCKABILITY -->
