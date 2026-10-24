# researchguard-member-model-loops Specification

## Purpose
Let each ResearchGuard route grow its model with the research: predict, observe, revise, on plain model files, with native gap transitions.

## Requirements
### Requirement: Each route owns its own loop
LogicGuard (`argument-iteration`), SourceGuard (`search-iteration`), TraceGuard (`iterate`) and ExperimentGuard (`observe`) SHALL each continue only through their own native model; no loop SHALL invoke another route automatically.

#### Scenario: An open gap remains
- **WHEN** one route's iteration ends with an open gap
- **THEN** that route SHALL report `continue_iteration` or its exact stop reason and SHALL NOT run a sibling route

### Requirement: Predictions are bound to the model
The routes SHALL use one shared current/candidate lifecycle kernel. Frozen prediction schemas are v3 and carry `baseline_identity`; retired prediction schemas SHALL fail with `stale_prediction: re-freeze`. A changed baseline SHALL be frozen again. Named hypotheses, claims and coverage ids SHALL exist in that baseline. TraceGuard MAY predict evidence/event ids not yet present; its expected support direction SHALL be optional and, when declared, one of `weaken`, `strengthen` or `unchanged`. Other routes retain their native expected-id requirements.

#### Scenario: A coverage id is misspelled
- **WHEN** `freeze` is given a coverage id that is not in the model
- **THEN** freeze SHALL fail with a message naming the missing id

### Requirement: The loop never writes model files
A loop SHALL leave baseline and candidate model files unchanged; the caller SHALL supply a candidate at a separate path. Rollback SHALL select the baseline without overwriting either file.

#### Scenario: A candidate is rejected
- **WHEN** the decision is `reject` or the candidate fails a protected or holdout check
- **THEN** the baseline file SHALL remain the current model

### Requirement: Results carry native gap transitions
Each iteration result SHALL record input, resolved, persisted and introduced gap ids, the native depth gaps, next actions and the terminal reason,. Transitions SHALL compare the actual baseline and candidate model native gaps using one shared set operation. Only resolved gaps SHALL count as progress; prior-open ids SHALL control stagnation only. Trace prediction mismatch ids SHALL remain rejection reasons and SHALL NOT enter native gap transitions.

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

### Requirement: Trace observations can append native records
A v2 TraceGuard observation MAY carry `new_sources`, `new_evidence`, `new_events` and `new_links`. Compare SHALL append these only in memory, reject conflicting ids, rebind native references and use canonical evaluation to report the checked hypothesis's support before/after. A delta below -0.01 SHALL weaken, above 0.01 SHALL strengthen, and otherwise remain unchanged. A declared direction that differs SHALL be a `direction_mismatch`. Native depth gaps SHALL remain in `open_depth_gap_ids`, outside prediction mismatches.

#### Scenario: New opposing evidence weakens the checked hypothesis
- **WHEN** expected evidence absent from the baseline arrives as a native observation row with an opposing link
- **THEN** compare SHALL evaluate that appended model without changing the baseline and SHALL check its support direction

### Requirement: Trace acceptance is separate from closure
A candidate SHALL preserve all newly observed records with the same ids and content, including links. It MAY revise other model content. Unaddressed/unknown mismatches, invalid observations, failed canonical evaluation, holdout failures and rollback SHALL retain their guards. Acceptance with remaining native gaps SHALL select the candidate and continue iteration; only gap-free accepted candidates MAY close the task.

#### Scenario: Accepted revision retains a live alternative
- **WHEN** a valid candidate preserves new observed records and satisfies mismatch/holdout guards but has unresolved native depth gaps
- **THEN** its disposition SHALL be `accepted`, its effective fingerprint SHALL identify that candidate and its terminal reason SHALL remain `continue_iteration` unless an existing external-input, iteration or stagnation bound applies

### Requirement: Ordinary argument coverage uses an internal inventory
When all recognized model/node declared-unit, card and role declarations are absent and there are no nonempty native blocks, LogicGuard SHALL derive one internal unit/card covering root-reachable nodes while retaining important disconnected nodes. It SHALL expose `coverage_universe.implicit_inventory` without changing model metadata, nodes, blocks or its fingerprint. Explicit declarations, including empty or null ones, SHALL retain existing checks. Real role, scope, competition and perturbation gaps SHALL still block closure.

#### Scenario: Evidence is shared by competing claims
- **WHEN** two important claims use the same Evidence node
- **THEN** it SHALL appear in `shared_evidence_node_ids` without a shared-role gap or blocked row from that sharing; shared non-Evidence roles SHALL still require explicit consumer declarations

### Requirement: Experiment recommendations preserve their finite objective
Absent experiment costs SHALL retain count-first recommendation. A supplied cost mapping (including empty) SHALL use non-negative finite numeric costs, default omitted candidate costs to 1, and permit at most 16 candidates. Within the declared count limit, recommendation SHALL minimize total cost, then count, then experiment ids; alternatives SHALL exclude the selected set. Remaining recommendations SHALL retain the projected cost mode after observations.

#### Scenario: A matrix miss follows valid counterevidence
- **WHEN** a hypothesis has already been contradicted by a valid construction observation and a later outcome matches no declared hypothesis
- **THEN** it SHALL remain `eliminated`, other uncontradicted hypotheses SHALL be `model_miss`, and zero survivors SHALL require matrix revision rather than closure

#### Scenario: Retired experiment port keys occur in old JSON
- **WHEN** an old prediction or observation contains one of the four retired port fields
- **THEN** the loader SHALL ignore that field, retain the current native task and observation semantics, and omit it from serialized output
