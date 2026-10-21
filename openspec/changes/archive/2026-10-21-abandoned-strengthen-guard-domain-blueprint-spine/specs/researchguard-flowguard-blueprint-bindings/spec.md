## Purpose

Define one later-bound FlowGuard repository software-DNA hierarchy that connects ResearchGuard and its four native members to implementation, tests, intent, resources, topology, and external boundaries without becoming a second domain-model authority.

## ADDED Requirements

### Requirement: The repository has one software-DNA root and four recursively decomposed member subtrees
After the FlowGuard toolchain identity is frozen, the ResearchGuard project SHALL publish exactly one current repository software-DNA root with child subtrees for LogicGuard, SourceGuard, TraceGuard, and ExperimentGuard. The root SHALL own admission, direct and umbrella routing, composition, envelope, handoff, and authority behavior; it MUST NOT appear again as a fifth sibling child. Each member subtree SHALL continue downward into multiple concrete function blocks, public surfaces, state and side-effect owners, adapters, and supporting helpers. Every behavior-bearing function block SHALL declare its permitted behavior as `Input x State -> Set(Output x State)` and SHALL identify its code, test, intent, resource, topology, and native domain-model boundary.

#### Scenario: Current software-model hierarchy is assembled
- **WHEN** the frozen implementation inventory, repository root, and all four member subtree bindings are current
- **THEN** the root contains exactly those four member subtrees, reports its own composition responsibilities, and reports every subtree's deeper disjoint and shared owners

#### Scenario: A child is absent or duplicated
- **WHEN** one native member lacks a subtree, a subtree stops at one opaque member owner, or two owners claim the same primary implementation responsibility without a declared shared relation
- **THEN** FlowGuard blocks whole-repository blueprint qualification and exposes the missing, oversized, or duplicate owner

#### Scenario: A behavior block declares an incomplete transition contract
- **WHEN** a block names inputs and outputs but omits consumed state, successor state, permitted alternate outputs, or side effects
- **THEN** FlowGuard keeps that block incomplete and does not infer the missing `Input x State -> Set(Output x State)` relation from its implementation name

### Requirement: FlowGuard binds implementation but does not reinterpret domain semantics
Each FlowGuard member subtree SHALL reference the owning member's native schema, checks, receipts, and claim boundary while treating native domain payloads as opaque. The existing LogicGuard argument blueprint, SourceGuard information blueprint, TraceGuard investigation blueprint, and ExperimentGuard design blueprint SHALL remain member-domain DNA. They MAY supply semantic and behavioral obligations to their corresponding software subtree but MUST NOT claim whole-repository implementation coverage or become four additional repository software-DNA roots. Generic skill-maintenance contract models MUST NOT be promoted as substitutes for those member-domain models.

#### Scenario: Native member receipt is referenced
- **WHEN** a FlowGuard software child binds a member behavior to code and tests
- **THEN** it records the native owner and receipt reference without recalculating the member's professional judgment

#### Scenario: Generic contract is offered as domain proof
- **WHEN** a maintenance contract model is the only evidence supplied for a member's domain behavior
- **THEN** FlowGuard reports the native model and test binding as unresolved

#### Scenario: A native domain blueprint is complete but its implementation binding is absent
- **WHEN** a member-domain blueprint has current native closure but the repository software-DNA subtree has no current code, test, resource, or topology binding for the behavior
- **THEN** the native domain claim MAY remain current within its own boundary while repository software-DNA readiness remains incomplete

#### Scenario: Desired behavior differs from observed behavior
- **WHEN** an intent source or accepted change describes a future behavior that the current implementation and observed model do not yet realize
- **THEN** FlowGuard keeps the intent as a typed target and acceptance obligation while the sole observed implementation remains current-behavior authority until a validated model revision is activated

### Requirement: Whole-software coverage uses a complete provider-neutral implementation denominator
The software-model hierarchy SHALL consume an independently produced current implementation denominator covering the declared repository boundary, source and generated-code boundaries, skills and prompts, public CLI and API surfaces, schemas and contracts, configuration, workflows, resources, tests, intent sources, topology edges, external interfaces, and unresolved dynamic or parse findings. Every admitted item SHALL have exactly one terminal disposition, and every behavior-bearing item SHALL have exactly one primary owner; shared helpers and resources SHALL have declared supporting owners and consumer edges. Model-declared paths, contracts, a Python-only scan, or a caller-provided subset MUST NOT define the whole-software denominator.

The denominator route SHALL use one current provider-neutral adapter contract. Python syntax and test discovery MAY be supplied by one convenience adapter, but target languages, declarative formats, and workflows SHALL remain open to their own declared current adapters. An unknown adapter, unsupported schema, unparseable surface, unmapped item, ambiguous exclusion, or duplicate primary owner MUST remain an explicit gap and MUST NOT select a legacy reader, compatibility route, Python-only fallback, caller-authored subset, or automatic broad scan.

#### Scenario: Tracked implementation surface is unmapped
- **WHEN** the independent denominator contains an in-scope implementation, test, intent, resource, topology, public-surface, configuration, or non-Python item with no binding or explicit disposition
- **THEN** the suite reports that surface as unresolved and does not claim whole-software blueprint completeness

#### Scenario: Ordinary affected change is reviewed
- **WHEN** a bounded change does not request whole-software qualification
- **THEN** FlowGuard loads and revalidates only the affected blueprint neighborhood rather than rematerializing the complete project inventory

#### Scenario: A non-Python workflow is admitted
- **WHEN** a maintained workflow, schema, configuration, prompt, or resource surface is inside the repository boundary
- **THEN** its declared current adapter and owner participate in the same denominator and binding rules as Python surfaces

### Requirement: Software-DNA readiness has seven explicit layers
The repository root SHALL report the longest exact-current prefix and first unresolved gap across exactly seven readiness layers: evidence qualification, implementation inventory, traceability, independent semantics, model-code-test binding, resource-oracle binding, and static blueprint readiness. A later layer MUST NOT hide or compensate for an earlier incomplete layer. Static blueprint readiness MUST remain separate from executed-test freshness, external-resource availability, installed projection currentness, Git identity, and release currentness.

#### Scenario: Static hierarchy exists before an earlier layer closes
- **WHEN** a reconstructable hierarchy and export exist but the implementation denominator, traceability, native semantics, code/test binding, or resource/oracle binding is incomplete
- **THEN** FlowGuard reports only the longest complete readiness prefix and the first earlier gap

#### Scenario: A test is named but not bound to a behavior contract
- **WHEN** a test file is listed but its setup, input, pre-state, expected output, post-state, effect, failure class, or oracle cannot be traced to the block it claims to check
- **THEN** the model-code-test layer remains incomplete even when that test has previously passed

#### Scenario: Static blueprint is ready but release evidence is not current
- **WHEN** all seven static readiness layers are complete but required tests, installation, or release evidence is stale or not run
- **THEN** FlowGuard reports static blueprint readiness without claiming executed validation, installation, or release readiness

### Requirement: Every admitted identity is connected by forward, reverse, and affected indexes
The software-DNA root SHALL maintain exact forward and reverse relations among model blocks, implementation items, tests, intent sources, resources, topology edges, public surfaces, native domain identities, and external interfaces. It SHALL also maintain an affected index that closes from a changed identity through declared readers, writers, parents, children, consumers, tests, handoffs, resources, and topology dependents. Unknown ownership or an unknown relation MUST block affected-confidence and MUST NOT authorize `run all`.

#### Scenario: A changed helper has several declared consumers
- **WHEN** one helper identity changes and its reverse index names two behavior owners, three tests, and one resource-producing path
- **THEN** the affected index returns exactly those owners and their declared transitive dependents while unrelated subtrees retain current evidence

#### Scenario: A repository item has no reverse owner
- **WHEN** an admitted code, test, intent, resource, topology, or public-surface item cannot be traced back to one primary behavior owner or explicit supporting disposition
- **THEN** whole-DNA readiness blocks and an ordinary affected claim remains bounded to the known closure

### Requirement: Canonical self-DNA export cannot fingerprint itself
The canonical self-DNA export SHALL be deterministic, content-addressed, and materialized outside the repository boundary it describes. Generated inventories, project definitions, canonical projections, current pointers, receipts, and export metadata MUST NOT enter their own denominator or become source authority; excluding their paths from a recursive scan is insufficient. External artifacts SHALL be represented by exact owner, locator, fingerprint, availability, and claim-boundary references unless their bytes are explicitly admitted. Release archive checksums, signatures, and publication receipts SHALL remain outside the archive they authenticate.

#### Scenario: Canonical output is requested under the repository root
- **WHEN** a caller selects an export or current-pointer location inside the scanned ResearchGuard repository
- **THEN** FlowGuard blocks canonical publication and identifies the self-fingerprint boundary violation

#### Scenario: An external resource is not materialized
- **WHEN** a dataset, executable, model, source artifact, or other external dependency is referenced but its exact bytes are outside the admitted boundary
- **THEN** the export preserves its identity, owner, locator, fingerprint, and unavailable or unverified status without copying or inventing the resource

### Requirement: Architecture reduction requires proof-ready affected contracts
FlowGuard SHALL treat duplicate, dead-path, adapter, helper, handler, facade, and validation-layer findings as reduction candidates until the affected observable contract, primary owner, target disposition, reverse and affected closures, native evidence, and required parity checks are current. It MUST NOT delete or merge paths based only on names, size, similarity, or an incomplete blueprint. Accepted reductions SHALL revalidate the affected closure and SHALL participate in one whole-DNA and release gate only after the integration snapshot is frozen. Compatibility readers, aliases, dual emission, and fallback paths MUST NOT be used to hide an unresolved reduction.

#### Scenario: Two handlers appear equivalent but proof is incomplete
- **WHEN** two paths look duplicate but one public effect, failure state, consumer, or test binding is unresolved
- **THEN** FlowGuard retains both paths and records the unresolved candidate rather than contracting them

#### Scenario: A reduction has current equivalence evidence
- **WHEN** one candidate has a complete observable contract, target owner, removal disposition, affected closure, and parity evidence
- **THEN** the owning structure and lifecycle routes MAY contract it and must regenerate the affected software-DNA evidence before release qualification

### Requirement: Projection waits for a stable FlowGuard toolchain
No new FlowGuard suite projection, observed snapshot, revision, activation, or project-record update SHALL be produced until the exact FlowGuard package, imported source, schema, command implementation, and relevant consumer-skill identities are frozen and peer modifications affecting them are settled. A preview from a mutable toolchain MAY inform planning but MUST NOT authorize activation.

#### Scenario: Installed version comes from a mutable editable checkout
- **WHEN** the imported FlowGuard package reports the target version but its source checkout has unsettled peer modifications
- **THEN** the project defers writing the upgrade and reruns the non-mutating preview after the toolchain is frozen

#### Scenario: Frozen preview remains unchanged
- **WHEN** the frozen toolchain's project-upgrade preview has no blockers and the exact proposed files and semantic changes are accepted
- **THEN** the project may update only those declared records before affected revalidation

### Requirement: The released FlowGuard dependency has one public immutable authority
The ResearchGuard package and its CI workflow SHALL resolve the same exact publicly retrievable FlowGuard release identity. A version range that cannot be obtained from its declared package source, a mutable local checkout, a different CI-only source, an old-version downgrade, an optional skip, or a retry/fallback dependency path MUST NOT satisfy installation or release readiness. If the official package distribution is unavailable, ResearchGuard MAY bind one immutable public Git commit/tag or one immutable release artifact directly, provided clean Windows, Linux, CI, and end-user installation resolve that same identity.

#### Scenario: The declared package range is absent from its package index
- **WHEN** clean dependency resolution cannot retrieve the declared FlowGuard version range from the configured public package source
- **THEN** ResearchGuard release readiness is blocked until the dependency contract names one actually retrievable immutable public authority
- **AND** it does not downgrade, use a local path, skip FlowGuard, or select a second CI-only source

#### Scenario: One frozen public FlowGuard identity is resolvable everywhere
- **WHEN** package metadata and CI both bind the same immutable public FlowGuard release identity and clean Windows and Linux installation reproduce it
- **THEN** dependency availability may pass as its own lifecycle gate without being treated as software-DNA static-depth evidence

### Requirement: Model revisions and activation preserve exact freshness
FlowGuard SHALL build a new immutable revision from the exact current parent, child bindings, implementation inventory, and native owner evidence, persist its evidence before changing the sole observed pointer, and activate it only after every affected obligation has current terminal proof. Hash-named snapshots, revisions, and activations SHALL be generated by the current toolchain rather than edited manually.

#### Scenario: Child binding changes after revision build
- **WHEN** a child code, test, model, or receipt fingerprint changes after a candidate revision is built
- **THEN** activation blocks as stale and a new affected revision is required

#### Scenario: Activation succeeds
- **WHEN** every affected child and parent obligation has current evidence against one frozen source and toolchain identity
- **THEN** FlowGuard writes the new observed pointer last and retains the prior immutable authority for declared recovery

### Requirement: FlowGuard evidence and peer work remain isolated
Implementation and validation SHALL preserve concurrent peer work and SHALL not delete, overwrite, adopt, or manufacture authority from pre-existing untracked evidence. Unknown-writer changes affecting an owned path MUST be re-read and reconciled before writing.

#### Scenario: Untracked evidence belongs to another worker
- **WHEN** the project contains an untracked FlowGuard evidence subtree outside the change's declared write set
- **THEN** the blueprint implementation leaves it untouched and excludes it from newly claimed evidence
