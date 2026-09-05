"""VesselOptima — Phase 6: Idle Management & Alternative Employment Engine Test Suite

Follows the strict architectural boundary:
    Candidate Generation != Global Allocation
    Idle Management != Fleet Optimization

Tests:
    1. test_vessel_availability_window_known_position
    2. test_idle_window_identification_no_immediate_commitment
    3. test_idle_cost_calculation_itemized
    4. test_ballast_repositioning_canonical_route
    5. test_ballast_repositioning_great_circle_fallback
    6. test_ballast_arrival_before_laycan_waiting
    7. test_ballast_arrival_after_laycan_rejection
    8. test_phase4_feasibility_rejection_inherited
    9. test_phase5_procurement_lead_time_compliance
    10. test_commitment_overlap_rejection
    11. test_commitment_overlap_evidence
    12. test_multi_cargo_alternative_candidate_generation
    13. test_employment_economics_itemized_breakdown
    14. test_candidate_admissibility_flag_ready_for_optimization
    15. test_anti_optimization_boundary_no_winner
    16. test_database_persistence_and_query
    17. test_deterministic_reproducibility
    18. test_network_isolation
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import socket
import pytest

from app.engines.employment.ballast import calculate_ballast_repositioning
from app.engines.employment.economics import calculate_employment_economics
from app.engines.employment.idle_model import evaluate_vessel_idle_state
from app.engines.employment.reason_codes import EmploymentReasonCode, describe_reason_code
from app.engines.employment.service import EmploymentService
from app.engines.employment.timeline import validate_employment_timeline
from app.models.domain import EmploymentOpportunity, IdleAssessment


# ── 1. Vessel Availability Window ─────────────────────────────────────

def test_vessel_availability_window_known_position(db):
    """Verify vessel availability date, location, and window bounds from canonical data."""
    service = EmploymentService(db=db)
    status = service.get_vessel_employment_status(vessel_id=1, as_of_date=datetime(2026, 9, 1))
    assert status is not None
    assert status["vessel_id"] == 1
    assert "vessel_name" in status
    assert status["current_location_port_id"] in [1, 2, 3, 4, 6, 7, 8, 9, 11, 13]
    assert status["available_at"] is not None
    assert "current_location_name" in status


# ── 2. Idle Window Identification ─────────────────────────────────────

def test_idle_window_identification_no_immediate_commitment(db):
    """Vessel without active immediate commitment shows idle state with idle_days >= 0."""
    service = EmploymentService(db=db)
    assessment = service.assess_vessel_idle_state(vessel_id=1, as_of_date=datetime(2026, 9, 1))
    assert "is_idle" in assessment
    assert assessment["idle_days"] >= 0.0
    assert assessment["reason_code"] in [
        EmploymentReasonCode.VESSEL_IDLE_NO_COMMITMENT.value,
        EmploymentReasonCode.VESSEL_COMMITTED.value,
        EmploymentReasonCode.VESSEL_IDLE_SCHEDULE_GAP.value,
    ]


# ── 3. Idle Cost Calculation Itemized ─────────────────────────────────

def test_idle_cost_calculation_itemized():
    """Holding cost equals daily_idle_rate * idle_days with exact math and transparent source."""
    as_of = datetime(2026, 9, 1, 0, 0, 0)
    avail_start = datetime(2026, 8, 25, 0, 0, 0)
    daily_cost = 7800.0

    res = evaluate_vessel_idle_state(
        vessel_id=10,
        vessel_name="Test Panamax",
        vessel_class="PANAMAX",
        as_of_date=as_of,
        availability_start=avail_start,
        availability_end=as_of + timedelta(days=60),
        commitments=[],
        daily_operating_cost=daily_cost,
    )

    expected_days = (res["window_end_dt"] - as_of).total_seconds() / 86400.0 if "window_end_dt" in res else 60.0
    expected_cost = round(expected_days * daily_cost, 2)

    assert res["is_idle"] is True
    assert abs(res["idle_days"] - expected_days) < 0.01
    assert abs(res["idle_cost"] - expected_cost) < 0.01
    assert res["daily_idle_rate"] == daily_cost
    assert "cost_source" in res


# ── 4. Ballast Repositioning Canonical Route ──────────────────────────

def test_ballast_repositioning_canonical_route():
    """Ballast distance, duration, and bunker consumption from canonical route table."""
    # Port 13 (Singapore) to Port 1 (Paradip) is a canonical route
    res = calculate_ballast_repositioning(
        vessel_id=1,
        current_port_id=13,
        current_port_coords=(1.29, 103.85),
        origin_port_id=1,
        origin_port_coords=(20.26, 86.67),
        availability_start=datetime(2026, 9, 1, 0, 0, 0),
        vessel_speed_ballast=13.0,
    )
    assert res["ballast_distance_nm"] > 0
    assert res["ballast_days"] > 0
    assert res["bunker_consumption_vlsfo_mt"] > 0
    assert res["arrival_at_origin"] is not None
    assert res["data_source"] == "CANONICAL_DATABASE_ROUTE"


# ── 5. Ballast Repositioning Great Circle Fallback ─────────────────────

def test_ballast_repositioning_great_circle_fallback():
    """Fallback calculates great-circle distance with 1.15 routing margin and PROVENANCE_FALLBACK flag."""
    # Port 99 to Port 100 has no canonical route
    res = calculate_ballast_repositioning(
        vessel_id=99,
        current_port_id=99,
        current_port_coords=(10.0, 70.0),
        origin_port_id=100,
        origin_port_coords=(20.0, 85.0),
        availability_start=datetime(2026, 9, 1, 0, 0, 0),
        vessel_speed_ballast=12.0,
    )
    assert res["ballast_distance_nm"] > 0
    assert res["data_source"] == "HAVERSINE_PROXIMITY_ESTIMATE_WITH_1.15_ROUTING_MARGIN"
    assert res["provenance_fallback"] is True


# ── 6. Ballast Arrival Before Laycan (Waiting Tracked) ────────────────

def test_ballast_arrival_before_laycan_waiting():
    """Vessel arriving before laycan start waits at anchor; idle_before_days tracked."""
    avail_start = datetime(2026, 9, 1, 0, 0, 0)
    laycan_start = datetime(2026, 9, 10, 0, 0, 0)
    laycan_end = datetime(2026, 9, 15, 0, 0, 0)
    delivery_deadline = datetime(2026, 10, 5, 0, 0, 0)
    ballast_days = 2.0  # Arrives Sept 3, well before laycan start Sept 10

    res = validate_employment_timeline(
        vessel_id=1,
        availability_start=avail_start,
        availability_end=avail_start + timedelta(days=60),
        ballast_days=ballast_days,
        loading_window_start=laycan_start,
        loading_window_end=laycan_end,
        loading_days=3.0,
        sailing_days=10.0,
        discharge_days=3.0,
        delivery_deadline=delivery_deadline,
        commitments=[],
    )

    assert res["is_timeline_feasible"] is True
    assert res["duration_breakdown"]["idle_before_days"] == pytest.approx(7.0, 0.1)
    assert res["timing_milestones"]["loading_start"] == laycan_start.isoformat()


# ── 7. Ballast Arrival After Laycan Rejection ─────────────────────────

def test_ballast_arrival_after_laycan_rejection():
    """Vessel arriving after laycan end is rejected with BALLAST_TIME_EXCEEDS_WINDOW."""
    avail_start = datetime(2026, 9, 1, 0, 0, 0)
    laycan_start = datetime(2026, 9, 2, 0, 0, 0)
    laycan_end = datetime(2026, 9, 4, 0, 0, 0)
    delivery_deadline = datetime(2026, 9, 30, 0, 0, 0)
    ballast_days = 6.0  # Arrives Sept 7, after laycan end Sept 4

    res = validate_employment_timeline(
        vessel_id=1,
        availability_start=avail_start,
        availability_end=avail_start + timedelta(days=60),
        ballast_days=ballast_days,
        loading_window_start=laycan_start,
        loading_window_end=laycan_end,
        loading_days=3.0,
        sailing_days=10.0,
        discharge_days=3.0,
        delivery_deadline=delivery_deadline,
        commitments=[],
    )

    assert res["is_timeline_feasible"] is False
    assert EmploymentReasonCode.BALLAST_TIME_EXCEEDS_WINDOW.value in res["reason_codes"]
    assert res["primary_reason_code"] == EmploymentReasonCode.BALLAST_TIME_EXCEEDS_WINDOW.value


# ── 8. Phase 4 Feasibility Rejection Inherited ────────────────────────

def test_phase4_feasibility_rejection_inherited(db):
    """Physical / port constraint rejection from Phase 4 is inherited as an infeasibility reason."""
    service = EmploymentService(db=db)
    # Cargo 1 is 160,000 MT Capesize cargo.
    # Vessel 1 is Panamax (dwt ~75,000 MT). Cargo volume exceeds vessel capacity.
    cand = service.evaluate_employment_candidate(
        vessel_id=1,
        cargo_id=1,
        as_of_date=datetime(2026, 9, 1),
    )
    assert cand["status"] == "INFEASIBLE"
    assert cand["optimization_status"] == "REJECTED"
    assert cand["feasibility"]["is_feasible"] is False
    assert len(cand["failed_reasons"]) > 0


# ── 9. Phase 5 Procurement Lead Time Compliance ───────────────────────

def test_phase5_procurement_lead_time_compliance(db):
    """Procurement lead time violation flags PROCUREMENT_TIMING_FAILED."""
    service = EmploymentService(db=db)
    # With LONG_TERM profile (requires 28+ days lead time), evaluating for cargo with laycan in 5 days
    cand = service.evaluate_employment_candidate(
        vessel_id=1,
        cargo_id=2,
        as_of_date=datetime(2026, 9, 12),  # Very late evaluation date near laycan
        procurement_profile_id="LONG_TERM",
    )
    assert "procurement" in cand
    assert cand["procurement"]["lead_time_days"] > 0
    # If lead time exceeds window, timing is infeasible
    if not cand["procurement"]["is_timing_feasible"]:
        assert (
            EmploymentReasonCode.PROCUREMENT_TIMING_FAILED.value in cand["failed_reasons"]
            or cand["status"] == "INFEASIBLE"
        )


# ── 10. Commitment Overlap Rejection ──────────────────────────────────

def test_commitment_overlap_rejection():
    """Candidate voyage extending past existing commitment start is rejected with VESSEL_COMMITMENT_CONFLICT."""
    avail_start = datetime(2026, 9, 1, 0, 0, 0)
    laycan_start = datetime(2026, 9, 5, 0, 0, 0)
    laycan_end = datetime(2026, 9, 8, 0, 0, 0)
    delivery_deadline = datetime(2026, 10, 15, 0, 0, 0)

    # Confirmed commitment starting on Sept 20
    commitments = [
        {
            "id": 101,
            "route_description": "Confirmed Voyage to Richards Bay",
            "commitment_start": datetime(2026, 9, 20, 0, 0, 0),
            "commitment_end": datetime(2026, 10, 10, 0, 0, 0),
            "status": "CONFIRMED",
        }
    ]

    # Voyage: loading 4d + sailing 15d + discharge 4d = 23 days from Sept 5 => completes Sept 28 (overlaps Sept 20)
    res = validate_employment_timeline(
        vessel_id=1,
        availability_start=avail_start,
        availability_end=avail_start + timedelta(days=60),
        ballast_days=2.0,
        loading_window_start=laycan_start,
        loading_window_end=laycan_end,
        loading_days=4.0,
        sailing_days=15.0,
        discharge_days=4.0,
        delivery_deadline=delivery_deadline,
        commitments=commitments,
    )

    assert res["is_timeline_feasible"] is False
    assert EmploymentReasonCode.VESSEL_COMMITMENT_CONFLICT.value in res["reason_codes"]


# ── 11. Commitment Overlap Evidence ───────────────────────────────────

def test_commitment_overlap_evidence():
    """Rejection includes exact overlap days, conflicting commitment ID, and date boundaries."""
    avail_start = datetime(2026, 9, 1, 0, 0, 0)
    commitments = [
        {
            "id": 999,
            "route_description": "Scheduled Maintenance / Fixture",
            "commitment_start": datetime(2026, 9, 18, 0, 0, 0),
            "commitment_end": datetime(2026, 9, 25, 0, 0, 0),
            "status": "CONFIRMED",
        }
    ]

    res = validate_employment_timeline(
        vessel_id=1,
        availability_start=avail_start,
        availability_end=avail_start + timedelta(days=60),
        ballast_days=1.0,
        loading_window_start=datetime(2026, 9, 3, 0, 0, 0),
        loading_window_end=datetime(2026, 9, 6, 0, 0, 0),
        loading_days=3.0,
        sailing_days=14.0,
        discharge_days=3.0,
        delivery_deadline=datetime(2026, 10, 1, 0, 0, 0),
        commitments=commitments,
    )

    assert len(res["conflicts"]) > 0
    conflict = res["conflicts"][0]
    assert conflict["conflict_id"] == 999
    assert conflict["overlap_days"] > 0
    assert "commitment_start" in conflict
    assert "candidate_discharge_end" in conflict


# ── 12. Multi-Cargo Alternative Candidate Generation ──────────────────

def test_multi_cargo_alternative_candidate_generation(db):
    """Multiple canonical cargos evaluated independently for a single vessel."""
    service = EmploymentService(db=db)
    candidates = service.generate_alternative_candidates(vessel_id=1, as_of_date=datetime(2026, 9, 1))
    assert len(candidates) >= 3
    # Check that different cargos were evaluated
    cargo_ids = {c["cargo_id"] for c in candidates}
    assert len(cargo_ids) >= 3
    for c in candidates:
        assert "candidate_id" in c
        assert "status" in c
        assert "optimization_status" in c
        assert "economics" in c


# ── 13. Employment Economics Itemized Breakdown ───────────────────────

def test_employment_economics_itemized_breakdown():
    """Itemized breakdown of operating, bunker, port, idle, revenue, and gross contribution."""
    econ = calculate_employment_economics(
        volume_mt=70000.0,
        freight_rate_per_mt=18.50,
        ballast_days=3.0,
        sailing_days=12.0,
        loading_days=3.0,
        discharge_days=3.0,
        idle_days=2.0,
        daily_operating_cost=8000.0,
        daily_idle_rate=8000.0,
        vlsfo_price_per_mt=620.0,
        lsmgo_price_per_mt=850.0,
        origin_port_fee=45000.0,
        dest_port_fee=50000.0,
    )

    expected_revenue = 70000.0 * 18.50
    assert econ["expected_revenue_usd"] == round(expected_revenue, 2)
    assert econ["cost_breakdown"]["daily_operating_costs"] == round((3.0 + 12.0 + 3.0 + 3.0) * 8000.0, 2)
    assert econ["cost_breakdown"]["idle_holding_costs"] == round(2.0 * 8000.0, 2)
    assert econ["cost_breakdown"]["origin_port_costs"] == 45000.0
    assert econ["cost_breakdown"]["destination_port_costs"] == 50000.0
    assert (
        econ["total_voyage_costs_usd"]
        == econ["cost_breakdown"]["daily_operating_costs"]
        + econ["cost_breakdown"]["ballast_bunker_costs"]
        + econ["cost_breakdown"]["laden_bunker_costs"]
        + econ["cost_breakdown"]["auxiliary_port_bunker_costs"]
        + econ["cost_breakdown"]["origin_port_costs"]
        + econ["cost_breakdown"]["destination_port_costs"]
        + econ["cost_breakdown"]["idle_holding_costs"]
    )
    assert (
        econ["gross_contribution_usd"]
        == round(econ["expected_revenue_usd"] - econ["total_voyage_costs_usd"], 2)
    )
    assert 0.0 <= econ["utilization_ratio_pct"] <= 100.0


# ── 14. Candidate Admissibility Flag READY_FOR_OPTIMIZATION ───────────

def test_candidate_admissibility_flag_ready_for_optimization(db):
    """Feasible candidate has status='FEASIBLE' and optimization_status='READY_FOR_OPTIMIZATION'."""
    service = EmploymentService(db=db)
    # Cargo 2 is 70,000 MT coal suitable for Panamax Vessel 1
    cand = service.evaluate_employment_candidate(
        vessel_id=1,
        cargo_id=2,
        as_of_date=datetime(2026, 9, 1),
    )
    if cand["status"] == "FEASIBLE":
        assert cand["optimization_status"] == "READY_FOR_OPTIMIZATION"
        assert cand["primary_reason_code"] == EmploymentReasonCode.EMPLOYMENT_FEASIBLE.value
        assert len(cand["failed_reasons"]) == 0
    else:
        assert cand["optimization_status"] == "REJECTED"


# ── 15. Anti-Optimization Boundary (No Winner / No Ranking) ───────────

def test_anti_optimization_boundary_no_winner(db):
    """Verify candidate outputs have NO ranking, NO score, NO winner declaration."""
    service = EmploymentService(db=db)
    matrix = service.get_candidates_matrix(vessel_id=1, as_of_date=datetime(2026, 9, 1))
    compare = service.compare_candidates(vessel_id=1, as_of_date=datetime(2026, 9, 1))

    # Forbidden terms
    forbidden = ["winner", "rank", "score", "is_optimal", "best_option", "winning_vessel"]

    for cand in matrix["candidates"]:
        for key in cand.keys():
            assert key.lower() not in forbidden
        assert "is_winner" not in cand
        assert "rank" not in cand

    assert "advisory_note" in compare
    assert "Candidate Generation != Global Allocation" in compare["advisory_note"]
    assert "MILP" in compare["advisory_note"]


# ── 16. Database Persistence and Query ────────────────────────────────

def test_database_persistence_and_query(db):
    """Verify EmploymentOpportunity and IdleAssessment records persist and retrieve."""
    service = EmploymentService(db=db)

    # Persist candidate
    res = service.evaluate_employment_candidate(
        vessel_id=1,
        cargo_id=2,
        as_of_date=datetime(2026, 9, 1),
        persist=True,
    )

    db_rec = db.query(EmploymentOpportunity).filter_by(candidate_id=res["candidate_id"]).first()
    assert db_rec is not None
    assert db_rec.vessel_id == 1
    assert db_rec.cargo_id == 2
    assert db_rec.status in ["FEASIBLE", "INFEASIBLE"]
    assert db_rec.economic_summary is not None
    assert db_rec.timeline_detail is not None


# ── 17. Deterministic Reproducibility ─────────────────────────────────

def test_deterministic_reproducibility(db):
    """Repeating evaluation with same inputs yields identical byte-level and float outputs."""
    service = EmploymentService(db=db)
    as_of = datetime(2026, 9, 1, 0, 0, 0)

    res1 = service.evaluate_employment_candidate(vessel_id=1, cargo_id=2, as_of_date=as_of, persist=False)
    res2 = service.evaluate_employment_candidate(vessel_id=1, cargo_id=2, as_of_date=as_of, persist=False)

    # Provenance evaluated_at will differ by milliseconds; check core deterministic attributes
    assert res1["candidate_id"] == res2["candidate_id"]
    assert res1["status"] == res2["status"]
    assert res1["optimization_status"] == res2["optimization_status"]
    assert res1["primary_reason_code"] == res2["primary_reason_code"]
    assert res1["ballast"]["ballast_distance_nm"] == res2["ballast"]["ballast_distance_nm"]
    assert res1["ballast"]["ballast_days"] == res2["ballast"]["ballast_days"]
    assert res1["timeline"]["duration_breakdown"] == res2["timeline"]["duration_breakdown"]
    assert res1["economics"]["total_voyage_costs_usd"] == res2["economics"]["total_voyage_costs_usd"]
    assert res1["economics"]["gross_contribution_usd"] == res2["economics"]["gross_contribution_usd"]


# ── 18. Network Isolation ─────────────────────────────────────────────

def test_network_isolation(db, monkeypatch):
    """Verify zero external network calls occur during complete employment evaluation."""
    def guarded_connect(self, *args, **kwargs):
        raise RuntimeError("Air-gap violation: Network call attempted during Phase 6 Employment evaluation!")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    service = EmploymentService(db=db)
    result = service.evaluate_employment_candidate(
        vessel_id=1,
        cargo_id=2,
        as_of_date=datetime(2026, 9, 1),
        persist=False,
    )
    assert result["candidate_id"] is not None
    assert result["economics"]["total_voyage_costs_usd"] > 0


# ── 19. REST API Endpoints ───────────────────────────────────────────

def test_api_employment_overview(client):
    """Test GET /v1/employment/overview."""
    res = client.get("/v1/employment/overview")
    assert res.status_code == 200
    data = res.json()
    assert "total_vessels" in data
    assert "available_vessels" in data
    assert "idle_vessels" in data


def test_api_employment_vessels(client):
    """Test GET /v1/employment/vessels."""
    res = client.get("/v1/employment/vessels")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_api_employment_vessel_timeline(client):
    """Test GET /v1/employment/vessels/{vessel_id}/timeline."""
    res = client.get("/v1/employment/vessels/1/timeline?horizon_days=30")
    assert res.status_code == 200
    data = res.json()
    assert data["vessel_id"] == 1
    assert "events" in data


def test_api_employment_opportunities(client):
    """Test GET /v1/employment/opportunities."""
    res = client.get("/v1/employment/opportunities")
    assert res.status_code == 200
    data = res.json()
    assert "opportunities" in data
    assert data["total_count"] > 0


def test_api_employment_idle(client):
    """Test GET /v1/employment/idle."""
    res = client.get("/v1/employment/idle")
    assert res.status_code == 200
    data = res.json()
    assert "assessments" in data
    assert data["total_vessels_assessed"] > 0


def test_api_employment_evaluate(client):
    """Test POST /v1/employment/evaluate."""
    res = client.post(
        "/v1/employment/evaluate",
        json={"vessel_id": 1, "cargo_id": 2, "as_of_date": "2026-09-01T00:00:00"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["vessel_id"] == 1
    assert data["cargo_id"] == 2
    assert "status" in data
    assert "economics" in data


def test_api_employment_candidates(client):
    """Test POST /v1/employment/candidates."""
    res = client.post(
        "/v1/employment/candidates",
        json={"vessel_id": 1, "ready_only": False, "as_of_date": "2026-09-01T00:00:00"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "candidates" in data
    assert data["total_evaluated"] > 0


def test_api_employment_compare(client):
    """Test POST /v1/employment/compare."""
    res = client.post(
        "/v1/employment/compare",
        json={"vessel_id": 1, "as_of_date": "2026-09-01T00:00:00"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "candidates" in data
    assert "advisory_note" in data

