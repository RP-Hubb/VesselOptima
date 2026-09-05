"""
VesselOptima — Employment Engine: Chronological Timeline Validation
Follows Section 10 & 17 of the Phase 6 Specification.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.engines.employment.reason_codes import EmploymentReasonCode


def validate_employment_timeline(
    vessel_id: int,
    availability_start: datetime,
    availability_end: Optional[datetime],
    ballast_days: float,
    loading_window_start: datetime,
    loading_window_end: datetime,
    loading_days: float,
    sailing_days: float,
    discharge_days: float,
    delivery_deadline: Optional[datetime],
    commitments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Validates complete chronological voyage timeline and verifies boundaries
    against laycan, deadline, and confirmed vessel commitments.
    """
    failed_checks = []
    reason_codes: List[EmploymentReasonCode] = []
    warnings = []

    # 1. Chronological event projections
    ballast_departure = availability_start
    ballast_arrival = ballast_departure + timedelta(days=ballast_days)

    # Cargo presentation: vessel can only commence loading after laycan opens
    # If vessel arrives early, it waits (idle before); if it arrives inside laycan, loading starts at arrival
    if ballast_arrival < loading_window_start:
        actual_loading_start = loading_window_start
        idle_before_days = round((loading_window_start - ballast_arrival).total_seconds() / 86400.0, 2)
    else:
        actual_loading_start = ballast_arrival
        idle_before_days = 0.0

    loading_end = actual_loading_start + timedelta(days=loading_days)
    voyage_departure = loading_end
    voyage_arrival = voyage_departure + timedelta(days=sailing_days)
    discharge_end = voyage_arrival + timedelta(days=discharge_days)
    employment_end = discharge_end

    total_voyage_days = round(loading_days + sailing_days + discharge_days, 2)
    total_employment_span_days = round(ballast_days + idle_before_days + total_voyage_days, 2)

    # 2. Check: Laycan Compliance (Ballast arrival must be <= loading_window_end)
    if ballast_arrival > loading_window_end:
        failed_checks.append("laycan_cutoff_exceeded")
        reason_codes.append(EmploymentReasonCode.BALLAST_TIME_EXCEEDS_WINDOW)

    # 3. Check: Delivery Deadline Compliance
    if delivery_deadline and discharge_end > delivery_deadline:
        failed_checks.append("delivery_deadline_exceeded")
        reason_codes.append(EmploymentReasonCode.DELIVERY_DEADLINE_UNATTAINABLE)

    # 4. Check: Confirmed Commitment Overlap Conflicts
    conflicts = []
    idle_after_days = 0.0
    next_commitment_id = None
    next_commitment_start_dt = None

    if commitments:
        for c in commitments:
            c_start_raw = c.get("commitment_start")
            c_end_raw = c.get("commitment_end")

            c_start = (
                datetime.fromisoformat(str(c_start_raw))
                if isinstance(c_start_raw, str)
                else c_start_raw
            )
            c_end = (
                datetime.fromisoformat(str(c_end_raw))
                if isinstance(c_end_raw, str)
                else c_end_raw
            ) if c_end_raw else None

            if not c_start:
                continue

            # Check if this commitment is in the future relative to availability
            if c_start >= availability_start:
                if next_commitment_start_dt is None or c_start < next_commitment_start_dt:
                    next_commitment_start_dt = c_start
                    next_commitment_id = c.get("id")

                # Detect overlap: employment completes after commitment start
                if discharge_end > c_start:
                    overlap_seconds = (discharge_end - c_start).total_seconds()
                    overlap_days = round(overlap_seconds / 86400.0, 2)
                    conflicts.append({
                        "conflict_id": c.get("id"),
                        "conflicting_commitment_id": c.get("id"),
                        "description": c.get("route_description") or "Confirmed fixture",
                        "conflict_start": c_start.isoformat(),
                        "commitment_start": c_start.isoformat(),
                        "conflict_end": c_end.isoformat() if c_end else None,
                        "commitment_end": c_end.isoformat() if c_end else None,
                        "candidate_completion": discharge_end.isoformat(),
                        "candidate_discharge_end": discharge_end.isoformat(),
                        "overlap_days": overlap_days,
                    })

    if conflicts:
        failed_checks.append("vessel_commitment_conflict")
        reason_codes.append(EmploymentReasonCode.VESSEL_COMMITMENT_CONFLICT)

    # Compute idle buffer after discharge if next commitment exists
    if next_commitment_start_dt and discharge_end < next_commitment_start_dt:
        idle_after_days = round(
            (next_commitment_start_dt - discharge_end).total_seconds() / 86400.0, 2
        )

    # 5. Check: Availability Horizon
    if availability_end and discharge_end > availability_end:
        warnings.append(
            f"Candidate completion ({discharge_end.date()}) extends past availability horizon ({availability_end.date()})."
        )

    is_feasible = (len(failed_checks) == 0)
    primary_reason = reason_codes[0] if reason_codes else (
        EmploymentReasonCode.EMPLOYMENT_FEASIBLE if is_feasible else EmploymentReasonCode.EMPLOYMENT_WINDOW_MISSED
    )

    return {
        "is_timeline_feasible": is_feasible,
        "primary_reason_code": primary_reason.value,
        "failed_checks": failed_checks,
        "reason_codes": [r.value for r in reason_codes],
        "conflicts": conflicts,
        "warnings": warnings,
        "timing_milestones": {
            "vessel_available_at": availability_start.isoformat(),
            "ballast_departure": ballast_departure.isoformat(),
            "ballast_arrival": ballast_arrival.isoformat(),
            "cargo_laycan_start": loading_window_start.isoformat(),
            "cargo_laycan_end": loading_window_end.isoformat(),
            "loading_start": actual_loading_start.isoformat(),
            "loading_end": loading_end.isoformat(),
            "sailing_start": voyage_departure.isoformat(),
            "sailing_arrival": voyage_arrival.isoformat(),
            "discharge_end": discharge_end.isoformat(),
            "delivery_deadline": delivery_deadline.isoformat() if delivery_deadline else None,
            "next_commitment_id": next_commitment_id,
            "next_commitment_start": next_commitment_start_dt.isoformat() if next_commitment_start_dt else None,
        },
        "duration_breakdown": {
            "ballast_days": ballast_days,
            "idle_before_days": idle_before_days,
            "loading_days": loading_days,
            "sailing_days": sailing_days,
            "discharge_days": discharge_days,
            "total_voyage_days": total_voyage_days,
            "idle_after_days": idle_after_days,
            "total_employment_span_days": total_employment_span_days,
        },
        "commitment_conflicts": conflicts,
    }
