## Purpose

This capability turns a reader-declared selection into an ordered, bounded,
evidence-backed argument-unit handoff without discarding unselected material.

## ADDED Requirements

### Requirement: Synthesis accepts a typed unit request

The current synthesis provider SHALL require a `researchguard.logic.synthesis-request.v1`
request containing ordered units, claim ids, reader jobs, dependencies,
placements, budgets, source branch bindings, and current model identity. It
SHALL reject missing, stale, cyclic, or inconsistent identifiers.

#### Scenario: Valid units are ordered
- **WHEN** required units form an acyclic complete body order and all source bindings resolve
- **THEN** synthesis SHALL return `research_handoff_ready` with the same unit order

#### Scenario: Implicit top-N call is used
- **WHEN** a caller omits the typed selection request
- **THEN** synthesis SHALL return `blocked_invalid_request`
- **AND** SHALL not silently select a default top-N set

### Requirement: Candidate accounting is complete and dispositions are explicit

The result SHALL account for every candidate exactly once, including selected,
omitted, appendix, note, internal, and blocked dispositions. Omitted material
MUST not enter body delivery; source-branch support MUST bind to the actual
selected unit.

#### Scenario: Twenty-five candidates are supplied
- **WHEN** the request selects fewer than all candidates
- **THEN** the result SHALL contain all twenty-five candidate dispositions
- **AND** each id SHALL occur exactly once

#### Scenario: Required support is missing
- **WHEN** a selected claim has no valid support, warrant, or boundary closure
- **THEN** synthesis SHALL return `blocked_support_gap` with the exact unit and gap
