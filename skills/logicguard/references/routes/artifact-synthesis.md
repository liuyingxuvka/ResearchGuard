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
14. For source-backed artifact synthesis, include a claim-to-source matrix in the plan: claim, target locator such as paragraph, section, page, slide, or appendix, source ids, source registry ids or citation markers, footnote id when applicable, source role, support boundary, limitation, claim strength, verification status, final treatment, and required inline citation marker. When a LogicGuard model is available, run `researchguard logic citation matrix` and `researchguard logic citation audit` before treating final prose as ready.
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
24. Return current native synthesis readiness, unsupported sections, source fit,
    conclusion boundaries and remaining structural gaps. Final prose integration
    and postwrite review belong to the active writing/document owner. If final
    text changes, that owner rechecks affected claims and citations; no separate
    hand-written closure-ledger checker is required.

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
researchguard logic synthesize examples/logic/structured_artifact_deck.yaml --selection-request <selection-request.json>
researchguard logic synthesize examples/logic/structured_artifact_deck.yaml --selection-request <selection-request.json> --delivery
researchguard logic structure from-markdown examples\structured_report_outline.md --artifact-kind report --output report_model.yaml
researchguard logic outline examples\engineering_efficiency_argument.yaml
researchguard logic citation matrix examples\engineering_efficiency_argument.yaml
researchguard logic citation audit examples\engineering_efficiency_argument.yaml
```

The selection request uses `researchguard.logic.synthesis-request.v1` and carries the target artifact units and goal; `--delivery` adds delivery guidance.

## Native completion and stopping

1. Prepare the exact selection request, current model, real source bindings and required native depth receipt.
2. Call synthesize_artifact_plan, preserving descendant structure-gap propagation to ancestors and current target-proof checks.
3. Return the ready/blocked plan, target units and source/claim matrix. Final prose remains owned by the active writing/document owner.

Stop at the native plan terminal. Graphs, hashes and package shape do not establish synthesis closure; no second handwritten execution package is required.

`researchguard logic route-depth PACKAGE.json` remains an optional declared-package shape diagnostic only. Its pass does not verify native execution, evidence content or task closure.

## Template packs on request

Only when the task requests an existing template pack, load [validated-template-pack.md](../validated-template-pack.md) and use the corresponding native template operation.


## Target-model purpose boundary

For a real target model or native closure claim, retain the current native purpose/guard-model contract and its target-bound known-good/known-bad proof, as described in [broad-depth-and-closure.md](../broad-depth-and-closure.md). Use `researchguard logic guard-contract freeze`, `researchguard logic guard-contract bind`, and `researchguard logic guard-contract verify` with the explicit target root and the current `researchguard.logic.guard_model_contract` owner. Missing, late, stale or non-blocking proof remains non-pass. Internal native `target_skill_id` stays `logicguard`. Viewing, saving, searching and package export do not require a new good/bad model.
