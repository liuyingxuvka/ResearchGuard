# LogicGuard

Audit argument support, hierarchy, source-library structure and evidence-bounded
synthesis. Select one internal route and model the task before drafting a conclusion.

## Use / do not use

Use for arguments, artifact structure, modeled libraries, deepening and synthesis.
For factual discovery or temporal causality, hand off to SourceGuard or TraceGuard.
Ambiguous internal work stays in `route:general-argument` until its first action is clear.

## Command order

Load the selected route's reference, construct or inspect its model, then run:

```text
researchguard logic validate <model> --source-model <source.yaml>
researchguard logic evaluate <model>
researchguard logic depth <model>
researchguard logic minimal-sets <model> --claim <id>
```

Use the selected sub-route's commands for library, artifact or synthesis work.
Fields and node/edge meanings: `references/logic/h-wadf-quick-reference.md`.

## Hard rules and stops

Exactly one route owns the current action; never retry a failed member elsewhere.
Missing support, warrant, assumption, boundary, opposition, perturbation or declared
inventory coverage blocks closure. Broad wording requires its depth checks.
No self-report replaces current target-native evidence or upgrades another member's claim.
`assert`, `qualify`, `withhold` are wording licenses, not factual-truth judgments.

Only `model_closed_for_task` closes the task. For `progress_stalled`, stop and obtain
missing input; for `iteration_limit`, report the bound; for `external_input_required`,
request the named evidence; for `scope_excluded`, return the typed handoff.
Keep each non-closure visible; revise addressable gaps in the native loop.

## Conditional references

Load only the selected route and active triggers:

- `route:general-argument`: ordinary/unclear argument → `references/logic/general-argument.md`.
- `route:source-library`: preserve/reuse sources → `references/logic/source-library.md`.
- `route:structured-artifact`: audit artifact units → `references/logic/structured-artifact.md`.
- `route:model-deepening`: deepen a model → `references/logic/model-deepening.md`.
- `route:artifact-synthesis`: plan from modeled material → `references/logic/artifact-synthesis.md`.
- `route:project-library-viewer`: inspect library UI → `references/logic/project-library-viewer.md`.
- `trigger:task-model-maturation`: change, observation, prediction, miss, contradiction or gap → `references/logic/task-model-maturation.md`.
- `trigger:broad-depth-closure`: broad/final/high-impact wording → `references/logic/broad-depth-and-closure.md`.
- `trigger:structural-contribution`: parent/consumer contribution → `references/logic/structural-contribution.md`.
- `trigger:citation-grounding`: source-backed writing → `references/logic/citation-grounding.md`.
- `trigger:commands`: CLI execution → `references/logic/commands.md`.
- `trigger:model-creation`: model construction → `references/logic/h-wadf-quick-reference.md`.
