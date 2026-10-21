## ADDED Requirements

### Requirement: Blueprint material loads only for the selected native operation
The umbrella and direct member entries SHALL treat domain-blueprint check, impact, reverse-trace, and export as explicit conditional operations. The system MUST load only the selected member's entry, the reference declared for that operation, and the affected slice required by the request. A blueprint operation MUST NOT eagerly load sibling skills, unrelated deep references, or whole-project material.

#### Scenario: Ordinary member task does not request a blueprint operation
- **WHEN** a selected member can perform its bounded native action without blueprint check, impact, reverse-trace, or export
- **THEN** blueprint references and unrelated member material remain unloaded

#### Scenario: Selected member performs impact analysis
- **WHEN** a source-bound request explicitly requires impact analysis for one member and one affected slice
- **THEN** only that member's impact reference and declared affected neighborhood are loaded

#### Scenario: Cross-member composition uses envelopes
- **WHEN** a necessary composition consumes current member envelopes and handoff contracts
- **THEN** the umbrella loads the envelope contract but does not load or interpret each member's internal blueprint payload

### Requirement: Software-DNA loading distinguishes affected work from explicit whole-repository work
Ordinary maintenance SHALL start from the changed request, model, code, test, intent, resource, topology, public-surface, or external-interface identities and load only their forward, reverse, and affected closure. Complete repository denominator materialization SHALL occur only for an explicit whole-DNA qualification, canonical export, proof-gated architecture-reduction qualification, or frozen release gate. Unknown ownership MUST block the bounded claim and MUST NOT silently widen it into a whole-repository scan.

#### Scenario: One bound behavior changes
- **WHEN** one function block, implementation item, test, intent source, resource, or topology edge changes during ordinary maintenance
- **THEN** FlowGuard loads that item's indexed owner, relations, and transitive affected closure while unrelated member subtrees remain unloaded

#### Scenario: Whole-repository software-DNA qualification is explicit
- **WHEN** a caller explicitly requests whole-DNA qualification or canonical export
- **THEN** the independent complete denominator and all four member subtrees are materialized under one frozen source and toolchain identity

#### Scenario: An affected relation is unknown
- **WHEN** the bounded request reaches an item with no current owner or dependency relation
- **THEN** the operation reports that gap and does not choose `run all`, a legacy index, or a caller-supplied path subset

### Requirement: Direct and umbrella blueprint routes retain the same native owner
A blueprint operation reached directly or through ResearchGuard SHALL invoke the same member-native checker, impact owner, trace owner, or export owner with the same model, schema, task, expected-target anchor, and resolved native-receipt identities. Umbrella admission MAY supply the external expected-target anchor from original task facts. A direct member route MUST receive that anchor from an external owner and MUST remain unverified when it is unavailable; the member MUST NOT create one from submitted candidate or universe material. The umbrella MUST NOT add a parallel generic checker, target or receipt issuer, alternate threshold, alias, retry, or compatibility route.

#### Scenario: Direct and composed checks are compared
- **WHEN** the same current member blueprint is checked directly and referenced by an umbrella composition
- **THEN** both paths identify the same native owner and receipt while the umbrella reports only transport and composition evidence

#### Scenario: Native checker is unavailable
- **WHEN** the selected member's native blueprint checker cannot run or has no current receipt
- **THEN** the operation blocks visibly and does not fall back to an umbrella or sibling checker

#### Scenario: Direct route lacks external admission
- **WHEN** a direct member request supplies model and raw target bytes but no current externally owned expected-target anchor
- **THEN** the same native checker reports unverified admission and does not self-admit or select an alternate route

### Requirement: Prompt budgets cover conditional blueprint routes
The prompt-bundle contract SHALL include every new blueprint trigger and reference edge, preserve the existing entry-byte limits and required headroom, and reject eager loading, undeclared references, duplicate trigger authority, stale generated indexes, or cross-member blueprint imports.

#### Scenario: Blueprint reference is conditionally reachable
- **WHEN** the matching selected-member blueprint trigger is present
- **THEN** the prompt checker reports the exact loaded reference, byte total, limit, and remaining headroom

#### Scenario: Blueprint text bloats the entry shell
- **WHEN** detailed blueprint instructions are embedded in an always-loaded entry and required headroom is no longer preserved
- **THEN** the prompt-bundle check fails and identifies the oversized entry
