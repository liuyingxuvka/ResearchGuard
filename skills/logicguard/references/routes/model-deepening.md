# Internal LogicGuard route: model-deepening

This is an internal LogicGuard route for growing an existing model. Use it when a model, outline, report structure, paper plan, deck flow, or public-facing project page is already present but too coarse.

The job is not to write more prose. The job is to decide which model nodes should grow next, split them into more precise child nodes, mark missing support honestly, and route follow-up work to existing LogicGuard skills.
If an upper-level writing workflow is active, this skill deepens the model and
returns missing-support or repair needs to that workflow. It does not add
domain-specific final-prose gates or claim final artifact-native copy.

Use the LogicGuard CLI entrypoint when executable checks are needed:

```powershell
researchguard logic <args>
```

## Workflow

1. Identify the current model, target artifact, target reader, and expansion goal. If there is no model yet, return to the general LogicGuard route or `route:structured-artifact` to build one first.
2. Validate or inspect the model when a YAML/JSON model is available. If only prose is available, map the relevant artifact boundaries first: `Document -> Section -> ArgumentBlock -> local nodes`.
3. Build a model-card coverage view before selecting individual nodes when the artifact is non-trivial. Record target units, existing model cards, deep cards, shallow cards, skeleton cards, skipped units, and skipped reasons.
4. Build a deepening queue. Rank candidate nodes by:
   - importance to the root claim or target artifact;
   - under-modeled state, especially high-importance sections or blocks that are still leaves;
   - structural contribution risk: missing parent goal, missing unit job, missing child obligation, missing downstream consumer, missing same-level progression, orphan block, or unrecovered conclusion obligation;
   - missing evidence, warrant, boundary, or rebuttal handling;
   - likely reader objection or trust gap;
   - usefulness for the user's requested artifact depth, length, or decision.
5. Iterate by bounded rounds, not by one shallow pass. After each round, recompute which high-importance cards are still under-modeled. Continue until high-importance cards expose their support path, remaining gaps are routed, or a stopping reason is recorded.
   For thesis, dissertation, or paper revision requests that explicitly ask for
   all large, medium, and small logic weaknesses to be handled, treat the queue
   as exhaustive for the selected scope: every high-priority or
   material-boundary card must receive child roles plus a terminal state, not
   merely a transition sentence or a sampled repair. A high-priority card that
   is locally coherent but has no downstream consumer is still a structural
   deepening candidate or an omit/appendix/background decision.
6. Select a bounded batch of nodes to deepen. Prefer the smallest batch that can materially improve the argument while still satisfying the requested model depth.
7. For each selected node, split it into the relevant child nodes. Typical child roles are:
   - problem or need;
   - failed baseline or current gap;
   - mechanism or warrant;
   - evidence, method, result, or source support;
   - assumption;
   - limitation, qualifier, or scope boundary;
   - rebuttal or undercutter;
   - reader or user value;
   - example, application, appendix item, or background context.
   For literature reviews and technology summaries, useful child roles also
   include previous item, limitation exposed, scope change, contrast,
   downstream method/gap use, and final treatment. For method sections, useful
   child roles include design need, selected choice, rejected alternative,
   rejection reason, implementation consequence, validation consequence, and
   limitation. A method block that only says what was done is still shallow.
   For source-backed reports or papers, high-importance nodes should also
   expose the source roles needed later: event fact, official claim,
   independent report, limiting/counter evidence, expert analysis, historical
   background, or hypothesis/inference. Do not treat a node as adequately deep
   if it has only supportive material and no recorded counter, limiting, or
   missing-evidence branch.
   For Research Reasoning Atlas work, high-importance nodes should also expose
   the roles needed for a conclusion tournament: preferred conclusion,
   steelman opposition, alternative explanation, selected model-lens warrant,
   expert stance boundary, robustness test, falsifier, or future trigger.
   These are generic reasoning roles; topic-specific details belong in the
   selected lens or example, not in this core skill.
8. Re-estimate child importance from their role in the argument. Do not mechanically force every child score to be lower than the parent. A child mechanism, evidence item, or rebuttal may become the highest-value item to deepen next.
9. Mark missing support as gaps. Do not fill missing evidence, warrants, boundaries, or source-backed details with confident prose.
10. Mark missing structural contribution as gaps too. If a node cannot serve a parent goal, progress from sibling units, feed a later unit, or return in the conclusion, choose an explicit treatment: add bridge, rewrite parent/children together, reduce, move, move appendix, omit, source search, trace review, or human review.
11. Record stopping reasons for nodes that should not be split further: low deepening value, already adequate local support chain and structural contribution, missing source material, user-requested lightweight scope, budget limit, artifact focus risk, or diminishing returns.
12. If the user asked for a deep project, do not stop after a single selected batch unless the coverage view shows high-importance cards are no longer under-modeled or structurally unconsumed.
    If the remaining high-importance cards depend on missing standards,
    project-internal records, datasets, final metrics, or figure/table
    provenance, record those as terminal source or project-material gaps and
    safe wording rather than pretending the model is fully evidenced.
13. Recommend the next route:
   - `route:source-library` for source search, intake, anchored deepening, or source-node linking;
   - `route:structured-artifact` for section, paragraph, slide, page, or block placement;
   - `route:artifact-synthesis` when the expanded model is ready for a target story plan, outline, section plan, paragraph blueprint, or delivery guidance;
   - `logicguard` for mixed or ambiguous follow-up modeling.
14. For non-trivial deepening, show a compact AI-selected Mermaid diagram or table of the selected node, proposed children, structural contribution rows, gaps, and next route. A why/proof tree is often clearest for child support, a contribution graph is often clearest for downstream use, and a gap table is often clearest for missing evidence, warrant, boundary, or rebuttal work. Keep it as explanation; it is not validation evidence.
15. After each deepening round, update the main LogicGuard closure ledger with
    remaining high-importance leaf nodes, open gaps, skipped cards, terminal
    classifications, and next-route recommendations. A deepening round is not
    complete while high-importance cards remain unexpanded without a terminal
    treatment such as source gap, trace gap, appendix, omit, downgrade, or
    human review.

## Output Contract

Return a model-first result, not final article copy:

- target and scope;
- model-card coverage before and after the deepening round;
- structural contribution status before and after the round: parent goal, unit job, downstream consumer, conclusion recovery, and repair action for selected high-importance units;
- same-level progression status for selected literature, technology-summary,
  method, result, or validation units when neighboring units should build on
  each other;
- selected nodes and why they were selected;
- proposed child nodes with roles and rough importance;
- method-depth status for selected method blocks: design need, choice,
  alternative, rejection reason, implementation consequence, validation
  consequence, and limitation;
- gaps or missing additions;
- for source-backed artifacts, source-role needs and citation-marker readiness;
- for Atlas-backed research, conclusion-tournament readiness: preferred
  conclusion, strongest opposition, material alternatives, lens warrants,
  expert boundaries, robustness tests, and unresolved falsifiers;
- stopping reasons;
- next-route recommendations;
- any checks run or explicitly not run.

For thesis/paper deepening, also return the planned revision treatment for
each selected node: add bridge, add new prose, rewrite original wording,
rename heading, rewrite parent and child together, move existing material,
move appendix, omit/delete, source search, trace review, or human review. This
keeps model deepening connected to visible document edits.

If the user asks for prose too, first deliver or inspect the deepened model plan. Then hand off to `route:artifact-synthesis` or the relevant route for final copy.
For thesis, paper, or deep-research writing and revision under `logic-writing`,
hand the deepened plan back to that workflow for contribution-and-expression
integration.

## Boundaries

- Do not create a README-, paper-, report-, or deck-specific route. This skill is generic model deepening.
- Do not replace `route:source-library`; source-backed gaps need preserved and modeled sources.
- Do not replace `route:structured-artifact`; structure placement and flow still belong there.
- Do not replace `route:artifact-synthesis`; final artifact-native story plans and prose belong there.
- Do not replace an active upper-level writing workflow; final thesis/paper
  expression integration belongs there.
- Do not treat raw importance as a separate standalone skill. Importance remains a cross-cutting LogicGuard property used inside this route.
- Do not invent facts to satisfy a deepening plan.

## Example Shape

```text
Selected node: C_prompt_isolation
Why selected: high importance, abstract mechanism, likely reader objection.
Children:
  P1 problem: long AI runs mix planning, execution, review, approval, and continuation prompts.
  B1 failed baseline: one shared chat context lets roles inherit unrelated instructions and self-justifications.
  M1 mechanism: role-scoped cards, sealed packet bodies, typed envelopes, and narrow acknowledgements.
  E1 evidence gap: point to protocol docs, packet examples, route ledgers, or tests.
  W1 warrant: separating role inputs and outputs reduces authority collapse.
  Q1 boundary: process isolation does not prove factual truth.
  R1 rebuttal: system cards are still prompts, so why trust them?
Next route: source-library for evidence, then artifact-synthesis for final paragraph blueprint.
```

## Native execution-depth receipt gate

After the final meaningful deepening round, run `researchguard logic depth <model.yaml> --output <logic-depth-receipt.json>`. Broad depth or readiness claims require the LogicGuard-owned threshold, current model and authoritative-universe fingerprints, a non-empty target-unit denominator, every explicit target-authored card/native block reconciled regardless of caller-declared importance, only closed non-contributing card exclusions, complete requested claim scope, every important card's required roles or closed dispositions, every important claim's own connected support/warrant/assumption/boundary/opposition universe, explicit declarations for role nodes shared across claims, explicit competing-conclusion consideration at the root, no unresolved important target unit or disconnected important node, no unresolved comparable conclusion, every critical perturbable node and every claim-local applicable perturbation selected and effectively perturbed, no untested important node, and `broad_claim_licensed: true`. A rich aggregate cannot hide a claim-plus-evidence critical card, and a small top-level graph cannot pass by perturbing only one convenient node. LogicGuard exposes one enforced depth route; callers cannot select a lighter profile or threshold. If the receipt is blocked, continue deepening or report the work as partial with its named gaps. The target-owned shallow-negative regression calibrates this gate but does not replace a current per-run receipt. The command reuses LogicGuard's native evaluator/simulator.

Then issue the route binding with
`researchguard logic route-depth PACKAGE.json --output RECEIPT.json`
using target `route:model-deepening`, owner
`logicguard.model-deepening`, and route
`route:route:model-deepening:deepen`. Every eligible target unit must have
an under-modeling diagnosis, selected action, role completion, effective
perturbation result, and stopping boundary. A high aggregate score cannot hide
one omitted important unit, and the wrapper cannot promote a blocked native
LogicGuard receipt.
Declare a non-empty authoritative `important_unit_ids` denominator. An important
or required unit cannot be excluded or reclassified; another exclusion needs
current hashed evidence, a closed non-contributing/not-applicable disposition,
and no depth contribution.

Counts, role-name lists, catalog expansion, whole-receipt hashes, and ordinal
ranges are not per-obligation evidence. Every satisfied deepening obligation
must retain its exact target-native semantic object, `evidence_ref`, and
lowercase content hash; a missing, renamed, overlapping, mechanically generated,
or summary-only mapping blocks broad deepening closure.



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

Packaged baseline purpose: Prevent a LogicGuard model from being called sufficiently deep while important nodes, under-modeling diagnoses, recursive expansions, role coverage, perturbations, stopping boundaries, or next-route handoffs remain incomplete.

Baseline claim boundary: A pass licenses only the exact deepened model and declared stopping boundary; it does not prove factual truth or that no further useful deepening exists.

The repository keeps these representative baseline failures only to prove that the native verifier can block them:

- `An important node is omitted`: block when the important-node denominator is incomplete.
- `Under-modeling is undiagnosed`: block when shallow or unsupported areas lack a native diagnosis.
- `Expansion or role coverage is shallow`: block when recursive expansions or required role completion are absent.
- `Perturbation depth is unproved`: block when important branches are not effectively perturbed.
- `Stopping boundary or handoff is unresolved`: block when budget/stopping reasoning or the next native route is missing.

These packaged examples are not the purpose of a real target model and cannot authorize one. Before building every real model or route result, AI must write a target-local `logicguard.target_model_purpose_declaration.v1` under the explicit target root. AI declares what this exact model is meant to prevent, its bounded claim, the exact candidate path, and one or many current failure declarations. Every current failure binds one LogicGuard-native oracle plus one target-owned known-good and known-bad case. Then AI freezes `.logicguard/guard-purpose-contract.json` while the candidate path is still absent, builds the candidate, binds it to the frozen fingerprint, exhausts every declared proof, and only then requests native closure.

Missing declarations, late declarations, stale fingerprints, non-blocking bad cases, failing good cases, or a candidate that exposes any declared failure are non-pass. There is one enforced route and no selectable mode, threshold, compatibility reader, fallback, or lighter success path. Evidence insufficiency may narrow the final claim, but it does not select a weaker check.

`guard-model/verify.py` is the LogicGuard-native verifier. `guard-model/baseline-*.json` proves only family capability.
<!-- END MANAGED PURPOSE AND BLOCKABILITY -->
