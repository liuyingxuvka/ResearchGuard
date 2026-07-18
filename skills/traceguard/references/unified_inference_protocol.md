# TraceGuard Unified Inference Protocol

Version: `traceguard.unified-inference.v2`

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
`researchguard.trace.inference.osqp_backend` converts that exact model to a
sparse QP and calls OSQP directly. There is no fallback evaluator.

The values are structural MAP support inside the declared model. They are not
calibrated probabilities and do not prove that the underlying facts are true.

## 2. Input and output separation

Caller-authored model input may declare source lineage and independence,
evidence observations, typed events and relations, hypotheses, causal
candidates, mechanisms, confounders, alternatives, scope, perturbations, and
expected sensitivities.

Caller-authored input must not declare final trace status, final hypothesis
rank, final causal support, final safe wording, generic predicate values that
bypass typed compilation, or old intervention/counterfactual outcome records.
Those are projections of one current inference receipt.

## 3. Provenance and independence

Every source has a `lineage_id`, an `independence_group`, and optional direct
provenance edges. Several rows in one independence group improve traceability
but count as one independent support lane.

## 4. Factor ownership

The compiler invokes deterministic factor builders in this order:

1. evidence and trace quality, lineage, sparsity, and hard source gates;
2. observed entity features and latent identity;
3. temporal order, stage coherence, contradictions, and hard caps;
4. hypothesis support/opposition, alternatives, and bounded causal support.

Feature extraction may use deterministic heuristics. A feature is an observed
atom, not a second decision authority.

## 5. Qualitative causal exploration

Bounded qualitative causal support requires supported cause/effect events,
cause-before-effect chronology, an evidence-backed mechanism, explicit
alternative comparison, reviewed confounders, and declared scope. Missing or
reversed chronology, missing mechanism evidence, unresolved confounders,
missing alternatives, or missing scope caps causal support.

Causal text alone creates no causal atom. A supported projection does not
identify interventions or treatment effects.

## 6. Competing storylines

Each hypothesis has its own latent support atom. Typed evidence polarity and
competition relations shape that atom. Rank and live status are projected from
the same solution; no separate ranking formula may overwrite solved values.

## 7. Perturbation and sensitivity

A perturbation is a pure transformation of the typed model. TraceGuard
fingerprints and solves the baseline, constructs the transformation without
mutation, recompiles with the same policy/factors/solver, solves again, and
binds both receipts into the perturbation effect.

An expected sensitivity is a regression expectation about the model, not a
factual counterfactual outcome.

## 8. Solver and receipt hard gates

OSQP output is accepted only when status, finite values, residual limits, hard
constraints, and recomputed objective all pass. Failure is visible and closed;
TraceGuard never switches solver, reuses stale output, or manufactures a
projection.

Every inference receipt binds schema, policy, factor set, solver, problem,
solution, contributions, projections, diagnostics, gaps, contradictions, and
claim boundary. Every reported factor id resolves inside that same receipt.

## 9. Prompt protocol

1. State the investigation question and maximum claim scope.
2. Preserve sources and assign lineage/independence.
3. Create typed evidence, events, traces, and competing hypotheses without
   final statuses.
4. Declare mechanism, confounders, alternatives, chronology, and scope for
   causal exploration.
5. Run canonical evaluation and read the inference receipt.
6. Run same-engine perturbations for why/what-if/evidence-importance questions.
7. Report support, opposition, binding constraints, gaps, and bounded wording.
8. Hand consequential final claim licensing to LogicGuard.

AI may propose missing objects, but only the engine projects status, support,
rank, or causal license.

## 10. Public claim boundary

TraceGuard can report which evidence-backed trace or competing storyline is
structurally supported, which evidence or boundary affects it, whether a
bounded qualitative causal explanation is licensed, and how the same model
responds to declared changes.

It does not by itself establish factual truth, statistically identify causal
effects, predict an intervention, or license final prose.
