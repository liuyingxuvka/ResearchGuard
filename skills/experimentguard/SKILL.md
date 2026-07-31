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

## Required Workflow

1. Freeze the hypothesis and candidate-experiment inventories.
2. Validate that predictions are explicit and comparable.
3. Find all minimum-cardinality experiment sets that distinguish every
   hypothesis pair within the declared bound.
4. Return the deterministic first recommendation, all tied minimum sets, and
   every unresolved hypothesis pair.
5. Keep the result recommendation-only and state its claim boundary.

## Local Route

Use `researchguard experiment recommend <spec.json>`. Direct and umbrella
routing must reach the same `researchguard.experiment` owner. Never invoke a
sibling member automatically after failure.

## Output Contract

Return `status`, `selected_experiment_ids`, `alternative_minimal_sets`,
`unresolved_hypothesis_pairs`, `reason_code`, and `claim_boundary`. A
`recommended` status proves only minimum-cardinality discrimination for the
declared finite predictions.
