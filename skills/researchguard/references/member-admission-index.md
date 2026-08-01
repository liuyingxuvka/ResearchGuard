# ResearchGuard Member Admission Index

Generated from the four current member-owned admission contracts. Do not infer a route from wording or load member skills to classify the request.

Only source-bound `primary_action` facts create responsibilities to cover. Context facts may satisfy required inputs or expose forbidden conditions but do not create another responsibility. Every forbidden condition needs its exact disposition.

## logicguard

- Positive `logic.primary.general-argument`: `logic.argument_structure, logic.claim_licensing, logic.mixed_workflow`
  - First action: Build or inspect the current argument model and run its native structural checks.
  - First reference: `references/general-argument.md`
- Positive `logic.primary.source-library`: `logic.source_library`
  - First action: Preserve or reuse the concrete source in the LogicGuard source library.
  - First reference: `references/routes/source-library.md`
- Positive `logic.primary.structured-artifact`: `logic.structured_artifact`
  - First action: Map the artifact's natural structure before judging or rewriting it.
  - First reference: `references/routes/structured-artifact.md`
- Positive `logic.primary.model-deepening`: `logic.model_deepening`
  - First action: Select the highest-impact under-modeled node and deepen it in place.
  - First reference: `references/routes/model-deepening.md`
- Positive `logic.primary.artifact-synthesis`: `logic.artifact_synthesis`
  - First action: Freeze the target goal and synthesize one inspectable story plan from current models.
  - First reference: `references/routes/artifact-synthesis.md`
- Positive `logic.primary.project-library-viewer`: `logic.project_library_viewer`
  - First action: Open or check the read-only project-library viewer.
  - First reference: `references/routes/project-library-viewer.md`
- Required `logic.required.reasoning-target`: `logic.argument_structure, logic.claim_licensing, logic.mixed_workflow, logic.source_library, logic.structured_artifact, logic.model_deepening, logic.artifact_synthesis, logic.project_library_viewer`
- Forbidden `logic.forbidden.silent-external-search`: `logic.silent_external_search`
- Forbidden `logic.forbidden.chronology-as-causality`: `logic.chronology_as_causality`
- Forbidden `logic.forbidden.experiment-execution`: `logic.experiment_execution`

## sourceguard

- Positive `source.primary.discovery`: `source.primary_discovery`
  - First action: Declare the target claim and source-role gaps before choosing a search action.
  - First reference: `references/source-model-protocol.md`
- Required `source.required.discovery-target`: `source.primary_discovery`
- Forbidden `source.forbidden.final-argument-license`: `source.final_argument_license`
- Forbidden `source.forbidden.storyline-inference`: `source.storyline_inference`
- Forbidden `source.forbidden.experiment-execution`: `source.experiment_execution`

## traceguard

- Positive `trace.primary.reconstruction`: `trace.temporal_reconstruction`
  - First action: Declare the trace scope, evidence objects, and competing storylines before inference.
  - First reference: `references/routes/general-trace.md`
- Positive `trace.primary.case-library`: `trace.case_library`
  - First action: Preserve the messy case material and search direction before building a trace model.
  - First reference: `references/routes/case-library.md`
- Required `trace.required.trace-target`: `trace.temporal_reconstruction, trace.case_library`
- Forbidden `trace.forbidden.primary-source-search`: `trace.primary_source_search`
- Forbidden `trace.forbidden.final-argument-license`: `trace.final_argument_license`
- Forbidden `trace.forbidden.experiment-execution`: `trace.experiment_execution`

## experimentguard

- Positive `experiment.primary.discriminating-set`: `experiment.discriminating_set`
  - First action: Freeze the declared hypothesis and finite candidate-experiment inventories.
  - First reference: `SKILL.md#required-inputs`
- Required `experiment.required.explicit-hypotheses`: `experiment.explicit_hypotheses`
- Required `experiment.required.finite-candidates`: `experiment.finite_candidates`
- Required `experiment.required.predicted-outcomes`: `experiment.predicted_outcomes`
- Forbidden `experiment.forbidden.execution`: `experiment.execution_requested`
- Forbidden `experiment.forbidden.physical-diagnosis`: `physics.diagnosis`
- Forbidden `experiment.forbidden.software-test-selection`: `software.test_selection`

## Decision boundary

Choose the unique minimum-cardinality applicable member set that covers every primary responsibility. One sufficient member stays single. A necessary multi-member set requires a declarative composition with exact members, order, dependencies, responsibilities, handoffs, single field ownership, and one claim boundary. Zero coverage, equal-minimum ambiguity, over-selection, invalid composition, missing/unknown forbidden review, stale fingerprints, unknown kinds, or missing source spans block before execution. Direct member requests bypass this index.
