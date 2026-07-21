## flowguard-project-adopt - FlowGuard project adopt record update

- Project: ResearchGuard
- Trigger reason: target project requires current semantic adoption and version records
- Status: completed
- Skill decision: used_flowguard
- Started: 2026-07-18T09:34:02+00:00
- Ended: 2026-07-18T09:34:02+00:00
- Duration seconds: 0.000
- Commands OK: True

### Model Files
- none recorded

### Commands
- OK (0.000s): `managed adoption rule-set preflight` - generated block contains every required stable rule
- OK (0.000s): `canonical FlowGuard skill-suite validation` - blocked
- OK (0.000s): `post-write project adoption audit` - semantic and version parity after write

### Findings
- suite_inventory_unresolved: Canonical FlowGuard skill-suite validation is unresolved.
- adoption_record_written: FlowGuard project AGENTS block and manifest were written or refreshed.

### Counterexamples
- none recorded

### Friction Points
- none recorded

### Skipped Steps
- Project adoption does not replace executable model checks, tests, replay, or closure evidence.

### Risk Evidence Summary
- none recorded

### Next Actions
- python -m flowguard project-audit --root . --json
- python scripts/verify_skill_suite_markers.py --root . --json
- Rerun affected FlowGuard model checks and focused tests before broad confidence.


## researchguard-v0.1.1-package-identity - Model-miss repair

- Project: ResearchGuard
- Trigger reason: the v0.1.0 mesh-store fingerprint queried the retired
  `logicguard` distribution and produced `0.18.0` instead of the current
  ResearchGuard `0.1.0` identity.
- Status: completed
- Skill decision: reused the existing ResearchGuard suite model and applied
  the model-miss and development-process routes.
- Model files:
  - `.flowguard/researchguard_suite_model.py`
  - `.flowguard/researchguard_suite_model.json`
  - `.flowguard/run_researchguard_suite_model.py`
- Model-miss class: `code_boundary_mismatch`
- Findings:
  - package identity now comes only from the current in-package
    `researchguard.__version__`;
  - predecessor-present and predecessor-absent scenarios resolve the same
    current identity without a metadata query or alternate-success edge;
  - the zero-residual scanner rejects retired imports, metadata queries, and
    declared dependencies.
- Commands:
  - PASS: focused package-identity, residual, installer, and suite-routing tests
    (`16 passed`)
  - PASS: executable FlowGuard model (`8/8` scenarios)
  - PASS: zero-residual scanner (`0` findings)
- Counterexamples: the frozen v0.1.0 reproduction resolved
  `logicguard==0.18.0` into the mesh-store tool fingerprint.
- Friction points: predictive-KB preflight was fail-closed because the current
  Chaos Brain maintenance standard was not committed; no fallback retrieval
  was attempted.
- Skipped steps: native member tests, installation, and release evidence are
  separate gates and are not claimed by this entry.
- Next actions: run all member-native checks, the full suite, exact installation
  parity, and the v0.1.1 release identity audit.
- Claim boundary: this entry covers the executable model-miss repair and
  focused evidence only; it does not by itself prove full tests, installation,
  or publication.


## flowguard-project-upgrade - FlowGuard project upgrade record update

- Project: ResearchGuard
- Trigger reason: target project requires current semantic adoption and version records
- Status: completed
- Skill decision: used_flowguard
- Started: 2026-07-18T16:00:59+00:00
- Ended: 2026-07-18T16:00:59+00:00
- Duration seconds: 0.000
- Commands OK: True

### Model Files
- none recorded

### Commands
- OK (0.000s): `managed adoption rule-set preflight` - generated block contains every required stable rule
- OK (0.000s): `canonical FlowGuard skill-suite validation` - pass
- OK (0.000s): `post-write project adoption audit` - semantic and version parity after write

### Findings
- adoption_record_written: FlowGuard project AGENTS block and manifest were written or refreshed.

### Counterexamples
- none recorded

### Friction Points
- none recorded

### Skipped Steps
- Project adoption does not replace executable model checks, tests, replay, or closure evidence.

### Risk Evidence Summary
- none recorded

### Next Actions
- python -m flowguard project-audit --root . --json
- python scripts/verify_skill_suite_markers.py --root . --json
- Rerun affected FlowGuard model checks and focused tests before broad confidence.


## flowguard-project-upgrade - FlowGuard project upgrade record update

- Project: ResearchGuard
- Trigger reason: target project requires current semantic adoption and version records
- Status: completed
- Skill decision: used_flowguard
- Started: 2026-07-19T16:26:39+00:00
- Ended: 2026-07-19T16:26:39+00:00
- Duration seconds: 0.000
- Commands OK: True

### Model Files
- none recorded

### Commands
- OK (0.000s): `managed adoption rule-set preflight` - generated block contains every required stable rule
- OK (0.000s): `package-authority/global-consumer validation` - pass
- OK (0.000s): `post-write project adoption audit` - semantic and version parity after write

### Findings
- adoption_record_written: FlowGuard project AGENTS block and manifest were written or refreshed.

### Counterexamples
- none recorded

### Friction Points
- none recorded

### Skipped Steps
- Project adoption does not replace executable model checks, tests, replay, or closure evidence.

### Risk Evidence Summary
- none recorded

### Next Actions
- python -m flowguard project-audit --root . --json
- Rerun affected FlowGuard model checks and focused tests before broad confidence.


## flowguard-project-upgrade - FlowGuard project upgrade record update

- Project: ResearchGuard
- Trigger reason: target project requires current semantic adoption and version records
- Status: completed
- Skill decision: used_flowguard
- Started: 2026-07-21T22:20:27+00:00
- Ended: 2026-07-21T22:20:27+00:00
- Duration seconds: 0.000
- Commands OK: True

### Model Files
- none recorded

### Commands
- OK (0.000s): `managed adoption rule-set preflight` - generated block contains every required stable rule
- OK (0.000s): `package-authority/global-consumer validation` - pass
- OK (0.000s): `post-write project adoption audit` - semantic and version parity after write

### Findings
- adoption_record_written: FlowGuard project AGENTS block and manifest were written or refreshed.

### Counterexamples
- none recorded

### Friction Points
- none recorded

### Skipped Steps
- Project adoption does not replace executable model checks, tests, replay, or closure evidence.

### Risk Evidence Summary
- none recorded

### Next Actions
- python -m flowguard project-audit --root . --json
- Rerun affected FlowGuard model checks and focused tests before broad confidence.


## sourceguard-content-anchor-oracle-code-alignment - Repair the SourceGuard content-anchor native blocking-code drift

- Project: ResearchGuard
- Trigger reason: the catalog required `sourceguard_blocked:contentless-anchor`, but the native depth owner emitted `no_content_qualified_anchor` for the same bad case.
- Status: completed
- Skill decision: existing-model preflight + model-miss review + development-process flow
- Started: 2026-07-21T22:20:27Z
- Ended: 2026-07-21T22:49:46Z

### Model Files

- `.flowguard/sourceguard_content_anchor_oracle_model.py`
- `.flowguard/researchguard_suite_model.py`
- `.flowguard/run_researchguard_suite_model.py`

### Commands

- PASS: pre-fix target-purpose reproduction observed the exact code mismatch.
- PASS: SourceGuard native suite, 84 tests.
- PASS: content-anchor FlowGuard child model; the retired code produced the expected invariant violation.
- PASS: ResearchGuard suite FlowGuard model, 8 of 8 scenarios.
- PASS: complete repository suite, 540 tests.
- PASS: all four SkillGuard member closures are enforced and current.

### Findings

- The fingerprint-bound SourceGuard oracle catalog remains the single contract authority.
- The native depth owner was the minimal drifted boundary and now emits the declared code directly.
- Runtime and test residuals of the retired code are zero; no alias, dual emission, or fallback was added.

### Counterexamples

- The v0.1.2 bad case blocked depth but failed exact target-purpose proof closure because the emitted finding identity differed from the catalog declaration.

### Friction Points

- FlowGuard project adoption was upgraded from 0.58.4 to 0.58.5 before modeling.
- One outer SkillGuard wait window expired while the owned SourceGuard execution continued. The exact process tree reached zero and the same terminal result was inspected; no retry was started.

### Skipped Steps

- Progress, contract, conformance, and counterexample-minimization checks are outside the child model's finite finding-identity claim and remain explicitly not run.
- Installation and GitHub publication remain separate release gates.

### Next Actions

- Verify, sync, and archive the OpenSpec change.
- Install the exact v0.1.3 consumer projection.
- Publish and audit the v0.1.3 GitHub identity.

### Claim Boundary

This entry proves the modeled finding-identity repair, affected checks, full suite, and frozen author-side member closures. It does not by itself prove installation, publication, source truth, or future AI behavior.
