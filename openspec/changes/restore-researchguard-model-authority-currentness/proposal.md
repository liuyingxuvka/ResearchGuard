## Why

ResearchGuard v0.1.4 is the current source, installed package, tag, and release, but the suite FlowGuard model still identifies v0.1.3 and the model/runner/test files are not all freshness inputs. That makes the existing green suite evidence insufficient for a current model-authority claim.

## What Changes

- Align the suite model, JSON projection, runner, and currentness checks to one v0.1.4 authority before feature work.
- Add four-source version parity across package metadata, module version, executable model, and JSON model.
- Make all suite model, runner, and currentness tests explicit SkillGuard freshness inputs.
- Establish and audit one observed FlowGuard model-system snapshot after the currentness checks pass.
- Keep the installed three-member ResearchGuard distribution unchanged during this repair.

## Capabilities

### New Capabilities

- `researchguard-model-authority-currentness`: Defines exact suite-version parity, freshness coverage, and observed model-authority requirements.

### Modified Capabilities

- None.

## Impact

Affected surfaces: `.flowguard/researchguard_suite_model.py`, its JSON projection and runner, currentness scripts/tests, SkillGuard contract sources, and FlowGuard adoption/model-authority records.
