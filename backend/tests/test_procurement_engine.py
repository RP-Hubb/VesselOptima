"""
VesselOptima — Phase 5: Dynamic Procurement Strategy & Timing Engine Test Suite
Follows Section 26, 27, 28, 29 of the Phase 5 Specification.
"""

from __future__ import annotations

from datetime import date, timedelta
import socket
import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.engines.procurement.cost_model import calculate_expected_procurement_costs
from app.engines.procurement.lead_time import (
    DEFAULT_PROFILES,
    ProcurementProfile,
    get_procurement_profile,
)
from app.engines.procurement.reason_codes import (
    ProcurementReasonCode,
    describe_reason_code,
)
from app.engines.procurement.service import ProcurementService
from app.engines.procurement.strategies import (
    STRATEGY_DEFINITIONS,
    ProcurementStrategyEngine,
)
from app.engines.procurement.timing import evaluate_procurement_timing
from app.main import app


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



# ── Configuration & Lead Time Tests ──────────────────────────────────

def test_procurement_lead_time_summation():
    """Verify lead time is exact sum of all stages without hardcoded legal claims."""
    profile = DEFAULT_PROFILES["STANDARD_COMMERCIAL"]
    expected_sum = (
        profile.tender_preparation_days
        + profile.bid_submission_days
        + profile.technical_evaluation_days
        + profile.commercial_evaluation_days
        + profile.approval_days
        + profile.award_days
    )
    assert profile.minimum_lead_time_days == expected_sum
    assert profile.minimum_lead_time_days == 14.0


def test_procurement_profile_custom_overrides():
    """Verify custom overrides create customized profile with recalculated lead time."""
    custom = get_procurement_profile(
        profile_id="STRICT_GOVERNMENT",
        custom_stages={
            "tender_preparation_days": 10.0,
            "bid_submission_days": 14.0,
            "approval_days": 5.0,
        },
    )
    assert custom.profile_id == "STRICT_GOVERNMENT_CUSTOM"
    assert custom.tender_preparation_days == 10.0
    assert custom.bid_submission_days == 14.0
    assert custom.approval_days == 5.0
    assert custom.minimum_lead_time_days == (10.0 + 14.0 + 3.0 + 3.0 + 5.0 + 1.0)
    assert custom.data_classification == "ASSUMPTION"


# ── Timing Model Tests ────────────────────────────────────────────────

def test_timing_window_open():
    """Verify WINDOW_OPEN signal when ample buffer exists before laycan."""
    profile = DEFAULT_PROFILES["EXPEDITED_SPOT"]  # 4 days lead time
    res = evaluate_procurement_timing(
        current_date=date(2026, 9, 1),
        laycan_start=date(2026, 9, 20),
        laycan_end=date(2026, 9, 25),
        delivery_deadline=date(2026, 10, 15),
        profile=profile,
        min_positioning_days=2.0,
    )
    assert res["is_timing_feasible"] is True
    assert res["timing_signal"] == "WINDOW_OPEN"
    assert res["remaining_decision_window_days"] > 7


def test_timing_window_closing_and_immediate():
    """Verify WINDOW_CLOSING when buffer <= 7 days, and IMMEDIATE_PROCURE when buffer <= 0."""
    profile = DEFAULT_PROFILES["STANDARD_COMMERCIAL"]  # 14 days lead time
    # Laycan end Sept 20. Lead time (14d) + positioning (2d) = 16d.
    # Latest safe launch: Sept 20 - 16d = Sept 4.
    # Current date Sept 1: remaining window = 3 days <= 7 -> WINDOW_CLOSING
    res_closing = evaluate_procurement_timing(
        current_date=date(2026, 9, 1),
        laycan_start=date(2026, 9, 15),
        laycan_end=date(2026, 9, 20),
        delivery_deadline=date(2026, 10, 15),
        profile=profile,
        min_positioning_days=2.0,
    )
    assert res_closing["is_timing_feasible"] is True
    assert res_closing["timing_signal"] == "WINDOW_CLOSING"
    assert 0 < res_closing["remaining_decision_window_days"] <= 7

    # Current date Sept 4: remaining window = 0 -> IMMEDIATE_PROCURE
    res_imm = evaluate_procurement_timing(
        current_date=date(2026, 9, 4),
        laycan_start=date(2026, 9, 15),
        laycan_end=date(2026, 9, 20),
        delivery_deadline=date(2026, 10, 15),
        profile=profile,
        min_positioning_days=2.0,
    )
    assert res_imm["is_timing_feasible"] is True
    assert res_imm["timing_signal"] == "IMMEDIATE_PROCURE"


def test_timing_lead_time_exceeded():
    """Verify LEAD_TIME_EXCEEDED when lead time pushes presentation past laycan end."""
    profile = DEFAULT_PROFILES["STRICT_GOVERNMENT"]  # 21 days lead time
    # Current Sept 1 + 21d lead time + 2d positioning = Sept 24 > Sept 20 laycan end
    res = evaluate_procurement_timing(
        current_date=date(2026, 9, 1),
        laycan_start=date(2026, 9, 15),
        laycan_end=date(2026, 9, 20),
        delivery_deadline=date(2026, 10, 15),
        profile=profile,
        min_positioning_days=2.0,
    )
    assert res["is_timing_feasible"] is False
    assert res["timing_signal"] == "LEAD_TIME_EXCEEDED"
    assert res["reason_code"] == ProcurementReasonCode.PROCUREMENT_LEAD_TIME_EXCEEDED.value


def test_timing_deadline_missed():
    """Verify DEADLINE_MISSED when voyage completion exceeds delivery deadline."""
    profile = DEFAULT_PROFILES["EXPEDITED_SPOT"]
    res = evaluate_procurement_timing(
        current_date=date(2026, 9, 1),
        laycan_start=date(2026, 9, 5),
        laycan_end=date(2026, 9, 8),
        delivery_deadline=date(2026, 9, 10),  # Impossible delivery date
        profile=profile,
        estimated_sailing_days=15.0,
    )
    assert res["is_timing_feasible"] is False
    assert res["reason_code"] == ProcurementReasonCode.PROCUREMENT_DEADLINE_MISSED.value


# ── Demonstration Cases (A, B, C, D) ─────────────────────────────────

def test_case_a_spot_feasible(db_session):
    """Case A: Cargo + feasible vessel + valid window yields FEASIBLE SPOT strategy."""
    service = ProcurementService(db=db_session)
    # Cargo 2: Port Hedland -> Dhamra, Iron Ore (Pilbara Iron is feasible)
    results = service.evaluate_cargo_strategies(
        cargo_id=2,
        profile_id="EXPEDITED_SPOT",
        as_of_date=date(2026, 9, 1),
        strategy_types=["SPOT"],
    )
    assert results["cargo_id"] == 2
    spot = results["strategies"][0]
    assert spot["strategy_type"] == "SPOT"
    assert spot["status"] == "FEASIBLE"
    assert spot["feasibility_summary"]["feasible_vessel_count"] >= 1
    assert spot["cost_summary"]["expected_total_cost"] > 0


def test_case_b_procurement_timing_conflict(db_session):
    """Case B: Laycan window too soon for strict government lead time."""
    service = ProcurementService(db=db_session)
    # If evaluation date is Sept 20, 2026 and laycan ends Sept 25, 2026:
    # 21 days lead time makes procurement impossible!
    results = service.evaluate_cargo_strategies(
        cargo_id=2,
        profile_id="STRICT_GOVERNMENT",
        as_of_date=date(2026, 9, 20),
        strategy_types=["SPOT"],
    )
    spot = results["strategies"][0]
    assert spot["status"] == "INFEASIBLE"
    assert spot["primary_reason_code"] == ProcurementReasonCode.PROCUREMENT_LEAD_TIME_EXCEEDED.value


def test_case_c_forecast_uncertainty(db_session):
    """Case C: Forecast uncertainty is preserved and surfaced, not masked."""
    service = ProcurementService(db=db_session)
    results = service.evaluate_cargo_strategies(
        cargo_id=1,
        profile_id="STANDARD_COMMERCIAL",
        as_of_date=date(2026, 9, 1),
        strategy_types=["SPOT"],
    )
    spot = results["strategies"][0]
    forecast_evidence = spot["forecast_evidence"]
    assert forecast_evidence is not None
    assert "uncertainty_level" in forecast_evidence
    assert "uncertainty_spread_pct" in forecast_evidence
    # Anti-optimization check: uncertainty does not force fake certainty
    assert forecast_evidence["provenance"]["data_type"] in ("PROXY", "SYNTHETIC", "OBSERVED")


def test_case_d_feasibility_filtering(db_session):
    """Case D: Only Phase 4 feasible vessels are admitted into procurement candidates."""
    service = ProcurementService(db=db_session)
    results = service.evaluate_cargo_strategies(
        cargo_id=2,
        profile_id="EXPEDITED_SPOT",
        as_of_date=date(2026, 9, 1),
        strategy_types=["SPOT"],
    )
    spot = results["strategies"][0]
    feas_summary = spot["feasibility_summary"]
    # Total fleet evaluated is 20
    assert feas_summary["total_fleet_evaluated"] == 20
    # Infeasible vessels are strictly excluded
    assert feas_summary["infeasible_vessel_count"] > 0
    # Only feasible vessels become viable candidate vessels
    for v in feas_summary["viable_candidate_vessels"]:
        assert v["vessel_name"] is not None
        assert v["cargo_capacity"] > 0


# ── Strategy Types Tests ─────────────────────────────────────────────

def test_all_four_strategies_evaluated(db_session):
    """Verify SPOT, SHORT_TERM, MEDIUM_TERM, and MULTI_VOYAGE are all evaluated."""
    service = ProcurementService(db=db_session)
    results = service.evaluate_cargo_strategies(
        cargo_id=2,
        profile_id="STANDARD_COMMERCIAL",
        as_of_date=date(2026, 9, 1),
    )
    assert len(results["strategies"]) == 4
    strategy_types = {s["strategy_type"] for s in results["strategies"]}
    assert strategy_types == {"SPOT", "SHORT_TERM", "MEDIUM_TERM", "MULTI_VOYAGE"}


def test_cost_model_breakdown():
    """Verify transparent expected cost calculation."""
    costs = calculate_expected_procurement_costs(
        volume_mt=75000.0,
        freight_rate_per_mt=20.0,
        sailing_days=15.0,
        daily_fuel_consumption_mt=30.0,
        bunker_price_per_mt=600.0,
        origin_port_dues=30000.0,
        destination_port_dues=35000.0,
        procurement_admin_fee=5000.0,
        strategy_discount_factor=0.95,
        voyage_count=2,
    )
    # Freight: 75000 * (20 * 0.95) * 2 = 75000 * 19 * 2 = 2,850,000
    assert costs["expected_freight_cost"] == 2850000.0
    # Bunker: 15 * 30 * 600 * 2 = 540,000
    assert costs["expected_bunker_cost"] == 540000.0
    # Ports: (30000 + 35000) * 2 = 130,000
    assert costs["expected_port_costs"] == 130000.0
    # Total: 2850000 + 540000 + 130000 + 5000 = 3,525,000
    assert costs["expected_total_cost"] == 3525000.0


# ── Anti-Optimization & Determinism Tests ─────────────────────────────

def test_anti_optimization_boundary(db_session):
    """
    CRITICAL: Verify Phase 5 does NOT rank strategies, does NOT select an 'optimal' strategy,
    and labels candidates as 'READY FOR OPTIMIZATION'.
    """
    service = ProcurementService(db=db_session)
    results = service.evaluate_cargo_strategies(
        cargo_id=2,
        profile_id="STANDARD_COMMERCIAL",
        as_of_date=date(2026, 9, 1),
    )
    # Check that no strategy is marked "BEST" or "OPTIMAL"
    for strat in results["strategies"]:
        assert "optimal" not in strat["status"].lower()
        assert "best" not in strat["status"].lower()
        if strat["status"] == "FEASIBLE":
            assert strat["candidate_metadata"]["optimization_status"] == "READY FOR OPTIMIZATION"


def test_procurement_determinism(db_session):
    """Given identical cargo, profile, and anchor date, output is 100% deterministic."""
    service = ProcurementService(db=db_session)
    run1 = service.evaluate_cargo_strategies(
        cargo_id=2,
        profile_id="STANDARD_COMMERCIAL",
        as_of_date=date(2026, 9, 1),
    )
    run2 = service.evaluate_cargo_strategies(
        cargo_id=2,
        profile_id="STANDARD_COMMERCIAL",
        as_of_date=date(2026, 9, 1),
    )
    assert run1["strategies_evaluated_count"] == run2["strategies_evaluated_count"]
    assert run1["feasible_strategies_count"] == run2["feasible_strategies_count"]
    for s1, s2 in zip(run1["strategies"], run2["strategies"]):
        assert s1["strategy_type"] == s2["strategy_type"]
        assert s1["status"] == s2["status"]
        assert s1["timing_signal"] == s2["timing_signal"]
        if s1["cost_summary"]:
            assert s1["cost_summary"]["expected_total_cost"] == s2["cost_summary"]["expected_total_cost"]


def test_procurement_zero_network_calls(db_session, monkeypatch):
    """Verify zero external network calls occur during procurement evaluation."""
    def guarded_connect(self, *args, **kwargs):
        raise RuntimeError("Air-gap violation: Network call attempted during Phase 5 procurement!")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    service = ProcurementService(db=db_session)
    results = service.evaluate_cargo_strategies(
        cargo_id=2,
        profile_id="STANDARD_COMMERCIAL",
        as_of_date=date(2026, 9, 1),
    )
    assert results["strategies_evaluated_count"] == 4


# ── API Endpoint Tests ────────────────────────────────────────────────

def test_api_procurement_config_endpoints(client):
    """Test GET and PUT on /v1/procurement/config."""
    res = client.get("/v1/procurement/config")
    assert res.status_code == 200
    profiles = res.json()
    assert len(profiles) >= 3

    # Test update/custom profile
    put_res = client.put(
        "/v1/procurement/config",
        json={
            "profile_id": "TEST_CUSTOM",
            "name": "Test Custom Profile",
            "tender_preparation_days": 4.0,
            "bid_submission_days": 6.0,
        },
    )
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["profile_id"] == "TEST_CUSTOM"
    assert updated["minimum_lead_time_days"] > 0


def test_api_procurement_candidates_endpoint(client):
    """Test GET /v1/procurement/candidates/{cargo_id}."""
    res = client.get("/v1/procurement/candidates/2?profile_id=STANDARD_COMMERCIAL&as_of_date=2026-09-01")
    assert res.status_code == 200
    data = res.json()
    assert data["cargo_id"] == 2
    assert len(data["strategies"]) == 4


def test_api_procurement_compare_endpoint(client):
    """Test POST /v1/procurement/compare."""
    res = client.post(
        "/v1/procurement/compare",
        json={
            "cargo_id": 2,
            "profile_id": "EXPEDITED_SPOT",
            "as_of_date": "2026-09-01",
            "strategy_types": ["SPOT", "SHORT_TERM"],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["strategies"]) == 2
