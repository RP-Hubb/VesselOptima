"""
VesselOptima — Feasibility Reason Codes

Standardized, machine-readable reason codes and descriptions for operational,
physical, and temporal constraint evaluations.
Follows Section 20 of the Phase 4 Specification.
"""

from __future__ import annotations

import enum
from typing import Dict


class FeasibilityReasonCode(str, enum.Enum):
    # Entity Resolution Codes
    VESSEL_NOT_FOUND = "VESSEL_NOT_FOUND"
    CARGO_NOT_FOUND = "CARGO_NOT_FOUND"
    ROUTE_NOT_FOUND = "ROUTE_NOT_FOUND"

    # Vessel & Cargo Compatibility Codes
    INSUFFICIENT_VESSEL_CAPACITY = "INSUFFICIENT_VESSEL_CAPACITY"
    INCOMPATIBLE_VESSEL_TYPE = "INCOMPATIBLE_VESSEL_TYPE"

    # Port Physical Dimension Codes
    VESSEL_DRAFT_EXCEEDS_PORT_LIMIT = "VESSEL_DRAFT_EXCEEDS_PORT_LIMIT"
    VESSEL_LOA_EXCEEDS_PORT_LIMIT = "VESSEL_LOA_EXCEEDS_PORT_LIMIT"
    VESSEL_BEAM_EXCEEDS_PORT_LIMIT = "VESSEL_BEAM_EXCEEDS_PORT_LIMIT"

    # Port Composite Status Codes
    ORIGIN_PORT_INFEASIBLE = "ORIGIN_PORT_INFEASIBLE"
    DESTINATION_PORT_INFEASIBLE = "DESTINATION_PORT_INFEASIBLE"

    # Availability & Commitment Codes
    VESSEL_NOT_AVAILABLE = "VESSEL_NOT_AVAILABLE"
    VESSEL_COMMITMENT_CONFLICT = "VESSEL_COMMITMENT_CONFLICT"

    # Schedule & Timing Codes
    LOADING_WINDOW_INVALID = "LOADING_WINDOW_INVALID"
    DEADLINE_MISSED = "DEADLINE_MISSED"
    VOYAGE_TIME_INFEASIBLE = "VOYAGE_TIME_INFEASIBLE"


REASON_CODE_DESCRIPTIONS: Dict[FeasibilityReasonCode, str] = {
    FeasibilityReasonCode.VESSEL_NOT_FOUND: "The specified vessel identifier was not found in the fleet registry.",
    FeasibilityReasonCode.CARGO_NOT_FOUND: "The specified cargo parcel requirement was not found.",
    FeasibilityReasonCode.ROUTE_NOT_FOUND: "No valid maritime route connects the specified origin and destination ports.",
    FeasibilityReasonCode.INSUFFICIENT_VESSEL_CAPACITY: "Vessel cargo capacity is less than the required cargo volume (exceeds allowable tolerance).",
    FeasibilityReasonCode.INCOMPATIBLE_VESSEL_TYPE: "Vessel class or design particulars are incompatible with the cargo commodity/parcel size.",
    FeasibilityReasonCode.VESSEL_DRAFT_EXCEEDS_PORT_LIMIT: "Vessel laden/arrival draft exceeds the maximum permitted port/terminal draft.",
    FeasibilityReasonCode.VESSEL_LOA_EXCEEDS_PORT_LIMIT: "Vessel length overall (LOA) exceeds the maximum permitted port/berth limit.",
    FeasibilityReasonCode.VESSEL_BEAM_EXCEEDS_PORT_LIMIT: "Vessel extreme breadth (beam) exceeds the maximum permitted port/berth limit.",
    FeasibilityReasonCode.ORIGIN_PORT_INFEASIBLE: "Vessel fails one or more physical constraints at the origin loading port.",
    FeasibilityReasonCode.DESTINATION_PORT_INFEASIBLE: "Vessel fails one or more physical constraints at the destination discharge port.",
    FeasibilityReasonCode.VESSEL_NOT_AVAILABLE: "Vessel cannot position to the load port prior to the close of the cargo loading window.",
    FeasibilityReasonCode.VESSEL_COMMITMENT_CONFLICT: "Proposed voyage schedule conflicts with an immutable existing fixture or charter commitment.",
    FeasibilityReasonCode.LOADING_WINDOW_INVALID: "Vessel arrival or loading window timing is invalid or backwards.",
    FeasibilityReasonCode.DEADLINE_MISSED: "Estimated voyage arrival and discharge at the destination port exceeds the cargo delivery deadline.",
    FeasibilityReasonCode.VOYAGE_TIME_INFEASIBLE: "Estimated total duration exceeds the permissible delivery window.",
}


def describe_reason_code(code: str | FeasibilityReasonCode) -> str:
    """Returns human-readable explanation for a standardized reason code."""
    try:
        enum_val = FeasibilityReasonCode(code) if isinstance(code, str) else code
        return REASON_CODE_DESCRIPTIONS.get(enum_val, str(code))
    except ValueError:
        return str(code)
