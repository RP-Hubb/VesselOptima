"""
VesselOptima — Feasibility API Router

Endpoints:
- POST /v1/feasibility/evaluate
- GET  /v1/feasibility/vessels/{cargo_id}
- GET  /v1/feasibility/cargos
- POST /v1/feasibility/matrix

Follows Section 27, 28, 29 of the Phase 4 Specification.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.engines.feasibility.service import FeasibilityService
from app.schemas.feasibility import (
    CargoRequirementItem,
    FeasibilityEvaluateRequest,
    FeasibilityMatrixRequest,
    FeasibilityResultResponse,
    FleetFeasibilityResponse,
    FleetVesselItem,
)

router = APIRouter(prefix="/feasibility", tags=["feasibility"])


@router.post("/evaluate", response_model=FeasibilityResultResponse)
def evaluate_feasibility(
    req: FeasibilityEvaluateRequest,
    db: Session = Depends(get_db),
):
    """
    Evaluates whether a specific vessel can perform a proposed cargo movement
    under operational, physical, and temporal constraints.
    """
    service = FeasibilityService(db=db)
    result = service.evaluate_assignment(
        cargo_id=req.cargo_id,
        vessel_id=req.vessel_id,
        route_id=req.route_id,
        persist=req.persist,
    )

    if result.get("primary_reason_code") == "CARGO_NOT_FOUND":
        raise HTTPException(status_code=404, detail=f"Cargo requirement {req.cargo_id} not found.")
    if result.get("primary_reason_code") == "VESSEL_NOT_FOUND":
        raise HTTPException(status_code=404, detail=f"Vessel {req.vessel_id} not found.")

    return result


@router.get("/vessels/{cargo_id}", response_model=FleetFeasibilityResponse)
def evaluate_candidate_fleet(
    cargo_id: int,
    route_id: Optional[int] = Query(None, description="Optional specific route ID"),
    db: Session = Depends(get_db),
):
    """
    Evaluates all candidate fleet vessels against a cargo requirement.
    Acts as a feasibility filter without economic ranking.
    """
    service = FeasibilityService(db=db)
    cargo = service._get_cargo(cargo_id)
    if not cargo:
        raise HTTPException(status_code=404, detail=f"Cargo requirement {cargo_id} not found.")

    fleet_results = service.evaluate_candidate_fleet(cargo_id=cargo_id, route_id=route_id)

    feasible_count = sum(1 for r in fleet_results if r["is_feasible"])
    infeasible_count = len(fleet_results) - feasible_count

    return {
        "cargo_id": cargo_id,
        "cargo_name": f"{cargo['commodity']} ({cargo['volume_mt']:,.0f} MT)",
        "total_vessels": len(fleet_results),
        "feasible_count": feasible_count,
        "infeasible_count": infeasible_count,
        "vessels": fleet_results,
        "provenance": service._get_provenance(),
        "evaluated_at": service._get_provenance().get("evaluated_at") or "",
    }


@router.get("/cargos", response_model=List[CargoRequirementItem])
def list_cargo_requirements(db: Session = Depends(get_db)):
    """
    Returns available active cargo requirements for feasibility selection.
    """
    service = FeasibilityService(db=db)
    cargos = service._list_all_cargos()
    items = []
    for c in cargos:
        orig = service._get_port(c["origin_port_id"])
        dest = service._get_port(c["destination_port_id"])
        items.append({
            "id": c["id"],
            "commodity": c["commodity"],
            "volume_mt": c["volume_mt"],
            "origin_port_id": c["origin_port_id"],
            "destination_port_id": c["destination_port_id"],
            "origin_port_name": orig.get("name", f"Port {c['origin_port_id']}"),
            "destination_port_name": dest.get("name", f"Port {c['destination_port_id']}"),
            "loading_window_start": c["loading_window_start"].isoformat(),
            "loading_window_end": c["loading_window_end"].isoformat(),
            "delivery_deadline": c["delivery_deadline"].isoformat(),
            "tolerance_pct": c["tolerance_pct"],
        })
    return items


@router.post("/matrix")
def evaluate_feasibility_matrix(
    req: FeasibilityMatrixRequest,
    db: Session = Depends(get_db),
):
    """
    Evaluates a 2D matrix of (Cargo Requirements x Candidate Vessels).
    """
    service = FeasibilityService(db=db)
    return service.evaluate_feasibility_matrix(
        cargo_ids=req.cargo_ids,
        vessel_ids=req.vessel_ids,
    )
