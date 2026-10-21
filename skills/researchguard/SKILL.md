---
name: researchguard
description: Pick the right ResearchGuard member (logicguard, sourceguard, traceguard, experimentguard) for an ambiguous or multi-domain research request, then use that member directly. When the owner is already clear, use the member skill directly.
---

# ResearchGuard

## Routing table

- LogicGuard owns argument structure, source-library work, structured artifacts, model deepening, synthesis, and its project-library viewer.
- SourceGuard owns evidence discovery, retrieval, provenance, source-role gaps, and claim-use qualification.
- TraceGuard owns temporal reconstruction, competing storylines, execution/effect chains, counter-scenarios, and bounded causal narratives.
- ExperimentGuard owns recommendation-only minimum finite experiment sets over declared hypotheses and outcomes.

Several domains: run the members one after another (usual order SourceGuard → TraceGuard → LogicGuard; ExperimentGuard when hypotheses and candidate experiments are declared). Pass results with `researchguard source export-traceguard`, `researchguard trace export-logicguard` and `researchguard logic import-handoff`. Each member's result is only that member's claim; a failed member result stays visible and is not retried through another member.

## Output Requirements

Return the native result, evidence and claim boundary, blockers and next action.
Include full JSON only when it is needed or requested.
