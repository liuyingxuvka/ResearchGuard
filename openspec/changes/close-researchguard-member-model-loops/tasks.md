## 1. Contracts and member receipts

- [x] 1.1 Add member-loop requirements and ExperimentGuard observation capability specs.
- [x] 1.2 Extend LogicGuard `ArgumentIterationReceipt` with depth/gap/iteration/terminal fields.
- [x] 1.3 Extend SourceGuard `SearchIterationReceipt` with depth/gap/iteration/terminal fields and stop dispositions.
- [x] 1.4 Extend TraceGuard iteration/candidate records with storyline gap transitions and next actions.

## 2. Logic, Source, and Trace behavior

- [x] 2.1 Make LogicGuard native depth gaps override a matching single perturbation and require continuation.
- [x] 2.2 Make SourceGuard replan while allowed gap-closing actions remain and expose provider/finite blockers.
- [x] 2.3 Make TraceGuard continue until important evidence/storyline/causal-boundary gaps close or external evidence is named.
- [x] 2.4 Update the three member prompts and CLI outputs without adding a shared engine.

## 3. ExperimentGuard observation iteration

- [x] 3.1 Add observation, hypothesis-disposition, iteration-receipt, and prediction-matrix revision types.
- [x] 3.2 Add `experiment observe` and `experiment iterate` routes to the existing ExperimentGuard CLI.
- [x] 3.3 Recompute minimum next experiments after real results and preserve underdetermined/model-miss outcomes.
- [x] 3.4 Add known-good, unexpected-result, budget-blocked, and no-probability-invention tests.

## 4. Suite validation and local installation

- [x] 4.1 Update the ResearchGuard umbrella prompt to preserve exact-one routing and opaque member handoffs.
- [x] 4.2 Run member tests and `scripts/check_researchguard_suite.py`.
- [x] 4.3 Regenerate all five maintained contracts and check their current source/compiled/manifest parity.

## 5. Strict current-only closure repair

- [x] 5.1 Replace Logic, Source, Trace, and Experiment task packets with strict
  task/coverage/predecessor/base-candidate/native-receipt/gap-lineage terminals.
- [x] 5.2 Reconcile exact four-member authored admission evidence in the umbrella.
- [x] 5.3 Remove SourceGuard's pre-iterative success path and compute stop terminals
  only after candidate acceptance and native revalidation.
- [x] 5.4 Require TraceGuard semantic evidence/source/event bindings and a disjoint
  holdout observation; run current native storyline depth on base and candidate.
- [x] 5.5 Treat zero ExperimentGuard survivors and invalid/not-run/unknown observations
  as explicit gaps with an unapplied immutable matrix-revision candidate.
- [x] 5.6 Add exact known-bad tests for empty task scope, stale predecessor, self-report,
  same-evidence holdout, no-progress, ambiguous routing, and zero survivors.
- [x] 5.7 Update all five prompts, FlowGuard declared coverage, SkillGuard five-member
  source plan, version 0.4.0, README, and changelog.
- [x] 5.8 Run affected tests and local model checks. Leave final frozen full validation,
  installation, commit, tag, push, and release to the integration owner.

## 6. Final integration and publication

- [x] 6.1 Freeze the five-member source, toolchain, owner plan, and model authority; run one foreground full validation with current target-owned receipts.
- [x] 6.2 Install the package and all five clean consumer skills, then verify source/package/installed-skill parity.
- [ ] 6.3 Commit, tag 0.4.0, push, publish the GitHub Release, and verify source/Git/tag/release identities separately.
