## MODIFIED Requirements

### Requirement: Current task packets are strict and evidence-bound

Every non-trivial member iteration SHALL bind a non-empty task id and purpose,
an independently fingerprinted coverage universe, explicit assumptions and
unknowns, an iteration and predecessor receipt, base and candidate identities,
one current member-native depth receipt, computed input/resolved/persisted/
introduced gaps, next actions, and one exact terminal. A synthesis request
SHALL additionally bind its ordered argument units, source branches, and
reader-selected dependencies. Former schemas SHALL be rejected rather than
interpreted.

#### Scenario: Caller claims a gap is resolved
- **GIVEN** consecutive native receipts still contain the same addressable gap
- **WHEN** the caller supplies prose saying it is resolved
- **THEN** the member computes `persisted` and does not close the task

#### Scenario: Holdout reuses construction evidence
- **GIVEN** a candidate was built from one evidence fingerprint
- **WHEN** the same evidence id or content fingerprint is supplied as holdout
- **THEN** candidate closure is blocked

#### Scenario: Unit order skips a required predecessor
- **GIVEN** a request declares a required predecessor unit after its dependent
- **WHEN** the synthesis contract is validated
- **THEN** the request is rejected as an invalid or cyclic plan

## ADDED Requirements

### Requirement: Cross-unit contribution is visible

Member closure SHALL distinguish local support edges from contribution to the
target argument. Each selected unit SHALL identify parent, sibling progression,
and downstream consumer or a terminal reason. Missing contribution bindings
SHALL remain visible gaps.

#### Scenario: Local evidence has no target contribution
- **WHEN** a unit has an Evidence-to-Claim edge but no parent or downstream binding to the target
- **THEN** structure audit SHALL report a contribution gap

#### Scenario: Complete handoff is supplied
- **WHEN** parent, sibling, and downstream bindings resolve to current units
- **THEN** the corresponding structural gap MAY close while textual coherence remains a LogicWriting responsibility
