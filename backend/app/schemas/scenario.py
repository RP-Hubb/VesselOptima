"""
VesselOptima — Phase 8: Scenario Analysis & What-If Pydantic Schemas

Defines typed request and response contracts for scenario simulation,
batch what-if runs, sensitivity sweeps, and robustness analysis.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ScenarioConfigPayload(BaseModel):
    scenario_id: Optional[str] = Field(default=None, description="Unique scenario identifier")
    name: str = Field(..., description="Human-readable scenario title")
    description: Optional[str] = Field(default="", description="Detailed narrative of scenario assumptions")
    scenario_type: Optional[str] = Field(default="CUSTOM", description="Scenario category")
    baseline_scenario: Optional[str] = Field(default="DEMO_FLEET", description="Underlying baseline fleet candidate set")
    freight_multiplier: float = Field(default=1.0, ge=0.0, le=5.0, description="Gross freight revenue multiplier")
    bunker_multiplier: float = Field(default=1.0, ge=0.0, le=10.0, description="Fuel cost multiplier")
    idle_cost_multiplier: float = Field(default=1.0, ge=0.0, le=10.0, description="Daily idle holding cost multiplier")
    port_cost_multiplier: float = Field(default=1.0, ge=0.0, le=5.0, description="Port dues & tariffs multiplier")
    laycan_adjustment_days: float = Field(default=0.0, ge=0.0, le=30.0, description="Days to tighten cargo laycan windows")
    excluded_vessel_ids: List[int] = Field(default_factory=list, description="IDs of vessels unavailable in scenario")
    vessel_delay_days: Dict[str, float] = Field(default_factory=dict, description="Days delayed per vessel ID")
    alpha_idle_weight: float = Field(default=1.0, ge=0.0, description="Idle cost objective weight")
    beta_ballast_penalty: float = Field(default=0.0, ge=0.0, description="Ballast penalty objective coefficient")
    default_unserved_penalty: float = Field(default=0.0, ge=0.0, description="Cargo unserved penalty")


class CandidateDeltaSchema(BaseModel):
    candidate_id: str
    vessel_id: int
    vessel_name: str
    cargo_id: Optional[int]
    cargo_name: str
    delta_status: str  # UNCHANGED, ADDED, DROPPED, REJECTED
    in_baseline: bool
    in_scenario: bool
    baseline_revenue: float
    scenario_revenue: float
    baseline_cost: float
    scenario_cost: float
    baseline_net_contribution: float
    scenario_net_contribution: float
    contribution_delta: float
    trade_off_explanation: str


class CargoDeltaSchema(BaseModel):
    cargo_id: int
    cargo_name: str
    delta_status: str  # UNCHANGED, REPLACED, DROPPED_TO_UNSERVED, NEWLY_SERVED
    baseline_vessel_id: Optional[int]
    baseline_vessel_name: Optional[str]
    scenario_vessel_id: Optional[int]
    scenario_vessel_name: Optional[str]
    explanation: str


class VesselDeltaSchema(BaseModel):
    vessel_id: int
    vessel_name: str
    baseline_cargo_id: Optional[int]
    baseline_cargo_name: Optional[str]
    scenario_cargo_id: Optional[int]
    scenario_cargo_name: Optional[str]
    is_assignment_changed: bool
    explanation: str


class ScenarioComparisonResponse(BaseModel):
    scenario_id: str
    scenario_name: str
    baseline_run_id: str
    scenario_run_id: str

    # Objectives & Economics
    objective_value_baseline: float
    objective_value_scenario: float
    objective_value_delta: float
    objective_value_pct_change: float

    total_revenue_baseline: float
    total_revenue_scenario: float
    total_revenue_delta: float

    total_cost_baseline: float
    total_cost_scenario: float
    total_cost_delta: float

    net_contribution_baseline: float
    net_contribution_scenario: float
    net_contribution_delta: float

    idle_cost_avoided_baseline: float
    idle_cost_avoided_scenario: float
    idle_cost_avoided_delta: float

    # Operations
    cargoes_served_baseline: int
    cargoes_served_scenario: int
    cargoes_served_delta: int

    cargoes_unserved_baseline: int
    cargoes_unserved_scenario: int
    cargoes_unserved_delta: int

    vessels_utilized_baseline: int
    vessels_utilized_scenario: int
    vessels_utilized_delta: int

    total_ballast_nm_baseline: float
    total_ballast_nm_scenario: float
    total_ballast_nm_delta: float

    # Stability
    unchanged_assignments_count: int
    added_assignments_count: int
    dropped_assignments_count: int
    jaccard_similarity: float
    stability_score_pct: float

    # Detailed deltas
    candidate_deltas: List[CandidateDeltaSchema]
    cargo_deltas: List[CargoDeltaSchema]
    vessel_deltas: List[VesselDeltaSchema]


class BatchScenarioRequest(BaseModel):
    scenarios: List[ScenarioConfigPayload]


class BatchScenarioResponse(BaseModel):
    total_scenarios_executed: int
    comparisons: List[ScenarioComparisonResponse]


class SensitivityPointSchema(BaseModel):
    parameter_value: float
    parameter_label: str
    objective_value: float
    total_revenue: float
    total_cost: float
    net_contribution: float
    avoided_idle_cost: float
    cargoes_served: int
    vessels_utilized: int
    selected_candidate_ids: List[str]
    cargo_assignments: Dict[int, int]
    jaccard_stability: float


class BreakEvenThresholdSchema(BaseModel):
    entity_type: str
    entity_id: Any
    entity_name: str
    event_type: str
    threshold_type: str
    parameter_name: str
    threshold_value: Optional[float]
    lower_bound: Optional[float]
    upper_bound: Optional[float]
    explanation: str


class SensitivitySweepRequest(BaseModel):
    parameter_name: str = Field(..., description="Parameter to sweep (e.g. bunker_multiplier, freight_multiplier, idle_cost_multiplier)")
    sweep_values: List[float] = Field(..., min_length=2, description="Values to evaluate in the parameter sweep")
    base_config: Optional[ScenarioConfigPayload] = None


class SensitivitySweepResponse(BaseModel):
    parameter_name: str
    baseline_run_id: str
    baseline_value: float
    points: List[SensitivityPointSchema]
    break_even_thresholds: List[BreakEvenThresholdSchema]
    summary: str


class AssignmentRobustnessSchema(BaseModel):
    candidate_id: str
    vessel_id: int
    vessel_name: str
    cargo_id: Optional[int]
    cargo_name: str
    total_scenarios_evaluated: int
    scenarios_preserved: int
    robustness_score_pct: float
    robustness_tier: str  # CORE_ROBUST, CONDITIONALLY_STABLE, FRAGILE
    scenarios_selected_in: List[str]
    scenarios_dropped_in: List[str]
    advisory_notes: str


class RobustnessResponse(BaseModel):
    total_scenarios: int
    scenario_ids: List[str]
    overall_fleet_robustness_pct: float
    assignments: List[AssignmentRobustnessSchema]
    summary: str
