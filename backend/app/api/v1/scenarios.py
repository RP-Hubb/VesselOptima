"""
VesselOptima — Phase 8: Scenario Analysis & What-If REST API Router

Provides institutional endpoints for scenario simulation, batch execution,
sensitivity curve generation, and robustness analysis.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.engines.scenarios.config import ScenarioConfig, ScenarioPresets, ScenarioType
from app.engines.scenarios.service import ScenarioService
from app.models.domain import ScenarioEvaluation, ScenarioSensitivityRun
from app.schemas.scenario import (
    BatchScenarioRequest,
    BatchScenarioResponse,
    RobustnessResponse,
    ScenarioComparisonResponse,
    ScenarioConfigPayload,
    SensitivitySweepRequest,
    SensitivitySweepResponse,
)

logger = logging.getLogger("vesseloptima.api.v1.scenarios")
router = APIRouter(prefix="/scenarios", tags=["Phase 8: Scenarios & Sensitivity"])


def _payload_to_config(p: ScenarioConfigPayload) -> ScenarioConfig:
    scen_id = p.scenario_id or f"SCEN-{p.name.upper().replace(' ', '-')[:16]}"
    raw_type = p.scenario_type or "CUSTOM"
    try:
        stype = ScenarioType(raw_type)
    except ValueError:
        stype = ScenarioType.CUSTOM

    return ScenarioConfig(
        scenario_id=scen_id,
        name=p.name,
        description=p.description or "",
        scenario_type=stype,
        baseline_scenario=p.baseline_scenario or "DEMO_FLEET",
        freight_multiplier=p.freight_multiplier,
        bunker_multiplier=p.bunker_multiplier,
        idle_cost_multiplier=p.idle_cost_multiplier,
        port_cost_multiplier=p.port_cost_multiplier,
        laycan_adjustment_days=p.laycan_adjustment_days,
        excluded_vessel_ids=p.excluded_vessel_ids,
        vessel_delay_days={int(k): v for k, v in p.vessel_delay_days.items()},
        alpha_idle_weight=p.alpha_idle_weight,
        beta_ballast_penalty=p.beta_ballast_penalty,
        default_unserved_penalty=p.default_unserved_penalty,
    )


@router.get("/presets", response_model=List[Dict[str, Any]])
def get_scenario_presets() -> List[Dict[str, Any]]:
    """Returns standard institutional preset scenarios."""
    presets = ScenarioPresets.all_presets()
    return [p.to_dict() for p in presets]


@router.post("/run", response_model=ScenarioComparisonResponse)
def run_scenario(
    payload: ScenarioConfigPayload,
    persist: bool = Query(default=True, description="Persist evaluation to database"),
    db: Session = Depends(get_db),
) -> ScenarioComparisonResponse:
    """
    Executes a what-if scenario:
    1. Transforms candidates via copy-on-scenario semantics.
    2. Revalidates temporal boundaries.
    3. Solves through Phase 7 HiGHS MILP.
    4. Computes baseline vs scenario deltas.
    """
    try:
        service = ScenarioService(db=db)
        config = _payload_to_config(payload)
        comparison = service.run_scenario(config=config, persist=persist)
        return ScenarioComparisonResponse(**comparison.to_dict())
    except Exception as ex:
        logger.error("Error executing scenario %s: %s", payload.name, ex, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scenario execution failed: {str(ex)}",
        )


@router.post("/batch", response_model=BatchScenarioResponse)
def run_batch_scenarios(
    payload: BatchScenarioRequest,
    persist: bool = Query(default=True, description="Persist evaluations to database"),
    db: Session = Depends(get_db),
) -> BatchScenarioResponse:
    """
    Executes a batch of scenarios against an immutable shared baseline.
    """
    try:
        service = ScenarioService(db=db)
        configs = [_payload_to_config(p) for p in payload.scenarios]
        comparisons = service.run_batch_scenarios(configs=configs, persist=persist)
        return BatchScenarioResponse(
            total_scenarios_executed=len(comparisons),
            comparisons=[ScenarioComparisonResponse(**c.to_dict()) for c in comparisons],
        )
    except Exception as ex:
        logger.error("Error executing batch scenarios: %s", ex, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch execution failed: {str(ex)}",
        )


@router.post("/sensitivity", response_model=SensitivitySweepResponse)
def run_sensitivity_sweep(
    payload: SensitivitySweepRequest,
    persist: bool = Query(default=True, description="Persist sweep results to database"),
    db: Session = Depends(get_db),
) -> SensitivitySweepResponse:
    """
    Executes a one-variable-at-a-time (OVAT) sensitivity sweep and detects break-even thresholds.
    """
    try:
        service = ScenarioService(db=db)
        base_cfg = _payload_to_config(payload.base_config) if payload.base_config else None
        res = service.run_sensitivity_sweep(
            parameter_name=payload.parameter_name,
            sweep_values=payload.sweep_values,
            base_config=base_cfg,
            persist=persist,
        )
        return SensitivitySweepResponse(**res.to_dict())
    except Exception as ex:
        logger.error("Error executing sensitivity sweep for %s: %s", payload.parameter_name, ex, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sensitivity sweep failed: {str(ex)}",
        )


@router.get("/robustness", response_model=RobustnessResponse)
def evaluate_robustness(
    db: Session = Depends(get_db),
) -> RobustnessResponse:
    """
    Evaluates baseline allocation stability across an ensemble of heterogeneous stress scenarios.
    """
    try:
        service = ScenarioService(db=db)
        res = service.evaluate_ensemble_robustness()
        return RobustnessResponse(**res.to_dict())
    except Exception as ex:
        logger.error("Error evaluating ensemble robustness: %s", ex, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Robustness evaluation failed: {str(ex)}",
        )


@router.get("/evaluations", response_model=List[Dict[str, Any]])
def list_scenario_evaluations(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Lists past scenario evaluations stored in the database."""
    records = db.query(ScenarioEvaluation).order_by(ScenarioEvaluation.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "scenario_code": r.scenario_code,
            "name": r.name,
            "description": r.description,
            "scenario_type": r.scenario_type,
            "baseline_run_id": r.baseline_run_id,
            "scenario_run_id": r.scenario_run_id,
            "parameters": r.parameters,
            "comparison_metrics": r.comparison_metrics,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


@router.get("/evaluations/{evaluation_id}", response_model=Dict[str, Any])
def get_scenario_evaluation(
    evaluation_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieves detailed delta records for a specific scenario evaluation."""
    rec = db.query(ScenarioEvaluation).filter(ScenarioEvaluation.id == evaluation_id).first()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ScenarioEvaluation with id {evaluation_id} not found.",
        )
    return {
        "id": rec.id,
        "scenario_code": rec.scenario_code,
        "name": rec.name,
        "description": rec.description,
        "scenario_type": rec.scenario_type,
        "baseline_run_id": rec.baseline_run_id,
        "scenario_run_id": rec.scenario_run_id,
        "parameters": rec.parameters,
        "config_hash": rec.config_hash,
        "comparison_metrics": rec.comparison_metrics,
        "assignment_deltas": rec.assignment_deltas,
        "cargo_deltas": rec.cargo_deltas,
        "audit_trail": rec.audit_trail,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
    }
