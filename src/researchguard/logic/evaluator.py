"""H-WADF state propagation evaluator."""

from __future__ import annotations

from collections import defaultdict

from .acceptance import evaluate_acceptance, initial_node_evaluation
from .model import EvaluationResult, EvaluationTraceStep, LogicModel, NodeEvaluation
from .schema import STATE_UNDECIDED, SUPPORT_EDGE_TYPES


def evaluate_model(model: LogicModel, *, max_iterations: int = 25) -> EvaluationResult:
    """Evaluate a LogicGuard model with transparent fixed-point propagation."""

    current = {node_id: initial_node_evaluation(node_id, model) for node_id in model.nodes}
    trace: list[EvaluationTraceStep] = []
    cycles = detect_argument_cycles(model)
    seen_vectors: set[tuple[tuple[str, str, int], ...]] = set()
    converged = False

    for iteration in range(1, max_iterations + 1):
        vector = _state_vector(current)
        if vector in seen_vectors:
            trace.append(
                EvaluationTraceStep(
                    iteration,
                    "__model__",
                    STATE_UNDECIDED,
                    STATE_UNDECIDED,
                    0.0,
                    0.0,
                    "State vector repeated; possible oscillation or circular dependency.",
                )
            )
            break
        seen_vectors.add(vector)

        next_results: dict[str, NodeEvaluation] = {}
        changed = False
        for node_id in model.nodes:
            decision = evaluate_acceptance(model, node_id, current)
            previous = current[node_id]
            next_eval = NodeEvaluation(
                node_id=node_id,
                state=decision.state,
                confidence=round(decision.confidence, 6),
                explanation=decision.explanation,
                blockers=list(dict.fromkeys(decision.blockers)),
            )
            next_results[node_id] = next_eval
            if previous.state != next_eval.state or abs(previous.confidence - next_eval.confidence) > 0.0001:
                changed = True
                trace.append(
                    EvaluationTraceStep(
                        iteration=iteration,
                        node_id=node_id,
                        old_state=previous.state,
                        new_state=next_eval.state,
                        old_confidence=previous.confidence,
                        new_confidence=next_eval.confidence,
                        reason=next_eval.explanation,
                    )
                )
        current = next_results
        if not changed:
            converged = True
            break

    warnings: list[str] = []
    if cycles:
        warnings.append("Circular support/dependency paths detected.")
    if not converged:
        warnings.append("Evaluation did not converge before the iteration or oscillation limit.")

    return EvaluationResult(
        model_id=model.id,
        root_claim=model.root_claim,
        node_results=current,
        trace=trace,
        iterations=iteration if "iteration" in locals() else 0,
        converged=converged,
        cycles=cycles,
        warnings=warnings,
        model_revision_id=(
            str(model.metadata.get("model_revision_id"))
            if model.metadata.get("model_revision_id")
            else None
        ),
    )


def detect_argument_cycles(model: LogicModel) -> list[list[str]]:
    """Return directed support cycles without relying on Python recursion.

    Logic models can contain long evidence-to-claim chains.  An explicit DFS
    stack keeps cycle diagnostics safe for chains that are much deeper than
    Python's recursion limit while preserving the model's node/edge order in
    the reported cycle.
    """

    graph: dict[str, list[str]] = defaultdict(list)
    for edge in model.edges:
        if edge.type in SUPPORT_EDGE_TYPES:
            graph[edge.source].append(edge.target)

    visited: set[str] = set()
    cycles: list[list[str]] = []
    cycle_keys: set[frozenset[str]] = set()

    for root_id in model.nodes:
        if root_id in visited:
            continue

        active: set[str] = {root_id}
        path = [root_id]
        path_positions = {root_id: 0}
        visited.add(root_id)
        frames: list[tuple[str, int]] = [(root_id, 0)]

        while frames:
            node_id, neighbor_index = frames[-1]
            neighbors = graph.get(node_id, [])
            if neighbor_index >= len(neighbors):
                frames.pop()
                active.remove(node_id)
                path_positions.pop(node_id, None)
                path.pop()
                continue

            neighbor = neighbors[neighbor_index]
            frames[-1] = (node_id, neighbor_index + 1)
            if neighbor not in visited:
                visited.add(neighbor)
                active.add(neighbor)
                path_positions[neighbor] = len(path)
                path.append(neighbor)
                frames.append((neighbor, 0))
                continue

            if neighbor in active:
                start = path_positions[neighbor]
                cycle = path[start:] + [neighbor]
                cycle_key = frozenset(cycle)
                if cycle_key not in cycle_keys:
                    cycle_keys.add(cycle_key)
                    cycles.append(cycle)
    return cycles


def _cycle_seen(cycles: list[list[str]], candidate: list[str]) -> bool:
    candidate_set = set(candidate)
    return any(set(cycle) == candidate_set for cycle in cycles)


def _state_vector(results: dict[str, NodeEvaluation]) -> tuple[tuple[str, str, int], ...]:
    return tuple(
        sorted((node_id, result.state, int(result.confidence * 10000)) for node_id, result in results.items())
    )
