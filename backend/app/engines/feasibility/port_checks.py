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
    fail_on_unrecorded: bool = False,
) -> PortCheckResult:
    """
    Evaluates all physical constraints for a single port role (Origin or Destination).
    """
    result = PortCheckResult(port_id=port_id, port_name=port_name, role=role)

    # If no specific constraints exist in the database for this port, mark as UNKNOWN / BLOCKED
    if not constraints:
        result.is_pass = False
        result.failed_checks.append(f"{role.lower()}_constraints")
        result.reason_codes.append(FeasibilityReasonCode.PORT_CONSTRAINTS_NOT_RECORDED)
        result.checks[f"{role.lower()}_constraints"] = {
            "status": "UNKNOWN",
            "message": f"Physical navigation constraints (draft, LOA, beam) not recorded for {port_name} ({role}); navigation clearance unverified.",
            "port_name": port_name,
            "role": role,
            "reason_code": FeasibilityReasonCode.PORT_CONSTRAINTS_NOT_RECORDED.value,
        }
        return result

    draft_failed = False
    loa_failed = False
    beam_failed = False
    checked_rules = set()

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
            checked_rules.add("MAX_DRAFT")
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
            checked_rules.add("MAX_LOA")
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
            checked_rules.add("MAX_BEAM")
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

    # Explicitly record unrecorded mandatory navigation dimensions (DEF-003 partial constraint hardening)
    mandatory_specs = [
        ("MAX_DRAFT", vessel_draft, "draft", FeasibilityReasonCode.VESSEL_DRAFT_EXCEEDS_PORT_LIMIT),
        ("MAX_LOA", vessel_loa, "loa", FeasibilityReasonCode.VESSEL_LOA_EXCEEDS_PORT_LIMIT),
        ("MAX_BEAM", vessel_beam, "beam", FeasibilityReasonCode.VESSEL_BEAM_EXCEEDS_PORT_LIMIT),
    ]

    for rule_type, req_val, dim_name, fail_code in mandatory_specs:
        rule_key = f"{role.lower()}_{rule_type.lower()}"
        if rule_type not in checked_rules:
            evidence = {
                "constraint": rule_type,
                "role": role,
                "port_id": port_id,
                "port_name": port_name,
                f"required_{dim_name}": round(req_val, 2),
                f"permitted_{dim_name}": None,
                "unit": "M",
                "status": "NOT_RECORDED",
                "reason_code": FeasibilityReasonCode.PORT_CONSTRAINTS_NOT_RECORDED.value,
                "message": f"Physical {rule_type} limit is not recorded for {port_name} ({role}); clearance unverified.",
            }
            result.checks[rule_key] = evidence
            result.warnings.append(
                f"[{role} - {port_name}] {rule_type} constraint not recorded in berth schedule; clearance unverified."
            )

            # Global physical threshold validation: absurdly oversized vessels (e.g. LOA > 365m, beam > 65m)
            # exceeding the largest dry bulk vessel ever built (Valemax 362m) fail unconditionally
            if (rule_type == "MAX_LOA" and req_val > 365.0) or (rule_type == "MAX_BEAM" and req_val > 65.0):
                result.is_pass = False
                evidence["status"] = "FAIL"
                evidence["message"] = (
                    f"Vessel {dim_name.upper()} ({req_val:.1f}m) exceeds global maximum physical limit "
                    f"for commercial bulk berths (365m LOA / 65m Beam); unrecorded clearance cannot pass."
                )
                result.failed_checks.append(rule_key)
                if fail_code not in result.reason_codes:
                    result.reason_codes.append(fail_code)
            elif fail_on_unrecorded:
                result.is_pass = False
                result.failed_checks.append(rule_key)
                if FeasibilityReasonCode.PORT_CONSTRAINTS_NOT_RECORDED not in result.reason_codes:
                    result.reason_codes.append(FeasibilityReasonCode.PORT_CONSTRAINTS_NOT_RECORDED)

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
