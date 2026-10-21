## Why

ResearchGuard v0.1.0 computes the LogicGuard ModelMesh store fingerprint from
the retired `logicguard` distribution. A machine with that predecessor
installed therefore writes a foreign version into current ResearchGuard
receipts, while a machine without it falls to `0+local`; the same ResearchGuard
source can produce different durable identities.

## What Changes

- Make the ModelMesh store fingerprint and commit receipt use the sole current
  ResearchGuard package identity.
- Remove all normal-runtime metadata queries, imports, or dependencies on the
  retired `logicguard`, `sourceguard`, and `traceguard` distributions.
- Add regression evidence proving that the LogicGuard predecessor distribution
  being present or absent cannot change the fingerprint.
- Strengthen predecessor-absence checks so a future old-package import or
  metadata lookup fails validation.
- Update the existing FlowGuard model-miss evidence and all four member
  contracts in the existing ResearchGuard SkillGuard maintenance unit.
- Release and install ResearchGuard `v0.1.1` as one Python distribution and
  four clean consumer skills with no compatibility or fallback route.

## Capabilities

### New Capabilities

- `researchguard-package-identity`: Defines the sole current package identity
  used by durable ModelMesh fingerprints, predecessor-absence requirements,
  direct upgrade behavior, and release/install parity.

### Modified Capabilities

None. The repository has no synchronized main OpenSpec capabilities; the
v0.1.0 planning change remains historical context rather than a mutable
v0.1.1 authority.

## Impact

Affected surfaces are `src/researchguard/logic/mesh_store.py`, package/version
metadata, the direct installer, predecessor-residual checks, FlowGuard suite
models and adoption evidence, all four member SkillGuard contracts, tests,
documentation, Git/tag/Release identity, and the four installed Codex skills.
The public CLI and member routing semantics do not change.
