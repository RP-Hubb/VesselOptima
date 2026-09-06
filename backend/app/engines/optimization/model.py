"""
VesselOptima — Phase 7: MILP Optimization Model

Assembles variables, constraints, objective, and solver adapters into a cohesive,
deterministic optimization model. Performs post-solution trade-off analysis and
constructs the comprehensive OptimizationResult.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.engines.optimization.constraints import ConstraintBuilder, LinearConstraintDefinition
from app.engines.optimization.objective import ObjectiveBuilder, ObjectiveConfig, ObjectiveDecomposition
from app.engines.optimization.reason_codes import (
    AssignmentSelectionStatus,
    OptimizationStatus,
    TradeOffReasonCode,
    TRADE_OFF_DESCRIPTIONS,
)
from app.engines.optimization.result import (
    AssignmentResult,
    OptimizationResult,
    UnassignedCargoResult,
)
from app.engines.optimization.solver import BaseSolverAdapter, HiGHSSolverAdapter, RawSolverResult
from app.engines.optimization.variables import CandidateVariable, CargoSlackVariable, VariableRegistry


class OptimizationModel:
    """Deterministic Mixed-Integer Linear Programming fleet optimization model."""

    def __init__(
        self,
        solver: Optional[BaseSolverAdapter] = None,
        objective_config: Optional[ObjectiveConfig] = None,
        turnaround_hours: float = 24.0,
    ):
        self.solver = solver or HiGHSSolverAdapter()
        self.objective_config = objective_config or ObjectiveConfig()
        self.turnaround_hours = turnaround_hours

        self.registry = VariableRegistry()
        self.constraint_builder = ConstraintBuilder(self.registry, turnaround_hours=turnaround_hours)
        self.objective_builder = ObjectiveBuilder(self.registry, self.objective_config)

        self._candidate_counter = 0
        self._cargo_counter = 0
        self._commitments: dict[int, list[tuple[datetime, datetime]]] = {}
        self._transit_days: dict[tuple[int, int], float] = {}

    def add_candidate(
        self,
        candidate_id: str,
        vessel_id: int,
        vessel_name: str,
        cargo_id: Optional[int],
        cargo_name: str,
        start_time: datetime,
        end_time: datetime,
        expected_revenue: float,
        voyage_cost: float,
        net_contribution: float,
        idle_days_saved: float = 0.0,
        avoided_idle_cost: float = 0.0,
        ballast_distance_nm: float = 0.0,
        ballast_days: float = 0.0,
        origin_port_id: Optional[int] = None,
        destination_port_id: Optional[int] = None,
        employment_type: str = "CARGO_VOYAGE",
        raw_metadata: Optional[dict[str, Any]] = None,
    ) -> CandidateVariable:
        """Registers a candidate voyage decision variable x_k."""
        idx = self.registry.total_variables
        var = CandidateVariable(
            index=idx,
            candidate_id=candidate_id,
            vessel_id=vessel_id,
            vessel_name=vessel_name,
            cargo_id=cargo_id,
            cargo_name=cargo_name,
            start_time=start_time,
            end_time=end_time,
            expected_revenue=expected_revenue,
            voyage_cost=voyage_cost,
            net_contribution=net_contribution,
            idle_days_saved=idle_days_saved,
            avoided_idle_cost=avoided_idle_cost,
            ballast_distance_nm=ballast_distance_nm,
            ballast_days=ballast_days,
            origin_port_id=origin_port_id,
            destination_port_id=destination_port_id,
            employment_type=employment_type,
            raw_metadata=raw_metadata or {},
        )
        self.registry.add_candidate(var)
        self._candidate_counter += 1
        return var

    def add_cargo(
        self, cargo_id: int, cargo_name: str, unserved_penalty: Optional[float] = None
    ) -> CargoSlackVariable:
        """Registers a cargo parcel slack variable u_c for optional rejection."""
        if cargo_id in self.registry.slack_by_cargo_id:
            return self.registry.slack_by_cargo_id[cargo_id]

        idx = self.registry.total_variables
        penalty = (
            unserved_penalty
            if unserved_penalty is not None
            else self.objective_config.cargo_penalties.get(cargo_id, self.objective_config.default_unserved_penalty)
        )
        var = CargoSlackVariable(
            index=idx,
            cargo_id=cargo_id,
            cargo_name=cargo_name,
            unserved_penalty=penalty,
        )
        self.registry.add_cargo_slack(var)
        self._cargo_counter += 1
        return var

    def set_vessel_commitments(
        self, vessel_commitments: dict[int, list[tuple[datetime, datetime]]]
    ) -> None:
        """Sets hard commitments (fixtures) per vessel."""
        self._commitments = vessel_commitments

    def add_custom_constraint(self, constraint: LinearConstraintDefinition) -> None:
        """Adds an explicit custom linear constraint to the model."""
        self.constraint_builder.add_custom_constraint(constraint)

    def set_inter_port_transit_days(self, transit_days: dict[tuple[int, int], float]) -> None:
        """Sets inter-port transit durations for multi-period transition feasibility."""
        self._transit_days = transit_days

    def solve(
        self,
        time_limit_seconds: Optional[float] = None,
        mip_gap: float = 1e-4,
        run_id: Optional[str] = None,
    ) -> OptimizationResult:
        """Constructs and executes the MILP optimization model."""
        now = datetime.now(timezone.utc)
        opt_run_id = run_id or f"OPT-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

        audit_trail: list[dict[str, Any]] = [
            {
                "timestamp": now.isoformat(),
                "event": "OPTIMIZATION_INITIALIZED",
                "run_id": opt_run_id,
                "candidate_count": self.registry.candidate_count,
                "cargo_count": self.registry.slack_count,
                "solver": self.solver.name,
            }
        ]

        # Handle zero candidates cleanly
        if self.registry.candidate_count == 0:
            audit_trail.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event": "EMPTY_MODEL_DETECTED",
                    "message": "Zero admissible candidates submitted to optimizer.",
                }
            )
            return OptimizationResult(
                run_id=opt_run_id,
                status=OptimizationStatus.EMPTY_MODEL,
                objective_value=0.0,
                decomposition=ObjectiveDecomposition(),
                selected_assignments=[],
                rejected_opportunities=[],
                unassigned_cargos=[],
                vessel_utilization={"total_vessels": 0, "assigned_vessels": 0, "utilization_pct": 0.0},
                solver_metadata={"solver": self.solver.name, "message": "Zero candidates in input set."},
                constraint_summary={"total_constraints": 0},
                audit_trail=audit_trail,
                solve_time_seconds=0.0,
                created_at=now,
            )

        # 1. Build constraints
        constraints = self.constraint_builder.build_all(
            vessel_commitments=self._commitments,
            inter_port_transit_days=self._transit_days,
        )

        # 2. Build cost vector
        c_vector = self.objective_builder.build_cost_vector()

        # 3. All variables are binary
        binary_indices = list(range(self.registry.total_variables))

        audit_trail.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": "MODEL_CONSTRUCTED",
                "variables": self.registry.total_variables,
                "constraints": len(constraints),
            }
        )

        # 4. Invoke solver
        raw_res: RawSolverResult = self.solver.solve(
            c=c_vector,
            constraints=constraints,
            variable_count=self.registry.total_variables,
            binary_indices=binary_indices,
            time_limit_seconds=time_limit_seconds,
            mip_gap=mip_gap,
        )

        audit_trail.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": "SOLVER_COMPLETED",
                "solver_status": raw_res.status.value,
                "is_optimal": raw_res.is_optimal,
                "raw_code": raw_res.raw_status_code,
                "solve_time_s": raw_res.solve_time_seconds,
            }
        )

        # If infeasible or error
        if raw_res.status not in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE):
            return OptimizationResult(
                run_id=opt_run_id,
                status=raw_res.status,
                objective_value=0.0,
                decomposition=ObjectiveDecomposition(),
                selected_assignments=[],
                rejected_opportunities=[],
                unassigned_cargos=[],
                vessel_utilization={"total_vessels": 0, "assigned_vessels": 0, "utilization_pct": 0.0},
                solver_metadata=raw_res.solver_metadata,
                constraint_summary=self._summarize_constraints(constraints),
                audit_trail=audit_trail,
                solve_time_seconds=raw_res.solve_time_seconds,
                created_at=now,
            )

        # 5. Decompose objective
        decomposition = self.objective_builder.decompose_solution(raw_res.solution)

        # 6. Extract assignments and perform trade-off diagnostics
        selected_assignments, rejected_opportunities, unassigned_cargos = self._extract_results(
            raw_res.solution, constraints
        )

        # 7. Vessel utilization
        utilization = self._compute_utilization(selected_assignments)

        # 8. Constraint summary
        constraint_summary = self._summarize_constraints(constraints)

        audit_trail.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": "OPTIMIZATION_COMPLETE",
                "selected_count": len(selected_assignments),
                "rejected_count": len(rejected_opportunities),
                "unassigned_cargo_count": len(unassigned_cargos),
                "global_objective": round(decomposition.global_objective_value, 2),
            }
        )

        return OptimizationResult(
            run_id=opt_run_id,
            status=raw_res.status,
            objective_value=decomposition.global_objective_value,
            decomposition=decomposition,
            selected_assignments=selected_assignments,
            rejected_opportunities=rejected_opportunities,
            unassigned_cargos=unassigned_cargos,
            vessel_utilization=utilization,
            solver_metadata=raw_res.solver_metadata,
            constraint_summary=constraint_summary,
            audit_trail=audit_trail,
            solve_time_seconds=raw_res.solve_time_seconds,
            created_at=now,
        )

    def _extract_results(
        self, solution: list[float], constraints: list[LinearConstraintDefinition]
    ) -> tuple[list[AssignmentResult], list[AssignmentResult], list[UnassignedCargoResult]]:
        selected: list[AssignmentResult] = []
        rejected: list[AssignmentResult] = []
        unassigned: list[UnassignedCargoResult] = []

        selected_candidates: set[str] = set()
        selected_by_vessel: dict[int, list[CandidateVariable]] = {}
        selected_by_cargo: dict[int, CandidateVariable] = {}

        for c_var in self.registry.candidate_vars:
            val = solution[c_var.index] if c_var.index < len(solution) else 0.0
            if val > 0.5:
                selected_candidates.add(c_var.candidate_id)
                selected_by_vessel.setdefault(c_var.vessel_id, []).append(c_var)
                if c_var.cargo_id is not None:
                    selected_by_cargo[c_var.cargo_id] = c_var

        # Classify candidate variables
        for c_var in self.registry.candidate_vars:
            voyage_days = (
                (c_var.end_time - c_var.start_time).total_seconds() / 86400.0
                if c_var.end_time and c_var.start_time
                else 0.0
            )
            if c_var.candidate_id in selected_candidates:
                selected.append(
                    AssignmentResult(
                        candidate_id=c_var.candidate_id,
                        vessel_id=c_var.vessel_id,
                        vessel_name=c_var.vessel_name,
                        cargo_id=c_var.cargo_id,
                        cargo_name=c_var.cargo_name,
                        is_selected=True,
                        selection_status=AssignmentSelectionStatus.SELECTED,
                        start_time=c_var.start_time,
                        end_time=c_var.end_time,
                        expected_revenue=c_var.expected_revenue,
                        voyage_cost=c_var.voyage_cost,
                        gross_contribution=c_var.net_contribution,
                        idle_days_saved=c_var.idle_days_saved,
                        avoided_idle_cost=c_var.avoided_idle_cost,
                        ballast_distance_nm=c_var.ballast_distance_nm,
                        ballast_days=c_var.ballast_days,
                        voyage_days=voyage_days,
                        trade_off_reason_code=TradeOffReasonCode.OPTIMAL_GLOBAL_ALLOCATION,
                        trade_off_explanation=TRADE_OFF_DESCRIPTIONS[TradeOffReasonCode.OPTIMAL_GLOBAL_ALLOCATION],
                        assignment_metadata=c_var.raw_metadata,
                    )
                )
            else:
                # Determine trade-off reason
                reason_code, reason_text = self._diagnose_rejection(
                    c_var, selected_by_vessel, selected_by_cargo
                )
                rejected.append(
                    AssignmentResult(
                        candidate_id=c_var.candidate_id,
                        vessel_id=c_var.vessel_id,
                        vessel_name=c_var.vessel_name,
                        cargo_id=c_var.cargo_id,
                        cargo_name=c_var.cargo_name,
                        is_selected=False,
                        selection_status=AssignmentSelectionStatus.MODEL_REJECTED,
                        start_time=c_var.start_time,
                        end_time=c_var.end_time,
                        expected_revenue=c_var.expected_revenue,
                        voyage_cost=c_var.voyage_cost,
                        gross_contribution=c_var.net_contribution,
                        idle_days_saved=c_var.idle_days_saved,
                        avoided_idle_cost=c_var.avoided_idle_cost,
                        ballast_distance_nm=c_var.ballast_distance_nm,
                        ballast_days=c_var.ballast_days,
                        voyage_days=voyage_days,
                        trade_off_reason_code=reason_code,
                        trade_off_explanation=reason_text,
                        assignment_metadata=c_var.raw_metadata,
                    )
                )

        # Classify cargo slack variables
        for s_var in self.registry.cargo_slack_vars:
            val = solution[s_var.index] if s_var.index < len(solution) else 0.0
            if val > 0.5 or s_var.cargo_id not in selected_by_cargo:
                unassigned.append(
                    UnassignedCargoResult(
                        cargo_id=s_var.cargo_id,
                        cargo_name=s_var.cargo_name,
                        unserved_penalty=s_var.unserved_penalty,
                        reason_code=TradeOffReasonCode.UNSERVED_OPTIONAL_REJECTION,
                        reason_explanation=TRADE_OFF_DESCRIPTIONS[TradeOffReasonCode.UNSERVED_OPTIONAL_REJECTION],
                    )
                )

        return selected, rejected, unassigned

    def _diagnose_rejection(
        self,
        c_var: CandidateVariable,
        selected_by_vessel: dict[int, list[CandidateVariable]],
        selected_by_cargo: dict[int, CandidateVariable],
    ) -> tuple[TradeOffReasonCode, str]:
        # 1. Was cargo served by another vessel?
        if c_var.cargo_id is not None and c_var.cargo_id in selected_by_cargo:
            winning_cand = selected_by_cargo[c_var.cargo_id]
            return (
                TradeOffReasonCode.CARGO_EXCLUSIVITY_LOST,
                f"Cargo parcel was allocated to {winning_cand.vessel_name} (Candidate {winning_cand.candidate_id}) yielding superior economic contribution (${winning_cand.net_contribution:,.0f} vs ${c_var.net_contribution:,.0f}).",
            )

        # 2. Did this vessel get allocated to an overlapping voyage?
        vessel_cands = selected_by_vessel.get(c_var.vessel_id, [])
        for winning_v_cand in vessel_cands:
            # Check overlap
            if max(c_var.start_time, winning_v_cand.start_time) < min(
                c_var.end_time, winning_v_cand.end_time
            ):
                return (
                    TradeOffReasonCode.VESSEL_TIMELINE_CONFLICT,
                    f"Vessel {c_var.vessel_name} was allocated to Candidate {winning_v_cand.candidate_id} (${winning_v_cand.net_contribution:,.0f}) which overlaps with this opportunity.",
                )

        # 3. Is net contribution negative?
        if c_var.net_contribution < 0:
            return (
                TradeOffReasonCode.NEGATIVE_ECONOMIC_CONTRIBUTION,
                f"Voyage expenses (${c_var.voyage_cost:,.0f}) exceed freight revenue (${c_var.expected_revenue:,.0f}); unassigned to avoid financial loss.",
            )

        # 4. Default: lower global net contribution
        return (
            TradeOffReasonCode.LOWER_NET_CONTRIBUTION,
            "Opportunity is feasible and profitable, but alternative fleet assignments generated a higher global portfolio contribution.",
        )

    def _compute_utilization(self, selected_assignments: list[AssignmentResult]) -> dict[str, Any]:
        all_vessel_ids = {c.vessel_id for c in self.registry.candidate_vars}
        assigned_vessel_ids = {a.vessel_id for a in selected_assignments}
        total_vessels = len(all_vessel_ids)
        assigned_vessels = len(assigned_vessel_ids)
        pct = (assigned_vessels / total_vessels * 100.0) if total_vessels > 0 else 0.0

        total_voyage_days = sum(a.voyage_days for a in selected_assignments)
        total_ballast_days = sum(a.ballast_days for a in selected_assignments)

        return {
            "total_vessels": total_vessels,
            "assigned_vessels": assigned_vessels,
            "idle_vessels": total_vessels - assigned_vessels,
            "utilization_pct": round(pct, 1),
            "total_voyage_days": round(total_voyage_days, 1),
            "total_ballast_days": round(total_ballast_days, 1),
            "assigned_vessel_ids": sorted(list(assigned_vessel_ids)),
        }

    def _summarize_constraints(
        self, constraints: list[LinearConstraintDefinition]
    ) -> dict[str, Any]:
        breakdown: dict[str, int] = {}
        for c in constraints:
            breakdown[c.constraint_type] = breakdown.get(c.constraint_type, 0) + 1

        return {
            "total_constraints": len(constraints),
            "breakdown": breakdown,
        }
