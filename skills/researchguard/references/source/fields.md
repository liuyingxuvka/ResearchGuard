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

## Observations

An independent observation file is a mapping with these same fields as each row
in the model's `observations`. It is YAML, without an extra schema envelope.

| Field | Required / optional, default |
|---|---|
| `observation_id` | Required nonempty string. |
| `action_id` | Optional string, `""`; in a frozen search iteration it must equal that prediction's action ID. |
| `observed_sources` | Optional list of source objects, `[]`. |
| `observed_anchors` | Optional list of anchor objects, `[]`. |
| `new_entities` | Optional string list, `[]`. |
| `new_leads` | Optional list of lead objects, `[]`. |
| `new_gaps` | Optional list of gap objects, `[]`; the same lifecycle/default rules apply. |
| `contradictions` | Optional list of strings, `[]`. |
| `notes` | Optional string, `""`. |
| `observation_fingerprint` | Optional string, `""`; when supplied, use a `sha256:` digest. |
| `unconsumed_output_disposition` | Optional string, `""`. |

A supplied search-iteration observation requires provider status
`OBSERVATION_SUPPLIED`; no-observation work remains `NOT_RUN` or
`PROVIDER_UNAVAILABLE`. Prediction fields such as `baseline_identity` and
`expected_cost` belong to the frozen prediction, not this observation mapping.

## Depth policy

| Fields | Optional defaults and constraints |
|---|---|
| `requested_claim_scope` | `bounded`; only `bounded` or `broad`. |
| `important_threshold` | `0.6`; bounded to `[0, 1]`, then capped at `0.6`. |
| `required_portfolio_classes` | `[]`; each member is a `SOURCE_PORTFOLIO_CLASSES` value. |
| `required_source_roles` | `[]`; each member is a `SOURCE_ROLES` value. |
| `minimum_independent_lineages` | `2`; input must parse as an integer at least 1, and the effective minimum is 2. |
| `target_unit_inventory_ids`, `required_target_unit_ids`, `excluded_target_unit_ids` | String lists, `[]`. |
| `target_unit_exclusion_reasons` | String-keyed reason mapping, `{}`; give a nonempty reason for exclusions. |
| `require_explicit_lineage`, `require_anchor_content`, `per_gap_portfolio_required` | Booleans, each `true`. |
| `required_gap_ids`, `required_lineage_slot_ids`, `required_anchor_requirement_ids`, `required_handoff_ids` | String lists, `[]`. |
| `known_good_case_ids`, `known_bad_case_ids` | String lists, `[]`. |
| `coverage_floors` | Numeric mapping, `{}`; values are bounded to `[0, 1]`, with `1.0` as the fallback for an empty/invalid value. |
| `policy_origin` | Native value `sourceguard-native-depth-v2`; a supplied replacement does not change the native origin. |

## Complete enum values

The following lists are exhaustive. An ID, locator, note, `source_policy`, or
qualification decision is a string rather than an additional enum.

- **SOURCE_TYPES**: `audio`, `book`, `database_record`, `dataset`, `government_record`, `image`, `internal_document`, `interview`, `local_file`, `map`, `paper`, `patent`, `pdf_report`, `procurement_record`, `report`, `social_post`, `unknown`, `video`, `web_page`.
- **SOURCE_STATUSES**: `candidate`, `duplicate`, `inaccessible`, `permission_gated`, `promoted_logicguard`, `promoted_traceguard`, `rejected`, `saved`, `unknown`.
- **SOURCE_ROLES**: `audio_evidence`, `bridge_evidence`, `context_only`, `counter_evidence`, `expert_analysis`, `historical_background`, `hypothesis_source`, `independent_report`, `limiting_evidence`, `method_source`, `official_claim`, `primary_source`, `unknown`, `validation_evidence`, `visual_evidence`.
- **ACCESS_STATUSES**: `internal`, `local`, `permission_gated`, `public`, `unavailable`, `unknown`.
- **ANCHOR_TYPES**: `audio_segment`, `citation`, `dataset_row`, `figure`, `footnote`, `image`, `image_region`, `index_entry`, `map_location`, `metadata`, `page`, `paragraph`, `section`, `table`, `transcript_segment`, `unknown`, `video_segment`.
- **MODALITIES**: `audio`, `book_page`, `chart`, `image`, `map`, `mixed`, `pdf_page`, `table`, `text`, `unknown`, `video`.
- **LEAD_STATUSES**: `access_gap`, `candidate`, `closed`, `contradicted`, `downgraded`, `open`, `supported_incomplete`, `unknown`.
- **GAP_TYPES**: `contradiction`, `duplicate_source_cluster`, `missing_audio_anchor`, `missing_baseline`, `missing_book_page`, `missing_bridge_evidence`, `missing_conclusion_recovery_source`, `missing_counterevidence`, `missing_date`, `missing_execution_evidence`, `missing_independent_source`, `missing_location`, `missing_numeric_provenance`, `missing_pdf_page`, `missing_primary_source`, `missing_structural_source_support`, `missing_visual_anchor`, `one_sided_support`, `permission_gap`, `stale_source`, `unclear_entity`, `unclear_scope`, `unknown`, `weak_signal_only`.
- **SEMANTIC_GAP_STATES**: `blocked`, `claim_usable`, `closed`, `contradicted`, `discovered`, `observed`, `qualified`.
- **ACTION_TYPES**: `audio_transcript_search`, `book_index_search`, `citation_backward`, `citation_forward`, `counterevidence_search`, `entity_expand`, `exact_phrase_search`, `followup_from_anchor`, `image_search`, `internal_source_search`, `local_file_search`, `map_location_search`, `pdf_page_search`, `primary_source_search`, `report_page_search`, `reverse_image_search`, `source_domain_search`, `text_search`, `unknown`, `video_search`.
- **ACTION_STATUSES**: `blocked`, `completed`, `executed`, `proposed`, `rejected`, `selected`, `unknown`.
- **SOURCE_DEPTH_CLAIM_SCOPES**: `bounded`, `broad`.
- **SOURCE_PORTFOLIO_CLASSES**: `counter_or_limiting`, `direct_or_primary`, `independent`.

The declared `BLUEPRINT_OUTPUT_DISPOSITIONS` vocabulary is `excluded`,
`terminal`, `unsupported`. The optional `unconsumed_output_disposition` string
otherwise defaults to `""`; listing it does not make it a required field.

## Optional typed graph edges

Each `graph_edges` row requires nonempty `edge_id`, `source_id`, `source_type`,
`target_id`, `target_type`, and `relation_type`; optional `notes` defaults to `""`.
Unknown graph-edge fields, repeated edge IDs, missing endpoints, and endpoint
types that disagree with actual objects are rejected.

`GRAPH_OBJECT_TYPES`: `anchor`, `claim_use`, `gap`, `handoff`, `lead`, `observation`, `search_action`, `source`, `source_role`, `target_unit`.
Allowed relations and endpoint pairs are:

| relation_type | source_type → target_type |
|---|---|
| `addresses` | search_action → gap; source_role → search_action |
| `after` | anchor → anchor; source → source |
| `before` | anchor → anchor; source → source |
| `candidate_for` | source → gap; source → lead |
| `cited_by` | source → source |
| `cites` | anchor → source; source → source |
| `closes_gap` | anchor → gap |
| `consumed_by` | anchor → claim_use; anchor → handoff |
| `contains_anchor` | source → anchor |
| `generated_action` | gap → search_action; lead → search_action |
| `limits` | anchor → claim_use; anchor → gap |
| `mentions` | anchor → claim_use; source → anchor |
| `observation_from` | observation → anchor; observation → source; search_action → observation |
| `opens_gap` | lead → gap; target_unit → gap |
| `promoted_to_logicguard` | anchor → handoff; source → handoff |
| `promoted_to_traceguard` | anchor → handoff; source → handoff |
| `qualifies` | anchor → gap |
| `rebuts` | anchor → claim_use |
| `requires_role` | gap → source_role |
| `returns_source` | search_action → source |
| `same_entity_as` | lead → lead; source → source |
| `same_location_as` | anchor → anchor; source → source |
| `supports` | anchor → claim_use; anchor → gap |

## Minimal complete model example

`researchguard source create --output starter.yaml` writes this teaching model
with the installed version added to metadata. Replace all `example-` rows with
retrieved material. `source validate` warns while starter example IDs remain;
that warning is not an evidence-qualification failure or permission to use the
sample as a real source.

```yaml
metadata:
  purpose: Illustrate source discovery for a bounded recovery claim; the sample is synthetic.
  repository: https://github.com/liuyingxuvka/ResearchGuard
  skill: SourceGuard
  math_boundary: Expected utility ranks discovery value, not factual truth or calibrated probability.
  cli: researchguard source validate starter.yaml
  boundary: Replace the teaching rows with retrieved material; sample anchors do not license real claims.
  source_policy: public_only
  domain_hints:
  - harbor departures
  - reopening
  qualification_thresholds:
    source_reliability: 0.5
    extraction_confidence: 0.5
    specificity: 0.5
leads:
- lead_id: example-recovery
  question: Did daily harbor departures recover after reopening?
  hypothesis: Daily departures recovered within the reported observation period.
  importance: 0.7
  status: open
  related_sources:
  - example-departure-log
  related_anchors:
  - example-log-row
  gaps:
  - example-independent-report
  - example-later-period
sources:
- source_id: example-departure-log
  title: Synthetic daily departure log
  source_type: local_file
  source_status: saved
  source_role: primary_source
  lineage_id: example-log-lineage
  access_status: local
  notes: Teaching data only; no real-world source was retrieved.
anchors:
- anchor_id: example-log-row
  source_id: example-departure-log
  anchor_type: dataset_row
  locator: row 1
  text: 'Synthetic example: daily departures increased during the stated period.'
  modality: text
  supports:
  - example-recovery
  limits:
  - Synthetic teaching data; not evidence for an actual harbor.
  usable_for_trace: false
  usable_for_claim: false
gaps:
- gap_id: example-independent-report
  lead_id: example-recovery
  gap_type: missing_independent_source
  description: Retrieve an independent report before licensing the recovery claim.
  importance: 0.8
  blocking: true
  suggested_source_roles:
  - independent_report
  suggested_modalities:
  - text
- gap_id: example-later-period
  lead_id: example-recovery
  gap_type: unclear_scope
  description: A later observation period would bound persistence of any recovery.
  importance: 0.3
  blocking: false
  suggested_source_roles:
  - limiting_evidence
  suggested_modalities:
  - text
actions:
- action_id: example-search-independent
  action_type: text_search
  query: harbor departures reopening independent report
  target_lead_id: example-recovery
  target_gap_id: example-independent-report
  expected_source_role: independent_report
  expected_modality: text
  source_policy: public_only
  cost: 0.3
  permission_risk: 0.0
  status: proposed
observations: []
graph_edges: []
weights: {}
depth_policy:
  requested_claim_scope: bounded
```

## Observation file example

This illustrates a follow-up to the declared example action. It is still
synthetic teaching data, not a record of retrieval. Save an actual observation
using these fields and the material that was really obtained.

```yaml
observation_id: example-followup-observation
action_id: example-search-independent
observed_sources:
  - source_id: example-independent-record
    title: Synthetic independent departure report
    source_type: local_file
    source_role: independent_report
    access_status: local
    notes: Teaching data only; replace with retrieved material.
observed_anchors:
  - anchor_id: example-independent-row
    source_id: example-independent-record
    anchor_type: paragraph
    locator: Paragraph 2
    text: "Synthetic report: departures increased during the reported period."
    modality: text
    supports: [example-independent-report]
    usable_for_claim: false
new_entities: []
new_leads: []
new_gaps: []
contradictions: []
notes: Synthetic observation shape; it does not close a real evidence gap.
```
