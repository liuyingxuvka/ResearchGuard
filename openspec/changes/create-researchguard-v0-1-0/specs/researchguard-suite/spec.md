## ADDED Requirements

### Requirement: One suite identity
ResearchGuard SHALL expose version `0.1.0`, one content-addressed suite
fingerprint, one Python distribution, and exactly four installed Skill
members.

#### Scenario: Complete suite is current
- **WHEN** the distribution and all four Skill projections carry the same
  version and suite fingerprint
- **THEN** the suite currentness check reports current

#### Scenario: Mixed member is rejected
- **WHEN** any member is absent or carries a different version or fingerprint
- **THEN** the suite currentness check fails without selecting another copy

### Requirement: Atomic suite installation
The target-owned installer SHALL stage, verify, activate, and recover the
Python distribution and four Skill members as one transaction.

#### Scenario: Activation succeeds
- **WHEN** every staged artifact passes its target-owned identity checks
- **THEN** all four members become active under one transaction identity

#### Scenario: Post-activation check fails
- **WHEN** any required post-activation check fails
- **THEN** the installer restores the entire previous active suite

### Requirement: One final suite validation
The release SHALL bind one frozen source, toolchain, member inventory,
dependency plan, and explicit execution owner before full validation.

#### Scenario: Frozen suite passes
- **WHEN** every member-owned required check has current terminal-success
  evidence and aggregation is complete
- **THEN** the suite may proceed to installation and release checks

#### Scenario: Evidence is stale or non-terminal
- **WHEN** any required evidence is stale, missing, skipped, timed out,
  cancelled, failed, or cleanup-unconfirmed
- **THEN** suite release readiness remains blocked
