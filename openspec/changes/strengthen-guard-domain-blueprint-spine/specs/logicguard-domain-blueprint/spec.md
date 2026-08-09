## Purpose

Define a LogicGuard-owned argument and artifact blueprint whose hierarchy, block interfaces, independent target inventory, evidence bindings, impact, and reverse trace can be checked without weakening native reasoning semantics.

## ADDED Requirements

### Requirement: Argument blocks have explicit producer-consumer interfaces
LogicGuard SHALL bind every material child-block output used by a parent to one declared parent input, with stable block, node, classification, scope, and consumer identities. Every required parent input MUST have one permitted producer, and every material child output MUST be consumed or carry an explicit unresolved, excluded, or intentionally terminal disposition.

#### Scenario: Child output feeds parent input
- **WHEN** a child output claim and parent input node have a current compatible binding
- **THEN** LogicGuard includes that binding in the parent closure proof

#### Scenario: Public parent-child realization replays leaf evidence
- **WHEN** the public purpose-backed blueprint check receives a real parent/child block interface, current native depth, and exact current leaf receipt bytes
- **THEN** it closes the realization binding only for the exact producer/result/model/task receipt, while missing, stale, foreign, or never-published leaf receipts produce the exact realization gap

#### Scenario: Required parent input has no producer
- **WHEN** a parent block requires an input that no current child, source, or declared external input produces
- **THEN** LogicGuard reports the exact interface gap and blocks blueprint completion for that parent

#### Scenario: Material child output is silently dropped
- **WHEN** an important child output is neither consumed nor explicitly dispositioned
- **THEN** LogicGuard keeps the output visible as an unresolved structural-contribution gap

### Requirement: Artifact containment and argument reasoning have distinct owners
LogicGuard SHALL maintain one authoritative artifact-unit containment hierarchy and one authoritative argument-block hierarchy, connected by typed realization bindings. It MUST reject conflicting ownership projections and MUST NOT treat a document section, an argument block, and a reasoning node as interchangeable solely because they share an identifier or title.

#### Scenario: Artifact unit realizes an argument block
- **WHEN** one artifact unit is declared to realize one argument block
- **THEN** LogicGuard preserves both identities and validates their typed binding without merging their hierarchy ownership

#### Scenario: Competing parent projections disagree
- **WHEN** two authoritative fields assign incompatible parents to the same artifact unit or argument block
- **THEN** LogicGuard blocks the durable blueprint rather than reducing the conflict to a warning

### Requirement: Artifact completeness uses an independent inventory
LogicGuard SHALL consume an independently fingerprinted inventory of required artifact units, their containment relations, locators, parse dispositions, and content identities. A model MUST NOT qualify itself as complete by counting only its own cards, nodes, or blocks.

#### Scenario: Inventory unit is absent from the model
- **WHEN** a required artifact unit appears in the independent inventory but has no model binding or explicit disposition
- **THEN** the blueprint reports that unit as missing and does not claim complete artifact coverage

#### Scenario: Unparsed format remains visible
- **WHEN** an inventory provider cannot parse a required document unit or asset
- **THEN** LogicGuard preserves a typed parse gap and does not infer the unit's argument content

### Requirement: Structural and content reconstruction claims are separate
LogicGuard SHALL distinguish structural-blueprint completeness from content-blueprint completeness. Structural completeness MAY support reconstruction of the artifact hierarchy and argument responsibilities; exact prose, citation placement, layout, visual assets, or page structure SHALL require their own current content and resource bindings.

#### Scenario: Structure is complete but content is not captured
- **WHEN** every artifact unit and argument interface is modeled but exact content or layout fingerprints are missing
- **THEN** LogicGuard may license structural reconstruction and MUST reject an exact-content reconstruction claim

#### Scenario: Content identity changes
- **WHEN** a bound artifact unit's content fingerprint changes
- **THEN** the unit and its declared argument consumers become stale while unrelated units remain current

### Requirement: Logic blueprint impact and reverse trace are native
LogicGuard SHALL provide member-native check, impact, reverse-trace, and deterministic export operations over the same current argument, artifact, source, citation, ModelMesh, and receipt identities. Impact and reverse trace SHALL each consume exactly one current blueprint qualification for the same model, artifact material, authority, bindings, and required depth receipt. A failed, stale, unverified, or not-run qualification MUST suppress ordinary affected/unaffected output and MUST keep reverse trace incomplete. A reverse trace SHALL connect an artifact unit or conclusion to its argument block, claim, support, warrant, assumptions, opposition, evidence, and source references.

#### Scenario: Leaf claim changes
- **WHEN** one bound leaf claim or source changes
- **THEN** LogicGuard identifies the exact affected blocks, parent interfaces, citations, artifact units, overlays, synthesis projections, and receipts

#### Scenario: Final unit is reverse traced
- **WHEN** a caller traces a conclusion-bearing artifact unit
- **THEN** LogicGuard returns its argument block, output claim, supporting and opposing relations, assumptions, boundaries, citations, sources, and current receipt references

#### Scenario: Blocked reverse trace reports each qualification gap once
- **WHEN** LogicGuard rejects reverse trace because structural or native-depth qualification is incomplete
- **THEN** `trace_gaps` contains one sorted copy of the qualification gaps and `native_depth_gaps` is only the typed native-depth subset, with no duplicate promoted gap

#### Scenario: Blueprint round trip is stable
- **WHEN** a structurally complete blueprint is exported and reloaded without semantic changes
- **THEN** its artifact hierarchy, argument hierarchy, interface bindings, claim graph, gaps, and fingerprint remain identical
### Requirement: Artifact denominator is fixed by an external expected-target anchor

Before LogicGuard models the artifact, one provider-neutral externally owned expected-target anchor SHALL freeze the original task/request identity, artifact target identity and revision, exact raw artifact-material locator and fingerprint, admission owner/producer, admission input/result identities, and immutable admission-receipt identity. Umbrella admission MAY produce the anchor from original task facts; direct member use MUST receive it externally and MUST remain unverified when it is absent or unavailable.

LogicGuard SHALL parse the artifact-unit, containment, resource-role, and resource denominator only from the exact bytes named by the supplied anchor through its closed current artifact adapter on initial check and serialized reload. Private target authority SHALL bind the anchor identity and exact material fingerprint. Production MUST NOT expose a public target-authority issuer, arbitrary locator route, inline target-material authoring helper, or inventory-to-target helper. Every model, block-interface, leaf, native-depth, and owner receipt used for qualification MUST resolve from immutable producer bytes and bind its producer, request, input, result, model, checker, task, status, locator, and receipt fingerprint. Submitted inventory rows, process-local memory, self-fingerprinted authority, caller-invented receipt ids, and receipt self-hashes SHALL NOT establish independent completeness.

#### Scenario: Blueprint query has no current qualification
- **WHEN** impact or reverse trace receives failed, stale, unverified, or not-run artifact material, authority, binding, or required depth evidence
- **THEN** LogicGuard returns the exact qualification gaps, no ordinary affected/unaffected set, and no complete reverse-trace terminal

#### Scenario: Unknown artifact cannot bypass structural and native-depth admission
- **WHEN** reverse trace receives an unknown artifact id while structural status is incomplete or required native depth is not current
- **THEN** LogicGuard returns an atomic rejected report before artifact/binding lookup or node traversal, with ordinary artifact, node, edge, evidence, resource, receipt-terminal, and path fields empty

#### Scenario: Inventory and raw artifact bytes are coherently shrunk
- **WHEN** a caller removes the same citation resource and role from the inventory, realization, and raw target bytes, recomputes every caller-controlled identity, and retains the originally admitted expected-target anchor
- **THEN** exact anchor replay fails and LogicGuard preserves an incomplete result with ordinary impact and reverse-trace output suppressed

#### Scenario: Caller invents a LogicGuard receipt
- **WHEN** a coherent-looking block-interface, leaf, native-depth, model, or owner receipt cannot be reopened from its declared immutable producer locator
- **THEN** LogicGuard rejects it as unresolved even when its caller-computed fingerprint is internally consistent

#### Scenario: Direct member has no external anchor
- **WHEN** LogicGuard is invoked directly without a provider-owned expected-target anchor
- **THEN** artifact qualification is unverified and LogicGuard does not treat the submitted inventory as its own target

#### Scenario: Artifact target material is not replayable
- **WHEN** the anchor or receipt locator is external, missing, changed, or cannot be parsed by the current LogicGuard adapter or resolver
- **THEN** LogicGuard reports failed or unverified target or receipt material and does not infer a denominator or receipt from submitted rows

#### Scenario: Alternate artifact target has a new anchor
- **WHEN** a different artifact target is separately admitted under a new external expected-target anchor
- **THEN** LogicGuard may replay that exact target while rejecting any attempt to reuse the earlier anchor

### Requirement: The argument blueprint remains member-domain DNA
The LogicGuard blueprint SHALL own argument, artifact, claim-support, interface, evidence-role, and native closure semantics. It MAY be referenced by the ResearchGuard repository software-DNA subtree as semantic evidence, but it MUST NOT by itself claim complete repository code, test, intent, resource, topology, installation, or release coverage and MUST NOT become a competing whole-repository software blueprint.

#### Scenario: Native reasoning closes before its software binding
- **WHEN** an argument and artifact blueprint has current native closure but its implementing surfaces, tests, resources, or repository ownership bindings are incomplete
- **THEN** LogicGuard MAY retain its bounded domain result while ResearchGuard software-DNA readiness remains incomplete
