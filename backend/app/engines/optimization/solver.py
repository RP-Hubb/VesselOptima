"""
VesselOptima — Phase 7: MILP Solver Abstraction & HiGHS Adapter

Provides a decoupled, pluggable solver adapter layer.
Default implementation uses the embedded open-source HiGHS solver via scipy.optimize.milp,
requiring zero external software, zero proprietary licenses, and 100% air-gapped operation.
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
from scipy.optimize import LinearConstraint, Bounds, milp

from app.engines.optimization.constraints import LinearConstraintDefinition
from app.engines.optimization.reason_codes import OptimizationStatus


@dataclass
class RawSolverResult:
    """Standardized output from any underlying MILP solver adapter."""
    status: OptimizationStatus
    objective_value: float
    solution: list[float]
    solve_time_seconds: float
    solver_name: str
    solver_version: str
    solver_message: str
    raw_status_code: int
    is_optimal: bool
    iterations: int = 0
    node_count: int = 0
    solver_metadata: dict[str, Any] = field(default_factory=dict)


class BaseSolverAdapter(abc.ABC):
    """Abstract interface for MILP solver adapters."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def version(self) -> str:
        pass

    @abc.abstractmethod
    def solve(
        self,
        c: list[float],
        constraints: list[LinearConstraintDefinition],
        variable_count: int,
        binary_indices: list[int],
        time_limit_seconds: Optional[float] = None,
        mip_gap: float = 1e-4,
    ) -> RawSolverResult:
        """Executes the MILP optimization problem."""
        pass


class HiGHSSolverAdapter(BaseSolverAdapter):
    """
    High-performance, open-source HiGHS simplex & branch-and-cut solver
    integrated natively via scipy.optimize.milp.
    """

    @property
    def name(self) -> str:
        return "HiGHS"

    @property
    def version(self) -> str:
        import scipy
        return f"HiGHS (via SciPy {scipy.__version__})"

    def solve(
        self,
        c: list[float],
        constraints: list[LinearConstraintDefinition],
        variable_count: int,
        binary_indices: list[int],
        time_limit_seconds: Optional[float] = None,
        mip_gap: float = 1e-4,
    ) -> RawSolverResult:
        start_time = time.perf_counter()

        if variable_count == 0:
            return RawSolverResult(
                status=OptimizationStatus.EMPTY_MODEL,
                objective_value=0.0,
                solution=[],
                solve_time_seconds=0.0,
                solver_name=self.name,
                solver_version=self.version,
                solver_message="No variables in optimization model.",
                raw_status_code=0,
                is_optimal=True,
            )

        c_arr = np.array(c, dtype=np.float64)

        # Integrality constraints: 1 for binary, 0 for continuous
        integrality = np.zeros(variable_count, dtype=np.int32)
        for idx in binary_indices:
            if idx < variable_count:
                integrality[idx] = 1

        # Bounds: for binary variables [0, 1]
        lb = np.zeros(variable_count, dtype=np.float64)
        ub = np.ones(variable_count, dtype=np.float64)
        bounds = Bounds(lb=lb, ub=ub)

        # Assemble linear constraint matrix A, b_l, b_u
        num_constraints = len(constraints)
        if num_constraints > 0:
            A = np.zeros((num_constraints, variable_count), dtype=np.float64)
            b_l = np.zeros(num_constraints, dtype=np.float64)
            b_u = np.zeros(num_constraints, dtype=np.float64)

            for row_idx, constr in enumerate(constraints):
                b_l[row_idx] = constr.lower_bound
                b_u[row_idx] = constr.upper_bound
                for col_idx, coeff in constr.coefficients.items():
                    if col_idx < variable_count:
                        A[row_idx, col_idx] = coeff

            linear_constraints = LinearConstraint(A, b_l, b_u)
        else:
            linear_constraints = None

        options: dict[str, Any] = {
            "mip_rel_gap": mip_gap,
            "disp": False,
        }
        if time_limit_seconds is not None and time_limit_seconds > 0:
            options["time_limit"] = float(time_limit_seconds)

        try:
            res = milp(
                c=c_arr,
                integrality=integrality,
                bounds=bounds,
                constraints=linear_constraints,
                options=options,
            )
            elapsed = time.perf_counter() - start_time

            # Map status
            # HiGHS / scipy status codes:
            # 0: Optimal
            # 1: Iteration or time limit reached
            # 2: Infeasible problem
            # 3: Unbounded problem
            # 4: Other solver error
            status = OptimizationStatus.SOLVER_ERROR
            is_optimal = False

            if res.status == 0:
                status = OptimizationStatus.OPTIMAL
                is_optimal = True
            elif res.status == 1:
                status = OptimizationStatus.TIME_LIMIT
                # If a feasible solution exists, mark as FEASIBLE
                if res.x is not None:
                    status = OptimizationStatus.FEASIBLE
            elif res.status == 2:
                status = OptimizationStatus.INFEASIBLE
            elif res.status == 3:
                status = OptimizationStatus.UNBOUNDED
            else:
                status = OptimizationStatus.SOLVER_ERROR

            # Notice: scipy.optimize.milp MINIMIZES c^T x.
            # Our maximization objective is Z = -res.fun (or 0.0 if infeasible)
            obj_val = float(-res.fun) if res.fun is not None and not np.isnan(res.fun) else 0.0
            sol = [float(v) for v in res.x] if res.x is not None else [0.0] * variable_count

            return RawSolverResult(
                status=status,
                objective_value=obj_val,
                solution=sol,
                solve_time_seconds=round(elapsed, 4),
                solver_name=self.name,
                solver_version=self.version,
                solver_message=str(res.message),
                raw_status_code=int(res.status),
                is_optimal=is_optimal,
                solver_metadata={
                    "success": bool(res.success),
                    "status_code": int(res.status),
                    "message": str(res.message),
                    "variable_count": variable_count,
                    "constraint_count": num_constraints,
                },
            )

        except Exception as exc:
            elapsed = time.perf_counter() - start_time
            return RawSolverResult(
                status=OptimizationStatus.SOLVER_ERROR,
                objective_value=0.0,
                solution=[0.0] * variable_count,
                solve_time_seconds=round(elapsed, 4),
                solver_name=self.name,
                solver_version=self.version,
                solver_message=f"Solver exception: {str(exc)}",
                raw_status_code=-1,
                is_optimal=False,
                solver_metadata={"error": str(exc)},
            )
