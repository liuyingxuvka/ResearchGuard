## ADDED Requirements

### Requirement: The suite has exactly four native members

The current ResearchGuard suite SHALL contain `logicguard`, `sourceguard`, `traceguard`, and `experimentguard` in source, router, CLI, FlowGuard model, installer, installed authority, and SkillGuard maintenance inventory.

#### Scenario: Inventory is current

- **WHEN** suite currentness runs
- **THEN** every authority SHALL name exactly the same four members and zero retired members

### Requirement: Routing selects one member

ResearchGuard SHALL reconcile member-authored applicability and forbidden-condition evidence to exactly one selected member or one visible blocked terminal.

#### Scenario: Multiple members appear applicable

- **WHEN** applicability and forbidden-condition evidence does not yield exactly one member
- **THEN** the router SHALL return visible ambiguity and SHALL NOT use lexical score or list order

#### Scenario: One member is selected

- **WHEN** exactly one member satisfies its admission contract
- **THEN** ResearchGuard SHALL invoke that member once and SHALL NOT retry another member after a blocked terminal
