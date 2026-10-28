# Changelog

## Unreleased

- Size caps on skill text, prompt bundles and command output are replaced by checks for repeated paragraphs, dead links, unknown names and complete output; byte totals are printed, not limited.

- Counter-source searches use the source title without trailing curation notes such as "(trial transcription)".

- The self-models declare the product functions their replays call, so a change to research_status selects every research-tree model that runs it.

- Maintenance checks run on FlowGuard 0.70.14.

## v0.5.16 - 2026-10-27 - Fresh status reports and the question model split by aspect

- Research inputs drop writing-plan fields; validation warns about retired gap keys and rewriting omits them. Structural coverage ids and source boundaries remain research-owned.

- The search-stop model requires declared searches to win ties. Counter-source gaps generate one source-title query; pages name each search gap and group anchor routes on one line.

- The content-anchor model requires source ownership for new anchors. `source add-anchor` creates source-owned anchors and rejects duplicate ids.
- Source YAML omits dataclass defaults while retaining identical loaded values.

- The question cross-reference model now requires status to name every input; JSON reports include file digests and evidence locator, summary and boundary.

- Maintenance checks run on FlowGuard 0.70.13.

## v0.5.15 - 2026-10-24

- Read one hypothesis back with `researchguard status <folder> --hypothesis <id>`: its state in each route, the evidence for, against and limiting it, its ablations, disagreements, open gaps and next actions. An unknown id exits 2. Empty status sections print `none`.
- Evidence rows in `status --json` carry `directions` (route, hypothesis, support/oppose/limit, logic node) for both trace and logic, counting direct evidence only; `used_by` is unchanged. The page shows the same directions.
- Question-level ablations judge the trace route with TraceGuard's own expected-sensitivity check, so `status` and `trace depth` agree; each ablation row lists `effects` on other hypotheses (for example a hypothesis that becomes live).
- SourceGuard gaps may list `hypothesis_ids`; `status` checks them against the question and shows which hypotheses each open gap and next search would move.
- `status --candidate` also compares the verdict, ablations and disagreements and prints only the fields that changed, with two decimals. The reference describes one candidate procedure: copy the folder, sync new evidence into the copy, compare, replace on acceptance.
- The skill starts from the model: read an existing research folder with `status`, or write `research.yaml` first for a new question; `status` names the template when no index is found.
- Maintenance: ResearchGuard's own model tree is checked with FlowGuard 0.70.12 and now models trace projection, experiment elimination, synthesis plans and the source library. Several helper functions are public under names without a leading underscore (`load_spec`, `load_spec_payload`, `load_observations`, `build_native_depth_analysis`, `load_json_object`, `apply_declared_perturbation`, `expected_sensitivity_matches`); the underscore names are gone.

## v0.5.14 - 2026-10-24

- Research folders now expose one native verdict for writers, readable status pages and current/candidate comparisons. Optional library, search and anchor-ablation declarations join source, trace, logic and experiment results without replacing their native reasoning rules.
- Source-owned copied text and metadata are checked for drift. Explicit handoff synchronization refreshes those fields and reports updated identities while preserving downstream links, author summaries and unrelated provenance.
- Predict-observe-revise loops share canonical baseline_identity, terminal decisions and gap lineage. Older frozen predictions must be frozen again; candidates never overwrite current models.
- Removed unused interface-binding inputs: remove nonempty block_interfaces and interface_bindings lists. Provenance uses separation_reason in place of separation_receipt_id; empty legacy lists remain readable.
- Removed logic outline and synthesize --delivery. The stable synthesize request/plan API remains available; writing tools own finished outlines and delivery. LogicWriting should consume the five-key status verdict.
- The skill explains one research tree and one meaning for target. Maintenance uses FlowGuard 0.70.11, function-based map components and native wording/license and iteration models.

## v0.5.13 - 2026-10-23

- Keep native route models in one research folder with a `research.yaml` index and shared hypothesis, source and anchor ids. Use `researchguard status <folder>` for a readable or JSON view of hypotheses, evidence, open gaps and next actions.
- Make SourceGuard the owner of source identity. Use `logic validate --source-model <source.yaml>` to check provenance and `--source-id` on intake or library import to reuse canonical ids. Remove `source export-logicguard`; read the SourceGuard model YAML directly instead.
- Add `--into` to source-to-trace exports and logic handoff imports. Sync appends missing records, reports conflicts, preserves existing work and writes a separate output file.
- Include an Ever Given research tree with quoted source provenance and an example observation flowing through both handoffs.
- Return native results without receipt ids or redundant output fingerprints. Rename trace `inference_receipt` to `inference`, depth result types to `*DepthResult`, `build_source_depth_receipt` to `build_source_depth`, and `revalidate_native_depth_receipt` to `revalidate_native_depth`. Preserve actual model/content freshness and existing input interface structures. Case libraries write gaps and contradictions without storing solver histories.
- Group full attack chains separately in logic reports and show unresolved items from the native conclusion comparison.
- Install the desktop viewer with the optional `viewer` extra and a Python that includes tkinter. Core commands no longer require Pillow. Remove `trace simulate --mode projectradar`.
- Declare evidence type strengths in model `metadata.evidence_type_strength`; undeclared types use neutral 0.25. Existing examples carry their previous values explicitly, including generated case models.

## v0.5.12 - 2026-10-23

- Add field sheets and filled starter models for the four research routes. Validation names the offending node and lists allowed values; quoted evidence can derive its content hash automatically.
- Shorten route instructions to their purpose, command sequence and stopping rules, and show timelines, hypotheses, blocking gaps and source decisions in readable research reports.
- Accept new evidence in trace prediction and revision loops, check the predicted direction, and let ordinary research arguments reach logic depth closure.
- Support optional experiment costs, preserve eliminated hypotheses across observations, remove unused port fields, and allow OSQP versions at or above 1.0.
- Maintain the component map and bind model invariants to tests that exercise their implementation.

## v0.5.11 - 2026-10-22

- Compute absolute storyline support from evidence before causal projection. Competition remains available for comparison and explanation without feeding support back into competing hypotheses; declaring a causal candidate cannot raise storyline support.
- Make opposing evidence contribute negative support directly, give unresolved or partly addressed confounders no positive contribution, and always check causal-declaration and opposition removal during `trace depth`.
- Stop source search when its scope is declared sufficient and no blocking gap is open. Keep `optional_followups` visible and choose affordable critical searches from all executable candidates, with a native stop-rule model covering the decision.
- Compute source, logic and trace loop gap transitions from the actual baseline model. Count only resolved gaps as progress and keep prediction mismatches separate from native gap changes.
- Classify minimal argument-set candidates by the edge entering the claim. When support is unavailable, report the native blockers and their types while preserving the conservative wording license.
- Preserve hypothesis ids, supporting, opposing and limiting evidence, original text and source provenance across trace-to-logic handoffs; retain existing trace-only bundles and the result-only export API.
- Let source depth read observations already applied to the model and preview another observation on a clone without claiming a provider ran during the current call.
- Suppress generated searches for gaps with executable declared actions, keep generated queries short, and use one complete native scoring path for `plan` and `score-actions` without changing scoring weights.
- Compare versions of one source model using actual semantic gap state and qualification decisions; self-comparison reports no changes.
- Run FlowGuard map and release checks in push CI, align the route model and component map, and keep execution journals outside the repository.

## v0.5.10 - 2026-10-21

- `scripts/install_skill.py --check` compares installed files byte by byte.

- One `researchguard` skill with a route table (logic, source, trace, experiment) replaces the five skill entries;
  the installer copies it into `--target`, removes the retired member skill folders and offers `--check`/`--dry-run`.
  The console `researchguard logic|source|trace|experiment` is unchanged.
- Removed SkillGuard-era proof machinery: admission and routing envelopes, native receipts and owner proofs, domain
  and self DNA, blueprints and template packs, ModelMesh, the ModelStore stack, SourceGuard model contracts, the
  LogicGuard depth receipt chain and guard contracts, and the suite fingerprint.
- New: `researchguard source stop-decision` and `researchguard logic minimal-sets`; `trace evaluate` no longer runs
  storyline depth (use `trace depth`); `logic validate --library-root` checks Evidence provenance anchors against the
  source library; the predict-observe-revise loops reject coverage ids (and TraceGuard expected evidence and
  event ids) that are not in the model.
- The two self-models replay the real console, installer and SourceGuard depth code; `flowguard release` passes with
  FlowGuard 0.70.6 and the new FlowGuard.
- `AGENTS.md`: a release records the exact tested commit and follows the maintainer's three-part,
  patch-only version policy. The `stop-decision` CLI test runs on real SourceGuard example models and checks that a model with open
  gaps is not reported as sufficient.

## v0.5.9 - 2026-10-18

- Keep every validated independent holdout counterexample visible and block closure even when another holdout matches.
- Continue bounded multi-survivor iterations with a concrete distinguishing next experiment without claiming unprovable historical progress; retain the strict iteration limit.
- Round-trip ordinary experiment specs without activating blueprint validation; preserve strict partial/nonempty blueprint rejection.
- Align seven command examples and their repeated references with current required native CLI arguments.
- Cover ordinary member-restoration failures, continued rollback and suite aggregation, plus retired-skill preflight rejection before active files change.
- Pin maintenance and CI to the published FlowGuard 0.70.6 dependency.

## v0.5.8 - 2026-10-18

- Complete library, viewer, structure, synthesis and deepening tasks through their native owners; keep route-depth and library-depth as optional shape diagnostics that never license native execution or closure.
- Mark Trace library package, scheduler, obligation, relationship and inference-observation declarations as unverified; retain real purpose, depth and independent holdout checks.
- Correct current schema names, v3 envelope fields, verifier paths and CLI examples without accepting retired contracts.
- Close valid later Experiment iterations before same-gap stall detection, retain the iteration limit first, and distinguish a declared experiment-count limit from genuinely indistinguishable candidates.
- Pin maintenance and CI to the published FlowGuard 0.70.5 dependency.

## v0.5.7 - 2026-10-17

- Rebind four native software-DNA cases to their actual implementation owners and add direct read-only assertions to three existing cases.
- Preserve all 17 native models, 20 function blocks, domain rejection cases and the distinction between static readiness and model execution.
- Pin current maintenance and CI to the published FlowGuard 0.70.4 dependency.
- Separate CLI, composition and native attestation adapters from shared contracts and native members in the living map; preserve all test/model bindings without changing domain implementations.

## v0.5.6 - 2026-10-17

- Fix portable proof paths across Windows/POSIX and bound process-tree timeout cleanup.
- Remove retired SkillGuard controls and fixed ten-owner self-proof/receipt tooling; preserve the 17 native models, 20 code/test/resource bindings and affected/reverse indexes.
- Install the distribution and five skills through ordinary files with independent package, skill and legacy-manifest restoration.
- Use the current FlowGuard 0.70.3 map and executable native models; report static currentness separately from execution.
- Load CLI/member APIs lazily; retire manual closure-ledger helpers; reuse concise views of current Source/Trace results without reducing default Trace stress.
- Reuse one trusted qualification within external-DNA projections while standalone impact/reverse retain their native validation gate and cheap bad cases.
- Validation limit: 13 tests requiring an external frozen paper root are skipped when that independently supplied material is unavailable; no paper material or evidence is fabricated.

## v0.5.5 - 2026-09-21

- Refresh the five current SkillGuard v2 consumer contracts after the A09 documentation and dynamic-model contract repairs.
- Keep the suite package, examples, executable suite model, regression manifest, tests, and all five consumer projections on one current patch identity.
- Preserve direct-current replacement and fail-closed routing with no compatibility reader, alias, or fallback path.

## v0.5.4 - 2026-09-21

- Fix the SkillGuard transaction installer to pass each member's declared
  contract root to prepare, verify, activate, and installed-skill audit.
- Add rollback and root-binding coverage so a suite-root/member-root mismatch
  fails closed without leaving a partial installation.

## v0.5.3 - 2026-09-21

- Add a canonical FlowGuard behavior-commitment envelope boundary and strict
  round-trip loading for the ResearchGuard software-DNA bridge.
- Keep the 17-model, 20-function-block, and 10-native-owner denominators
  separate, with incomplete native evidence remaining explicitly blocked.
- Add counterexample coverage for malformed, foreign, stale, duplicated, and
  tampered behavior commitments.

## v0.5.2 - 2026-09-21

- Adopt the compact SkillGuard v3 author contracts and one explicit sequential
  validation route for each of the five current consumer surfaces.
- Refresh the ResearchGuard suite identity, current model pins, examples, and
  tests to the 0.5.2 patch release without adding compatibility or fallback
  paths.

## v0.5.1 - 2026-09-08

- Remove historical FlowGuard working evidence from the public release tree;
  retain it only in the local audit evidence area.
- Keep the current model authority, package, and five consumer projections on
  one synchronized patch version.

## v0.5.0 - 2026-08-12

- Add one repository-native software-DNA root with four recursively decomposed
  member subtrees, an independently enumerated provider-neutral denominator,
  exact forward/reverse indexes, affected-only closure, and seven readiness
  layers.
- Make CI resolve the public FlowGuard authority from one immutable Git commit;
  the already published v0.4.10 tag and release remain unchanged.

## v0.4.9 - 2026-08-12

- Keep the ResearchGuard suite directory as its native DNA: models,
  code/test bindings, and current evidence remain inspectable in place.
- Keep external-object DNA as an explicit target projection while avoiding a
  standalone package for the suite's own DNA.
- Refresh the five maintained consumer contracts and patch identities.

## v0.4.8 - 2026-08-11

- Keep the ResearchGuard suite DNA in its native directory: models, code/test
  bindings, and evidence stay inspectable and versioned in place.
- Refresh the self-DNA and external-object blueprint after the FlowGuard
  provider update without emitting a standalone transport bundle.
- Regenerate the five consumer contracts and install projection for the new
  patch identity.

## v0.4.7 - 2026-08-11

- Keep the ResearchGuard suite DNA in its native directory: models, bindings,
  and test evidence remain directly inspectable without a standalone bundle.
- Refresh the suite self-model and consumer projections after the FlowGuard
  0.68.11 upgrade.

## v0.4.6 - 2026-08-10

- Synchronize the ResearchGuard package and five maintained skill projections
  with the current provider-neutral DNA boundary.
- Refresh self-DNA, object-DNA qualification, code/test bindings, and current
  model evidence for the patch release; historical receipts remain immutable.

## v0.4.5 - 2026-08-10

- Repair native external-object receipt identity so independently authored
  target paths cannot collide under one receipt id.
- Refresh the portable composition bundle and its member bindings for the
  current patch identity.
- Keep the target-neutral DNA route explicit about trust boundaries and
  preserve the no-reconstruction routine path.

## v0.4.4 - 2026-08-10

- Refresh the repository self-DNA and model-regression identity for the patch release.
- Regenerate the maintained SkillGuard contracts from the current source version.
- Keep external-object DNA target-scoped and preserve the explicit no-reconstruction routine path.

## v0.4.3 - 2026-08-09

- Complete the repository self-DNA spine with current model, code, test,
  intent, and installation bindings while keeping external-object DNA scoped
  to its declared target.

## v0.4.2 - 2026-08-08

- Promote the model-first domain-DNA blueprint spine with current model, code,
  test, intent, and installation bindings.
- Keep the external-object DNA route explicit about declared scope and current
  qualification evidence.

## v0.4.1 - 2026-08-01

- Replaced caller-authored applicability with source-bound task facts and
  member-owned admission-v2 condition derivation, including exact per-condition
  forbidden review and visible stale/placeholder/ambiguous blocking.
- Added minimum-sufficient member-set derivation: one independently sufficient
  member remains direct, while necessary compositions require exact members,
  order, dependencies, responsibilities, handoffs, field owners, and one claim
  boundary; over-selection and unbounded `run all` remain blocked.
- Added one generated admission index and selected-only prompt loading; direct
  member requests continue to bypass the umbrella.
- Reduced the ResearchGuard, LogicGuard, SourceGuard, and TraceGuard entry
  prompts and moved existing deep protocols, commands, safety language, and
  template guidance into conditionally loaded target-owned references.
- Added prompt-bundle/load-graph budgets and known-bad checks while preserving
  every member's existing strict task-local prediction, native depth, gap, and
  holdout closure rules.

## v0.4.0 - 2026-07-31

- Replaced caller-selected umbrella routing with exact four-member,
  member-authored admission evidence and visible zero/many/stale blocking.
- Made LogicGuard, SourceGuard, TraceGuard, and ExperimentGuard task-local
  packets current-only, with explicit scope, iteration lineage, native
  receipts, computed gap transitions, and exact terminal reasons.
- Added independent holdout gates for predictive closure, actual semantic
  binding checks for TraceGuard, provider/finite-action terminals for
  SourceGuard, and prediction-matrix-miss revision candidates for
  ExperimentGuard.
- Expanded FlowGuard and SkillGuard maintenance coverage over the strict
  runtime, prompts, and member-owned regression checks.

## v0.3.0 - 2026-07-31

- Added task-local iterative maturation for LogicGuard, SourceGuard,
  TraceGuard, and ExperimentGuard with predictions, falsifiers, gap
  transitions, next actions, progress, and explicit terminals.
- Added ExperimentGuard observation/iteration routes and target-native
  closure checks for all five ResearchGuard consumer surfaces.

## v0.2.0 - 2026-07-30

- Add ExperimentGuard as the fourth native ResearchGuard member and fifth
  direct skill surface, with exact finite minimum-set recommendations and no
  experiment execution or invented probability.
- Add typed SourceGuard search-stop decisions, TraceGuard deletion-minimal
  contradiction cores, and LogicGuard deletion-minimal support/attack evidence
  with conservative wording licenses.
- Restore exact suite/model/package currentness and register one observed
  FlowGuard model authority for the complete v0.2.0 route boundary.
- Pin the FlowGuard v0.65.1 development dependency by immutable commit and
  enable Git long paths on Windows CI so clean Windows and Ubuntu environments
  can install and execute the governed suite model.
- Expand the single ResearchGuard SkillGuard maintenance unit to all five
  consumer skill surfaces without copying author-side state into consumers.

## v0.1.4 - 2026-07-22

- Adopt SkillGuard 0.4 bounded evidence lifecycle for the four maintained ResearchGuard members.
- Preserve the eight target-declared semantic checks and four independent closure identities.
- Keep consumer distributions free of author-side SkillGuard state.

## v0.1.3 - 2026-07-22

- Align the SourceGuard content-anchor depth finding with the catalog-declared
  `sourceguard_blocked:contentless-anchor` oracle contract so the native
  target-purpose gate closes for the declared bad case.
- Add an executable FlowGuard regression model and native end-to-end coverage
  that reject the retired `no_content_qualified_anchor` finding without an
  alias, dual emission, or fallback path.
- Support one direct `v0.1.2` to `v0.1.3` replacement transaction with no
  compatibility reader, alternate launcher, or fallback runtime.

## v0.1.2 - 2026-07-19

- Refresh the four ResearchGuard author-side SkillGuard contracts and current
  FlowGuard adoption records without exposing maintainer evidence to consumers.
- Keep `researchguard` as the single runtime distribution while preserving
  ResearchGuard, LogicGuard, SourceGuard, and TraceGuard as direct skill
  entrypoints backed by exactly three native member owners.
- Support one direct `v0.1.1` to `v0.1.2` replacement transaction with no
  compatibility reader, alias, alternate launcher, or fallback runtime.

## v0.1.1 - 2026-07-18

- Bind durable mesh-store receipts and fingerprints to the current
  `researchguard` package identity only.
- Prove that a retired `logicguard` distribution being present or absent cannot
  change the current ResearchGuard fingerprint.
- Strengthen zero-residual checks so retired Python imports, distribution
  metadata queries, and declared dependencies block release.
- Directly migrate the current SourceGuard examples to the v0.1.1 suite
  identity and bind them into the SourceGuard maintenance graph.
- Support one direct `v0.1.0` to `v0.1.1` replacement transaction without
  introducing a compatibility reader, alias, or fallback runtime.

## v0.1.0 - 2026-07-18

- Consolidate LogicGuard, SourceGuard, and TraceGuard into one versioned
  `researchguard` distribution.
- Preserve four direct Codex Skill entrypoints backed by three native member
  owners.
- Replace satellite Skill IDs with internal member routes.
- Require terminal selected-route failure, typed handoffs, atomic suite
  installation, and zero normal-runtime compatibility readers or fallbacks.
