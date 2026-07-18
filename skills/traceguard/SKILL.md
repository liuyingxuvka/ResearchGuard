---
name: traceguard
description: Reconstruct and stress-test evidence-backed temporal traces, competing storylines, execution chains, and bounded causal narratives. Use for event/evidence separation and counter-scenarios, not source discovery planning or final argument licensing.
---

# TraceGuard Skill

## Purpose

TraceGuard reconstructs and stress-tests evidence-backed temporal traces,
competing storylines, execution chains, and bounded qualitative causal
narratives. It keeps events, explanations, outcomes, and predictions separate.

## Entrypoint Scope

TraceGuard owns evidence-trace reconstruction and its internal case-library
route. It does not own source discovery or final argument licensing.

## Local Material Routing

Use the current `researchguard trace` command. Read
`references/routes/case-library.md` only for the internal case-library route;
it is not a separately installed skill.

## Entrypoint Acceptance Map

- event/evidence sequence -> current trace route;
- messy case material -> internal case-library route;
- missing source role -> explicit SourceGuard handoff;
- final conclusion license -> explicit LogicGuard handoff;
- solver failure, infeasibility, weak lineage, live alternatives, or missing
  outcome evidence -> visible blocked or bounded result.

## Use When

Use for temporal order, incident/research lineage, competing storylines,
execution and effect chains, counter-scenarios, and bounded causal-story review.

## Do Not Use When

Do not use TraceGuard to infer causality from chronology, promote an
announcement to an outcome, claim prediction without a native future holdout,
or retry through heuristic or legacy scoring.

## Required Workflow

Declare the trace scope and evidence objects, validate lineage and hard gates,
build and evaluate the canonical trace, test alternatives and perturbations,
and preserve weakest links, safe wording, and typed handoffs.

## Hard Gates

Solver failure, unacceptable residuals, missing evidence lineage, unresolved
critical objects, ineffective critical perturbations, scope transfer, or an
unsupported predictive holdout blocks broad or predictive closure. There is no
solver fallback.

## Output Requirements

Report trace and receipt identities, evidence, failures, blockers, skipped
checks, live alternatives, weakest links, residual risk, safe wording, typed
handoffs, and the claim boundary.

## Detailed Route Contract

Use this skill when an AI must reconstruct an event trace, temporal storyline, competing storyline set, causal chain, counterfactual trace, red-team narrative, structural handoff chain, logic-lead map, project lineage, technology evolution, incident chain, requirement history, audit timeline, research lineage, competitor signal timeline, or ProjectRadar candidate from source-backed evidence.

For academic thesis, dissertation, paper revision, or deep research, use the
consolidated `logic-writing` skill as the upper-level route when the task also
needs existing-document rewriting, visible revision provenance, DOCX output, or
a revision report. TraceGuard still owns method derivation, requirement
history, validation chronology, feedback loops, implementation sequence,
causal/effect chains, literature/technology progression chains, and
safe/unsafe wording for time-dependent or handoff-dependent claims.
It returns progression gaps, weakest links, and safe handoff wording to the
upper-level writing workflow; it does not own final thesis-native prose
integration, citation structure, or submission-ready closure.

TraceGuard is not a summarizer. Build or inspect a model first:

```text
source lineage -> evidence -> entity mention -> event candidate -> typed temporal/stage relation -> hypothesis link -> optional bounded causal candidate -> one compiled HL-MRF/QP -> inference receipt -> trace/hypothesis/causal projection -> gap ledger -> contradiction ledger -> claim boundary
```

## Guard model purpose gate

Before AI creates or materially expands a TraceGuard model, it must write down
what this particular model is supposed to prevent. Create one target-local
`traceguard.task_model_purpose.v1` contract before candidate construction. It
must give the model instance a stable id, state the prevention purpose and
unsupported boundary in plain language, select a non-empty one-or-many subset
of concrete failure ids, retain one task-local native known-good, and bind
exactly one task-local native known-bad to every selected failure. Run the
task proof before ordinary modeling or closure.

The packaged TraceGuard guard-model contract, oracles, known-good cases,
known-bad cases, and verifier are only the family capability boundary and
native-oracle catalog. They prove that supported reactions exist;
they never choose a production model's purpose and must not be copied as its
task declaration. A task may select any meaningful one-or-many subset from
the catalog. If it needs a failure with no TraceGuard-native oracle, first add
that real native oracle and family regression proof, then select it in the
task contract. There is one fixed enforced workflow; no quick, routine,
functional, release, highest-quality, or other selectable success mode exists.

This order is executable, not merely documentary. A generated model candidate
must carry `metadata.guard_purpose_contract` with the exact current purpose
contract reference and fingerprint, model-instance id, plain-language purpose
and boundary, exact ordered selected-failure ids, task-proof fingerprint, and
candidate fingerprint. `traceguard create --purpose-contract ...` and the
case-library model builder require that contract and bind it before returning
a candidate. The formal native storyline-depth bridge recomputes the task
contract and proof and blocks missing, empty, stale, extra, wrong-instance,
unknown-oracle, incomplete-good/bad, post-construction, or mismatched bindings;
a model-file hash or family-baseline fingerprint alone is not a purpose proof.

For a repository regression or one target task, use
`researchguard trace depth <model.yaml> --pretty`; the same current interface
verifies the bound task contract, native cases, and receipt identities.
In scheduled production, the exact target-input set is the request, candidate,
task contract, its one known-good model, and every selected known-bad model—no
fewer and no extras.

TraceGuard freezes, executes, and reconciles its own declared checks. It
remains the sole owner of evidence lineage, factor compilation, hard constraints,
event and trace support, temporal contradiction, bounded qualitative-causal
meaning, perturbation re-inference, scope, and prediction-boundary meaning.

For hierarchical artifacts, preserve the structure route for each material trace:

```text
source_unit_id -> trace_layer -> destination_unit_id/downstream_consumer -> relation_to_previous -> weakest_link -> conclusion_transfer_status -> safe wording
```

Use this for thesis, report, deck, or paper units where a literature review,
technology summary, method decision, validation setup, result, feedback loop,
or project-local case is supposed to support a later section or conclusion.
TraceGuard checks whether the chain exists and where it is weakest; it does not
decide final argument sufficiency without LogicGuard.
When an upper-level writing workflow is active, treat the structure route as
handoff context and return final treatment decisions to that workflow.

For `Stand der Technik`, literature review, and technology summary chapters,
do not only ask whether each item points back to the parent model. Also ask
whether item B is introduced because item A has a scope limit, missing
implementation range, contrast, narrower case, or dependency. If every item
separately returns to the parent but the sibling chain is missing, mark the
trace as `missing_progression_chain` or `parallel_background`.
Treat `Stand der Technik` as one representative review form, not a special
German-only rule. Apply the same progression check to any review, case,
technology, method, or result sequence when the artifact presents neighboring
items as part of one reasoning path.

## Trace Model Mesh Default

For non-trivial timeline, process, validation, execution, outcome, causal,
counter-scenario, or competing-storyline work, TraceGuard defaults to a
layered trace model mesh rather than one clean storyline. Only skip the trace
mesh when the task has no material time, process, causal, validation,
execution, or outcome claim.

Use trace cards such as:

- `lead_card`: question, hypothesis, or claim needing trace reconstruction;
- `event_fact_card`: what happened, when, where, and who is involved;
- `sequence_card`: before/after or process-step relation;
- `mechanism_card`: why one step is supposed to lead to another;
- `evidence_card`: source-linked support for a trace step;
- `counter_card`: contradiction, limiting evidence, alternative explanation, or confounder;
- `boundary_card`: safe wording, unsafe wording, and missing evidence;
- `handoff_card`: downstream LogicGuard or SourceGuard action.
- `progression_card`: previous unit, next unit, relation to previous, scope
  change or limitation exposed, downstream consumer, weakest link, and safe
  wording for literature/technology review sequences.

For substantive trace work, report coverage: leads detected, trace cards created, layer coverage for event fact, sequence, mechanism, execution/outcome, counter/limiting evidence, access gaps, live alternatives, safe wording, unsafe wording, and downstream handoff ids. If only a small timeline or single storyline is built, mark it as partial rather than full TraceGuard coverage.

For engineering or empirical theses, treat these as trace candidates when
material to the conclusion: research question to method selection, requirement
to design decision, model or framework to implementation step, validation
setup to result, result to conclusion, checkpoint to feedback, and pilot or
project-local evidence to broader thesis claim.
For literature and technology review chapters, also treat source A to source B,
model family to narrower implementation case, prior limitation to research
gap, and figure/table takeaway to later claim as trace candidates when they are
used to justify the thesis direction.

## Storyline Depth Execution

For non-trivial `why`, `what if`, prediction-boundary, causal,
competing-storyline, or robustness questions, run the canonical inference
engine and its storyline-depth projection. Preserve:

- one primary hypothesis and any live alternatives;
- linked traces, events, supporting and contradicting evidence;
- typed causal candidates with mechanism, confounder disposition, competing
  alternative, and explicit scope when causal wording is requested;
- declared scenario perturbations and expected sensitivities when available;
- a model-derived perturbation plan ranked by centrality, alternative
  discrimination, importance, and temporal uncertainty;
- per-perturbation changes in hypothesis rank, structural support,
  event/evidence attachment, contradictions, gaps, and declared sensitivity;
- both baseline and perturbed canonical inference receipts, unresolved high-impact gaps, untested
  candidates, the complete candidate-universe fingerprint, eligible/critical/
  selected/executed/effective counts, per-kind coverage, critical-uncovered
  ids, requested/covered claim scope, closure status, and claim boundary.

Do not select the first stored evidence or first trace merely because it is
first. Run `researchguard trace depth <model.yaml> --pretty` or inspect the
`storyline_depth` object emitted by `evaluate`. The native route runs every
candidate at or above its target-owned critical threshold and at least one
representative for each available perturbation kind. `--max-perturbations N`
may create bounded evidence, but it never removes omitted candidates from the
denominator; any omitted critical candidate prevents `PASS`. A perturbation
that changes no modeled result is ineffective unless its null result was
explicitly planned as informative; it does not satisfy depth coverage.

Every perturbation changes typed declarations and invokes the same compiler,
solver, explanation builder, and projection policy again. A shortcut that
edits a reported score, rank, status, or causal label is invalid.

The native TraceGuard receipt and its current input identity are the authority.
No other layer may reconstruct traces, compile a parallel factor graph, rank
hypotheses, choose perturbations, or run a second storyline simulator.

## Core Boundary

TraceGuard v0.6.0 has one canonical mathematical language: a typed,
provenance-aware constrained HL-MRF/MAP problem compiled to a convex quadratic
program and solved directly by OSQP. The same solved latent state projects
trace status, hypothesis support and rank, bounded qualitative-causal status,
explanations, gaps, and safe claim boundaries. Scenario perturbations recompile
and resolve that same problem. The authoritative mathematical and prompt
contract is `references/unified_inference_protocol.md`.

The input model contains declarations only. Caller-authored final status,
support/confidence, rank, causal support, safe wording, or old
intervention/counterfactual outcomes are rejected rather than trusted.
Inference output is structural model support, not calibrated factual
probability, causal identification, factual future prediction, or proof.

LLMs may extract candidate entities/events/times/locations, but final `SameProject`, `Before`, `ValidatedTrace`, `Contradiction`, and `ClaimBoundary` decisions must come from the TraceGuard model and rules.

## Task-Local Storyline Iteration

For a non-trivial task in which new evidence will arrive after the current
storyline model is built, TraceGuard owns this independent loop:

```text
current task model v1
-> freeze expected evidence footprint or future event
-> admit one later evidence batch
-> compare prediction and observation
-> create a distinct candidate model v2
-> run the canonical TraceGuard evaluator
-> accept v2, reject v2, or roll back to v1
```

The prediction must be written before the observation timestamp and bound to
the exact baseline model bytes. An expected evidence footprint should name the
storyline or hypothesis, expected evidence/events, expected order when
material, and what result would weaken it. A future-event expectation also
needs a separate target-owned future-holdout receipt; internal perturbation or
expected sensitivity is still not factual future prediction.

Use the native commands:

```powershell
researchguard trace iterate freeze --model MODEL.yaml --prediction-id P1 --frozen-at 2026-07-17T10:00:00+00:00 --target-kind storyline --target-id TRACE1 --expected-evidence EV1 --weakens-when "EV1 is absent" --output prediction.json
researchguard trace iterate compare --prediction prediction.json --observation observation.json --output comparison.json
researchguard trace iterate decide --comparison comparison.json --observation observation.json --candidate candidate-v2.yaml --required-holdout-evidence EV-HOLDOUT --output revision.json
```

The lifecycle never overwrites v1. Acceptance selects only the current task's
candidate model. Rejection or `--rollback` keeps v1 effective. It does not
change TraceGuard's solver, rules, thresholds, skill defaults, or another
Guard's model, and it does not promote one task result into permanent learning.

## Hard Gates

1. Source entry is not a trace or storyline.
2. No evidence, no event.
3. No evidence, no trace.
4. `invalid_or_empty` source is not validation evidence.
5. `need_auth_or_permission` is access gap, not checked evidence.
6. Weak signal is not a validated trace.
7. Patent is not deployment evidence.
8. Hiring is not operation evidence.
9. Time contradiction must be visible.
10. Location role required.
11. No fake PSL.
12. No LLM final inference in core.
13. Local executable core.
14. Candidate is not validated.
15. Confidence is not factual certainty.
16. Event evidence is not motive, outcome, or future-impact evidence unless the model records that link.
17. One-sided support is not deep investigation coverage; important leads need counter, limiting, or execution-evidence search status.
18. Context, motive, interpretation, or stakeholder concern is not execution, outcome, causal, or broader-scope evidence unless a bridging source records that link.
19. Local, scope-limited, actor-specific, or pilot evidence is not broader-scope evidence unless another source establishes the broader scope.
20. Announcement, plan, forecast, or actor claim is not implementation, operation, outcome, impact, or non-occurrence evidence.
21. If a lead depends on follow-through, TraceGuard must record execution-chain status before handoff or safe final wording.
22. Source registry ids or citation markers should travel with high-impact evidence when the downstream artifact will use compact citations.
23. A clean single storyline is not required when evidence supports multiple live explanations.
24. Causality requires a mechanism and link evidence; chronology alone is not causality.
25. Counterfactual uncertainty must remain visible when an outcome may plausibly occur without the proposed main cause.
26. Confounders, scope conditions, and alternative drivers must be recorded instead of hidden in prose.
27. Deep investigations require layered lead modeling, not only a single trace. Important leads must separate event fact, explanation, execution or follow-through, outcome or impact, stakeholder signal, counter/delay/non-occurrence, future trigger, and safe wording.
28. Effect claims require effect-chain status. Planning, forecast, capacity, wholesale, transmission, resource-procurement, retail, stakeholder, and terminal-impact layers must not be collapsed without bridge evidence.
29. Scope transfer must be visible. Local-to-national, actor-to-sector, forecast-to-fact, wholesale-to-retail, planning-to-outcome, announcement-to-operation, chronology-to-causality, and interpretation-to-direct-fact moves need bridge evidence or downgraded wording.
30. Non-trivial trace work requires countable trace coverage. A single clean storyline is not enough when important trace layers, missing evidence roles, or live alternatives remain unmodeled.
31. A structural trace must preserve source unit, destination unit, required trace layer, weakest link, downstream consumer, conclusion-transfer status, safe wording, and unsafe wording when those fields are available. These are trace handoff fields, not universal prose fields for every artifact.
32. A result-to-conclusion or project-local-to-general claim is not closed when the trace only supports setup, sequence, or local execution.
33. A literature or technology review sequence is not closed when each item
    independently points to the parent chapter but no item-to-item progression,
    contrast, dependency, or background treatment is recorded.
34. A method or validation handoff is not closed when it only lists chronological
    steps without the decision, evidence layer, result layer, and conclusion
    transfer boundary.
35. Storage order is not importance. Evidence-removal and contradiction probes must be selected from current model centrality, uncertainty, discrimination, and declared importance.
36. A perturbation that changes no rank, structural support, event/evidence attachment, contradiction, gap, or causal-boundary state is ineffective and does not satisfy storyline-depth coverage unless an informative-null purpose was declared in advance.
37. An important causal storyline without a mechanism and considered confounders is depth-blocked; chronology and a smooth narrative do not repair it.
38. A broad causal storyline without a competing hypothesis or explicit bounded exclusion reason has a missing-alternative gap.
39. Storyline-depth closure requires the native fingerprinted receipt. A baseline evaluator `ok` value alone does not prove alternative, causal, or perturbation depth.
40. Scenario-perturbation results describe local model behavior under declared changes, not factual future outcomes or causal identification.
41. Every model-derived critical perturbation candidate must execute before broad storyline-depth closure; selecting only the highest candidate per kind is bounded and cannot pass.
42. An explicit perturbation budget must preserve the full candidate-universe fingerprint and report all critical-uncovered ids; budget exhaustion is `GAP` or `BLOCKED`, never broad `PASS`.
43. Broad storyline wording requires requested and covered claim scope to match and `broad_claim_licensed=true`; a locally successful subset is not a broad license.
44. Perturbation coverage is not the whole object universe. Broad depth also requires every critical hypothesis, trace, event, evidence item, mechanism, confounder, causal scope, perturbation, and expected-sensitivity object row to pass under the current object-universe fingerprint.
45. Every explicit trace in a broad request binds its complete ordered unique event-id child universe. A qualified child needs usable time, a non-empty action, and content-qualified source-backed evidence. The effective count floor is the maximum of `max(3, ceil(sqrt(N)))`, any project count floor, and any project ratio-derived floor. Qualified children must cover early, middle, and late sequence thirds, and the longest consecutive unqualified run must stay within the native `ceil(sqrt(N))` ceiling or a stricter project ceiling. Three isolated points in a 1,000-event trace therefore fail (native count floor 32), while 32 well-distributed qualified points can satisfy this anti-degeneracy gate without pretending that every event received project-level validation. Every individually critical event and evidence object still has its own hard row.
46. Every critical perturbation must be effective on its declared target or be explicitly predeclared as an informative-null probe. One effective perturbation cannot hide another ineffective critical probe.
47. A linked confounder with `status: unresolved` is not a completed review. Important causal depth requires resolved, considered, controlled, bounded, or rejected disposition plus mechanism evidence.
48. A scenario perturbation may declare an expected sensitivity direction, and the observed same-engine model delta must match it. Merely applying the same transformation twice does not validate a factual counterfactual outcome.
49. Internal storyline perturbation is not future prediction. If prediction is requested without a separate target-owned future-holdout validator, report `predictive_holdout_status: unsupported_without_native_future_holdout` and block predictive wording.
50. Source lineage and independence groups are semantic inputs. Repeated copies
    from one lineage may not accumulate as independent support.
51. Hard admissibility and contradiction gates are constraints, not large
    penalty weights; soft support may not compensate for a violated hard gate.
52. Solver failure, infeasibility, unacceptable residuals, or an unapproved
    backend is a visible blocked result. There is no heuristic scoring fallback.
53. Every reported support, rank, status, causal boundary, and explanation
    factor id must bind to the same problem, policy, solver, and solution
    fingerprints in one canonical inference receipt.
54. Causal words in source text and chronology alone create no causal atom.
    Qualitative-causal exploration starts only from typed mechanism,
    confounder, alternative, scope, and evidence declarations.

Before broad closure, inspect the canonical inference receipt's schema, policy,
problem, solver, solution, and explanation fingerprints; solver status and
quality gates; the native depth receipt's candidate and object-universe
fingerprints; each trace's eligible and qualified child counts, effective
dynamic floor, early/middle/late phase rows, maximum unqualified run, and
policy origin; critical object rows; critical-uncovered and
critical-ineffective ids; expected-sensitivity mismatches; requested/covered
scope; and predictive holdout status. Consumers may verify these receipts but
must not reproduce TraceGuard's compilation, object selection,
temporal qualification, causal review, or perturbation execution.

## Current-run execution-depth gate

For a non-trivial TraceGuard run that requests broad, complete, causal, deep,
or predictive wording, the canonical inference receipt and its subordinate
storyline-depth receipt are necessary but not by themselves sufficient.
Declare the exact target request and model paths, run the target-owned
`traceguard.storyline_depth` route, and require its current
`EXECUTION_DEPTH_PASS` receipt before broad closure. The evaluator must derive
its dynamic object and perturbation universes, per-trace child
universes, native dynamic-floor receipts, object classes, temporal/kind
strata, critical flags, effectiveness, covered scope, and exact per-obligation
semantic locators from immutable current native receipt content; ordinal spans
and catalog-expanded summaries are not evidence. A caller-authored count,
score, status, or causal label; an old receipt; missing model input; a globally
rich model with one shallow critical trace; three isolated points from a long
trace; or many effective probes beside one untested or ineffective critical
probe cannot satisfy this gate.

An object count, kind list, catalog expansion, whole-receipt hash, or ordinal
range is not proof of an individual TraceGuard obligation. Every satisfied
governed object, trace child, perturbation, qualitative-causal boundary,
expected-sensitivity check, and holdout boundary must retain its exact
target-native semantic object, `evidence_ref`, and lowercase content hash.
Missing, renamed, overlapping, mechanically generated, or summary-only
mappings block broad or predictive closure.

TraceGuard checks current input identity, per-object depth, calibration,
evidence uniqueness, and closure replay, and remains the only owner of evidence
lineage, factor compilation,
hard constraints, event/trace semantics, alternative hypotheses, mechanisms,
confounders, causal scopes, perturbation effects, expected sensitivities, and
prediction boundaries. If a quick local check does not run this target-owned
gate, label it bounded; it cannot support a broad or predictive claim.

## Commands

```powershell
researchguard trace validate <model.yaml>
researchguard trace evaluate <model.yaml> --pretty
researchguard trace depth <model.yaml> --pretty
researchguard trace depth <model.yaml> --max-perturbations 4 --claim-scope broad --pretty
researchguard trace diagnose <model.yaml> --pretty
researchguard trace gaps <model.yaml> --pretty
researchguard trace report <model.yaml> --format markdown
researchguard trace export-logicguard <model.yaml> --output trace_logicguard_bundle.yaml
researchguard trace create --output starter_trace.yaml
researchguard trace simulate --mode storyline --pretty
researchguard trace simulate --mode storyline-depth --model <model.yaml> --pretty
researchguard trace simulate --mode evidence-removal --model <model.yaml> --pretty
researchguard trace simulate --mode contradiction-injection --model <model.yaml> --pretty
researchguard trace compare <before.yaml> <after.yaml> --pretty
researchguard trace library validate examples/case_library --pretty
researchguard trace library build-model examples/case_library metadata-api-incident --output metadata_trace.yaml --pretty
```

For non-trivial TraceGuard work, run the closure helper when available:

```powershell
python scripts/traceguard_closure_check.py --ledger <traceguard-closure-ledger.json> --model <model.yaml> --json
```

The ledger should record `trace_layer_coverage`, weakest link, safe wording,
downstream handoff, literature/technology progression status,
method/validation handoff status, competing-storyline status, stale evidence,
and skipped checks. If the helper returns `partial`, `blocked`, or
`downgraded`, continue
with the named next action: fill missing trace layers, search for execution or
effect evidence through SourceGuard, preserve live alternatives, rerun review
after final-claim edits, or downgrade the final wording. Do not let event
facts, chronology, announcements, or a single clean storyline become full
outcome, causal, or final-argument proof.

## General Route

TraceGuard is general. ProjectRadar is one representative application, not the core definition. Use the same source-to-storyline pipeline for incidents, requirements, research lineage, audit timelines, competitor signals, and project traces.

Examples:

- logs + issue + PR + meeting note -> incident response storyline;
- meeting note + issue + design doc + PR -> requirement evolution storyline;
- paper + patent + dataset + lab note -> research lineage;
- source records + weak signals + independent evidence + limiting sources -> competitor or market-signal trace.

## Case Library Route

Use the internal `route:case-library` when the user needs to save messy investigation material by case and search direction before building a model. Read `references/routes/case-library.md` before executing it.

Keep this route separate from LogicGuard source library:

```text
TraceGuard Case Library = case-scoped investigation memory.
LogicGuard Source Library = durable support for final arguments.
```

Recommended loop:

```text
lead map -> search -> save source -> extract evidence -> build model -> evaluate -> write gaps back -> search again
```

For deep investigations, keep the handoff explicit:

```text
lead question -> event facts -> explanation hypothesis -> competing storyline -> causal chain -> counterfactual trace -> follow-up impact/outcome -> supporting evidence -> limiting/counter evidence -> missing evidence -> safe wording
```

Do not collapse event chains, explanation chains, and follow-up impact chains. A source can confirm that something happened while leaving motives, causal effects, broader scope, or later execution unproven.

For report-grade or paper-grade investigations, preserve a deeper layered lead model:

```text
lead -> event fact layer -> explanation layer -> execution/follow-through layer -> outcome or impact layer -> stakeholder layer -> counter/delay/non-occurrence layer -> future trigger -> safe wording / unsafe wording
```

Each high-impact lead should identify which layers are supported, incomplete, contradicted, access-gated, or not supported.

For model-mesh trace work, preserve trace-card ids and coverage status for each high-impact lead. The minimum coverage row should include `trace_id`, source/evidence ids, event fact status, sequence status, mechanism or causal link status, execution/outcome status when relevant, counter or limiting evidence status, live alternatives, missing evidence, safe wording, unsafe wording, and downstream handoff ids.

Use this three-layer status check for important leads before LogicGuard handoff or final-artifact drafting:

```text
event fact: what happened, when, where, and who was involved
explanation: why it happened, what mechanism or motive is supported
outcome or impact: what changed, shipped, operated, failed, improved, or harmed
```

Evidence for one layer does not validate the others. If only the event fact is supported, the explanation and outcome remain candidate, weak, access-gap, not-supported, or downgraded until their own evidence chain exists.

For important leads, preserve a general evidence-role table:

```text
claim origin -> direct/original fact -> source statement -> scope boundary -> execution/outcome evidence -> context/motive evidence -> interpretation -> counter/limiting evidence -> future trigger
```

For each important lead, record the counter-evidence chain status: supporting evidence found, counter evidence checked, limiting evidence found, critical missing evidence, and whether the lead remains only a hypothesis. Missing execution, outcome, scope, stakeholder, or future-trigger signals should become gaps or safe negative wording, not hidden assumptions.

For follow-through claims, preserve an execution chain:

```text
announcement or claim -> planned action -> implementation signal -> operating or outcome signal -> stakeholder signal -> counter/delay/non-occurrence signal -> future trigger
```

Use statuses such as `complete`, `supported-incomplete`, `candidate`, `gap`, `access-gap`, `not-supported`, or `not-applicable`. If the chain stops at announcement, the safe wording should say that implementation or outcome evidence is missing.

For thesis validation claims, use the same discipline: a described method,
prototype, checkpoint, or test setup is not by itself evidence of validated
outcome. Preserve validation setup, measured result, metric provenance,
feedback action, and conclusion strength as separate layers.

For thesis structural handoffs, preserve:

```text
structure_unit_id
source_unit_id
destination_unit_id
downstream_consumer
trace_layer: requirement_to_design | model_to_implementation | validation_setup_to_result | result_to_conclusion | feedback_loop | project_local_to_broader_claim
trace_layer additions for thesis reviews: literature_scope_progression | technology_case_progression | gap_to_method | figure_table_to_claim
relation_to_previous: extends | narrows | contrasts | exposes_limitation | changes_scope | parallel_background | depends_on | not_applicable
weakest_link
conclusion_transfer_status: supported | partial | missing | overclaim
safe wording
unsafe wording
```

If the weakest link is missing or only partial, return a TraceGuard gap and
safe wording rather than letting a transition sentence imply that the later
section or conclusion has been supported.
For final thesis or paper prose, hand this gap and safe wording back to the
owning academic workflow for contribution-and-expression integration.

For effect claims, preserve an effect chain:

```text
driver or proposed cause -> mechanism -> intermediate signal -> observed outcome or impact -> stakeholder signal -> counter or limiting evidence -> alternative drivers/confounders -> future trigger -> weakest link -> safe wording
```

Do not let intermediate signals become terminal effects. A capacity-market result, wholesale-price movement, resource procurement, queue, planning document, or forecast can support its own layer; it does not by itself establish retail, national, stakeholder, or final outcome impact.

For Atlas-driven investigations, preserve competing storylines:

```text
storyline id
storyline claim
supporting evidence ids
opposing evidence ids
alternative explanation relation
confounders or scope limits
causal-chain weakest link
counterfactual question
status: supported | candidate | weak | contradicted | access-gap | not-supported
safe wording
unsafe wording
next evidence need
```

Do not select the smoothest story just because it reads better. If two storylines remain live, pass that state to LogicGuard for conclusion tournament review.

For causal claims, preserve:

```text
proposed cause
intermediate mechanism
observed effect
evidence for each link
alternative causes
confounders
weakest link
counterfactual: what might happen without the proposed cause
claim impact
```

If the counterfactual remains unresolved, the final wording should be qualified.

When a claim is circulating before it is proven, track the claim-origin path: original record, actor statement, expert interpretation, media interpretation, secondary misread, contextual inference, or unknown origin.

When sources conflict, do not smooth the conflict away. Record which sources conflict, which is fresher, which is closer to the event, which has stronger locator/provenance, which claim layer is affected, and whether the next step is SourceGuard follow-up, LogicGuard warrant review, or claim downgrade.

When a desired final claim would move beyond the current evidence layer, preserve a scope-transfer warning:

```text
transfer type: local-to-national | actor-to-sector | forecast-to-fact | wholesale-to-retail | planning-to-outcome | announcement-to-operation | chronology-to-causality | interpretation-to-direct-fact
current evidence layer
desired wording layer
bridge evidence found or missing
safe wording
unsafe wording
```

When a red-team storyline is material, preserve the strongest opposing narrative even if the preferred storyline remains more likely. Red-team material should include what would make the preferred claim fail or become narrower.

## ProjectRadar Route

ProjectRadar source registry is not a project database. `stable_keep` can enter evidence discovery. `need_auth_or_permission` is an access gap. `invalid_or_empty` is excluded from validation. `source_only` is not a map point.

UI consumers should distinguish `weak_signal`, `candidate`, `validated`, `contradicted`, `insufficient`, `source_only`, and `unknown`.

## LogicGuard Handoff

TraceGuard reconstructs candidate trace and lead status. LogicGuard audits whether the written claim about that trace or lead is structurally licensed.

Before LogicGuard handoff, check that lead status is known, event evidence is anchored, explanation/outcome evidence is separated from event evidence, execution-chain and effect-chain status are recorded when relevant, counter or limiting evidence has been considered, safe wording exists, unsafe overclaim wording is visible when material, missing evidence is identified, scope-transfer warnings are carried forward, access gaps are carried forward, and trace ids or downstream model-card ids are preserved when available.

For final-artifact handoff, also check that source registry ids or citation markers are preserved when available, competing-storyline status is visible, causal-chain weakest links are recorded, counterfactual uncertainty is carried forward, execution-chain status is recorded for follow-through claims, effect-chain status is recorded for causal/impact/price/market/policy claims, and safe wording does not imply execution, causality, scope, price layer, or impact beyond the evidence layer that TraceGuard validated.
If a domain writing workflow is active, this final-artifact handoff is an input
to that workflow, not a TraceGuard claim that final prose is complete.

TraceGuard -> LogicGuard handoff should include `trace_id`, `model_card_id` when known, `structure_unit_id`, `source_unit_id`, `destination_unit_id`, trace layer, validated steps, missing steps, competing-storyline status, causal weakest link, conclusion-transfer status, downstream consumer, safe wording, and unsafe wording.

TraceGuard -> SourceGuard handoff should include `trace_gap_id`, needed evidence role, source class, locator need, counter or limiting need, and bridge-evidence need.

Example safer wording:

```text
Incident A has log, issue, and PR evidence for mitigation; permanent resolution remains outside the current evidence boundary.
```

Avoid:

```text
Incident A was fully resolved by the PR.
```

Also avoid:

```text
The announced project is operating at scale.
The reported concern has already raised prices.
No source was found, so the event did not happen.
A single clean storyline is enough when alternatives remain live.
The event happened before the outcome, so the event caused the outcome.
Regional, planning, forecast, wholesale, capacity, or announcement evidence establishes national, retail, outcome, stakeholder, or observed-fact impact.
TraceGuard fixed the final thesis prose.
```


<!-- BEGIN MANAGED VALIDATED TEMPLATE PACK -->
## Validated Template Pack Routing

- Target families: `traceguard`; native owner: `traceguard.template_packs`.
- Current catalogs: `traceguard.template-pack.catalog` revision `1.0.0`.
- Resolve the task through this Guard's native router first, then ask the target-owned adapter for a current neutral projection; never infer a template from wording or a skill name.
- Preserve the adapter's complete candidate and rejection accounting. Zero candidates may use only the declared validated base; one candidate gets a read-only preview; many candidates require complete dependencies, pairwise compatibility, one field owner, and target-authored dominance or must block as ambiguous.
- Recompute the projection immediately before applying a preview. A stale request, catalog, route, builder, validator, or content identity blocks all writes.
- Hand the selected preview to the target-declared builder and consume every target-native validator receipt. Template structure is not domain validity, completion, installation, release, or publication evidence.
- Record a harvest disposition after creating or materially deepening a reusable model, and keep no-match evidence visible.
- Declared validated bases: `purpose`.
- Template inventory: `case-library`, `causal`, `competing-storyline`, `counterfactual`, `handoff`, `incident`, `purpose`, `research-lineage`, `technology-progression`.
- Native validator inventory: `traceguard.template_packs.validate_native_payload`.
- Claim boundaries: TraceGuard template instances are non-factual model skeletons; source rows are not evidence, evidence must precede events, events must precede traces, and generated traces are not validated.
<!-- END MANAGED VALIDATED TEMPLATE PACK -->
