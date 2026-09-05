"""
VesselOptima — Pydantic Schemas: Dynamic Procurement Strategy Engine
Follows Section 17 of the Phase 5 Specification.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ProcurementProfileSchema(BaseModel):
    profile_id: str
    name: str
    tender_preparation_days: float
    bid_submission_days: float
    technical_evaluation_days: float
    commercial_evaluation_days: float
    approval_days: float
    award_days: float
    minimum_lead_time_days: float
    description: str
    data_classification: str = "CONFIGURED"


class ProcurementProfileUpdateSchema(BaseModel):
    profile_id: str
    name: Optional[str] = None
    tender_preparation_days: Optional[float] = None
    bid_submission_days: Optional[float] = None
    technical_evaluation_days: Optional[float] = None
    commercial_evaluation_days: Optional[float] = None
    approval_days: Optional[float] = None
    award_days: Optional[float] = None


class StrategyDefinitionSchema(BaseModel):
    strategy_type: str
    name: str
    description: str
    duration_days: int
    voyage_count: int
    discount_factor: float
    market_exposure: str
    commitment_level: str


class StrategyEvaluationSchema(BaseModel):
    strategy_type: str
    strategy_name: str
    description: Optional[str] = None
    status: str
    primary_reason_code: Optional[str] = None
    primary_reason_description: Optional[str] = None
    timing_signal: Optional[str] = None
    contract_duration_days: Optional[int] = None
    voyage_count: Optional[int] = None
    market_exposure: Optional[str] = None
    commitment_level: Optional[str] = None
    timing: Optional[Dict[str, Any]] = None
    forecast_evidence: Optional[Dict[str, Any]] = None
    cost_summary: Optional[Dict[str, Any]] = None
    feasibility_summary: Optional[Dict[str, Any]] = None
    candidate_metadata: Optional[Dict[str, Any]] = None
    provenance: Optional[Dict[str, Any]] = None


class ProcurementCompareRequest(BaseModel):
    cargo_id: int
    profile_id: Optional[str] = None
    strategy_types: Optional[List[str]] = None
    as_of_date: Optional[str] = None
    custom_stages: Optional[Dict[str, float]] = None
    persist: bool = False


class ProcurementCompareResponse(BaseModel):
    cargo_id: int
    commodity: str
    volume_mt: float
    origin_port: str
    destination_port: str
    laycan_start: str
    laycan_end: str
    delivery_deadline: str
    as_of_date: str
    procurement_profile: Dict[str, Any]
    procurement_lead_time_days: float
    strategies_evaluated_count: int
    feasible_strategies_count: int
    infeasible_strategies_count: int
    strategies: List[StrategyEvaluationSchema]
    advisory_note: str
    evaluated_at: str
