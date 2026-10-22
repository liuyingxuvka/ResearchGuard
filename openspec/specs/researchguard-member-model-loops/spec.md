# researchguard-member-model-loops Specification

## Purpose
Let each ResearchGuard route grow its model with the research: predict, observe, revise, on plain model files, without receipts.

## Requirements
### Requirement: Each route owns its own loop
LogicGuard (`argument-iteration`), SourceGuard (`search-iteration`), TraceGuard (`iterate`) and ExperimentGuard (`observe`) SHALL each continue only through their own native model; no loop SHALL invoke another route automatically.

#### Scenario: An open gap remains
- **WHEN** one route's iteration ends with an open gap
- **THEN** that route SHALL report `continue_iteration` or its exact stop reason and SHALL NOT run a sibling route

### Requirement: Predictions are bound to the model
A frozen prediction SHALL name only ids that exist in the model it is frozen against (claims and nodes, actions and gaps, traces, evidence, events, sources or hypotheses, including coverage ids), and SHALL be reported as stale when that model file changes.

#### Scenario: A coverage id is misspelled
- **WHEN** `freeze` is given a coverage id that is not in the model
- **THEN** freeze SHALL fail with a message naming the missing id

### Requirement: The loop never writes model files
A loop SHALL leave the baseline model file unchanged and write a candidate only to a new path; rollback SHALL be keeping or restoring the previous model file.

#### Scenario: A candidate is rejected
- **WHEN** the decision is `reject` or the candidate fails a protected or holdout check
- **THEN** the baseline file SHALL remain the current model

### Requirement: Results carry gap transitions, not receipts
Each iteration result SHALL record input, resolved, persisted and introduced gap ids, the native depth gaps, next actions and the terminal reason, and SHALL NOT carry receipt fingerprints. Transitions SHALL compare the actual baseline and candidate model native gaps using one shared set operation. Only resolved gaps SHALL count as progress; prior-open ids SHALL control stagnation only. Trace prediction mismatch ids SHALL remain rejection reasons and SHALL NOT enter native gap transitions.

#### Scenario: Matching prediction with an open depth gap
- **WHEN** the prediction matches but an important native depth gap remains
- **THEN** the result SHALL be non-terminal and SHALL list that gap

#### Scenario: A first iteration discovers a gap
- **WHEN** a candidate retains baseline gaps and introduces a new gap without resolving any
- **THEN** the baseline gaps SHALL be persisted, only the new gap SHALL be introduced, and `progressed` SHALL be false

### Requirement: Holdouts are optional but independent
A holdout claim or observation SHALL be optional; when one is given it SHALL be independent of the evidence used to build the model.

#### Scenario: Holdout reuses construction evidence
- **WHEN** a holdout observation shares evidence ids with the construction observation
- **THEN** the decision SHALL fail with a message about holdout independence
