## Why

ResearchGuard already has deep native modeling loops, but its umbrella still trusts caller-authored applicability labels and its larger member skills eagerly place route-specific and deep-work instructions in the first read. This makes the entrance both easier to misroute and more expensive than necessary even when only one narrow owner action is required.

## What Changes

- **BREAKING** Replace the umbrella's caller-authored admission-v1 packet with a task-facts packet whose facts carry source spans; each member's current contract derives applicability, required-input status, forbidden-condition disposition, first action, and selected reference from those facts.
- Generate and verify one compact ResearchGuard member-admission index. Direct member requests continue to skip the umbrella; ambiguous requests read only the index, then choose the minimum sufficient member set. One independently sufficient member stays a single route; genuinely irreducible multi-member work requires an explicit declarative composition.
- Reduce the ResearchGuard, LogicGuard, SourceGuard, and TraceGuard entry files to route/claim shells and move existing deep contracts, commands, safety language, and template-pack guidance into conditionally loaded references. Keep ExperimentGuard independent and compact.
- Make all five default prompts route first and enter task-local deepening only for a declared deepening trigger, without weakening any member's existing native closure gate.
- Add target-owned prompt-bundle/load-graph checks and known-bad admission cases, then synchronize FlowGuard suite models, SkillGuard author contracts, version identity, and changelog for patch release `0.4.1`.

## Capabilities

### New Capabilities

- `researchguard-narrow-entry-loading`: Defines source-bound task-fact admission, minimum-sufficient member selection, declarative composition, direct-entry bypass, conditional reference loading, and preservation of native deep closure.

### Modified Capabilities

- None.

## Impact

- Root routing and CLI: `src/researchguard/routing.py`, the four member admission modules, and `src/researchguard/cli.py`.
- Consumer skills: the five `skills/*/SKILL.md` files, their `agents/openai.yaml` defaults, and new member-owned references.
- Governance and evidence: ResearchGuard FlowGuard suite/skill-contract models, prompt-bundle checks, native suite checks, SkillGuard contract builder and generated author contracts.
- Identity: Python/package/model version fields and `CHANGELOG.md` advance from `0.4.0` to `0.4.1`; installation, Git publication, tag, and release remain outside this change's implementation task.
