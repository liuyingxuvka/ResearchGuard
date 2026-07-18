# TraceGuard Unified Inference Protocol

Version: `researchguard.trace.unified-inference.v2`

This is the sole detailed mathematical and prompt protocol for TraceGuard
inference. Other TraceGuard documentation may explain a domain view, but it
must link here instead of defining a second scoring language.

## 1. One mathematical language

TraceGuard schema v2 is compiled into one constrained hybrid
logical/continuous model:

- \(x \in [0,1]^m\): observed atoms derived from typed source, evidence,
  entity, time, stage, hypothesis-link, and causal-boundary declarations;
- \(y \in [0,1]^n\): latent atoms such as trace support, entity identity,
  hypothesis support, and bounded qualitative causal support;
- \(\ell_j(x,y)=a_j^\top[x;y]+b_j\): a declared linear expression;
- \(\phi_j(x,y)=w_j\max(0,\ell_j(x,y))^{p_j}\), where \(p_j\in\{1,2\}\):
  a weighted hinge factor;
- \(A[x;y]\le b\), \(C[x;y]=d\): hard constraints that soft evidence cannot
  compensate for.

The canonical inference result is

\[
y^\*=\arg\min_{y\in[0,1]^n}
\sum_j w_j\max(0,\ell_j(x,y))^{p_j}
\quad\text{subject to all declared hard constraints.}
\]

`researchguard.trace.inference.compiler` owns compilation.
`researchguard.trace.inference.osqp_backend` converts that exact model to a sparse QP
and calls OSQP directly. There is no fallback evaluator.

The values are structural MAP support inside the declared model. They are not
calibrated probabilities and do not prove that the underlying facts are true.

## 2. Input and output separation

Caller-authored model input may declare:

- source lineage and independence groups;
- evidence observations and their extraction quality;
- events, time intervals, stages, entities, locations, and trace candidates;
- typed hypothesis-evidence polarity: `support`, `oppose`, or `limit`;
- typed relations between hypotheses;
- causal candidates, mechanisms, confounder reviews, alternatives, and scope;
- evidence ablations, scenario perturbations, and expected sensitivities.

Caller-authored model input must not declare:

- final trace status or support/confidence;
- final hypothesis support, rank, live-winner state, or causal support;
- final safe wording or unsafe-wording clearance;
- generic predicate values that bypass typed compilation;
- old intervention or counterfactual-outcome records.

Those are solution projections and belong only in a current
`InferenceReceipt` or `StorylineDepthReceipt`.

## 3. Provenance and independence

Every source has:

- `lineage_id`: the derivation family;
- `independence_group`: the lane allowed to count as independent support;
- optional `derived_from_source_ids`: direct provenance edges.

Multiple evidence rows in one independence group may improve traceability, but
they contribute at most one independent support lane. A syndicated copy is not
a second corroborating source.

## 4. Factor ownership

The compiler invokes deterministic factor builders in this order:

1. `evidence_trace`: evidence quality, lineage deduplication, trace support,
   sparsity, source-only and invalid-source hard gates;
2. `entity`: observed name/alias/location features and latent identity;
3. `temporal_stage`: interval order, stage coherence, contradictions, and
   temporal hard caps;
4. `storyline_causal`: hypothesis support/opposition, competing alternatives,
   and bounded qualitative-causal support.

Feature extraction may use deterministic heuristics. A feature is only an
observed atom; it is never a second decision authority.

## 5. Qualitative causal exploration

TraceGuard represents a causal candidate in the same objective as its trace
and storyline:

\[
0\le C_h\le H_h\le1,
\]

where \(H_h\) is hypothesis support and \(C_h\) is bounded qualitative causal
support. Factors for \(C_h\) require:

- supported cause and effect events;
- cause-before-effect chronology;
- an evidence-backed mechanism;
- explicit alternative comparison;
- reviewed confounders;
- a declared population/time/location/boundary scope.

Missing or reversed chronology, missing mechanism evidence, unresolved
confounders, missing alternatives, or missing scope cap causal support. Text
containing words such as “because” or “caused” creates no causal atom.

A `supported` causal projection licenses only wording such as “the declared
evidence structurally supports this bounded causal explanation.” It does not
identify `do(X)`, average treatment effects, conditional treatment effects, or
real-world counterfactual truth.

## 6. Competing storylines

Each hypothesis has its own latent support atom. Typed evidence links shape
that atom according to their polarity. `alternative` and `competes_with`
relations add joint competition factors. Rank and `live` status are projected
from the same solution:

- rank orders solved support deterministically;
- a hypothesis remains live when it is within the policy margin of the winner;
- no separate ranking formula may overwrite the solved values.

## 7. Perturbation and sensitivity

An evidence ablation or scenario perturbation is a pure transformation
\(T_k(M)\) of the typed model. TraceGuard must:

1. fingerprint and solve baseline model \(M\);
2. construct \(T_k(M)\) without mutating \(M\);
3. compile \(T_k(M)\) with the same schema, policy, factor set, and solver;
4. solve it again;
5. compare canonical trace/hypothesis projections;
6. bind baseline and perturbed receipt ids, problem fingerprints, and solver
   ids into the perturbation effect.

An expected sensitivity states a direction and minimum absolute support
change. It is a regression expectation about this model, not a factual
counterfactual outcome.

## 8. Solver and receipt hard gates

OSQP output is accepted only when:

- status is in the frozen accepted-status inventory;
- the primal vector and quality metrics are finite;
- primal and dual residuals are within policy limits;
- every hard constraint is feasible within tolerance;
- the recomputed factor objective matches the solver objective.

Failure is visible and closed. TraceGuard must not silently switch solver,
reuse a stale solution, or manufacture projections.

Every `InferenceReceipt` binds:

- schema, policy, factor-set, solver, problem, and solution identities;
- objective and factor-level contributions;
- trace and hypothesis projections;
- diagnostics, gaps, contradictions, and claim boundary.

Every projected top-support or top-opposition factor id must resolve to a
contribution in that same receipt.

## 9. Prompt protocol

When an AI uses TraceGuard, it should follow this sequence:

1. State the investigation question and the maximum claim scope.
2. Preserve sources before extracting evidence.
3. Assign source lineage and independence groups.
4. Create typed events and trace candidates without final status/support.
5. For competing explanations, create separate hypotheses and typed links.
6. For causal exploration, explicitly create mechanism, confounder,
   alternative, chronology, and scope records. If any are missing, keep a
   visible gap.
7. Run canonical evaluation and read the inference receipt.
8. For “why”, “what if”, or “which evidence matters”, run same-engine
   perturbations and read the depth receipt.
9. Report support, opposition, binding constraints, gaps, and bounded wording.
10. Hand final claim-licensing review to LogicGuard when the output becomes
    prose, a report, or a consequential conclusion.

The AI must not estimate support or causal strength in prose when the canonical
engine is available. It may propose missing objects, but only the engine may
project status, support, rank, or causal license.

## 10. Public claim boundary

TraceGuard answers:

- what evidence-backed temporal trace is structurally supported;
- which competing storyline currently has more modeled support;
- which evidence, contradiction, or boundary most affects that result;
- whether a bounded qualitative causal explanation is licensed;
- how the same model responds to declared evidence/scenario changes.

TraceGuard does not answer, by itself:

- whether every source statement is factually true;
- whether a causal effect is statistically identified;
- what would actually happen under intervention;
- whether final written prose is logically licensed.
