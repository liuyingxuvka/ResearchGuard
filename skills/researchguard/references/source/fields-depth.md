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

