## ADDED Requirements

### Requirement: One explicit four-member author unit
The repository SHALL declare itself as the sole current SkillGuard author source for `researchguard`, `logicguard`, `sourceguard`, and `traceguard` in `unit:researchguard-suite`, while retaining one complete native route for each member.

#### Scenario: Current author adoption
- **WHEN** the author repository is audited with the current SkillGuard maintainer audit
- **THEN** exactly four managed members SHALL resolve to the same maintenance unit and current native route evidence

#### Scenario: Duplicate predecessor authority is excluded
- **WHEN** the current unit inventory is frozen
- **THEN** old standalone repository identities SHALL NOT be enrolled, rewritten, or used as alternate success authorities

### Requirement: SkillGuard preserves target-owned depth
SkillGuard SHALL compile and validate only the exact native checks, evidence subjects, obligations, and execution owners declared by each target skill, and SHALL NOT invent or deepen domain requirements.

#### Scenario: Exact declared inventory
- **WHEN** the maintenance-unit validation plan is frozen
- **THEN** it SHALL contain exactly the eight declared checks owned by the four members with no foreign or inferred domain check

#### Scenario: Missing declared evidence
- **WHEN** any declared check is missing, stale, skipped, failed, non-terminal, or bound to a different identity
- **THEN** author-maintenance closure SHALL remain blocked rather than weakening the target contract

### Requirement: Current authority uses direct replacement
Each member SHALL have one current SkillGuard 0.4 compiled contract and check manifest derived directly from its current source contract, with no compatibility reader, converter, fallback, alias, or parallel authority.

#### Scenario: Current compile parity
- **WHEN** each generated contract trio is checked with the current compiler
- **THEN** the compiled contract and check manifest SHALL equal the canonical outputs for the unchanged target declaration

#### Scenario: Former generated authority
- **WHEN** an older generated shape is encountered
- **THEN** it SHALL be replaced directly and SHALL NOT remain a second readable success path

### Requirement: Consumer projections remain independent
The consumer projection for each member SHALL contain only target-owned runtime material and SHALL exclude author contracts, receipts, run state, maintenance-unit identifiers, author paths, router state, and SkillGuard commands.

#### Scenario: Source-to-consumer comparison
- **WHEN** a clean consumer projection is compared with the current installed consumer tree
- **THEN** content differences and missing target-owned release identity SHALL be reported separately from author validation

#### Scenario: No activation in this change
- **WHEN** this maintenance change completes local verification
- **THEN** no global consumer installation SHALL be created or modified

### Requirement: Evidence and claims remain bounded
Current validation evidence SHALL bind the exact unit, member, owner, request, inputs, dependencies, toolchain, and environment, and the final claim SHALL distinguish author maintenance, consumer content parity, installation, and publication.

#### Scenario: Current affected validation
- **WHEN** source, toolchain, and the eight-check plan are frozen
- **THEN** each missing owner SHALL execute once and closure SHALL consume only its current same-unit terminal result

#### Scenario: Historical evidence remains untouched
- **WHEN** old run-state or owner-evidence objects are found without current roots
- **THEN** this change SHALL leave them intact and report lifecycle cleanup as a separately authorized follow-up
