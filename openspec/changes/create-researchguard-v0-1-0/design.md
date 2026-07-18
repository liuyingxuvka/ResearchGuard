## Context

The three current Guard repositories contain mature but separately versioned
native engines. LogicGuard also exposes five satellite Skill IDs and
TraceGuard exposes a separate case-library Skill ID. Logic Writing and other
consumers import or invoke these providers independently, so mixed versions can
look available even when the research workflow is not coherent.

The user requires one clean current path: no runtime compatibility readers,
fallback routes, forwarding aliases, alternate CLIs, or silent downgrade. Old
files are handled by an explicit, rollbackable upgrade operation and are never
normal-runtime authority.

## Goals / Non-Goals

**Goals:**

- Ship one `researchguard` distribution and one CLI at `0.1.0`.
- Preserve four direct semantic entrypoints and three independent native
  member owners.
- Make suite version, content fingerprint, installation, validation, and
  release atomic.
- Preserve the existing LogicGuard, SourceGuard, and TraceGuard mathematical
  and claim boundaries.
- Fold helper/satellite Skill IDs into internal member routes.
- Migrate active consumers directly and prove zero executable legacy
  residuals.

**Non-Goals:**

- Do not merge the three native mathematical models into one generic model.
- Do not let `$researchguard` reimplement a member's native judgment.
- Do not preserve old package names, console scripts, Skill IDs, schemas, or
  aliases for convenience.
- Resolve the installed `researchguard` console executable from the wheel's
  installed distribution record and execute that exact file during installation
  validation. PATH lookup, alternate commands, and fallback launchers are not
  installation authorities.
- Do not make old repositories private before the new release and consumer
  migration are verified.
- Do not treat a typed cross-Guard handoff as automatic fallback.

## Decisions

### One distribution with namespaced native members

The package layout is:

```text
researchguard
├── routing
├── suite
├── logic
├── source
└── trace
```

All internal imports use `researchguard.*`. The wheel exposes only the
`researchguard` top-level package. Keeping three old top-level packages inside
one wheel was rejected because it would preserve three runtime authorities and
let old consumers continue accidentally.

### Four direct Skills, one installation suite

The installable member inventory is exactly:

- `researchguard`
- `logicguard`
- `sourceguard`
- `traceguard`

The umbrella owns only exact intent selection and typed handoff orchestration.
The three members own their full native workflows. Direct invocation and
umbrella dispatch bind the same `business_intent_id`, `primary_path_id`,
`native_owner_id`, suite version, and suite fingerprint.

Installing only some members was rejected because a mixed suite would recreate
the current drift problem. A target-owned suite installer stages all four
consumer projections, verifies their common identity, installs the Python
distribution, and activates the four directories in one rollbackable
transaction.

### Internal routes replace satellite Skill IDs

LogicGuard keeps source-library, structured-artifact, model-deepening,
artifact-synthesis, and project-library-viewer as internal routes. TraceGuard
keeps case-library as an internal route. Their source, native checks, and
receipts remain target-owned; only their direct Skill discovery surfaces are
removed.

Forwarding Skill stubs were rejected because they are runtime aliases and would
keep retired names discoverable.

### Selected route failure is terminal

Routing is performed exactly once. A selected member returns its native
terminal status. A failure, block, missing provider, stale receipt, timeout, or
unsupported boundary is returned unchanged.

A member may emit a typed handoff request. Only `$researchguard` or an explicit
outer owner such as Logic Writing can choose to execute that handoff. The
member does not call a sibling as a rescue route.

### Stable semantic owners, new machine paths

Native owner identifiers remain `logicguard`, `sourceguard`, and `traceguard`
where their contracts already use those stable semantic identities. Machine
paths change to `researchguard.logic`, `researchguard.source`, and
`researchguard.trace`.

Logic Writing calls the exact member directly and verifies the common suite
fingerprint. It never calls `$researchguard` merely to rediscover a route.

### Direct-to-current migration

Migration uses an input snapshot, an evidence-bound disposition ledger,
staging, native validation, an atomic switch, rollback of the whole switch on
failure, and a residual-zero scan. Migration code is not imported by normal
runtime.

Old readers, aliases, and output projections are deleted from current runtime.
An unknown residual blocks the upgrade and remains an explicit AI work item;
it never causes the product to add another reader.

### FlowGuard model

The suite is modeled as these functions:

```text
Route: Intent x Unrouted -> {(MemberRequest, Routed), (TypedGap, Blocked)}
ExecuteMember: MemberRequest x Routed -> {(NativeResult, Terminal)}
RequestHandoff: NativeResult x Terminal -> {(TypedHandoff, AwaitingOwner)}
OrchestrateHandoff: TypedHandoff x AwaitingOwner
  -> {(MemberRequest, Routed), (TypedGap, Blocked)}
InstallSuite: FrozenSuite x InstalledOld
  -> {(InstalledCurrent, Active), (InstalledOld, RolledBack)}
MigrateLegacy: LegacySnapshot x UpgradePending
  -> {(CurrentStaging, Validated), (LegacySnapshot, RolledBack)}
```

No function has an automatic alternate-success edge.

## Risks / Trade-offs

- **Large source migration can introduce import drift** → mechanically rewrite
  imports, then run per-member focused tests before the frozen full suite.
- **Existing consumers can silently use old packages** → uninstall old
  distributions in the isolated install test and scan source, metadata, PATH,
  console scripts, and installed Skill IDs for residuals.
- **Atomic install spans Python and four Skill directories** → stage all
  artifacts first, record the previous state, activate under one transaction,
  and roll back the entire transaction if any post-activation check fails.
- **One suite can make unrelated member tests expensive** → use exact
  component edges for affected checks during development, but require one full
  suite validation on the frozen release snapshot.
- **Private old repositories can break public links** → delay privacy changes
  until v0.1.0, remote CI, consumer migration, documentation, and link scans
  are current.

## Migration Plan

1. Freeze the three source revisions, contracts, tests, and consumer
   projections.
2. Create the new repository and OpenSpec/FlowGuard/SkillGuard authority.
3. Move native code into the namespaced package and remove compatibility
   surfaces.
4. Create the four Skills and target-owned atomic installer.
5. Run focused native tests and residual scans.
6. Migrate Logic Writing and all located active consumers.
7. Freeze source/toolchain/check inventory and run one full suite validation.
8. Build and test the `0.1.0` distribution in an isolated environment and
   isolated `CODEX_HOME`.
9. Publish the public repository, tag, Release, and exact-commit CI.
10. Recheck consumers and public links.
11. Make the three old repositories private.

Rollback is transaction-wide before release: restore the pre-migration
environment and old repository visibility. After release, defects require a
new ResearchGuard version; old runtime aliases are not restored.

## Open Questions

None. The user fixed the release version at `v0.1.0` and approved the
four-entry, one-runtime, zero-fallback architecture.
