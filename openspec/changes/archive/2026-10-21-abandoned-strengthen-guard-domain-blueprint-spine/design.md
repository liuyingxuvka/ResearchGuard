## Context

See `proposal.md` for motivation. ResearchGuard v0.4.1 is one Python distribution with five maintained skill surfaces: the ResearchGuard umbrella plus independently invokable LogicGuard, SourceGuard, TraceGuard, and ExperimentGuard members. The umbrella already selects the minimum sufficient member set and supports explicit multi-member composition; it must retain that current behavior.

The four members already own substantial but different native models:

- LogicGuard owns H-WADF argument semantics, `ArgumentBlock` hierarchy, native depth receipts, artifact projections, and ModelMesh invalidation.
- SourceGuard owns POMDP-style evidence-discovery planning, source and anchor qualification, gaps, stop decisions, and task iteration. A typed `GraphEdge` exists, but the persisted belief state still accepts raw mapping edges.
- TraceGuard owns its source/evidence/entity/event/trace/hypothesis/causal schema and one canonical constrained inference path. Its hierarchy is currently implicit across object references and prompt guidance.
- ExperimentGuard owns a strict finite hypothesis-by-experiment prediction matrix, minimum distinguishing-set recommendation, externally supplied observations, model-miss handling, and holdout closure. It does not yet model the procedure and ports of a candidate experiment.

The current FlowGuard project record names version 0.68.2 while the available imported package reports 0.68.6 from an editable FlowGuard checkout with active peer modifications. A 0.68.6 `project-upgrade --dry-run` currently reports no artifact migration, no blocker, no managed-rule semantic change, and four proposed project-record files, but that preview is planning evidence only until the FlowGuard source and toolchain identities are frozen.

The existing FlowGuard observed snapshot contains one suite-level model whose boundary is routing, installation, migration, and authority topology. Generic per-skill contract models describe SkillGuard maintenance surfaces and are not member domain models. The new domain-blueprint spine therefore extends native owners first and projects their implementation into FlowGuard only after native schemas, tests, and the external FlowGuard toolchain are stable.

## Goals / Non-Goals

**Goals:**

- Deliver one end-to-end blueprint spine in which every native member has a hierarchical, fingerprinted, independently bounded model with explicit interfaces, native check/impact/trace/export operations, and current receipt lineage.
- Let ResearchGuard compose exact member identities and typed handoffs while keeping member payloads opaque.
- Preserve one native semantic owner and one native execution/check path per member.
- Compute affected-only invalidation and bidirectional traceability from declared native dependencies.
- Keep prompt entry shells small by loading blueprint guidance only for a selected member and operation.
- Add one later FlowGuard repository software-DNA root with four recursively decomposed member subtrees that bind the new capability to code, tests, intent, resources, and topology without becoming a member-domain authority.
- Make software-DNA readiness explicit across seven independently checkable layers and expose the first unresolved layer instead of reducing understanding to one score.
- Keep ordinary work affected-only while reserving whole-repository inspection for
  explicit software-DNA qualification, architecture reduction, and release
  gates. The native directory remains the DNA; transport projections are not a
  second authority.
- Keep implementation, SkillGuard maintenance, installation, release, and archive evidence as separate freshness stages.

**Non-Goals:**

- A shared cross-Guard node ontology, scoring model, solver, confidence number, closure algorithm, or universal domain payload.
- An umbrella interpretation of LogicGuard, SourceGuard, TraceGuard, or ExperimentGuard results.
- Automatic sibling invocation, `run all`, retry, alias, compatibility reader, legacy parser, or fallback route.
- Exact claims about prose, page layout, external source files, physical
  apparatus, or every target resource require an owning native blueprint and
  explicit bindings; an unbound resource remains a visible gap.
- Replacing SourceGuard with LogicGuard's source library, replacing TraceGuard with a formal SCM, or replacing ExperimentGuard with PhysicsGuard or external execution infrastructure.
- Treating the FlowGuard self-model, prompt text, a generic SkillGuard contract, or an export projection as native semantic proof.
- Five overlapping whole-repository blueprints, one for each maintained skill surface, or a single opaque member child that does not decompose into concrete behavior owners.
- Restricting the repository denominator to Python. Python introspection is a convenience adapter; maintained non-Python code, prompts, schemas, configuration, resources, workflows, and external boundaries remain first-class when admitted.

## Decisions

### 1. Keep domain semantics independent and share only a transport envelope

ResearchGuard will own a small `MemberModelEnvelope` and `HandoffFieldContract`. The envelope exposes identity, freshness, declared interfaces, receipt references, gaps, terminal status, and claim boundary. It contains no generic domain nodes and provides no method for the umbrella to calculate a native result.

The minimum envelope fields are:

```text
member_id
native_model_id
native_schema_id
native_model_fingerprint
declared_input_field_refs
declared_output_field_refs
native_receipt_refs
open_gap_refs
terminal_status
claim_boundary
```

Each handoff field adds:

```text
field_id
field_schema_id
payload_fingerprint
producer_member_id
producer_receipt_ref
consumer_member_id
consumer_requirement_id
consumer_status
```

ResearchGuard validates those fields and the composition topology, but it never deserializes a native payload. Native explanations are explicit handoffs to the member owner.

**Alternative rejected:** one universal Guard blueprint schema. Shared field names would quickly become shared semantic authority and would either weaken member checks to a lowest common denominator or create an implicit second solver.

### 2. Make each blueprint a projection of its current native model, not a parallel model

Each member will keep its current schema and execution owner. A member-specific blueprint module will validate or deterministically project the hierarchy, interfaces, inventory, impact, reverse trace, and export from those current identities.

- LogicGuard extends `LogicModel` and its validator with explicit block-interface bindings and consumes a separate artifact inventory.
- SourceGuard promotes its existing typed edge object to the sole persisted relationship authority and derives the information hierarchy from that graph.
- TraceGuard deterministically projects the hierarchy from `TraceGuardModel` references and the canonical inference receipt.
- ExperimentGuard extends its current spec with native procedure blocks and ports and requires the existing prediction matrix to reference those same identities.

No member receives a second score or alternate terminal.

The task target is frozen before any member derives a model or denominator. One provider-neutral `ExpectedTargetAnchor` carries the externally owned task and request identities, target id and revision, exact raw-material locator and content fingerprint, admission owner and producer identities, admission input and result fingerprints, immutable admission-receipt locator and fingerprint, and a deterministic anchor fingerprint. ResearchGuard umbrella admission may produce this anchor only from the original admitted task facts. A direct member route cannot manufacture or silently replace it: it must receive an external anchor, and absence or unavailable admission evidence is `unverified`.

Every member keeps its own closed current parser adapter, but that adapter may read only the locator named by the supplied anchor. It privately derives `TargetPurposeAuthority` after exact anchor replay; `TargetPurposeAuthority.issue`, arbitrary locator issuance, inline production authoring, and candidate-to-target helpers are removed. The private authority constructor binds the anchor identity and fingerprint in addition to the member-extracted denominator. If bytes, locator, task/request identity, admission owner/producer, or anchor receipt change under the same anchor, replay fails or becomes stale. A materially different target is valid only after a distinct external admission produces a new anchor. ExperimentGuard, LogicGuard, SourceGuard, and TraceGuard retain separate raw schemas, extractors, and semantic inventories; only the provider-neutral anchor carrier is shared.

Native evidence uses one closed immutable receipt resolver rather than caller-selected identifiers. A qualifying model, interface, depth, or owner receipt carries an immutable locator plus member, task, request, model, checker capability/version/entrypoint, input, result, status, producer, receipt id, and byte fingerprints. Its expectation also freezes the producer id/version and the complete signature descriptor: algorithm, signing-key id, public-key fingerprint, and producer-descriptor fingerprint. Resolution reopens the exact bytes, rejects missing/changed bytes and all identity or producer-descriptor mismatches, and rejects any coherent-looking receipt id or self-hash that was never published at the supplied immutable locator. There is no process cache, generic issuer, legacy reader, compatibility parser, or alternate receipt route. Member checkers derive terminal state and gaps only from resolved producer bytes.

For cross-member composition, opaque envelopes, expected target anchors, resolved native receipt references, and native owner attestations remain separate inputs. A closed registry binds each member to one exact owner, checker capability/version, module, and entry point. That member independently replays the external anchor, request, input, result, complete receipt set, and terminal; the umbrella never parses the domain payload. ResearchGuard compares a supplied attestation with that fresh replay and exposes no generic attestation issuer. A passed envelope, structurally self-hashed attestation, or caller-invented never-published receipt is insufficient. Impact and reverse trace first qualify the complete selected composition—including all four members when selected—and atomically suppress ordinary projections if any member or handoff is blocked. Reverse trace keeps the top-level composition terminal and blockers visible before stopping at each member-native receipt boundary.

The portable transport artifact is one deterministic, content-addressed bundle containing the composition, full member envelopes, expected-target anchors, handoff contracts and acknowledgements, immutable receipt references plus frozen producer descriptors, native attestations, exact claim boundary, and the closed raw proof inputs needed by every member-native replay. LogicGuard carries its purpose contract, bound candidate, and good/bad cases; SourceGuard carries its target contract and observations; TraceGuard carries its task contract and good/bad models; ExperimentGuard carries its frozen spec. A bundle-only handoff checker reconstructs all current transport evidence from the supplied bytes and immutable locator bindings; it receives no repository path, compiler temporary path, process-global registry shortcut, or caller prose. It returns `handoff_qualified` only when every selected member and handoff replays current, otherwise it returns one atomic blocked result with the first gap and all ordinary member result projections suppressed. Inside one bundle, `(member_id, receipt_id)` is unique and the carried reference must match its signed carried bytes. That does not prove producer non-equivocation across independently isolated bundles; such a claim requires a shared immutable authority or transparency log outside those bundles. This package transports member-domain DNA but does not interpret native payload meaning.

Every executable known-good, known-bad, failure-denominator, impact, and reverse-trace case records a full behavior transition contract: `Input`, `PreState`, permitted `Output`, `PostState`, `Effect`, protected `Failure`, and native `Oracle`. Test anchor and receipt producers receive an explicit isolated authority root and scoped registry fixture; importing a fixture cannot register a producer globally or write beneath the user's real authority directory.

Every member impact and reverse-trace operation first consumes exactly one current native blueprint qualification for the same model, authority, raw material, and required receipt identities. For reverse trace, this gate completes before target resolution, binding/index construction, ancestry or closure traversal, and terminal projection. Invalid, stale, failed, unverified, or not-run qualification returns one atomic rejected report: ordinary trace/path/node/edge/evidence/resource/terminal fields are empty, `partial_result_suppressed=true`, and only exact qualification/authority/material/receipt gaps plus the claim boundary remain. An unknown requested target cannot bypass the gate or replace it with a target-resolution exception.

**Alternatives rejected:** storing a second generic blueprint beside each native model creates dual freshness and disagreement risk; allowing a member to sign the target bytes supplied beside its candidate proves only internal consistency and permits coherent co-shrink; accepting self-hashed receipt identifiers without reopening immutable producer bytes turns a name into evidence. None of those routes establishes an externally fixed task target.

### 3. Use different native hierarchy shapes

The members share a requirement for parent/child closure, but not a common hierarchy vocabulary.

```text
LogicGuard:
ArtifactUnitTree <realizes> ArgumentBlockTree
child output claim -> parent input node

SourceGuard:
objective -> target unit -> gap -> source-role obligation
          -> search action -> source -> anchor -> claim-use/handoff

TraceGuard:
investigation -> storyline hypothesis -> trace -> sequence/stage
              -> event -> evidence -> source

ExperimentGuard:
purpose -> hypothesis family -> discrimination obligation
        -> candidate experiment -> procedure step
        -> manipulation/observation/outcome ports
```

Every material child output is either consumed by a parent input or carries a typed unresolved/excluded/terminal disposition.

### 4. Qualify completeness against an independent denominator

A model cannot prove completeness by counting its own contents. Each native blueprint binds an independent task-local universe:

- LogicGuard: artifact units, parse dispositions, and requested claim scope.
- SourceGuard: target units, gaps, source roles, lineage slots, anchor/bridge requirements, and handoffs.
- TraceGuard: required source/evidence/event/trace/hypothesis/causal-boundary objects from its task purpose and native inventory.
- ExperimentGuard: hypotheses, discrimination obligations, candidates, ports, constraints, and task-local good/bad cases.

Qualification reports the longest exact-current complete layer prefix and the first unresolved gap. Later material never hides an earlier incomplete layer.

### 5. Separate structural coverage from content/resource coverage

Blueprint projections are deterministic and member-native. They support a
coverage claim only for material explicitly represented and bound; the admitted
target directory and its model/test/evidence files remain the DNA authority.

- LogicGuard distinguishes structural artifact coverage from exact
  prose/layout/resource coverage.
- SourceGuard derives the search, qualification, source/anchor, and claim-use
  graph; raw source content remains bound by an external or library reference
  plus fingerprint.
- TraceGuard derives the trace graph, alternatives, bounded causal relations,
  and narrative obligations; it does not infer missing source content.
- ExperimentGuard derives the declared design, procedure, ports, and
  recommendation rationale; external apparatus and execution remain owned
  externally.

### 6. Derive affected-only invalidation from exact consumed identities

Every parent, consumer, receipt, handoff, and exported projection records the exact fingerprints it consumed. A changed fingerprint invalidates its direct consumers and transitive declared dependents. Unrelated branches retain exact-current evidence. Unknown dependency ownership blocks affected-confidence claims and does not authorize broad execution.

ResearchGuard performs this only over envelope and handoff topology. Each
member performs native impact inside its own payload boundary.

### 7. Provide four member-native blueprint operations

Each member exposes the same operation categories through its existing direct member command surface:

```text
blueprint check
blueprint impact
blueprint trace
blueprint export
```

The categories are consistent for discoverability; their schemas, checks, outputs, and claim boundaries remain member-owned. The ResearchGuard umbrella can route or reference them but does not implement a generic checker.

### 7a. External-domain-DNA is a topology facade, not a fifth semantic engine

The generic external-domain-DNA surface has exactly one direct-current composition path. ResearchGuard owns target-boundary admission, parent topology, complete mapping/disposition accounting, portable projection, compact queries, impact/reverse traversal, and claim-boundary aggregation. It does not own SourceGuard extraction/coverage, TraceGuard chronology, LogicGuard claim licensing, or ExperimentGuard discrimination. The current member blueprint, target-authority, owner-attestation, behavior-manifest, envelope, and portable-composition owners supply those semantics. Conflict-specific member `domain_dna.py` evaluators are a duplicate semantic boundary and are directly retired rather than wrapped, aliased, or kept as a fallback.

Completeness is established before candidate comparison by an independently produced signed scope authority plus current material replay. The authority is target-neutral and freezes provenance; target/version/material inventory; scope purpose and completion; included structures and their semantic obligations; required source occurrences, roles, artifacts, selectors, and distinct occurrence identities; every member's required inputs, output objects, and output kinds; handoffs and dispositions; LogicGuard limits; exclusions; and recursive frontier. For a frozen source tree its material inventory enumerates every file under one exact inclusion policy with relative locator, length, hash, material role, and one disposition. A candidate cannot define, derive, or shrink this denominator. A complete-looking candidate whose artifacts, structures, roles, claims, events, experiments, bindings, or owned ids are co-shrunk and re-fingerprinted is still incomplete.

The authority signature is created outside production. Runtime carries no private key and has no built-in trusted producer: it verifies the portable public descriptor and signature, then requires the caller to trust the exact authority fingerprint or authority-producer descriptor fingerprint out of band. A valid authority bundled beside the candidate is therefore authentic to its carried key but not automatically licensed. The candidate binds the authority identity; it never generates the authority or its trust root.

The comparison emits an obligation ledger with authority-required, candidate-produced, member-consumed, parent-disposed, missing, unexpected, and mismatched identities. Candidate-internal parent exhaustiveness remains useful but is not sufficient; the same parent is also compared with the authority-derived external inputs, member outputs, handoffs, and terminal dispositions. Known authority-required objects absent from the candidate remain addressable in impact and reverse as explicit incomplete gaps.

Material completeness and semantic-scope completeness are separate claims. Every external DNA declares its exact purpose, modeled question or whole-target boundary, included structure ids, per-member input and output object denominators, explicit exclusions, and recursive expansion frontier, while the independent authority fixes what those declarations must cover. A bounded model can be complete for its declared question while still naming unmodeled target regions. Therefore a 25-of-25 file inventory cannot by itself license whole-paper understanding, and `dna_qualified` always means qualified only inside the declared scope. Whole-target qualification requires an explicit whole-target authority whose complete structure denominator is covered and whose four native member scope bindings agree.

Qualification exposes six separate states: material inventory verified, member-native replay verified, candidate internal consistency, scope authority licensed, scope-obligation coverage, and final DNA qualification. This avoids treating a replayed candidate, a trusted material set, and an externally licensed complete scope as the same claim. A legitimate lightweight target succeeds under its own authority identity; it does not inherit canonical paper counts. Source occurrences use typed selectors (`line_pattern` for the current paper example and `json_pointer` for structured workflow/model fixtures), so production semantics are not tied to Python, TeX, line-oriented documents, or papers.

The ResearchGuard parent is an executable composition FunctionBlock, not a list of member labels. It freezes exact child order; aggregate Input, State, Output, and Effect fields; exhaustive child-input mappings; exhaustive child-output consumed/delegated/rejected dispositions; typed handoffs; and exactly one owner for every aggregate and child field. No orphan input, output, owned id, binding, object, structure node, behavior, claim, event, experiment, evidence reference, or gap is permitted. Structure-to-object-to-member edges form the only impact and reverse-trace graph: root changes reach declared descendants, local changes remain affected-only, and unknown ids block atomically rather than widen.

The same production topology accepts conflict and non-conflict paper-like targets and non-paper test/workflow targets. Production code contains no Attention, 41.x, arXiv, TeX, paper-title, forced-conflict, or numeric-special-case branch. Canonical examples contain target-specific data, while each member-native owner derives the corresponding semantic terminal. Bundle-only replay establishes deterministic self-consistency; only exact current material replay or a separately trusted extraction authority can establish anchor-dependent qualification.

Portable native qualification may use only a bounded, process-local, read-only memo of the exact replay result. Its key is the complete portable-composition bytes plus the normalized exact trusted producer-descriptor set; it stores no external material result, writes no disk state, creates no cross-process authority, and has no fallback. Altered bundle bytes or trust roots must miss and replay. Current material enumeration and hashing still execute for every material-qualified request, so cache reuse cannot turn stale or changed external material into current evidence.

Direct and umbrella-referenced operations must identify the same native owner, model, and receipt.

### 8. Keep prompt loading conditional and budgeted

Each `SKILL.md` receives only a short trigger and ownership statement. Detailed guidance lives in a new member-owned reference:

```text
researchguard/references/member-model-envelope.md
experimentguard/references/experiment-model-protocol.md
logicguard/references/domain-blueprint-contract.md
sourceguard/references/information-blueprint.md
traceguard/references/trace-blueprint-contract.md
```

The prompt manifest records exact trigger-to-reference edges. Ordinary member work loads no blueprint reference. Blueprint check, impact, trace, or export loads only the selected member's reference and affected slice. ResearchGuard does not eagerly load sibling blueprint references.

### 9. Use direct current schema replacement

Changed native shapes receive new current schema identities and all maintained fixtures, examples, tests, prompt references, and contract inputs move directly to them. Retired field shapes are rejected. No compatibility reader, converter, alias, fallback parser, dual emission, or version-choice route is added to normal runtime.

Historical artifacts remain historical evidence; they do not become current model input.

### 10. Delay FlowGuard projection until both sides are stable

FlowGuard work begins only after:

1. the four native schemas and operation contracts are frozen;
2. focused native tests pass on one source identity;
3. the imported FlowGuard package, source checkout, schema, command implementation, and installed consumer skills are frozen;
4. a fresh non-mutating project-upgrade preview is accepted.

The 0.68.6 preview currently proposes only:

```text
AGENTS.md
.flowguard/project.toml
.flowguard/adoption_log.jsonl
docs/flowguard_adoption_log.md
```

That list must be re-derived after the external toolchain freezes. The upgrade record is applied and audited before new FlowGuard model material is generated.

The new FlowGuard hierarchy has one repository software-DNA root and four member subtrees:

```text
ResearchGuard repository software-DNA root
├── LogicGuard member subtree
├── SourceGuard member subtree
├── TraceGuard member subtree
└── ExperimentGuard member subtree
```

The root is the software model for the ResearchGuard maintained skill surface; it is not a fifth sibling child. It owns repository admission, direct and umbrella routing, composition, envelopes, handoffs, and authority transitions. Each member subtree owns its member implementation boundary and MUST continue downward into multiple concrete function blocks, public surfaces, state/effect owners, adapters, and helpers rather than treating the entire member as one indivisible block. Every behavior-bearing function block is expressed as `Input x State -> Set(Output x State)` so nondeterministic permitted outcomes, emitted effects, and state transitions remain explicit.

The existing LogicGuard, SourceGuard, TraceGuard, and ExperimentGuard blueprints are member-domain DNA: they own argument, information-discovery, trace, and experiment-design meaning. The software-DNA root references those native models and their receipts at the semantic boundary but does not copy, reinterpret, or replace them. Generic skill-contract models remain SkillGuard maintenance evidence only. There is exactly one whole-repository software-DNA authority.

### 11. Derive whole-software coverage from an independent implementation inventory

Whole-repository self-DNA qualification consumes a current independent implementation inventory rather than the existing suite model's path list. The provider-neutral inventory covers every admitted source and generated-code boundary, skill and prompt surface, public CLI/API surface, schema and contract, configuration, workflow, resource, test, intent source, topology edge, external interface, and unresolved parse or dynamic finding. Every admitted item receives exactly one terminal disposition and every behavior-bearing item receives exactly one primary owner; shared helpers and resources have declared supporting owners and consumption edges. Unmapped, multiply owned, or ambiguously excluded material is an unresolved denominator gap.

The inventory route has one current provider-neutral contract. A Python adapter MAY use Python syntax and test conventions as an optimization, but it does not define the repository boundary. Other languages, declarative formats, generated surfaces, and business workflows use their declared current adapters under the same inventory and binding contract. An unknown adapter, unsupported schema, or unparseable dynamic surface blocks the relevant readiness layer; it never falls back to a Python-only subset, caller-supplied path list, legacy reader, or automatic full scan.

New immutable FlowGuard snapshot, revision, activation, and canonical-export identities are content-addressed outputs of the frozen toolchain and are never hand-edited. Their canonical materialization and current pointer remain outside the scanned repository boundary, and the pointer is updated last after affected owner receipts are current.

### 12. Report seven software-DNA readiness layers

Software-DNA readiness is not one confidence number. The root reports the longest exact-current prefix and first unresolved gap across these seven layers:

1. **Evidence qualification** — the admitted inventory, intent, native-model, resource, and adapter inputs have current identities and visible failed, stale, unverified, or not-run states.
2. **Implementation inventory** — the whole declared repository denominator is independently enumerated and every item has one terminal disposition.
3. **Traceability** — all declared forward and reverse relations among model, implementation, tests, intent, resources, topology, public surfaces, and external boundaries resolve without dangling or ambiguous ownership.
4. **Independent semantics** — the root behavior contracts and all referenced member-native domain obligations retain their own current semantic owners and claim boundaries.
5. **Model-code-test binding** — each behavior block is bound to its implementing surfaces and to tests that identify setup, input, pre-state, expected output, post-state, effect, failure class, and oracle for relevant good, bad-per-failure, invariant, transition, and regression obligations.
6. **Resource-oracle binding** — externally needed data, models, executors, fixtures, assets, providers, and oracles have exact identities, ownership, freshness, and unavailable/not-run dispositions.
7. **Static blueprint readiness** — the exact-current hierarchy, interfaces, state/effects, bindings, indexes, and bounded external references are sufficiently complete for reconstruction-oriented use within the stated claim boundary.

A later layer never hides an earlier gap. Static blueprint readiness does not claim that external resources are present, tests have just executed, installation is current, or release assets exist; those remain separate executed-evidence and lifecycle claim domains.

### 13. Maintain exact forward, reverse, and affected indexes

Every root and child owner records stable links in both directions among model blocks, implementation items, tests, intent sources, resources, topology edges, public surfaces, native domain identities, and external interfaces. The reverse index answers which model owner and claim boundary explain any admitted item. The affected index starts from any changed identity and closes over declared readers, writers, parents, children, consumers, tests, handoffs, resources, and topology dependents.

Ordinary maintenance loads and revalidates only that affected closure. Unknown ownership or an unknown edge blocks affected-confidence and never authorizes `run all`. Full denominator materialization is reserved for explicit whole-DNA qualification, canonical export, proof-gated architecture reduction, and the frozen release gate.

### 14. Keep canonical self-DNA and release assets outside the scanned repository

The canonical self-DNA export is a deterministic, content-addressed projection materialized outside the repository boundary it describes. Generated inventories, project definitions, canonical projections, current pointers, receipts, and export metadata MUST NOT enter their own denominator or become source authority; path exclusions alone are insufficient to cure a self-fingerprint cycle. The repository may hold governed source definitions needed to build the projection, but the canonical result and its current pointer remain external.

External source artifacts, datasets, binaries, executors, and other resources are represented by bounded identity, locator, owner, and fingerprint references unless their exact bytes are explicitly admitted. A release archive never contains or authenticates its own checksum: archive metadata, checksum, signature, and publication receipt remain outside that archive and bind it by identity.

### 15. Gate architecture reduction on proof-ready software DNA

Architecture reduction begins only when the affected observable contract, owner hierarchy, code/test/intent/resource/topology bindings, affected and reverse indexes, and required native evidence are proof-ready. A suspected duplicate branch, adapter, helper, handler, facade, or validation layer first becomes a candidate with its observable contract, current primary owner, proposed disposition, affected closure, and required parity evidence. Similar names, size, or apparently overlapping code are not deletion proof.

Public-entrypoint or large structure candidates route through the structure owner, and lifecycle/release effects route through the development-process owner. After an accepted contraction, the affected closure is revalidated; one whole-DNA/release gate runs only after the integration snapshot is frozen. Risky or under-evidenced candidates remain explicit findings rather than being removed or hidden behind compatibility, aliases, dual emission, or fallback.

### 16. Preserve SkillGuard and distribution boundaries

The five skill surfaces remain one explicitly registered ResearchGuard maintenance unit. Each target skill owns its prompt semantics and native checks. SkillGuard supervises author inventory, exact component impact, current receipts, and clean consumer projection; it does not supply domain behavior or become a consumer runtime dependency.

The repository installer remains the suite-level order and transaction coordinator; it does not implement a second member file-selection, release-manifest, receipt, backup, recovery, or per-member rollback algorithm. It owns exactly one process-held suite mutation lock so Python package replacement, the five delegated consumer activations, suite-manifest replacement, terminal verification, and any in-process restoration cannot overlap another suite installer. For each member it still uses SkillGuard's current consumer-distribution plan and target-installation `prepare`, `verify`, `activate`, and `rollback` APIs. The SkillGuard API root is derived from the one active Codex installation and cannot be redefined by an unverified environment variable. SkillGuard generates the `consumer-release.json`, transaction journal, receipt, HEAD, per-member lock, and per-member backup. `.skillguard`, author receipts, execution owners, FlowGuard evidence, and private author paths remain absent from the consumer tree.

All five trees are prepared and then independently reverified in a temporary root before any activation begins. A preparation or verification failure starts zero activations. Before `pip` may replace the package, the suite owner freezes the exact prior ResearchGuard distribution file inventory and bytes plus the prior suite-manifest bytes or verified absence. Activation is serialized in the frozen member order. If member N returns a failure, raises an ordinary exception, returns a malformed successful identity, or any later manifest/currentness/console check fails, the suite owner keeps the total lock and attempts all three restoration domains: every committed consumer through SkillGuard in reverse order, the exact prior Python distribution, and the exact prior suite manifest. Each restoration domain and each member rollback is isolated so one exception never suppresses another attempt. A returned consumer rollback is accepted only when its skill id, transaction id, and restored terminal status identify the exact requested rollback; package and manifest restoration are accepted only after exact inventory/byte revalidation. Any missing inventory, unusable pointer, residual, or failed verification returns `cleanup_unconfirmed`. The installer never edits installed skill trees directly. A process-termination window across separately committed members is not misreported as a single crash-atomic filesystem transaction: each member retains SkillGuard's durable recovery, while the suite currentness check remains blocked until the package, all five exact source releases, and the suite manifest are again mutually current. Explicitly retired skill residuals block before Python package replacement and are checked again before activation rather than being silently deleted. A read-only currentness check reuses SkillGuard's public static target verification against each active tree and never launches semantic validation or writes repair state.

The suite-level `researchguard.install-manifest.v2` records the exact Python package fingerprint, five SkillGuard release ids, and the transaction, receipt-hash, and HEAD-generation pointers returned by the five successful activations. These pointers are provenance, not a second receipt verifier: ResearchGuard checks their returned cross-field shape but does not read SkillGuard's private journal or claim that the pointers remain current later. Static installed currentness comes from public `verify_target_stage` against the current source plan. The read-only check also compares an observed package inventory even when it is empty, identifies source-projection versus installed-distribution import mode, and requires exactly one materialized console entrypoint.

Before any wheel or skill mutation, the installer requires one absolute `CODEX_HOME` that is neither a link nor a reparse point, the canonical `skills` child, a non-escaping ResearchGuard manifest root and suite-lock file, and agreement between the package version declared by `pyproject.toml` and the source package `__version__`. The suite lock is an operating-system lease released on process exit, not a stale lockfile heuristic. The suite manifest and every restored package file are written through unique exclusive temporary files in their validated roots and atomically replaced; predictable `.tmp` or `.restore` names and linked or reparse targets are forbidden.

Installation and release happen only after source, prompt, FlowGuard model, native tests, SkillGuard artifacts, package identity, and consumer projection are frozen. The patch version is selected at release preparation, not hard-coded into native model semantics.

### 17. Keep shared files and peer work under one integration owner

Member-native implementation can proceed in parallel because each member has disjoint runtime and test directories. One integration owner exclusively coordinates shared files:

- `src/researchguard/routing.py`
- `src/researchguard/cli.py`
- `src/researchguard/suite.py`
- `researchguard/prompt_bundle_manifest.json`
- `.flowguard/**` except excluded peer evidence
- `.skillguard/**`
- package/version/release files

Before editing any shared file, the integration owner re-reads current peer changes. Existing `.flowguard/evidence/` and unknown-writer files remain untouched unless a later explicit evidence owner claims an exact path.

## File Boundaries

| Area | Planned source paths | Planned focused tests |
|---|---|---|
| ResearchGuard envelope/composition | `src/researchguard/model_envelope.py` (new), `src/researchguard/routing.py`, `src/researchguard/cli.py`, `src/researchguard/suite.py`, `src/researchguard/__init__.py` if public export is required | `tests/test_member_model_envelope.py` (new), `tests/test_suite_routing.py`, `tests/test_root_cli.py`, `tests/test_guard_blueprint_integration.py` (new) |
| ExperimentGuard | `src/researchguard/experiment/schema.py`, `engine.py`, `cli.py`, `__init__.py`, `blueprint.py` (new) | `tests/experiment/test_blueprint_design.py` (new), `tests/experiment/test_recommendation.py` |
| LogicGuard | `src/researchguard/logic/model.py`, `validator.py`, `hierarchy.py`, `structured_artifact.py`, `execution_depth.py`, `mesh_invalidation.py`, `cli.py`, `artifact_inventory.py` (new), `blueprint.py` (new) | `tests/logic/test_blueprint_interfaces.py` (new), `test_artifact_inventory.py` (new), `test_schema.py`, `test_hierarchy.py`, `test_execution_depth.py`, `test_mesh_invalidation.py`, `test_structured_artifact.py` |
| SourceGuard | `src/researchguard/source/schema.py`, `graph.py`, `depth.py`, `task_iteration.py`, `handoff.py`, `cli.py`, `blueprint.py` (new) | `tests/source/test_blueprint_graph.py` (new), `test_schema.py`, `test_semantic_gap_depth.py`, `test_task_iteration.py`, `test_model_guard_binding.py`, `test_handoff.py` |
| TraceGuard | `src/researchguard/trace/schema.py`, `inference/compiler.py`, `inference/projection.py`, `storyline_depth.py`, `task_iteration.py`, `cli.py`, `blueprint.py` (new) | `tests/trace/test_blueprint_hierarchy.py` (new), `test_traceguard.py`, `test_inference_kernel.py`, `test_storyline_depth.py`, `test_task_iteration.py` |
| Prompt bundles | five `skills/*guard/SKILL.md`, five `skills/*guard/agents/openai.yaml`, the five new references named above, `researchguard/prompt_bundle_manifest.json` | `tests/test_prompt_bundles.py`, `tests/test_skill_suite.py` |
| FlowGuard self-DNA | `.flowguard/researchguard_suite_model.json`, `.flowguard/researchguard_suite_model.py`, `.flowguard/researchguard_suite/model.py`, `.flowguard/researchguard_suite/run_checks.py`, `.flowguard/run_researchguard_suite_model.py`, `.flowguard/model-regression-manifest.json`, `.flowguard/researchguard_skillguard_maintenance_preflight.md`, root/subtree/provider/index source definitions; externally materialized canonical snapshot/revision/activation/current-pointer artifacts | `tests/test_suite_model_currentness.py`, `tests/test_guard_blueprint_integration.py`, provider-neutral/non-Python fixtures, canonical-boundary tests, FlowGuard native model checks |
| SkillGuard/distribution | `.skillguard/author-project.json`, `.skillguard/researchguard-suite-validation-plan.json`, each maintained `skills/*guard/.skillguard/**`, installer/version/release files selected by the affected component inventory | existing contract/native suites, `tests/test_install_researchguard.py`, `tests/test_zero_residuals.py`, release parity checks |

## Validation Strategy

Validation proceeds in layers and never substitutes one owner for another:

1. Schema and known-good/known-bad tests for each native member.
2. Parent/child interface, independent-universe, external-anchor replay, immutable-receipt resolution, impact, reverse-trace, and round-trip tests per member.
3. Four permanent coherent raw-bytes co-shrink tests that change candidate, universe, raw target bytes, request/revision/authority identities, and native evidence together while holding the original external anchor fixed; plus same-target changed-bytes/changed-authority cases, absent-anchor direct-use cases, and separately admitted alternate-target positives.
4. Four arbitrary never-published receipt-id tests, fresh-process and serialized replay tests, real ExperimentGuard owner replay, and one real two-member composition proving unresolved receipts cannot become ready.
5. One real four-member composition with a blocked member proving atomic impact/reverse suppression and non-zero CLI exit, plus a current four-member positive proving exactly one qualification pass per selected member.
6. Producer-substitution tests proving that a different registered producer, producer version, signature algorithm, signing-key id, public-key fingerprint, or descriptor fingerprint cannot satisfy a frozen `NativeReceiptExpectation`.
7. Fixture-import and execution tests that set an explicit temporary authority root, restore registries, and prove zero writes beneath the user's real authority directory.
8. Per-behavior transition fixtures covering `Input`, `PreState`, permitted `Output`, `PostState`, `Effect`, protected `Failure`, and native `Oracle` for every newly claimed composition and handoff behavior.
9. Deterministic portable-bundle round trip plus a fresh-process, bundle-only internal integrity check with repository access unavailable; this check reports bundle status and query coverage and does not recruit an external agent or generate an independent answer.
10. Existing native semantic and iteration suites per affected member, including a real public LogicGuard parent/child realization fixture with exact, missing, stale, and foreign leaf receipts and a blocked reverse-trace gap de-duplication assertion.
11. ResearchGuard envelope, handoff, minimum-sufficient routing, and cross-member integration tests.
12. Prompt bundle, conditional-loading, and byte-headroom tests.
13. FlowGuard single-root software-DNA, provider-neutral denominator, seven-layer readiness, bidirectional/affected index, external canonical-boundary, and currentness checks after toolchain freeze.
14. SkillGuard affected author validation and clean consumer projection.
15. One full ResearchGuard suite on the frozen integration snapshot.
16. Isolated install/currentness checks, followed by source/install/Git/tag/release identity closure.

A structural blueprint result never replaces a native semantic receipt. A green focused command never closes a stale parent or downstream handoff unless the owning receipt is regenerated and consumed.

## Risks / Trade-offs

- **Adding parent/child contracts exposes many previously implicit gaps** → ship the spine with explicit incomplete states and first-gap reporting; do not weaken validators to preserve historical green results.
- **New current-only schemas can invalidate maintained fixtures and external model files** → update all registered maintained inputs atomically, reject retired shapes visibly, and document exact external migration responsibilities without adding runtime readers.
- **A uniform operation vocabulary could be mistaken for shared semantics** → keep request and result schemas member-native and share only the ResearchGuard transport envelope.
- **Independent inventories increase preparation cost** → materialize full inventories only for explicit blueprint qualification; ordinary work remains affected-only.
- **FlowGuard projection could absorb mutable peer changes** → freeze the external toolchain and rerun preview immediately before any project or model write.
- **Prompt growth could consume routing context** → keep entry edits minimal, place detail in conditional references, and enforce existing byte/headroom gates.
- **Parallel member work can conflict in shared manifests and CLI routing** → assign shared files to one integration owner and merge native branches only after their schema identities freeze.
- **Structural export may be overclaimed as exact reconstruction** → report structural, content/resource, semantic, evidence, impact, and software-binding layers separately.

## Migration Plan

1. Freeze the current ResearchGuard source identity and record the five-skill/four-native-member boundary.
2. Implement and validate each member-native schema and blueprint operation in isolated paths; update current fixtures directly and reject old shapes.
3. Freeze native schema ids, model fingerprints, operation contracts, and focused receipts.
4. Implement the opaque ResearchGuard envelope, typed handoff acknowledgement, affected-only composition invalidation, and reverse trace.
5. Add conditional prompt references and pass prompt budget/load-graph checks.
6. Run the cross-member blueprint integration fixture and affected native suites.
7. Freeze the external FlowGuard toolchain, rerun project-upgrade dry-run, apply only the accepted project-record paths, and audit the project.
8. Build one FlowGuard repository software-DNA root and four recursively decomposed member subtrees from the provider-neutral independent denominator; qualify seven-layer readiness, indexes, and external canonical boundaries, then produce and activate one immutable revision only after affected evidence is current.
9. Compile and validate affected SkillGuard author contracts, compare clean consumer projections, and keep author artifacts out of consumer runtime.
10. Run one frozen full suite, isolated installation checks, version synchronization, Git/tag/release gates, and then archive the completed OpenSpec change.

Rollback before release removes only the scoped new current implementation and restores the exact prior source, model pointer, project records, and consumer projection when every affected side effect is restorable. After release, defects use a forward patch; historical receipts, peer evidence, and prior immutable model records are not rewritten.

## Current implementation-round amendment (R00–R10, 2026-09-09)

The design above contains the domain-blueprint and self-DNA decisions that
preceded the current implementation pass. This amendment records how those
decisions are exercised now without rewriting that history:

* The native hierarchy is checked at two different boundaries. Each member's
  domain model owns its own parent/child/descendant semantics and immutable
  receipt. The FlowGuard software-DNA root separately owns repository code,
  tests, prompts, resources, topology, and their parent/child/consumer
  bindings. The 63 self-DNA case mapping is coverage metadata; it cannot be
  substituted for current native child and parent execution receipts.
* The only accepted provider path for production use is the installed
  ResearchGuard console selected by the current package/console identity.
  Test doubles may exercise the LogicWriting process boundary, but their
  receipts are marked `protocol_only` and cannot qualify native model,
  quality, installation, or release claims. All native receipts must be
  reopened from immutable producer bytes and retain producer, request, input,
  result, checker, status, locator, and cleanup identity.
* R01–R03 are process and evidence contracts consumed by the ResearchGuard
  side through R04's handoff. R05–R06 are ResearchGuard-native strict mapping,
  parent/child receipt, and bounded-suite checks. R07–R10 are integration
  gates, not new domain solvers: they freeze the package and projection,
  validate the installed chain, run the current model/test gates, and publish
  a scoped source commit only after those boundaries are visible.
* A blocked member is an atomic composition blocker. The umbrella may report
  the first gap and exact stale/foreign child, but it cannot expose an
  affected set, reverse trace, or terminal `composition_ready` result from a
  partial four-member set. The same fail-closed rule applies when the provider
  is unavailable, a child receipt is stale, cleanup is unconfirmed, or a
  consumer projection is not current.

The current acceptance matrix is maintained in `tasks.md`. It deliberately
keeps `implemented`, `protocol_tested`, `current_model_closed`,
`real_quality_proved`, and `installed_current` independent. A later release
receipt may consume these claims only after their exact source, toolchain,
input, and owner identities match; it cannot infer one claim from another.
