"""
Regression Test Suite for DEF-003: Port Physical Feasibility Unknown Handling
Follows Master Build Specification Section B & K.

Verifies:
1. Known safe port constraints -> PASS.
2. Known restrictive port constraints -> FAIL.
3. Missing port constraints in database -> UNKNOWN status, is_pass is False,
   and reason code is PORT_CONSTRAINTS_NOT_RECORDED.
4. Missing constraints cannot produce an implicit green feasibility pass.
"""

import pytest
from app.engines.feasibility.port_checks import evaluate_port_constraints
from app.engines.feasibility.reason_codes import FeasibilityReasonCode


def test_known_compatible_port_passes():
    """Vessel within limits of recorded constraints passes."""
    mock_constraints = [
        {"rule_type": "MAX_DRAFT", "value": 14.5, "unit": "M", "terminal": "Berth 1"},
        {"rule_type": "MAX_LOA", "value": 230.0, "unit": "M", "terminal": "Berth 1"},
        {"rule_type": "MAX_BEAM", "value": 33.0, "unit": "M", "terminal": "Berth 1"},
    ]
    res = evaluate_port_constraints(
        port_id=1,
        port_name="TestPort",
        role="DESTINATION",
        vessel_draft=13.0,
        vessel_loa=220.0,
        vessel_beam=32.0,
        constraints=mock_constraints,
    )
    assert res.is_pass is True
    assert len(res.failed_checks) == 0
    assert len(res.reason_codes) == 0


def test_known_restrictive_port_fails():
    """Vessel exceeding recorded limits fails with specific reason codes."""
    mock_constraints = [
        {"rule_type": "MAX_DRAFT", "value": 12.0, "unit": "M", "terminal": "Berth 1"},
    ]
    res = evaluate_port_constraints(
        port_id=1,
        port_name="TestPort",
        role="DESTINATION",
        vessel_draft=14.0,
        vessel_loa=220.0,
        vessel_beam=32.0,
        constraints=mock_constraints,
    )
    assert res.is_pass is False
    assert FeasibilityReasonCode.VESSEL_DRAFT_EXCEEDS_PORT_LIMIT in res.reason_codes
    assert FeasibilityReasonCode.DESTINATION_PORT_INFEASIBLE in res.reason_codes


def test_missing_port_constraints_returns_unknown_and_fails():
    """DEF-003: When constraints are missing, engine must return UNKNOWN and fail."""
    res = evaluate_port_constraints(
        port_id=999,
        port_name="UnchartedPort",
        role="DESTINATION",
        vessel_draft=14.0,
        vessel_loa=220.0,
        vessel_beam=32.0,
        constraints=[],  # Zero constraints recorded
    )

    assert res.is_pass is False, "Missing port constraints must NOT result in an implicit pass."
    assert FeasibilityReasonCode.PORT_CONSTRAINTS_NOT_RECORDED in res.reason_codes
    assert "destination_constraints" in res.failed_checks
    check_detail = res.checks["destination_constraints"]
    assert check_detail["status"] == "UNKNOWN"
    assert "Physical navigation constraints" in check_detail["message"]
    assert check_detail["reason_code"] == FeasibilityReasonCode.PORT_CONSTRAINTS_NOT_RECORDED.value
