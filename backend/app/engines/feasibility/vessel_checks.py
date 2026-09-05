"""
VesselOptima — Feasibility Engine: Vessel & Cargo Checks

Evaluates:
1. Vessel capacity vs cargo volume (with parcel tolerance).
2. Vessel class suitability for commodity parcel size.
3. Vessel dimensions (draft, LOA, beam).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.engines.feasibility.reason_codes import FeasibilityReasonCode


def check_vessel_capacity(
    vessel_capacity: float,
    cargo_volume: float,
    tolerance_pct: float = 0.0,
) -> Tuple[bool, Optional[FeasibilityReasonCode], Dict[str, Any], Optional[str]]:
    """
    Evaluates whether vessel cargo capacity meets cargo demand.
    Returns: (is_pass, reason_code, evidence_dict, warning_message)
    """
    tolerance = max(0.0, float(tolerance_pct or 0.0))
    min_allowable_volume = cargo_volume * (1.0 - (tolerance / 100.0))

    evidence = {
        "constraint": "CARGO_CAPACITY",
        "required_nominal": round(float(cargo_volume), 2),
        "min_required_with_tolerance": round(min_allowable_volume, 2),
        "available_capacity": round(float(vessel_capacity), 2),
        "unit": "MT",
        "tolerance_pct": tolerance,
    }

    if vessel_capacity < min_allowable_volume:
        evidence["status"] = "FAIL"
        evidence["deficit_mt"] = round(min_allowable_volume - vessel_capacity, 2)
        return False, FeasibilityReasonCode.INSUFFICIENT_VESSEL_CAPACITY, evidence, None

    warning = None
    if vessel_capacity < cargo_volume:
        evidence["status"] = "PASS_WITH_TOLERANCE"
        warning = (
            f"Vessel capacity ({vessel_capacity:,.0f} MT) is within allowable "
            f"tolerance (-{tolerance}%) of nominal cargo volume ({cargo_volume:,.0f} MT)."
        )
    else:
        evidence["status"] = "PASS"

    return True, None, evidence, warning


def check_vessel_class_suitability(
    vessel_class_name: Optional[str],
    cargo_volume: float,
    commodity: str,
    vessel_capacity: float,
) -> Tuple[bool, Optional[FeasibilityReasonCode], Dict[str, Any], Optional[str]]:
    """
    Evaluates whether vessel class is operationally suitable for cargo parcel size.
    """
    v_class = (vessel_class_name or "").upper()
    evidence = {
        "constraint": "VESSEL_CLASS_SUITABILITY",
        "vessel_class": v_class or "UNKNOWN",
        "commodity": commodity,
        "cargo_volume": round(float(cargo_volume), 2),
        "vessel_capacity": round(float(vessel_capacity), 2),
    }

    # Minimum threshold rules per class to avoid massive operational mismatch
    # (e.g., booking a Capesize for a 30k MT coastal cargo parcel)
    MIN_PARCEL_BY_CLASS = {
        "CAPESIZE": 100000.0,
        "PANAMAX": 50000.0,
        "SUPRAMAX": 35000.0,
        "HANDYSIZE": 15000.0,
    }

    min_economical_parcel = MIN_PARCEL_BY_CLASS.get(v_class, 0.0)
    evidence["min_economical_parcel_mt"] = min_economical_parcel

    if v_class == "CAPESIZE" and cargo_volume < 70000.0:
        # Severe operational mismatch: Capesize cannot be nominated for small Handysize/Supramax parcels
        evidence["status"] = "FAIL"
        return False, FeasibilityReasonCode.INCOMPATIBLE_VESSEL_TYPE, evidence, None

    warning = None
    if min_economical_parcel > 0 and cargo_volume < min_economical_parcel:
        evidence["status"] = "PASS_WITH_WARNING"
        warning = (
            f"Cargo parcel size ({cargo_volume:,.0f} MT) is below standard benchmark "
            f"for {v_class} class ({min_economical_parcel:,.0f} MT)."
        )
    else:
        evidence["status"] = "PASS"

    return True, None, evidence, warning
