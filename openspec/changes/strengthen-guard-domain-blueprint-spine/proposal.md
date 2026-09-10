## Why

The ResearchGuard suite has strong member-specific reasoning engines, but those models are not yet exposed as one composable set of living domain blueprints: ExperimentGuard lacks a procedural hierarchy, LogicGuard lacks enforced child-output/parent-input closure, SourceGuard has split graph authority, TraceGuard's hierarchy is mostly implicit, and the umbrella cannot carry exact model identity and localized invalidation without interpreting member payloads. The repository also lacks one complete software self-DNA that binds those domain models to the implementation, tests, intent, resources, and topology that realize them. This change completes both layers while preserving every member's independent semantics and preventing five overlapping repository blueprints.

## What Changes

- Add a stable opaque member-model envelope and typed handoff-field contract to ResearchGuard, including exact schema/model fingerprints, receipt and gap references, one producer, declared consumers, localized stale propagation, and reverse trace.
- Add a hierarchical ExperimentGuard design blueprint covering hypotheses, candidates, manipulation/observation/outcome ports, procedure steps, constraints, external execution ownership, and the existing recommendation matrix.
- Add LogicGuard block-interface closure and an artifact inventory independent from the argument model, with exact parent/child consumption, content identity, impact, and reverse trace.
- Make SourceGuard's typed graph the sole schema authority and add content/extractor/provider fingerprints plus an end-to-end target-unit-to-gap-to-source-to-anchor-to-claim blueprint.
- Add a deterministic TraceGuard hierarchy and typed interfaces compiled from the current model and canonical solver receipt, with no second score, solver, or fallback.
- Add member-native blueprint check, impact, trace, and export commands while keeping the umbrella payload-opaque and retaining current minimum-sufficient routing.
- Replace member-authored target authority with one provider-neutral `ExpectedTargetAnchor` admitted before member modeling. The anchor freezes the original task/request identity, target identity, exact raw-material locator and fingerprint, and external admission owner/producer receipt. Umbrella admission may produce it from original task facts; direct member use must receive it externally or remain visibly unverified. Member checks may replay only the frozen anchor and cannot admit a replacement target, accept an arbitrary locator, or expose a production candidate-to-target authoring shortcut.
- Replace caller-shaped native receipt references with a closed immutable receipt resolver. Every model, interface, depth, and owner receipt used for qualification binds its producer, request, input, result, member, model, checker, status, locator, and exact bytes; a caller-invented id or self-hash is never evidence.
- Close composition readiness around one exact registered member checker per envelope. The member independently replays its externally admitted target anchor and resolves the opaque request, input, result, receipt, and terminal from immutable producer bytes; the umbrella only compares the resulting transport attestation and cannot accept a generic, caller-self-hashed, or never-published substitute.
- Make every composition-derived impact or reverse-trace query qualification-first across the complete selected member set, including the four-member case: one blocked member atomically suppresses all ordinary affected, unaffected, path, and terminal projections, and the CLI exits non-zero without returning a usable partial result.
- Freeze the complete native-receipt producer descriptor in every expectation—producer id and version, signature algorithm, signing-key id, public-key fingerprint, and descriptor fingerprint—so a different registered signer can never satisfy an otherwise similar expectation.
- Add a deterministic portable member-composition bundle and an internal isolated-bundle integrity qualification that succeeds from bundle bytes alone only when all required anchors, envelopes, handoffs, native receipts, producer descriptors, and native attestations replay exactly; no repository checkout, process registry state, prose, or external agent is used to fill a missing identity.
- Require every executable behavior case used as blueprint evidence to declare `Input`, `PreState`, permitted `Output`, `PostState`, `Effect`, protected `Failure`, and native `Oracle`, and require all tests that admit anchors or receipts to use an explicit isolated authority root rather than the user's real authority installation.
- Require impact and reverse-trace operations to consume one current member-native blueprint qualification before returning ordinary affected sets or complete trace closure; failed, stale, unverified, and not-run qualification remains an atomic blocker.
- Update the five maintained skills, prompt bundles, native contracts, and tests with conditional loading and token-budget checks.
- Add a later-bound single ResearchGuard repository software-DNA root with LogicGuard, SourceGuard, TraceGuard, and ExperimentGuard child subtrees only after the external FlowGuard toolchain is stable. The root owns admission, routing, composition, envelopes, handoffs, and authority behavior; every member subtree continues downward into multiple concrete behavior owners. Existing member-domain blueprints remain domain DNA and never become competing whole-repository blueprints.
- Qualify software self-DNA against a complete provider-neutral repository denominator in which every admitted code, test, intent, resource, topology, public-surface, configuration, and non-Python item has one terminal disposition and every behavior-bearing item has one primary owner. Python inspection is one convenience adapter, not the target-language boundary.
- Add exact forward and reverse bindings, seven explicit readiness layers, affected-only ordinary loading, and externally materialized canonical export so the model can report what it understands, what remains unresolved, and what a change can affect without fingerprinting its own generated output.
- Permit architecture reduction only after the software-DNA model is proof-ready for the affected observable contract; duplicate or dead-path candidates remain findings until their behavior-preserving disposition and evidence are current.
- Make the repository installer delegate every installed skill tree to SkillGuard's current consumer-distribution and target-installation authorities, require a current `consumer-release.json` plus target transaction receipt, and reverse-roll back already activated members when a later member fails.

## Capabilities

### New Capabilities

- `researchguard-member-model-envelope`: Opaque member model identities, typed handoffs, consumer acknowledgement, affected-only invalidation, and cross-member reverse trace.
- `experimentguard-domain-blueprint`: Hierarchical experiment design and observation model bound to the current finite recommendation engine.
- `logicguard-domain-blueprint`: Argument/artifact hierarchy with explicit block interfaces, independent artifact inventory, bindings, impact, and reverse trace.
- `sourceguard-information-blueprint`: One typed evidence-discovery graph authority with source/anchor identity, complete target universe, affected-only invalidation, and reverse trace.
- `traceguard-trace-blueprint`: Deterministic investigation hierarchy and interfaces projected from the canonical inference receipt.
- `researchguard-flowguard-blueprint-bindings`: One later-bound ResearchGuard repository software-DNA root with four recursively decomposed member subtrees, complete provider-neutral implementation ownership, seven-layer readiness, model/code/test/intent/resource/topology bindings, affected and reverse indexes, external canonical export, and proof-gated architecture reduction.
- `researchguard-consumer-projection`: One ordered five-skill consumer projection using SkillGuard-owned preparation, verification, activation, receipt, lock, recovery, and rollback semantics with exact release identity, zero author-control files, explicit obsolete-surface blocking, and read-only installed-currentness audit.

### Modified Capabilities

- `researchguard-member-model-loops`: Task-local member revisions must publish current model identity, exact affected obligations, native receipt lineage, first unresolved gap, and bounded closure.
- `researchguard-narrow-entry-loading`: Routing remains minimum-sufficient and member-native while blueprint references are loaded only for the selected member, operation, and affected slice.

## Impact

This affects ResearchGuard admission/routing/composition and CLI code, the shared target-anchor and native-receipt contracts, all four member runtimes, five maintained skill prompts and author contracts, prompt manifests, focused and cross-member tests, the single FlowGuard repository self-DNA after toolchain stabilization, installed consumer projections, and the patch release. ResearchGuard remains the repository root owner for umbrella admission, routing, composition, envelopes, handoffs, and authority transport; it never becomes a shared member-domain solver or payload interpreter. Direct members consume externally owned anchors and cannot issue their own task target.

## Current implementation-round amendment (R00–R10, 2026-09-09)

The proposal above records the broader domain-blueprint intent and remains an
immutable historical design statement until this change is archived. The
current recovery round uses the same native member semantics but executes them
through a bounded, local, evidence-first sequence. R05 closes the distinction
between the 63-case self-DNA coverage map and strict native parent/child
execution. R06 gives the suite checker a bounded terminal path and re-runs
current member owners only after source and toolchain identities are frozen.
R07 prepares clean consumer projections and an isolated ResearchGuard package
and console. R08 exercises that installed console through LogicWriting's
production reader chain. R09 closes model/test/installation parity, and R10
publishes only the reviewed public source allowlist.

The ResearchGuard boundary is explicit: the repository owns native domain
semantics, opaque envelopes, target-anchor admission, immutable receipt
resolution, and the five-skill installation transaction. LogicWriting owns
reader ordering, materiality, composition, and prose evaluation. ResearchGuard
does not author a target from a caller-shaped candidate, interpret a
LogicWriting score, or provide a fallback solver. A directory count, an old
receipt, a synthetic fixture, or a successful package build cannot close a
native model or product claim.

The appended R00–R10 ledger in `tasks.md` is the current implementation and
acceptance source. It records implementation, protocol evidence, current
model closure, real quality, and installed-currentness as separate states.
The historical task checkboxes above remain useful for intent coverage, but a
checked historical row is not evidence that the corresponding current-round
receipt exists.
