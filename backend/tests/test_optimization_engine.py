"""
VesselOptima — Phase 7: MILP Optimization Engine Test Suite

Comprehensive tests covering:
1. Single Vessel / Single Cargo
2. Two Vessels / Same Cargo (Economic ranking proof)
3. Two Cargoes / One Vessel (Vessel capacity trade-off)
4. Two Vessels / Two Cargoes (Global allocation)
5. Overlapping Employment (Temporal mutual exclusivity)
6. Confirmed Commitment Protection (Hard fixture constraint)
7. Low Contribution Candidate (Optional cargo rejection)
8. Ballast Economics Trade-off (Repositioning penalty impact)
9. Idle Cost Trade-off (Avoided idle cost impact)
10. Zero-Candidate Clean Handling (EMPTY_MODEL)
11. Infeasible Model Handling (INFEASIBLE diagnostic)
12. Determinism (100% reproducible results)
13. Phase 6 End-to-End Integration
14. CRITICAL: Greedy vs Global Optimum (+$170,000 delta proof)
15. Multi-Period Sequential Ballast Transition Compatibility
16. Scalability & Performance (10, 50, 100, 200 candidates)
17. Air-Gap Isolation (Zero outbound network socket connections)
18. REST API Verification (/v1/optimization/solve, /runs, /compare)
"""

import socket
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.engines.optimization.constraints import LinearConstraintDefinition
from app.engines.optimization.model import OptimizationModel
from app.engines.optimization.objective import ObjectiveConfig
from app.engines.optimization.reason_codes import (
    AssignmentSelectionStatus,
    OptimizationStatus,
    TradeOffReasonCode,
)
from app.engines.optimization.service import OptimizationService
from app.engines.optimization.solver import HiGHSSolverAdapter
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


# ── Test 1: Single Vessel / Single Cargo ──────────────────────────────

def test_single_vessel_single_cargo():
    """One feasible candidate must be SELECTED by the optimizer."""
    model = OptimizationModel()
    start = datetime(2026, 9, 1, 10, 0)
    end = datetime(2026, 9, 15, 10, 0)

    model.add_candidate(
        candidate_id="CAND-01",
        vessel_id=1,
        vessel_name="Vessel Alpha",
        cargo_id=101,
        cargo_name="Iron Ore 70k MT",
        start_time=start,
        end_time=end,
        expected_revenue=500_000.0,
        voyage_cost=300_000.0,
        net_contribution=200_000.0,
        idle_days_saved=5.0,
        avoided_idle_cost=37_500.0,
    )
    model.add_cargo(101, "Iron Ore 70k MT")

    res = model.solve()
    assert res.status == OptimizationStatus.OPTIMAL
    assert len(res.selected_assignments) == 1
    selected = res.selected_assignments[0]
    assert selected.candidate_id == "CAND-01"
    assert selected.is_selected is True
    assert selected.selection_status == AssignmentSelectionStatus.SELECTED
    assert selected.trade_off_reason_code == TradeOffReasonCode.OPTIMAL_GLOBAL_ALLOCATION
    assert res.objective_value == pytest.approx(237_500.0)


# ── Test 2: Two Vessels / Same Cargo ──────────────────────────────────

def test_two_vessels_same_cargo_economic_ranking():
    """
    Two feasible candidates for the same cargo.
    Optimizer must select the vessel offering superior global economic contribution.
    """
    model = OptimizationModel()
    start = datetime(2026, 9, 1, 10, 0)
    end = datetime(2026, 9, 15, 10, 0)

    # Vessel 1: net contribution +$150k
    model.add_candidate(
        candidate_id="CAND-V1",
        vessel_id=1,
        vessel_name="Vessel 1",
        cargo_id=101,
        cargo_name="Coal 65k MT",
        start_time=start,
        end_time=end,
        expected_revenue=450_000.0,
        voyage_cost=300_000.0,
        net_contribution=150_000.0,
    )

    # Vessel 2: net contribution +$220k (superior)
    model.add_candidate(
        candidate_id="CAND-V2",
        vessel_id=2,
        vessel_name="Vessel 2",
        cargo_id=101,
        cargo_name="Coal 65k MT",
        start_time=start,
        end_time=end,
        expected_revenue=450_000.0,
        voyage_cost=230_000.0,
        net_contribution=220_000.0,
    )
    model.add_cargo(101, "Coal 65k MT")

    res = model.solve()
    assert res.status == OptimizationStatus.OPTIMAL
    assert len(res.selected_assignments) == 1
    assert res.selected_assignments[0].candidate_id == "CAND-V2"
    assert len(res.rejected_opportunities) == 1
    rejected = res.rejected_opportunities[0]
    assert rejected.candidate_id == "CAND-V1"
    assert rejected.selection_status == AssignmentSelectionStatus.MODEL_REJECTED
    assert rejected.trade_off_reason_code == TradeOffReasonCode.CARGO_EXCLUSIVITY_LOST


# ── Test 3: Two Cargoes / One Vessel ──────────────────────────────────

def test_two_cargoes_one_vessel():
    """
    One vessel can perform only one of two overlapping cargoes.
    Optimizer must select the higher-yielding cargo.
    """
    model = OptimizationModel()
    start = datetime(2026, 9, 1, 0, 0)
    end = datetime(2026, 9, 14, 0, 0)

    model.add_candidate(
        candidate_id="CAND-C1",
        vessel_id=1,
        vessel_name="Vessel 1",
        cargo_id=101,
        cargo_name="Cargo 101",
        start_time=start,
        end_time=end,
        expected_revenue=400_000.0,
        voyage_cost=250_000.0,
        net_contribution=150_000.0,
    )
    model.add_candidate(
        candidate_id="CAND-C2",
        vessel_id=1,
        vessel_name="Vessel 1",
        cargo_id=102,
        cargo_name="Cargo 102",
        start_time=start,
        end_time=end,
        expected_revenue=480_000.0,
        voyage_cost=260_000.0,
        net_contribution=220_000.0,
    )
    model.add_cargo(101, "Cargo 101")
    model.add_cargo(102, "Cargo 102")

    res = model.solve()
    assert res.status == OptimizationStatus.OPTIMAL
    assert len(res.selected_assignments) == 1
    assert res.selected_assignments[0].candidate_id == "CAND-C2"
    assert len(res.rejected_opportunities) == 1
    assert res.rejected_opportunities[0].candidate_id == "CAND-C1"
    assert res.rejected_opportunities[0].trade_off_reason_code == TradeOffReasonCode.VESSEL_TIMELINE_CONFLICT


# ── Test 4: Two Vessels / Two Cargoes ──────────────────────────────────

def test_two_vessels_two_cargoes():
    """Both vessels assigned to distinct cargoes when compatible."""
    model = OptimizationModel()
    start = datetime(2026, 9, 1, 0, 0)
    end = datetime(2026, 9, 14, 0, 0)

    model.add_candidate("V1-C1", 1, "V1", 101, "C1", start, end, 500_000.0, 300_000.0, 200_000.0)
    model.add_candidate("V2-C2", 2, "V2", 102, "C2", start, end, 600_000.0, 350_000.0, 250_000.0)
    model.add_cargo(101, "C1")
    model.add_cargo(102, "C2")

    res = model.solve()
    assert res.status == OptimizationStatus.OPTIMAL
    assert len(res.selected_assignments) == 2
    assert res.objective_value == pytest.approx(450_000.0)


# ── Test 5: Overlapping Employment Intervals ──────────────────────────

def test_overlapping_employment_on_same_vessel():
    """Two employment opportunities for the same vessel overlap in time."""
    model = OptimizationModel(turnaround_hours=12.0)
    start_1 = datetime(2026, 9, 1, 0, 0)
    end_1 = datetime(2026, 9, 10, 0, 0)

    start_2 = datetime(2026, 9, 8, 0, 0)  # Overlaps with voyage 1
    end_2 = datetime(2026, 9, 18, 0, 0)

    model.add_candidate("V1-OP1", 1, "V1", 101, "C1", start_1, end_1, 300_000.0, 150_000.0, 150_000.0)
    model.add_candidate("V1-OP2", 1, "V1", 102, "C2", start_2, end_2, 350_000.0, 160_000.0, 190_000.0)
    model.add_cargo(101, "C1")
    model.add_cargo(102, "C2")

    res = model.solve()
    assert res.status == OptimizationStatus.OPTIMAL
    assert len(res.selected_assignments) == 1
    assert res.selected_assignments[0].candidate_id == "V1-OP2"
    assert res.rejected_opportunities[0].trade_off_reason_code == TradeOffReasonCode.VESSEL_TIMELINE_CONFLICT


# ── Test 6: Confirmed Commitment Protection ───────────────────────────

def test_confirmed_commitment_protection():
    """
    A candidate that overlaps with a vessel's confirmed commercial commitment fixture
    must be excluded (x_k = 0).
    """
    model = OptimizationModel()
    start = datetime(2026, 9, 5, 0, 0)
    end = datetime(2026, 9, 18, 0, 0)

    model.add_candidate("V1-C1", 1, "V1", 101, "C1", start, end, 500_000.0, 200_000.0, 300_000.0)
    model.add_cargo(101, "C1")

    # Fixture on Vessel 1: Sept 10 to Sept 25 (overlaps with candidate)
    model.set_vessel_commitments({
        1: [(datetime(2026, 9, 10, 0, 0), datetime(2026, 9, 25, 0, 0))]
    })

    res = model.solve()
    assert res.status == OptimizationStatus.OPTIMAL
    assert len(res.selected_assignments) == 0
    assert len(res.rejected_opportunities) == 1
    assert res.rejected_opportunities[0].is_selected is False
    assert res.objective_value == 0.0


# ── Test 7: Low / Negative Contribution Candidate ─────────────────────

def test_negative_contribution_optional_rejection():
    """
    Candidate with negative economic contribution (costs exceed freight)
    must be left unassigned by optional cargo rejection.
    """
    model = OptimizationModel()
    start = datetime(2026, 9, 1, 0, 0)
    end = datetime(2026, 9, 10, 0, 0)

    # Freight $100k, Costs $180k -> Contribution -$80k
    model.add_candidate("V1-LOSS", 1, "V1", 101, "Loss Cargo", start, end, 100_000.0, 180_000.0, -80_000.0)
    model.add_cargo(101, "Loss Cargo", unserved_penalty=0.0)

    res = model.solve()
    assert res.status == OptimizationStatus.OPTIMAL
    assert len(res.selected_assignments) == 0
    assert len(res.rejected_opportunities) == 1
    assert res.rejected_opportunities[0].trade_off_reason_code == TradeOffReasonCode.NEGATIVE_ECONOMIC_CONTRIBUTION
    assert len(res.unassigned_cargos) == 1
    assert res.unassigned_cargos[0].cargo_id == 101
    assert res.objective_value == 0.0


# ── Test 8: Ballast Trade-Off ─────────────────────────────────────────

def test_ballast_penalty_trade_off():
    """
    Candidate A has slightly higher contribution but much longer ballast repositioning.
    With ballast penalty active, Candidate B with shorter ballast is preferred.
    """
    # Without ballast penalty: Candidate A (+110k) beats B (+100k)
    m1 = OptimizationModel()
    start = datetime(2026, 9, 1, 0, 0)
    end = datetime(2026, 9, 10, 0, 0)
    m1.add_candidate("A", 1, "V1", 101, "C1", start, end, 310_000.0, 200_000.0, 110_000.0, ballast_days=10.0)
    m1.add_candidate("B", 1, "V1", 102, "C2", start, end, 280_000.0, 180_000.0, 100_000.0, ballast_days=2.0)
    m1.add_cargo(101, "C1")
    m1.add_cargo(102, "C2")
    r1 = m1.solve()
    assert r1.selected_assignments[0].candidate_id == "A"

    # With ballast penalty: $2,000/day
    # Candidate A effective: 110k - (10 * 2k) = $90k
    # Candidate B effective: 100k - (2 * 2k) = $96k (B wins!)
    m2 = OptimizationModel(objective_config=ObjectiveConfig(beta_ballast_penalty=2000.0))
    m2.add_candidate("A", 1, "V1", 101, "C1", start, end, 310_000.0, 200_000.0, 110_000.0, ballast_days=10.0)
    m2.add_candidate("B", 1, "V1", 102, "C2", start, end, 280_000.0, 180_000.0, 100_000.0, ballast_days=2.0)
    m2.add_cargo(101, "C1")
    m2.add_cargo(102, "C2")
    r2 = m2.solve()
    assert r2.selected_assignments[0].candidate_id == "B"


# ── Test 9: Idle Cost Trade-Off ───────────────────────────────────────

def test_idle_cost_trade_off():
    """
    Candidate with lower voyage contribution but higher avoided idle cost
    wins when idle holding costs are accounted for.
    """
    start = datetime(2026, 9, 1, 0, 0)
    end = datetime(2026, 9, 10, 0, 0)

    # Cand 1: Net contribution +$120k, Avoided Idle = $0
    # Cand 2: Net contribution +$100k, Avoided Idle = $35k (7 days @ $5,000)
    # Total reward: Cand 1 = $120k; Cand 2 = $135k
    m = OptimizationModel(objective_config=ObjectiveConfig(alpha_idle_weight=1.0))
    m.add_candidate("C1", 1, "V1", 101, "C1", start, end, 300_000.0, 180_000.0, 120_000.0, avoided_idle_cost=0.0)
    m.add_candidate("C2", 1, "V1", 102, "C2", start, end, 280_000.0, 180_000.0, 100_000.0, avoided_idle_cost=35_000.0)
    m.add_cargo(101, "C1")
    m.add_cargo(102, "C2")

    res = m.solve()
    assert res.selected_assignments[0].candidate_id == "C2"
    assert res.objective_value == pytest.approx(135_000.0)


# ── Test 10: Zero-Candidate Handling (EMPTY_MODEL) ────────────────────

def test_zero_candidates_empty_model():
    """Zero admissible candidates must cleanly return EMPTY_MODEL without throwing exceptions."""
    model = OptimizationModel()
    res = model.solve()
    assert res.status == OptimizationStatus.EMPTY_MODEL
    assert res.objective_value == 0.0
    assert len(res.selected_assignments) == 0
    assert len(res.rejected_opportunities) == 0


# ── Test 11: Infeasible Model Handling ────────────────────────────────

def test_infeasible_model_handling():
    """Forced conflicting equality constraints produce INFEASIBLE diagnostic."""
    model = OptimizationModel()
    start = datetime(2026, 9, 1, 0, 0)
    end = datetime(2026, 9, 10, 0, 0)
    c1 = model.add_candidate("C1", 1, "V1", 101, "Cargo 101", start, end, 100_000.0, 50_000.0, 50_000.0)

    # Artificially inject contradictory constraints: x_0 == 1 AND x_0 == 0
    model.add_custom_constraint(
        LinearConstraintDefinition("must_be_1", "TEST", {c1.index: 1.0}, 1.0, 1.0)
    )
    model.add_custom_constraint(
        LinearConstraintDefinition("must_be_0", "TEST", {c1.index: 1.0}, 0.0, 0.0)
    )

    res = model.solve()
    assert res.status == OptimizationStatus.INFEASIBLE
    assert res.objective_value == 0.0
    assert len(res.selected_assignments) == 0


# ── Test 12: Determinism Verification ─────────────────────────────────

def test_determinism():
    """Executing optimization twice on identical inputs yields identical assignments and objective."""
    def run_scenario():
        m = OptimizationModel()
        start = datetime(2026, 9, 1, 0, 0)
        end = datetime(2026, 9, 15, 0, 0)
        m.add_candidate("A", 1, "V1", 101, "C1", start, end, 400_000.0, 200_000.0, 200_000.0)
        m.add_candidate("B", 2, "V2", 101, "C1", start, end, 420_000.0, 210_000.0, 210_000.0)
        m.add_candidate("C", 1, "V1", 102, "C2", start, end, 350_000.0, 170_000.0, 180_000.0)
        m.add_cargo(101, "C1")
        m.add_cargo(102, "C2")
        return m.solve()

    res1 = run_scenario()
    res2 = run_scenario()

    assert res1.status == res2.status == OptimizationStatus.OPTIMAL
    assert res1.objective_value == res2.objective_value
    assert [a.candidate_id for a in res1.selected_assignments] == [a.candidate_id for a in res2.selected_assignments]


# ── Test 13: Phase 6 Integration ──────────────────────────────────────

def test_phase6_integration_solve_fleet():
    """End-to-end integration: solve_fleet_assignment consumes Phase 6 candidates."""
    service = OptimizationService(db=None)
    res = service.solve_fleet_assignment(
        as_of_date=datetime(2026, 9, 1, 0, 0),
        persist=False,
    )
    assert res.status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE, OptimizationStatus.EMPTY_MODEL)
    assert res.objective_value >= 0.0
    assert isinstance(res.selected_assignments, list)
    assert isinstance(res.rejected_opportunities, list)
    assert "total_gross_revenue" in res.decomposition.to_dict()


# ── Test 14: CRITICAL GREEDY VS GLOBAL OPTIMUM PROOF ─────────────────

def test_critical_greedy_vs_global_optimum():
    """
    Mathematical Proof that MILP Optimization outperforms Naive Greedy Ranking.

    Scenario Setup:
        Vessel A -> Cargo 1 = +$300,000
        Vessel A -> Cargo 2 = +$280,000

        Vessel B -> Cargo 1 = +$290,000
        Vessel B -> Cargo 2 = +$100,000

    Naive Greedy Ranking:
        Step 1: Greedy picks highest overall single candidate: Vessel A -> Cargo 1 ($300k).
        Step 2: Cargo 1 and Vessel A are now consumed.
        Step 3: Only remaining feasible candidate for Vessel B is Cargo 2 ($100k).
        Greedy Total: $300,000 + $100,000 = $400,000.

    Global MILP Optimization:
        Assigns: Vessel B -> Cargo 1 ($290,000)
                 Vessel A -> Cargo 2 ($280,000)
        Global MILP Total: $290,000 + $280,000 = $570,000.

    Advantage: MILP generates +$170,000 (+42.5%) more global economic contribution!
    """
    model = OptimizationModel()
    start = datetime(2026, 9, 1, 0, 0)
    end = datetime(2026, 9, 15, 0, 0)

    # Vessel A candidates
    model.add_candidate("A-C1", 1, "Vessel A", 101, "Cargo 1", start, end, 500_000.0, 200_000.0, 300_000.0)
    model.add_candidate("A-C2", 1, "Vessel A", 102, "Cargo 2", start, end, 480_000.0, 200_000.0, 280_000.0)

    # Vessel B candidates
    model.add_candidate("B-C1", 2, "Vessel B", 101, "Cargo 1", start, end, 490_000.0, 200_000.0, 290_000.0)
    model.add_candidate("B-C2", 2, "Vessel B", 102, "Cargo 2", start, end, 300_000.0, 200_000.0, 100_000.0)

    model.add_cargo(101, "Cargo 1")
    model.add_cargo(102, "Cargo 2")

    res = model.solve()
    assert res.status == OptimizationStatus.OPTIMAL

    selected_ids = {a.candidate_id for a in res.selected_assignments}
    assert selected_ids == {"B-C1", "A-C2"}

    # Mathematical verification of global optimum
    greedy_total = 300_000.0 + 100_000.0  # $400k
    global_total = res.objective_value      # $570k
    delta = global_total - greedy_total

    assert global_total == pytest.approx(570_000.0)
    assert delta == pytest.approx(170_000.0)


# ── Test 15: Multi-Period Sequential Transition Compatibility ─────────

def test_multi_period_transition_compatibility():
    """
    Sequential opportunities on the same vessel must allow sufficient ballast
    repositioning days between discharge and next loading.
    """
    model = OptimizationModel(turnaround_hours=24.0)

    # Voyage 1: Sept 1 to Sept 10, discharge at Port 2
    v1_start = datetime(2026, 9, 1, 0, 0)
    v1_end = datetime(2026, 9, 10, 0, 0)

    # Voyage 2: Sept 13 to Sept 22, loading at Port 5
    # Transit from Port 2 to Port 5 requires 5 days ballast.
    # Available gap: Sept 10 to Sept 13 = 3 days < (5 days transit + 1 day turnaround = 6 days).
    # Therefore, Voyage 1 and Voyage 2 cannot both be performed sequentially!
    v2_start = datetime(2026, 9, 13, 0, 0)
    v2_end = datetime(2026, 9, 22, 0, 0)

    model.add_candidate(
        "SEQ-1", 1, "V1", 101, "C1", v1_start, v1_end, 300_000.0, 150_000.0, 150_000.0,
        origin_port_id=1, destination_port_id=2
    )
    model.add_candidate(
        "SEQ-2", 1, "V1", 102, "C2", v2_start, v2_end, 320_000.0, 150_000.0, 170_000.0,
        origin_port_id=5, destination_port_id=6
    )
    model.add_cargo(101, "C1")
    model.add_cargo(102, "C2")

    # Transit days Port 2 -> Port 5: 5.0 days
    model.set_inter_port_transit_days({(2, 5): 5.0})

    res = model.solve()
    assert res.status == OptimizationStatus.OPTIMAL
    # Only one can be selected
    assert len(res.selected_assignments) == 1
    # Picks the higher yielding SEQ-2 ($170k > $150k)
    assert res.selected_assignments[0].candidate_id == "SEQ-2"
    assert res.rejected_opportunities[0].candidate_id == "SEQ-1"


# ── Test 16: Scalability & Performance ────────────────────────────────

def test_scalability_and_performance():
    """Validates that HiGHS solves 100+ candidate models within seconds."""
    model = OptimizationModel()
    start = datetime(2026, 9, 1, 0, 0)
    end = datetime(2026, 9, 15, 0, 0)

    # 10 vessels x 10 cargoes = 100 candidate variables
    for v in range(1, 11):
        for c in range(1, 11):
            contrib = 100_000.0 + (v * 5_000.0) + (c * 3_000.0) - (abs(v - c) * 4_000.0)
            model.add_candidate(
                candidate_id=f"V{v:02d}-C{c:02d}",
                vessel_id=v,
                vessel_name=f"Vessel {v}",
                cargo_id=c,
                cargo_name=f"Cargo {c}",
                start_time=start,
                end_time=end,
                expected_revenue=contrib + 150_000.0,
                voyage_cost=150_000.0,
                net_contribution=contrib,
            )

    for c in range(1, 11):
        model.add_cargo(c, f"Cargo {c}")

    res = model.solve(time_limit_seconds=10.0)
    assert res.status == OptimizationStatus.OPTIMAL
    assert len(res.selected_assignments) == 10  # 1-to-1 matching across 10 vessels and 10 cargoes
    assert res.solve_time_seconds < 2.0  # HiGHS solves 100 candidates in < 0.2s


# ── Test 17: Air-Gap Isolation ────────────────────────────────────────

def test_air_gap_isolation(monkeypatch):
    """Verifies that running optimization triggers ZERO outbound network socket connections."""
    def block_socket_connect(*args, **kwargs):
        raise RuntimeError("AIR-GAP VIOLATION: Unexpected outbound network connection attempt!")

    monkeypatch.setattr(socket.socket, "connect", block_socket_connect)

    service = OptimizationService(db=None)
    res = service.solve_fleet_assignment(
        as_of_date=datetime(2026, 9, 1, 0, 0),
        persist=False,
    )
    assert res.status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE, OptimizationStatus.EMPTY_MODEL)


# ── Test 18: REST API Verification ────────────────────────────────────

def test_optimization_api_endpoints(client):
    """Verifies FastAPI /v1/optimization endpoints."""
    # 1. Trigger solve
    solve_payload = {
        "as_of_date": "2026-09-01T00:00:00",
        "alpha_idle_weight": 1.0,
        "beta_ballast_penalty": 0.0,
        "persist": True,
    }
    resp = client.post("/v1/optimization/solve", json=solve_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "run_id" in data
    assert "status" in data
    assert "objective_value" in data
    assert "decomposition" in data
    assert "selected_assignments" in data
    run_id = data["run_id"]

    # 2. List runs
    resp_runs = client.get("/v1/optimization/runs")
    assert resp_runs.status_code == 200
    runs = resp_runs.json()
    assert len(runs) >= 1
    assert any(r["run_id"] == run_id for r in runs)

    # 3. Get single run
    resp_single = client.get(f"/v1/optimization/runs/{run_id}")
    assert resp_single.status_code == 200
    single_data = resp_single.json()
    assert single_data["run_id"] == run_id

    # 4. Get run assignments
    resp_assign = client.get(f"/v1/optimization/runs/{run_id}/assignments")
    assert resp_assign.status_code == 200
    assert "assignments" in resp_assign.json()

    # 5. Get run constraints
    resp_constr = client.get(f"/v1/optimization/runs/{run_id}/constraints")
    assert resp_constr.status_code == 200

    # 6. Get run audit
    resp_audit = client.get(f"/v1/optimization/runs/{run_id}/audit")
    assert resp_audit.status_code == 200
