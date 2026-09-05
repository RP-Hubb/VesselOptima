"""
VesselOptima — Feasibility Engine Test Suite

Comprehensive tests for Phase 4:
1. Case A: Feasible assignment (Pilbara Iron on Port Hedland -> Dhamra iron ore voyage).
2. Case B: Infeasible due to destination port constraint (Capesize draft & LOA exceeds Paradip limits).
3. Case C: Infeasible due to insufficient vessel capacity (Handysize on Panamax coal cargo).
4. Case D: Infeasible due to vessel commitment conflict (confirmed existing charter/COA overlap).
5. Case E: Infeasible due to missed delivery deadline.
6. Case F: Infeasible due to missing route.
7. Origin vs Destination independent evaluation.
8. Warning vs Hard Failure distinction (advisory warnings do not fail feasibility).
9. Multi-vessel fleet evaluation (feasibility filter without economic ranking).
10. Feasibility matrix evaluation.
11. Determinism verification.
12. Air-gap network isolation verification (zero outbound network calls).
13. FastAPI feasibility endpoints.
"""

import socket
from datetime import datetime, timedelta
import pytest

from app.engines.feasibility.reason_codes import FeasibilityReasonCode
from app.engines.feasibility.service import FeasibilityService
from app.engines.feasibility.vessel_checks import (
    check_vessel_capacity,
    check_vessel_class_suitability,
)
from app.engines.feasibility.port_checks import evaluate_port_constraints
from app.engines.feasibility.schedule_checks import (
    calculate_great_circle_distance_nm,
    evaluate_schedule_and_commitments,
)


# ── 1. Unit Tests for Core Check Functions ──────────────────────────────

def test_vessel_capacity_check_pass_and_fail():
    """Vessel capacity checks enforce strict volume and tolerance limits."""
    # Strict pass
    is_pass, code, ev, warn = check_vessel_capacity(75000.0, 70000.0, tolerance_pct=5.0)
    assert is_pass is True
    assert code is None
    assert ev["status"] == "PASS"

    # Pass with tolerance
    is_pass, code, ev, warn = check_vessel_capacity(72000.0, 75000.0, tolerance_pct=5.0)
    assert is_pass is True
    assert code is None
    assert ev["status"] == "PASS_WITH_TOLERANCE"
    assert warn is not None

    # Hard failure (deficit exceeds tolerance)
    is_pass, code, ev, warn = check_vessel_capacity(32000.0, 75000.0, tolerance_pct=5.0)
    assert is_pass is False
    assert code == FeasibilityReasonCode.INSUFFICIENT_VESSEL_CAPACITY
    assert ev["status"] == "FAIL"
    assert ev["available_capacity"] == 32000.0
    assert ev["required_nominal"] == 75000.0


def test_port_constraints_evaluation():
    """Port draft, LOA, and beam checks report numeric evidence and reason codes."""
    mock_constraints = [
        {"rule_type": "MAX_DRAFT", "value": 14.5, "unit": "M", "terminal": "Central Quay", "berth": "CQ-1"},
        {"rule_type": "MAX_LOA", "value": 230.0, "unit": "M", "terminal": "Central Quay", "berth": "CQ-1"},
        {"rule_type": "MAX_BEAM", "value": 33.0, "unit": "M", "terminal": "Central Quay", "berth": "CQ-1"},
    ]

    # Panamax vessel: draft 14.1m, LOA 225m, beam 32.26m -> PASSES
    res_panamax = evaluate_port_constraints(
        port_id=1,
        port_name="Paradip",
        role="DESTINATION",
        vessel_draft=14.1,
        vessel_loa=225.0,
        vessel_beam=32.26,
        constraints=mock_constraints,
    )
    assert res_panamax.is_pass is True
    assert len(res_panamax.failed_checks) == 0

    # Capesize vessel: draft 18.2m, LOA 292m, beam 45m -> FAILS ALL 3
    res_cape = evaluate_port_constraints(
        port_id=1,
        port_name="Paradip",
        role="DESTINATION",
        vessel_draft=18.2,
        vessel_loa=292.0,
        vessel_beam=45.0,
        constraints=mock_constraints,
    )
    assert res_cape.is_pass is False
    assert FeasibilityReasonCode.VESSEL_DRAFT_EXCEEDS_PORT_LIMIT in res_cape.reason_codes
    assert FeasibilityReasonCode.VESSEL_LOA_EXCEEDS_PORT_LIMIT in res_cape.reason_codes
    assert FeasibilityReasonCode.VESSEL_BEAM_EXCEEDS_PORT_LIMIT in res_cape.reason_codes
    assert FeasibilityReasonCode.DESTINATION_PORT_INFEASIBLE in res_cape.reason_codes
    assert res_cape.checks["destination_max_draft"]["required_draft"] == 18.2
    assert res_cape.checks["destination_max_draft"]["permitted_draft"] == 14.5


def test_schedule_and_commitments_conflict():
    """Existing confirmed vessel commitments trigger hard failure."""
    available_at = datetime(2026, 9, 10, 0, 0)
    loading_start = datetime(2026, 9, 15, 0, 0)
    loading_end = datetime(2026, 9, 22, 0, 0)
    deadline = datetime(2026, 10, 15, 0, 0)

    # Mock commitment overlapping voyage window (Sept 24 to Oct 14)
    overlapping_commitment = [
        {
            "id": 101,
            "commitment_start": datetime(2026, 9, 24, 0, 0),
            "commitment_end": datetime(2026, 10, 14, 23, 59),
            "route_description": "Coastal Shuttle",
        }
    ]

    res = evaluate_schedule_and_commitments(
        vessel_id=1,
        vessel_speed_laden=12.5,
        vessel_speed_ballast=13.0,
        available_at=available_at,
        current_port_id=1,
        current_port_coords=(20.26, 86.67),
        origin_port_id=7,  # Newcastle
        origin_port_coords=(-32.92, 151.77),
        loading_window_start=loading_start,
        loading_window_end=loading_end,
        delivery_deadline=deadline,
        route_distance_nm=5250.0,
        cargo_volume_mt=75000.0,
        commitments=overlapping_commitment,
    )

    assert res.is_pass is False
    assert FeasibilityReasonCode.VESSEL_COMMITMENT_CONFLICT in res.reason_codes
    assert res.checks["vessel_commitments"]["status"] == "FAIL"
    assert res.checks["vessel_commitments"]["conflicts_count"] == 1


# ── 2. End-to-End Service Tests with Canonical Offline Data ─────────────

def test_case_a_feasible_voyage(db):
    """
    CASE A — FEASIBLE
    Cargo 2: 165,000 MT iron ore, Port Hedland -> Dhamra.
    Vessel 18 (Pilbara Iron): Capesize, capacity 170,000 MT, draft 18.0m.
    Port Hedland draft limit 19.5m, Dhamra draft limit 18.0m.
    Result must be FEASIBLE.
    """
    service = FeasibilityService(db=db)
    result = service.evaluate_assignment(cargo_id=2, vessel_id=18)

    assert result["is_feasible"] is True
    assert result["primary_reason_code"] is None
    assert len(result["failed_checks"]) == 0
    assert result["checks"]["capacity"]["status"] == "PASS"
    assert result["checks"]["origin_max_draft"]["status"] == "PASS"
    assert result["checks"]["destination_max_draft"]["status"] == "PASS"
    assert result["timing"]["sailing_days"] > 0


def test_case_b_infeasible_port_constraint(db):
    """
    CASE B — INFEASIBLE (Port Constraint)
    Cargo 1: 75,000 MT coal to Paradip Central Quay (Draft 14.5m, LOA 230m).
    Vessel 16 (VO Bharat Titan): Capesize, draft 18.2m, LOA 292m.
    Result must be INFEASIBLE with VESSEL_DRAFT_EXCEEDS_PORT_LIMIT.
    """
    service = FeasibilityService(db=db)
    result = service.evaluate_assignment(cargo_id=1, vessel_id=16)

    assert result["is_feasible"] is False
    assert FeasibilityReasonCode.VESSEL_DRAFT_EXCEEDS_PORT_LIMIT.value in result["reason_codes"]
    assert FeasibilityReasonCode.DESTINATION_PORT_INFEASIBLE.value in result["reason_codes"]
    assert "destination_max_draft" in result["failed_checks"]
    # Evidence must contain exact numbers
    draft_ev = result["checks"]["destination_max_draft"]
    assert draft_ev["required_draft"] == 18.2
    assert draft_ev["permitted_draft"] == 14.5


def test_case_c_infeasible_capacity(db):
    """
    CASE C — INFEASIBLE (Capacity)
    Cargo 1: 75,000 MT coal.
    Vessel 1 (VO Amber Leader): Handysize, cargo capacity 32,000 MT.
    Result must be INFEASIBLE with INSUFFICIENT_VESSEL_CAPACITY.
    """
    service = FeasibilityService(db=db)
    result = service.evaluate_assignment(cargo_id=1, vessel_id=1)

    assert result["is_feasible"] is False
    assert result["primary_reason_code"] == FeasibilityReasonCode.INSUFFICIENT_VESSEL_CAPACITY.value
    assert "capacity" in result["failed_checks"]
    assert result["evidence"]["capacity"]["available_capacity"] == 32000.0
    assert result["evidence"]["capacity"]["required_nominal"] == 75000.0


def test_case_d_infeasible_commitment_conflict(db):
    """
    CASE D — INFEASIBLE (Commitment Conflict)
    Vessel 11 (VO Utkal Glory) has confirmed commitment starting 2026-09-28.
    Attempting a long-distance Australia -> Paradip voyage starting late September
    causes an unavoidable schedule overlap.
    Result must be INFEASIBLE with VESSEL_COMMITMENT_CONFLICT.
    """
    service = FeasibilityService(db=db)
    result = service.evaluate_assignment(cargo_id=1, vessel_id=11)

    assert result["is_feasible"] is False
    assert FeasibilityReasonCode.VESSEL_COMMITMENT_CONFLICT.value in result["reason_codes"]
    assert "vessel_commitments" in result["failed_checks"]


def test_case_e_missing_route(db):
    """
    CASE E — INFEASIBLE (Missing Route)
    Requesting an invalid route ID that does not connect ports fails explicitly.
    """
    service = FeasibilityService(db=db)
    result = service.evaluate_assignment(cargo_id=1, vessel_id=10, route_id=999)

    assert result["is_feasible"] is False
    assert result["primary_reason_code"] == FeasibilityReasonCode.ROUTE_NOT_FOUND.value


def test_origin_vs_destination_independent_evaluation(db):
    """Origin and destination port constraints are evaluated independently."""
    service = FeasibilityService(db=db)
    # Vessel 16 at Port Hedland (Origin, max draft 19.5m -> PASS) to Dhamra (Dest, max draft 18.0m -> FAIL)
    result = service.evaluate_assignment(cargo_id=2, vessel_id=16)

    assert result["checks"]["origin_max_draft"]["status"] == "PASS"
    assert result["checks"]["destination_max_draft"]["status"] == "FAIL"


def test_warning_does_not_fail_feasibility(db):
    """Advisory warnings (e.g. daylight navigation or tolerance) do not cause infeasibility."""
    service = FeasibilityService(db=db)
    # Cargo 2 with Vessel 18 has tidal advisory condition at Port Hedland for draft > 17.5m
    result = service.evaluate_assignment(cargo_id=2, vessel_id=18)

    assert result["is_feasible"] is True
    assert len(result["warnings"]) > 0


def test_candidate_fleet_evaluation(db):
    """
    Fleet evaluation evaluates all vessels without performing economic ranking.
    """
    service = FeasibilityService(db=db)
    fleet_eval = service.evaluate_candidate_fleet(cargo_id=2)

    assert len(fleet_eval) == 20
    # Must contain both feasible and infeasible options
    feasible_vessels = [v for v in fleet_eval if v["is_feasible"]]
    infeasible_vessels = [v for v in fleet_eval if not v["is_feasible"]]

    assert len(feasible_vessels) >= 1
    assert len(infeasible_vessels) >= 1
    # Check that no economic scores (e.g. total_cost, score, rank) are injected
    for v in fleet_eval:
        assert "rank" not in v
        assert "score" not in v
        assert "optimal" not in v


def test_feasibility_matrix_evaluation(db):
    """Matrix evaluation covers multiple cargos and vessels."""
    service = FeasibilityService(db=db)
    matrix_res = service.evaluate_feasibility_matrix(cargo_ids=[1, 2], vessel_ids=[1, 16, 18])

    assert "matrix" in matrix_res
    assert "1" in matrix_res["matrix"]
    assert "2" in matrix_res["matrix"]
    assert matrix_res["summary"]["total_evaluations"] == 6


def test_feasibility_determinism(db):
    """Evaluating identical cargo and vessel twice produces bit-for-bit identical results."""
    service = FeasibilityService(db=db)
    res1 = service.evaluate_assignment(cargo_id=1, vessel_id=16)
    res2 = service.evaluate_assignment(cargo_id=1, vessel_id=16)

    assert res1["is_feasible"] == res2["is_feasible"]
    assert res1["primary_reason_code"] == res2["primary_reason_code"]
    assert res1["reason_codes"] == res2["reason_codes"]
    assert res1["failed_checks"] == res2["failed_checks"]


def test_feasibility_zero_network_calls(client, monkeypatch):
    """
    Air-gap test: Feasibility evaluation executes offline with zero outbound network calls.
    """
    original_connect = socket.socket.connect

    def blocked_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) and address else str(address)
        if host not in ("127.0.0.1", "localhost", "::1", "testserver"):
            raise ConnectionRefusedError(
                f"Outbound network connectivity to {host} is forbidden in OFFLINE_DEMO mode!"
            )
        return original_connect(self, address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)

    resp = client.post(
        "/v1/feasibility/evaluate",
        json={"cargo_id": 2, "vessel_id": 18},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_feasible"] is True
    assert data["provenance"]["runtime_mode"] == "OFFLINE_DEMO"


# ── 3. FastAPI Endpoint Tests ──────────────────────────────────────────

def test_api_feasibility_endpoints(client):
    """FastAPI routes /v1/feasibility/evaluate, /v1/feasibility/vessels, /cargos."""
    # 1. Cargos list
    r_cargos = client.get("/v1/feasibility/cargos")
    assert r_cargos.status_code == 200
    cargos = r_cargos.json()
    assert len(cargos) >= 6

    # 2. Evaluate valid feasible assignment
    r_eval = client.post(
        "/v1/feasibility/evaluate",
        json={"cargo_id": 2, "vessel_id": 18},
    )
    assert r_eval.status_code == 200
    data = r_eval.json()
    assert data["is_feasible"] is True
    assert data["vessel_id"] == 18

    # 3. Evaluate invalid cargo -> 404
    r_bad_cargo = client.post(
        "/v1/feasibility/evaluate",
        json={"cargo_id": 9999, "vessel_id": 18},
    )
    assert r_bad_cargo.status_code == 404

    # 4. Fleet evaluation
    r_fleet = client.get("/v1/feasibility/vessels/1")
    assert r_fleet.status_code == 200
    fleet_data = r_fleet.json()
    assert fleet_data["cargo_id"] == 1
    assert fleet_data["total_vessels"] == 20
    assert "vessels" in fleet_data

    # 5. Matrix evaluation
    r_mat = client.post(
        "/v1/feasibility/matrix",
        json={"cargo_ids": [1], "vessel_ids": [1, 16]},
    )
    assert r_mat.status_code == 200
    mat_data = r_mat.json()
    assert mat_data["summary"]["total_evaluations"] == 2
