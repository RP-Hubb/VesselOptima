"""
VesselOptima — Employment Engine: Idle State & Cost Exposure Model
Follows Section 5 & 11 of the Phase 6 Specification.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.engines.employment.reason_codes import EmploymentReasonCode, describe_reason_code

# Configured default daily idle rates by vessel class if not in registry
DEFAULT_DAILY_IDLE_RATES = {
    "HANDYSIZE": 5200.0,
    "SUPRAMAX": 6800.0,
    "ULTRAMAX": 7400.0,
    "PANAMAX": 8500.0,
    "KAMSARMAX": 9200.0,
    "CAPESIZE": 11500.0,
    "VLOC": 14000.0,
    "DEFAULT": 7500.0,
}


def evaluate_vessel_idle_state(
    vessel_id: int,
    vessel_name: str,
    vessel_class: str,
    as_of_date: datetime,
    availability_start: Optional[datetime],
    availability_end: Optional[datetime],
    commitments: Optional[List[Dict[str, Any]]] = None,
    daily_operating_cost: Optional[float] = None,
    next_candidate_employment: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates vessel idle state, availability gap, and financial holding cost exposure.
    """
    if not availability_start:
        return {
            "vessel_id": vessel_id,
            "vessel_name": vessel_name,
            "vessel_class": vessel_class,
            "as_of_date": as_of_date.isoformat(),
            "status": "UNAVAILABLE",
            "is_idle": False,
            "reason_code": EmploymentReasonCode.VESSEL_UNAVAILABLE.value,
            "reason_description": describe_reason_code(EmploymentReasonCode.VESSEL_UNAVAILABLE),
            "idle_reason": EmploymentReasonCode.VESSEL_UNAVAILABLE.value,
            "available_days": 0.0,
            "idle_days": 0.0,
            "daily_idle_rate": 0.0,
            "idle_cost": 0.0,
            "cost_source": "DATA_SOURCE_UNAVAILABLE",
            "window_start": as_of_date.isoformat(),
            "window_end": None,
            "next_commitment_id": None,
            "next_commitment_start": None,
            "next_candidate_employment": None,
            "provenance": {
                "package_id": "demo-v1",
                "data_mode": "OFFLINE_DEMO",
            },
        }

    # Resolve next confirmed commitment
    next_comm_id = None
    next_comm_start_dt = None
    if commitments:
        for c in commitments:
            c_start_raw = c.get("commitment_start")
            c_start = (
                datetime.fromisoformat(str(c_start_raw))
                if isinstance(c_start_raw, str)
                else c_start_raw
            )
            if c_start and c_start >= as_of_date:
                if next_comm_start_dt is None or c_start < next_comm_start_dt:
                    next_comm_start_dt = c_start
                    next_comm_id = c.get("id")

    # Determine idle window boundaries
    idle_start = max(availability_start, as_of_date)
    idle_end = next_comm_start_dt or availability_end

    if idle_end and idle_end > idle_start:
        idle_seconds = (idle_end - idle_start).total_seconds()
        idle_days = round(idle_seconds / 86400.0, 2)
    else:
        idle_days = 0.0

    # Rate resolution: prefer canonical operating cost, else class default
    if daily_operating_cost and daily_operating_cost > 0:
        daily_rate = float(daily_operating_cost)
        cost_source = "CANONICAL_REGISTRY"
    else:
        vclass_key = vessel_class.upper() if vessel_class else "DEFAULT"
        daily_rate = DEFAULT_DAILY_IDLE_RATES.get(vclass_key, DEFAULT_DAILY_IDLE_RATES["DEFAULT"])
        cost_source = "ASSUMED_CLASS_DEFAULT"

    idle_cost = round(idle_days * daily_rate, 2)

    # Determine idle reason
    if idle_days > 0:
        if next_comm_start_dt:
            idle_reason = EmploymentReasonCode.VESSEL_IDLE_SCHEDULE_GAP.value
        else:
            idle_reason = EmploymentReasonCode.VESSEL_IDLE_NO_COMMITMENT.value
    else:
        idle_reason = EmploymentReasonCode.VESSEL_COMMITTED.value

    return {
        "vessel_id": vessel_id,
        "vessel_name": vessel_name,
        "vessel_class": vessel_class,
        "as_of_date": as_of_date.isoformat(),
        "status": "IDLE" if idle_days > 0 else "COMMITTED",
        "is_idle": idle_days > 0,
        "reason_code": idle_reason,
        "reason_description": describe_reason_code(idle_reason),
        "idle_reason": idle_reason,
        "available_days": idle_days,
        "idle_days": idle_days,
        "daily_idle_rate": daily_rate,
        "idle_cost": idle_cost,
        "currency": "USD",
        "cost_source": cost_source,
        "window_start": idle_start.isoformat(),
        "window_end": idle_end.isoformat() if idle_end else None,
        "next_commitment_id": next_comm_id,
        "next_commitment_start": next_comm_start_dt.isoformat() if next_comm_start_dt else None,
        "next_candidate_employment": next_candidate_employment,
        "provenance": {
            "package_id": "demo-v1",
            "data_mode": "OFFLINE_DEMO",
            "daily_rate_source": cost_source,
        },
    }
