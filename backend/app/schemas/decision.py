"""
VesselOptima — Phase 10 Decision Intelligence Engine
Pydantic Schemas for API Requests & Responses
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DecisionWeightsConfig(BaseModel):
    economic: float = Field(0.35, ge=0.0, le=1.0)
    reliability: float = Field(0.25, ge=0.0, le=1.0)
    robustness: float = Field(0.20, ge=0.0, le=1.0)
    risk_penalty: float = Field(0.10, ge=0.0, le=1.0)
    schedule_penalty: float = Field(0.10, ge=0.0, le=1.0)


class DecisionThresholdsInput(BaseModel):
    max_loss_prob_proceed: Optional[float] = Field(0.05, ge=0.0, le=1.0)
    max_loss_prob_caution: Optional[float] = Field(0.15, ge=0.0, le=1.0)
    max_cvar95_downside_ratio_proceed: Optional[float] = Field(0.20, ge=0.0, le=2.0)
    min_schedule_buffer_days: Optional[float] = Field(2.0, ge=0.0)
    max_laycan_miss_prob_proceed: Optional[float] = Field(0.05, ge=0.0, le=1.0)
    min_reliability_proceed: Optional[float] = Field(80.0, ge=0.0, le=100.0)
    min_score_proceed: Optional[float] = Field(75.0, ge=0.0, le=100.0)
    min_score_caution: Optional[float] = Field(50.0, ge=0.0, le=100.0)
    risk_aversion_lambda: Optional[float] = Field(0.50, ge=0.0, le=5.0)
    weights: Optional[DecisionWeightsConfig] = None


class DecisionEvaluateRequest(BaseModel):
    optimization_run_id: str = Field(..., description="ID of Phase 7 MILP Optimization Run")
    scenario_run_id: Optional[str] = Field(None, description="Optional ID of Phase 8 Scenario Run")
    risk_run_id: Optional[str] = Field(None, description="Optional ID of Phase 9 Risk Run")
    strategy_flip_identified: bool = Field(False, description="Flag indicating strategy-flip vulnerability")
    thresholds: Optional[DecisionThresholdsInput] = None


class DecisionScoreBreakdownSchema(BaseModel):
    economic_component: float
    reliability_component: float
    robustness_component: float
    risk_penalty: float
    schedule_penalty: float
    composite_score: float


class DecisionEvidenceSchema(BaseModel):
    optimization_objective: Optional[float] = None
    expected_contribution: float
    baseline_contribution: Optional[float] = None
    risk_adjusted_contribution: float
    loss_probability: float
    cvar_95: float
    var_95_downside: float
    assignment_survival: float
    plan_reliability: float
    laycan_miss_probability: float
    scenario_survival_rate: float
    robustness_tier: str
    top_risk_drivers: Optional[List[Dict[str, Any]]] = None
    critical_warnings: Optional[List[str]] = None


class DecisionActionSchema(BaseModel):
    action_id: str
    priority: str
    title: str
    description: str
    affected_variable: Optional[str] = None
    affected_assignment_id: Optional[str] = None
    trigger_condition: Optional[str] = None
    recommended_action: str


class DecisionTradeoffSchema(BaseModel):
    comparison_plan_id: str
    comparison_plan_name: str
    baseline_plan_name: str
    contribution_delta: float
    loss_prob_delta: float
    cvar_delta: float
    reliability_delta: float
    tradeoff_summary: str
    tradeoff_details: Optional[Dict[str, Any]] = None


class AssignmentDecisionSchema(BaseModel):
    candidate_id: str
    vessel_id: int
    vessel_name: str
    cargo_id: Optional[int] = None
    cargo_name: Optional[str] = None
    recommendation_type: str
    primary_reason_code: str
    reason_codes: List[str]
    title: str
    summary: str
    action_advice: str
    expected_contribution: float
    contribution_std: float
    loss_probability: float
    cvar95: float
    schedule_buffer_days: float
    laycan_miss_prob: float
    economic_survival_prob: float
    schedule_survival_prob: float
    risk_tier: str


class DecisionResultResponse(BaseModel):
    run_id: str
    optimization_run_id: str
    scenario_run_id: Optional[str] = None
    risk_run_id: Optional[str] = None
    recommendation_type: str
    primary_reason_code: str
    reason_codes: List[str]
    confidence: str
    decision_score: float
    scoring_breakdown: DecisionScoreBreakdownSchema
    decision_stability: float
    risk_adjusted_contribution: float
    executive_summary: str
    financial_narrative: str
    risk_narrative: str
    schedule_narrative: str
    what_could_change: List[str]
    assignment_recommendations: List[AssignmentDecisionSchema]
    actions: List[DecisionActionSchema]
    tradeoffs: List[DecisionTradeoffSchema]
    evidence: DecisionEvidenceSchema
    input_hash: str
    output_hash: str
    execution_time_seconds: float


class DecisionRunSummaryResponse(BaseModel):
    id: int
    run_id: str
    optimization_run_id: str
    scenario_run_id: Optional[str] = None
    risk_run_id: Optional[str] = None
    recommendation_type: str
    confidence: str
    decision_score: float
    decision_stability: float
    risk_adjusted_contribution: Optional[float] = None
    status: str
    created_at: Optional[str] = None
