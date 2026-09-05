"""VesselOptima — Pydantic Schemas: Idle Management & Alternative Employment Engine

Strict Architectural Boundary:
    Candidate Generation != Global Allocation
    Idle Management != Fleet Optimization
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FleetEmploymentOverviewResponse(BaseModel):
    as_of_date: str
    total_vessels: int
    available_vessels: int
    committed_vessels: int
    idle_vessels: int
    alternative_candidates_generated: int
    provenance: Dict[str, Any]


class CommitmentDetailSchema(BaseModel):
    id: int
    description: str
    commitment_start: str
    commitment_end: Optional[str] = None


class VesselEmploymentStatusResponse(BaseModel):
    vessel_id: int
    vessel_name: str
    vessel_class: str
    current_location_port_id: int
    current_location_name: str
    available_at: str
    has_active_commitment: bool
    active_commitment: Optional[CommitmentDetailSchema] = None
    next_commitment: Optional[CommitmentDetailSchema] = None


class TimelineEventSchema(BaseModel):
    event_type: str
    title: str
    start_time: str
    end_time: str
    color: str
    details: str


class VesselTimelineResponse(BaseModel):
    vessel_id: int
    vessel_name: str
    vessel_class: str
    as_of_date: str
    horizon_end: str
    events: List[TimelineEventSchema]


class OpportunitySchema(BaseModel):
    opportunity_id: str
    cargo_id: int
    commodity: str
    volume_mt: float
    origin_port_id: int
    origin_port_name: str
    destination_port_id: int
    destination_port_name: str
    laycan_start: str
    laycan_end: str
    delivery_deadline: str
    tolerance_pct: float
    status: str = "OPEN"


class OpportunitiesResponse(BaseModel):
    opportunities: List[OpportunitySchema]
    total_count: int


class IdleAssessmentSchema(BaseModel):
    vessel_id: int
    vessel_name: str
    vessel_class: str
    as_of_date: str
    is_idle: bool
    idle_days: float
    window_start: str
    window_end: str
    daily_idle_rate: float
    idle_cost: float
    cost_source: str
    reason_code: str
    reason_description: str
    active_commitment: Optional[Dict[str, Any]] = None
    next_commitment: Optional[Dict[str, Any]] = None
    provenance: Dict[str, Any]


class FleetIdleResponse(BaseModel):
    as_of_date: str
    total_vessels_assessed: int
    idle_vessels_count: int
    active_vessels_count: int
    total_idle_days: float
    total_idle_cost: float
    assessments: List[IdleAssessmentSchema]
    provenance: Dict[str, Any]


class EmploymentCandidateRequest(BaseModel):
    vessel_id: int
    cargo_id: int
    as_of_date: Optional[str] = None
    employment_type: str = "ALTERNATIVE_EMPLOYMENT"
    procurement_profile_id: Optional[str] = "STANDARD_COMMERCIAL"
    persist: bool = False


class EmploymentCandidateResponse(BaseModel):
    candidate_id: str
    vessel_id: int
    vessel_name: str
    vessel_class: str
    cargo_id: int
    cargo_name: str
    employment_type: str
    origin_port_id: int
    origin_port_name: str
    destination_port_id: int
    destination_port_name: str
    status: str  # FEASIBLE | INFEASIBLE
    optimization_status: str  # READY_FOR_OPTIMIZATION | REJECTED
    primary_reason_code: str
    primary_reason_description: str
    failed_reasons: List[str]
    ballast: Dict[str, Any]
    feasibility: Dict[str, Any]
    procurement: Dict[str, Any]
    timeline: Dict[str, Any]
    economics: Dict[str, Any]
    provenance: Dict[str, Any]


class CandidateMatrixRequest(BaseModel):
    vessel_id: Optional[int] = None
    cargo_id: Optional[int] = None
    ready_only: bool = False
    as_of_date: Optional[str] = None
    persist: bool = False


class CandidateMatrixResponse(BaseModel):
    as_of_date: str
    total_evaluated: int
    feasible_count: int
    infeasible_count: int
    returned_count: int
    candidates: List[EmploymentCandidateResponse]
    governing_boundary: str
    provenance: Dict[str, Any]


class CandidateCompareRequest(BaseModel):
    vessel_id: Optional[int] = None
    cargo_id: Optional[int] = None
    as_of_date: Optional[str] = None


class CandidateCompareResponse(BaseModel):
    comparison_type: str
    filter_vessel_id: Optional[int] = None
    filter_cargo_id: Optional[int] = None
    as_of_date: str
    candidate_count: int
    candidates: List[EmploymentCandidateResponse]
    advisory_note: str
    provenance: Dict[str, Any]
