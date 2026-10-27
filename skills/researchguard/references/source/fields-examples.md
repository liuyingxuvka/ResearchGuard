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
