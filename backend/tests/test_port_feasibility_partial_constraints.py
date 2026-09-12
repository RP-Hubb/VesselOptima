"""
Regression Test Suite for Finding 3: Partial and Missing Port Physical Constraints.

Verifies:
1. Partial constraints never silently omit or silently PASS unrecorded dimensions.
2. Every mandatory dimension (MAX_DRAFT, MAX_LOA, MAX_BEAM) is explicitly recorded in checks.
3. Unrecorded dimensions are explicitly stamped with status="NOT_RECORDED" and advisory warnings.
4. Absurdly oversized vessels (LOA > 365m, beam > 65m) fail unconditionally even on unrecorded ports.
5. Strict / fail_on_unrecorded mode fails closed with PORT_CONSTRAINTS_NOT_RECORDED.
"""

import pytest
from app.engines.feasibility.port_checks import evaluate_port_constraints
from app.engines.feasibility.reason_codes import FeasibilityReasonCode


def test_partial_constraints_do_not_silently_pass_unrecorded_dimensions():
    """
    Port 7 has only MAX_DRAFT in berth schedule.
    Evaluating a standard vessel must record all three dimensions:
    - MAX_DRAFT with PASS
    - MAX_LOA with NOT_RECORDED (not silent pass)
    - MAX_BEAM with NOT_RECORDED (not silent pass)
    """
    port7_constraints = [
        {"rule_type": "MAX_DRAFT", "value": 15.2, "unit": "M", "terminal": "K4"}
    ]

    res = evaluate_port_constraints(
        port_id=7,
        port_name="PWCS Kooragang",
        role="ORIGIN",
        vessel_draft=14.0,
        vessel_loa=225.0,
        vessel_beam=32.2,
        constraints=port7_constraints,
    )

    # All 3 dimensions must be present in checks
    assert "origin_max_draft" in res.checks
    assert "origin_max_loa" in res.checks
    assert "origin_max_beam" in res.checks

    # Draft passed with recorded evidence
    assert res.checks["origin_max_draft"]["status"] == "PASS"
    assert res.checks["origin_max_draft"]["permitted_draft"] == 15.2

    # LOA and Beam must NOT silently pass — they are NOT_RECORDED
    assert res.checks["origin_max_loa"]["status"] == "NOT_RECORDED"
    assert res.checks["origin_max_loa"]["reason_code"] == FeasibilityReasonCode.PORT_CONSTRAINTS_NOT_RECORDED.value
    assert res.checks["origin_max_beam"]["status"] == "NOT_RECORDED"
    assert res.checks["origin_max_beam"]["reason_code"] == FeasibilityReasonCode.PORT_CONSTRAINTS_NOT_RECORDED.value

    # Warnings must explicitly alert operators to unverified dimensions
    assert any("MAX_LOA" in w for w in res.warnings)
    assert any("MAX_BEAM" in w for w in res.warnings)


def test_absurdly_oversized_vessel_fails_on_partial_port():
    """
    Deliberately absurd vessel (LOA 400m, beam 65m) entering Port 7
    (which only records draft) must FAIL, not silently pass.
    """
    port7_constraints = [
        {"rule_type": "MAX_DRAFT", "value": 15.2, "unit": "M", "terminal": "K4"}
    ]

    res = evaluate_port_constraints(
        port_id=7,
        port_name="PWCS Kooragang",
        role="ORIGIN",
        vessel_draft=14.0,
        vessel_loa=400.0,
        vessel_beam=65.0,
        constraints=port7_constraints,
    )

    assert res.is_pass is False, "400m LOA vessel must not pass berth check."
    assert "origin_max_loa" in res.failed_checks
    assert FeasibilityReasonCode.VESSEL_LOA_EXCEEDS_PORT_LIMIT in res.reason_codes
    assert FeasibilityReasonCode.ORIGIN_PORT_INFEASIBLE in res.reason_codes
    assert res.checks["origin_max_loa"]["status"] == "FAIL"


def test_fail_on_unrecorded_mode_fails_closed():
    """When fail_on_unrecorded is enabled, any missing dimension fails the port gate."""
    port7_constraints = [
        {"rule_type": "MAX_DRAFT", "value": 15.2, "unit": "M", "terminal": "K4"}
    ]

    res = evaluate_port_constraints(
        port_id=7,
        port_name="PWCS Kooragang",
        role="ORIGIN",
        vessel_draft=14.0,
        vessel_loa=225.0,
        vessel_beam=32.2,
        constraints=port7_constraints,
        fail_on_unrecorded=True,
    )

    assert res.is_pass is False
    assert "origin_max_loa" in res.failed_checks
    assert "origin_max_beam" in res.failed_checks
    assert FeasibilityReasonCode.PORT_CONSTRAINTS_NOT_RECORDED in res.reason_codes
