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
- [x] 4.3 Regenerate and check local installed skills; do not push GitHub or create a remote release.
