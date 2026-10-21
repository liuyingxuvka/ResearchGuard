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
12. For source-backed artifacts, require a section, paragraph, page, or slide blueprint before treating structure as ready for final prose. Core artifact units should identify what the unit proves, claim, support, limitation or counterpoint, who says it or which source role supports it, source markers, claim-strength label, structural role supported, downstream use, and final treatment: main text, footnote, appendix, or omitted with reason. Use `researchguard logic citation matrix`, `researchguard logic citation audit`, and `outline --paragraph <claim> --with-citations` when a model is available.
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
23. Return the native structure result, unresolved structural rows, important
    leaves, source/citation gaps and skipped work. The active writing/document
    owner performs final prose and postwrite integration. The retired manual
    closure-ledger helper is not a completion gate.

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
researchguard logic structure map examples/logic/structured_artifact_deck.yaml
researchguard logic structure from-markdown examples/logic/structured_report_outline.md --artifact-kind report --output report_model.yaml
researchguard logic structure audit examples/logic/structured_artifact_deck.yaml
researchguard logic importance examples/logic/structured_artifact_deck.yaml
researchguard logic diagnose examples/logic/structured_artifact_deck.yaml
researchguard logic citation matrix examples/logic/engineering_efficiency_argument.yaml
researchguard logic citation audit examples/logic/engineering_efficiency_argument.yaml
```

## Native completion and stopping

1. Start from the structure model or from-markdown input and build_artifact_map.
2. Run the native structure audit, preserving cross-unit contributions and claim/source/citation boundaries for the declared task.
3. For full argument or important delivery-readiness claims, run real native depth and report current gaps and licensed scope.

Stop at the structural diagnosis and its visible gaps, native closure, or an explicit non-closure terminal. Broad/final/high-impact claims retain important nodes, opposition, contributions and citation checks; do not shrink the universe to bypass them.
