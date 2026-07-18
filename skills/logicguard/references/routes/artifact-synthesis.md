# Internal LogicGuard route: artifact-synthesis

This is an internal LogicGuard route for building a new target story from existing modeled material. Use it after sources, argument nodes, or structured blocks exist, or when the user explicitly asks to synthesize a target artifact from them.

Use the LogicGuard CLI entrypoint:

```powershell
researchguard logic <args>
```

## Workflow

1. Require a target goal before synthesis. If the goal is absent, infer only when the prompt makes it clear.
2. Before final prose for non-trivial work, check model-mesh readiness. Require or inspect a model-card index, structural contribution graph, coverage summary, gap ledger, paragraph/page/slide blueprints for core blocks, source mapping for important claims, literature/technology progression rows when relevant, method-depth rows when relevant, figure/table rows when relevant, and unresolved limitation list. If these are missing, produce a missing-model worklist or deepening plan instead of final copy.
3. Select material from existing model nodes, source-library links, anchored source branches, structured blocks, and structural contribution rows using importance as a cross-cutting signal.
4. Carry source temporal context when available: use `source_date` and `coverage_period` to organize background, updates, current-context material, and unknown-time material.
5. Treat source-library branches as provenance-preserving chunks when they fit the target goal.
6. Mark missing support, bridge, evidence, limitation, downstream consumer, or conclusion recovery as a missing addition. Do not invent evidence or hide structural gaps with smoother transitions.
7. When missing additions need sources, route them through the gap ledger and `route:source-library`: search existing modeled sources first, then intake/model/link new sources only when needed.
8. Use treatment guidance from synthesis items: `deep` material should get prominent support/warrant/boundary treatment, `normal` material belongs in the main story, `brief` material is context, `appendix` material stays available outside the main path, and `omit` material is left out unless the user explicitly needs it.
9. For each `deep` or core synthesis item, expand the internal support chain before final prose: problem or need, mechanism, evidence, warrant, boundary, reader value, and likely rebuttal when relevant.
10. If a core item lacks evidence, warrant, boundary, source support, rebuttal handling, downstream use, or conclusion recovery, keep it as a missing addition or under-modeled item instead of smoothing it into confident copy.
11. For Research Reasoning Atlas synthesis, include conclusion tournament state for central claims: preferred conclusion, steelman opposition, live alternatives, selected model lens or warrant, expert stance role when relevant, winner, and allowed wording.
12. Produce an inspectable target story plan before final prose, slides, report copy, paper sections, memo blocks, article sections, or deck storyline pages. For important prose generation, the target story plan should be detailed enough to act as a section, paragraph, page, or slide blueprint and should show which later unit consumes each non-background high-importance unit. For literature and technology review material, show how neighboring items progress, narrow, contrast, or become background; for methods, show why choices were made rather than only which steps happen.
13. Preserve the requested artifact genre. Do not force source-role categories, diagnostic tables, tournament tables, or fact/official-claim/inference/gap headings into the reader-facing artifact unless that improves the requested artifact.
14. For source-backed artifact synthesis, include a claim-to-source matrix in the plan: claim, target locator such as paragraph, section, page, slide, or appendix, source ids, source registry ids or citation markers, footnote id when applicable, source role, support boundary, limitation, claim strength, verification status, final treatment, and required inline citation marker. When a LogicGuard model is available, run `logicguard citation matrix` and `logicguard citation audit` before treating final prose as ready.
15. For long artifacts, include a reader route in the plan: first question answered, why each section or artifact unit follows, who consumes important earlier material, where limitations appear, which obligations return in the conclusion, and where forecasts begin.
16. For substantive source-backed artifacts, keep claim origin, direct facts, source statements, scope boundaries, execution or outcome evidence, context or motive evidence, interpretation, counter/limiting evidence, and forecast triggers separate in the reasoning plan. Do not let commentary or motive context stand in for execution, causality, outcome, or broader-scope evidence.
17. Translate through a delivery profile such as `presentation`, `paper`, `report`, or another user-requested artifact genre so visible copy sounds artifact-native. When an upper-level domain workflow is active, synthesis should return the story plan, unsupported sections, and wording boundaries to that workflow instead of independently claiming final prose closure.
    For thesis or dissertation revision, artifact-native prose usually means
    integrating new material with the surrounding original paragraphs. Rewrite
    neighboring original text, headings, and transitions when needed for a
    coherent academic voice, while preserving the user's revision-provenance
    policy.
18. For source-backed profiles, final prose should include compact inline citation markers or artifact-appropriate source markers for important claims and should not rely only on a final bibliography. Paragraphs or artifact units that mix evidence, source claims, interpretation, and synthesis should say who says what in ordinary prose.
19. Reconcile final prose with the structural contribution graph, source registry, quality-gate ledgers, and conclusion tournament when they exist. Check that every non-background high-importance unit has a parent goal, a unit job, a downstream consumer or final treatment, and conclusion recovery when material; literature/technology items either progress from siblings or are explicitly background; method choices expose depth; figure/table references have body explanation and argument role; every marker resolves; duplicate ids are not ambiguous; source roles match paragraph wording; announcement/context sources are not used as execution, outcome, causality, scope, or forecast support; and final wording does not exceed the tournament result. For thesis workflows, treat this reconciliation as input to contribution-and-expression integration owned by the thesis workflow.
20. Surface temporal limitations in final copy only when they materially affect core claims, conflicts, current-state conclusions, or evidence freshness; do not force every artifact to include a timeline or risk page.
21. Remove internal workflow labels from reader-facing artifact copy unless the user explicitly requests a methods appendix.
22. Rerun argument, structure, structural-contribution, literature progression, method-depth, figure/table, citation, conclusion-tournament, and postwrite
    closure checks when final text, citation markers, claim-to-source matrix,
    target locator mapping, final treatment, source registry, tournament
    result, revision provenance, or structure materially changes.
23. After selecting a non-trivial synthesis route, usually show a compact AI-selected Mermaid diagram or table. A synthesis route is often best, but AI may choose an argument-support map, source-path view, structural-contribution graph, gap table, tournament table, structure map, or comparison matrix if that better explains the target story. Use explicit edge semantics: selected material contributes to target blocks, downstream consumers use prior units, missing bridges block or qualify target blocks, and appendix/brief/omit treatment changes placement rather than truth. Keep the diagram in the explanation, not in final artifact-native copy.
24. Before final artifact-native prose is treated as ready, update the main
    LogicGuard closure ledger with synthesis readiness: target story plan
    status, unsupported sections, citation/source-fit status, conclusion
    tournament status, structural-contribution recovery, postwrite audit
    freshness, safe wording, and unsafe wording. If final text changes after
    the audit, mark `postwrite_status` stale and rerun the main closure helper.

## Boundaries

- Return to the general LogicGuard route when the request is mixed or no target synthesis goal exists.
- Use `route:source-library` first when concrete source material still needs preservation.
- Use `route:structured-artifact` first when the existing artifact structure has not been audited.
- Keep internal diagnostic labels out of final artifact copy.
- When an upper-level writing workflow is active, do not claim final
  domain-native prose closure from synthesis alone.
- Synthesis diagrams are LogicGuard-specific and must not depend on FlowGuard diagram rules or a shared cross-family protocol.

## Common Commands

```powershell
researchguard logic synthesize examples\structured_artifact_deck.yaml --goal "Build a customer validation deck"
researchguard logic synthesize examples\structured_artifact_deck.yaml --goal "Build a customer validation deck" --profile presentation --delivery
researchguard logic structure from-markdown examples\structured_report_outline.md --artifact-kind report --output report_model.yaml
researchguard logic outline examples\engineering_efficiency_argument.yaml
researchguard logic citation matrix examples\engineering_efficiency_argument.yaml
researchguard logic citation audit examples\engineering_efficiency_argument.yaml
```

## Native execution-depth receipt gate

Before broad final wording, run `researchguard logic depth <model.yaml> --output <logic-depth-receipt.json>` against the final current model. A broad synthesis claim requires matching model and authoritative-universe fingerprints, the LogicGuard-owned threshold, complete requested claim scope, role-complete important cards or closed dispositions, no unresolved target/disconnected important unit, no unresolved comparable conclusion, every critical perturbation effective, no untested important node, and `broad_claim_licensed: true`. A root plus a token support sample cannot satisfy this gate. LogicGuard exposes one enforced depth route; callers cannot select a lighter profile or threshold. A blocked receipt means keep the prose qualified or return to modeling. Target-owned regression calibration is required but is not per-run evidence. The receipt comes from LogicGuard's native evaluator/simulator.

Then bind that exact native receipt to the synthesis route with
`researchguard logic route-depth PACKAGE.json --output RECEIPT.json`
using target `route:artifact-synthesis`, owner
`logicguard.artifact-synthesis`, and route
`route:route:artifact-synthesis:synthesize`. The package must reconcile
the complete synthesis-unit universe and prove each unit's parent goal, job,
support path, downstream consumer, and final treatment. This route receipt
cannot upgrade a bounded or blocked `logicguard depth` receipt.
Declare a non-empty authoritative `important_unit_ids` denominator. An important
or required synthesis unit cannot be excluded or reclassified; another exclusion
needs current hashed evidence, a closed non-contributing/not-applicable disposition,
and no claim contribution.

Counts, role-name lists, catalog expansion, whole-receipt hashes, and ordinal
ranges are not per-obligation evidence. Every satisfied synthesis obligation
must retain its exact target-native semantic object, `evidence_ref`, and
lowercase content hash; a missing, renamed, overlapping, mechanically generated,
or summary-only mapping blocks broad synthesis closure.



<!-- BEGIN MANAGED VALIDATED TEMPLATE PACK -->
## Validated Template Pack Routing

- Target families: `family:logicguard-template-packs`; native owner: `owner:logicguard-template-packs`.
- Current catalogs: `catalog:logicguard-template-packs` revision `1.0.0`.
- Resolve the task through this Guard's native router first, then ask the target-owned adapter for a current neutral projection; never infer a template from wording or a skill name.
- Preserve the adapter's complete candidate and rejection accounting. Zero candidates may use only the declared validated base; one candidate gets a read-only preview; many candidates require complete dependencies, pairwise compatibility, one field owner, and target-authored dominance or must block as ambiguous.
- Recompute the projection immediately before applying a preview. A stale request, catalog, route, builder, validator, or content identity blocks all writes.
- Hand the selected preview to the target-declared builder and consume every target-native validator receipt. Template structure is not domain validity, completion, installation, release, or publication evidence.
- Record a harvest disposition after creating or materially deepening a reusable model, and keep no-match evidence visible.
- Declared validated bases: `logicguard.base`.
- Template inventory: `logicguard.argument`, `logicguard.base`, `logicguard.deepening`, `logicguard.execution-package`, `logicguard.purpose`, `logicguard.source-library`, `logicguard.structured-artifact`, `logicguard.synthesis`.
- Native validator inventory: `logicguard-template-pack:argument`, `logicguard-template-pack:base`, `logicguard-template-pack:deepening`, `logicguard-template-pack:execution-package`, `logicguard-template-pack:purpose`, `logicguard-template-pack:source-library`, `logicguard-template-pack:structured-artifact`, `logicguard-template-pack:synthesis`.
- Claim boundaries: This unsealed catalog spec projects current LogicGuard-owned templates for target-owned candidate accounting only. Catalog digests and receipts remain LogicGuard-owned derived records.
<!-- END MANAGED VALIDATED TEMPLATE PACK -->

<!-- BEGIN MANAGED PURPOSE AND BLOCKABILITY -->
## LogicGuard purpose and blockability contract

Packaged baseline purpose: Prevent a final story, outline, or prose plan from being issued while its goal, complete unit inventory, important support, source/gap reconciliation, blueprints, delivery boundary, or postwrite freshness is incomplete.

Baseline claim boundary: A pass licenses only the current target artifact plan and exact modeled support paths; it does not prove source truth or final prose quality outside the receipt.

The repository keeps these representative baseline failures only to prove that the native verifier can block them:

- `Target goal or unit inventory is incomplete`: block when the final artifact goal or complete target-unit inventory is missing.
- `Important claim support is absent`: block when an important claim lacks a current support path.
- `Source or gap reconciliation is unresolved`: block when supporting sources or named gaps have no closed disposition.
- `Blueprint or downstream use is incomplete`: block when required synthesis blueprints or downstream consumers are missing.
- `Delivery boundary or freshness is overclaimed`: block when delivery scope or postwrite freshness is absent or stale.

These packaged examples are not the purpose of a real target model and cannot authorize one. Before building every real model or route result, AI must write a target-local `logicguard.target_model_purpose_declaration.v1` under the explicit target root. AI declares what this exact model is meant to prevent, its bounded claim, the exact candidate path, and one or many current failure declarations. Every current failure binds one LogicGuard-native oracle plus one target-owned known-good and known-bad case. Then AI freezes `.logicguard/guard-purpose-contract.json` while the candidate path is still absent, builds the candidate, binds it to the frozen fingerprint, exhausts every declared proof, and only then requests native closure.

Missing declarations, late declarations, stale fingerprints, non-blocking bad cases, failing good cases, or a candidate that exposes any declared failure are non-pass. There is one enforced route and no selectable mode, threshold, compatibility reader, fallback, or lighter success path. Evidence insufficiency may narrow the final claim, but it does not select a weaker check.

`guard-model/verify.py` is the LogicGuard-native verifier. `guard-model/baseline-*.json` proves only family capability.
<!-- END MANAGED PURPOSE AND BLOCKABILITY -->
