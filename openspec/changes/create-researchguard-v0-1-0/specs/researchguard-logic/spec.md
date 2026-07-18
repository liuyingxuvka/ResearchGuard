## ADDED Requirements

### Requirement: LogicGuard remains the argument owner
The logic member SHALL preserve LogicGuard's native argument evaluation,
model-depth, source-library, artifact-structure, synthesis, viewer, receipt,
and claim-boundary semantics.

#### Scenario: Argument workflow executes
- **WHEN** a valid logic task contract and model are supplied
- **THEN** `researchguard logic` executes the LogicGuard native owner and
  returns its native receipt

### Requirement: Former satellites are internal routes
Source-library, structured-artifact, model-deepening, artifact-synthesis, and
project-library-viewer SHALL be internal logic routes and SHALL NOT be
independent installed Skill IDs.

#### Scenario: Internal source-library route
- **WHEN** `$logicguard` receives a source-library request
- **THEN** it selects the internal source-library route under the same logic
  member and suite identity

#### Scenario: Retired satellite is absent
- **WHEN** the installed suite is inspected
- **THEN** none of the five former LogicGuard satellite Skill directories or
  aliases exists

### Requirement: Structural claim boundary is preserved
Logic results SHALL distinguish structural licensing from factual truth.

#### Scenario: Native logic check passes
- **WHEN** the current model satisfies the native structural obligations
- **THEN** the result licenses only the declared structural scope and does not
  claim factual truth
