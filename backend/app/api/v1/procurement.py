"""
VesselOptima — API Endpoints: Dynamic Procurement Strategy Engine
Follows Section 17 of the Phase 5 Specification.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import get_db
from app.engines.procurement.lead_time import DEFAULT_PROFILES
from app.engines.procurement.service import ProcurementService
from app.engines.procurement.strategies import STRATEGY_DEFINITIONS
from app.schemas.procurement import (
    ProcurementCompareRequest,
    ProcurementCompareResponse,
    ProcurementProfileSchema,
    ProcurementProfileUpdateSchema,
    StrategyDefinitionSchema,
    StrategyEvaluationSchema,
)

logger = get_logger("api.v1.procurement")

router = APIRouter(prefix="/procurement", tags=["procurement"])


@router.get("/config", response_model=List[ProcurementProfileSchema])
def get_procurement_profiles(db: Session = Depends(get_db)):
    """Returns active procurement lead-time profiles."""
    service = ProcurementService(db=db)
    return service.get_profiles()


@router.put("/config", response_model=ProcurementProfileSchema)
def update_procurement_profile(
    body: ProcurementProfileUpdateSchema,
    db: Session = Depends(get_db),
):
    """Updates or adds custom procurement profile configurations."""
    service = ProcurementService(db=db)
    updated = service.save_custom_profile(body.model_dump(exclude_unset=True))
    return updated


@router.get("/strategies", response_model=List[StrategyDefinitionSchema])
def get_supported_strategies():
    """Returns definitions of all supported procurement strategy structures."""
    return [
        {
            "strategy_type": s.strategy_type,
            "name": s.name,
            "description": s.description,
            "duration_days": s.duration_days,
            "voyage_count": s.voyage_count,
            "discount_factor": s.discount_factor,
            "market_exposure": s.market_exposure,
            "commitment_level": s.commitment_level,
        }
        for s in STRATEGY_DEFINITIONS.values()
    ]


@router.get("/candidates/{cargo_id}", response_model=ProcurementCompareResponse)
def get_cargo_procurement_candidates(
    cargo_id: int,
    profile_id: Optional[str] = Query("STANDARD_COMMERCIAL", description="Procurement profile identifier"),
    as_of_date: Optional[str] = Query("2026-09-01", description="Evaluation anchor date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    """Evaluates candidate procurement strategies for a cargo requirement."""
    service = ProcurementService(db=db)
    eval_date = date.fromisoformat(as_of_date) if as_of_date else None

    try:
        results = service.evaluate_cargo_strategies(
            cargo_id=cargo_id,
            profile_id=profile_id,
            as_of_date=eval_date,
            persist=False,
        )
        return results
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Procurement candidate evaluation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Procurement candidate evaluation failed: {str(e)}")


@router.post("/compare", response_model=ProcurementCompareResponse)
def compare_procurement_strategies(
    request: ProcurementCompareRequest,
    db: Session = Depends(get_db),
):
    """
    Compares candidate strategies (SPOT, SHORT_TERM, MEDIUM_TERM, MULTI_VOYAGE).
    Produces transparent evidence with zero hidden economic ranking.
    """
    service = ProcurementService(db=db)
    eval_date = date.fromisoformat(request.as_of_date) if request.as_of_date else None

    try:
        results = service.evaluate_cargo_strategies(
            cargo_id=request.cargo_id,
            profile_id=request.profile_id,
            as_of_date=eval_date,
            strategy_types=request.strategy_types,
            custom_stages=request.custom_stages,
            persist=request.persist,
        )
        return results
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Procurement strategy comparison failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Procurement strategy comparison failed: {str(e)}")


@router.post("/evaluate", response_model=StrategyEvaluationSchema)
def evaluate_single_strategy(
    request: ProcurementCompareRequest,
    strategy_type: str = Query("SPOT", description="Strategy type to evaluate"),
    db: Session = Depends(get_db),
):
    """Evaluates a single procurement strategy candidate."""
    service = ProcurementService(db=db)
    eval_date = date.fromisoformat(request.as_of_date) if request.as_of_date else None

    try:
        results = service.evaluate_cargo_strategies(
            cargo_id=request.cargo_id,
            profile_id=request.profile_id,
            as_of_date=eval_date,
            strategy_types=[strategy_type],
            custom_stages=request.custom_stages,
            persist=request.persist,
        )
        if not results.get("strategies"):
            raise HTTPException(status_code=400, detail=f"Failed to evaluate strategy {strategy_type}")
        return results["strategies"][0]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Single strategy evaluation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Single strategy evaluation failed: {str(e)}")
