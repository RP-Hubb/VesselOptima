"""
VesselOptima — Phase 13: Backtesting & Decision Replay Pydantic Schemas
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BacktestConfigurationCreate(BaseModel):
    name: str = Field(..., description="Institutional name for configuration")
    description: Optional[str] = None
    start_timestamp: datetime
    end_timestamp: datetime
    decision_frequency: str = Field("EVENT_DRIVEN", description="EVENT_DRIVEN, DAILY, WEEKLY, CUSTOM")
    decision_policy: str = "RECOMMENDED"
    dataset_versions: Dict[str, int] = Field(default_factory=lambda: {"maritime_data": 1})
    phase7_configuration: Dict[str, Any] = Field(default_factory=dict)
    phase8_enabled: bool = False
    phase9_enabled: bool = False
    phase10_configuration: Dict[str, Any] = Field(default_factory=dict)
    benchmark_set: List[str] = Field(
        default_factory=lambda: [
            "NO_ACTION",
            "CONTINUE_CURRENT_EMPLOYMENT",
            "FIRST_FEASIBLE",
            "BEST_EXPECTED_CONTRIBUTION",
            "HISTORICAL_ACTUAL",
        ]
    )
    seed: int = 42
    created_by: str = "institutional_risk_manager"


class BacktestConfigurationResponse(BaseModel):
    id: int
    config_code: str
    name: str
    description: Optional[str]
    start_timestamp: datetime
    end_timestamp: datetime
    decision_frequency: str
    decision_policy: str
    dataset_versions: Dict[str, int]
    phase8_enabled: bool
    phase9_enabled: bool
    benchmark_set: List[str]
    seed: int
    configuration_hash: str
    created_at: datetime
    created_by: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class BacktestRunCreate(BaseModel):
    name: str
    start_timestamp: datetime
    end_timestamp: datetime
    mode: str = "OUTCOME_BACKTEST"  # DECISION_REPLAY, OUTCOME_BACKTEST, BENCHMARK_BACKTEST
    frequency: str = "EVENT_DRIVEN"
    dataset_versions: Optional[Dict[str, int]] = None
    phase8_enabled: bool = False
    phase9_enabled: bool = False
    seed: int = 42
    benchmark_set: Optional[List[str]] = None
    strict_leakage: bool = True
    created_by: str = "fleet_analyst"


class BacktestRunSummary(BaseModel):
    id: int
    run_code: Optional[str]
    name: str
    mode: str
    status: str
    start_timestamp: Optional[datetime]
    end_timestamp: Optional[datetime]
    decision_frequency: Optional[str]
    backtest_hash: Optional[str]
    configuration_hash: Optional[str]
    warnings_count: int = 0
    failure_reason: Optional[str] = None
    execution_time_seconds: Optional[float] = None
    created_at: datetime
    created_by: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class BacktestRunDetail(BacktestRunSummary):
    configuration: Optional[BacktestConfigurationResponse] = None
    metrics_summary: Optional[Dict[str, Any]] = None
    dataset_versions: Optional[Dict[str, Any]] = None
    software_version: Optional[str] = "1.0.0"
    solver_version: Optional[str] = "HiGHS-1.5.1"


class BacktestTimelineStepItem(BaseModel):
    id: int
    step_index: int
    step_timestamp: datetime
    event_count: int
    status: str
    notes: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class BacktestDecisionItem(BaseModel):
    id: int
    decision_code: str
    decision_timestamp: datetime
    recommendation: str
    assignments: List[Dict[str, Any]]
    expected_contribution: float
    decision_hash: str
    phase7_run_id: Optional[str]
    phase8_run_id: Optional[str]
    phase9_run_id: Optional[str]
    phase10_run_id: Optional[str]
    risk_metrics: Optional[Dict[str, Any]]
    governance_state: Optional[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)


class BacktestOutcomeItem(BaseModel):
    id: int
    outcome_code: str
    vessel_id: int
    cargo_id: Optional[int]
    realized_revenue: float
    realized_bunker_cost: float
    realized_port_cost: float
    realized_voyage_cost: float
    realized_ballast_cost: float
    realized_idle_cost: float
    realized_contribution: float
    expected_contribution: float
    economic_error: float
    schedule_delay_days: float
    idle_days: float
    ballast_days: float
    cargo_completed: bool
    outcome_hash: str

    model_config = ConfigDict(from_attributes=True)


class BacktestBenchmarkResultItem(BaseModel):
    id: int
    benchmark_code: Optional[str] = None
    benchmark_name: Optional[str] = None
    strategy_type: Optional[str] = None
    step_timestamp: datetime
    assignments: List[Dict[str, Any]]
    realized_contribution: float
    vessel_utilization: float
    details: Optional[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)


class BacktestMetricItem(BaseModel):
    id: int
    metric_category: str
    metric_name: str
    metric_value: float
    details: Optional[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)


class BacktestAttributionItem(BaseModel):
    id: int
    attribution_type: str
    entity_id: str
    entity_name: str
    incremental_contribution: float
    decision_count: int
    utilization_pct: float
    details: Optional[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)


class BacktestLeakageItem(BaseModel):
    id: int
    leakage_type: str
    severity: str
    field_name: Optional[str]
    decision_timestamp: datetime
    information_timestamp: Optional[datetime]
    details: Optional[Dict[str, Any]]
    detected_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BacktestCompareRequest(BaseModel):
    run_ids: List[int] = Field(..., min_length=2)


class BacktestCompareRunItem(BaseModel):
    run_id: int
    run_code: str
    name: str
    mode: str
    status: str
    total_realized_contribution: float
    incremental_contribution: float
    relative_improvement_pct: float
    vessel_utilization_pct: float
    schedule_delay_days: float
    warnings_count: int
    backtest_hash: str


class BacktestCompareResponse(BaseModel):
    runs: List[BacktestCompareRunItem]
    winner_run_id: int
    delta_contribution_usd: float
    comparison_notes: List[str]
