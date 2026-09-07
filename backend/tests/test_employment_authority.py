"""
Regression Test Suite for DEF-001: Commercial Control Authority Gate
Follows Master Build Specification Section 74-105.

Verifies:
1. Authority established -> ALTERNATIVE_EMPLOYMENT can be FEASIBLE.
2. Authority NOT_ESTABLISHED -> ALTERNATIVE_EMPLOYMENT is rejected with EMPLOYMENT_RIGHTS_NOT_ESTABLISHED.
3. Authority UNKNOWN or RESTRICTED -> ALTERNATIVE_EMPLOYMENT is rejected.
4. Positive economic margin does NOT override lack of authority.
5. Reason code is deterministic and matches specification exactly.
"""

import pytest
from datetime import datetime
from app.engines.employment.service import EmploymentService
from app.engines.employment.reason_codes import EmploymentReasonCode


def test_authority_established_permits_alternative_employment(monkeypatch):
    """When commercial control status is ESTABLISHED, alternative employment is admissible."""
    service = EmploymentService()

    # Vessel 1 is a Handysize with established authority
    res = service.evaluate_employment_candidate(
        vessel_id=1,
        cargo_id=4,  # Tuticorin -> Chittagong Cement Clinker
        as_of_date=datetime(2026, 9, 1),
        employment_type="ALTERNATIVE_EMPLOYMENT",
    )

    assert res["employment_control_status"] == "ESTABLISHED"
    assert EmploymentReasonCode.EMPLOYMENT_RIGHTS_NOT_ESTABLISHED.value not in res["failed_reasons"]


def test_authority_not_established_blocks_alternative_employment(monkeypatch):
    """When commercial control status is NOT_ESTABLISHED, candidate must be rejected."""
    service = EmploymentService()

    # Mock vessel to have NOT_ESTABLISHED control status
    original_get_vessel = service._get_vessel

    def mock_get_vessel(vessel_id):
        v = original_get_vessel(vessel_id)
        if v:
            v_copy = dict(v)
            v_copy["employment_control_status"] = "NOT_ESTABLISHED"
            return v_copy
        return None

    monkeypatch.setattr(service, "_get_vessel", mock_get_vessel)

    res = service.evaluate_employment_candidate(
        vessel_id=1,
        cargo_id=4,
        as_of_date=datetime(2026, 9, 1),
        employment_type="ALTERNATIVE_EMPLOYMENT",
    )

    assert res["status"] == "INFEASIBLE"
    assert res["optimization_status"] == "REJECTED"
    assert res["primary_reason_code"] == EmploymentReasonCode.EMPLOYMENT_RIGHTS_NOT_ESTABLISHED.value
    assert "EMPLOYMENT RIGHTS NOT ESTABLISHED" in res["primary_reason_description"]
    assert EmploymentReasonCode.EMPLOYMENT_RIGHTS_NOT_ESTABLISHED.value in res["failed_reasons"]


def test_authority_unknown_or_restricted_blocks_employment(monkeypatch):
    """Authority states 'UNKNOWN' and 'RESTRICTED' must block commercial employment."""
    service = EmploymentService()
    original_get_vessel = service._get_vessel

    for test_status in ["UNKNOWN", "RESTRICTED", "THIRD_PARTY_MANAGED"]:
        def mock_get_vessel(vessel_id):
            v = original_get_vessel(vessel_id)
            if v:
                v_copy = dict(v)
                v_copy["employment_control_status"] = test_status
                return v_copy
            return None

        monkeypatch.setattr(service, "_get_vessel", mock_get_vessel)

        res = service.evaluate_employment_candidate(
            vessel_id=1,
            cargo_id=4,
            as_of_date=datetime(2026, 9, 1),
            employment_type="ALTERNATIVE_EMPLOYMENT",
        )

        assert res["status"] == "INFEASIBLE", f"Status {test_status} should be INFEASIBLE"
        assert res["primary_reason_code"] == EmploymentReasonCode.EMPLOYMENT_RIGHTS_NOT_ESTABLISHED.value


def test_positive_economics_cannot_override_missing_authority(monkeypatch):
    """High positive margin must NOT override missing employment control authority."""
    service = EmploymentService()
    original_get_vessel = service._get_vessel

    def mock_get_vessel(vessel_id):
        v = original_get_vessel(vessel_id)
        if v:
            v_copy = dict(v)
            v_copy["employment_control_status"] = "NOT_ESTABLISHED"
            return v_copy
        return None

    monkeypatch.setattr(service, "_get_vessel", mock_get_vessel)

    res = service.evaluate_employment_candidate(
        vessel_id=1,
        cargo_id=4,
        as_of_date=datetime(2026, 9, 1),
        employment_type="ALTERNATIVE_EMPLOYMENT",
    )

    # Even if gross contribution is positive
    assert res["economics"]["gross_contribution_usd"] > 0
    # Candidate must still be rejected
    assert res["status"] == "INFEASIBLE"
    assert res["optimization_status"] == "REJECTED"
    assert res["primary_reason_code"] == EmploymentReasonCode.EMPLOYMENT_RIGHTS_NOT_ESTABLISHED.value
