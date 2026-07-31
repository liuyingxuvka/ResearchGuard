## ADDED Requirements

### Requirement: Contradiction explanations are deletion-minimal

TraceGuard SHALL return a deterministic subset of trace evidence that remains contradictory and becomes non-contradictory when any retained member is removed.

#### Scenario: Redundant evidence is present

- **WHEN** a contradiction includes evidence not needed by the contradiction oracle
- **THEN** the returned core SHALL omit that evidence

#### Scenario: Core budget is exhausted

- **WHEN** the configured oracle-call budget expires before minimality is proven
- **THEN** TraceGuard SHALL label the result `bounded_incomplete` and SHALL NOT claim minimality

### Requirement: Minimality terminology is exact

TraceGuard SHALL distinguish proven subset minimality from minimum-cardinality optimality and bounded incomplete search.

#### Scenario: Deletion minimality is proven

- **WHEN** every retained member has been tested
- **THEN** the report SHALL say `subset_minimal` and SHALL NOT say `minimum_cardinality`
