"""
VesselOptima — Procurement Reason Code Catalogue
Follows Section 18 of the Phase 5 Specification.
Deterministic machine-readable tokens and plain-English descriptions.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict


class ProcurementReasonCode(str, Enum):
    # Timing & Lead Time
    PROCUREMENT_WINDOW_INVALID = "PROCUREMENT_WINDOW_INVALID"
    PROCUREMENT_DEADLINE_MISSED = "PROCUREMENT_DEADLINE_MISSED"
    PROCUREMENT_LEAD_TIME_EXCEEDED = "PROCUREMENT_LEAD_TIME_EXCEEDED"

    # Feasibility Admittance
    NO_FEASIBLE_VESSEL = "NO_FEASIBLE_VESSEL"
    VESSEL_AVAILABILITY_CONFLICT = "VESSEL_AVAILABILITY_CONFLICT"

    # Forecast Integration
    FORECAST_DATA_UNAVAILABLE = "FORECAST_DATA_UNAVAILABLE"
    FORECAST_HORIZON_INSUFFICIENT = "FORECAST_HORIZON_INSUFFICIENT"

    # Strategy & Contract Parameters
    STRATEGY_DURATION_INVALID = "STRATEGY_DURATION_INVALID"
    INSUFFICIENT_CARGO_COVERAGE = "INSUFFICIENT_CARGO_COVERAGE"
    CONTRACT_WINDOW_CONFLICT = "CONTRACT_WINDOW_CONFLICT"


REASON_CODE_DESCRIPTIONS: Dict[str, str] = {
    ProcurementReasonCode.PROCUREMENT_WINDOW_INVALID.value: (
        "Cargo laycan window or delivery deadline is malformed or inverted."
    ),
    ProcurementReasonCode.PROCUREMENT_DEADLINE_MISSED.value: (
        "Calculated voyage transit plus procurement lead time exceeds delivery deadline."
    ),
    ProcurementReasonCode.PROCUREMENT_LEAD_TIME_EXCEEDED.value: (
        "Configured administrative procurement lead time exceeds remaining laycan window."
    ),
    ProcurementReasonCode.NO_FEASIBLE_VESSEL.value: (
        "Zero candidate vessels passed Phase 4 operational and port feasibility checks."
    ),
    ProcurementReasonCode.VESSEL_AVAILABILITY_CONFLICT.value: (
        "Feasible vessels cannot position and present at load port before laycan closes post-award."
    ),
    ProcurementReasonCode.FORECAST_DATA_UNAVAILABLE.value: (
        "No causal time-series forecast series available for the trade route or commodity."
    ),
    ProcurementReasonCode.FORECAST_HORIZON_INSUFFICIENT.value: (
        "Required procurement horizon exceeds maximum model forecast horizon (30 days)."
    ),
    ProcurementReasonCode.STRATEGY_DURATION_INVALID.value: (
        "Contract strategy duration is incompatible with cargo schedule or voyage sequence."
    ),
    ProcurementReasonCode.INSUFFICIENT_CARGO_COVERAGE.value: (
        "Vessel deadweight or strategy capacity fails to meet required parcel volume."
    ),
    ProcurementReasonCode.CONTRACT_WINDOW_CONFLICT.value: (
        "Period charter commitment window conflicts with protected forward commitments."
    ),
}


def describe_reason_code(code: str) -> str:
    """Returns plain-English description for a machine-readable reason code."""
    return REASON_CODE_DESCRIPTIONS.get(code, f"Unrecognized procurement reason code: {code}")
