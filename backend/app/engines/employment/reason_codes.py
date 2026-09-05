"""
VesselOptima — Employment & Idle Engine: Deterministic Reason Codes
Follows Section 19 of the Phase 6 Specification.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional


class EmploymentReasonCode(str, Enum):
    """
    Deterministic reason codes for vessel employment opportunities,
    idle state assessments, and timeline evaluation.
    """
    # Admissible candidate
    EMPLOYMENT_FEASIBLE = "EMPLOYMENT_FEASIBLE"

    # Temporal & Chronological constraints
    EMPLOYMENT_WINDOW_MISSED = "EMPLOYMENT_WINDOW_MISSED"
    VESSEL_COMMITMENT_CONFLICT = "VESSEL_COMMITMENT_CONFLICT"
    INSUFFICIENT_AVAILABILITY = "INSUFFICIENT_AVAILABILITY"
    BALLAST_TIME_EXCEEDS_WINDOW = "BALLAST_TIME_EXCEEDS_WINDOW"
    LAYCAN_INCOMPATIBLE = "LAYCAN_INCOMPATIBLE"
    DELIVERY_DEADLINE_UNATTAINABLE = "DELIVERY_DEADLINE_UNATTAINABLE"

    # Fleet & Cargo availability
    NO_FEASIBLE_EMPLOYMENT = "NO_FEASIBLE_EMPLOYMENT"
    CARGO_UNAVAILABLE = "CARGO_UNAVAILABLE"
    VESSEL_UNAVAILABLE = "VESSEL_UNAVAILABLE"

    # Commercial & Procurement dependencies
    PROCUREMENT_REQUIRED = "PROCUREMENT_REQUIRED"
    PROCUREMENT_TIMING_FAILED = "PROCUREMENT_TIMING_FAILED"

    # Economic & State confirmation
    ECONOMIC_DATA_UNAVAILABLE = "ECONOMIC_DATA_UNAVAILABLE"
    IDLE_STATE_CONFIRMED = "IDLE_STATE_CONFIRMED"
    VESSEL_IDLE_NO_COMMITMENT = "VESSEL_IDLE_NO_COMMITMENT"
    VESSEL_IDLE_SCHEDULE_GAP = "VESSEL_IDLE_SCHEDULE_GAP"
    VESSEL_COMMITTED = "VESSEL_COMMITTED"
    REPOSITIONING_REQUIRED = "REPOSITIONING_REQUIRED"
    DATA_SOURCE_UNAVAILABLE = "DATA_SOURCE_UNAVAILABLE"


REASON_DESCRIPTIONS = {
    EmploymentReasonCode.EMPLOYMENT_FEASIBLE: (
        "Admissible alternative employment candidate satisfying operational feasibility, "
        "repositioning timing, cargo laycan, and delivery deadline constraints."
    ),
    EmploymentReasonCode.EMPLOYMENT_WINDOW_MISSED: (
        "Available operational time window between commitments is insufficient to execute "
        "the complete ballast repositioning, cargo loading, and laden voyage sequence."
    ),
    EmploymentReasonCode.VESSEL_COMMITMENT_CONFLICT: (
        "Proposed alternative employment completion date conflicts with an existing confirmed "
        "vessel commitment, violating protected schedule boundaries."
    ),
    EmploymentReasonCode.INSUFFICIENT_AVAILABILITY: (
        "Vessel earliest availability timestamp occurs after the cargo loading window has closed."
    ),
    EmploymentReasonCode.BALLAST_TIME_EXCEEDS_WINDOW: (
        "Required ballast transit duration prevents vessel from presenting at the cargo loading "
        "port before the cancellation date (laycan window end)."
    ),
    EmploymentReasonCode.LAYCAN_INCOMPATIBLE: (
        "Projected vessel arrival at the origin port falls outside the permissible cargo laycan interval."
    ),
    EmploymentReasonCode.DELIVERY_DEADLINE_UNATTAINABLE: (
        "Projected laden transit and discharge completion timestamp exceeds the strict cargo delivery deadline."
    ),
    EmploymentReasonCode.NO_FEASIBLE_EMPLOYMENT: (
        "No compatible alternative cargo parcel or employment structure found during this availability window."
    ),
    EmploymentReasonCode.CARGO_UNAVAILABLE: (
        "The designated cargo requirement is unavailable, already committed, or cancelled."
    ),
    EmploymentReasonCode.VESSEL_UNAVAILABLE: (
        "Vessel has no recorded availability event, is undergoing maintenance, or is inactive."
    ),
    EmploymentReasonCode.PROCUREMENT_REQUIRED: (
        "Alternative employment requires commercial tender/chartering procurement prior to fixture."
    ),
    EmploymentReasonCode.PROCUREMENT_TIMING_FAILED: (
        "Commercial procurement administrative lead time exceeds available days before cargo laycan start."
    ),
    EmploymentReasonCode.ECONOMIC_DATA_UNAVAILABLE: (
        "Benchmark freight rate or revenue fixture unavailable; gross contribution cannot be determined."
    ),
    EmploymentReasonCode.IDLE_STATE_CONFIRMED: (
        "Vessel is confirmed in an idle waiting state between fixtures with transparent holding cost exposure."
    ),
    EmploymentReasonCode.VESSEL_IDLE_NO_COMMITMENT: (
        "Vessel is available with no immediate future commitments scheduled."
    ),
    EmploymentReasonCode.VESSEL_IDLE_SCHEDULE_GAP: (
        "Vessel is idle in an operational schedule gap prior to next confirmed commitment."
    ),
    EmploymentReasonCode.VESSEL_COMMITTED: (
        "Vessel is actively engaged or committed with zero idle operational gap."
    ),
    EmploymentReasonCode.REPOSITIONING_REQUIRED: (
        "Vessel requires ballast repositioning to a strategic hub or origin port to become actionable."
    ),
    EmploymentReasonCode.DATA_SOURCE_UNAVAILABLE: (
        "Required canonical dataset, distance matrix, or route definition could not be resolved."
    ),
}


def describe_reason_code(code: Optional[EmploymentReasonCode | str]) -> str:
    """Returns human-readable explanation for an EmploymentReasonCode."""
    if not code:
        return "Operational status not specified."
    try:
        enum_val = EmploymentReasonCode(code) if isinstance(code, str) else code
        return REASON_DESCRIPTIONS.get(enum_val, f"Employment evaluation code: {enum_val.value}")
    except ValueError:
        return f"Operational code: {code}"
