---
name: experimentguard
description: Recommend a minimum finite set of experiments that can distinguish caller-declared hypotheses. Use for experiment selection and discriminating-test design, not experiment execution, causal truth, probability invention, or source/trace/argument work.
---

# ExperimentGuard Skill

## Purpose

ExperimentGuard turns explicit hypotheses, candidate experiments, and predicted
outcomes into a recommendation-only discriminating set.

## Entrypoint Scope

Own deterministic minimum-set recommendation for caller-declared hypotheses. Do
not execute experiments, decide causal truth, or replace another member.

## Local Material Routing

Native recommendations use the experiment contract only. For explicit blueprint
qualification, impact, trace, or export, read
`references/experiment-model-protocol.md` under `route:experiment-blueprint`
after admission fixes the target and denominator.

## Entrypoint Acceptance Map

- Require unique hypothesis IDs, a finite experiment inventory, and explicit
  comparable predictions.
- Task-local iteration also requires frozen task identity, purpose, coverage and
  fingerprint, assumptions, unknowns, bound, and predecessor receipt.
- Missing declarations, valid observations, holdout evidence, or the current
  native receipt remain visible as unresolved; never guess them.
- Direct and umbrella routing reach the same `researchguard.experiment` owner;
  a sibling is never a retry.

## Use When

Use this skill when at least two concrete hypotheses need one or more declared
experiments that distinguish them.

## Do Not Use When

Do not execute an experiment, invent outcomes or probabilities, infer causal
truth, search for sources, reconstruct a timeline, or license an argument.
Route those requests to the responsible ResearchGuard member.

## Required Inputs

Require unique hypothesis IDs, a finite candidate inventory, and a declared
outcome for each hypothesis/experiment relationship used for discrimination.
Missing declarations stay visible. For umbrella admission, the program derives
applicability from the current contract; direct requests bypass admission.

## Required Workflow

1. Freeze hypotheses, candidate experiments, and predictions.
2. Validate explicit, comparable predictions.
3. Find every minimum-cardinality set distinguishing each hypothesis pair.
4. Return the deterministic first recommendation, tied sets, and unresolved
   pairs.
5. State the claim boundary and keep the result recommendation-only.

## Hard Gates

- Never invent hypotheses, outcomes, probabilities, results, or evidence.
- Every selected or tied set must distinguish every declared pair within the
  finite bound; unresolved pairs remain visible.
- `invalid` and `not_run` observations create gaps. One survivor closes only
  after valid independent holdout evidence not used for construction.
- Zero survivors are a prediction-matrix miss requiring an immutable revision
  candidate and new iteration, never a silent rewrite or success.
- Recommendation status proves only finite-prediction discrimination.

## Conditional Task-Local Experiment Iteration

Blueprint qualification, impact, trace, or export uses
`route:experiment-blueprint` and its protocol. This is member-domain DNA; the
ResearchGuard repository software-DNA root is FlowGuard-owned.

Admission fixes target and denominator. Replay a persistent anchor and immutable
hashes; cache is not authority. Direct use is unverified; a different target
needs a separate anchor. No generic issuer or inline candidate-authoring.

Trigger the loop for a larger task, a real observation, a matrix miss, an
addressable gap, or requested predictive closure. Freeze task identity, purpose,
coverage and fingerprint, assumptions, unknowns, bound, predecessor receipt,
and exact inventories. Each observation carries an evidence ID, content
fingerprint, source, time, construction or holdout role, and `valid`, `invalid`,
or `not_run` status. Invalid and not-run evidence create visible gaps.

With valid observations, compute dispositions and rebuild the minimum set.
Zero survivors emit an immutable revision candidate and require a new iteration.
One survivor closes only with valid independent holdout evidence. Record gap
lineage, next experiments, native receipt identity, rollback base, and terminal
reason. Continue to `model_closed_for_task`, or stop with `iteration_limit`,
`progress_stalled`, or `external_input_required`.

## Local Route

Use `researchguard experiment recommend <spec.json>`. Direct and umbrella
routing reach `researchguard.experiment`; never invoke a sibling after failure.

## Output Requirements

Return `status`, `selected_experiment_ids`, `alternative_minimal_sets`,
`unresolved_hypothesis_pairs`, `reason_code`, and `claim_boundary`. Also report
`evidence`, `failures`, `blockers`, `skipped_checks`, and `residual_risk` to keep
supported, incomplete, and blocked results distinct.
