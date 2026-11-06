# Maintained decision contracts

The viewer counts and marks an element important when its declared/inferred importance is at least 0.75. The card count and node/edge markers share that boundary. The viewer count and both graph markers call the same importance decision owner.

These are distinct decisions, not one global definition of importance:

| Owner | Boundary and meaning |
|---|---|
| logic/library_viewer IMPORTANT_THRESHOLD | 0.75: viewer count and visible markers |
| logic/execution_depth CRITICAL_IMPORTANCE_THRESHOLD | 0.85 plus explicit high/critical impact or flag: required critical depth |
| logic/execution_depth NATIVE_BROAD_THRESHOLD | 0.6: native enforcement profile, not the viewer classification |
| logic/gap_ledger | 0.75: whether a confidence gap deserves follow-up, with evaluation state/confidence |
| logic/citation_matrix | 0.7: a source-backed claim must name a source |
| logic/importance | 0.82 core, 0.55 risk, 0.35 background: inferred salience with node type/root/role |
| logic/structure_audit | 0.65 late limitation/undated current claim, 0.75 overloaded claims, 0.45 orphan blocks, 0.6 date-vs-coverage: different structural findings |
| logic/synthesis | 0.8 branch salience; 0.35/0.5/0.85/0.7/0.65/0.6 prose treatment and appendix decisions with type/salience |
| trace/storyline_depth | 0.6 critical object and 2.0 perturbation priority: TraceGuard coverage; 0.5 is a secondary hypothesis criterion |

Keep these differences explicit rather than sharing a constant merely because the numbers coincide. The executable viewer rule binds the single decision owner; a generated Map call check keeps its three callers attached. Nine ordinary guarded checks retain the real count/node/edge outputs on both sides and at the boundary. Other current policies retain their ordinary production tests; this table does not invent a universal rule or claim that their full meanings are interchangeable.

Frozen prediction identity is checked by the real shared iteration owner. A matching baseline accepts; an edited baseline is refused; resetting the stimulus permits the original baseline again. This finite identity requirement does not model every research workflow.
