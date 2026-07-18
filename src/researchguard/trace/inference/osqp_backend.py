"""Direct sparse-QP backend for TraceGuard hinge-loss inference."""

from __future__ import annotations

from importlib.metadata import version
from math import inf, isfinite

import numpy as np
import osqp
from scipy import sparse

from .policy import InferencePolicy
from .types import CompiledProblem, InferenceSolution, SolverError


def _substitute_observed(
    problem: CompiledProblem,
    terms: tuple[tuple[str, float], ...],
    constant: float,
) -> tuple[dict[str, float], float]:
    observed = {atom.atom_id: float(atom.value) for atom in problem.observed_atoms}
    latent_coefficients: dict[str, float] = {}
    adjusted = float(constant)
    for atom_id, coefficient in terms:
        if atom_id in observed:
            adjusted += float(coefficient) * observed[atom_id]
        else:
            latent_coefficients[atom_id] = (
                latent_coefficients.get(atom_id, 0.0) + float(coefficient)
            )
    return latent_coefficients, adjusted


def solve_problem(
    problem: CompiledProblem,
    policy: InferencePolicy,
) -> InferenceSolution:
    """CompiledProblem x Policy -> InferenceSolution.

    Each factor receives one non-negative slack variable with
    ``slack >= expression``. Linear and squared hinge losses map directly to the
    OSQP objective. Hard constraints and atom bounds are linear rows.
    """

    latent_index = {
        atom.atom_id: index for index, atom in enumerate(problem.latent_atoms)
    }
    latent_count = len(problem.latent_atoms)
    factor_count = len(problem.factors)
    variable_count = latent_count + factor_count
    if variable_count == 0:
        raise SolverError("compiled problem has no latent atom or factor")

    p_diag = np.zeros(variable_count, dtype=float)
    q = np.zeros(variable_count, dtype=float)
    for index, factor in enumerate(problem.factors):
        slack_index = latent_count + index
        if factor.power == 2:
            p_diag[slack_index] = 2.0 * float(factor.weight)
        else:
            q[slack_index] = float(factor.weight)

    rows: list[dict[int, float]] = []
    lower: list[float] = []
    upper: list[float] = []

    for index, atom in enumerate(problem.latent_atoms):
        rows.append({index: 1.0})
        lower.append(float(atom.lower))
        upper.append(float(atom.upper))

    for factor_index, factor in enumerate(problem.factors):
        slack_index = latent_count + factor_index
        rows.append({slack_index: 1.0})
        lower.append(0.0)
        upper.append(inf)

        coefficients, constant = _substitute_observed(
            problem,
            factor.expression.terms,
            factor.expression.constant,
        )
        row = {
            latent_index[atom_id]: float(coefficient)
            for atom_id, coefficient in coefficients.items()
        }
        row[slack_index] = -1.0
        rows.append(row)
        lower.append(-inf)
        upper.append(-constant)

    for constraint in problem.hard_constraints:
        coefficients, constant = _substitute_observed(
            problem,
            constraint.expression.terms,
            constraint.expression.constant,
        )
        rows.append(
            {
                latent_index[atom_id]: float(coefficient)
                for atom_id, coefficient in coefficients.items()
            }
        )
        lower.append(
            -inf if constraint.lower is None else float(constraint.lower) - constant
        )
        upper.append(
            inf if constraint.upper is None else float(constraint.upper) - constant
        )

    row_indices: list[int] = []
    column_indices: list[int] = []
    values: list[float] = []
    for row_index, row in enumerate(rows):
        for column_index, coefficient in sorted(row.items()):
            row_indices.append(row_index)
            column_indices.append(column_index)
            values.append(coefficient)

    matrix_a = sparse.csc_matrix(
        (values, (row_indices, column_indices)),
        shape=(len(rows), variable_count),
    )
    matrix_p = sparse.diags(p_diag, format="csc")
    try:
        solver = osqp.OSQP()
        solver.setup(
            P=matrix_p,
            q=q,
            A=matrix_a,
            l=np.asarray(lower, dtype=float),
            u=np.asarray(upper, dtype=float),
            verbose=False,
            eps_abs=policy.eps_abs,
            eps_rel=policy.eps_rel,
            max_iter=policy.max_iter,
            polishing=policy.polish,
            warm_starting=False,
            scaled_termination=False,
        )
        result = solver.solve(raise_error=False)
    except Exception as exc:  # OSQP exposes several backend-specific errors.
        raise SolverError(f"OSQP setup/solve failed: {exc}") from exc

    status = str(result.info.status).strip().lower()
    if status not in set(policy.accepted_statuses):
        raise SolverError(f"OSQP did not converge to an accepted status: {status}")
    if result.x is None or len(result.x) != variable_count:
        raise SolverError("OSQP returned no complete primal solution")

    vector = np.asarray(result.x, dtype=float)
    if not np.all(np.isfinite(vector)):
        raise SolverError("OSQP returned non-finite primal values")
    primal_residual = float(result.info.prim_res)
    dual_residual = float(result.info.dual_res)
    objective = float(result.info.obj_val)
    if not all(isfinite(item) for item in (primal_residual, dual_residual, objective)):
        raise SolverError("OSQP returned non-finite quality metrics")
    if primal_residual > policy.maximum_primal_residual:
        raise SolverError(
            f"OSQP primal residual {primal_residual} exceeds "
            f"{policy.maximum_primal_residual}"
        )
    if dual_residual > policy.maximum_dual_residual:
        raise SolverError(
            f"OSQP dual residual {dual_residual} exceeds "
            f"{policy.maximum_dual_residual}"
        )

    observed_values = {
        atom.atom_id: float(atom.value) for atom in problem.observed_atoms
    }
    latent_values = {
        atom.atom_id: min(1.0, max(0.0, float(vector[index])))
        for atom, index in (
            (atom, latent_index[atom.atom_id]) for atom in problem.latent_atoms
        )
    }
    atom_values = {**observed_values, **latent_values}
    maximum_constraint_violation = max(
        (
            constraint.violation(atom_values)
            for constraint in problem.hard_constraints
        ),
        default=0.0,
    )
    if maximum_constraint_violation > policy.maximum_constraint_violation:
        raise SolverError(
            f"hard-constraint violation {maximum_constraint_violation} exceeds "
            f"{policy.maximum_constraint_violation}"
        )
    recomputed_objective = sum(
        factor.loss(atom_values) for factor in problem.factors
    )
    objective_tolerance = max(
        1e-6,
        policy.eps_abs * 10,
        policy.eps_rel * max(1.0, abs(recomputed_objective)),
    )
    if abs(objective - recomputed_objective) > objective_tolerance:
        raise SolverError(
            f"OSQP objective {objective} does not match factor objective "
            f"{recomputed_objective}"
        )

    return InferenceSolution(
        backend="osqp",
        backend_version=version("osqp"),
        status=status,
        objective=recomputed_objective,
        atom_values=atom_values,
        primal_residual=primal_residual,
        dual_residual=dual_residual,
        maximum_constraint_violation=maximum_constraint_violation,
        iterations=int(result.info.iter),
        run_time_seconds=float(result.info.run_time),
        problem_fingerprint=problem.problem_fingerprint,
    )
