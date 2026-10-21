## Purpose

This capability keeps domain propositions and mechanisms distinct from generic
trace tooling context when exporting a trace result to LogicGuard consumers.

## ADDED Requirements

### Requirement: Domain meaning is typed in trace export

Trace export SHALL preserve the domain proposition, trace identity, mechanism
references, evidence ids, assumptions, object scope, and material alternatives
as typed fields. Solver status, safe wording, and tool completeness SHALL remain
in audit context and SHALL not become a domain claim.

#### Scenario: Domain proposition and mechanism exist
- **WHEN** a trace contains a real event proposition and mechanism references
- **THEN** export SHALL preserve the same proposition and references
- **AND** generic tool language SHALL remain in audit context

#### Scenario: Mechanism is absent
- **WHEN** a trace has a timeline but no domain mechanism
- **THEN** export SHALL retain an explicit mechanism gap
- **AND** SHALL not infer causation from event order alone
