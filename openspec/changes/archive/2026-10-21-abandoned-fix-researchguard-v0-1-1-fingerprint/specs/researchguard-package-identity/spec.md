## ADDED Requirements

### Requirement: Sole ResearchGuard package identity
ResearchGuard SHALL derive the durable ModelMesh store fingerprint and commit
receipt package version from the current ResearchGuard package identity only.
It MUST NOT query, import, alias, or fall back to a predecessor distribution
for that identity.

#### Scenario: Retired LogicGuard distribution is present
- **WHEN** the retired `logicguard` distribution reports any installed version
- **THEN** ResearchGuard produces the fingerprint and receipt version for the current ResearchGuard release without consulting that distribution

#### Scenario: Retired LogicGuard distribution is absent
- **WHEN** no `logicguard` distribution metadata exists
- **THEN** ResearchGuard produces the same current-release fingerprint without `0+local`, alias, fallback, or error-recovery version selection

### Requirement: Predecessor runtime dependency absence
The current ResearchGuard runtime SHALL contain no executable import,
distribution metadata query, or declared package dependency on retired
`logicguard`, `sourceguard`, or `traceguard` distributions. Validation MUST
fail when such a dependency is introduced.

#### Scenario: Old metadata query is introduced
- **WHEN** a current runtime source queries distribution metadata for a retired member package
- **THEN** the predecessor-absence check reports the exact file and blocks validation

#### Scenario: Current namespaced member is used
- **WHEN** runtime imports a member through the `researchguard` package namespace
- **THEN** the predecessor-absence check accepts the import as current

### Requirement: Direct v0.1.1 replacement
The v0.1.1 installer SHALL replace the sole ResearchGuard distribution and
exactly four consumer skills directly. It MUST remove retired skill ids, MUST
exclude `.skillguard`, and MUST expose a blocked result instead of selecting a
different version, package, command, or install path.

#### Scenario: Upgrade from v0.1.0
- **WHEN** a machine has the v0.1.0 ResearchGuard distribution and four current member skills
- **THEN** one installer run replaces them with the exact v0.1.1 package and four v0.1.1 consumer projections

#### Scenario: Installed projection is audited
- **WHEN** installation completes
- **THEN** package version, package files, all four skill inventories, console entrypoint, retired-id absence, and `.skillguard` absence match the frozen v0.1.1 source

### Requirement: Six-face release identity
ResearchGuard v0.1.1 SHALL use one frozen release commit whose source version,
installed package and four skills, local and GitHub default branch, annotated
tag, and GitHub Release are mutually consistent. The GitHub Release SHALL be
source-only with zero attached assets.

#### Scenario: Release closure
- **WHEN** v0.1.1 is published
- **THEN** every identity face resolves to the frozen release content and the Release has no assets
