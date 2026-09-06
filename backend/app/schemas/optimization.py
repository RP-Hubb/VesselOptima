"""
VesselOptima — Phase 7: Optimization Schemas

Pydantic schemas for optimization requests, responses, objective decomposition,
candidate assignment audit records, and solver diagnostics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class SolveFleetAssignmentRequest(BaseModel):
    scenario: Optional[str] = Field("DEMO_FLEET", description="Optimization scenario: DEMO_FLEET, GREEDY_PROOF, RAW_PHASE6, HIGH_BALLAST, IDLE_FOCUS, REJECTION")
    as_of_date: Optional[datetime] = Field(None, description="Optimization evaluation as-of date (defaults to 2026-09-01)")
    vessel_id: Optional[int] = Field(None, description="Optional vessel filter")
    cargo_id: Optional[int] = Field(None, description="Optional cargo parcel filter")
    alpha_idle_weight: float = Field(1.0, ge=0.0, le=1.0, description="Multiplier for avoided idle holding costs")
    beta_ballast_penalty: float = Field(0.0, ge=0.0, description="Direct penalty rate per ballast day ($/day)")
    default_unserved_penalty: float = Field(0.0, ge=0.0, description="Penalty for leaving optional cargo unserved ($)")
    cargo_penalties: Optional[dict[int, float]] = Field(None, description="Cargo-specific unserved penalties ($)")
    time_limit_seconds: Optional[float] = Field(30.0, ge=0.1, le=300.0, description="Solver execution time limit in seconds")
    mip_gap: float = Field(1e-4, ge=1e-6, le=0.1, description="Relative MIP gap tolerance")
    persist: bool = Field(True, description="Whether to persist the optimization run and assignment records to the database")


class ObjectiveDecompositionResponse(BaseModel):
    total_gross_revenue: float
    total_voyage_cost: float
    total_net_contribution: float
    total_avoided_idle_cost: float
    total_ballast_penalty: float
    total_unserved_penalty: float
    global_objective_value: float


class AssignmentResponse(BaseModel):
    candidate_id: str
    vessel_id: int
    vessel_name: str
    cargo_id: Optional[int]
    cargo_name: str
    is_selected: bool
    selection_status: str
    start_time: Optional[str]
    end_time: Optional[str]
    expected_revenue: float
    voyage_cost: float
    gross_contribution: float
    idle_days_saved: float
    avoided_idle_cost: float
    ballast_distance_nm: float
    ballast_days: float
    voyage_days: float
    trade_off_reason_code: str
    trade_off_explanation: str
    assignment_metadata: Optional[dict[str, Any]] = None


class UnassignedCargoResponse(BaseModel):
    cargo_id: int
    cargo_name: str
    unserved_penalty: float
    reason_code: str
    reason_explanation: str


class OptimizationResultResponse(BaseModel):
    run_id: str
    status: str
    objective_value: float
    decomposition: ObjectiveDecompositionResponse
    selected_assignments: list[AssignmentResponse]
    rejected_opportunities: list[AssignmentResponse]
    unassigned_cargos: list[UnassignedCargoResponse]
    vessel_utilization: dict[str, Any]
    solver_metadata: dict[str, Any]
    constraint_summary: dict[str, Any]
    audit_trail: list[dict[str, Any]]
    solve_time_seconds: float
    created_at: str


class OptimizationRunSummaryResponse(BaseModel):
    run_id: str
    status: str
    objective_value: Optional[float] = None
    total_revenue: Optional[float] = None
    total_cost: Optional[float] = None
    total_contribution: Optional[float] = None
    avoided_idle_cost: Optional[float] = None
    solver_name: Optional[str] = None
    solve_time_seconds: Optional[float] = None
    result_summary: Optional[dict[str, Any]] = None
    created_at: Optional[str] = None


class CompareRunsRequest(BaseModel):
    run_id_a: str
    run_id_b: str
