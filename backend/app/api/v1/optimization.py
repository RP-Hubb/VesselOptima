"""
VesselOptima — Phase 7: Optimization API Endpoints

Provides REST endpoints for triggering global MILP optimization runs,
inspecting assignment decisions, reviewing constraint audit logs, and comparing runs.
"""

from __future__ import annotations

from typing import Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.engines.optimization.service import OptimizationService
from app.schemas.optimization import (
    CompareRunsRequest,
    OptimizationResultResponse,
    OptimizationRunSummaryResponse,
    SolveFleetAssignmentRequest,
)

router = APIRouter(prefix="/optimization", tags=["Optimization Engine"])


@router.post("/solve", response_model=OptimizationResultResponse)
def solve_optimization(
    request: SolveFleetAssignmentRequest,
    db: Session = Depends(get_db),
) -> Any:
    """
    Executes global fleet assignment optimization across admissible Phase 6 candidates.
    Solves the MILP model using embedded HiGHS solver and returns full assignment decisions,
    trade-off explanations, and objective decompositions.
    """
    service = OptimizationService(db=db)
    result = service.solve_fleet_assignment(
        scenario=request.scenario,
        as_of_date=request.as_of_date,
        vessel_id=request.vessel_id,
        cargo_id=request.cargo_id,
        alpha_idle_weight=request.alpha_idle_weight,
        beta_ballast_penalty=request.beta_ballast_penalty,
        default_unserved_penalty=request.default_unserved_penalty,
        cargo_penalties=request.cargo_penalties,
        time_limit_seconds=request.time_limit_seconds,
        mip_gap=request.mip_gap,
        persist=request.persist,
    )
    return result.to_dict()


@router.get("/runs", response_model=list[OptimizationRunSummaryResponse])
def list_optimization_runs(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> Any:
    """Lists past optimization runs with high-level outcome metrics."""
    service = OptimizationService(db=db)
    return service.list_runs(limit=limit)


@router.get("/runs/{run_id}")
def get_optimization_run(
    run_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Retrieves full details of a specific optimization run, including assignments."""
    service = OptimizationService(db=db)
    data = service.get_run(run_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Optimization run '{run_id}' not found.")
    return data


@router.get("/runs/{run_id}/assignments")
def get_run_assignments(
    run_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Retrieves all candidate assignments (selected and rejected) for an optimization run."""
    service = OptimizationService(db=db)
    data = service.get_run(run_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Optimization run '{run_id}' not found.")
    return {
        "run_id": run_id,
        "assignments": data.get("assignments", []),
    }


@router.get("/runs/{run_id}/constraints")
def get_run_constraints(
    run_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Retrieves constraint summary breakdown for a specific optimization run."""
    service = OptimizationService(db=db)
    data = service.get_run(run_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Optimization run '{run_id}' not found.")
    result_summary = data.get("result_summary", {})
    return {
        "run_id": run_id,
        "constraint_summary": result_summary.get("constraint_summary", {}),
    }


@router.get("/runs/{run_id}/audit")
def get_run_audit_trail(
    run_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Retrieves the chronological solver execution audit trail for a specific run."""
    service = OptimizationService(db=db)
    data = service.get_run(run_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Optimization run '{run_id}' not found.")
    return {
        "run_id": run_id,
        "audit_trail": data.get("audit_trail", []),
    }


@router.post("/compare")
def compare_optimization_runs(
    request: CompareRunsRequest,
    db: Session = Depends(get_db),
) -> Any:
    """Compares objective values, revenues, costs, and assignments between two optimization runs."""
    service = OptimizationService(db=db)
    run_a = service.get_run(request.run_id_a)
    run_b = service.get_run(request.run_id_b)

    if not run_a:
        raise HTTPException(status_code=404, detail=f"Run '{request.run_id_a}' not found.")
    if not run_b:
        raise HTTPException(status_code=404, detail=f"Run '{request.run_id_b}' not found.")

    obj_a = run_a.get("objective_value", 0.0) or 0.0
    obj_b = run_b.get("objective_value", 0.0) or 0.0
    delta_obj = obj_b - obj_a

    return {
        "run_a": {
            "run_id": run_a["run_id"],
            "status": run_a["status"],
            "objective_value": obj_a,
            "total_revenue": run_a.get("total_revenue", 0.0),
            "total_cost": run_a.get("total_cost", 0.0),
            "total_contribution": run_a.get("total_contribution", 0.0),
            "assignments_count": len(run_a.get("assignments", [])),
        },
        "run_b": {
            "run_id": run_b["run_id"],
            "status": run_b["status"],
            "objective_value": obj_b,
            "total_revenue": run_b.get("total_revenue", 0.0),
            "total_cost": run_b.get("total_cost", 0.0),
            "total_contribution": run_b.get("total_contribution", 0.0),
            "assignments_count": len(run_b.get("assignments", [])),
        },
        "comparison": {
            "objective_delta": round(delta_obj, 2),
            "pct_improvement": round((delta_obj / abs(obj_a) * 100.0), 2) if obj_a != 0 else 0.0,
            "superior_run": run_b["run_id"] if delta_obj > 0 else (run_a["run_id"] if delta_obj < 0 else "TIED"),
        },
    }
