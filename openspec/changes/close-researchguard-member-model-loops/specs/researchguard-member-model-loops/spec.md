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
