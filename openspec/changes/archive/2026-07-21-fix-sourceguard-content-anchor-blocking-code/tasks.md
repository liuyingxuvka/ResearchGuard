## 1. Model the observed miss

- [x] 1.1 Add a SourceGuard-owned FlowGuard child model for native oracle/depth finding alignment, including the observed drifted known-bad implementation.
- [x] 1.2 Run the current FlowGuard formal entry and confirm the aligned design passes while the drifted code variant is rejected.

## 2. Add native regression coverage

- [x] 2.1 Add an end-to-end target-purpose proof test for the content-anchor oracle's good and bad cases.
- [x] 2.2 Update the locator-only semantic-depth regression to require the catalog-declared content-anchor finding and preserve unrelated failures.

## 3. Repair the owning depth path

- [x] 3.1 Replace the drifted content-anchor finding at the native depth owner with `sourceguard_blocked:contentless-anchor`.
- [x] 3.2 Prove the retired finding has no remaining runtime or test residual and no compatibility alias was introduced.

## 4. Validate the frozen repair

- [x] 4.1 Run focused SourceGuard tests, the SourceGuard native model/contract checks, and the affected FlowGuard models.
- [x] 4.2 Run OpenSpec strict validation and one complete ResearchGuard test suite on a stable snapshot.
- [x] 4.3 Update FlowGuard adoption evidence and the patch-release version/changelog without changing unrelated member behavior.

## 5. Close and publish

- [x] 5.1 Verify the implementation against the OpenSpec artifacts, sync the new capability spec, and prepare the completed change for archival.
- [x] 5.2 Freeze the exact owned release contents, `v0.1.3` identity, direct `v0.1.2` replacement boundary, and source-only release notes for the post-archive publication transaction.
