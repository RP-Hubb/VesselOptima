"""
VesselOptima — Feasibility Engine: Schedule, Availability & Commitment Checks

Evaluates:
1. Vessel availability location and timestamp.
2. Ballast positioning voyage from current port to load port.
3. Cargo loading window feasibility (ETA_load <= loading_window_end).
4. Estimated turnaround (loading, laden sailing, discharge waiting, discharge).
5. Destination arrival vs cargo delivery deadline.
6. Hard conflict checking against confirmed existing vessel commitments.

Follows Sections 14, 15, 16, 17, 18 of the Phase 4 Specification.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.engines.feasibility.reason_codes import FeasibilityReasonCode


def calculate_great_circle_distance_nm(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Computes great-circle nautical distance between two geographical coordinates
    with standard maritime route detour multiplier (1.15).
    """
    R_NM = 3440.065  # Earth radius in nautical miles
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    direct_nm = R_NM * c
    # Standard maritime route factor for coastal and navigational contours
    return round(direct_nm * 1.15, 1)


class ScheduleCheckResult:
    def __init__(self):
        self.is_pass = True
        self.failed_checks: List[str] = []
        self.reason_codes: List[FeasibilityReasonCode] = []
        self.checks: Dict[str, Dict[str, Any]] = {}
        self.warnings: List[str] = []
        self.timing: Dict[str, Any] = {}


def evaluate_schedule_and_commitments(
    vessel_id: int,
    vessel_speed_laden: float,
    vessel_speed_ballast: float,
    available_at: Optional[datetime],
    current_port_id: Optional[int],
    current_port_coords: Optional[Tuple[float, float]],
    origin_port_id: int,
    origin_port_coords: Optional[Tuple[float, float]],
    loading_window_start: datetime,
    loading_window_end: datetime,
    delivery_deadline: datetime,
    route_distance_nm: float,
    cargo_volume_mt: float,
    commitments: List[Any],  # List of VesselCommitment models or dicts
    direct_positioning_distance_nm: Optional[float] = None,
) -> ScheduleCheckResult:
    """
    Evaluates complete voyage timeline, availability, positioning, deadline,
    and commitments.
    """
    res = ScheduleCheckResult()

    # 1. Base Availability Check
    if not available_at:
        res.is_pass = False
        res.failed_checks.append("vessel_availability")
        res.reason_codes.append(FeasibilityReasonCode.VESSEL_NOT_AVAILABLE)
        res.checks["vessel_availability"] = {
            "status": "FAIL",
            "message": "No availability event or position recorded for vessel.",
        }
        return res

    ballast_speed = float(vessel_speed_ballast or 13.0)
    laden_speed = float(vessel_speed_laden or 12.5)

    # 2. Positioning Voyage Calculation
    positioning_nm = 0.0
    positioning_source = "SAME_PORT"

    if current_port_id and current_port_id == origin_port_id:
        positioning_nm = 0.0
        positioning_source = "SAME_PORT"
    elif direct_positioning_distance_nm is not None and direct_positioning_distance_nm > 0:
        positioning_nm = float(direct_positioning_distance_nm)
        positioning_source = "CANONICAL_ROUTE_TABLE"
    elif current_port_coords and origin_port_coords:
        positioning_nm = calculate_great_circle_distance_nm(
            current_port_coords[0],
            current_port_coords[1],
            origin_port_coords[0],
            origin_port_coords[1],
        )
        positioning_source = "DERIVED_GREAT_CIRCLE"
    else:
        positioning_nm = 500.0  # Conservative nominal fallback
        positioning_source = "DEFAULT_ASSUMPTION"
        res.warnings.append(
            "Current vessel port location coordinates unavailable; applied nominal 500 NM positioning assumption."
        )

    positioning_hours = positioning_nm / max(1.0, ballast_speed)
    positioning_days = round(positioning_hours / 24.0, 2)
    eta_load = available_at + timedelta(days=positioning_days)

    res.timing["available_at"] = available_at.isoformat()
    res.timing["positioning_distance_nm"] = positioning_nm
    res.timing["positioning_source"] = positioning_source
    res.timing["speed_ballast_knots"] = ballast_speed
    res.timing["positioning_days"] = positioning_days
    res.timing["eta_load_port"] = eta_load.isoformat()
    res.timing["loading_window_start"] = loading_window_start.isoformat()
    res.timing["loading_window_end"] = loading_window_end.isoformat()

    # 3. Loading Window Verification
    evidence_load_win = {
        "constraint": "LOADING_WINDOW",
        "eta_load_port": eta_load.isoformat(),
        "loading_window_start": loading_window_start.isoformat(),
        "loading_window_end": loading_window_end.isoformat(),
        "positioning_days": positioning_days,
    }

    if eta_load > loading_window_end:
        res.is_pass = False
        res.failed_checks.append("loading_window")
        res.reason_codes.append(FeasibilityReasonCode.VESSEL_NOT_AVAILABLE)
        if FeasibilityReasonCode.LOADING_WINDOW_INVALID not in res.reason_codes:
            res.reason_codes.append(FeasibilityReasonCode.LOADING_WINDOW_INVALID)
        evidence_load_win["status"] = "FAIL"
        evidence_load_win["hours_late"] = round(
            (eta_load - loading_window_end).total_seconds() / 3600.0, 1
        )
    else:
        evidence_load_win["status"] = "PASS"
        if eta_load < loading_window_start:
            hours_early = round(
                (loading_window_start - eta_load).total_seconds() / 3600.0, 1
            )
            evidence_load_win["hours_early"] = hours_early
            res.warnings.append(
                f"Vessel arrives {hours_early:.1f}h before laycan opens; waiting at anchorage."
            )

    res.checks["loading_window"] = evidence_load_win

    # 4. Voyage & Turnaround Durations
    # Bulk loading duration (~30k MT / day, min 1.5d)
    loading_days = round(max(1.5, cargo_volume_mt / 30000.0), 2)
    # Laden transit
    sailing_hours = route_distance_nm / max(1.0, laden_speed)
    sailing_days = round(sailing_hours / 24.0, 2)
    # Expected port waiting & congestion buffer (~2 days default benchmark)
    waiting_days = 2.0
    # Bulk discharge duration (~25k MT / day, min 1.5d)
    discharge_days = round(max(1.5, cargo_volume_mt / 25000.0), 2)

    load_start = max(loading_window_start, eta_load)
    departure_origin = load_start + timedelta(days=loading_days)
    arrival_destination = departure_origin + timedelta(days=sailing_days + waiting_days)
    discharge_completion = arrival_destination + timedelta(days=discharge_days)

    res.timing["loading_days"] = loading_days
    res.timing["departure_origin"] = departure_origin.isoformat()
    res.timing["route_distance_nm"] = route_distance_nm
    res.timing["speed_laden_knots"] = laden_speed
    res.timing["sailing_days"] = sailing_days
    res.timing["expected_waiting_days"] = waiting_days
    res.timing["arrival_destination"] = arrival_destination.isoformat()
    res.timing["discharge_days"] = discharge_days
    res.timing["discharge_completion"] = discharge_completion.isoformat()
    res.timing["delivery_deadline"] = delivery_deadline.isoformat()

    # 5. Delivery Deadline Verification
    evidence_deadline = {
        "constraint": "DELIVERY_DEADLINE",
        "estimated_arrival": arrival_destination.isoformat(),
        "delivery_deadline": delivery_deadline.isoformat(),
        "total_transit_days": round(sailing_days + waiting_days, 2),
    }

    if arrival_destination > delivery_deadline:
        res.is_pass = False
        res.failed_checks.append("delivery_deadline")
        res.reason_codes.append(FeasibilityReasonCode.DEADLINE_MISSED)
        if FeasibilityReasonCode.VOYAGE_TIME_INFEASIBLE not in res.reason_codes:
            res.reason_codes.append(FeasibilityReasonCode.VOYAGE_TIME_INFEASIBLE)
        evidence_deadline["status"] = "FAIL"
        evidence_deadline["days_overdue"] = round(
            (arrival_destination - delivery_deadline).total_seconds() / 86400.0, 2
        )
    else:
        evidence_deadline["status"] = "PASS"
        evidence_deadline["buffer_days"] = round(
            (delivery_deadline - arrival_destination).total_seconds() / 86400.0, 2
        )

    res.checks["delivery_deadline"] = evidence_deadline

    # 6. Existing Vessel Commitments (Hard Operational Constraint)
    voyage_window_start = available_at
    voyage_window_end = discharge_completion

    conflicts = []
    for c in commitments:
        c_start = getattr(c, "commitment_start", None) or (c.get("commitment_start") if isinstance(c, dict) else None)
        c_end = getattr(c, "commitment_end", None) or (c.get("commitment_end") if isinstance(c, dict) else None)
        c_desc = getattr(c, "route_description", "") or (c.get("route_description", "") if isinstance(c, dict) else "")
        c_id = getattr(c, "id", None) or (c.get("id") if isinstance(c, dict) else None)

        if not c_start:
            continue

        # Parse if string
        if isinstance(c_start, str):
            c_start = datetime.fromisoformat(c_start)
        if isinstance(c_end, str):
            c_end = datetime.fromisoformat(c_end)
        elif not c_end:
            c_end = c_start + timedelta(days=30)  # Default assumption if unbounded

        # Overlap condition:
        # Proposed voyage is active during [voyage_window_start, voyage_window_end].
        # Commitment is active during [c_start, c_end].
        # Overlap exists if max(start1, start2) < min(end1, end2).
        if max(voyage_window_start, c_start) < min(voyage_window_end, c_end):
            conflicts.append({
                "commitment_id": c_id,
                "description": c_desc,
                "commitment_start": c_start.isoformat(),
                "commitment_end": c_end.isoformat(),
                "voyage_window_start": voyage_window_start.isoformat(),
                "voyage_window_end": voyage_window_end.isoformat(),
            })

    if conflicts:
        res.is_pass = False
        res.failed_checks.append("vessel_commitments")
        if FeasibilityReasonCode.VESSEL_COMMITMENT_CONFLICT not in res.reason_codes:
            res.reason_codes.append(FeasibilityReasonCode.VESSEL_COMMITMENT_CONFLICT)
        res.checks["vessel_commitments"] = {
            "status": "FAIL",
            "conflicts_count": len(conflicts),
            "conflicts": conflicts,
            "message": f"Vessel has {len(conflicts)} confirmed commitment(s) conflicting with proposed voyage window.",
        }
    else:
        res.checks["vessel_commitments"] = {
            "status": "PASS",
            "message": "No conflicting fixture or charter commitments identified.",
        }

    return res
