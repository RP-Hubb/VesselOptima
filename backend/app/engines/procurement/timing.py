"""
VesselOptima — Procurement Timing Model
Follows Section 6 and Section 8 of the Phase 5 Specification.

Combines:
  Current Date (Injectable for determinism)
  + Procurement Lead Time (Sum of administrative stages)
  + Cargo Laycan Start / End
  + Delivery Deadline
  + Vessel Ballast Positioning Days

Produces deterministic timing signals and evidence-backed decision windows.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from app.engines.procurement.lead_time import ProcurementProfile
from app.engines.procurement.reason_codes import ProcurementReasonCode


def parse_date(d: Any) -> date:
    """Safely converts string or datetime or date to date object."""
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        return datetime.strptime(d.split("T")[0], "%Y-%m-%d").date()
    raise ValueError(f"Cannot parse date: {d}")


def evaluate_procurement_timing(
    current_date: date,
    laycan_start: date,
    laycan_end: date,
    delivery_deadline: date,
    profile: ProcurementProfile,
    min_positioning_days: float = 0.0,
    estimated_sailing_days: float = 0.0,
) -> Dict[str, Any]:
    """
    Evaluates timing window feasibility and produces deterministic timing signals.
    """
    lead_time_days = profile.minimum_lead_time_days

    # Validation: laycan start <= laycan end <= delivery deadline
    if laycan_start > laycan_end or laycan_end > delivery_deadline:
        return {
            "is_timing_feasible": False,
            "timing_signal": "WINDOW_INVALID",
            "reason_code": ProcurementReasonCode.PROCUREMENT_WINDOW_INVALID.value,
            "reason_description": "Cargo laycan window or delivery deadline is logically inverted.",
            "lead_time_days": lead_time_days,
            "earliest_procurement_date": current_date.isoformat(),
            "procurement_completion_date": (current_date + timedelta(days=lead_time_days)).isoformat(),
            "latest_safe_procurement_date": None,
            "remaining_decision_window_days": None,
            "evidence": {
                "current_date": current_date.isoformat(),
                "laycan_start": laycan_start.isoformat(),
                "laycan_end": laycan_end.isoformat(),
                "delivery_deadline": delivery_deadline.isoformat(),
                "lead_time_days": lead_time_days,
            },
        }

    # Earliest procurement start is current evaluation date
    earliest_procurement = current_date
    earliest_award_completion = current_date + timedelta(days=int(lead_time_days))
    earliest_vessel_presentation = earliest_award_completion + timedelta(days=int(min_positioning_days))

    # Check 1: Does lead time + positioning miss the laycan end entirely right now?
    if earliest_vessel_presentation > laycan_end:
        return {
            "is_timing_feasible": False,
            "timing_signal": "LEAD_TIME_EXCEEDED",
            "reason_code": ProcurementReasonCode.PROCUREMENT_LEAD_TIME_EXCEEDED.value,
            "reason_description": (
                f"Configured procurement lead time ({lead_time_days}d) plus ballast positioning "
                f"({min_positioning_days}d) reaches load port ({earliest_vessel_presentation.isoformat()}) "
                f"after laycan closes ({laycan_end.isoformat()})."
            ),
            "lead_time_days": lead_time_days,
            "earliest_procurement_date": earliest_procurement.isoformat(),
            "procurement_completion_date": earliest_award_completion.isoformat(),
            "latest_safe_procurement_date": None,
            "remaining_decision_window_days": (laycan_end - earliest_vessel_presentation).days,
            "evidence": {
                "current_date": current_date.isoformat(),
                "lead_time_days": lead_time_days,
                "min_positioning_days": min_positioning_days,
                "earliest_vessel_presentation": earliest_vessel_presentation.isoformat(),
                "laycan_end": laycan_end.isoformat(),
                "days_deficit": (earliest_vessel_presentation - laycan_end).days,
            },
        }

    # Check 2: Delivery deadline check
    estimated_delivery = earliest_vessel_presentation + timedelta(days=int(estimated_sailing_days) + 4) # +4d port turnaround
    if estimated_delivery > delivery_deadline:
        return {
            "is_timing_feasible": False,
            "timing_signal": "DEADLINE_MISSED",
            "reason_code": ProcurementReasonCode.PROCUREMENT_DEADLINE_MISSED.value,
            "reason_description": (
                f"Estimated cargo delivery ({estimated_delivery.isoformat()}) exceeds "
                f"contractual delivery deadline ({delivery_deadline.isoformat()})."
            ),
            "lead_time_days": lead_time_days,
            "earliest_procurement_date": earliest_procurement.isoformat(),
            "procurement_completion_date": earliest_award_completion.isoformat(),
            "latest_safe_procurement_date": None,
            "remaining_decision_window_days": 0,
            "evidence": {
                "estimated_delivery": estimated_delivery.isoformat(),
                "delivery_deadline": delivery_deadline.isoformat(),
            },
        }

    # Latest safe procurement start date:
    # Latest tender launch such that tender award + positioning arrives at or before laycan end
    latest_presentation_target = laycan_end
    latest_safe_procurement = latest_presentation_target - timedelta(
        days=int(lead_time_days + min_positioning_days)
    )

    remaining_window_days = (latest_safe_procurement - current_date).days

    # Determine timing signal
    if remaining_window_days <= 0:
        signal = "IMMEDIATE_PROCURE"
        signal_reason = (
            f"Zero decision buffer remaining. To present vessel before laycan closes ({laycan_end.isoformat()}), "
            f"procurement tender must initiate immediately."
        )
    elif remaining_window_days <= 7:
        signal = "WINDOW_CLOSING"
        signal_reason = (
            f"Procurement window is narrowing. Configured lead time ({lead_time_days}d) leaves "
            f"only {remaining_window_days} days of decision buffer before latest safe launch date."
        )
    else:
        signal = "WINDOW_OPEN"
        signal_reason = (
            f"Procurement window open with {remaining_window_days} days buffer before latest safe "
            f"launch date ({latest_safe_procurement.isoformat()})."
        )

    return {
        "is_timing_feasible": True,
        "timing_signal": signal,
        "reason_code": None,
        "reason_description": signal_reason,
        "lead_time_days": lead_time_days,
        "earliest_procurement_date": earliest_procurement.isoformat(),
        "procurement_completion_date": earliest_award_completion.isoformat(),
        "latest_safe_procurement_date": latest_safe_procurement.isoformat(),
        "remaining_decision_window_days": remaining_window_days,
        "evidence": {
            "current_date": current_date.isoformat(),
            "lead_time_days": lead_time_days,
            "min_positioning_days": min_positioning_days,
            "earliest_award_completion": earliest_award_completion.isoformat(),
            "earliest_vessel_presentation": earliest_vessel_presentation.isoformat(),
            "laycan_start": laycan_start.isoformat(),
            "laycan_end": laycan_end.isoformat(),
            "latest_safe_procurement_date": latest_safe_procurement.isoformat(),
            "remaining_decision_window_days": remaining_window_days,
            "profile_used": profile.profile_id,
        },
    }
