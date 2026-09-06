"""
VesselOptima — Phase 9: Risk Intelligence & Uncertainty REST API Endpoints
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.engines.risk.models import (
    CorrelationConfig,
    DistributionType,
    RiskSimulationConfig,
    RiskVariable,
)
from app.engines.risk.reason_codes import (
    ProvenanceType,
    RiskCategory,
)
from app.engines.risk.risk_service import RiskService
from app.models.domain import RiskMetric, RiskRun
from app.schemas.risk import (
    CorrelationConfigSchema,
    PlanRiskComparisonRequest,
    PlanRiskComparisonResponse,
    PlanRiskSimulationResponse,
    RiskSimulationRequest,
    RiskVariableSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/risk", tags=["Risk Intelligence & Uncertainty"])


@router.get("/config/defaults", response_model=Dict[str, Any])
def get_default_config() -> Dict[str, Any]:
    """
    Returns default institutional probability distributions, physical domain ranges,
    correlation matrices, and provenance citations for maritime uncertainty modeling.
    """
    cfg = RiskService.get_default_risk_config()
    return cfg.to_dict()


@router.post("/simulate", response_model=PlanRiskSimulationResponse)
def simulate_plan_risk(
    req: RiskSimulationRequest,
    db: Session = Depends(get_db),
) -> PlanRiskSimulationResponse:
    """
    Executes an offline vectorized Monte Carlo simulation (N = 1,000 to 100,000)
    for a given fleet allocation plan. Quantifies downside VaR, CVaR, loss probability,
    schedule fragility, and risk driver sensitivity.
    """
    try:
        service = RiskService(db=db)
        
        # Convert Pydantic schemas to domain models if custom variables provided
        custom_cfg = None
        if req.variables:
            vars_list = [
                RiskVariable(
                    variable_id=v.variable_id,
                    name=v.name,
                    category=RiskCategory(v.category) if v.category in [c.value for c in RiskCategory] else RiskCategory.OPERATIONAL,
                    distribution_type=DistributionType(v.distribution_type),
                    parameters=v.parameters,
                    baseline_value=v.baseline_value,
                    unit=v.unit,
                    provenance=ProvenanceType(v.provenance) if v.provenance in [p.value for p in ProvenanceType] else ProvenanceType.STATISTICAL_MODEL,
                    source_ref=v.source_ref,
                )
                for v in req.variables
            ]
            corrs_list = []
            if req.correlations:
                corrs_list = [
                    CorrelationConfig(
                        variable_ids=c.variable_ids,
                        matrix=c.matrix,
                    )
                    for c in req.correlations
                ]

            custom_cfg = RiskSimulationConfig(
                simulation_count=req.simulation_count,
                random_seed=req.random_seed,
                variables=vars_list,
                correlations=corrs_list,
                include_demurrage=req.include_demurrage,
                demurrage_daily_rate=req.demurrage_daily_rate,
            )
        else:
            custom_cfg = RiskService.get_default_risk_config()
            custom_cfg.simulation_count = req.simulation_count
            custom_cfg.random_seed = req.random_seed
            custom_cfg.include_demurrage = req.include_demurrage
            custom_cfg.demurrage_daily_rate = req.demurrage_daily_rate

        result = service.simulate_plan_risk(
            optimization_run_id=req.optimization_run_id,
            scenario_run_id=req.scenario_run_id,
            config=custom_cfg,
            persist=True,
        )
        return PlanRiskSimulationResponse(**result.to_dict())

    except Exception as e:
        logger.exception("Error executing risk simulation")
        raise HTTPException(status_code=400, detail=f"Risk simulation failed: {str(e)}")


@router.post("/compare", response_model=PlanRiskComparisonResponse)
def compare_plans(
    req: PlanRiskComparisonRequest,
    db: Session = Depends(get_db),
) -> PlanRiskComparisonResponse:
    """
    Compares the risk-reward profiles of two fleet allocation plans.
    Can also trigger the canonical Institutional Demonstration of the Critical Risk Flip.
    """
    try:
        service = RiskService(db=db)
        if req.is_demo_flip or not (req.optimization_run_id_a and req.optimization_run_id_b):
            comparison = service.get_critical_risk_flip_demo()
        else:
            asgns_a = service._get_plan_assignments(req.optimization_run_id_a)
            asgns_b = service._get_plan_assignments(req.optimization_run_id_b)
            comparison = service.compare_plans(
                plan_a_assignments=asgns_a,
                plan_b_assignments=asgns_b,
                plan_a_name=f"Plan ({req.optimization_run_id_a})",
                plan_b_name=f"Plan ({req.optimization_run_id_b})",
            )
        return PlanRiskComparisonResponse(**comparison.to_dict())
    except Exception as e:
        logger.exception("Error comparing plan risks")
        raise HTTPException(status_code=400, detail=f"Plan risk comparison failed: {str(e)}")


@router.get("/flip-demo", response_model=PlanRiskComparisonResponse)
def get_flip_demo(db: Session = Depends(get_db)) -> PlanRiskComparisonResponse:
    """
    Direct endpoint to retrieve the Critical Risk Flip demonstration case.
    """
    service = RiskService(db=db)
    comparison = service.get_critical_risk_flip_demo()
    return PlanRiskComparisonResponse(**comparison.to_dict())


@router.get("/runs", response_model=List[Dict[str, Any]])
def list_risk_runs(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Lists recent historical Monte Carlo risk simulation runs.
    """
    runs = (
        db.query(RiskRun)
        .order_by(RiskRun.id.desc())
        .limit(limit)
        .all()
    )
    result = []
    for r in runs:
        metric = r.metrics
        result.append(
            {
                "run_id": r.run_id,
                "optimization_run_id": r.optimization_run_id,
                "scenario_run_id": r.scenario_run_id,
                "simulation_count": r.simulation_count,
                "random_seed": r.random_seed,
                "status": r.status,
                "execution_time_seconds": r.execution_time_seconds,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "expected_contribution": metric.expected_contribution if metric else None,
                "var95_downside": metric.var95_downside if metric else None,
                "cvar95": metric.cvar95 if metric else None,
                "loss_probability": metric.loss_probability if metric else None,
                "plan_reliability_score": metric.plan_reliability_score if metric else None,
                "risk_tier": metric.risk_tier if metric else None,
            }
        )
    return result


@router.get("/runs/{run_id}", response_model=Dict[str, Any])
def get_risk_run(run_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retrieves full details, percentiles, assignment fragile points, and drivers for a specific risk run.
    """
    r = db.query(RiskRun).filter(RiskRun.run_id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail=f"Risk run '{run_id}' not found")

    metric = r.metrics
    assignments = [
        {
            "candidate_id": a.candidate_id,
            "vessel_id": a.vessel_id,
            "vessel_name": a.vessel.name if a.vessel else f"Vessel-{a.vessel_id}",
            "cargo_id": a.cargo_id,
            "cargo_name": a.cargo.name if a.cargo else (f"Cargo-{a.cargo_id}" if a.cargo_id else "Reposition"),
            "expected_net_contribution": a.expected_net_contribution,
            "contribution_std": a.contribution_std,
            "loss_probability": a.loss_probability,
            "cvar95": a.cvar95,
            "expected_arrival": a.expected_arrival.isoformat() if a.expected_arrival else None,
            "p90_arrival": a.p90_arrival.isoformat() if a.p90_arrival else None,
            "schedule_buffer_days": a.schedule_buffer_days,
            "laycan_miss_probability": a.laycan_miss_probability,
            "economic_survival_probability": a.economic_survival_probability,
            "schedule_survival_probability": a.schedule_survival_probability,
            "risk_tier": a.risk_tier,
        }
        for a in r.assignment_metrics
    ]
    drivers = [
        {
            "variable_id": d.variable_id,
            "name": d.variable_name,
            "category": d.category,
            "uncertainty_contribution_pct": d.uncertainty_contribution_pct,
            "sensitivity_coefficient": d.sensitivity_coefficient,
        }
        for d in r.drivers
    ]

    return {
        "run_id": r.run_id,
        "optimization_run_id": r.optimization_run_id,
        "scenario_run_id": r.scenario_run_id,
        "simulation_count": r.simulation_count,
        "random_seed": r.random_seed,
        "status": r.status,
        "execution_time_seconds": r.execution_time_seconds,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "metrics": {
            "expected_contribution": metric.expected_contribution if metric else 0.0,
            "contribution_std": metric.contribution_std if metric else 0.0,
            "percentiles": metric.percentiles if metric else {},
            "var90": metric.var90 if metric else 0.0,
            "var95": metric.var95 if metric else 0.0,
            "var95_downside": metric.var95_downside if metric else 0.0,
            "cvar90": metric.cvar90 if metric else 0.0,
            "cvar95": metric.cvar95 if metric else 0.0,
            "loss_probability": metric.loss_probability if metric else 0.0,
            "expected_loss": metric.expected_loss if metric else 0.0,
            "plan_reliability_score": metric.plan_reliability_score if metric else 0.0,
            "risk_tier": metric.risk_tier if metric else "MODERATE",
            "distribution_summary": metric.distribution_summary if metric else [],
        },
        "assignments": assignments,
        "drivers": drivers,
        "provenance_audit": (r.audit_trail or {}).get("provenance", []),
    }
