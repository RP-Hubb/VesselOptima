"""
VesselOptima — Phase 9: Pydantic Schemas for Risk Intelligence & Uncertainty
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RiskVariableSchema(BaseModel):
    variable_id: str
    name: str
    category: str
    distribution_type: str
    parameters: Dict[str, float]
    baseline_value: Optional[float] = None
    unit: str = ""
    provenance: str = "STATISTICAL_MODEL"
    source_ref: Optional[str] = None


class CorrelationConfigSchema(BaseModel):
    variable_ids: List[str]
    matrix: List[List[float]]


class RiskSimulationRequest(BaseModel):
    optimization_run_id: str = "BASELINE_OPTIMAL"
    scenario_run_id: Optional[str] = None
    simulation_count: int = Field(default=5000, ge=100, le=100000)
    random_seed: int = 42
    variables: Optional[List[RiskVariableSchema]] = None
    correlations: Optional[List[CorrelationConfigSchema]] = None
    include_demurrage: bool = True
    demurrage_daily_rate: float = 15000.0


class AssignmentRiskResponse(BaseModel):
    candidate_id: str
    vessel_id: int
    vessel_name: str
    cargo_id: Optional[int]
    cargo_name: str
    expected_revenue: float
    expected_cost: float
    expected_net_contribution: float
    contribution_std: float
    loss_probability: float
    var95_downside: float
    cvar95: float
    expected_arrival: str
    p50_arrival: str
    p90_arrival: str
    p95_arrival: str
    laycan_end: str
    schedule_buffer_days: float
    laycan_miss_probability: float
    economic_survival_probability: float
    schedule_survival_probability: float
    combined_survival_probability: float
    risk_tier: str


class RiskDriverResponse(BaseModel):
    variable_id: str
    name: str
    category: str
    uncertainty_contribution_pct: float
    sensitivity_coefficient: float
    label: str = "CONTRIBUTION"


class HistogramBinResponse(BaseModel):
    bin_start: float
    bin_end: float
    count: int
    frequency: float


class PlanRiskSimulationResponse(BaseModel):
    run_id: str
    optimization_run_id: str
    scenario_run_id: Optional[str]
    simulation_count: int
    random_seed: int
    expected_portfolio_contribution: float
    portfolio_contribution_std: float
    expected_portfolio_revenue: float
    expected_portfolio_cost: float
    percentiles: Dict[str, float]
    var90_level: float
    var95_level: float
    var90_downside: float
    var95_downside: float
    cvar90: float
    cvar95: float
    loss_probability: float
    expected_loss: float
    plan_reliability_score: float
    risk_tier: str
    assignments: List[AssignmentRiskResponse]
    drivers: List[RiskDriverResponse]
    distribution_histogram: List[HistogramBinResponse]
    provenance_audit: List[Dict[str, Any]]


class PlanRiskComparisonRequest(BaseModel):
    optimization_run_id_a: Optional[str] = None
    optimization_run_id_b: Optional[str] = None
    is_demo_flip: bool = False


class PlanRiskComparisonResponse(BaseModel):
    plan_a_id: str
    plan_a_name: str
    plan_b_id: str
    plan_b_name: str
    plan_a_expected_contribution: float
    plan_b_expected_contribution: float
    expected_contribution_delta: float
    plan_a_loss_probability: float
    plan_b_loss_probability: float
    plan_a_cvar95: float
    plan_b_cvar95: float
    plan_a_reliability_score: float
    plan_b_reliability_score: float
    trade_off_summary: str
    recommendation_notes: str
