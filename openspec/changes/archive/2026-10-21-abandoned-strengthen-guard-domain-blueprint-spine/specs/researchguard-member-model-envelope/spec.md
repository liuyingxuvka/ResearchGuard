## Purpose

Define a payload-opaque, evidence-bound transport contract through which ResearchGuard can compose independently owned member blueprints without interpreting, rescoring, or replacing any member's native semantics.

## ADDED Requirements

### Requirement: Every composed member publishes one current opaque envelope
For every selected member participating in a composition, ResearchGuard SHALL require one current member-model envelope containing the member identity, native model identity, native schema identity, model fingerprint, declared input and output field references, native receipt references, open-gap references, terminal status, and claim boundary. The umbrella MUST treat the native payload as opaque and MUST NOT deserialize it into a shared domain schema or use it to make a member-native judgment.

#### Scenario: Current member envelope is accepted
- **WHEN** a selected member supplies all required envelope identities and every referenced model and receipt is current for the same task
- **THEN** ResearchGuard accepts the envelope as transport evidence without interpreting the member payload

#### Scenario: Opaque payload is unavailable to the umbrella
- **WHEN** composition planning has a valid envelope but no access to the member's internal domain payload
- **THEN** ResearchGuard can still validate identity, handoff topology, freshness, terminal status, and claim boundary

#### Scenario: Missing or stale envelope blocks composition
- **WHEN** a selected member lacks a required envelope field or its model, schema, task, or receipt identity is stale or mismatched
- **THEN** ResearchGuard blocks that composition step and does not substitute another member or infer the missing value

### Requirement: Target anchors and native receipts are externally owned replayable evidence
Every selected member SHALL receive one provider-neutral expected-target anchor admitted before member modeling. The anchor MUST bind the original task and request, target identity and revision, exact raw-material locator and fingerprint, admission owner and producer, admission input and result identities, immutable admission-receipt locator and fingerprint, and deterministic anchor fingerprint. Umbrella admission MAY produce it from original task facts; a direct member without an externally supplied current anchor MUST remain unverified. A member MUST NOT admit a new anchor during its own check, replace the anchor when candidate material changes, or accept an arbitrary raw locator as target authority.

Every model, interface, depth, purpose, canonical-result, and owner receipt referenced by an envelope or member qualification SHALL include an immutable locator and exact producer, task, request, member, model, checker, input, result, status, receipt-id, and bytes fingerprints. A closed resolver MUST reopen and validate those exact bytes. There MUST be no public generic receipt issuer, process cache, inline production authoring helper, legacy reader, or fallback that promotes caller-authored receipt metadata.

The receipt expectation SHALL additionally freeze the exact producer id and producer version, signature algorithm, signing-key id, public-key fingerprint, and producer-descriptor fingerprint. A receipt signed by any other registered producer or key MUST fail expectation resolution even when every member, model, checker, request, input, result, status, and receipt-content field otherwise matches.

#### Scenario: Same target id is supplied with changed bytes
- **WHEN** a caller changes raw target bytes and recomputes candidate, universe, authority, request, target-revision, and receipt identities while retaining the original expected-target anchor
- **THEN** every selected member reports an expected-anchor mismatch and ResearchGuard suppresses ordinary impact, reverse trace, and composition readiness

#### Scenario: Caller invents a never-published receipt
- **WHEN** an envelope references an internally consistent receipt id and self-hash that cannot be reopened from its declared immutable producer locator
- **THEN** ResearchGuard and the member owner reject it as unresolved and composition remains blocked

#### Scenario: Another registered producer signs matching receipt content
- **WHEN** a receipt matches the expected task, member, model, checker, request, input, result, and status but its producer id/version, signature algorithm, signing-key id, public-key fingerprint, or descriptor fingerprint differs from the frozen expectation
- **THEN** the resolver reports the exact producer-identity mismatch and the receipt cannot qualify an envelope or composition

#### Scenario: Alternate target is separately admitted
- **WHEN** a genuinely different target receives its own external expected-target anchor and immutable admission receipt
- **THEN** members may qualify that new target without weakening or replacing the earlier anchor

### Requirement: Handoff fields have exact producer and consumer contracts
Every cross-member handoff field SHALL declare a stable field identity, field schema identity, payload fingerprint, exactly one producing member and native receipt, every intended consuming member and requirement, and one consumer acknowledgement or explicit rejection for each intended consumer. ResearchGuard MUST NOT treat declaration of a handoff as evidence that the consumer executed.

#### Scenario: Declared consumer acknowledges a handoff
- **WHEN** one producer emits a fingerprinted field and the declared consumer records that it consumed the same field identity and fingerprint for its declared requirement
- **THEN** the handoff is current for that producer-consumer edge

#### Scenario: Producer ownership is ambiguous
- **WHEN** zero or more than one member claims production ownership for one handoff field
- **THEN** composition blocks before any dependent member is treated as ready

#### Scenario: Consumer has not acknowledged the field
- **WHEN** a producer has emitted a handoff field but a declared consumer has neither consumed it nor recorded an explicit rejection reason
- **THEN** the handoff remains incomplete and no downstream completion claim is permitted

### Requirement: Envelopes connect member-domain DNA to one repository software-DNA root
The ResearchGuard repository software-DNA root SHALL own the behavior of admitting a member request, selecting direct or umbrella routing, composing members, carrying opaque envelopes, validating handoffs, and preserving authority transitions. Each envelope SHALL connect one member-native domain identity to the corresponding LogicGuard, SourceGuard, TraceGuard, or ExperimentGuard software subtree. An envelope MUST NOT become a fifth member subtree, a shared domain model, or a second whole-repository blueprint.

#### Scenario: A composition crosses two member subtrees
- **WHEN** the root routes an exact SourceGuard output field into one declared LogicGuard input
- **THEN** the software-DNA trace passes through the root-owned route, envelope, handoff, and authority blocks while each member's semantic interpretation remains inside its native domain boundary

#### Scenario: An envelope is offered as repository completeness proof
- **WHEN** all selected member envelopes are current but code, test, intent, resource, topology, or deeper child-owner bindings are missing
- **THEN** ResearchGuard MAY report current composition transport while whole-repository software-DNA readiness remains incomplete

### Requirement: Member changes invalidate only declared downstream consumers
ResearchGuard SHALL compare current envelope and handoff fingerprints with the fingerprints consumed by each composition step and SHALL mark stale only the steps that directly or transitively consume a changed field or member result. Unknown dependency ownership MUST block affected-confidence claims and MUST NOT trigger `run all`, retry, or blanket sibling invalidation.

#### Scenario: One upstream field changes
- **WHEN** a member model or handoff payload fingerprint changes and only two later steps consume that field
- **THEN** those two steps and their declared dependent claim boundaries become stale while unrelated member steps retain their current status

#### Scenario: Dependency ownership is unknown
- **WHEN** ResearchGuard cannot determine whether a changed field is consumed by a downstream step
- **THEN** it reports an unresolved dependency blocker and does not execute every member as a fallback

### Requirement: Cross-member reverse trace stops at native ownership boundaries
ResearchGuard SHALL provide a deterministic reverse trace from a composed result or overall claim boundary through the composition step, handoff field, producer and consumer identities, member-model envelope, native receipt reference, and source-bound responsibility span. The trace MUST stop at the native receipt boundary unless the owning member is explicitly invoked to interpret its own model.

#### Scenario: Composed claim is traced to native receipts
- **WHEN** a caller requests the provenance of a composition-level claim boundary
- **THEN** ResearchGuard returns the exact step, handoff, envelope, native receipt, and responsibility-span chain without explaining the native receipt's domain meaning

#### Scenario: Member-native interpretation is requested
- **WHEN** a caller asks why a native LogicGuard, SourceGuard, TraceGuard, or ExperimentGuard result holds
- **THEN** ResearchGuard hands the request to that exact native owner rather than interpreting the opaque payload itself

### Requirement: Member failure remains terminal and visible
A failed, blocked, stale, skipped, not-run, or non-terminal member envelope SHALL remain visible in the composition result and SHALL not be converted into success by another member, an aggregate score, a compatibility path, or umbrella prose.

#### Scenario: One member blocks in a necessary composition
- **WHEN** a required member returns a blocked terminal with open gaps
- **THEN** the overall composition reports that member and its gaps as blocking and does not upgrade the result from successful sibling output
### Requirement: Composition readiness requires independently owned member attestations

ResearchGuard SHALL require one separately supplied current member-native attestation for every selected opaque member envelope. Its closed registry SHALL bind the member to one exact native owner, checker capability, checker version, module, and entry point. The selected member SHALL independently replay the external expected-target anchor and resolve its exact request, input, result, complete immutable receipt set, and terminal. ResearchGuard SHALL compare the supplied attestation with that fresh member result without interpreting the payload and MUST NOT expose a generic attestation or receipt issuer. Caller-authored passed envelopes, structurally self-hashed attestations, or never-published receipt identifiers MUST NOT produce `composition_ready`.

Member target-denominator interpretation SHALL remain outside the umbrella: ResearchGuard umbrella admission owns the original expected-target anchor when it admitted the task, each member owns only its current parser/checker replay, and ResearchGuard transports the resulting attestation identity and terminal. The umbrella MUST NOT parse member target bytes, let a member auto-admit its own target, keep a shared first-seen denominator cache, expose a candidate-to-target authoring shortcut, or upgrade an unverified member result.

#### Scenario: Caller supplies only passed envelopes
- **WHEN** every composition envelope and native receipt reference is caller-labeled passed but no independently owned member attestation is supplied
- **THEN** ResearchGuard returns a typed composition gap and does not claim readiness

#### Scenario: Caller self-hashes complete-looking attestations
- **WHEN** a fresh process receives caller-constructed attestations with valid transport fingerprints but request, input, or result identities not produced by each registered member checker
- **THEN** ResearchGuard replays every opaque envelope through its exact member checker, returns `composition_blocked`, and reports the non-current attestation gaps

#### Scenario: Real owner replay encounters an unresolved receipt
- **WHEN** an ExperimentGuard envelope or a two-member composition reaches the registered owner checker with an arbitrary never-published native receipt id
- **THEN** the owner replay remains blocked, the envelope cannot become current, and the composition cannot become ready

#### Scenario: Blocked composition is reverse traced
- **WHEN** a composition contains a blocked, stale, failed, not-run, or empty member chain
- **THEN** reverse trace exposes top-level composition status, blocking member ids, composition gaps, and incomplete trace status before stopping at the native receipt boundary

### Requirement: Composition-derived operations qualify the complete selected member set first

Composition impact and reverse trace SHALL replay the complete selected composition, all required member attestations, and all handoff acknowledgements exactly once before calculating an affected set, resolving a requested output, building a path, or projecting any member terminal. This applies to every selected set, including a four-member recursive composition. If composition status is not `composition_ready`, both operations MUST atomically suppress ordinary affected, unaffected, step, handoff, path, and native-terminal projections, set `partial_result_suppressed=true`, preserve the composition blockers and claim boundary, and return a non-success CLI status.

#### Scenario: One member blocks a four-member recursive composition
- **WHEN** LogicGuard, SourceGuard, TraceGuard, and ExperimentGuard are all required and any member, nested handoff, anchor, receipt, or attestation is blocked, stale, failed, skipped, not run, or unresolved
- **THEN** composition impact and reverse trace return no usable partial affected/path result, identify the blocking member or handoff, and the CLI exits non-zero

#### Scenario: Four-member composition is current
- **WHEN** all four required members and every recursive handoff replay current under the same task and claim boundary
- **THEN** impact and reverse trace qualify each selected member exactly once before returning the deterministic declared transport closure

### Requirement: Executable behavior evidence binds complete transitions and native oracles

Every executable case used to license member-envelope, composition, impact, reverse-trace, or bundle-only handoff behavior SHALL bind one exact `Input`, `PreState`, permitted `Output`, `PostState`, `Effect`, protected `Failure`, and native `Oracle`. A case name, green test, structural envelope, or expected-value literal without those bindings MUST NOT license behavior coverage.

#### Scenario: A claimed composition behavior omits its post-state or oracle
- **WHEN** an acceptance case names inputs and expected output but omits post-state, effect, protected failure, or the native oracle that decides the result
- **THEN** the behavior remains uncovered even if the test function passes

### Requirement: Portable composition bundles support independent bundle-only handoff

ResearchGuard SHALL export one deterministic content-addressed portable bundle containing the complete selected composition, member envelopes, externally admitted target anchors, handoff contracts and acknowledgements, immutable native receipt references with frozen producer descriptors, member-native attestations, claim boundary, and the exact closed proof inputs consumed by each member-native replay. LogicGuard's purpose contract/candidate/good-bad cases, SourceGuard's contract/observations, TraceGuard's task contract/good-bad models, and ExperimentGuard's frozen spec SHALL be integrity-bound bundle material rather than hidden local path dependencies. A fresh independent process SHALL be able to qualify the handoff from the bundle and its declared immutable locator bindings alone, without repository checkout access, compiler temporary files, caller prose, process-global registry residue, or implicit local authority. The checker MUST keep native payloads opaque and MUST return a visible first gap rather than filling a missing identity.

Within one supplied bundle, every `(member_id, receipt_id)` SHALL occur exactly once and its carried reference SHALL match the exact signed carried bytes. This bundle-local proof MUST NOT be reported as producer non-equivocation across two independently isolated bundles. Cross-bundle uniqueness requires a separately supplied shared immutable authority or transparency log that covers both bundles.

#### Scenario: Internal verifier receives only a complete current bundle
- **WHEN** a fresh verifier process receives the deterministic bundle bytes and every declared immutable locator remains available and exact
- **THEN** it reproduces the same bundle fingerprint, composition terminal, handoff ownership, receipt identities, and claim boundary and returns the typed internal qualification status without consulting an external agent

#### Scenario: Bundle relies on hidden local state
- **WHEN** qualification would require an unbundled registry entry, repository file, caller explanation, changed receipt bytes, or undeclared producer key
- **THEN** bundle-only handoff is blocked, the missing dependency is the first gap, and no ordinary member result is projected

#### Scenario: Two isolated bundles carry different receipts under one identity
- **WHEN** each bundle is internally valid but there is no shared immutable authority or transparency log covering both producer publications
- **THEN** each bundle can prove only its own carried-byte consistency and MUST NOT claim that the producer did not equivocate across bundles

### Requirement: Test authority is explicit and isolated

Tests that create expected-target anchors, native receipts, producer descriptors, or attestations SHALL receive an explicit temporary authority root and scoped registry state. Importing a test fixture MUST NOT register producers or write files. Test teardown SHALL restore the prior registry and remove only files created beneath that exact temporary root; no test may write to or broadly clean the user's real ResearchGuard authority directory.

#### Scenario: Authority fixture module is imported
- **WHEN** a test process imports its anchor or receipt fixture helpers before creating an isolated authority context
- **THEN** no producer is registered and no authority file or directory is created

### Requirement: External objects have one portable, member-owned domain-DNA projection

ResearchGuard SHALL provide one generic external-domain-DNA API and CLI for a paper, model, test system, workflow, or other declared target. The artifact SHALL bind the target version and official locators, non-embedded artifact hashes and lengths, one parent/child structure hierarchy, exactly one SourceGuard, TraceGuard, LogicGuard, and ExperimentGuard transition model, all model/object bindings, and one acyclic dependency graph. Each member transition SHALL be replayed by that member's fixed evaluator entry point over exact `Input`, `PreState`, permitted `Output`, `PostState`, `Effect`, and protected `Failure`; a caller-rebound member projection MUST fail native-evidence replay.

The default projection SHALL remain below 16 KiB and at least ten times smaller than the complete artifact, while one explicit member, behavior-ID, object, impact, or reverse query MAY reveal the requested detail. Bundle self-consistency and member replay SHALL remain distinct from external artifact authenticity. Caller-supplied exact artifact hashes MAY license only the whole-artifact identity; they MUST NOT license bundle-carried line hashes, short value tokens, anchor extraction, or claims derived from those anchors. Anchor-dependent qualification requires the current process to reopen the complete trusted material denominator and replay the fixed SourceGuard extraction, or a separately specified signed extraction authority with an exact out-of-band trusted producer identity.

#### Scenario: Internal verifier receives a real paper DNA bundle
- **WHEN** a fresh installed-wheel verifier process receives only the bundle plus exact out-of-band artifact hashes, with repository and target-file reads prohibited
- **THEN** it replays the portable four-member semantics, returns `dna_self_consistent` with `material_identity_trusted_but_anchor_extraction_unlicensed`, exposes the compact summary or one requested behavior, and performs no source-tree, target-file, registry, user-profile, or external-agent fallback

#### Scenario: Current material is supplied for anchor qualification
- **WHEN** the qualifier receives the bundle, every exact trusted artifact hash, and an explicit material root containing the complete frozen material denominator
- **THEN** it verifies every declared artifact byte length and hash, re-extracts every SourceGuard anchor from the declared line and pattern, replays all downstream member semantics, and returns `dna_qualified` only when the whole chain matches

#### Scenario: Frozen primary-source values conflict
- **WHEN** separate exact locators in one frozen target report incompatible values
- **THEN** SourceGuard preserves every locator/value, TraceGuard preserves their sequence, LogicGuard licenses only the bounded conflict claim, ExperimentGuard keeps the resolution hypotheses open, and no layer silently selects one value

#### Scenario: Caller changes one member projection and rebinds transport identity
- **WHEN** a caller changes a member output and recomputes the outer DNA id and fingerprint without matching member-native evidence
- **THEN** qualification returns `dna_blocked` with a native replay or native-evidence mismatch and suppresses a qualified claim

#### Scenario: Caller coherently rebinds bundle-carried anchors
- **WHEN** a caller changes an expected anchor value, regenerates all four member outputs and evidence, recomputes the outer DNA identity, and retains the authentic whole-artifact hashes
- **THEN** bundle-only inspection remains at most `dna_self_consistent`, and current-material qualification blocks when SourceGuard re-extraction differs from the rebound anchor

#### Scenario: A real target DNA is retained outside tests
- **WHEN** the real-paper regression is maintained
- **THEN** one canonical repository model remains directly inspectable and reusable without absolute machine paths or embedded paper/TeX bytes, and the test loads that same model before building it through the public CLI

#### Scenario: The target is not a paper
- **WHEN** the same production API receives an independently authorized test workflow with its own version, material hashes, JSON-pointer occurrence, hierarchy, values, member models, and bindings
- **THEN** it qualifies through the same four fixed evaluator entry points without a paper title, arXiv identity, TeX path, line-number requirement, or numeric-value special case in production code

### Requirement: External-domain-DNA completeness uses an independent closed denominator

Before ResearchGuard compares or executes a candidate external-domain-DNA artifact, one current target-boundary owner SHALL independently replay the admitted material boundary and enumerate every required file, target object, structure node, member input, member output, behavior, evidence reference, and binding under one exact inclusion and disposition policy. Every independently inventoried item SHALL appear exactly once in the candidate or carry one allowed typed terminal disposition. Candidate counts, candidate hashes, caller prose, bundle fingerprints, and member self-hashes MUST NOT define completeness.

#### Scenario: Candidate shrinks a four-file target to two files and recomputes every fingerprint
- **WHEN** the admitted material root independently contains four included files but a coherent candidate contains two and recomputes all member evidence and outer identities
- **THEN** qualification is `candidate_model`, names the two omitted denominator ids, reports scope-obligation coverage false, and suppresses a qualified claim

#### Scenario: Candidate removes every binding and remains internally coherent
- **WHEN** a candidate removes all object/member/material bindings and recomputes every dependent fingerprint
- **THEN** qualification is blocked by binding-denominator exhaustion rather than accepted as a smaller valid target

### Requirement: External semantic completeness is licensed by an independently signed scope authority

One target-neutral current scope-authority record SHALL independently freeze provenance; target identity, kind, version, official location, and complete material inventory; modeling purpose and completion boundary; included structure identities and per-structure semantic obligations; every required anchor, semantic role, artifact, structure, selector, and distinct occurrence; every SourceGuard, TraceGuard, LogicGuard, and ExperimentGuard required input, output object, and output kind; every cross-member handoff and terminal disposition; LogicGuard scope limits; exclusions; and recursive frontier. The candidate spec, candidate member outputs, candidate parent, bundle identity, and generated obligation evaluation MUST NOT produce or redefine this authority.

The authority SHALL carry an independently produced signature and public producer descriptor but production SHALL contain no authority private key and no built-in trusted authority. A qualifier MUST receive an exact trusted authority fingerprint or trusted authority-producer descriptor fingerprint from the caller. A signature carried in the same DNA bundle proves signature consistency only; it MUST NOT grant trust to itself.

#### Scenario: Every candidate layer is coherently shrunk together
- **WHEN** Source anchors shrink from three to one, Trace events from three to one, Logic occurrence claims from three to one, Experiment hypotheses from two to one, and every downstream binding, state, native evidence, parent mapping, and outer fingerprint is recomputed
- **THEN** candidate internal consistency and native replay MAY pass, but scope-obligation coverage fails against the unchanged signed authority and `dna_qualified` remains false

#### Scenario: The bundled authority is valid but the caller did not trust it
- **WHEN** the DNA carries a valid signed scope authority and complete candidate while the caller supplies neither its exact authority fingerprint nor its producer-descriptor fingerprint as trust
- **THEN** the result is at most `dna_self_consistent`, reports `scope_authority_licensed=false`, and MUST NOT infer trust from the bundled public key

#### Scenario: A genuinely smaller target is independently authorized
- **WHEN** a new authority identity explicitly freezes a one-transition workflow with one JSON-pointer occurrence and smaller four-member obligations
- **THEN** that smaller candidate MAY qualify after exact authority, material, artifact, and native-member trust; it is not compared with the unrelated paper authority or forced to inherit paper counts

### Requirement: External-DNA qualification exposes six independent states

Qualification SHALL separately report `material_inventory_verified`, `member_native_replay_verified`, `candidate_internal_consistency`, `scope_authority_licensed`, `scope_obligation_coverage`, and `dna_qualified`. `dna_qualified` SHALL require all five preceding states plus the native producer trust required by the current composition contract. Missing or invalid authority, authority-required missing objects, unexpected candidate objects, semantic mismatches, or untrusted authority MUST remain visible and MUST NOT be collapsed into material replay, native replay, or candidate self-consistency.

#### Scenario: Authority coverage fails while native replay passes
- **WHEN** a synchronized candidate mutation remains internally well-formed and replays every member-native transition but no longer covers the authority-derived structures, anchors, output kinds, handoffs, limits, or parent interface
- **THEN** `candidate_internal_consistency=true`, `member_native_replay_verified=true`, `scope_obligation_coverage=false`, and `dna_qualified=false`

#### Scenario: A required candidate object is absent
- **WHEN** impact or reverse trace reaches an object required by the scope authority but absent from the candidate graph
- **THEN** impact exposes the `authority-required-but-missing` object and reverse returns `reverse_incomplete` with that gap instead of misclassifying the known required object as an unknown id

### Requirement: Material completeness does not overclaim semantic scope

Every external-domain-DNA target SHALL declare one exact modeling purpose and scope kind, the included question and structure identities, explicit excluded semantic regions, recursive expansion-frontier identities, completion status, and whether whole-target semantics are claimed. Each of the four member models SHALL bind that same scope to its exact complete output-object denominator, exact consumed input-object denominator, and the same expansion frontier. `dna_qualified` SHALL mean qualified only within that declared scope. A complete file/material inventory MUST NOT by itself license whole-target, whole-paper, whole-workflow, or reconstruction-complete semantic understanding. A whole-target claim SHALL require an explicit whole-target scope, complete declared structure coverage, no bounded-scope exclusions, and exact four-member scope agreement.

#### Scenario: Every paper file is accounted for but only one result question is modeled
- **WHEN** all admitted paper files have exact hashes and dispositions while the target scope covers only one declared result-consistency question
- **THEN** the DNA may qualify for that bounded question, reports whole-target semantics as not claimed, preserves the excluded regions and recursive expansion frontier, and does not present 25-of-25 material coverage as whole-paper understanding

#### Scenario: A member silently shrinks its scoped input denominator
- **WHEN** one member omits a declared input object or substitutes a different scope id and every candidate fingerprint is recomputed
- **THEN** qualification blocks because the four native member scope bindings no longer exhaust the declared external-object scope

### Requirement: The composition parent exhaustively accounts child interfaces

The external-domain-DNA parent SHALL be a machine-checkable `Input x State -> Set(Output x State)` FunctionBlock with exact child order; aggregate inputs, state, outputs, and effects; exhaustive child-input source mappings; exhaustive child-output terminal dispositions; typed handoffs; and exactly one owner per field. Every owned object, structure, binding, behavior, claim, event, experiment, evidence reference, and gap SHALL resolve to the exact owning child and parent disposition. Missing, duplicate, conflicting, or orphan ownership MUST block even if all supplied fingerprints are valid.

#### Scenario: A Trace event or Logic claim is omitted but its owned id remains
- **WHEN** the candidate retains an owned id or binding whose Trace event or Logic claim no longer exists
- **THEN** the parent reports the orphan and cannot return `dna_self_consistent` or `dna_qualified`

#### Scenario: Logic scope limits are removed
- **WHEN** a LogicGuard output retains a claim but removes the scope limits that bound that claim and the candidate is coherently re-fingerprinted
- **THEN** native replay and parent-output exhaustion block the top-level boundary from widening

### Requirement: Impact and reverse trace follow complete structure-to-member edges

The external-domain-DNA artifact SHALL bind every admitted root, section, object, and leaf structure identity to its exact member inputs, outputs, behaviors, material locators, native evidence, and parent/child edges. Impact from the root SHALL reach every declared descendant and selected member model. Impact from a local identity SHALL close only over exact declared descendants and consumers. Reverse trace SHALL return the exact structure, object, binding, member, behavior, material, oracle, test, and evidence chain. An unknown identity MUST atomically block and MUST NOT widen to all members.

#### Scenario: A table anchor is rebound to a prose locator
- **WHEN** an anchor keeps its id and value but changes from its independently inventoried table object to a prose locator and all candidate fingerprints are recomputed
- **THEN** object-role and structure-member replay block the candidate

### Requirement: Generic targets share the same member-native topology

Conflicting and non-conflicting paper-like targets and non-paper test/workflow targets SHALL use the same production parent topology and four member-native owner entry points. ResearchGuard MUST NOT force a conflict, fabricate roles or coverage, infer a paper identity, or derive member conclusions from an umbrella domain mode. Target-specific names, values, locators, and expectations belong only to admitted target data or canonical examples.

#### Scenario: A consistent paper-like target is modeled
- **WHEN** all independently extracted anchors agree and the target declares no competing value
- **THEN** SourceGuard preserves the exact source coverage, TraceGuard preserves the admitted sequence, LogicGuard returns its native non-conflict bounded conclusion, and ExperimentGuard derives only the hypotheses supported by those native outputs

#### Scenario: A Source role is invented by the caller
- **WHEN** the candidate adds or changes a SourceGuard role or coverage claim that is absent from the independently replayed target authority
- **THEN** native SourceGuard replay blocks even when all candidate and outer fingerprints are coherent

### Requirement: Canonical external DNA is installed and discoverable without broad prompt loading

The clean ResearchGuard distribution SHALL include the canonical external-domain-DNA model directory and README plus one compact build/inspect facade. The maintained ResearchGuard prompt SHALL conditionally direct an AI to the canonical paper and workflow examples, distinguish current-material qualification from bundle-only self-consistency, and expose exact member, behavior, object, impact, and reverse queries. The default projection SHALL be below 16 KiB and at least ten times smaller than a full bundle whenever the full bundle is at least 160 KiB.

#### Scenario: A fresh installed wheel has no repository access
- **WHEN** an AI in a clean process imports the installed package and inspects the packaged canonical index
- **THEN** it discovers the direct-current commands and canonical model resources without reading the source repository, user profile, or an alternate prompt authority

### Requirement: Native replay caching is exact, bounded, and never material authority

ResearchGuard MAY memoize portable native-composition replay only in a bounded process-local read-only cache keyed by the complete bundle bytes and the normalized exact trusted producer-descriptor fingerprint set. The cache MUST NOT store external material enumeration, file hashes, target extraction, or qualification outcomes; MUST NOT persist to disk or across processes; and MUST NOT provide an alternate, compatibility, or fallback replay path. Mutated bundle bytes or trust identities SHALL miss and execute the current native replay chain. Material-qualified calls SHALL enumerate and hash the admitted material boundary every time, including after a native-replay cache hit.

#### Scenario: The same portable bundle is inspected twice with reordered trust input
- **WHEN** the complete bundle bytes and exact trust set are unchanged but the caller supplies the trust fingerprints in a different order
- **THEN** the normalized key may reuse one immutable native replay result without changing the returned result or exposing mutable cached state

#### Scenario: External material changes after a native cache hit
- **WHEN** a prior request cached the exact portable native replay but a later material-qualified request observes changed or missing target bytes
- **THEN** material replay still executes and qualification blocks; the native cache cannot license the altered material
