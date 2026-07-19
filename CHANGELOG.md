# Changelog

## v0.1.2 - 2026-07-19

- Refresh the four ResearchGuard author-side SkillGuard contracts and current
  FlowGuard adoption records without exposing maintainer evidence to consumers.
- Keep `researchguard` as the single runtime distribution while preserving
  ResearchGuard, LogicGuard, SourceGuard, and TraceGuard as direct skill
  entrypoints backed by exactly three native member owners.
- Support one direct `v0.1.1` to `v0.1.2` replacement transaction with no
  compatibility reader, alias, alternate launcher, or fallback runtime.

## v0.1.1 - 2026-07-18

- Bind durable mesh-store receipts and fingerprints to the current
  `researchguard` package identity only.
- Prove that a retired `logicguard` distribution being present or absent cannot
  change the current ResearchGuard fingerprint.
- Strengthen zero-residual checks so retired Python imports, distribution
  metadata queries, and declared dependencies block release.
- Directly migrate the current SourceGuard examples to the v0.1.1 suite
  identity and bind them into the SourceGuard maintenance graph.
- Support one direct `v0.1.0` to `v0.1.1` replacement transaction without
  introducing a compatibility reader, alias, or fallback runtime.

## v0.1.0 - 2026-07-18

- Consolidate LogicGuard, SourceGuard, and TraceGuard into one versioned
  `researchguard` distribution.
- Preserve four direct Codex Skill entrypoints backed by three native member
  owners.
- Replace satellite Skill IDs with internal member routes.
- Require terminal selected-route failure, typed handoffs, atomic suite
  installation, and zero normal-runtime compatibility readers or fallbacks.
