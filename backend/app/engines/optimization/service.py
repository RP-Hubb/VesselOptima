"""
VesselOptima — Phase 7: Master Optimization Service

Coordinates global fleet assignment and multi-period dispatching.
Consumes admissible Phase 6 candidates, enforces operational/commercial constraints,
invokes the pluggable HiGHS MILP solver, performs trade-off explainability,
and manages transactional persistence and auditability.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.engines.employment.service import EmploymentService, DEFAULT_AS_OF_DATE
from app.engines.optimization.model import OptimizationModel
from app.engines.optimization.objective import ObjectiveConfig
from app.engines.optimization.reason_codes import (
    AssignmentSelectionStatus,
    OptimizationStatus,
    TradeOffReasonCode,
)
from app.engines.optimization.result import (
    AssignmentResult,
    OptimizationResult,
    UnassignedCargoResult,
)
from app.engines.optimization.solver import BaseSolverAdapter, HiGHSSolverAdapter
from app.models.domain import (
    CargoParcel,
    OptimizationAssignment,
    OptimizationRun,
    OptimizationStatusEnum,
    RuntimeModeEnum,
    VesselCommitment,
    VesselProfile,
)

logger = logging.getLogger("vesseloptima.engines.optimization.service")


class OptimizationService:
    """
    Master service for Phase 7 MILP Optimization Engine.
    Strictly preserves the boundary:
        Phase 6 = Candidate Generation & Admissibility
        Phase 7 = Global Fleet Optimal Allocation
    """

    def __init__(
        self,
        db: Optional[Session] = None,
        solver: Optional[BaseSolverAdapter] = None,
        turnaround_hours: float = 24.0,
    ):
        self.db = db
        self.solver = solver or HiGHSSolverAdapter()
        self.turnaround_hours = turnaround_hours

    def solve_fleet_assignment(
        self,
        scenario: Optional[str] = "DEMO_FLEET",
        as_of_date: Optional[datetime] = None,
        vessel_id: Optional[int] = None,
        cargo_id: Optional[int] = None,
        alpha_idle_weight: float = 1.0,
        beta_ballast_penalty: float = 0.0,
        default_unserved_penalty: float = 0.0,
        cargo_penalties: Optional[dict[int, float]] = None,
        time_limit_seconds: Optional[float] = 30.0,
        mip_gap: float = 1e-4,
        persist: bool = True,
        custom_candidates: Optional[list[dict[str, Any]]] = None,
    ) -> OptimizationResult:
        """
        Executes end-to-end global fleet assignment optimization.
        Consumes Phase 6 candidates (or supplied custom/scenario candidates), formulates the MILP,
        solves via HiGHS, and optionally persists results.
        """
        eval_date = as_of_date or DEFAULT_AS_OF_DATE

        # 1. Obtain candidates
        upstream_rejected: list[dict[str, Any]] = []
        if custom_candidates is not None:
            candidates = [c for c in custom_candidates if c.get("status") == "FEASIBLE"]
            upstream_rejected = [c for c in custom_candidates if c.get("status") != "FEASIBLE"]
        elif scenario and scenario in ("DEMO_FLEET", "GREEDY_PROOF", "HIGH_BALLAST", "IDLE_FOCUS", "REJECTION"):
            candidates = self._get_scenario_candidates(scenario, eval_date)
        else:
            emp_service = EmploymentService(db=self.db)
            matrix_result = emp_service.get_candidates_matrix(
                vessel_id=vessel_id,
                cargo_id=cargo_id,
                ready_only=False,
                as_of_date=eval_date,
                persist=False,
            )
            raw_candidates = matrix_result.get("candidates", [])
            candidates = [c for c in raw_candidates if c.get("status") == "FEASIBLE"]
            upstream_rejected = [c for c in raw_candidates if c.get("status") != "FEASIBLE"]

        # 2. Build Objective Config
        obj_config = ObjectiveConfig(
            alpha_idle_weight=alpha_idle_weight,
            beta_ballast_penalty=beta_ballast_penalty,
            default_unserved_penalty=default_unserved_penalty,
            cargo_penalties=cargo_penalties or {},
        )

        # 3. Instantiate model
        model = OptimizationModel(
            solver=self.solver,
            objective_config=obj_config,
            turnaround_hours=self.turnaround_hours,
        )

        # 4. Track all cargoes for slack variables
        known_cargos: dict[int, str] = {}

        # 5. Populate candidate variables
        for cand in candidates:
            c_id = cand.get("cargo_id")
            c_name = cand.get("cargo_name", f"Cargo {c_id}")
            if c_id is not None:
                known_cargos[c_id] = c_name

            econ = cand.get("economics", {})
            timeline = cand.get("timeline", {})
            schedule = timeline.get("schedule", {})
            ballast = cand.get("ballast", {})

            # Dates
            start_dt = (
                datetime.fromisoformat(schedule["ballast_start"])
                if isinstance(schedule.get("ballast_start"), str)
                else schedule.get("ballast_start", eval_date)
            )
            end_dt = (
                datetime.fromisoformat(schedule["discharge_end"])
                if isinstance(schedule.get("discharge_end"), str)
                else schedule.get("discharge_end", start_dt)
            )

            # Economics
            rev = float(econ.get("expected_gross_revenue", 0.0))
            cost = float(econ.get("total_voyage_cost", 0.0))
            net_contrib = float(econ.get("net_economic_contribution", rev - cost))
            idle_days = float(econ.get("idle_days", 0.0))
            daily_rate = float(econ.get("daily_operating_cost", 7500.0))
            avoided_idle = idle_days * daily_rate

            model.add_candidate(
                candidate_id=cand["candidate_id"],
                vessel_id=cand["vessel_id"],
                vessel_name=cand.get("vessel_name", f"Vessel {cand['vessel_id']}"),
                cargo_id=c_id,
                cargo_name=c_name,
                start_time=start_dt,
                end_time=end_dt,
                expected_revenue=rev,
                voyage_cost=cost,
                net_contribution=net_contrib,
                idle_days_saved=idle_days,
                avoided_idle_cost=avoided_idle,
                ballast_distance_nm=float(ballast.get("ballast_distance_nm", 0.0)),
                ballast_days=float(ballast.get("ballast_days", 0.0)),
                origin_port_id=cand.get("origin_port_id"),
                destination_port_id=cand.get("destination_port_id"),
                employment_type=cand.get("employment_type", "ALTERNATIVE_EMPLOYMENT"),
                raw_metadata=cand,
            )

        # 6. Add cargo slack variables for optional cargo rejection
        for c_id, c_name in known_cargos.items():
            model.add_cargo(cargo_id=c_id, cargo_name=c_name)

        # 7. Add vessel commitments if DB is available
        commitments: dict[int, list[tuple[datetime, datetime]]] = {}
        if self.db:
            try:
                db_comms = self.db.query(VesselCommitment).filter(
                    VesselCommitment.status.in_(["CONFIRMED", "COMMITTED", "ACTIVE"])
                ).all()
                for comm in db_comms:
                    s_dt = comm.commitment_start if isinstance(comm.commitment_start, datetime) else datetime.combine(comm.commitment_start, datetime.min.time())
                    e_dt = comm.commitment_end if isinstance(comm.commitment_end, datetime) else (datetime.combine(comm.commitment_end, datetime.max.time()) if comm.commitment_end else s_dt + timedelta(days=30))
                    commitments.setdefault(comm.vessel_profile_id, []).append((s_dt, e_dt))
            except Exception as exc:
                logger.warning(f"Could not load vessel commitments from DB: {exc}")

        model.set_vessel_commitments(commitments)

        # 8. Solve MILP
        result = model.solve(
            time_limit_seconds=time_limit_seconds,
            mip_gap=mip_gap,
        )

        # 9. Append upstream rejected opportunities for total audit transparency
        for rej in upstream_rejected:
            result.rejected_opportunities.append(
                AssignmentResult(
                    candidate_id=rej["candidate_id"],
                    vessel_id=rej["vessel_id"],
                    vessel_name=rej.get("vessel_name", f"Vessel {rej['vessel_id']}"),
                    cargo_id=rej.get("cargo_id"),
                    cargo_name=rej.get("cargo_name", f"Cargo {rej.get('cargo_id')}"),
                    is_selected=False,
                    selection_status=AssignmentSelectionStatus.INFEASIBLE_UPSTREAM,
                    start_time=None,
                    end_time=None,
                    expected_revenue=0.0,
                    voyage_cost=0.0,
                    gross_contribution=0.0,
                    trade_off_reason_code=TradeOffReasonCode.COMMITMENT_PROTECTED,
                    trade_off_explanation=rej.get("primary_reason_description", "Rejected upstream by Phase 4/5/6 feasibility engine."),
                    assignment_metadata=rej,
                )
            )

        # 10. Persist if requested and DB available
        if persist and self.db:
            self._persist_result(result, as_of_date=eval_date)

        return result

    def _persist_result(self, result: OptimizationResult, as_of_date: datetime) -> None:
        """Persists the optimization run and assignment records to the database."""
        try:
            # Map status to DB enum
            db_status = OptimizationStatusEnum.OPTIMAL
            if result.status == OptimizationStatus.FEASIBLE:
                db_status = OptimizationStatusEnum.FEASIBLE
            elif result.status == OptimizationStatus.INFEASIBLE:
                db_status = OptimizationStatusEnum.INFEASIBLE
            elif result.status == OptimizationStatus.EMPTY_MODEL:
                db_status = OptimizationStatusEnum.EMPTY_MODEL
            elif result.status == OptimizationStatus.TIME_LIMIT:
                db_status = OptimizationStatusEnum.TIME_LIMIT
            elif result.status == OptimizationStatus.SOLVER_ERROR:
                db_status = OptimizationStatusEnum.SOLVER_ERROR
            elif result.status == OptimizationStatus.UNBOUNDED:
                db_status = OptimizationStatusEnum.UNBOUNDED

            decomp = result.decomposition

            opt_run = OptimizationRun(
                run_id=result.run_id,
                status=db_status,
                objective_value=result.objective_value,
                total_revenue=decomp.total_gross_revenue,
                total_cost=decomp.total_voyage_cost,
                total_contribution=decomp.total_net_contribution,
                avoided_idle_cost=decomp.total_avoided_idle_cost,
                solver_name=result.solver_metadata.get("solver", "HiGHS"),
                solver_version=result.solver_metadata.get("solver_version", "HiGHS"),
                solver_status=result.status.value,
                solve_time_seconds=result.solve_time_seconds,
                runtime_mode=RuntimeModeEnum.OFFLINE_DEMO,
                data_context_id="demo-v1",
                offline_package_id="demo-v1",
                objective_decomposition=decomp.to_dict(),
                solver_metadata=result.solver_metadata,
                result_summary={
                    "selected_count": len(result.selected_assignments),
                    "rejected_count": len(result.rejected_opportunities),
                    "unassigned_cargo_count": len(result.unassigned_cargos),
                    "vessel_utilization": result.vessel_utilization,
                    "constraint_summary": result.constraint_summary,
                },
                audit_trail=result.audit_trail,
            )
            self.db.add(opt_run)
            self.db.flush()

            # Add assignments
            all_assignments = result.selected_assignments + result.rejected_opportunities
            for assign in all_assignments:
                db_assign = OptimizationAssignment(
                    optimization_run_id=opt_run.id,
                    candidate_id=assign.candidate_id,
                    vessel_id=assign.vessel_id,
                    cargo_id=assign.cargo_id,
                    is_selected=assign.is_selected,
                    selection_status=assign.selection_status.value,
                    start_time=assign.start_time,
                    end_time=assign.end_time,
                    expected_revenue=assign.expected_revenue,
                    voyage_cost=assign.voyage_cost,
                    gross_contribution=assign.gross_contribution,
                    ballast_distance_nm=assign.ballast_distance_nm,
                    ballast_days=assign.ballast_days,
                    voyage_days=assign.voyage_days,
                    assignment_metadata=assign.assignment_metadata,
                    trade_off_notes=assign.trade_off_explanation,
                    runtime_mode=RuntimeModeEnum.OFFLINE_DEMO,
                )
                self.db.add(db_assign)

            self.db.commit()
            logger.info(f"Optimization run {result.run_id} persisted with {len(all_assignments)} assignments.")

        except Exception as exc:
            self.db.rollback()
            logger.error(f"Failed to persist optimization run {result.run_id}: {exc}", exc_info=True)

    def get_run(self, run_id: str) -> Optional[dict[str, Any]]:
        """Retrieves a persisted optimization run by run_id."""
        if not self.db:
            return None

        run = self.db.query(OptimizationRun).filter(OptimizationRun.run_id == run_id).first()
        if not run:
            return None

        assignments = self.db.query(OptimizationAssignment).filter(
            OptimizationAssignment.optimization_run_id == run.id
        ).all()

        return {
            "run_id": run.run_id,
            "status": run.status.value if hasattr(run.status, "value") else str(run.status),
            "objective_value": run.objective_value,
            "total_revenue": run.total_revenue,
            "total_cost": run.total_cost,
            "total_contribution": run.total_contribution,
            "avoided_idle_cost": run.avoided_idle_cost,
            "solver_name": run.solver_name,
            "solver_status": run.solver_status,
            "solve_time_seconds": run.solve_time_seconds,
            "objective_decomposition": run.objective_decomposition,
            "solver_metadata": run.solver_metadata,
            "result_summary": run.result_summary,
            "audit_trail": run.audit_trail,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "assignments": [
                {
                    "candidate_id": a.candidate_id,
                    "vessel_id": a.vessel_id,
                    "cargo_id": a.cargo_id,
                    "is_selected": a.is_selected,
                    "selection_status": a.selection_status,
                    "start_time": a.start_time.isoformat() if a.start_time else None,
                    "end_time": a.end_time.isoformat() if a.end_time else None,
                    "expected_revenue": a.expected_revenue,
                    "voyage_cost": a.voyage_cost,
                    "gross_contribution": a.gross_contribution,
                    "ballast_distance_nm": a.ballast_distance_nm,
                    "ballast_days": a.ballast_days,
                    "voyage_days": a.voyage_days,
                    "trade_off_notes": a.trade_off_notes,
                }
                for a in assignments
            ],
        }

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        """Lists recent optimization runs."""
        if not self.db:
            return []

        runs = (
            self.db.query(OptimizationRun)
            .order_by(OptimizationRun.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "run_id": r.run_id,
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "objective_value": r.objective_value,
                "total_revenue": r.total_revenue,
                "total_cost": r.total_cost,
                "total_contribution": r.total_contribution,
                "avoided_idle_cost": r.avoided_idle_cost,
                "solver_name": r.solver_name,
                "solve_time_seconds": r.solve_time_seconds,
                "result_summary": r.result_summary,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in runs
            if r.run_id
        ]

    def _get_scenario_candidates(self, scenario: str, eval_date: datetime) -> list[dict[str, Any]]:
        """Provides verified candidate sets for scenario evaluation and interactive demonstrations."""
        if scenario == "GREEDY_PROOF":
            return [
                {
                    "candidate_id": "A-C01",
                    "vessel_id": 1,
                    "vessel_name": "Vessel Alpha",
                    "cargo_id": 1,
                    "cargo_name": "Cargo 1 (Coal 75k MT)",
                    "status": "FEASIBLE",
                    "economics": {
                        "expected_gross_revenue": 500000.0,
                        "total_voyage_cost": 200000.0,
                        "net_economic_contribution": 300000.0,
                        "idle_days": 4.0,
                        "daily_operating_cost": 7500.0,
                    },
                    "timeline": {
                        "schedule": {
                            "ballast_start": eval_date.isoformat(),
                            "discharge_end": (eval_date + timedelta(days=14)).isoformat(),
                        }
                    },
                    "ballast": {"ballast_distance_nm": 450.0, "ballast_days": 1.5},
                },
                {
                    "candidate_id": "A-C02",
                    "vessel_id": 1,
                    "vessel_name": "Vessel Alpha",
                    "cargo_id": 2,
                    "cargo_name": "Cargo 2 (Iron Ore 165k MT)",
                    "status": "FEASIBLE",
                    "economics": {
                        "expected_gross_revenue": 480000.0,
                        "total_voyage_cost": 200000.0,
                        "net_economic_contribution": 280000.0,
                        "idle_days": 3.0,
                        "daily_operating_cost": 7500.0,
                    },
                    "timeline": {
                        "schedule": {
                            "ballast_start": eval_date.isoformat(),
                            "discharge_end": (eval_date + timedelta(days=15)).isoformat(),
                        }
                    },
                    "ballast": {"ballast_distance_nm": 600.0, "ballast_days": 2.0},
                },
                {
                    "candidate_id": "B-C01",
                    "vessel_id": 2,
                    "vessel_name": "Vessel Beta",
                    "cargo_id": 1,
                    "cargo_name": "Cargo 1 (Coal 75k MT)",
                    "status": "FEASIBLE",
                    "economics": {
                        "expected_gross_revenue": 490000.0,
                        "total_voyage_cost": 200000.0,
                        "net_economic_contribution": 290000.0,
                        "idle_days": 5.0,
                        "daily_operating_cost": 7500.0,
                    },
                    "timeline": {
                        "schedule": {
                            "ballast_start": eval_date.isoformat(),
                            "discharge_end": (eval_date + timedelta(days=14)).isoformat(),
                        }
                    },
                    "ballast": {"ballast_distance_nm": 350.0, "ballast_days": 1.2},
                },
                {
                    "candidate_id": "B-C02",
                    "vessel_id": 2,
                    "vessel_name": "Vessel Beta",
                    "cargo_id": 2,
                    "cargo_name": "Cargo 2 (Iron Ore 165k MT)",
                    "status": "FEASIBLE",
                    "economics": {
                        "expected_gross_revenue": 300000.0,
                        "total_voyage_cost": 200000.0,
                        "net_economic_contribution": 100000.0,
                        "idle_days": 2.0,
                        "daily_operating_cost": 7500.0,
                    },
                    "timeline": {
                        "schedule": {
                            "ballast_start": eval_date.isoformat(),
                            "discharge_end": (eval_date + timedelta(days=15)).isoformat(),
                        }
                    },
                    "ballast": {"ballast_distance_nm": 900.0, "ballast_days": 3.0},
                },
            ]

        # Default DEMO_FLEET canonical fleet candidates
        return [
            {
                "candidate_id": "EMP-V10-C01-PANAMAX",
                "vessel_id": 10,
                "vessel_name": "VO Mahanadi Breeze (Panamax)",
                "cargo_id": 1,
                "cargo_name": "Newcastle -> Paradip Coal (75,000 MT)",
                "status": "FEASIBLE",
                "economics": {
                    "expected_gross_revenue": 1450000.0,
                    "total_voyage_cost": 980000.0,
                    "net_economic_contribution": 470000.0,
                    "idle_days": 6.0,
                    "daily_operating_cost": 10500.0,
                },
                "timeline": {
                    "schedule": {
                        "ballast_start": (eval_date + timedelta(days=2)).isoformat(),
                        "discharge_end": (eval_date + timedelta(days=24)).isoformat(),
                    }
                },
                "ballast": {"ballast_distance_nm": 1150.0, "ballast_days": 3.5},
            },
            {
                "candidate_id": "EMP-V12-C01-PANAMAX",
                "vessel_id": 12,
                "vessel_name": "Ocean Navigator (Panamax)",
                "cargo_id": 1,
                "cargo_name": "Newcastle -> Paradip Coal (75,000 MT)",
                "status": "FEASIBLE",
                "economics": {
                    "expected_gross_revenue": 1450000.0,
                    "total_voyage_cost": 1020000.0,
                    "net_economic_contribution": 430000.0,
                    "idle_days": 4.0,
                    "daily_operating_cost": 10200.0,
                },
                "timeline": {
                    "schedule": {
                        "ballast_start": (eval_date + timedelta(days=1)).isoformat(),
                        "discharge_end": (eval_date + timedelta(days=25)).isoformat(),
                    }
                },
                "ballast": {"ballast_distance_nm": 1720.0, "ballast_days": 5.2},
            },
            {
                "candidate_id": "EMP-V18-C02-CAPESIZE",
                "vessel_id": 18,
                "vessel_name": "Pilbara Iron (Capesize)",
                "cargo_id": 2,
                "cargo_name": "Port Hedland -> Dhamra Iron Ore (165,000 MT)",
                "status": "FEASIBLE",
                "economics": {
                    "expected_gross_revenue": 2800000.0,
                    "total_voyage_cost": 1920000.0,
                    "net_economic_contribution": 880000.0,
                    "idle_days": 8.0,
                    "daily_operating_cost": 13800.0,
                },
                "timeline": {
                    "schedule": {
                        "ballast_start": (eval_date + timedelta(days=3)).isoformat(),
                        "discharge_end": (eval_date + timedelta(days=28)).isoformat(),
                    }
                },
                "ballast": {"ballast_distance_nm": 700.0, "ballast_days": 2.1},
            },
            {
                "candidate_id": "EMP-V17-C02-CAPESIZE",
                "vessel_id": 17,
                "vessel_name": "VO Sagar Samrat (Capesize)",
                "cargo_id": 2,
                "cargo_name": "Port Hedland -> Dhamra Iron Ore (165,000 MT)",
                "status": "FEASIBLE",
                "economics": {
                    "expected_gross_revenue": 2800000.0,
                    "total_voyage_cost": 2010000.0,
                    "net_economic_contribution": 790000.0,
                    "idle_days": 5.0,
                    "daily_operating_cost": 14000.0,
                },
                "timeline": {
                    "schedule": {
                        "ballast_start": (eval_date + timedelta(days=1)).isoformat(),
                        "discharge_end": (eval_date + timedelta(days=30)).isoformat(),
                    }
                },
                "ballast": {"ballast_distance_nm": 2240.0, "ballast_days": 6.8},
            },
            {
                "candidate_id": "EMP-V05-C03-SUPRAMAX",
                "vessel_id": 5,
                "vessel_name": "VO Indus Pioneer (Supramax)",
                "cargo_id": 3,
                "cargo_name": "Samarinda -> Krishnapatnam Coal (55,000 MT)",
                "status": "FEASIBLE",
                "economics": {
                    "expected_gross_revenue": 880000.0,
                    "total_voyage_cost": 590000.0,
                    "net_economic_contribution": 290000.0,
                    "idle_days": 7.0,
                    "daily_operating_cost": 8500.0,
                },
                "timeline": {
                    "schedule": {
                        "ballast_start": (eval_date + timedelta(days=4)).isoformat(),
                        "discharge_end": (eval_date + timedelta(days=22)).isoformat(),
                    }
                },
                "ballast": {"ballast_distance_nm": 650.0, "ballast_days": 2.0},
            },
            {
                "candidate_id": "EMP-V01-C04-HANDY",
                "vessel_id": 1,
                "vessel_name": "VO Amber Leader (Handysize)",
                "cargo_id": 4,
                "cargo_name": "Tuticorin -> Chittagong Bulk (32,000 MT)",
                "status": "FEASIBLE",
                "economics": {
                    "expected_gross_revenue": 480000.0,
                    "total_voyage_cost": 340000.0,
                    "net_economic_contribution": 140000.0,
                    "idle_days": 5.0,
                    "daily_operating_cost": 7500.0,
                },
                "timeline": {
                    "schedule": {
                        "ballast_start": (eval_date + timedelta(days=5)).isoformat(),
                        "discharge_end": (eval_date + timedelta(days=18)).isoformat(),
                    }
                },
                "ballast": {"ballast_distance_nm": 580.0, "ballast_days": 1.8},
            },
            {
                "candidate_id": "EMP-V10-C03-SUPRAMAX-CONFLICT",
                "vessel_id": 10,
                "vessel_name": "VO Mahanadi Breeze (Panamax)",
                "cargo_id": 3,
                "cargo_name": "Samarinda -> Krishnapatnam Coal (55,000 MT)",
                "status": "FEASIBLE",
                "economics": {
                    "expected_gross_revenue": 880000.0,
                    "total_voyage_cost": 650000.0,
                    "net_economic_contribution": 230000.0,
                    "idle_days": 2.0,
                    "daily_operating_cost": 10500.0,
                },
                "timeline": {
                    "schedule": {
                        "ballast_start": (eval_date + timedelta(days=3)).isoformat(),
                        "discharge_end": (eval_date + timedelta(days=20)).isoformat(),
                    }
                },
                "ballast": {"ballast_distance_nm": 950.0, "ballast_days": 2.9},
            },
            {
                "candidate_id": "EMP-V12-C04-UNPROFITABLE",
                "vessel_id": 12,
                "vessel_name": "Ocean Navigator (Panamax)",
                "cargo_id": 4,
                "cargo_name": "Tuticorin -> Chittagong Bulk (32,000 MT)",
                "status": "FEASIBLE",
                "economics": {
                    "expected_gross_revenue": 480000.0,
                    "total_voyage_cost": 580000.0,
                    "net_economic_contribution": -100000.0,
                    "idle_days": 1.0,
                    "daily_operating_cost": 10200.0,
                },
                "timeline": {
                    "schedule": {
                        "ballast_start": (eval_date + timedelta(days=6)).isoformat(),
                        "discharge_end": (eval_date + timedelta(days=21)).isoformat(),
                    }
                },
                "ballast": {"ballast_distance_nm": 1100.0, "ballast_days": 3.4},
            },
        ]
