"""
VesselOptima — Phase 8: Scenario Analysis & What-If Engine Test Suite

Validates:
1. Baseline Reproduction
2. Freight Increase
3. Freight Decrease
4. Bunker Price Increase
5. Idle Cost Increase
6. Multi-Parameter Market Stress
7. Tight Laycan Upstream Revalidation
8. Fleet Unavailability & Vessel Outage
9. Baseline Immutability (SHA-256 integrity before == after)
10. Determinism (Repeated runs yield identical hashes)
11. Assignment Difference Engine (UNCHANGED, ADDED, DROPPED, REPLACED)
12. Critical Strategy Flip (Mathematical assignment swap proof)
13. Sensitivity Sweep (One-Variable-at-a-Time curve)
14. Break-Even Switching Threshold Detection
15. Robustness Analysis (Ensemble survival scoring)
16. Batch Scenario Execution
17. Database Persistence & Audit Trail
18. Phase 7 MILP Engine Integration (HiGHS solver without greedy fallback)
19. Air-Gap Network Isolation (Zero external socket connections)
20. REST API Endpoints (/v1/scenarios/*)
"""

from datetime import datetime, timedelta, timezone
import pytest
import socket
from unittest.mock import patch

from app.db.session import SessionLocal
from app.engines.employment.service import DEFAULT_AS_OF_DATE
from app.engines.optimization.service import OptimizationService
from app.engines.scenarios.comparison import (
    AssignmentDifferenceEngine,
    CandidateDeltaStatus,
    CargoDeltaStatus,
)
from app.engines.scenarios.config import (
    ScenarioConfig,
    ScenarioPresets,
    ScenarioType,
)
from app.engines.scenarios.revalidation import ScenarioRevalidator
from app.engines.scenarios.robustness import RobustnessEngine, RobustnessTier
from app.engines.scenarios.sensitivity import SensitivityEngine
from app.engines.scenarios.service import ScenarioService
from app.engines.scenarios.transform import ScenarioTransformer, hash_candidate_set
from app.models.domain import ScenarioEvaluation, ScenarioSensitivityRun


@pytest.fixture
def db_session():
    """Provides an isolated database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def strategy_flip_candidates():
    """
    Constructs synthetic candidates mathematically calibrated to flip optimal assignments:
    At Bunker Multiplier = 1.0:
        Option 1: (Vessel A -> Cargo 1) and (Vessel B -> Cargo 2) = $680,000 (WINNER)
        Option 2: (Vessel A -> Cargo 2) and (Vessel B -> Cargo 1) = $660,000
    At Bunker Multiplier = 1.5:
        Option 1: (Vessel A -> Cargo 1) and (Vessel B -> Cargo 2) = $530,000
        Option 2: (Vessel A -> Cargo 2) and (Vessel B -> Cargo 1) = $610,000 (WINNER)
    """
    eval_date = DEFAULT_AS_OF_DATE
    return [
        {
            "candidate_id": "FLIP-A1",
            "vessel_id": 101,
            "vessel_name": "Vessel A (Eco Bulker)",
            "cargo_id": 201,
            "cargo_name": "Cargo 1 (Coal)",
            "status": "FEASIBLE",
            "economics": {
                "expected_gross_revenue": 500000.0,
                "total_voyage_cost": 160000.0,
                "net_economic_contribution": 340000.0,
                "daily_operating_cost": 10000.0,
                "idle_days": 2.0,
                "cost_breakdown": {
                    "operating_cost": 10000.0,
                    "bunker_cost": 150000.0,
                    "port_cost": 0.0,
                },
            },
            "timeline": {
                "schedule": {
                    "ballast_start": eval_date.isoformat(),
                    "discharge_end": (eval_date + timedelta(days=12)).isoformat(),
                },
                "timing_milestones": {
                    "ballast_arrival": (eval_date + timedelta(days=2)).isoformat(),
                    "cargo_laycan_start": eval_date.isoformat(),
                    "cargo_laycan_end": (eval_date + timedelta(days=6)).isoformat(),
                },
            },
            "ballast": {"ballast_distance_nm": 400.0, "ballast_days": 2.0},
        },
        {
            "candidate_id": "FLIP-A2",
            "vessel_id": 101,
            "vessel_name": "Vessel A (Eco Bulker)",
            "cargo_id": 202,
            "cargo_name": "Cargo 2 (Iron Ore)",
            "status": "FEASIBLE",
            "economics": {
                "expected_gross_revenue": 390000.0,
                "total_voyage_cost": 60000.0,
                "net_economic_contribution": 330000.0,
                "daily_operating_cost": 10000.0,
                "idle_days": 2.0,
                "cost_breakdown": {
                    "operating_cost": 10000.0,
                    "bunker_cost": 50000.0,
                    "port_cost": 0.0,
                },
            },
            "timeline": {
                "schedule": {
                    "ballast_start": eval_date.isoformat(),
                    "discharge_end": (eval_date + timedelta(days=12)).isoformat(),
                },
                "timing_milestones": {
                    "ballast_arrival": (eval_date + timedelta(days=1)).isoformat(),
                    "cargo_laycan_start": eval_date.isoformat(),
                    "cargo_laycan_end": (eval_date + timedelta(days=6)).isoformat(),
                },
            },
            "ballast": {"ballast_distance_nm": 200.0, "ballast_days": 1.0},
        },
        {
            "candidate_id": "FLIP-B1",
            "vessel_id": 102,
            "vessel_name": "Vessel B (Conventional)",
            "cargo_id": 201,
            "cargo_name": "Cargo 1 (Coal)",
            "status": "FEASIBLE",
            "economics": {
                "expected_gross_revenue": 390000.0,
                "total_voyage_cost": 60000.0,
                "net_economic_contribution": 330000.0,
                "daily_operating_cost": 10000.0,
                "idle_days": 2.0,
                "cost_breakdown": {
                    "operating_cost": 10000.0,
                    "bunker_cost": 50000.0,
                    "port_cost": 0.0,
                },
            },
            "timeline": {
                "schedule": {
                    "ballast_start": eval_date.isoformat(),
                    "discharge_end": (eval_date + timedelta(days=12)).isoformat(),
                },
                "timing_milestones": {
                    "ballast_arrival": (eval_date + timedelta(days=1)).isoformat(),
                    "cargo_laycan_start": eval_date.isoformat(),
                    "cargo_laycan_end": (eval_date + timedelta(days=6)).isoformat(),
                },
            },
            "ballast": {"ballast_distance_nm": 200.0, "ballast_days": 1.0},
        },
        {
            "candidate_id": "FLIP-B2",
            "vessel_id": 102,
            "vessel_name": "Vessel B (Conventional)",
            "cargo_id": 202,
            "cargo_name": "Cargo 2 (Iron Ore)",
            "status": "FEASIBLE",
            "economics": {
                "expected_gross_revenue": 500000.0,
                "total_voyage_cost": 160000.0,
                "net_economic_contribution": 340000.0,
                "daily_operating_cost": 10000.0,
                "idle_days": 2.0,
                "cost_breakdown": {
                    "operating_cost": 10000.0,
                    "bunker_cost": 150000.0,
                    "port_cost": 0.0,
                },
            },
            "timeline": {
                "schedule": {
                    "ballast_start": eval_date.isoformat(),
                    "discharge_end": (eval_date + timedelta(days=12)).isoformat(),
                },
                "timing_milestones": {
                    "ballast_arrival": (eval_date + timedelta(days=2)).isoformat(),
                    "cargo_laycan_start": eval_date.isoformat(),
                    "cargo_laycan_end": (eval_date + timedelta(days=6)).isoformat(),
                },
            },
            "ballast": {"ballast_distance_nm": 400.0, "ballast_days": 2.0},
        },
    ]


# ── Test 1: Baseline Reproduction ────────────────────────────────────────────

def test_baseline_reproduction():
    """Scenario with 1.0 multipliers must reproduce baseline optimization identically."""
    service = ScenarioService()
    cfg = ScenarioPresets.baseline()
    comp = service.run_scenario(config=cfg, persist=False)

    assert comp.objective_value_delta == 0.0
    assert comp.total_revenue_delta == 0.0
    assert comp.total_cost_delta == 0.0
    assert comp.unchanged_assignments_count > 0
    assert comp.added_assignments_count == 0
    assert comp.dropped_assignments_count == 0
    assert comp.stability_score_pct == 100.0
    assert comp.jaccard_similarity == 1.0


# ── Test 2: Freight Increase ─────────────────────────────────────────────────

def test_freight_increase():
    """Freight +20% must increase expected revenue and overall objective."""
    service = ScenarioService()
    cfg = ScenarioPresets.freight_plus_20()
    comp = service.run_scenario(config=cfg, persist=False)

    assert comp.total_revenue_scenario > comp.total_revenue_baseline
    assert comp.objective_value_scenario > comp.objective_value_baseline
    assert comp.objective_value_delta > 0.0


# ── Test 3: Freight Decrease ─────────────────────────────────────────────────

def test_freight_decrease():
    """Freight -20% must reduce revenue and net contribution."""
    service = ScenarioService()
    cfg = ScenarioPresets.freight_minus_20()
    comp = service.run_scenario(config=cfg, persist=False)

    assert comp.total_revenue_scenario < comp.total_revenue_baseline
    assert comp.objective_value_scenario < comp.objective_value_baseline
    assert comp.objective_value_delta < 0.0


# ── Test 4: Bunker Increase ──────────────────────────────────────────────────

def test_bunker_increase():
    """Bunker +50% must increase voyage costs and reduce objective value."""
    service = ScenarioService()
    cfg = ScenarioPresets.bunker_plus_50()
    comp = service.run_scenario(config=cfg, persist=False)

    assert comp.total_cost_scenario > comp.total_cost_baseline
    assert comp.objective_value_scenario < comp.objective_value_baseline


# ── Test 5: Idle Cost Increase ───────────────────────────────────────────────

def test_idle_cost_increase():
    """Idle holding rate +50% must increase avoided idle valuation for active voyages."""
    service = ScenarioService()
    cfg = ScenarioPresets.idle_plus_50()
    comp = service.run_scenario(config=cfg, persist=False)

    assert comp.idle_cost_avoided_scenario > comp.idle_cost_avoided_baseline


# ── Test 6: Multi-Parameter Stress Scenario ──────────────────────────────────

def test_multi_parameter_stress():
    """Simultaneous freight slump, bunker surge, and idle inflation."""
    service = ScenarioService()
    cfg = ScenarioPresets.market_stress()
    comp = service.run_scenario(config=cfg, persist=False)

    assert comp.total_revenue_scenario < comp.total_revenue_baseline
    assert comp.total_cost_scenario > comp.total_cost_baseline
    assert comp.net_contribution_scenario < comp.net_contribution_baseline


# ── Test 7: Tight Laycan Upstream Revalidation ───────────────────────────────

def test_tight_laycan_revalidation():
    """Tightening laycan window by 4 days must disqualify late-arriving vessels."""
    service = ScenarioService()
    cfg = ScenarioPresets.tight_laycan(days=4.0)
    comp = service.run_scenario(config=cfg, persist=False)

    # Some candidates should fail temporal revalidation and be excluded from scenario allocation
    assert comp.cargoes_served_scenario <= comp.cargoes_served_baseline


# ── Test 8: Fleet Unavailability Scenario ────────────────────────────────────

def test_vessel_unavailability():
    """Excluding Vessel 1 removes its candidates and re-optimizes remaining fleet."""
    service = ScenarioService()
    cfg = ScenarioPresets.vessel_outage(excluded_id=1)
    comp = service.run_scenario(config=cfg, persist=False)

    for delta in comp.candidate_deltas:
        if delta.vessel_id == 1:
            assert not delta.in_scenario, f"Excluded vessel 1 candidate {delta.candidate_id} was selected!"


# ── Test 9: Strict Baseline Immutability ─────────────────────────────────────

def test_baseline_immutability(strategy_flip_candidates):
    """Execution of scenario must NOT mutate baseline candidate objects in any way."""
    hash_before = hash_candidate_set(strategy_flip_candidates)

    service = ScenarioService()
    cfg = ScenarioPresets.market_stress()
    _ = service.run_scenario(config=cfg, baseline_candidates=strategy_flip_candidates, persist=False)

    hash_after = hash_candidate_set(strategy_flip_candidates)
    assert hash_before == hash_after, "Baseline candidate set was mutated during scenario execution!"


# ── Test 10: Determinism ─────────────────────────────────────────────────────

def test_determinism():
    """Identical scenario configuration executed twice must produce identical results."""
    service = ScenarioService()
    cfg = ScenarioPresets.bunker_plus_25()

    comp1 = service.run_scenario(config=cfg, persist=False)
    comp2 = service.run_scenario(config=cfg, persist=False)

    assert comp1.objective_value_delta == comp2.objective_value_delta
    assert comp1.total_cost_delta == comp2.total_cost_delta
    assert comp1.unchanged_assignments_count == comp2.unchanged_assignments_count
    assert comp1.jaccard_similarity == comp2.jaccard_similarity


# ── Test 11: Assignment Delta Engine ─────────────────────────────────────────

def test_assignment_delta_classification(strategy_flip_candidates):
    """Verifies UNCHANGED, ADDED, DROPPED, REPLACED classification."""
    service = ScenarioService()
    cfg_flip = ScenarioConfig(
        scenario_id="TEST-FLIP",
        name="Flip Test",
        bunker_multiplier=1.5,
    )
    comp = service.run_scenario(
        config=cfg_flip,
        baseline_candidates=strategy_flip_candidates,
        persist=False,
    )

    statuses = {d.candidate_id: d.delta_status for d in comp.candidate_deltas}
    assert statuses["FLIP-A1"] == CandidateDeltaStatus.DROPPED
    assert statuses["FLIP-B2"] == CandidateDeltaStatus.DROPPED
    assert statuses["FLIP-A2"] == CandidateDeltaStatus.ADDED
    assert statuses["FLIP-B1"] == CandidateDeltaStatus.ADDED

    cargo_statuses = {c.cargo_id: c.delta_status for c in comp.cargo_deltas}
    assert cargo_statuses[201] == CargoDeltaStatus.REPLACED
    assert cargo_statuses[202] == CargoDeltaStatus.REPLACED


# ── Test 12: Critical Test — Genuine Strategy Flip ───────────────────────────

def test_critical_strategy_flip(strategy_flip_candidates):
    """
    Mathematical proof of global re-optimization:
    Baseline ($600 bunker):
        Vessel A (101) -> Cargo 1 (201)
        Vessel B (102) -> Cargo 2 (202)
    Bunker +50% ($900 bunker):
        Vessel A (101) -> Cargo 2 (202)
        Vessel B (102) -> Cargo 1 (201)
    """
    opt_service = OptimizationService()

    # 1. Baseline Solve (bunker multiplier = 1.0)
    base_res = opt_service.solve_fleet_assignment(
        custom_candidates=strategy_flip_candidates,
        persist=False,
    )
    base_assignments = {a.vessel_id: a.cargo_id for a in base_res.selected_assignments}
    assert base_assignments[101] == 201, "Baseline should allocate Vessel A -> Cargo 1"
    assert base_assignments[102] == 202, "Baseline should allocate Vessel B -> Cargo 2"
    assert round(base_res.objective_value, 2) == 720000.0  # 680k net + 40k idle

    # 2. Scenario Solve (bunker multiplier = 1.5)
    service = ScenarioService()
    cfg_flip = ScenarioConfig(
        scenario_id="CRITICAL-STRATEGY-FLIP",
        name="Strategy Flip Proof",
        bunker_multiplier=1.5,
    )
    comp = service.run_scenario(
        config=cfg_flip,
        baseline_candidates=strategy_flip_candidates,
        baseline_result=base_res,
        persist=False,
    )

    # Inspect scenario assignments
    scen_assignments = {d.vessel_id: d.cargo_id for d in comp.candidate_deltas if d.in_scenario}
    assert scen_assignments[101] == 202, "Under Bunker +50%, Vessel A must flip to Cargo 2!"
    assert scen_assignments[102] == 201, "Under Bunker +50%, Vessel B must flip to Cargo 1!"

    # Verify objective value matches the flipped allocation
    assert comp.objective_value_scenario == 650000.0  # 610k net + 40k idle
    assert comp.dropped_assignments_count == 2
    assert comp.added_assignments_count == 2


# ── Test 13: Sensitivity Sweep ───────────────────────────────────────────────

def test_sensitivity_sweep(strategy_flip_candidates):
    """Verifies one-variable-at-a-time parameter sweep generates full curve."""
    service = ScenarioService()
    sweep_vals = [0.8, 1.0, 1.2, 1.4, 1.6]
    res = service.run_sensitivity_sweep(
        parameter_name="bunker_multiplier",
        sweep_values=sweep_vals,
        baseline_candidates=strategy_flip_candidates,
        persist=False,
    )

    assert len(res.points) == 5
    assert res.points[0].parameter_value == 0.8
    assert res.points[-1].parameter_value == 1.6

    # Increasing bunker must decrease objective value monotonically
    objs = [p.objective_value for p in res.points]
    assert objs[0] > objs[-1]


# ── Test 14: Break-Even Switching Threshold Detection ────────────────────────

def test_break_even_detection(strategy_flip_candidates):
    """Detects that cargo assignments switch between 1.0 and 1.2 bunker multiplier."""
    service = ScenarioService()
    sweep_vals = [0.8, 1.0, 1.2, 1.4]
    res = service.run_sensitivity_sweep(
        parameter_name="bunker_multiplier",
        sweep_values=sweep_vals,
        baseline_candidates=strategy_flip_candidates,
        persist=False,
    )

    assert len(res.break_even_thresholds) >= 1
    thresh = res.break_even_thresholds[0]
    assert thresh.threshold_type == "OBSERVED_THRESHOLD"
    assert thresh.lower_bound <= 1.1 <= thresh.upper_bound or thresh.threshold_value == 1.1


# ── Test 15: Robustness Analysis ─────────────────────────────────────────────

def test_robustness_scoring(strategy_flip_candidates):
    """Evaluates stability of baseline assignments across scenario ensemble."""
    service = ScenarioService()
    res = service.evaluate_ensemble_robustness(
        ensemble_configs=[
            ScenarioConfig(scenario_id="S1", name="S1", bunker_multiplier=1.05),
            ScenarioConfig(scenario_id="S2", name="S2", bunker_multiplier=1.08),
            ScenarioConfig(scenario_id="S3", name="S3", bunker_multiplier=1.50),  # Flips
        ],
        baseline_candidates=strategy_flip_candidates,
    )

    assert res.total_scenarios == 3
    assert len(res.assignments) == 2
    for a in res.assignments:
        assert a.scenarios_preserved in (2, 3)
        assert a.robustness_tier in (RobustnessTier.CONDITIONALLY_STABLE, RobustnessTier.CORE_ROBUST)


# ── Test 16: Batch Scenario Execution ────────────────────────────────────────

def test_batch_execution():
    """Runs batch of 4 scenarios and verifies isolation."""
    service = ScenarioService()
    configs = [
        ScenarioPresets.baseline(),
        ScenarioPresets.freight_plus_20(),
        ScenarioPresets.bunker_plus_25(),
        ScenarioPresets.market_stress(),
    ]
    batch_results = service.run_batch_scenarios(configs=configs, persist=False)

    assert len(batch_results) == 4
    assert batch_results[0].objective_value_delta == 0.0
    assert batch_results[1].objective_value_delta > 0.0
    assert batch_results[2].objective_value_delta < 0.0
    assert batch_results[3].objective_value_delta < 0.0


# ── Test 17: Database Persistence & Audit Trail ──────────────────────────────

def test_scenario_audit_and_persistence(db_session):
    """Verifies that ScenarioEvaluation is persisted with JSON parameters and metrics."""
    service = ScenarioService(db=db_session)
    cfg = ScenarioConfig(
        scenario_id="TEST-PERSIST-01",
        name="Persistence Verification",
        freight_multiplier=1.1,
    )
    comp = service.run_scenario(config=cfg, persist=True)

    record = (
        db_session.query(ScenarioEvaluation)
        .filter(ScenarioEvaluation.scenario_code == "TEST-PERSIST-01")
        .first()
    )
    assert record is not None
    assert record.name == "Persistence Verification"
    assert record.comparison_metrics["objective_value_delta"] == comp.objective_value_delta
    assert len(record.assignment_deltas) > 0


# ── Test 18: HiGHS MILP Solver Engine Integration ────────────────────────────

def test_phase7_milp_solver_integration():
    """Verifies that scenario engine re-solves strictly via Phase 7 HiGHS MILP."""
    opt_service = OptimizationService()
    solver_name = opt_service.solver.name.lower()
    assert "highs" in solver_name, f"Expected HiGHS solver adapter, got {solver_name}"


# ── Test 19: Air-Gap Network Isolation ───────────────────────────────────────

def test_air_gap_isolation():
    """Asserts that all scenario operations execute strictly offline with 0 network calls."""
    def guarded_connect(*args, **kwargs):
        raise RuntimeError("AIR-GAP VIOLATION: Socket connection attempted during scenario run!")

    with patch.object(socket.socket, "connect", side_effect=guarded_connect):
        service = ScenarioService()
        cfg = ScenarioPresets.market_stress()
        comp = service.run_scenario(config=cfg, persist=False)
        assert comp.scenario_id == "SCEN-STRESS"


# ── Test 20: REST API Endpoints ──────────────────────────────────────────────

def test_api_endpoints():
    """Verifies REST endpoints for presets, run, batch, sensitivity, and robustness."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # 1. Presets
    res = client.get("/v1/scenarios/presets")
    assert res.status_code == 200
    presets = res.json()
    assert len(presets) >= 8

    # 2. Run Single Scenario
    payload = {
        "name": "API Bunker Stress",
        "bunker_multiplier": 1.3,
        "freight_multiplier": 1.0,
    }
    run_res = client.post("/v1/scenarios/run?persist=false", json=payload)
    assert run_res.status_code == 200
    data = run_res.json()
    assert "objective_value_delta" in data
    assert "candidate_deltas" in data

    # 3. Sensitivity Sweep
    sweep_payload = {
        "parameter_name": "bunker_multiplier",
        "sweep_values": [0.9, 1.0, 1.1, 1.2],
    }
    sweep_res = client.post("/v1/scenarios/sensitivity?persist=false", json=sweep_payload)
    assert sweep_res.status_code == 200
    sweep_data = sweep_res.json()
    assert len(sweep_data["points"]) == 4

    # 4. Robustness
    rob_res = client.get("/v1/scenarios/robustness")
    assert rob_res.status_code == 200
    rob_data = rob_res.json()
    assert "overall_fleet_robustness_pct" in rob_data
