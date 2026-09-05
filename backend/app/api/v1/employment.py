"""VesselOptima — API Endpoints: Idle Management & Alternative Employment Engine

Strict Architectural Boundary:
    Candidate Generation != Global Allocation
    Idle Management != Fleet Optimization
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import get_db
from app.engines.employment.service import EmploymentService
from app.schemas.employment import (
    CandidateCompareRequest,
    CandidateCompareResponse,
    CandidateMatrixRequest,
    CandidateMatrixResponse,
    EmploymentCandidateRequest,
    EmploymentCandidateResponse,
    FleetEmploymentOverviewResponse,
    FleetIdleResponse,
    OpportunitiesResponse,
    VesselEmploymentStatusResponse,
    VesselTimelineResponse,
)

logger = get_logger("api.v1.employment")

router = APIRouter(prefix="/employment", tags=["employment"])


@router.get("/overview", response_model=FleetEmploymentOverviewResponse)
def get_fleet_employment_overview(
    as_of_date: Optional[str] = Query(None, description="Evaluation anchor date (ISO format YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"),
    db: Session = Depends(get_db),
):
    """Returns high-level fleet employment status overview."""
    service = EmploymentService(db=db)
    eval_dt = datetime.fromisoformat(as_of_date) if as_of_date else None
    try:
        return service.get_fleet_employment_overview(as_of_date=eval_dt)
    except Exception as e:
        logger.error(f"Fleet employment overview failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vessels", response_model=List[VesselEmploymentStatusResponse])
def get_vessels_employment_status(
    as_of_date: Optional[str] = Query(None, description="Evaluation anchor date (ISO format)"),
    db: Session = Depends(get_db),
):
    """Returns availability and commitment status for all fleet vessels."""
    service = EmploymentService(db=db)
    eval_dt = datetime.fromisoformat(as_of_date) if as_of_date else None
    try:
        vessels = service._get_all_vessels()
        statuses = []
        for v in vessels:
            stat = service.get_vessel_employment_status(vessel_id=v["id"], as_of_date=eval_dt)
            if stat:
                statuses.append(stat)
        return statuses
    except Exception as e:
        logger.error(f"Vessel status resolution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vessels/{vessel_id}/timeline", response_model=VesselTimelineResponse)
def get_vessel_timeline(
    vessel_id: int,
    horizon_days: int = Query(45, description="Timeline horizon in days"),
    as_of_date: Optional[str] = Query(None, description="Evaluation anchor date (ISO format)"),
    db: Session = Depends(get_db),
):
    """Returns structured chronological timeline events for a vessel."""
    service = EmploymentService(db=db)
    eval_dt = datetime.fromisoformat(as_of_date) if as_of_date else None
    try:
        res = service.get_vessel_timeline(vessel_id=vessel_id, as_of_date=eval_dt, horizon_days=horizon_days)
        if not res.get("events") and not service._get_vessel(vessel_id):
            raise HTTPException(status_code=404, detail=f"Vessel {vessel_id} not found")
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Timeline generation failed for vessel {vessel_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/opportunities", response_model=OpportunitiesResponse)
def get_opportunities(db: Session = Depends(get_db)):
    """Returns canonical employment opportunities (cargo demand requirements)."""
    service = EmploymentService(db=db)
    try:
        opps = service.get_all_opportunities()
        return {"opportunities": opps, "total_count": len(opps)}
    except Exception as e:
        logger.error(f"Failed to fetch opportunities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/idle", response_model=FleetIdleResponse)
def get_fleet_idle_assessments(
    as_of_date: Optional[str] = Query(None, description="Evaluation anchor date (ISO format)"),
    db: Session = Depends(get_db),
):
    """Evaluates idle state across all fleet vessels and holding cost exposures."""
    service = EmploymentService(db=db)
    eval_dt = datetime.fromisoformat(as_of_date) if as_of_date else None
    try:
        return service.get_all_idle_assessments(as_of_date=eval_dt)
    except Exception as e:
        logger.error(f"Fleet idle assessment failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluate", response_model=EmploymentCandidateResponse)
def evaluate_candidate(
    request: EmploymentCandidateRequest,
    db: Session = Depends(get_db),
):
    """
    Evaluates a specific vessel-cargo alternative employment candidate.
    Integrates Ballast, Feasibility, Procurement, Timeline, and Economics.
    """
    service = EmploymentService(db=db)
    eval_dt = datetime.fromisoformat(request.as_of_date) if request.as_of_date else None
    try:
        result = service.evaluate_employment_candidate(
            vessel_id=request.vessel_id,
            cargo_id=request.cargo_id,
            as_of_date=eval_dt,
            employment_type=request.employment_type,
            procurement_profile_id=request.procurement_profile_id,
            persist=request.persist,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Candidate evaluation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/candidates", response_model=CandidateMatrixResponse)
def get_candidates(
    request: CandidateMatrixRequest,
    db: Session = Depends(get_db),
):
    """
    Generates alternative employment candidate options across fleet and opportunities.
    Does NOT rank or perform global allocation.
    """
    service = EmploymentService(db=db)
    eval_dt = datetime.fromisoformat(request.as_of_date) if request.as_of_date else None
    try:
        return service.get_candidates_matrix(
            vessel_id=request.vessel_id,
            cargo_id=request.cargo_id,
            ready_only=request.ready_only,
            as_of_date=eval_dt,
            persist=request.persist,
        )
    except Exception as e:
        logger.error(f"Candidates matrix generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare", response_model=CandidateCompareResponse)
def compare_candidates(
    request: CandidateCompareRequest,
    db: Session = Depends(get_db),
):
    """
    Produces side-by-side comparison of alternative employment candidates.
    Strictly non-ranking advisory output; no vessel is marked winner.
    """
    service = EmploymentService(db=db)
    eval_dt = datetime.fromisoformat(request.as_of_date) if request.as_of_date else None
    try:
        return service.compare_candidates(
            vessel_id=request.vessel_id,
            cargo_id=request.cargo_id,
            as_of_date=eval_dt,
        )
    except Exception as e:
        logger.error(f"Candidate comparison failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
