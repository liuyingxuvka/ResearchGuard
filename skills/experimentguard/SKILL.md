---
name: experimentguard
description: Recommend a minimum finite set of experiments that can distinguish caller-declared hypotheses. Use for experiment selection and discriminating-test design, not experiment execution, causal truth, probability invention, or source/trace/argument work.
---

# ExperimentGuard Skill

## Purpose

ExperimentGuard turns explicit hypotheses, candidate experiments, and
hypothesis-specific predicted outcomes into a recommendation-only experiment
set. It is the fourth native ResearchGuard member.

## Use When

Use this skill when the user has at least two concrete hypotheses and wants to
know which declared experiment or finite experiment set would distinguish
them.

## Do Not Use When

Do not use ExperimentGuard to execute an experiment, invent missing outcomes
or probabilities, infer causal truth, search for sources, reconstruct a
timeline, or license an argument. Route those requests explicitly to the
responsible ResearchGuard member.

## Required Inputs

Require unique hypothesis IDs, a finite candidate experiment inventory, and a
declared outcome for each hypothesis/experiment relationship used for
discrimination. Missing declarations remain visible and never become guessed
probabilities.

For umbrella admission, these inputs are source-bound task facts. The program,
not AI, derives applicability from the current ExperimentGuard contract. A
direct ExperimentGuard request bypasses umbrella admission.

## Required Workflow

1. Freeze the hypothesis and candidate-experiment inventories.
2. Validate that predictions are explicit and comparable.
3. Find all minimum-cardinality experiment sets that distinguish every
   hypothesis pair within the declared bound.
4. Return the deterministic first recommendation, all tied minimum sets, and
   every unresolved hypothesis pair.
5. Keep the result recommendation-only and state its claim boundary.

## Conditional Task-Local Experiment Iteration

Trigger the existing task-local loop only when a recommendation is part of a
larger non-trivial research task, a real observation arrives, the prediction
matrix misses, an addressable discrimination gap remains, or the user requests
predictive/deep closure. Then freeze the task id,
purpose, experiment coverage and fingerprint, assumptions, unknowns, current
iteration bound, and predecessor receipt on later iterations with the exact
hypothesis and candidate inventories. Every observation must carry a unique
evidence id, content fingerprint, source, observation time, construction or
holdout role, and an explicit `valid`, `invalid`, or `not_run` status. Invalid
and not-run evidence create visible gaps. After valid observations are
supplied, compute each hypothesis disposition and rebuild the minimum finite
discriminating set from the survivors. Zero survivors is a prediction-matrix
miss: emit an immutable revision candidate and require a new iteration; never
close by silently rewriting the matrix. One survivor closes only after valid,
independent holdout evidence that was not used for construction. The engine
records exact gap lineage, next experiments, native receipt identity, rollback
base, and terminal reason; it never asks whether the model understands and
never invents a probability. Continue until `model_closed_for_task`, or stop
visibly with `iteration_limit`, `progress_stalled`, or
`external_input_required`.

## Local Route

Use `researchguard experiment recommend <spec.json>`. Direct and umbrella
routing must reach the same `researchguard.experiment` owner. Never invoke a
sibling member automatically after failure.

## Output Contract

Return `status`, `selected_experiment_ids`, `alternative_minimal_sets`,
`unresolved_hypothesis_pairs`, `reason_code`, and `claim_boundary`. A
`recommended` status proves only minimum-cardinality discrimination for the
declared finite predictions.
