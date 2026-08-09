## ADDED Requirements

### Requirement: Member iterations publish current blueprint lineage
Every non-trivial LogicGuard, SourceGuard, TraceGuard, or ExperimentGuard iteration SHALL publish the member's current native model and schema identities, model fingerprint, externally admitted expected-target anchor identity, independently fingerprinted target universe, exact affected obligation ids, immutable resolved native receipt lineage, deepest proven blueprint layer, first unresolved gap, and bounded claim boundary. ResearchGuard SHALL transport these identities without replacing the member's terminal semantics. A receipt name or caller-computed fingerprint without resolvable immutable producer bytes MUST remain an evidence gap.

#### Scenario: Member advances one blueprint layer
- **WHEN** a member closes its current first unresolved gap with new native evidence
- **THEN** the next iteration records the predecessor receipt, changed obligations, new deepest proven layer, remaining first gap, and current model fingerprint

#### Scenario: Later layer is present before an earlier layer closes
- **WHEN** a member has export or reconstruction material but an earlier inventory, interface, semantic, binding, or evidence layer is incomplete
- **THEN** the member reports the longest complete prefix and the first earlier gap rather than promoting the later material to blueprint completion

### Requirement: Member revision impact is exact and affected-only
Each member SHALL derive the exact native obligations, parent and child interfaces, evidence bindings, outputs, tests, and handoffs affected by a model revision. Unaffected obligations MAY retain exact-current evidence; unknown ownership or unknown impact MUST remain a blocker and MUST NOT cause a shared `run all` fallback.

#### Scenario: One native leaf changes
- **WHEN** a revision changes one model leaf with declared parent and downstream consumers
- **THEN** the member marks only that leaf, its affected ancestors, declared consumers, and bound evidence as stale

#### Scenario: Impact ownership is unknown
- **WHEN** a changed object has no current dependency owner or binding
- **THEN** the member reports an impact-ownership gap and does not claim affected-only closure or execute every check automatically

### Requirement: Native closure remains the only domain authority
A blueprint envelope, hierarchy projection, export, understanding-status display, FlowGuard software binding, or suite aggregate SHALL NOT close a member task unless the current native member receipt closes every obligation required by that task's claim boundary.

#### Scenario: Blueprint structure is complete but native receipt is blocked
- **WHEN** all declared hierarchy and interface checks pass but the member's native depth or semantic receipt remains blocked
- **THEN** the iteration remains blocked and no structural or suite-level artifact upgrades it to closed

#### Scenario: Native closure is current
- **WHEN** the member's current native receipt closes the task and all required blueprint lineage identities match
- **THEN** the member may publish its bounded terminal and current envelope without creating a suite-level understanding score

#### Scenario: Native receipt identity was never published
- **WHEN** an iteration supplies an internally consistent receipt reference whose immutable producer bytes cannot be resolved for the same anchor, task, request, input, model, checker, result, and status
- **THEN** the iteration keeps native closure incomplete and publishes the unresolved receipt gap
