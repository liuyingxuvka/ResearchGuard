## ADDED Requirements

### Requirement: Suite identity is exact and current

ResearchGuard SHALL expose one current v0.1.4 identity across package metadata, module version, executable suite model, and JSON suite model.

#### Scenario: All identities match

- **WHEN** the currentness checker reads all four sources
- **THEN** it SHALL return a passing receipt containing every source identity and fingerprint

#### Scenario: Any identity drifts

- **WHEN** one source differs or cannot be read
- **THEN** the checker SHALL fail visibly and SHALL NOT select another source as fallback authority

### Requirement: Model freshness inputs are complete

The SkillGuard contract compiler SHALL map the suite model, JSON model, runner, currentness checker, and focused tests to exact source components.

#### Scenario: Model runner changes

- **WHEN** the suite runner changes after a passing receipt
- **THEN** the mapped owner receipt SHALL become stale and require affected revalidation

### Requirement: Observed model authority is explicit

ResearchGuard SHALL bind one audited observed model-system snapshot before feature-level model coverage is claimed.

#### Scenario: Snapshot authority is absent

- **WHEN** model-system audit finds no observed snapshot
- **THEN** broad model-coverage claims SHALL remain blocked
