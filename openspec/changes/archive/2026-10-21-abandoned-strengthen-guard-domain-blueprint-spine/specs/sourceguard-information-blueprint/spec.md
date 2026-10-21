## Purpose

Define one SourceGuard-owned information blueprint that connects target units, evidence gaps, search actions, source identities, anchors, claim uses, impact, and reverse trace through a single validated typed graph.

## ADDED Requirements

### Requirement: One typed graph is the SourceGuard model authority
SourceGuard SHALL load, validate, store, update, and export graph relations through one current typed edge schema. Every edge MUST have a stable identity, permitted endpoint types, resolvable endpoints, and one current relation type. Raw or unvalidated mapping edges MUST NOT become a parallel model authority.

#### Scenario: Typed graph loads successfully
- **WHEN** every edge has a permitted relation and both endpoints resolve to compatible current objects
- **THEN** SourceGuard accepts the graph as the sole relationship authority

#### Scenario: Edge endpoint is missing or incompatible
- **WHEN** an edge points to an absent object or connects object types not allowed by its relation
- **THEN** SourceGuard rejects the model at load time and identifies the offending edge

#### Scenario: Raw edge bypass is attempted
- **WHEN** a caller supplies a relationship shape that is not part of the current typed edge schema
- **THEN** SourceGuard rejects it rather than preserving it for a later helper to interpret

### Requirement: The information blueprint closes explicit parent-child interfaces
SourceGuard SHALL model the chain from objective and target unit through gap, required source role, search action, source, evidence anchor, and claim-use or handoff. Each parent obligation MUST consume the exact typed output of its child or preserve an explicit unresolved disposition.

#### Scenario: Gap is closed by qualified anchors
- **WHEN** a gap's required roles and lineage obligations are satisfied by current qualified source and anchor outputs
- **THEN** SourceGuard records the exact consumed outputs and closure boundary for that gap

#### Scenario: Search result is not consumed
- **WHEN** a search action returns a source or anchor that no declared gap, claim-use, or handoff consumes
- **THEN** SourceGuard records it as an unconsumed candidate and does not count it toward closure

### Requirement: Source and anchor identities bind retrieved content
Every source used for blueprint closure SHALL bind its source identity, content fingerprint, retrieval request fingerprint, provider identity and revision, access time, lineage, and source role. Every evidence anchor used for closure SHALL bind its locator, exact anchor-content fingerprint, source-content fingerprint, extractor identity and revision, observation time, and support and limitation boundary.

#### Scenario: Same URL returns changed content
- **WHEN** a previously used URL resolves to a different content fingerprint
- **THEN** SourceGuard treats the affected source and anchors as changed and reopens only their consuming obligations

#### Scenario: Extractor revision changes an anchor
- **WHEN** the extractor identity or revision changes and produces a different anchor fingerprint
- **THEN** SourceGuard invalidates the affected anchor uses and does not reuse the former qualification silently

### Requirement: Source completeness uses a complete independent universe
SourceGuard SHALL bind one independently fingerprinted universe containing required target units, gaps, source roles, lineage slots, anchor or bridge requirements, and handoff obligations. The contained graph MUST NOT define its own completeness denominator.

#### Scenario: Required source role is omitted
- **WHEN** the independent universe requires a primary or independent source role absent from the graph
- **THEN** SourceGuard keeps the corresponding gap open even if all contained graph nodes are internally connected

#### Scenario: Declared exclusion hides an active gap
- **WHEN** an excluded target unit or role is still required by an active gap
- **THEN** SourceGuard rejects the exclusion and blocks broad information-blueprint closure

### Requirement: Source impact and reverse trace are affected-only
SourceGuard SHALL provide member-native check, impact, reverse-trace, and deterministic export operations. Impact and reverse trace SHALL each consume exactly one current native blueprint qualification for the same graph, target material, authority, purpose receipt, and contract bytes. Failed, stale, unverified, or not-run qualification MUST atomically suppress ordinary affected/unaffected output and MUST keep reverse trace incomplete. Once admitted, a source or anchor change SHALL invalidate only the qualifications, gaps, stop decisions, claim uses, and member handoffs that consume it, while unknown dependency ownership SHALL remain a visible blocker.

#### Scenario: One anchor changes
- **WHEN** one anchor fingerprint changes and only two gaps consume it
- **THEN** those gaps and their dependent stop decisions and handoffs become stale while unrelated branches retain current status

#### Scenario: Claim use is reverse traced
- **WHEN** a caller traces one source-backed claim use
- **THEN** SourceGuard identifies the target unit, gap, source-role obligation, search action, source revision, anchor locator and fingerprint, qualification, and handoff references

#### Scenario: Blueprint round trip is stable
- **WHEN** a current information blueprint is exported and reloaded without semantic changes
- **THEN** its target universe, typed graph, source and anchor identities, gap status, stop boundary, and fingerprint remain identical

### Requirement: SourceGuard does not become the final reasoning owner
SourceGuard SHALL report discovery value, source identity, anchor qualification, limitations, and information gaps. It MUST NOT convert those results into final argument truth, a completed temporal storyline, a causal conclusion, or a shared cross-Guard confidence score.

#### Scenario: Final argument judgment is requested
- **WHEN** a caller asks whether the discovered evidence proves an argument conclusion
- **THEN** SourceGuard returns its bounded source and anchor result and hands final argument evaluation to LogicGuard
### Requirement: Information denominator is replayed from an external expected-target anchor

Before SourceGuard models the target, one provider-neutral externally owned expected-target anchor SHALL freeze the original task/request identity, target identity and revision, exact raw target-tree locator and fingerprint, admission owner/producer, admission input/result identities, and immutable admission-receipt identity. Umbrella admission MAY produce the anchor from original task facts; direct member use MUST receive it externally and MUST remain unverified when it is absent or unavailable.

SourceGuard SHALL parse target units, ports, interfaces, gap/source-role/lineage/anchor/handoff obligations, cases, and failure classes only from the exact bytes named by that anchor through its closed current guard-contract/target parser on initial check and serialized reload. Private target authority SHALL bind the anchor identity and exact material fingerprint. Production MUST NOT expose a public target-authority issuer, arbitrary locator route, inline target-material authoring helper, or graph/universe-to-target helper. Every model, interface, purpose, contract, and owner receipt used for qualification MUST resolve from immutable producer bytes and bind its producer, request, input, result, model, checker, task, status, locator, and receipt fingerprint. Caller-controlled graph/universe rows, process memory, self-fingerprinted authority, caller-invented receipt ids, and receipt self-hashes SHALL NOT substitute for external admission or producer evidence.

#### Scenario: Blueprint query has no current qualification
- **WHEN** impact or reverse trace receives failed, stale, unverified, or not-run target material, authority, purpose receipt, or contract replay
- **THEN** SourceGuard returns the exact qualification gaps, no ordinary affected/unaffected set, and no complete reverse-trace terminal

#### Scenario: Unknown claim use cannot bypass a failed qualification
- **WHEN** reverse trace receives an unknown claim-use id while its one current native qualification is not complete
- **THEN** SourceGuard returns an atomic rejected report before claim-use, edge, anchor, closure, or target-ancestry resolution, with all ordinary information-chain and terminal fields empty

#### Scenario: Target hierarchy and raw target bytes are coherently shrunk
- **WHEN** a caller removes the same child target unit and interface from the target hierarchy, universe, and raw target bytes, recomputes every caller-controlled identity, and retains the originally admitted expected-target anchor
- **THEN** exact anchor replay fails, SourceGuard does not complete the information blueprint, and ordinary impact and reverse-trace output is suppressed

#### Scenario: Caller invents a SourceGuard receipt
- **WHEN** a coherent-looking model, interface, purpose, contract, or owner receipt cannot be reopened from its declared immutable producer locator
- **THEN** SourceGuard rejects it as unresolved even when its caller-computed fingerprint is internally consistent

#### Scenario: Direct member has no external anchor
- **WHEN** SourceGuard is invoked directly without a provider-owned expected-target anchor
- **THEN** target qualification is unverified and SourceGuard does not treat the submitted graph or universe as its own target

#### Scenario: Source target snapshot reloads in a new process
- **WHEN** a serialized information blueprint still references an unchanged external expected-target anchor and immutable receipt locators
- **THEN** SourceGuard re-parses the same denominator and receipts without a process cache; external or unavailable material remains explicitly unverified

#### Scenario: Alternate information target has a new anchor
- **WHEN** a different information target is separately admitted under a new external expected-target anchor
- **THEN** SourceGuard may replay that exact target while rejecting any attempt to reuse the earlier anchor

### Requirement: The information blueprint remains member-domain DNA
The SourceGuard blueprint SHALL own target-unit, gap, search, source, anchor, claim-use, lineage, and native closure semantics. It MAY be referenced by the ResearchGuard repository software-DNA subtree as semantic evidence, but it MUST NOT by itself claim complete repository code, test, intent, resource, topology, installation, or release coverage and MUST NOT become a competing whole-repository software blueprint.

#### Scenario: Native information closure precedes its software binding
- **WHEN** an information blueprint has current native closure but its implementing surfaces, tests, providers, resources, or repository ownership bindings are incomplete
- **THEN** SourceGuard MAY retain its bounded domain result while ResearchGuard software-DNA readiness remains incomplete
