"""
VesselOptima — Feasibility Engine: Port Physical Constraints Checks

Evaluates Origin and Destination ports independently against active constraints:
1. Maximum Permissible Draft (vessel draft vs port/berth limit)
2. Maximum Permissible LOA (vessel LOA vs port/berth limit)
3. Maximum Permissible Beam (vessel beam vs port/berth limit)
4. Tidal, daylight navigation, and pilotage conditions (warnings)

Follows Sections 10, 11, 12 of the Phase 4 Specification.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.engines.feasibility.reason_codes import FeasibilityReasonCode


class PortCheckResult:
    def __init__(
        self,
        port_id: int,
        port_name: str,
        role: str,  # "ORIGIN" or "DESTINATION"
    ):
        self.port_id = port_id
        self.port_name = port_name
        self.role = role
        self.is_pass = True
        self.failed_checks: List[str] = []
        self.reason_codes: List[FeasibilityReasonCode] = []
        self.checks: Dict[str, Dict[str, Any]] = {}
        self.warnings: List[str] = []


def evaluate_port_constraints(
    port_id: int,
    port_name: str,
    role: str,  # "ORIGIN" or "DESTINATION"
    vessel_draft: float,
    vessel_loa: float,
    vessel_beam: float,
    constraints: List[Any],  # List of PortConstraint ORM models or dicts
) -> PortCheckResult:
    """
    Evaluates all physical constraints for a single port role (Origin or Destination).
    """
    result = PortCheckResult(port_id=port_id, port_name=port_name, role=role)

    # If no specific constraints exist in the database for this port, record an explicit check
    if not constraints:
        result.checks[f"{role.lower()}_constraints"] = {
            "status": "PASS",
            "message": f"No restrictive constraints recorded for {port_name} ({role}).",
            "port_name": port_name,
            "role": role,
        }
        return result

    draft_failed = False
    loa_failed = False
    beam_failed = False

    for c in constraints:
        # Support both SQLAlchemy model and dictionary access
        rule_type = getattr(c, "rule_type", None) or (c.get("rule_type") if isinstance(c, dict) else "")
        limit_val = getattr(c, "value", None) or (c.get("value") if isinstance(c, dict) else None)
        unit = getattr(c, "unit", "M") or "M"
        terminal = getattr(c, "terminal", None) or (c.get("terminal") if isinstance(c, dict) else "")
        berth = getattr(c, "berth", None) or (c.get("berth") if isinstance(c, dict) else "")
        condition = getattr(c, "condition", None) or (c.get("condition") if isinstance(c, dict) else "")

        if limit_val is None:
            continue

        limit_val = float(limit_val)
        rule_key = f"{role.lower()}_{rule_type.lower()}"

        # 1. Draft Check
        if rule_type == "MAX_DRAFT":
            evidence = {
                "constraint": "MAX_DRAFT",
                "role": role,
                "port_id": port_id,
                "port_name": port_name,
                "terminal": terminal,
                "berth": berth,
                "required_draft": round(vessel_draft, 2),
                "permitted_draft": round(limit_val, 2),
                "unit": unit,
                "condition": condition,
            }
            if vessel_draft > limit_val:
                result.is_pass = False
                draft_failed = True
                evidence["status"] = "FAIL"
                evidence["excess_draft_m"] = round(vessel_draft - limit_val, 2)
                result.failed_checks.append(rule_key)
                if FeasibilityReasonCode.VESSEL_DRAFT_EXCEEDS_PORT_LIMIT not in result.reason_codes:
                    result.reason_codes.append(FeasibilityReasonCode.VESSEL_DRAFT_EXCEEDS_PORT_LIMIT)
            else:
                evidence["status"] = "PASS"
                evidence["clearance_draft_m"] = round(limit_val - vessel_draft, 2)
            result.checks[rule_key] = evidence

            # Advisory condition warnings (e.g. tidal window required)
            if condition and "tidal" in condition.lower():
                if vessel_draft > 15.0:
                    result.warnings.append(
                        f"[{role} - {port_name}] Deep-draft vessel ({vessel_draft:.1f}m): {condition}"
                    )

        # 2. LOA Check
        elif rule_type == "MAX_LOA":
            evidence = {
                "constraint": "MAX_LOA",
                "role": role,
                "port_id": port_id,
                "port_name": port_name,
                "terminal": terminal,
                "berth": berth,
                "required_loa": round(vessel_loa, 2),
                "permitted_loa": round(limit_val, 2),
                "unit": unit,
                "condition": condition,
            }
            if vessel_loa > limit_val:
                result.is_pass = False
                loa_failed = True
                evidence["status"] = "FAIL"
                evidence["excess_loa_m"] = round(vessel_loa - limit_val, 2)
                result.failed_checks.append(rule_key)
                if FeasibilityReasonCode.VESSEL_LOA_EXCEEDS_PORT_LIMIT not in result.reason_codes:
                    result.reason_codes.append(FeasibilityReasonCode.VESSEL_LOA_EXCEEDS_PORT_LIMIT)
            else:
                evidence["status"] = "PASS"
                evidence["clearance_loa_m"] = round(limit_val - vessel_loa, 2)
            result.checks[rule_key] = evidence

            if condition and "daylight" in condition.lower() and vessel_loa > 225.0:
                result.warnings.append(
                    f"[{role} - {port_name}] LOA ({vessel_loa:.1f}m > 225m): {condition}"
                )

        # 3. Beam Check
        elif rule_type == "MAX_BEAM":
            evidence = {
                "constraint": "MAX_BEAM",
                "role": role,
                "port_id": port_id,
                "port_name": port_name,
                "terminal": terminal,
                "berth": berth,
                "required_beam": round(vessel_beam, 2),
                "permitted_beam": round(limit_val, 2),
                "unit": unit,
                "condition": condition,
            }
            if vessel_beam > limit_val:
                result.is_pass = False
                beam_failed = True
                evidence["status"] = "FAIL"
                evidence["excess_beam_m"] = round(vessel_beam - limit_val, 2)
                result.failed_checks.append(rule_key)
                if FeasibilityReasonCode.VESSEL_BEAM_EXCEEDS_PORT_LIMIT not in result.reason_codes:
                    result.reason_codes.append(FeasibilityReasonCode.VESSEL_BEAM_EXCEEDS_PORT_LIMIT)
            else:
                evidence["status"] = "PASS"
                evidence["clearance_beam_m"] = round(limit_val - vessel_beam, 2)
            result.checks[rule_key] = evidence

    # Add composite port failure code if any constraint failed
    if not result.is_pass:
        composite_code = (
            FeasibilityReasonCode.ORIGIN_PORT_INFEASIBLE
            if role == "ORIGIN"
            else FeasibilityReasonCode.DESTINATION_PORT_INFEASIBLE
        )
        if composite_code not in result.reason_codes:
            result.reason_codes.append(composite_code)

    return result
