## Evidence-batch observation v2

This separate observation JSON records a real batch for task-local prediction comparison. It neither retrieves evidence nor licenses factual future prediction. All fifteen serialized fields are shown below; the four new-record lists are optional and omission preserves ID-only observations.

| Field | Required / omission default |
| --- | --- |
| `schema_version` | required: `researchguard.trace.evidence_batch_observation.v2` |
| `observation_id` | required, nonempty |
| `observed_at` | required ISO-8601 timestamp with timezone |
| `quality_status` | required: `valid`, `invalid`, `access_gap` |
| `evidence_ids` | `[]` |
| `event_ids` | `[]` |
| `event_order` | `[]`; only IDs in `event_ids` or `new_events` |
| `contradiction_ids` | `[]` |
| `source_refs` | `[]` |
| `future_holdout_status` | `"not_run"`; descriptive string, not a factual future-prediction license |
| `external_input_ids` | `[]` |
| `new_sources` | `[]`; native `SourceRecord` rows, as in model `sources` |
| `new_evidence` | `[]`; native `EvidenceItem` rows, as in model `evidence` |
| `new_events` | `[]`; native `EventCandidate` rows, as in model `events` |
| `new_links` | `[]`; native `HypothesisEvidenceLink` rows, as in model `hypothesis_evidence_links` |

Each new list contains mappings using the corresponding model-row fields above. Comparison appends them to the baseline in memory and applies native schema and cross-reference validation. Each typed collection rejects an ID already in that baseline collection or repeated among its new rows, even with identical contents. Refer to an existing record by ID instead of submitting it as new. Evidence, event and source IDs must resolve in the combined model; a candidate must also retain the construction observation's four new-record lists unchanged. Older baseline records may be revised and additional links added, subject to native checks.

`event_order` is ordered; other ID collections are deduplicated in input order. Expected evidence/event IDs frozen before observation may be absent from the baseline and supplied later by listed IDs or new rows. The predicted hypothesis or trace and coverage IDs must already exist at freeze time. The optional freeze argument `--expected-direction` accepts `weaken`, `strengthen`, or `unchanged`; omission imposes no direction check. `--weakens-when` is an optional remark. Comparison derives direction from canonical support of the checked hypothesis: below −0.01 is weakening, above +0.01 strengthening, otherwise unchanged. Native `open_depth_gap_ids` are separate from prediction mismatches; an accepted candidate with gaps normally continues iteration and does not claim task closure. See [task-iteration.md](task-iteration.md) for holdout, mismatch, rollback and bounded-stop rules.

A valid quality declaration is not external verification of the contents. This synthetic ID-only example references the worked model below; replace it with actual batch observations.

```json
{
  "schema_version": "researchguard.trace.evidence_batch_observation.v2",
  "observation_id": "example-observation",
  "observed_at": "2024-01-03T12:00:00Z",
  "quality_status": "valid",
  "evidence_ids": ["example-change-note", "example-recovery-note"],
  "event_ids": ["example-filter-change", "example-output-recovery"],
  "event_order": ["example-filter-change", "example-output-recovery"],
  "contradiction_ids": [],
  "source_refs": ["example-source"],
  "future_holdout_status": "not_run",
  "external_input_ids": [],
  "new_sources": [],
  "new_evidence": [],
  "new_events": [],
  "new_links": []
}
```

