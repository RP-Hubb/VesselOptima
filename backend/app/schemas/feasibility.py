"""
VesselOptima — Pydantic Schemas: Feasibility Engine
Follows Section 27, 28, 29 of the Phase 4 Specification.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class FeasibilityEvaluateRequest(BaseModel):
    cargo_id: int
    vessel_id: int
    route_id: Optional[int] = None
    persist: bool = False


class FeasibilityMatrixRequest(BaseModel):
    cargo_ids: Optional[List[int]] = None
    vessel_ids: Optional[List[int]] = None


class FeasibilityResultResponse(BaseModel):
    is_feasible: bool
    cargo_id: Optional[int] = None
    cargo_name: Optional[str] = None
    vessel_id: Optional[int] = None
    vessel_name: Optional[str] = None
    vessel_class: Optional[str] = None
    route_id: Optional[int] = None
    route_name: Optional[str] = None
    origin_port: Optional[str] = None
    destination_port: Optional[str] = None
    primary_reason_code: Optional[str] = None
    primary_reason_description: Optional[str] = None
    reason_codes: List[str]
    failed_checks: List[str]
    checks: Dict[str, Any]
    warnings: List[str]
    timing: Dict[str, Any]
    evidence: Dict[str, Any]
    provenance: Dict[str, Any]
    evaluated_at: str


class FleetVesselItem(BaseModel):
    vessel_id: int
    vessel_name: str
    vessel_class: str
    cargo_capacity: float
    draft: float
    loa: float
    beam: float
    is_feasible: bool
    primary_reason_code: Optional[str] = None
    primary_reason_description: Optional[str] = None
    failed_checks: List[str]
    warnings_count: int


class FleetFeasibilityResponse(BaseModel):
    cargo_id: int
    cargo_name: str
    total_vessels: int
    feasible_count: int
    infeasible_count: int
    vessels: List[FleetVesselItem]
    provenance: Dict[str, Any]
    evaluated_at: str


class CargoRequirementItem(BaseModel):
    id: int
    commodity: str
    volume_mt: float
    origin_port_id: int
    destination_port_id: int
    origin_port_name: Optional[str] = None
    destination_port_name: Optional[str] = None
    loading_window_start: str
    loading_window_end: str
    delivery_deadline: str
    tolerance_pct: float
