---
name: sourceguard
description: Plan and execute evidence/source discovery for a claim with explicit source roles, provider evidence, gaps, and bounded claim-use decisions. Use for source search plans and retrieval qualification, not argument licensing or temporal-storyline inference.
---

# SourceGuard Skill

## Purpose

SourceGuard plans and audits evidence discovery for claims and research
questions. It distinguishes source roles, retrieval evidence, provenance,
semantic gaps, and safe claim use without declaring a source true.

## Entrypoint Scope

SourceGuard owns evidence-discovery planning and source qualification. It does
not own final argument licensing or evidence-backed storyline reconstruction.

## Local Material Routing

Use the current `researchguard source` command and the target-owned references,
schemas, examples, and template catalog under this skill. No former standalone
package or launcher is part of normal execution.

## Entrypoint Acceptance Map

- claim or research question -> source-role and gap model;
- current retrieval evidence -> qualified source record;
- argument-structure need -> explicit LogicGuard handoff;
- temporal/storyline need -> explicit TraceGuard handoff;
- missing, conflicting, inaccessible, stale, or insufficient evidence ->
  visible gap or blocked result.

## Use When

Use for source discovery plans, provider/retrieval evidence, source-role gaps,
provenance, search iteration, and claim-use qualification.

## Do Not Use When

Do not use SourceGuard to assert factual truth, convert a search result into
validated evidence automatically, or silently continue through another Guard.

## Required Workflow

Declare the target claim and source roles, build the current gap/search model,
execute or inspect retrieval evidence, qualify each source for its intended
claim use, and preserve unresolved gaps and typed handoffs.

## Hard Gates

Unanchored source identity, missing provenance, unsupported status projection,
inaccessible evidence, unresolved semantic gaps, or an unqualified closure
basis blocks strong claim use. There is one current semantic-state authority.

## Output Requirements

Report source roles, evidence, failures, blockers, skipped checks, unresolved
gaps, residual risk, safe claim use, typed handoffs, and the claim boundary.

## Detailed Route Contract

Use this skill when the user needs to:
- discover new sources;
- plan evidence search;
- expand leads from known sources;
- decide what to search next;
- search across text, PDFs, reports, books, images, video, audio, maps, citations, and local/internal materials;
- preserve source candidates and evidence anchors;
- find counter/limiting evidence;
- review source-role coverage before substantive final writing;
- plan search by reasoning branch, alternative explanation, confounder, falsifier, model-lens need, or expert stance gap;
- find disconfirming, branch-distinguishing, expert-stance, and model-source material;
- identify source-lineage and false-diversity risks when many sources repeat one origin;
- build a source portfolio plan that checks high-value source classes rather than source count alone;
- trace key numbers, statistics, forecasts, tables, or model estimates back to their original or closest-available source;
- find bridge evidence when a draft moves across scope, time, effect layer, or source role;
- find evidence for a structural contribution role, such as whether a source can support background only, a method choice, a validation criterion, validation evidence, a bridge between chapters, a limitation, or conclusion recovery;
- convert post-draft citation, coverage, execution, or source-role gaps into targeted search actions;
- audit whether citation markers and footnotes have source roles, support
  boundaries, unsupported boundaries, and verification status before downstream
  thesis or paper writing treats them as usable support;
- decide whether material is ready for TraceGuard or LogicGuard.

Do not use this skill for:
- final factual proof;
- final argument audit;
- trace reconstruction after evidence is already modeled;
- process closure;
- ordinary summarization;
- fake web crawling;
- fake OCR or fake video/audio analysis.

## Core Boundary

SourceGuard is a POMDP-style approximate source discovery planner. It maintains a belief-state evidence graph, proposes search actions, scores expected utility, accepts observations, updates gaps and frontier, and exports candidate handoff bundles. Its utility score is not truth, not calibrated probability, and not final confidence.

## Mandatory purpose before model

Before building or accepting any non-trivial SourceGuard model, the AI must first author and freeze a target-local `sourceguard.model_guard_contract.v2` sidecar: what this particular model is meant to prevent, the external target-unit/source/gap/lineage/anchor universe, one or more task-specific failure declarations, each declaration's SourceGuard-native blocking oracle and good/bad proof cases, and the claim boundary. The candidate must carry the exact sidecar snapshot and fingerprint. A model may prevent one failure or several; the AI decides from the current task, not from a fixed family list.

There is one fixed route and no selectable enforcement mode:

1. freeze the task-local prevented-failure contract;
2. build the candidate against that contract;
3. prove the declared native known-good passes;
4. prove one SourceGuard-native known-bad for every declared failure is blocked;
5. only then accept the ordinary SourceGuard depth receipt and closure.

The target purpose proof is executed from that explicit sidecar on every model
load. `researchguard source depth` is the current target-owned depth interface;
family capability cases prove only native oracle behavior and never substitute
for the target model's purpose contract.

Missing, empty, stale, mismatched, unmapped, inferred, or family-baseline-substituted target contracts are hard failures. There is no compatibility reader, fallback contract, optional mode, or path inference.

## Model Gap Mesh Default

For non-trivial source-backed work, SourceGuard defaults to a model-gap coverage network, not a broad bibliography search. When LogicGuard, TraceGuard, a claim-to-source matrix, or a draft audit provides gaps, bind every important search action to a concrete gap and model unit before treating the work as coverage.

Preferred inputs are:

- LogicGuard gap ledger;
- LogicGuard model-card `source_need` rows;
- LogicGuard structural contribution rows;
- TraceGuard missing evidence chain;
- claim-to-source matrix gaps;
- user-provided source registry gaps.

For academic thesis, dissertation, paper revision, or deep research, use
`logic-writing` as the upper-level route when the task also
needs existing-document rewriting, visible revision provenance, DOCX output, or
a revision report. SourceGuard still owns source discovery planning,
candidate-source preservation, support-boundary rows, and source-gap handoff.
It does not own final thesis structure or thesis-native prose integration.
When an upper-level writing workflow is active, return source-fit findings,
source gaps, downgrade advice, and handoff notes to that workflow.

Keep a source coverage map when the task is substantive:

```text
gap_id -> model_card_id -> claim -> source_role -> search_action -> candidate_source -> can_support -> cannot_support -> status
```

For hierarchical artifacts, preserve structural context supplied by the
upstream workflow when it is useful for handoff:

```text
structure_unit_id -> parent_goal -> unit_job -> contribution_type -> structural_role_needed -> downstream_consumer -> source_role -> can_support_structural_use -> cannot_support_structural_use -> status
```

These structural values are context for source-fit review, not SourceGuard's
ownership of the final artifact structure.

For thesis, dissertation, and paper revision, also keep a citation/footnote
support matrix when a draft or source registry exists:

```text
claim_id -> artifact_locator -> claim_text -> citation_marker/footnote_id -> source_id -> source_role -> can_support -> cannot_support -> verification_status -> safe_wording -> next_action
```

Use statuses such as `verified_source_support`,
`downgraded_without_source`, `uncited_framing`, `ambiguous_marker`,
`human_source_review_required`, `access-gap`, and `source-gap`. A row with a
marker but no support boundary is not verified support.

Use statuses such as `complete`, `supported-incomplete`, `gap`, `access-gap`, `not-run`, and `downgrade-needed`. If no model gap exists yet, SourceGuard may run exploratory source planning, but it must label the output as exploration rather than downstream source coverage completion.

For thesis work, common high-value source gaps include standard or regulation
text, literature support, benchmark or method sources, project-internal
records, dataset splits, metrics, figure/table provenance, and limiting or
counter evidence. If any of these are unavailable or permission-gated, record
an access or project-material gap and recommend safe or downgraded wording
instead of filling the thesis with unsupported prose.

## Hard Gates

1. Search result is not evidence.
2. Source candidate is not evidence.
3. Evidence anchor is not event.
4. Event/trace/final claim belongs to TraceGuard/LogicGuard, not SourceGuard.
5. Utility score is not factual confidence.
6. High relevance is not proof.
7. Permission-gated source is an access gap.
8. Do not invent OCR, transcripts, visual recognition, page text, or audio content.
9. Multimodal anchor must carry locator when available.
10. One-sided support requires counter/limiting search before strong claims.
11. Weak signals such as patents, hiring, keyword hits, or source-only rows need stronger independent evidence before deployment/operation wording.
12. Candidate handoff to TraceGuard or LogicGuard must remain candidate unless downstream guard validates/models it.
13. Do not claim SourceGuard performed external search unless the available tool was actually used.
14. A source registry entry is not proof; it is a durable pointer to a source, role, locator, access status, and claim use.
15. Context, motive, expert commentary, or market concern does not replace execution, outcome, scope, or counter/limiting evidence.
16. If a final draft exposes missing source roles, undefined citations, unsupported execution claims, or bibliography-only support, route the gap back into SourceGuard or downgrade the dependent claim.
17. A preferred conclusion with no meaningful disconfirming or alternative-explanation search is not deeply sourced.
18. Multiple sources repeating one origin are not independent support unless source lineage is checked.
19. Domain-specific source tactics belong in selected lenses or examples, not in universal SourceGuard rules.
20. A broad bibliography is not a source portfolio. High-value source classes must be checked, marked missing, or explicitly downgraded.
21. A key number without original-source provenance, source date or coverage period, and observed-versus-forecast status is not ready for strong final wording.
22. Bridge claims need bridge evidence. Regional evidence does not become national evidence, wholesale/capacity evidence does not become retail evidence, and forecast/model/announcement evidence does not become observed fact without a source that supports the bridge.
23. A broad bibliography or many source candidates is not model-gap coverage unless important gaps are mapped to source roles and support boundaries.
24. A source that supports background does not automatically support a method choice, validation criterion, validation evidence, limitation, or conclusion recovery.
25. Do not claim completion from README/SKILL edits alone; run tests and CLI smoke checks.
26. A citation marker or footnote is not source verification. The exact claim
    wording still needs source role, `can_support`, `cannot_support`, and a
    verification status.
27. A source-disposition row such as "needs source", "access gap", or
    "downgrade" is not the same as verified support.
28. A locator alone never closes a semantic gap. Reliability, extraction confidence, specificity, source-role/modality target fit, and claim usability when requested must pass the declared thresholds.
29. Reject any gap record that lacks the current `semantic_state` and a complete closure basis. Historical records must be migrated directly before normal runtime.
30. Broad source-depth or gap-closure wording requires a current native SourceGuard depth receipt. Contract supervision may inspect that receipt but must not implement a second planner or semantic qualifier.
31. A broad receipt must use the complete SourceGuard-owned coverage universe. One closed gap, one qualified source, an empty required dimension, dependent sources that repeat one lineage, or missing direct/independent/counter-limiting portfolio classes remains bounded even when local semantic qualification passes.
32. Global portfolio diversity does not substitute for per-object depth. Every critical gap must separately carry direct/primary, independent, and counter/limiting coverage plus the required explicit lineage count, or broad closure is blocked.
33. A locator without extracted text or a normalized content summary is not a content-qualified anchor for broad depth.
34. Missing `lineage_id` is unknown provenance, not independent provenance; a different `source_id` must never manufacture independence.
35. Broad source work requires a non-empty source-required target-unit inventory. Units without mapped, closed gaps remain explicit coverage gaps and stale the universe fingerprint.
36. The target-unit denominator cannot be whichever units the current model happens to list as required. Reconcile `target_unit_inventory_ids` against every baseline gap `structure_unit_id`; every inventory member must be exactly required or explicitly excluded with a non-empty non-contribution reason, and an excluded unit with an active gap blocks broad closure.

## Workflow

1. Identify the user's research target and desired claim strength.
2. Build or load a SourceGuard belief state.
3. Identify leads, Research Reasoning Atlas branch ids, current source candidates, source registry ids when present, evidence anchors, gaps, contradictions, modalities, and source policies.
4. If a model-gap source ledger exists, convert it into the source coverage map before broad search. Preserve `gap_id`, `model_card_id`, `structure_unit_id`, parent goal, unit job, contribution type, downstream consumer, claim, source role, required claim strength, locator needs, citation marker or footnote id when available, unsafe wording, and safe interim wording when available.
   Treat structure fields as upstream context. SourceGuard should not create a
   thesis-wide structure schema or decide final prose placement.
5. Build or inspect a source portfolio plan for substantive investigations:
   - primary or closest-available records;
   - official, regulatory, or institutional records when relevant;
   - implementation, operating, execution, outcome, or market-result records;
   - independent or third-party records;
   - expert, model, method, benchmark, or analytical-lens sources;
   - affected-stakeholder sources;
   - counter, limiting, non-occurrence, delay, or cancellation sources;
   - source-lineage and independence checks;
   - future-trigger or falsifier sources.
6. Identify key numbers, statistics, forecasts, model estimates, and central claims that need provenance, source date or coverage period, source role, and support boundary.
7. Generate search actions from gaps and leads. Use search tactics appropriate to the evidence role:
   - `original-source`: primary or closest-available records.
   - `specific-site`: known domains, publishers, repositories, or archives.
   - `source-lineage`: earliest origin of a claim, quote, rumor, or statistic.
   - `numeric-provenance`: original table/report/dataset or closest-available source for a material number, forecast, scenario, or model estimate.
   - `independent-source`: third-party or non-dependent corroboration.
   - `counter-limiting`: evidence that contradicts, narrows, or weakens a claim.
   - `execution-outcome`: implementation, operation, rollout, result, or impact evidence.
   - `freshness`: newer records, version changes, updates, or current-state checks.
   - `stakeholder`: affected actors, implementers, critics, users, regulators, or opponents.
   - `absence-signal`: records that should exist if a claim were established, with coverage recorded.
   - `multimodal-anchor`: image, chart, PDF page, table row, map, video timestamp, audio segment, or other locator needs.
   - `branch-distinguishing`: evidence that separates live explanations or branches.
   - `disconfirming-source`: evidence likely to weaken or falsify the preferred branch.
   - `expert-stance-source`: expert or institutional stance sources, typed by role.
   - `model-source`: sources that define, justify, or limit an analytical lens.
   - `bridge-evidence`: evidence that licenses a move across scope, time, effect layer, source role, or claim strength.
8. Score actions by expected utility.
9. Recommend next actions with reasons.
10. If search tools are available and permitted, execute selected search actions externally; otherwise return a search plan.
11. Save observations as sources and evidence anchors. For important source-reading observations, record source id, Atlas branch id or debate row, gap id, model-card id, and structure-unit id when known; artifact locator; citation marker or footnote id when known; what the source says; what it can support; what it cannot support; source class; source role; structural role supported; structural role not supported; source date/freshness; coverage period; locator; contradiction or limitation; source-lineage clue; independence status; key numbers anchored; scope/effect layer supported; new lead; claim use; verification status; and handoff readiness.
12. Update belief state through the staged semantic lifecycle: `discovered`, `observed`, `qualified`, `claim_usable`, `contradicted`, `blocked`, or `closed`. Persist only the current `semantic_state`, and close only with a basis that records anchors, sources, observations, thresholds, target match, and claim-use decision. After a supplied observation, run the native cloned-baseline depth route and inspect its before/after replan comparison. If no observation or provider is available, keep `NOT_RUN` or `PROVIDER_UNAVAILABLE` visible and claim planning depth only.
13. Review source-role coverage for substantive artifacts:
    - claim origin;
    - direct or original facts;
    - source statements;
    - scope boundaries;
    - execution or outcome evidence;
    - counter or limiting evidence;
    - future trigger conditions.
14. For each important role, mark `complete`, `supported-incomplete`, `gap`, `access-gap`, `not-applicable`, `not-run`, or `downgrade-needed`, then recommend either a targeted search, an access-gap note, or a claim downgrade.
15. Review source portfolio coverage: required source classes checked, missing high-value classes, source-lineage risk, independence risk, key-number provenance gaps, and bridge-evidence gaps.
16. Review Atlas coverage:
    - support branches searched;
    - opposing branches searched;
    - alternative explanations searched;
    - disconfirming sources searched;
    - branch-distinguishing evidence searched;
    - expert/model source gaps reviewed;
    - source-lineage independence checked.
17. When a draft already exists, inspect unresolved source gaps at artifact-unit level: missing inline source support, unresolved footnote, ambiguous marker, source-role mismatch, source-scope mismatch, forecast/model evidence written as observed fact, announcement written as execution, wholesale/capacity/planning evidence written as retail or terminal impact, inaccessible sources used as support, limiting evidence missing from the paragraph it narrows, or preferred conclusions without meaningful opposition search.
    For thesis drafts, keep the artifact locator precise enough for later DOCX
    editing: chapter, section, subsection, paragraph block, figure/table, or
    heading. Return candidate sources with `can_support`, `cannot_support`,
    locator, source role, citation marker or footnote id when present,
    verification status, and suggested safe wording for the exact thesis claim.
18. For structural contribution gaps, classify whether candidate sources can support the intended structural use. Record `can_support_structural_use` and `cannot_support_structural_use`; if a source only supports background, downgrade or route the method/validation/conclusion use back to search.
    Return this classification to the owning structure or writing workflow for
    final treatment decisions.
19. Replan until enough candidate material exists, key gaps are blocked, or claim strength must be downgraded.
20. Export TraceGuard seed when event/trace reconstruction, competing-storyline review, causal-chain review, effect-chain review, or counterfactual trace review is needed. Include source id, evidence anchor locator, event or process anchor, evidence role, source date or coverage period when available, structural source gap rows when relevant, and candidate status.
21. Export LogicGuard source candidates when final claim support modeling, semantic source-fit review, hierarchical artifact modeling, structural contribution review, citation/footnote verification, or conclusion-tournament audit is needed. Include source id, gap id, model-card id, structure-unit id, parent goal, contribution type, downstream consumer, artifact locator, citation marker or footnote id, supported claim fragment, unsupported claim fragment, source role, structural role supported, structural role not supported, verification status, limitation, suggested claim strength, source registry ids, source portfolio status, key-claim ledger entries, branch ids, model-lens ids, or a source-id map when available.
22. Use FlowGuard for multi-stage closure when the investigation is non-trivial.

### Task-local search iteration

Use the native task-local loop when the current belief model should predict
what one selected search will produce before its observation is available:

1. Freeze the selected action's expected target-gap reduction, independent
   lineage result, counterevidence result, cost, and any protected gaps:

   ```powershell
   researchguard source search-iteration freeze <baseline.yaml> `
     --model-contract <baseline.contract.json> `
     --action-id <action-id> `
     --expected-gap-reduction <none|partial|closed> `
     --expected-independent-lineage <true|false> `
     --expected-counterevidence <true|false> `
     --expected-cost <0..1> `
     --protect-gap <unaffected-gap-id> `
     --output <prediction.json>
   ```

2. After a real observation is available, create candidate v2 through the
   existing cloned-baseline observation update and replan path:

   ```powershell
   researchguard source search-iteration run <baseline.yaml> `
     --model-contract <baseline.contract.json> `
     --prediction <prediction.json> `
     --observation <observation.yaml> `
     --actual-cost <0..1> `
     --decision <accept|reject> `
     --candidate-output <candidate-v2.yaml> `
     --candidate-model-contract-output <candidate-v2.contract.json> `
     --receipt-output <iteration-receipt.json>
   ```

3. Keep prediction error separate from observation validity. A valid
   counterexample or lower-than-expected gap reduction may still produce a
   useful candidate. Acceptance requires an explicit caller decision, an
   unchanged utility-weight vector, current model-contract bindings, an exact
   current native-depth receipt for the baseline, candidate, and supplied
   observation with a scope-appropriate result, and no change to declared
   protected gaps.
4. Never overwrite the baseline, prediction, observation, candidate, contract,
   or receipt. To undo an accepted candidate, use
   `search-iteration rollback` to write a new baseline-equivalent projection
   and rollback receipt.

This loop may revise only the current task's belief state, observations, gaps,
leads, and action ordering. It must not tune SourceGuard's global utility
weights, qualification thresholds, scoring, defaults, templates, or core
code. It does not call LogicGuard, TraceGuard, FlowGuard, or any other Guard,
and it does not promote one task's outcome into a permanent search rule.

## Commands

```powershell
researchguard source create --model-contract <model.contract.json> --output starter_sourceguard.yaml
researchguard source validate <model.yaml> --model-contract <model.contract.json> --pretty
researchguard source plan <model.yaml> --model-contract <model.contract.json> --limit 5 --pretty
researchguard source score-actions <model.yaml> --model-contract <model.contract.json> --pretty
researchguard source frontier <model.yaml> --model-contract <model.contract.json> --pretty
researchguard source depth <model.yaml> --model-contract <model.contract.json> --pretty
researchguard source depth <model.yaml> --model-contract <model.contract.json> --observation observation.yaml --output source-depth-receipt.json --updated-model-output updated.yaml --updated-model-contract-output updated.contract.json --pretty
researchguard source add-observation <model.yaml> --model-contract <model.contract.json> --observation observation.yaml --output updated.yaml --output-model-contract updated.contract.json --pretty
researchguard source search-iteration freeze <model.yaml> --model-contract <model.contract.json> --action-id <action-id> --expected-gap-reduction <none|partial|closed> --expected-independent-lineage <true|false> --expected-counterevidence <true|false> --expected-cost <0..1> --output prediction.json
researchguard source search-iteration run <model.yaml> --model-contract <model.contract.json> --prediction prediction.json --observation observation.yaml --actual-cost <0..1> --decision <accept|reject> --candidate-output candidate-v2.yaml --candidate-model-contract-output candidate-v2.contract.json --receipt-output iteration-receipt.json
researchguard source search-iteration rollback <baseline.yaml> --model-contract <baseline.contract.json> --accepted-receipt iteration-receipt.json --output restored.yaml --output-model-contract restored.contract.json --receipt-output rollback-receipt.json
researchguard source report <model.yaml> --model-contract <model.contract.json> --format markdown
researchguard source export-traceguard <model.yaml> --model-contract <model.contract.json> --output traceguard_seed.yaml
researchguard source export-logicguard <model.yaml> --model-contract <model.contract.json> --output logicguard_source_candidates.yaml
researchguard source simulate --mode fuel-cell-project --pretty
researchguard source simulate --mode gap-closure --model <model.yaml> --model-contract <model.contract.json> --pretty
researchguard source compare <before.yaml> <after.yaml> --before-model-contract <before.contract.json> --after-model-contract <after.contract.json> --pretty
```

## Native semantic-depth receipt gate

Run `researchguard source depth <model.yaml> --model-contract <model.contract.json> --pretty` when only planning was possible; the receipt must remain `planning_only` with observation depth not run. After an actual observation is supplied, run the same native route with `--observation`. Do not claim broad gap closure unless the current receipt is bound to the current model/result and coverage-universe fingerprints, records the observation and gap transitions, compares the plan before and after on a cloned baseline, carries complete closure bases, reconciles declared/discovered/required/excluded target units with reasoned exclusions and no excluded active gap, covers every source-required target unit, every critical gap and important branch, satisfies the target-owned source-role and global portfolio floors, satisfies per-gap portfolio and explicit-lineage rows, uses content-bearing anchors, closes bridge/provenance needs, leaves no unresolved or critical-uncovered item, reports `adequacy_status: pass`, matches requested and covered claim scope, and reports `broad_claim_licensed: true`. A one-gap/one-source success, a silently omitted or unclassified target unit, an exclusion without disposition, global-only portfolio, missing lineage, locator-only anchor, empty required universe, `bounded`, `planning_only`, `NOT_RUN`, or `PROVIDER_UNAVAILABLE` result must stay visible in the final wording. SourceGuard's own planner, update owner, checks, and current receipts decide all of those facts.

## Fixed SourceGuard check chain

For a non-trivial SourceGuard run that requests broad, complete, deep, or final gap-closure wording, declare the exact target request, model contract, model, proof case, and observation paths. Run the target-owned stages in their fixed order—`family_baseline_regression`, `model_purpose_proof`, `claim_or_source_intake`, `evidence_model`, `gap_review`, then `closure`—and require every SourceGuard-declared check to produce one current terminal-success result before broad closure. The family baseline only proves oracle capability. The target proof binds this model's AI-authored failures. SourceGuard derives its universe, object ids, object classes, portfolio/lineage/content strata, covered scope, and exact per-obligation semantic locators from immutable current native receipt content. A manifest declaration, caller-authored count, old receipt, missing input, or one rich gap beside another shallow critical gap cannot satisfy a SourceGuard-native check.

A source count, portfolio-class list, catalog expansion, whole-receipt hash, or ordinal range is not proof of an individual SourceGuard obligation. Every satisfied governed gap, portfolio role, lineage slot, content anchor, and target-unit binding must retain its exact target-native semantic object, `evidence_ref`, and lowercase content hash. Missing, renamed, overlapping, mechanically generated, or summary-only mappings block broad closure.

If a quick local check does not run the fixed target-owned chain, label its result `bounded` or `planning_only`; never promote it to broad closure.

If the installed `sourceguard` console script is on `PATH`, the shorter `sourceguard ...` form is also acceptable.

For non-trivial SourceGuard work, also run the closure helper when available:

```powershell
python scripts/sourceguard_closure_check.py --ledger <sourceguard-closure-ledger.json> --model <model.yaml> --json
```

The ledger should record `source_role_coverage`, `source_portfolio`,
`key_number_provenance`, `bridge_evidence_status`,
`citation_footnote_matrix`, candidate handoff status, safe wording, unsafe
wording, stale evidence, and skipped checks. If the helper
returns `partial`, `blocked`, or `downgraded`, continue with targeted source
search, access-gap handling, bridge-evidence search, downstream handoff, or
claim downgrade. Do not treat a source candidate, utility score, search hit, or
export bundle as final evidence while the closure report has open rows.

## Safe Output

Say:
- "SourceGuard recommends these next search actions because they are expected to close specific gaps."
- "This source is a candidate, not validated evidence."
- "This source can support X but cannot support Y."
- "This source role is still a gap, so the claim should be searched further or downgraded."
- "This citation or footnote row is not verified until the source role and
  support boundary match the exact claim wording."
- "This source coverage row is tied to gap <id> and model card <id>."
- "This source can support background for structure unit <id>, but not the method-choice or conclusion-recovery role."
- "This structural source note is handoff context; the upper-level writing workflow still owns final thesis placement and prose."
- "This search was exploratory because no model-card gap existed yet."
- "This branch still lacks disconfirming or branch-distinguishing evidence."
- "These sources appear to repeat one origin, so they should not be treated as fully independent yet."
- "This key number still needs original-source provenance, date or coverage period, and observed-versus-forecast status."
- "This draft claim needs bridge evidence because it moves from one scope, time status, source role, or effect layer to another."
- "The available sources show an announcement, but SourceGuard still needs execution or outcome evidence for stronger wording."
- "This model or expert source can guide interpretation, but it is not direct evidence unless it provides direct support."
- "This anchor needs downstream TraceGuard/LogicGuard review."
- "This utility score ranks search value, not factual truth."
- "This permission-gated source is an access gap."

Avoid:
- "The source proves the claim."
- "The search result validates the trace."
- "The image/video/audio shows X" unless actual extracted content is provided.
- "SourceGuard confirmed the final conclusion."
- "High score means true."
- "The title/snippet is relevant, so the source is ready for final claims."
- "The bibliography contains a source, so the paragraph is supported."
- "The footnote exists, so the claim is supported."
- "The source supports the topic, so it supports the section's role in the thesis."
- "SourceGuard decided how the thesis section should be written."
- "Many sources mention the branch, so the branch is independently supported."
- "A selected model lens proves the conclusion."
- "A regional, planning, wholesale, capacity, forecast, or announcement source is enough for national, retail, outcome, or observed-fact wording."

<!-- BEGIN MANAGED VALIDATED TEMPLATE PACK -->
## Validated Template Pack Routing

- Target families: `sourceguard`; native owner: `sourceguard.template_packs`.
- Current catalogs: `sourceguard.template-pack.catalog` revision `1.0.0`.
- Resolve the task through this Guard's native router first, then ask the target-owned adapter for a current neutral projection; never infer a template from wording or a skill name.
- Preserve the adapter's complete candidate and rejection accounting. Zero candidates may use only the declared validated base; one candidate gets a read-only preview; many candidates require complete dependencies, pairwise compatibility, one field owner, and target-authored dominance or must block as ambiguous.
- Recompute the projection immediately before applying a preview. A stale request, catalog, route, builder, validator, or content identity blocks all writes.
- Hand the selected preview to the target-declared builder and consume every target-native validator receipt. Template structure is not domain validity, completion, installation, release, or publication evidence.
- Record a harvest disposition after creating or materially deepening a reusable model, and keep no-match evidence visible.
- Declared validated bases: `discovery`.
- Template inventory: `bridge-evidence`, `citation`, `disconfirming`, `discovery`, `gap`, `lineage`, `multimodal-anchor`, `numeric-provenance`.
- Native validator inventory: `sourceguard.template_packs.validate_native_payload`.
- Claim boundaries: SourceGuard template instances plan source discovery only; source candidates are not evidence, anchors are not events, and handoffs are not downstream validation.
<!-- END MANAGED VALIDATED TEMPLATE PACK -->
