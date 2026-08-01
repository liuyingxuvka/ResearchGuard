# Source Model Protocol

SourceGuard is one POMDP-style approximate evidence-discovery planner. It maintains a source/gap belief graph, proposes search actions, ranks expected utility, accepts real observations, updates semantic state, and exports candidate handoffs. Utility is not truth, calibrated probability, or final confidence.

Before any non-trivial model, freeze a target-local `sourceguard.model_guard_contract.v2`: exact prevention purpose, external target-unit/source/gap/lineage/anchor universe, task-specific failures, one SourceGuard-native blocking oracle and target-owned good/bad case per failure, and claim boundary. Bind the candidate to that exact current sidecar. Missing, late, stale, inferred, or family-baseline-substituted purpose blocks.

Prefer a model-gap coverage network over a broad bibliography. Preserve `gap_id -> model_card_id -> claim -> source_role -> search_action -> candidate_source -> can_support -> cannot_support -> status`. When structure context exists, retain unit, parent goal, contribution type, downstream consumer, and structural role as handoff context without taking ownership of final artifact structure.

Search results and source candidates remain candidates. Semantic lifecycle is `discovered`, `observed`, `qualified`, `claim_usable`, `contradicted`, `blocked`, or `closed`. One current `semantic_state` and a complete closure basis are the sole authority; retired projections are rejected.
