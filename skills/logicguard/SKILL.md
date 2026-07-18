---
name: logicguard
description: Use LogicGuard, the local hierarchical executable argument-modeling tool, as the general route for explicit LogicGuard requests, ordinary argument modeling, mixed LogicGuard workflows, and logically demanding writing or reasoning audits. Use internal routes first when a request clearly matches source-library intake/reuse, structured artifact review, artifact synthesis, model deepening, or project-library viewer work. Chinese triggers include 逻辑审计, 论证模拟, 论文逻辑, 大型报告, 技术报告, PPT逻辑, 结构审查, 父子结构, 章节之间互相支撑, 同级章节递进, 技术综述递进, 方法深度, 结论是否被证据支持, 缺失假设, 反驳未回应, 结论过强, 生成论文大纲, and 用 LogicGuard.
---

# LogicGuard

## Purpose

Use LogicGuard as a local guard layer for structured reasoning. It checks whether a conclusion is structurally licensed by declared premises, evidence, warrants, assumptions, rebuttals, and scope. It does not decide factual truth.

Use the single installed `researchguard` console. No checkout locator, environment-variable launcher, or alternate module command is part of normal execution.

## Entrypoint Scope

LogicGuard owns argument modeling and its five internal routes. It does not own
source discovery or evidence-trace reconstruction; those go to SourceGuard or
TraceGuard through an explicit typed handoff.

## Local Material Routing

Read the exact file under `references/routes/` for source-library,
structured-artifact, model-deepening, artifact-synthesis, or
project-library-viewer work. These are internal routes, not installed skills.

## Entrypoint Acceptance Map

- one clear internal capability -> its current LogicGuard route;
- ordinary or mixed argument work -> the general LogicGuard route;
- missing evidence -> explicit SourceGuard handoff;
- missing temporal or competing-storyline support -> explicit TraceGuard
  handoff;
- ambiguous, failed, stale, or incomplete work -> visible non-pass result.

## Use When

Use for explicit LogicGuard requests, logically demanding writing or reasoning
audits, argument models, and mixed LogicGuard workflows.

## Do Not Use When

Do not use LogicGuard to decide factual truth, silently search for missing
evidence, retry through another route, or turn chronology into causality.

## Required Workflow

Select one current route, load its target-owned instructions, build or inspect
the argument model, execute the route's native checks, and preserve gaps and
handoffs before writing a conclusion.

## Hard Gates

Missing warrants, hidden assumptions, overclaim, scope mismatch, unanswered
rebuttals, unsupported causal transfer, stale evidence, or an incomplete
high-importance model blocks broad closure. No internal route may silently
become another route.

## Output Requirements

Report the route and model identity, evidence, failures, blockers, skipped
checks, open gaps, residual risk, safe wording, typed handoffs, and the claim
boundary.

## Skill Structure

LogicGuard is one direct ResearchGuard member with five internal routes. Route once by the requested first action:

- `route:source-library`: preserve, model, deepen, link, or move sources.
- `route:structured-artifact`: audit or repair document/deck structure.
- `route:model-deepening`: recursively deepen an existing model.
- `route:artifact-synthesis`: produce an evidence-bounded story plan.
- `route:project-library-viewer`: inspect the read-only project library.

These are internal routes, not separately installed skills. Read the matching file under `references/routes/` before executing it. Mixed or ambiguous requests remain in this general route until one exact owner is selected; an unclear route blocks instead of trying another route.

Use this main `logicguard` skill for explicit `$logicguard`, ordinary argument modeling, mixed workflows, ambiguous requests, or any case where multiple internal routes must be coordinated.

Internally, LogicGuard keeps these callable flows:

- `default_source_intake`: preserve concrete materials in the reusable source library before deeper reasoning, then create shallow source models and best-effort labeled logic nodes.
- `argument_modeling`: build and maintain the user's own paper, book, report, or claim model.
- `source_library`: maintain the reusable source logic library for papers, books, reports, web snapshots, source models, project branches, anchored topic-focused deepening branches, and node links.
- `structured_artifact`: map natural boundaries such as deck sections, slides, paper sections, paragraphs, report sections, and multi-source briefs onto the existing LogicGuard hierarchy.
- `model_deepening`: grow an existing model by selecting important or weak nodes, proposing child nodes, recording gaps, and routing source/structure/synthesis follow-up.
- `artifact_synthesis`: create a target story plan from existing argument models, source-library links, structured artifact blocks, user goals, and importance metadata.
- `project_library_viewer`: open or check the project-oriented source-library UI copied from Khaos Brain and rewired to LogicGuard cards, top-level logic graphs, local version status, green-blue active-view package import/export actions, and project dissolve.

Importance is not a separate flow. It is a cross-cutting model property on nodes, edges, blocks, source nodes, source branches, and project links. Keep `confidence`, `weight`, and `importance` distinct: confidence is support strength, weight is edge strength, and importance is how critical the item is to the target artifact or reasoning goal.

Source temporal context is lightweight and separate from importance. Preserve `source_date` for the source's own date and `coverage_period` for the factual period covered when those clues are available. Keep them separate from library accession time such as `added_at`. Use temporal context to organize reports, papers, presentations, and project summaries, but surface it in final artifact copy only when it materially affects core claims, conflicts, current-state conclusions, or evidence freshness.

## Guard Closure Contract

For non-trivial LogicGuard work, create or update a closure ledger before final
claims. The ledger should record `model_card_coverage`,
`high_importance_open_gaps`, `postwrite_status`, skipped checks, safe wording,
and unsafe claim boundaries. When a model, structure model, or citation model
exists, run the aggregate helper:

```powershell
python scripts/logicguard_closure_check.py --ledger <logicguard-closure-ledger.json> --model <model.yaml-or-json> --structure-model <structure.yaml-or-json> --citation-model <citation.yaml-or-json> --json
```

If the helper returns `partial`, `blocked`, or `downgraded`, continue through
the named `next_actions`: deepen high-importance open gaps, route source gaps
to SourceGuard, route trace gaps to TraceGuard, rerun postwrite audits after
final prose changes, or downgrade the final claim. Do not claim full
LogicGuard coverage from a top-level model, a sample of blocks, a stale
postwrite audit, or a skipped citation/structure check.

## Research Reasoning Atlas Contract

For substantive research artifacts, LogicGuard must not only ask whether the preferred conclusion has support. It must ask whether that conclusion survives strong opposition, material alternatives, relevant model lenses, expert-role boundaries, and robustness tests.

Use this contract when a Research Reasoning Atlas is present or when a central conclusion is important enough to require deeper adjudication:

- Build or inspect a conclusion tournament before strong final wording.
- Steelman the strongest opposing case instead of using a weak rebuttal.
- Compare material alternative explanations, not just support for the preferred conclusion.
- Treat analytical model lenses as warrants, scope rules, limitations, or evidence needs; a lens name alone is not support.
- Type expert stances as fact evidence, interpretation, forecast, stakeholder statement, method lens, disputed claim, or background.
- Run or simulate robustness checks: remove strongest support, accept strongest opposition, flip a fragile assumption, or narrow scope.
- Recommend final wording as preferred, qualified, unresolved, downgraded, or omitted.

Conclusion tournaments remain structural audits. They do not decide factual truth without evidence; they decide whether the written conclusion follows better than its live competitors.

## Model Mesh Default Contract

For non-trivial reasoning, writing, audit, synthesis, source-backed, or structured-artifact work, LogicGuard defaults to a model mesh, not a single shallow model. Build or inspect a countable network of model cards whenever the task can benefit from deeper structure. Only use a shallow model when the user explicitly asks for a lightweight pass, the task is clearly small and low-risk, or source/material limits make deeper modeling impossible.

Default mesh layers are:

```text
Task or Artifact -> Structure Unit -> Subunit or Paragraph Block -> Local Argument -> Role Nodes
```

Use model-card roles such as `mesh_root`, `structure_card`, `argument_card`, `deep_card`, `handoff_card`, and `skeleton_card`. For long papers, reports, theses, decks, investigations, public project pages, or complex rewrite work, the number of model cards should scale with the natural structure units, not with only the top-level sections. A high-quality run should leave a model-card index and a coverage summary: target units, cards created, deep cards, shallow cards, skeleton cards, skipped units, and skipped reasons.

High-importance cards are not acceptable leaves. A deep card should expose claim, support, warrant or mechanism, assumption, limitation or qualifier, rebuttal or undercutter, source need, and next action when those roles are relevant. Missing roles remain explicit gaps.

If LogicGuard only builds a top-level route, a small node set, a chapter list, or a few sample paragraph blueprints for a complex task, label it as `round-0 skeleton`, `partial model`, or `under-modeled`. Do not claim full LogicGuard coverage until the model-card network and coverage summary support that claim.

Cross-Guard handoffs must preserve card identity:

- LogicGuard -> SourceGuard: `gap_id`, `model_card_id`, `structure_unit_id`, `parent_goal`, `unit_job`, `contribution_type`, `downstream_consumer`, `claim`, `missing_source_role`, `required_strength`, `locator`, `unsafe_wording`, and `safe_interim_wording`.
- LogicGuard -> TraceGuard: `trace_need_id`, `model_card_id`, `structure_unit_id`, `source_unit_id`, `destination_unit_id`, `process_or_causal_claim`, `required_trace_layer`, `known_steps`, `missing_steps`, `weakest_link`, `unsafe_wording`, and `safe_interim_wording`.

For thesis, dissertation, paper, or deep-research writing and revision, prefer
the upper-level `logic-writing` skill when the task also needs existing DOCX
handling, visible revision provenance, authorial-voice integration, multi-round
source/trace handoffs, or a separate revision report. LogicGuard
still owns the argument model, model-card coverage, recursive deepening,
source-fit audit, synthesis plan, and postwrite closure.
When that upper-level workflow is active, LogicGuard returns diagnostic
findings and safe wording boundaries; it does not independently claim final
thesis-native prose integration or submission-ready closure.

## Structural Contribution Graph Contract

For long papers, reports, theses, dissertations, decks, and other hierarchical artifacts, LogicGuard must check more than whether each local unit reads coherently. It must build or inspect a structural contribution graph that asks:

```text
What does this unit do for its parent, who later uses it, and how is it recovered in the conclusion or terminal claim?
```

Keep one row per important structure unit with these fields when material.
For lighter work, use the smallest useful contribution note instead: unit role,
parent support, downstream use, and repair action. Detailed rows are for
high-risk artifacts, source-backed claims, or upper-level workflows that need
auditable closure; they are not mandatory fields for every small structure
review.

- `structure_unit_id`, `artifact_locator`, `artifact_unit_type`, `parent_unit_id`, `parent_goal`, and `unit_job`;
- `contribution_type`, such as `background`, `definition`, `literature_summary`, `technology_summary`, `gap_derivation`, `method_choice`, `validation_criterion`, `validation_evidence`, `limitation`, or `conclusion_recovery`;
- `importance`, `child_obligations`, `downstream_consumers`, and `conclusion_recovery`;
- `local_logic_status`, `source_status`, `trace_status`, `structural_status`, `repair_action`, `allowed_wording`, and `unsafe_wording`.

A high-importance non-background unit is not structurally closed merely because its paragraph-level logic passes. It also needs a parent goal, a clear unit job, relevant child obligations, at least one real downstream consumer, and recovery in the conclusion or terminal claim when it affects the final result. Otherwise classify it as `orphan`, `missing_downstream_consumer`, `unrecovered`, `background_only`, `appendix`, `omit`, or `human_review`.

For literature reviews, technology summaries, and `Stand der Technik` chapters,
also audit same-level progression. Adjacent review items should record whether
the later item extends, narrows, contrasts with, depends on, or exposes a
limitation in the earlier item. If each item only returns to the parent model,
instead of building a sibling chain toward the research gap, classify the route
as `missing_sibling_progression` or `parallel_background` and choose a visible
treatment: add a bridge, reduce to background, reorder, move, omit, or request
human source review.

Use this graph to keep local logic, source support, trace/process support, and structural contribution separate. A unit may be locally coherent but structurally unused; a source may support background but not a method choice; a trace may support process setup but not conclusion recovery.

## Deep Modeling Contract

For important writing and reasoning work, LogicGuard must not stop at a document-level or section-level outline. Public-facing project pages, papers, reports, policy memos, technical conclusions, review responses, deck storylines, and other high-importance artifacts need recursive modeling before final prose or final conclusions.

- High-importance `Section` and `ArgumentBlock` nodes are not acceptable leaves. Expand them into local `Claim`, `Evidence`, `Warrant`, `Assumption`, `Rebuttal` or `Undercutter`, `Qualifier` or `Limitation`, `Method`, and `Result` nodes as relevant.
- For source-backed artifacts, model at the requested artifact's natural hierarchy: report/document -> section -> paragraph, paper -> section -> paragraph, memo -> decision block, deck -> section -> slide, article -> section/scene -> paragraph, literature review -> theme -> source cluster. Do not force a fixed report hierarchy when the user requested a different artifact type.
- Important paragraphs, slides, pages, or artifact units are not acceptable leaves when they carry material claims. Expand them into local claim, source support, warrant or mechanism, assumption, limitation, rebuttal or undercutter when relevant, source role, citation marker, final treatment, and allowed wording.
- Abstract capability or outcome claims must be decomposed into problem, failed baseline or need, mechanism, evidence, warrant, reader/user value, boundary, and likely rebuttal when those elements matter.
- A shallow model can still be useful, but it must be reported as under-modeled or partial. Do not claim full LogicGuard coverage when only top-level block relationships were checked.
- For generation work, produce or inspect a section plan, paragraph blueprint, or target story plan before final artifact-native copy. Missing support, missing warrant, missing boundary, or unanswered rebuttal stays a gap; do not hide it with smoother prose.
- For hierarchical artifacts, also produce or inspect the structural contribution graph before final prose. Missing parent support, missing child obligation, missing downstream consumer, orphan material, or unrecovered conclusion obligation stays a structural gap even when local argument diagnostics are green.
- For method, methodology, and research-design sections, a list of steps is not
  a deep model. Core method units should expose design need, selected choice,
  rejected alternative, rejection reason, implementation consequence,
  validation consequence, limitation, and downstream use. If those fields are
  missing, classify the unit as `flat_method_step` instead of treating it as
  ready prose.
- For figure and table references, model the intended takeaway, argument role,
  body explanation, caption/source status, and visual clarity concern. A
  figure/table that is merely present in the document is not yet serving the
  argument.
- Keep the rule general. Do not create artifact-specific routes for one format such as README; use the existing structured-artifact, artifact-synthesis, source-library, and argument-modeling routes.
- For thesis and paper revision, original-text rewriting, heading rewriting,
  neighboring-paragraph rewriting, and style integration are normal
  model-grounded repair actions unless the user forbids them. Do not restrict
  LogicGuard repair to additions or transition sentences when existing prose is
  the source of the weak warrant, overclaim, missing boundary, or poor handoff.
- After final prose is written, rerun or simulate a postwrite closure pass for
  high-priority model cards. Classify every remaining important boundary as
  supported, written repair, downgraded, source gap, project-material gap,
  trace gap, structural gap, scope boundary, or human-review item before
  claiming closure.

## Citation-Grounded Writing Contract

For reports, papers, policy memos, literature reviews, investigation reports, and other source-backed long-form writing, LogicGuard must make source support visible in the writing plan and final prose.

The requested artifact genre controls the final prose. LogicGuard must not force a diagnostic-table style, fixed report style, or fixed fact/official-claim/inference/gap headings into the reader-facing artifact. Use source roles, claim types, limitations, and gaps as internal coverage obligations and audit dimensions. They may appear as natural prose, citations, footnotes, tables, or appendix depending on whether the user requested a report, paper, memo, brief, article, literature review, deck storyline, decision note, or another artifact. When the general `logic-writing` workflow owns thesis, paper, or deep-research final writing, hand the coverage obligations back to that workflow for contribution-and-expression integration.

- Build or inspect a claim-to-source matrix before final prose. Each important claim should list source ids, source role, claim strength, limitation or rebuttal, source can support, source cannot support, semantic-fit risk, required inline citation marker, and target artifact locator such as paragraph, section, page, slide, note, or appendix.
- Prefer the executable matrix path when a model is available: `logicguard citation matrix` for the table and `logicguard citation audit` for missing source, missing role, generated-marker, and duplicate-placement checks.
- When the upstream investigation has a source registry, reconcile the matrix with it before final delivery: every inline marker should resolve to one registered source, every important registry source used in prose should appear in the matrix, and source roles should match the claim as written.
- Use compact inline markers such as `[S1]`, `[S2; S4]`, or `[S3, limiting]` in the final prose for important factual claims, official-claim reports, analytic inferences, limitations, and future hypotheses.
- Distinguish source roles: event fact, official claim, independent report, limiting/counter evidence, expert analysis, historical background, and hypothesis.
- For each core paragraph or artifact unit, create or inspect a blueprint: paragraph/page/slide/unit job, what it proves, claim sentence or claim region, support, limiting/counter sentence when relevant, who says it or which source role supports it, source markers, claim-strength label, semantic source-fit risk, allowed wording, and final treatment: main text, footnote, appendix, or omitted with reason.
- For each core section or artifact region, create or inspect a section/region blueprint: purpose, previous-section handoff, main claim, source path, paragraph/page/slide order, and next-section handoff.
- Direct quotes must be short and attributed. Paraphrases require source markers. Synthesis needs multiple source markers and cautious wording such as "taken together" or "the available evidence supports".
- Do not leave source-backed claims supported only by a final bibliography.
- If final prose changes after audit, rerun the audit or report the audit as stale.
- For all substantive source-backed final artifacts, keep claim origin, direct facts, source statements, scope boundaries, execution or outcome evidence, context or motive evidence, interpretation, counter/limiting evidence, and forecast triggers separate in the reasoning plan. These categories are coverage obligations, not mandatory visible headings. Context or interpretation can support plausibility, not execution, causality, outcome, or broader scope.
- Negative or partial findings should name the missing evidence roles or concrete signals checked when execution, outcome, scope, causality, stakeholder position, or future trigger is material.
- Final artifact audits must check artifact units, not only the whole document: unsupported important claims, missing inline markers, undefined or duplicate source markers, official or actor claims written as independent facts, inference written as fact, missing counter/limitation, source-role mismatch, execution or outcome claims citing only announcement/context sources, section or page jumps, target genre mismatch, diagnostic-dump style, and internal workflow terms leaking into reader-facing copy.
- A structurally valid citation marker is not enough. LogicGuard must still ask whether the cited source can support the exact wording, scope, tense, causality, execution, outcome, price layer, source role, independence, or forecast claim in the artifact unit.
- For papers and theses with footnotes, treat footnotes as claim-support
  surfaces, not decoration. Each important footnote or inline marker should
  resolve to a source role, support boundary, and verification status such as
  `verified_source_support`, `downgraded_without_source`,
  `uncited_framing`, `ambiguous_marker`, or
  `human_source_review_required`.
- When an upstream investigation provides a source portfolio, key-claim/key-number ledger, or semantic-fit ledger, reconcile it with the claim-to-source matrix before final delivery. Treat material numbers without source date/coverage period, forecast/model/announcement status, or allowed wording as under-supported until repaired or downgraded.
- For central conclusions, audit whether the preferred conclusion faced steelman opposition, material alternatives, relevant model lenses, expert stance boundaries, and robustness tests. Missing tournament work means the conclusion is under-modeled or must stay qualified.

For non-trivial LogicGuard work, default to showing one compact Mermaid diagram, table, or viewer graph in the conversation once the relevant model path is stable enough to explain. Before drawing, run a LogicGuard diagram intent gate: decide what relationship is being explained, then let AI choose the most explanatory diagram or table from the LogicGuard toolbox. This is not a rigid route-to-chart mapping. The chosen output must make node roles and edge meanings clear when they are not obvious; do not collapse claim/evidence/method/result/limitation, section order, source reuse, and synthesis into one generic flowchart.

LogicGuard diagram modes:

- Argument support: Claim, Conclusion, Evidence, Warrant, Assumption, Rebuttal, Qualifier, Limitation, and Scope; edges mean supports, explains, qualifies, attacks, undercuts, or bounds.
- Research process: Problem/Context, Design, Method, Experiment/Test, Result, Conclusion, and Future Work; edges mean produces, measures, derives, or constrains.
- Document structure: Document, Section, ArgumentBlock, Paragraph, Slide, Figure, or Table; edges mean contains, precedes, hands off, duplicates, or overloads.
- Source path: Source, source node, anchor, project branch, project claim, and missing deepening; edges mean selected from, anchored at, expands, reused by, or cites.
- Synthesis route: selected material, missing bridge, target outline block, delivery profile, appendix, and omission; edges mean contributes to, needs bridge, moves to appendix, or is omitted.
- Gap or diagnostic table: claim, issue type, missing support, affected scope, and next repair route; rows mean actionable weaknesses, not proof steps.
- Comparison matrix: sources, claims, evidence strength, baseline, scope, and limitations; cells compare boundaries, not chronological order.
- Viewer graph: the UI-visible graph selected by AI-authored source semantics or the semantic router. The viewer renders the single recommended graph directly and must not expose graph-mode tabs. Layout must not imply chronological flow unless the selected mode is research process.

Use diagrams during progress updates as well as final explanations for model changes, before/after logic, source reuse or deepening paths, structure changes, and synthesis routes. Keep diagrams informative but selective: show the relevant path and nearby context, not the full internal graph. In chat, AI may use two small diagrams when one diagram would mix edge meanings. In the project viewer, show only the recommended graph. Skip diagrams for tiny edits, grammar-only work, simple low-stakes answers, user-suppressed diagrams, or final artifact copy where model-audit internals do not belong.

Use internal routes when the route is clear. Use the main LogicGuard skill as the router when the request is explicit, mixed, or ambiguous. Do not create separate Codex skills for every CLI helper or for cross-cutting `importance`; keep helper APIs and importance inside the owning workflow.

## Routing

Use this skill when the user asks to:

- write, review, or strengthen a large report, paper, technical report, literature review, policy memo, research argument, or audit-style response;
- preserve, remember, reuse, or reason over concrete source materials such as files, long pasted text, text files, URLs, papers, reports, books, or web snapshots;
- create or maintain their own argument model for a paper, book, report, or claim chain;
- import references, papers, books, reports, or web snapshots into a reusable source logic library;
- reuse an already imported source across projects, deduplicate source files, search source logic nodes, or deepen a source under an existing source node or block;
- inspect a LogicGuard source library visually by project, source card, source type, modeling status, or top-level logic graph;
- connect a project argument node to a source claim, evidence, warrant, limitation, rebuttal, or method node;
- review the logic structure of a presentation, paper, report, deck storyline, or any naturally structured artifact;
- identify which claims, evidence, limitations, bridges, source links, slides, sections, or paragraphs are most important to the current goal;
- recursively deepen an existing model, split high-importance nodes, expand by importance, or decide which under-modeled node should grow next;
- generate a new target outline, deck storyline, paper structure, report flow, or synthesis plan from existing modeled material and sources;
- check whether claims follow from evidence, assumptions, warrants, limitations, and rebuttals;
- find missing warrants, hidden assumptions, overclaiming, scope mismatch, circular reasoning, unanswered rebuttals, causal overclaiming, or fragile conclusions;
- find structure-flow issues such as missing handoff, late limitation, overloaded block, orphan block, or duplicate claim;
- simulate what happens if evidence weakens, assumptions flip, rebuttals activate, or a root claim loses support;
- turn diagnostics, importance, evaluation state, and simulation evidence into a gap ledger that routes missing work back through existing source-library, structured-artifact, artifact-synthesis, or argument-repair workflows;
- generate model-grounded outlines, section plans, paragraph blueprints, review reports, cautious rewrite suggestions, or claim-source-paragraph matrix audits.

Skip for casual copy edits, pure formatting, short low-stakes prose, or requests that only need grammar/style polishing.

## Workflow

Default source intake runs first when the request includes concrete materials:

1. Identify concrete materials: local file paths, long pasted text, text files, URL snapshots, or source-like model files. Do not store short command-only text as a source.
2. Preserve the material in the source library before deeper reasoning. Use `logicguard intake` or `logicguard library intake` so files/text/URLs go through the same storage and deduplication path.
3. If the user supplies an explicit project id/topic, attach the source to that project. If project context is missing or uncertain, leave the source uncategorized rather than guessing.
4. Create or reuse a shallow source model immediately after preservation.
5. Extract clearly labeled claim, evidence, warrant, method, result, scope, limitation, or rebuttal text when available. Treat extraction as best-effort; partial or failed extraction must not undo source preservation.
6. Report a concise status: saved/reused, project or uncategorized, modeled/partial/error.
7. Continue with the user's requested LogicGuard analysis using the preserved source where relevant.

For ordinary argument modeling:

1. Identify the reasoning target: root claim, section claims, evidence, warrants, assumptions, rebuttals, qualifiers, limitations, and scope.
2. If a LogicGuard YAML/JSON model already exists, validate it first.
3. If no model exists, create the smallest useful model for low-stakes work, but for non-trivial work apply the Model Mesh Default Contract and Deep Modeling Contract before drafting or judging the argument.
4. Prefer explicit `Claim`, `Evidence`, `Warrant`, `Assumption`, `Rebuttal`, `Undercutter`, `Qualifier`, `Limitation`, `Method`, and `Result` nodes.
5. Expand high-importance sections, blocks, and abstract outcome claims until their internal support path is visible or clearly recorded as a gap.
6. For non-trivial hierarchical work, keep a structural contribution graph alongside the model-card index. Record parent goal, unit job, child obligations, downstream consumers, conclusion recovery, status, and repair action for each important unit.
7. For non-trivial work, keep a model-card index and coverage summary so shallow skeletons, ordinary cards, deep cards, skipped units, and handoff gaps remain countable.
8. Run evaluation and inspect root state, confidence, blockers, trace, and cycles.
9. Run diagnostics and prioritize actionable findings over numeric scores.
10. Track importance from the start: mark core claims, key evidence, fragile bridges, dangerous limitations, and optional background.
11. Build a gap ledger when the next action is not obvious. Use it to route evidence, baseline, rebuttal, scope, confidence, fragility, and structural-contribution gaps through the owning internal routes rather than creating a new gap-routing skill.
12. For source-backed gaps, search existing source-library nodes first. If external evidence is needed, AI may search for candidate material, but completion requires source preservation, content modeling, source/project linking, and re-evaluation; do not invent facts.
13. For important conclusions, run fragility, counterexample, or bounded combination-counterexample simulation.
14. For Research Reasoning Atlas work, run or simulate a conclusion tournament for central conclusions: preferred conclusion, steelman opposition, alternatives, model-lens warrant, expert stance boundary, assumption load, scope fit, robustness, winner, and allowed wording.
15. For writing tasks, generate outline/section-plan/paragraph-blueprint only from the model structure and diagnostics; if the model is still shallow or the structural contribution graph has unresolved high-importance gaps, say the writing is under-modeled rather than final. If an upper-level writing workflow is active, return a diagnostic plan and do not claim final artifact-native prose integration yourself.
16. For source-backed writing, build the claim-to-source matrix and paragraph/section blueprint before final prose. Important claims need inline citation markers, source-role labels, and natural prose that makes clear who says the point or which evidence role supports it; use `outline --paragraph <claim> --with-citations` when the paragraph blueprint should show the matrix row.
17. Before final prose for long reports, create a reader route: first question answered, section handoffs, limitation placement, forecast boundary, structural contribution path, and appendix-only material.
18. Before claiming final source-backed prose is ready, reconcile source registry, source portfolio status when available, key-claim/key-number ledger when available, claim-to-source matrix, inline citation markers, source roles, semantic source-fit, structural contribution graph, paragraph wording, artifact-genre target, and conclusion tournament result. If the reconciliation fails, route missing evidence to source-library/SourceGuard work, weaken the claim, move it to background/appendix/hypothesis, or omit it. If a domain workflow owns final prose, report the reconciliation result to that workflow rather than closing the writing route here.
19. After a meaningful model change, usually show the AI-selected Mermaid diagram or table in the chat explanation, often a before/after, claim-support, proof-tree, tournament, structural-contribution, or gap view for added warrants, assumptions, limitations, rebuttal handling, or claim-strength changes. Use the LogicGuard diagram intent gate first so the graph's edges say support/attack/qualify/consumed-by rather than accidental chronology.
20. State the boundary in final outputs: LogicGuard audits structural support, not factual truth.

### Task-local argument iteration

Use the native task-local loop when an important argument-model change should
be driven by a prediction rather than a post-hoc explanation. This loop is
entirely owned by LogicGuard:

1. Freeze the expected claim status before running the perturbation:

   ```powershell
   researchguard logic argument-iteration freeze <baseline-model> `
     --expected-state <IN|OUT|UNDECIDED> `
     --mode <premise-removal|evidence-weakening|rebuttal-activation|assumption-flip|scope-narrowing> `
     --root <claim-id> `
     --node <perturbed-node-id> `
     --protect-claim <unaffected-important-claim-id> `
     --output <prediction.json>
   ```

2. Run the frozen perturbation through LogicGuard's existing simulator. If the
   baseline result differs from the prediction, provide one candidate model and
   explicitly request acceptance or rejection:

   ```powershell
   researchguard logic argument-iteration run <baseline-model> `
     --prediction <prediction.json> `
     --candidate <candidate-model> `
     --store-root <task-model-store> `
     --decision <accept|reject> `
     --output <iteration-receipt.json>
   ```

3. Accept only when the candidate produces the frozen expected status and every
   declared protected claim keeps its native unperturbed status. A caller
   decision to reject always preserves the baseline. A failed mandatory check
   overrides a requested acceptance.
4. Keep every accepted model as an immutable child revision. If later task
   evidence invalidates it, use `argument-iteration rollback` to append a
   compensating revision from a selected historical snapshot; never rewrite or
   move revision history backward.

The loop may revise only the current task's `LogicModel`. It must not change
LogicGuard's evaluator, simulator, thresholds, scoring, defaults, templates, or
core code. It does not call SourceGuard, TraceGuard, FlowGuard, or any other
Guard, and it does not turn one task result into a permanent rule.

For source-library work:

1. Preserve relevant sources through default intake whenever concrete material is present.
2. Define the project topic when the source should belong to a project.
3. Reuse existing source records when the same material was already imported.
4. Create or reuse a shallow source logic model first: major claims, evidence, warrants, methods, results, scope, limitations, and rebuttals when available.
5. Deepen only topic-relevant paths. Prefer anchoring each deepening branch to the source node or block it expands. A paper's main claim may be irrelevant while a detailed experiment, definition, formula, or limitation is highly relevant.
6. If a high-importance project claim depends on a shallow source model that does not expose the relevant method, result, evidence, warrant, limitation, or rebuttal, deepen that source path or report the claim as under-supported.
7. Create a project branch that references global sources instead of copying source files.
8. Use branch metadata to preserve `source_id`, `project_id`, `topic_focus`, `locator`, `anchor_node_id` or `anchor_block_id`, `branch_role`, generated node ids, branch status, and importance.
9. Link the user's argument nodes to source nodes or branch nodes with relations such as `supports`, `attacks`, `undercuts`, `qualifies`, `depends_on`, `derives`, or `contextualizes`.
10. Preserve source temporal context when available: `source_date` for source chronology and `coverage_period` for covered facts.
11. Preserve project-relative importance on important source nodes, branches, and links.
12. After meaningful source reuse or deepening, usually show the AI-selected Mermaid diagram or table. A source path often best explains how a project claim connects to a source node, source branch, anchored deepening path, and material temporal context; a research process often best explains method/result/conclusion material; a comparison matrix often best explains competing sources. Do not mix these edge meanings into a generic flowchart.
13. Use source-library packages when moving material between libraries. Prefer `export-package` for project/full/uncategorized/selected-source bundles, `inspect-package` before accepting an unknown package, and `import-package --dry-run` before a real safe merge.
14. Reuse existing source models and promoted branches across future projects; deepen additional paths only when needed.

For structured-artifact work:

1. Identify natural boundaries first: `Document -> Section -> ArgumentBlock -> local nodes`.
2. Reuse existing node types. For a deck, use `Document` for the deck, `Section` for deck sections, and `ArgumentBlock` for slides. For a paper, use `Section` for paper sections and `ArgumentBlock` for paragraphs or local subarguments.
3. For Markdown-like outlines, use `structure from-markdown` to convert headings and labeled fields into the hierarchy. Keep this narrow; it is not a generic PDF, DOCX, citation, or page-layout parser.
4. Add artifact metadata when useful: `artifact_kind`, `locator`, `order_index`, `role`, `importance`, `salience`, `source_date`, and `coverage_period`.
5. Build or inspect a structural contribution graph for high-importance units: parent goal, unit job, contribution type, child obligations, downstream consumers, conclusion recovery, structural status, and repair action.
6. For high-importance sections and blocks, model the inside of the block: local claim, support, warrant or mechanism, assumptions, rebuttal or undercutter, limitation, and handoff role.
7. Run ordinary argument diagnostics for local claim support.
8. Run structure audit for cross-block flow: missing handoff, late limitation, overloaded block, orphan block, duplicate claim, unsupported parent goal, missing downstream consumer, and unrecovered obligation.
9. If the cross-block structure looks valid but high-importance blocks are internally undecomposed or structurally unconsumed, report the artifact as under-modeled rather than fully checked.
10. After meaningful artifact structure analysis or changes, usually show the AI-selected Mermaid diagram or table. A structure diagram often best explains containment, section order, slide/page handoffs, moved limitations, merged blocks, added bridge pages, or downstream consumption. Do not use the structure diagram as evidence-support proof; choose an argument-support diagram or gap table when the question is whether a claim follows.
11. Keep internal labels in audit notes only. Do not paste labels such as `missing_handoff`, `late_limitation`, or `core_claim` into final PPT, paper, report, memo, brief, article, or other user-facing artifact copy.

For artifact synthesis:

1. Require a target goal before synthesis.
2. Select material from existing model nodes, source-library links, anchored source branches, and structured blocks using importance as a cross-cutting signal.
3. Reuse anchored source branches as provenance-preserving chunks when they fit the target goal.
4. Carry source temporal context into the story plan when available. Importance/treatment controls selection and depth; temporal context controls chronology, background/update/current-state organization, and material caveats.
5. Carry structural contribution rows into the story plan when available. A selected section or paragraph should name the parent goal it serves, the later block that consumes it, and whether the final conclusion recovers it.
6. Mark missing support, bridge, evidence, limitation, downstream consumer, or conclusion recovery as missing additions instead of inventing them.
7. Use treatment guidance on synthesis items: `deep` for material that needs prominent support/warrant/boundary treatment, `normal` for the main story, `brief` for context, `appendix` for material kept outside the main path, and `omit` for low-priority material.
8. Expand each `deep` or core synthesis item into its internal support chain before turning it into final prose. If evidence, warrant, boundary, rebuttal handling, downstream use, or conclusion recovery is missing, keep it as a missing addition.
9. For central conclusion items, include conclusion tournament status before final prose: preferred conclusion, steelman opposition, live alternatives, winner, and allowed wording.
10. Produce an inspectable target story plan before final artifact prose.
11. After selecting a synthesis route, usually show the AI-selected Mermaid diagram or table. A synthesis route often best explains which model nodes, source branches, structure blocks, structural contribution rows, missing additions, and material temporal clues lead to the target story. Keep source selection, missing bridge, target outline, appendix, and omitted material roles explicit.
12. Translate the plan through a delivery profile (`presentation`, `paper`, `report`, `memo`, `article`, `literature-review`, `decision-note`, or another user-requested artifact genre) so final text fits the target artifact, not a model audit or a fixed report style. Do not force timeline or risk pages; surface temporal caveats near relevant claims only when material.
13. For source-backed final prose, do a final citation consistency, semantic source-fit, hierarchical artifact-unit, structural-contribution, and conclusion-tournament pass after the last material edit. The pass must check not just marker presence, but semantic fit between source role, source scope, source time status, claim wording, effect layer, downstream use, and allowed conclusion strength.

For project-library viewer work:

1. Treat card and graph inspection as read-only. The viewer must not directly edit source text, project membership, models, or graph nodes.
2. Each UI card represents one source record, not one claim.
3. Project grouping is the primary navigation axis; all sources, recent, source type, modeling status, and uncategorized views are secondary filters.
4. Opening a source card should show the single AI/semantic-router recommended top-level logic graph as the primary detail view, with importance/risk markers directly on nodes and edges, plus temporal clues for accession time, source date, and covered period when available. Do not add graph-mode tabs; if another graph kind becomes useful later, route it into the same recommended graph surface.
5. The main header may export/import portable source-library packages for the active all, project, or uncategorized view. Import uses safe merge and conflict reporting.
6. On a project route, package import should preserve package projects and also attach imported sources to the current project.
7. On a project route, project dissolve may remove the project relationship directory, but it must not delete source files, source models, or global source records.
8. Keep the local version/status capsule visible. Do not reintroduce organization-maintenance controls into this viewer.
9. Header package actions should use the LogicGuard green-blue accent, regular-weight pill text, and built-in folder transfer icon glyphs rather than ad hoc arrow sketches.
10. Use `researchguard logic library viewer --library-root <root> --check` for a headless smoke check before opening the desktop window.

## Commands

Use the single installed ResearchGuard entrypoint:

```powershell
researchguard logic validate examples\engineering_efficiency_argument.yaml
researchguard logic evaluate examples\engineering_efficiency_argument.yaml
researchguard logic diagnose examples\engineering_efficiency_argument.yaml
researchguard logic simulate examples\engineering_efficiency_argument.yaml --mode fragility
researchguard logic simulate examples\engineering_efficiency_argument.yaml --mode combination-counterexample
researchguard logic gaps examples\engineering_efficiency_argument.yaml
researchguard logic report examples\engineering_efficiency_argument.yaml
researchguard logic outline examples\engineering_efficiency_argument.yaml
researchguard logic importance examples\structured_artifact_deck.yaml
researchguard logic structure from-markdown examples\structured_report_outline.md --artifact-kind report --output report_model.yaml
researchguard logic structure audit examples\structured_artifact_deck.yaml
researchguard logic synthesize examples\structured_artifact_deck.yaml --goal "Create a short validation briefing" --delivery
```

Default intake examples:

```powershell
researchguard logic intake .logicguard-library --file paper.txt --project ai-efficiency-paper --project-topic "AI effects on software engineering efficiency" --claim "AI tools reduce short-term maintenance task time." --evidence "Participants completed bounded tasks faster." --locator "abstract" --json
researchguard logic intake .logicguard-library --text "Claim: The source should be preserved. Evidence: The user provided source-like material."
```

Source-library examples:

```powershell
researchguard logic argument create project_argument.yaml --claim "AI tools can improve short-term software engineering efficiency."
researchguard logic library init .logicguard-library
researchguard logic library import .logicguard-library paper.pdf --title "AI Maintenance Study" --year 2026
researchguard logic library model-source .logicguard-library ai-maintenance-study-2026 --claim "AI tools reduce short-term maintenance task time." --evidence "Participants completed simple maintenance tasks faster." --locator "abstract"
researchguard logic library create-project .logicguard-library ai-efficiency-paper --topic "AI effects on software engineering efficiency"
researchguard logic library select-source .logicguard-library ai-efficiency-paper ai-maintenance-study-2026
researchguard logic library deepen-source .logicguard-library ai-maintenance-study-2026 --project ai-efficiency-paper --topic-focus "task-time evidence" --locator "section 4" --anchor-node C1 --branch-role evidence_detail --evidence "Treatment participants completed bounded tasks faster."
researchguard logic library branches .logicguard-library ai-maintenance-study-2026 --anchor-node C1
researchguard logic library audit-branches .logicguard-library ai-maintenance-study-2026
researchguard logic library search .logicguard-library "maintenance task time" --project ai-efficiency-paper
researchguard logic library view-snapshot .logicguard-library
researchguard logic library view-graph .logicguard-library ai-maintenance-study-2026
researchguard logic library export-package .logicguard-library ai-efficiency-paper.zip --project ai-efficiency-paper
researchguard logic library export-package .logicguard-library all.zip --all
researchguard logic library inspect-package ai-efficiency-paper.zip
researchguard logic library import-package .logicguard-library ai-efficiency-paper.zip --dry-run
researchguard logic library viewer --library-root .logicguard-library --check
```

The installed `researchguard logic` command is the only normal runtime path.

## Model Creation Guidance

Keep the model low-fidelity and auditable. Do not turn LogicGuard into a generic text generator. Generated outlines and rewrites must be grounded in declared model nodes and diagnostics.

For structured artifacts and synthesis, generate the story model before final copy. Final visible copy must be artifact-native and must not leak internal diagnostic labels.

Use Mermaid diagrams, tables, or viewer graphs for explanation, comparison, progress updates, or discussion. Keep them purposeful and compact; skip only when they would add no explanatory value or when final artifact-native copy should not expose internal diagnostic labels. LogicGuard owns its own diagram semantics; AI chooses the best LogicGuard diagram or table from the current relationship, and the project viewer displays only the recommended graph. LogicGuard must not require FlowGuard or a shared cross-family diagram protocol to decide graph types.

Load `references/h-wadf-quick-reference.md` when creating a new model, explaining H-WADF semantics, or choosing node/edge/acceptance-condition fields.

## Native execution-depth receipt gate

For a non-trivial model, run the native owner after the last meaningful model change:

```powershell
researchguard logic depth <model.yaml> --output <logic-depth-receipt.json>
```

For a broad claim, the native `broad` profile is mandatory. Its importance threshold is LogicGuard-owned (`0.6`); caller attempts to raise or otherwise replace that threshold block the receipt instead of shrinking the denominator. The receipt must be current for both the model fingerprint and the separately fingerprinted authoritative coverage universe derived from the current task/artifact units, model cards, requested claim nodes, and all important nodes, including important nodes disconnected from the root.

Broad coverage also reconciles every explicitly declared card and native block before depth is credited. A low caller-supplied card importance cannot remove a card: effective importance is the maximum of declared importance, member-node importance, and structural/downstream importance. An excluded card remains visible, needs a concrete reason plus a closed target-owned disposition, and cannot contribute role, perturbation, or claim-scope evidence; an excluded card whose nodes still participate in the active argument is blocking.

Card-level role presence is not enough. Every important `Claim` must have its own connected support, warrant, assumption, boundary, and opposition nodes or closed claim-local dispositions. A role node counts only through a native edge or acceptance dependency to that claim. If one role node is reused by several important claims, declare all consumers through `shared_claim_ids` (or explicit shared edge metadata); implicit sharing is a broad-depth gap. LogicGuard also derives an applicable perturbation set for each important claim and requires every applicable node to be selected, executed, and effective. Many perturbations elsewhere cannot hide one untested claim.

Do not claim that the argument is comprehensively modeled, robust, or ready for broad final wording unless the target-unit denominator is non-empty; at least one explicit target-authored model card or native block exists; every important card (and the root argument scope) has claim, support, warrant, assumption, boundary, and opposition coverage or an explicit closed target-authored disposition; the root also exposes a competing conclusion or an explicit closed competition disposition; every requested claim node is present and evaluated; no important target unit or disconnected important node is unresolved; no comparable conclusion remains unresolved; every critical perturbable node is selected and produces an effective native perturbation; no remaining important node is untested; and `broad_claim_licensed: true`. A rich aggregate cannot hide one shallow important card, and a root claim plus one or two support nodes is a shallow blocked model, not evidence of broad depth. LogicGuard has one target-owned enforcement path: callers cannot select a lighter profile or threshold. A blocked receipt is useful evidence: continue modeling or narrow the wording and name the remaining gaps. The target repository's authoritative-coverage regression calibrates these rules but never substitutes for the current task's own receipt. This command reuses LogicGuard's native evaluator and simulator.

For any non-trivial, comprehensive, robust, or otherwise broad conclusion, the current target-native LogicGuard depth receipt is the required runtime closure evidence. Local regressions, one-off spot checks, and repository health tests can support only an explicitly bounded conclusion.

A coverage count, role-name list, catalog expansion, whole-receipt hash, or ordinal range is not proof of an individual LogicGuard obligation. Every satisfied governed obligation must retain the exact target-native semantic object, `evidence_ref`, and lowercase content hash that proves it. Missing, renamed, overlapping, or summary-only mappings block broad closure even when aggregate coverage is green.

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

Packaged baseline purpose: Prevent a structurally unlicensed conclusion from being treated as warranted when its support, warrant, assumptions, boundaries, opposition, or authoritative argument universe is incomplete.

Baseline claim boundary: A pass licenses only structural support for the exact current model, target-unit/card universe, claim scope, and perturbations. It never proves factual truth or absent real-world alternatives.

The repository keeps these representative baseline failures only to prove that the native verifier can block them:

- `Support or evidence is missing`: block when an important claim lacks connected supporting evidence.
- `Warrant or mechanism is missing`: block when support is present but the inference mechanism is absent.
- `A material assumption is hidden`: block when an important claim lacks an explicit assumption or closed disposition.
- `Boundary or limitation is missing`: block when the conclusion has no explicit scope boundary or limitation.
- `Opposition or alternative is unanswered`: block when material opposition, rebuttal, or competing conclusion is absent or unresolved.
- `The authoritative argument universe is incomplete`: block when a target unit, card, important node, claim scope, or perturbation obligation is omitted.

These packaged examples are not the purpose of a real target model and cannot authorize one. Before building every real model or route result, AI must write a target-local `logicguard.target_model_purpose_declaration.v1` under the explicit target root. AI declares what this exact model is meant to prevent, its bounded claim, the exact candidate path, and one or many current failure declarations. Every current failure binds one LogicGuard-native oracle plus one target-owned known-good and known-bad case. Then AI freezes the target-local LogicGuard purpose contract while the candidate path is still absent, builds the candidate, binds it to the frozen fingerprint, exhausts every declared proof, and only then requests native closure.

Missing declarations, late declarations, stale fingerprints, non-blocking bad cases, failing good cases, or a candidate that exposes any declared failure are non-pass. There is one enforced route and no selectable mode, threshold, compatibility reader, fallback, or lighter success path. Evidence insufficiency may narrow the final claim, but it does not select a weaker check.

`researchguard logic guard-contract` is the current LogicGuard purpose-contract
interface. `researchguard logic depth` issues the target-bound native
execution-depth receipt; packaged capability cases never substitute for the
target-local proof.
<!-- END MANAGED PURPOSE AND BLOCKABILITY -->
