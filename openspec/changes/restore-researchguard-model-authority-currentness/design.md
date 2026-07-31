## Context

The released product is v0.1.4, while the suite model and JSON identity remain v0.1.3. The current FlowGuard project policy also requires an observed model-system authority, and SkillGuard freshness compilation does not yet consume every model-currentness input.

## Goals / Non-Goals

**Goals**

- Make v0.1.4 the sole current suite identity across source and executable projections.
- Fail visibly on any version or model/runner freshness drift.
- Establish one observed snapshot from current passing evidence.

**Non-Goals**

- No new member, route, public command, or product behavior.
- No reuse of old FlowGuard 0.59.0/0.60.0 receipts as current evidence.
- No compatibility acceptance for v0.1.3 model identities.

## Decisions

1. One `RESEARCHGUARD_VERSION` value remains the product source of truth; currentness checks compare it with package metadata, module version, executable model version, and JSON model version.
2. SkillGuard contract compilation maps the model, JSON, runner, checker, and focused tests into exact source components.
3. A passing currentness receipt is fingerprinted and used to bootstrap the first observed model-system snapshot.
4. The observed snapshot records current owners and gaps; it does not claim feature completeness.

## Risks / Trade-offs

- Updating the model identity invalidates prior receipts. This is intentional and requires fresh focused validation.
- Snapshot bootstrap can expose unrelated historical model gaps; those stay visible and cannot be silently scoped away.

## Migration Plan

Directly replace v0.1.3 current identifiers, run focused checks, bootstrap and audit model authority, then freeze the repaired baseline before feature edits.
