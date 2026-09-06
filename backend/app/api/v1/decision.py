"""
VesselOptima — Phase 10 Decision Intelligence Engine
FastAPI Router for Decision Intelligence Endpoints
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.engines.decision import (
    DecisionService,
    DecisionThresholds,
    DecisionWeights,
)
from app.schemas.decision import (
    DecisionEvaluateRequest,
    DecisionResultResponse,
    DecisionRunSummaryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/decision", tags=["Decision Intelligence"])


@router.post("/evaluate", response_model=DecisionResultResponse)
def evaluate_decision(
    req: DecisionEvaluateRequest,
    db: Session = Depends(get_db),
) -> Any:
    """
    Evaluates optimal allocation and risk intelligence to produce an auditable,
    deterministic decision recommendation with explicit reason codes and action guidance.
    """
    try:
        service = DecisionService(db)

        # Parse thresholds if provided
        thresholds = None
        if req.thresholds:
            weights = DecisionWeights()
            if req.thresholds.weights:
                weights = DecisionWeights(
                    economic=req.thresholds.weights.economic,
                    reliability=req.thresholds.weights.reliability,
                    robustness=req.thresholds.weights.robustness,
                    risk_penalty=req.thresholds.weights.risk_penalty,
                    schedule_penalty=req.thresholds.weights.schedule_penalty,
                )
            thresholds = DecisionThresholds(
                max_loss_prob_proceed=req.thresholds.max_loss_prob_proceed or 0.05,
                max_loss_prob_caution=req.thresholds.max_loss_prob_caution or 0.15,
                max_cvar95_downside_ratio_proceed=req.thresholds.max_cvar95_downside_ratio_proceed or 0.20,
                min_schedule_buffer_days=req.thresholds.min_schedule_buffer_days or 2.0,
                max_laycan_miss_prob_proceed=req.thresholds.max_laycan_miss_prob_proceed or 0.05,
                min_reliability_proceed=req.thresholds.min_reliability_proceed or 80.0,
                min_score_proceed=req.thresholds.min_score_proceed or 75.0,
                min_score_caution=req.thresholds.min_score_caution or 50.0,
                risk_aversion_lambda=req.thresholds.risk_aversion_lambda or 0.50,
                weights=weights,
            )

        result = service.evaluate_decision(
            optimization_run_id=req.optimization_run_id,
            scenario_run_id=req.scenario_run_id,
            risk_run_id=req.risk_run_id,
            thresholds=thresholds,
            strategy_flip_identified=req.strategy_flip_identified,
        )
        return result.to_dict()

    except Exception as e:
        logger.error(f"Error evaluating decision: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Decision evaluation failed: {str(e)}")


@router.get("/demo/{scenario_type}", response_model=DecisionResultResponse)
def get_demo_decision(
    scenario_type: str = "BASELINE",
    db: Session = Depends(get_db),
) -> Any:
    """
    Returns pre-calculated canonical institutional demo decisions.

    Available scenarios:
    - 'BASELINE': Standard balanced allocation -> PROCEED
    - 'STRATEGY_FLIP_A': High nominal return ($730k) with severe tail risk -> PROCEED_WITH_CAUTION
    - 'STRATEGY_FLIP_B': Moderate nominal return ($685k) with near-zero tail risk -> PROCEED
    - 'STRESS_TEST': Severe bunker price shock -> RECONSIDER
    """
    try:
        service = DecisionService(db)
        result = service.get_or_create_demo_decision(scenario_type=scenario_type)
        return result.to_dict()
    except Exception as e:
        logger.error(f"Error retrieving demo decision: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Demo retrieval failed: {str(e)}")


@router.get("/runs", response_model=List[DecisionRunSummaryResponse])
def list_decision_runs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> Any:
    """Lists historical decision evaluation runs."""
    try:
        service = DecisionService(db)
        return service.list_decision_runs(limit=limit)
    except Exception as e:
        logger.error(f"Error listing decision runs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list decision runs: {str(e)}")


@router.get("/runs/{run_id}", response_model=DecisionResultResponse)
def get_decision_run(
    run_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Retrieves full details of a past decision run by run_id."""
    try:
        service = DecisionService(db)
        result = service.get_decision_run(run_id=run_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Decision run '{run_id}' not found")
        return result.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving decision run: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve decision run: {str(e)}")


@router.get("/thresholds")
def get_decision_thresholds() -> Dict[str, Any]:
    """Returns default decision gating thresholds and weights."""
    t = DecisionThresholds()
    return {
        "max_loss_prob_proceed": t.max_loss_prob_proceed,
        "max_loss_prob_caution": t.max_loss_prob_caution,
        "max_cvar95_downside_ratio_proceed": t.max_cvar95_downside_ratio_proceed,
        "min_schedule_buffer_days": t.min_schedule_buffer_days,
        "max_laycan_miss_prob_proceed": t.max_laycan_miss_prob_proceed,
        "min_reliability_proceed": t.min_reliability_proceed,
        "min_score_proceed": t.min_score_proceed,
        "min_score_caution": t.min_score_caution,
        "risk_aversion_lambda": t.risk_aversion_lambda,
        "weights": {
            "economic": t.weights.economic,
            "reliability": t.weights.reliability,
            "robustness": t.weights.robustness,
            "risk_penalty": t.weights.risk_penalty,
            "schedule_penalty": t.weights.schedule_penalty,
        },
    }
