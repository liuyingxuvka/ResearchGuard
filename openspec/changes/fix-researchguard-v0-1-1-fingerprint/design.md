## Context

The current ModelMesh store defines one durable tool fingerprint at module
load and writes the same package version into commit receipts. In v0.1.0 both
values come from `importlib.metadata.version("logicguard")`. That predecessor
distribution is outside ResearchGuard authority and may be present at version
0.18.0, absent, or independently changed, so it cannot identify current
ResearchGuard code.

The repository already has one FlowGuard suite model, one ResearchGuard
SkillGuard maintenance unit with four member contracts, a direct installer for
one Python distribution and four consumer skills, and fail-closed no-fallback
rules. This change extends those owners instead of adding an identity adapter
or compatibility reader.

## Goals / Non-Goals

**Goals:**

- Bind every ModelMesh store package version and tool fingerprint to the
  current `researchguard` package version.
- Prove the result is invariant when the retired `logicguard` distribution is
  absent or reports arbitrary versions.
- Reject old-package imports and metadata lookups anywhere in normal runtime.
- Upgrade the sole package and four skills directly to v0.1.1 and prove exact
  source/install/repository/tag/Release identity.

**Non-Goals:**

- Changing member routing, research semantics, schemas, or persisted ModelMesh
  layouts.
- Reading or migrating a legacy fingerprint at runtime.
- Keeping an alias, wrapper, old console command, alternate distribution, or
  fallback version.
- Reopening or rewriting the historical v0.1.0 OpenSpec authority.

## Decisions

### Use the imported ResearchGuard package version as the sole runtime identity

`mesh_store` will import the current package `__version__` through its
ResearchGuard package boundary and use that value for both the durable
fingerprint and commit receipt. It will not query distribution metadata.

This is preferred over changing the metadata query from `logicguard` to
`researchguard`: source-tree validation can otherwise observe an older
installed ResearchGuard distribution and still produce a foreign fingerprint.
It is also preferred over `0+local`, environment variables, or a second
version source because those are fallback or parallel authorities.

### Generalize predecessor-absence validation

The existing zero-residual check will parse current Python runtime sources and
reject top-level imports of retired member distributions plus literal
`importlib.metadata` queries for them. It will also reject retired
distributions in declared package dependencies. Tests will exercise both the
scanner and the fingerprint under simulated predecessor-present and
predecessor-absent environments.

### Backpropagate the miss into the existing FlowGuard suite model

The existing product-runtime model will gain one package-identity FunctionBlock
and scenarios for predecessor-present and predecessor-absent states. Both
states must produce the same ResearchGuard-owned version and fingerprint, with
no alternate success. The model identifier advances to v0.1.1 and the adoption
log records the observed v0.1.0 false negative and current closure evidence.

### Preserve the existing four-member SkillGuard unit boundary

The single ResearchGuard maintenance unit retains four member contracts and
member-owned checks for `researchguard`, `logicguard`, `sourceguard`, and
`traceguard`. Version/identity and predecessor-absence changes are compiled
into every affected member contract. Consumer projections exclude
`.skillguard`, and no external unit receipt is consumed.

### Replace v0.1.0 directly with v0.1.1

The installer will build exactly one v0.1.1 wheel, force-replace the current
`researchguard` distribution, transactionally replace the four consumer
skills, remove retired skill ids, and run currentness plus CLI checks. There
is no first-install-only branch, version alias, dual package, or automatic
downgrade. Skill activation retains its existing rollback boundary; any
unverified package or skill state is visible as blocked.

### Freeze one release commit

After all source and maintenance evidence is current, one reviewed commit is
merged to `main`. The Python distribution, four installed skills, local and
GitHub default branch, annotated `v0.1.1` tag, and source-only GitHub Release
must resolve to that frozen content identity. The Release has zero assets.

## Risks / Trade-offs

- **[Version constants drift across files]** → Keep explicit suite checks for
  package, CLI, installer, documentation, and test version identity.
- **[A scanner produces false positives for legitimate member ids]** → Restrict
  dependency findings to executable imports, exact metadata calls, and package
  dependency declarations; member routing strings remain allowed.
- **[Installed smoke checks generate bytecode outside the projection]** → Run
  them with `PYTHONDONTWRITEBYTECODE=1` and audit every installed skill against
  the source inventory afterward.
- **[Package replacement succeeds but a later check fails]** → Report the
  installation as blocked, restore the four-skill activation through the
  existing backup boundary, and do not publish or claim currentness.

## Migration Plan

1. Freeze v0.1.0 failure evidence and update OpenSpec/FlowGuard ownership.
2. Implement the sole package identity and predecessor scanner with focused
   known-bad and same-class tests.
3. Update version surfaces and all four SkillGuard contracts.
4. Run focused tests, FlowGuard scenarios, OpenSpec validation, every
   SkillGuard unit check, then one frozen full test run.
5. Commit, push, review, merge, and use the merge commit as the release
   identity.
6. Build/install v0.1.1 and all four skills, run installed checks without
   bytecode writes, and verify zero unexpected files or `.skillguard`.
7. Create the annotated tag and zero-asset GitHub Release, then rerun the six
   identity faces.

Rollback before publication means restoring the previous skill activation and
leaving the failed v0.1.1 commit untagged. No old runtime reader is introduced.
