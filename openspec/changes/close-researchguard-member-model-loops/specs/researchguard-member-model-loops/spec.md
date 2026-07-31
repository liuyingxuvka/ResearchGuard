# researchguard-member-model-loops Specification

## ADDED Requirements

### Requirement: Each member owns its own iterative closure

LogicGuard, SourceGuard, TraceGuard, and ExperimentGuard SHALL continue only through their own native model/evidence owner and SHALL preserve member identity in every iteration receipt.

#### Scenario: Umbrella route does not combine members
- **GIVEN** a request maps to one ResearchGuard member
- **WHEN** that member has an open gap
- **THEN** the member continues or reports its own blocker; ResearchGuard does not invoke a sibling automatically

### Requirement: Argument, source, and trace receipts carry gap transitions

Each member iteration receipt SHALL record input, resolved, and introduced gap ids, iteration identity, current native depth receipt, next required actions, and terminal reason.

#### Scenario: Matching local result with open depth gap
- **GIVEN** one prediction matches
- **AND** important native depth gaps remain
- **WHEN** the iteration is recorded
- **THEN** the receipt is non-terminal and requires another member-owned iteration

### Requirement: Source search stops only at a declared boundary

SourceGuard SHALL continue when an allowed, budgeted search action can close an important gap, and SHALL distinguish provider/permission blocking from finite-action exhaustion.

#### Scenario: Provider unavailable
- **GIVEN** no permitted provider can be reached
- **WHEN** source iteration is evaluated
- **THEN** it records `provider_access_required` and does not claim source closure

### Requirement: ExperimentGuard consumes real results without executing them

ExperimentGuard SHALL accept an externally supplied observation, classify hypotheses as consistent, eliminated, underdetermined, or model-miss, and recompute the next finite distinguishing set.

#### Scenario: Unexpected experiment result
- **GIVEN** the observed outcome matches none of the declared predictions
- **WHEN** the experiment iteration is evaluated
- **THEN** it creates a prediction-matrix revision candidate and does not select a true hypothesis

### Requirement: No suite-level understanding status exists

ResearchGuard SHALL not use a numeric understanding level or self-reported understanding as a terminal or routing authority.

#### Scenario: Self-assessment cannot route a member
- **GIVEN** a member answer contains an understanding level or self-assessment
- **WHEN** the ResearchGuard router evaluates the result
- **THEN** it uses only the member's native receipt and terminal reason

### Requirement: Current task packets are strict and evidence-bound

Every non-trivial member iteration SHALL bind a non-empty task id and purpose,
an independently fingerprinted coverage universe, explicit assumptions and
unknowns, an iteration and predecessor receipt, base and candidate identities,
one current member-native depth receipt, computed input/resolved/persisted/
introduced gaps, next actions, and one exact terminal. Former schemas SHALL be
rejected rather than interpreted.

#### Scenario: Caller claims a gap is resolved
- **GIVEN** consecutive native receipts still contain the same addressable gap
- **WHEN** the caller supplies prose saying it is resolved
- **THEN** the member computes `persisted` and does not close the task

#### Scenario: Holdout reuses construction evidence
- **GIVEN** a candidate was built from one evidence fingerprint
- **WHEN** the same evidence id or content fingerprint is supplied as holdout
- **THEN** candidate closure is blocked

### Requirement: Zero surviving hypotheses is an ExperimentGuard model miss

When a valid external outcome agrees with none of the frozen prediction matrix,
ExperimentGuard SHALL retain zero truth selections, emit a matrix-revision
candidate bound to the base matrix, and require external model revision.

#### Scenario: Every hypothesis is contradicted
- **WHEN** all declared hypotheses disagree with the valid observation
- **THEN** the terminal is not `model_closed_for_task`
- **AND** `prediction-matrix-revision-required` remains an open gap

### Requirement: Umbrella admission is exact and member-authored

ResearchGuard SHALL reconcile exactly one current admission row from each member,
all bound to the same request and each member's current admission contract.

#### Scenario: Caller selects a member without admission evidence
- **WHEN** the umbrella is invoked with only a member name
- **THEN** it blocks before execution

#### Scenario: Two members are admitted
- **WHEN** two current rows say applicable and forbidden-clear
- **THEN** the umbrella reports visible ambiguity without lexical fallback
