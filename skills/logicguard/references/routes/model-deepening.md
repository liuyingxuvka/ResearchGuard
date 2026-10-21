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
15. After each deepening round, return the native remaining important leaves,
    open gaps, skipped cards, terminal classifications and next-route needs. A deepening round is not
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

## Native completion and stopping

1. Use diagnose/importance on the current model to identify a real gap affecting the target conclusion.
2. Extend only relevant important nodes, opposition, sources or dependencies and run the current native perturbation/depth evaluation once.
3. For further rounds use the existing argument-iteration freeze/run/rollback route; record actual changes and remaining gaps.

Stop at model_closed_for_task or iteration_limit/progress_stalled/external_input_required. Preserve the finite budget, independent holdout and native blockers; do not add a role package after stopping.
