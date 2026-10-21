## ADDED Requirements

### Requirement: Search continuation has a typed terminal

SourceGuard SHALL derive exactly one of `continue`, `stop_satisfied`, `blocked`, `exhausted`, or `downgrade` from the frozen research objective, coverage obligations, evidence freshness, blockers, and remaining tasks.

#### Scenario: Objective and coverage are satisfied

- **WHEN** all required coverage obligations have current evidence and no blocking source role remains
- **THEN** SourceGuard SHALL return `stop_satisfied` with the satisfied obligations and evidence ids

#### Scenario: Useful work remains

- **WHEN** a required obligation has a feasible unresolved search task
- **THEN** SourceGuard SHALL return `continue` with that exact next task

#### Scenario: Search cannot proceed

- **WHEN** access, source availability, or policy blocks every remaining required task
- **THEN** SourceGuard SHALL return `blocked` rather than treating absence as negative evidence

### Requirement: Stop evidence stays current

SourceGuard SHALL bind every stop decision to the fingerprints of all evidence and coverage inputs it consumed.

#### Scenario: A cited source changes after the decision

- **WHEN** any consumed evidence fingerprint changes
- **THEN** the prior stop decision SHALL be stale and SHALL NOT authorize final closure
