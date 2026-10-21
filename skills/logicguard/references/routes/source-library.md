# Internal LogicGuard route: source-library

This is an internal LogicGuard route for source intake and reusable source-library work. Use it before ordinary argument modeling when the user provides concrete material that should not be lost.

For Codex-facing work, "added to the source library" means two things:

1. The material is preserved or reused as a durable LogicGuard source record.
2. Codex has read the material and saved a content-level shallow source model.

Mechanical `intake` or `library import` alone is only preservation. It is not completion for PDFs, papers, books, reports, or other source-like materials.

Use the LogicGuard CLI entrypoint:

```powershell
researchguard logic <args>
```

## Workflow

1. Identify concrete materials: local files, long pasted text, text files, URLs, papers, books, reports, or web snapshots. Do not treat a short command-only prompt as a source.
2. Preserve material first with `intake` or `library intake`; do not wait until after reasoning to store it.
3. Treat the preservation command as an intermediate step. Continue automatically to AI content reading and modeling when the material is a PDF, paper, report, book, article, long text, or source-like file.
4. Read the material content using the available Codex/file-reading capability. Do not require the LogicGuard CLI to parse arbitrary PDFs; the AI agent owns the reading and extraction step.
5. Build a content-level shallow model before deeper reasoning. At minimum, extract source-derived problem/context, central claim, method, key evidence or results, warrant/mechanism, conclusion, and limitation or scope boundary when available. Do not invent missing elements.
6. Save the model with `library model-source` or the equivalent API, using Claim, Evidence, Warrant, Method, Result, Scope, Limitation, and Rebuttal nodes as appropriate.
7. When the source or UI needs Chinese/English switching, save bilingual model text in the same write with `--i18n-json`: explicit Chinese and English display variants with no implicit language substitution for title and node fields.
8. Verify with `library view-graph` or `library view-snapshot`. Only claim intake is complete when the source graph has content logic nodes beyond the Document/navigation node. For bilingual models, check both `--language en` and `--language zh-CN`.
9. If preservation succeeds but reading or model writing fails, report "saved but modeling incomplete" with the blocker; do not call the source fully added.
10. Attach to an explicit project only when the user supplies a project id or topic. Leave uncertain material uncategorized.
11. Preserve lightweight temporal clues when available: `source_date` for the source's own date and `coverage_period` for the factual period covered. Keep these separate from library accession time such as `added_at`.
12. When a LogicGuard gap ledger identifies missing evidence, missing baseline, unanswered rebuttal, scope mismatch, or fragile source support, search existing library nodes first and only then intake/model new candidate material when needed.
13. For model-mesh projects, preserve the gap handoff fields whenever available: `gap_id`, `model_card_id`, `claim`, `missing_source_role`, `required_strength`, `locator`, `unsafe_wording`, and `safe_interim_wording`.
14. For project work, select sources, deepen only topic-relevant paths, anchor branches to source nodes or blocks when possible, and link project argument nodes to source nodes, branch nodes, or model-card ids.
15. When a high-importance project claim depends on a shallow source model, check whether the relevant method, result, evidence, warrant, limitation, or rebuttal is actually exposed. If not, deepen the anchored path or report the claim as under-supported.
16. Preserve source-role cues for later writing: event fact, official claim, independent report, limiting/counter evidence, expert analysis, historical background, or hypothesis. These roles should be available to a later claim-to-source matrix.
17. When source work supports a structural contribution graph, preserve `structure_unit_id`, parent goal, contribution type, intended downstream consumer, and the structural role the source can and cannot support, such as background, definition, method choice, validation criterion, validation evidence, limitation, or conclusion recovery.
    These fields are handoff context, not source-library ownership of the final
    artifact structure or prose.
18. When source work supports a Research Reasoning Atlas, also preserve the branch id, model-lens id when relevant, expert stance family when relevant, and whether the source supports, opposes, distinguishes, qualifies, or could falsify a conclusion candidate. These are generic source roles, not domain-specific source categories.
19. When an upstream source registry or final citation marker exists, preserve that id or marker, locator, claim use, and access status in project notes or model metadata when feasible. Do not let source-library ids, registry ids, and final citation markers become ambiguous.
20. After gap-driven source work, re-run evaluation, diagnostics, and relevant simulation; do not claim the gap is resolved from AI prose alone.
21. Use package export/import only through LogicGuard safe-merge commands. Inspect unknown packages and dry-run before real imports.
22. For non-trivial source reuse, deepening, linking, or package-route explanations, default to a compact AI-selected Mermaid diagram or table. Before drawing, identify the relationship being explained, then choose the clearest source-path, argument-support, research-process, document-structure, structural-contribution, gap table, or comparison-matrix view. This is a toolbox, not a fixed mapping. Do not turn all source nodes into one generic flowchart. Skip simple search/status answers where a diagram adds no explanation value.

## Completion Gate

For source intake, completion requires:

- source record saved or reused;
- Codex-readable content inspected;
- content-level shallow model written;
- bilingual model content written when language switching is expected;
- viewer payload or source graph verified in the relevant display language(s);
- source-backed gap rechecked through evaluation/diagnostics/simulation when this intake was triggered by a gap ledger;
- anchored deepening completed or explicitly reported as missing when the source supports a high-importance project claim;
- model-card id, gap id, source role, required claim strength, and unsafe/safe wording preserved when the intake was triggered by a model-mesh gap;
- structural contribution fields preserved when the source is used to support a parent goal, downstream consumer, method choice, validation criterion, validation evidence, limitation, or conclusion recovery;
- source-role cues, source registry ids or citation markers, locator, claim use, and access status preserved when the source will support citation-grounded writing;
- Atlas branch role, model-lens role, expert stance role, or falsifier role preserved when the source is used for branch-aware research;
- any partial or missing model element reported honestly.

When showing the verified graph, make the selected graph mode clear. A source can have more than one possible reading, but the viewer should render the single recommended graph directly. Argument support explains why a conclusion is licensed, research process explains how methods produced results, source path explains how project work reuses the source, and comparison/gap tables may be clearer when the issue is source contrast or missing support.

If only the first item is true, say the source is preserved, not fully modeled.

For source-library work feeding an artifact, return saved native source/content
nodes, the cards or gaps that depend on them, remaining deepening needs and safe
source roles. Saved material does not prove completed argument modeling. Keep
missing content or unresolved support visible; final prose integration belongs
to the active writing/document owner. No separate closure ledger is required.

## Boundaries

- Return to the general LogicGuard route for mixed or ambiguous LogicGuard requests.
- Use `route:structured-artifact` when the main task is section, slide, page, or paragraph structure review.
- Use `route:artifact-synthesis` when the main task is building a new target story plan from existing material.
- When an upper-level writing workflow is active, return source-reuse and
  source-role findings to that workflow for final prose integration.
- Importance is cross-cutting. Use it inside the source-library workflow; do not route to a separate importance skill.

## Common Commands

```powershell
researchguard logic intake .logicguard-library --file paper.txt --project my-project --project-topic "Topic" --json
researchguard logic library import .logicguard-library paper.pdf --title "Source title" --source-date 2024 --coverage-period "2021-2023"
researchguard logic library model-source .logicguard-library source-id --claim "AI-read central claim" --method "AI-read method" --evidence "AI-read key evidence" --result "AI-read result" --warrant "AI-read mechanism" --limitation "AI-read scope boundary" --i18n-json .\source-id.i18n.json
researchguard logic library view-graph .logicguard-library source-id --language en
researchguard logic library view-graph .logicguard-library source-id --language zh-CN
researchguard logic library deepen-source .logicguard-library source-id --project my-project --topic-focus "Focus" --locator "Section 4" --anchor-node C1
researchguard logic library search .logicguard-library "query" --project my-project
researchguard logic gaps project_argument.yaml
researchguard logic library export-package .logicguard-library project.zip --project my-project
researchguard logic library import-package .logicguard-library project.zip --dry-run
```

## Native completion and stopping

1. Use intake/import to preserve source originals, source records, and selected project bindings.
2. When a content model is needed, read the material and run model-source or deepen the relevant nodes to produce the source graph.
3. Report extraction failures, content shells and unfinished models. Saved material and argument readiness are separate outcomes.

Stop at the actual saved/graph result or explicit partial completion. Do not hand-fill a per-object PASS checklist.
