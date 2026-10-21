## ADDED Requirements

### Requirement: Direct-to-current upgrade
Legacy inputs SHALL be handled only by an explicit rollbackable upgrade owner
that writes the one current format.

#### Scenario: Known legacy input is migrated
- **WHEN** an exact supported legacy input is present in the upgrade snapshot
- **THEN** the upgrade owner records one evidence-bound disposition and writes
  the current format in staging

#### Scenario: Unknown residual remains
- **WHEN** an input cannot be dispositioned to the current format
- **THEN** the upgrade blocks and preserves the previous active environment

### Requirement: Zero runtime residuals
Normal runtime and installed projections SHALL contain no old package import,
old console script, old Skill ID, forwarding stub, compatibility reader,
fallback route, locale fallback, dual manifest, or dual output field.

#### Scenario: Residual scan is clean
- **WHEN** the staged suite is ready for activation
- **THEN** the residual scan reports zero executable legacy surfaces

#### Scenario: Residual is found
- **WHEN** any executable legacy surface remains
- **THEN** activation and release are blocked

### Requirement: Consumer migration precedes retirement
All located active consumers SHALL use current namespaced imports and the
common suite fingerprint before old repositories are made private.

#### Scenario: Consumer fleet is current
- **WHEN** every located active consumer passes current provider and
  mixed-version rejection checks
- **THEN** old-repository privacy changes may proceed after v0.1.0 release

#### Scenario: Consumer still references old authority
- **WHEN** any active consumer imports an old package or calls an old CLI or
  Skill ID
- **THEN** old-repository privacy changes remain blocked
