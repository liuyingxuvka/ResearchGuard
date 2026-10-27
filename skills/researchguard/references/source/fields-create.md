# Source model and observation fields

Write the the conclusion to check in `leads[].question`. Set the requested strength in
`depth_policy.requested_claim_scope`: `bounded` or `broad`. Search utility ranks
discovery value; it does not establish truth or license a final claim. Keep real
retrieval material separate from the synthetic teaching rows below.

## Root and metadata

The root is a mapping. `leads`, `gaps`, `actions`, `sources`, `anchors`,
`observations`, and `graph_edges` are optional lists, default `[]`. `metadata` and
`weights` default to `{}`. `weights` maps names to numeric values. `depth_policy`
uses the defaults below when omitted. `generated_at` defaults to the current UTC
ISO timestamp.

`metadata` has no required child fields. Common optional fields are:

| Fields | Shape and default |
|---|---|
| `purpose`, `repository`, `skill`, `math_boundary`, `cli`, `boundary`, `version` | Descriptive strings; omitted keys remain absent. |
| `source_policy` | String; planning uses `public_only` when absent. |
| `domain_hints` | List of actual search-domain hints; omitted means no hints. |
| `qualification_thresholds` | Mapping with optional `source_reliability`, `extraction_confidence`, `specificity`; each defaults to `0.5` and is clamped to `[0, 1]`. |
| `warnings`, `handoff_ids` | Optional lists of strings used by the corresponding workflow. |

Use YAML booleans (`true`, `false`), numeric values, and lists of strings. Unless a
row says otherwise, optional string fields default to `""`, list fields to `[]`,
and mappings to `{}`. Scores below are bounded to `[0, 1]` using their stated
default; they are declared heuristics, not calibrated probabilities.

## Leads

| Fields | Required / optional, defaults |
|---|---|
| `lead_id` | Required nonempty string. |
| `question`, `hypothesis`, `notes` | Optional strings, `""`. `question` carries the the conclusion to check to investigate. |
| `importance` | Optional score, `0.5`. |
| `status` | Optional `LEAD_STATUSES`, `open`. |
| `related_entities`, `related_sources`, `related_anchors`, `gaps` | Optional string lists, `[]`. Reference the relevant current row IDs. |

## Gaps

| Fields | Required / optional, defaults |
|---|---|
| `gap_id` | Required nonempty string. |
| `lead_id`, `description`, `notes` | Optional strings, `""`. |
| `gap_type` | Optional `GAP_TYPES`, `unknown`. |
| `semantic_state` | Optional only when omitted, default `discovered`. Explicit `null`, empty string, or non-string values are invalid. |
| `importance` | Optional score, `0.5`. |
| `blocking`, `review_required` | Optional booleans, `false`. |
| `requires_claim_usability` | Optional boolean, `true`. |
| `hypothesis_ids` | Optional list of hypothesis ids from `research.yaml`, `[]`. SourceGuard only stores it; `researchguard status` checks the ids and groups gaps and next searches by them. |
| `suggested_source_roles` | Optional list drawn from `SOURCE_ROLES`, `[]`. |
| `suggested_modalities` | Optional list drawn from `MODALITIES`, `[]`. |
| `structure_unit_id`, `parent_goal`, `unit_job`, `contribution_type`, `downstream_consumer`, `structural_role_needed` | Optional structural-context strings, `""`. |
| `can_support_structural_use`, `cannot_support_structural_use`, `allowed_wording`, `unsafe_wording` | Optional claim-boundary strings, `""`. |
| `qualification`, `closure_basis` | Optional nested mappings with the defaults below. A `closed` gap requires a complete `closure_basis`. |

`gap.status` is retired and is rejected whenever present. Use the single
`semantic_state`; omitting it starts a discovery, not a closed or qualified gap.

### qualification

All fields are optional. `anchor_id`, `source_id`, `observation_id` default to
`""`. `locator_present`, `source_accessible`, `supports_gap`, `role_match`,
`modality_match`, `target_match`, and `usable_for_claim` default to `false`.
`source_reliability`, `extraction_confidence`, and `specificity` default to `0.0`.
`decision` is a descriptive string, default `not_evaluated`; `reasons` defaults to
`[]`. These fields record the qualification result; merely filling them in is
not independent evidence.

### closure_basis

`anchor_ids`, `source_ids`, `observation_ids` default to `[]`; `thresholds` defaults
to `{}`; `target_match` and `claim_use_decision` are strings, default `""`;
`qualified` defaults to `false`. Unlike qualification's boolean `target_match`,
the closure-basis `target_match` describes the actual claim fit.

A `closed` gap requires **all** of: `qualified: true`; nonempty `anchor_ids`,
`source_ids`, and `observation_ids`; `thresholds` containing `source_reliability`,
`extraction_confidence`, and `specificity`; and nonempty `target_match` and
`claim_use_decision`. Threshold values are scores bounded to `[0, 1]`. Actual
closure still depends on accessible sources, the qualification thresholds,
content, role/modality/claim fit, and claim usability where required. A locator
or newly observed anchor alone does not close a gap.

## Actions

| Fields | Required / optional, defaults |
|---|---|
| `action_id` | Required nonempty string. |
| `action_type` | Optional `ACTION_TYPES`, `unknown`. |
| `query`, `target_lead_id`, `target_gap_id`, `notes`, `unconsumed_output_disposition` | Optional strings, `""`. |
| `expected_source_role` | Optional `SOURCE_ROLES`, `unknown`. |
| `expected_modality` | Optional `MODALITIES`, `unknown`. |
| `source_policy` | Optional string, `public_only`. |
| `cost` | Optional score, `0.3`. |
| `permission_risk` | Optional score, `0.0`. |
| `status` | Optional `ACTION_STATUSES`, `proposed`. |
| `parameters` | Optional mapping, `{}`. |

## Sources

| Fields | Required / optional, defaults |
|---|---|
| `source_id` | Required nonempty string. |
| `source_type` | Optional `SOURCE_TYPES`, `unknown`. |
| `source_status` | Optional `SOURCE_STATUSES`, `candidate`. |
| `source_role` | Optional `SOURCE_ROLES`, `unknown`. `official_claim` is a role; `government_record` is a type. |
| `access_status` | Optional `ACCESS_STATUSES`, `unknown`. |
| `source_reliability` | Optional score, `0.0`. |
| `title`, `url`, `lineage_id`, `source_date`, `coverage_period`, `language`, `country`, `can_support_structural_use`, `cannot_support_structural_use`, `notes` | Optional strings, `""`. |
| `content_fingerprint`, `retrieval_request_fingerprint` | Optional strings, `""`; when supplied, use `sha256:` followed by the 64-character digest. |
| `provider_id`, `provider_revision`, `retrieved_at`, `unconsumed_output_disposition` | Optional strings, `""`. |

## Anchors

| Fields | Required / optional, defaults |
|---|---|
| `anchor_id`, `source_id` | Required nonempty strings. `source_id` identifies the source containing this anchor. |
| `anchor_type` | Optional `ANCHOR_TYPES`, `unknown`. |
| `modality` | Optional `MODALITIES`, `unknown`. |
| `locator`, `text`, `normalized_summary`, `observed_at`, `notes` | Optional strings, `""`. Put extracted source wording in `text`. |
| `extraction_confidence`, `specificity` | Optional scores, `0.0`. |
| `supports`, `limits`, `claim_use_ids`, `handoff_ids`, `warnings` | Optional string lists, `[]`. |
| `usable_for_trace`, `usable_for_claim` | Optional booleans, `false`. A declared flag does not replace downstream review. |
| `anchor_content_fingerprint`, `source_content_fingerprint`, `observation_fingerprint` | Optional strings, `""`; when supplied, use a `sha256:` digest. |
| `extractor_id`, `extractor_revision`, `unconsumed_output_disposition` | Optional strings, `""`. |

