## Purpose

Define a hierarchical, executable experiment-design blueprint that preserves ExperimentGuard's finite hypothesis-discrimination semantics while making procedures, interfaces, constraints, evidence, and revision impact explicit.

## ADDED Requirements

### Requirement: Experiment designs have one closed hierarchy
ExperimentGuard SHALL represent an experiment-design blueprint with one declared root, explicit parent and child blocks, and stable blocks for purpose, hypothesis families, discrimination obligations, candidate experiments, procedure steps, constraints, and outcomes. Every non-root block MUST have exactly one declared parent within the blueprint, and every declared child MUST exist.

#### Scenario: Hierarchical experiment design is valid
- **WHEN** every non-root design block has one parent, every child reference resolves, and the hierarchy is acyclic
- **THEN** ExperimentGuard accepts the hierarchy for native blueprint checking

#### Scenario: Design hierarchy is incomplete
- **WHEN** a block is orphaned, multiply parented, missing, or part of a cycle
- **THEN** ExperimentGuard blocks blueprint completion and identifies the exact relation

### Requirement: Candidate experiments expose typed procedure interfaces
Every candidate experiment SHALL declare its input, manipulation, observation, and outcome ports; ordered procedure steps; material constraints; and external execution owner. Parent blocks MUST consume required child outputs or record an explicit unresolved or excluded disposition. ExperimentGuard SHALL recommend experiments but MUST NOT execute the external procedure or claim that the external owner completed it.

#### Scenario: Candidate interface closes
- **WHEN** a candidate declares all required ports and procedure steps and its parent consumes the required outcome ports
- **THEN** the candidate can participate in native recommendation and blueprint qualification

#### Scenario: Manipulation or observation port is missing
- **WHEN** a candidate cannot identify what is changed or what is observed
- **THEN** ExperimentGuard reports an interface gap and does not qualify that candidate as a complete experiment design

#### Scenario: External procedure remains external
- **WHEN** ExperimentGuard recommends a candidate with an external execution owner
- **THEN** the result contains the owner and required inputs but records the experiment itself as not run until external evidence is supplied

### Requirement: The recommendation matrix and design blueprint share one identity
The current finite hypothesis-by-experiment prediction matrix SHALL reference the same hypothesis, candidate-experiment, observation-port, and outcome identities declared by the design blueprint. ExperimentGuard MUST reject missing, foreign, ambiguous, or stale identities and MUST NOT maintain a second recommendation matrix disconnected from the design.

#### Scenario: Matrix and design agree
- **WHEN** every matrix row and outcome resolves to a current design identity
- **THEN** the existing finite recommendation engine uses that same identity set

#### Scenario: Matrix references an undeclared candidate
- **WHEN** a prediction refers to an experiment or outcome that is absent from the current design blueprint
- **THEN** ExperimentGuard blocks before recommendation and reports the unresolved identity

### Requirement: Experiment completeness uses an independent target universe
ExperimentGuard SHALL bind the blueprint to a task-local purpose contract and an independently fingerprinted universe of required hypotheses, discrimination obligations, candidates, ports, constraints, and failure cases. The blueprint MUST NOT derive its completeness denominator only from the objects it already contains.

#### Scenario: Required hypothesis is omitted
- **WHEN** the independent universe declares a required hypothesis that is absent from the blueprint
- **THEN** blueprint qualification remains incomplete even if the contained matrix is internally consistent

#### Scenario: Known-bad design is not rejected
- **WHEN** a declared task-local known-bad case passes the proposed blueprint and native oracle
- **THEN** ExperimentGuard blocks the purpose proof and does not publish a complete blueprint envelope

### Requirement: Experiment blueprint operations are native and deterministic
ExperimentGuard SHALL provide member-native check, impact, reverse-trace, and deterministic export operations over the same current design and recommendation identities. Impact and reverse trace SHALL each consume exactly one current native blueprint qualification for the same model, target material, authority, and receipts. A failed, stale, unverified, or not-run qualification MUST atomically suppress ordinary affected/unaffected output and MUST keep reverse trace incomplete. Serialization and reload MUST preserve the model fingerprint, recommendation result, open gaps, and claim boundary.

#### Scenario: Blueprint round trip is stable
- **WHEN** a current experiment blueprint is exported and loaded without semantic changes
- **THEN** its fingerprint, finite recommendation, unresolved hypothesis pairs, and claim boundary remain identical

#### Scenario: One prediction changes
- **WHEN** one hypothesis prediction or candidate outcome changes
- **THEN** the impact result identifies the exact affected hypothesis pairs, candidate sets, observations, holdout status, and receipts while leaving unrelated obligations current

#### Scenario: Recommendation is reverse traced
- **WHEN** a caller traces one recommended experiment
- **THEN** ExperimentGuard identifies the discriminated hypothesis pairs, differing outcomes, candidate output ports, procedure block, and supporting external observation references
### Requirement: Child result consumption and externally admitted target authority are independently replayable

ExperimentGuard SHALL bind every consumed child observation or outcome to one parent input with exact endpoint, schema, refinement, payload, producer-model, producer-result, task, and current immutable receipt identities. Before ExperimentGuard models the task, one provider-neutral externally owned expected-target anchor SHALL freeze the original task/request identity, target identity and revision, exact raw target-material locator and fingerprint, admission owner/producer, admission input/result identities, and immutable admission-receipt identity. Umbrella admission MAY produce the anchor from the original task facts; direct member use MUST receive it externally and MUST remain unverified when it is absent or unavailable.

The current closed ExperimentGuard adapter SHALL parse only the raw bytes named by that anchor on initial check and serialized reload. Private target authority SHALL bind the anchor identity and exact material fingerprint. Production MUST NOT expose a public target-authority issuer, arbitrary locator route, inline target-material authoring helper, or candidate-to-target helper. Every model, interface, depth, and owner receipt used for qualification MUST resolve from immutable producer bytes and bind its producer, request, input, result, model, checker, task, status, locator, and receipt fingerprint. The denominator and receipts MUST NOT be derived from submitted design/universe rows, an authority or receipt self-hash, a caller-invented receipt id, or process-local memory.

#### Scenario: Blueprint query has no current qualification
- **WHEN** impact or reverse trace receives failed, stale, unverified, or not-run target material, authority, or native receipt evidence
- **THEN** ExperimentGuard returns the exact qualification gaps, no ordinary affected/unaffected set, and no complete reverse-trace terminal

#### Scenario: Unknown experiment cannot bypass a failed qualification
- **WHEN** reverse trace receives an unknown experiment id while its one current qualification is not complete
- **THEN** ExperimentGuard returns an atomic rejected report before experiment lookup, with ordinary design, path, port, binding, and terminal fields empty and no target-resolution exception

#### Scenario: Design universe and raw target bytes are coherently shrunk
- **WHEN** a caller removes the same material constraint from the design, target universe, and raw target bytes, recomputes every caller-controlled identity, and retains the originally admitted expected-target anchor
- **THEN** exact anchor replay fails, ExperimentGuard reports an incomplete blueprint, and impact and reverse trace expose no ordinary result

#### Scenario: Caller invents a native receipt
- **WHEN** a caller supplies a coherent-looking interface, depth, model, or owner receipt id and self-hash that cannot be reopened from its declared immutable producer locator
- **THEN** ExperimentGuard rejects the receipt as unresolved and keeps qualification incomplete

#### Scenario: Direct member has no external anchor
- **WHEN** ExperimentGuard is invoked directly without a provider-owned expected-target anchor
- **THEN** target qualification is unverified and ExperimentGuard does not admit the submitted design as its own target

#### Scenario: Serialized alternate target is replayable
- **WHEN** a different exact current request/revision is admitted as a new externally owned expected-target anchor and its blueprint is serialized and loaded in a new process
- **THEN** the current adapter can replay that separately admitted target without any fixture-specific target id, while missing, changed, or externally unreplayable anchor or receipt material remains blocked or unverified

### Requirement: The experiment blueprint remains member-domain DNA
The ExperimentGuard blueprint SHALL own experiment-design meaning, discrimination obligations, procedure interfaces, observation requirements, external execution boundaries, and native closure. It MAY be referenced by the ResearchGuard repository software-DNA subtree as semantic evidence, but it MUST NOT by itself claim complete repository code, test, intent, resource, topology, installation, or release coverage and MUST NOT become a competing whole-repository software blueprint.

#### Scenario: Native design closes before its software binding
- **WHEN** an experiment design has current native closure but the implementing adapter, tests, external executor, or repository ownership binding is missing
- **THEN** ExperimentGuard MAY retain its bounded domain result while ResearchGuard software-DNA readiness remains incomplete
