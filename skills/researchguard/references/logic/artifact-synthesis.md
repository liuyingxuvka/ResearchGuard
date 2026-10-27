# LogicGuard route: artifact-synthesis

Build an argument-ordered unit plan for a writer from the current model, selected claims and source material. LogicGuard establishes argument support and native readiness. LogicWriting or another writing owner decides the paragraphs, genre and final delivery.

## Inputs and native result

Use `researchguard.logic.synthesis-request.v1` with the current model identity and fingerprint, the requested goal, unit list, explicit body order and source branch bindings. Preserve the strict request validation, claim and source identities, placements, required units and declared scope. A selection request cannot create missing evidence or license an unsupported claim.

`synthesize` computes native evaluation and depth on that model and returns the unchanged `synthesis-plan.v1` contract. Its units retain claim ids, source fit, dependencies and dispositions. The plan exposes closure gaps, native evaluation, native coverage and candidate dispositions; an ancestor retains relevant unresolved descendant gaps. Keep omitted material and its reasons visible. Structural review uses the native structure audit, rather than self-reported coverage counts.

## Workflow

1. Preserve source material through the source-library route when necessary. Audit an existing artifact through structured-artifact before using its structure.
2. Model the important claims, evidence, warrants, assumptions, limitations and opposition needed for the requested argument.
3. Prepare the exact selection request and source branch bindings, using the current native model fingerprint.
4. Run `synthesize` and review the native ready/blocked result, unsupported units, claim boundaries and remaining gaps. Do not replace a blocked result with a hand-written readiness statement.
5. Hand the argument plan to the writing owner. Keep native unit and source identities available so revisions can recheck affected support and citations.

## Commands

```powershell
researchguard logic synthesize examples/logic/structured_artifact_deck.yaml --selection-request <selection-request.json>
researchguard logic structure from-markdown examples/logic/structured_report_outline.md --artifact-kind report --output report_model.yaml
researchguard logic citation matrix examples/logic/engineering_efficiency_argument.yaml
researchguard logic citation audit examples/logic/engineering_efficiency_argument.yaml
```

Stop at the native plan terminal. A ready plan licenses the declared argument boundary; it does not establish factual truth or finish the writer's prose. The writing owner rechecks affected claims and citations after material changes.

LogicWriting does not import this plan; its own CompositionPlan is the plan of a piece.
