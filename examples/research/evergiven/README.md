# Ever Given research tree

Question: did the March 2021 Suez blockage cause the Asia–Europe freight rate rise?
`research.yaml` shares hypothesis ids across native route models.
`source.yaml` holds source identities, lineage, anchors and recorded observations.
`trace.yaml` compares Suez and demand explanations with signed evidence links.
`logic.yaml` retains the bounded argument and its counterevidence.
`experiment.json` and `exp-obs1.json` declare finite predictions and observations.
Run `researchguard status examples/research/evergiven` (`--json` for data).
`h_yantian` appears only in experiment; its missing-logic warning is expected.
`src-wci-transpacific` is cited by title only: neither `source.yaml` nor `trace.yaml` gives it a link, DOI, ISBN or arXiv id (`trace.yaml` has `url: null`).
Status warns `unverifiable_source` for every source, old or new, that a reader outside the folder cannot look up, so this warning is expected.
No link is made up to silence it: it stays until a locator for that lane is recorded.
Numbers are approximate public-data transcriptions, not established conclusions.
`experiment observe` returns 2 (`continue_iteration`): demand and Yantian both survive; the next check is `e_yantian_timing`.

## Discussing the verdict

The owner asks: *"The blockage was huge news. Why may the answer not say it caused the rise?"*
The reply shows what the claim rests on, drawn by `researchguard status examples/research/evergiven --picture`
from this folder's models rather than from the AI's memory of the argument:

<!-- BEGIN COMPUTED PICTURE: researchguard status examples/research/evergiven --picture -->
**What h_suez rests on**

- h_suez: UNDECIDED 0.16 · licence withhold
- blocked by: R_h_suez_anc-transpacific, R_h_suez_anc-unctad-surge, R_pretrend, h_demand

```mermaid
flowchart BT
  n0["h_suez<br/>The Ever Given grounding (23-29 Mar 2021) caused the 2021...<br/>UNDECIDED 0.16 · licence withhold"]
  n1["R_h_suez_anc-transpacific (Rebuttal)<br/>Opposing evidence for h_suez: Approx. USD/FEU...<br/>IN 0.70"]
  n2["R_h_suez_anc-unctad-surge (Rebuttal)<br/>Opposing evidence for h_suez: Container spot...<br/>IN 0.80"]
  n3["R_pretrend (Rebuttal)<br/>Rates had already quadrupled before the block...<br/>IN 0.74"]
  n4["h_demand<br/>Pandemic demand and container shortage caused...<br/>IN 0.74"]
  n5["A_timing (Assumption)<br/>The Q2-Q3 rise is attributable to the March b...<br/>IN 0.40"]
  n6["E_dates<br/>Grounding 23 Mar 2021, refloated 29 Mar 2021...<br/>anc-sca-dates · Suez Canal Authority statements on th...<br/>IN 0.90"]
  n7["E_series<br/>WCI Shanghai-Rotterdam: ~2,000 (Oct 2020), ~8...<br/>anc-wci-series · Drewry World Container Index, Shangha...<br/>IN 0.70"]
  n8["W_capacity (Warrant)<br/>Removing transit capacity for ~1-2 weeks rais...<br/>IN 0.60"]
  n9["E_transpacific<br/>WCI Shanghai-Los Angeles (no Suez exposure):...<br/>anc-transpacific · Drewry WCI Shanghai-Los Angeles lane... · unverifiable source<br/>IN 0.70"]
  n10["E_pretrend<br/>UNCTAD RMT 2021: rates surged from H2 2020 on...<br/>anc-unctad-surge · UNCTAD Review of Maritime Transport 2...<br/>IN 0.80"]
  n9 -->|"supports"| n1
  n10 -->|"supports"| n2
  n10 -->|"supports"| n3
  n7 -->|"supports"| n3
  n9 -->|"supports"| n3
  n10 -->|"supports"| n4
  n7 -->|"supports"| n4
  n9 -->|"supports"| n4
  n6 -->|"supports · trace agrees"| n0
  n7 -->|"supports · trace agrees"| n0
  n8 -->|"supports"| n0
  n5 -->|"depends_on"| n0
  n3 ==>|"attacks · blocks"| n0
  n4 ==>|"contradicts · blocks"| n0
  n1 ==>|"attacks · blocks"| n0
  n2 ==>|"attacks · blocks"| n0
  n9 -.->|"trace: oppose"| n0
  n10 -.->|"trace: oppose"| n0
  classDef claim stroke-width:3px
  class n0 claim
  classDef blocker stroke:#b03030,stroke-width:2px
  class n1,n2,n3,n4 blocker
  classDef problem stroke:#b03030,stroke-dasharray:4 3
  class n9 problem
```

Drawn: 11 boxes and 18 arrows, computed from the logic model, its evaluation, the source model and the trace route's evidence directions (readable size 12 boxes, 20 arrows).

**Not drawn**

- route states shown as text, not boxes: trace not live; experiment eliminated
- the timeline order of the trace route and the search plan are not drawn

**Problems in what is drawn**

- warning unverifiable_source:src-wci-transpacific (no link, DOI, ISBN or arXiv id; nothing outside this folder to check it against)
<!-- END COMPUTED PICTURE -->

Reply: *Two anchored pieces of evidence support the claim directly (the grounding dates and the Shanghai-Rotterdam
series), with a warrant and a timing assumption; the timeline agrees on both pieces. Four nodes block it: the
pre-trend rebuttal, the demand explanation, and two rebuttals built from the UNCTAD surge and the transpacific lane,
which had no Suez exposure but rose too. The timeline counts those two anchors against the claim as well. So the
folder licenses only "withhold": these records do not support saying the blockage caused the rise. The transpacific
lane is drawn dashed because its source is cited by title only: nobody can look it up yet, so it needs a link before
the answer leans on it. The picture leaves out the experiment route, which has eliminated the claim, and the timeline
order.*
