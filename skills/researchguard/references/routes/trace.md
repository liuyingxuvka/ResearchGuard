# TraceGuard

Inside a research folder: run `researchguard status <folder>` first; do the step its `Next` names.

Reconstruct temporal/execution/effect chains and competing stories; review bounded cause. Declare scope, evidence/event boundaries and alternatives first.

## Use / not use

Use for incidents, lineage, requirements history, contradictions and counter-scenarios. The case library preserves messy material before modeling; it is not another skill.
Do not infer cause from chronology, upgrade announcements to operations/outcomes, invent predictions, search for missing sources, license final arguments or use heuristic/legacy scoring. Hand source gaps to SourceGuard and final arguments to LogicGuard.

## Command order

Read the selected route and active references; build the scoped model:

`researchguard trace create --output model.yaml` (new model only; replace synthetic examples)
`researchguard trace validate model.yaml`
`researchguard trace evaluate model.yaml --output evaluation.json`
`researchguard trace depth model.yaml --output depth.json` (when depth is required)
`researchguard trace export-logicguard model.yaml --output bundle.yaml` (handoff only)

Evaluate omits depth. Reuse results; do not rerun the menu for an unchanged model. Load iteration/library references as needed.

## Fields

Fields/examples: `references/trace/fields.md`.

## Hard rules / stop rules

Use the canonical solver; preserve lineage and separate events, explanations and outcomes. Required perturbation, residual, contradiction and holdout checks remain mandatory. Solver failure/bad residuals, missing lineage, unresolved critical objects, untested/ineffective critical probes, scope transfers, live alternatives or unsupported predictive holdout block broad closure. No self-report replaces current evaluation/depth; a member result cannot license another member's claim.

- `model_closed_for_task`: close with current evaluation/depth; acceptance alone never closes.
- `progress_stalled`: report weakest links; seek changed evidence or narrow scope.
- `iteration_limit`: stop retries; report unresolved blockers.
- `external_input_required`: request the missing input or typed owner handoff.
- `scope_excluded`: state the exclusion; do not transfer conclusions outside scope.

## Conditional references

- `route:general-trace`: `references/trace/general-trace.md`; mathematical inference work also reads `references/trace/unified_inference_protocol.md`.
- `route:case-library`: `references/trace/case-library.md`.
- `trigger:fields`: model/observation writing → `references/trace/fields.md`.
- `trigger:task-iteration`: later evidence, prediction test, model miss or revision → `references/trace/task-iteration.md`.
- `trigger:depth-closure`: broad/complete/causal/deep/predictive/high-impact/robust or competing claims → `references/trace/depth-and-closure.md`.
- `trigger:commands-handoffs`: CLI or typed handoff → `references/trace/commands-and-handoffs.md`.
- `trigger:safe-output`: separation, scope, weakest link or downgrade → `references/trace/safe-output.md`.
