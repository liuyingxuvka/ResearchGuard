# ExperimentGuard model protocol

Load this only for explicit experiment-blueprint work. Ordinary minimum-set recommendation continues through the normal ExperimentGuard route.

## DNA ownership boundary

This blueprint is ExperimentGuard member-domain DNA: it owns experiment-design meaning, discrimination obligations, procedure interfaces, observations, and external execution boundaries. It may supply semantic obligations to the ExperimentGuard subtree under the sole FlowGuard-owned ResearchGuard repository software-DNA root, but it is not a whole-repository software blueprint. Code, test, intent, resource, topology, repository-denominator, seven-layer readiness, canonical-export, installation, and release claims remain with that root and their native evidence owners. Native experiment closure and repository software-DNA readiness therefore stay separate.

Model one rooted design hierarchy: purpose → discrimination obligation → candidate experiment. Candidate blocks declare typed input, manipulation, observation, and outcome ports; ordered procedure steps; constraints; external execution owner; and exact input bindings. Every consumed child output names one parent input and binds exact schema refinement, derived payload/model/result fingerprints, current task identity, and a current receipt; otherwise it remains explicitly dispositioned. ExperimentGuard never executes the external experiment.

The independent target universe—not the design itself—lists every required hypothesis, discrimination block, candidate, port, procedure step, constraint, input binding, child-output binding, and native good/bad case. Freeze those targets in an exact request contract plus a replayable raw-material locator and content hash. The request id is the content address of that request, and the target revision is the content address of the independently authored target inventory. Production exposes no candidate-to-target snapshot builder: the caller supplies already-existing raw material, and ExperimentGuard's current closed adapter parses it on issuance and every serialized reload. It compares that denominator with both universe and design; no process-global first-seen value or co-shrunk candidate can become authority by receiving a new signature. Current native case receipts must be replayed through the same design validator and finite recommendation engine. A changed/missing local snapshot blocks, and an external locator that cannot be replayed is explicitly unverified.

External expected-target admission fixes the experiment target and denominator; ExperimentGuard-native parsing separately interprets the admitted bytes. Anchor and immutable receipt locators/hashes are persistent evidence and cache state is never authority. Direct blueprint use without admission is unverified, and a different target requires a separately admitted anchor. Production has no public or generic target, attestation, or receipt issuer and no inline candidate-authoring path. Impact and reverse trace each perform exactly one current closed native replay over resolved evidence.

Use the one grouped native surface:

- `researchguard experiment blueprint check <spec.json>`
- `researchguard experiment blueprint impact <spec.json> <changed-id>...`
- `researchguard experiment blueprint trace <spec.json> <experiment-id>`
- `researchguard experiment blueprint export <spec.json>`

Impact and reverse trace each consume exactly one current blueprint qualification before returning ordinary closure. Failed, stale, unverified, or not-run material/authority suppresses affected and unaffected lists and leaves the trace incomplete with the precise qualification gaps. Once admitted, impact follows candidate/port/procedure/constraint/binding → referencing predictions and hypothesis pairs → recommendation and native receipts, while a directly changed hypothesis reaches its candidate matrix and design ancestors. Unknown ownership suppresses all partial impact. Reverse trace ends at the declared laboratory owner and external observation boundary. Blueprint completeness proves only the caller-declared design and finite discrimination contract.

The reverse gate is ordered, not merely descriptive: run that qualification exactly once and require `status=complete` before resolving the requested experiment, indexing blocks, walking ancestry, or deriving hypothesis pairs. If qualification is not current, return one atomic rejected report with `partial_result_suppressed=true`; design/path/port/binding/terminal fields stay empty, and only qualification, material/authority/receipt gaps plus the claim boundary remain. An unknown experiment id never bypasses this gate or replaces the qualification report with a target-resolution error.
