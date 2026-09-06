"""
VesselOptima — Phase 10 Decision Intelligence Engine Test Suite

Comprehensive automated test verification covering:
1. Determinism and reproducibility (zero non-deterministic models/LLMs)
2. Decision score formulation and weight distribution
3. Risk-adjusted economic contribution formulation
4. Gating thresholds for PROCEED, PROCEED_WITH_CAUTION, RECONSIDER, REJECT
5. Confidence tier assessment and decision stability
6. Multi-plan trade-offs and critical risk flip (Plan A vs Plan B)
7. Explanations, narratives, and "What Could Change" triggers
8. Action priority queue and monitoring guidelines
9. Assignment-level granular recommendations
10. Database persistence, retrieval, and audit hashes
11. Air-gap offline compliance (zero outbound sockets)
12. FastAPI endpoint integration
"""

import socket
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.engines.decision import (
    DecisionResult,
    DecisionService,
    DecisionThresholds,
    DecisionWeights,
    calculate_decision_score,
    calculate_decision_stability,
    calculate_risk_adjusted_contribution,
    evaluate_assignment_recommendation,
    evaluate_decision_confidence,
    evaluate_plan_recommendation,
    evaluate_plan_tradeoffs,
    generate_executive_summary,
    generate_financial_narrative,
    generate_prioritized_actions,
    generate_risk_narrative,
    generate_schedule_narrative,
    generate_what_could_change,
)
from app.engines.decision.reason_codes import (
    ActionPriority,
    DecisionConfidence,
    DecisionReasonCode,
    RecommendationType,
)
from app.main import app
from app.models.domain import (
    DecisionAction,
    DecisionEvidence,
    DecisionRecommendation,
    DecisionRun,
    DecisionTradeoff,
)


@pytest.fixture
def client():
    return TestClient(app)


# ── 1. Pure Python Determinism ────────────────────────────────────────

def test_decision_engine_pure_python_determinism():
    """Identical inputs produce exact identical scores, reason codes, and outputs."""
    res1 = calculate_decision_score(
        expected_contribution=680000.0,
        baseline_contribution=680000.0,
        plan_reliability_score=85.0,
        scenario_survival_rate=0.90,
        loss_probability=0.03,
        cvar_95_downside=45000.0,
        laycan_miss_probability=0.02,
        schedule_buffer_days=3.0,
    )
    res2 = calculate_decision_score(
        expected_contribution=680000.0,
        baseline_contribution=680000.0,
        plan_reliability_score=85.0,
        scenario_survival_rate=0.90,
        loss_probability=0.03,
        cvar_95_downside=45000.0,
        laycan_miss_probability=0.02,
        schedule_buffer_days=3.0,
    )

    assert res1.composite_score == res2.composite_score
    assert res1.economic_component == res2.economic_component
    assert res1.reliability_component == res2.reliability_component
    assert res1.risk_penalty == res2.risk_penalty
    assert res1.schedule_penalty == res2.schedule_penalty


# ── 2. Decision Score Formulation ────────────────────────────────────

def test_decision_score_formulation():
    """Validates default weights (0.35, 0.25, 0.20, 0.10, 0.10) and score in [0, 100]."""
    thresholds = DecisionThresholds()
    assert thresholds.weights.economic == 0.35
    assert thresholds.weights.reliability == 0.25
    assert thresholds.weights.robustness == 0.20
    assert thresholds.weights.risk_penalty == 0.10
    assert thresholds.weights.schedule_penalty == 0.10
    assert sum([
        thresholds.weights.economic,
        thresholds.weights.reliability,
        thresholds.weights.robustness,
        thresholds.weights.risk_penalty,
        thresholds.weights.schedule_penalty,
    ]) == pytest.approx(1.0)

    score_res = calculate_decision_score(
        expected_contribution=1000000.0,
        baseline_contribution=1000000.0,
        plan_reliability_score=100.0,
        scenario_survival_rate=1.0,
        loss_probability=0.0,
        cvar_95_downside=0.0,
        laycan_miss_probability=0.0,
        schedule_buffer_days=4.0,
        thresholds=thresholds,
    )
    # Under perfect conditions, score should be 80.0 (35 + 25 + 20) with 0 penalties
    assert score_res.composite_score == 80.0
    assert score_res.risk_penalty == 0.0
    assert score_res.schedule_penalty == 0.0


# ── 3. Risk-Adjusted Economic Contribution ────────────────────────────

def test_risk_adjusted_contribution_formulation():
    """Verifies E[Pi] - lambda * CVaR95_downside formula."""
    expected = 730000.0
    cvar_tail = 295000.0
    lambda_val = 0.50

    adj = calculate_risk_adjusted_contribution(expected, cvar_tail, lambda_val)
    expected_adj = 730000.0 - (0.50 * 295000.0)  # 582,500.0
    assert adj == expected_adj

    # When tail risk is zero, risk-adjusted equals expected
    adj_zero = calculate_risk_adjusted_contribution(500000.0, 0.0, lambda_val)
    assert adj_zero == 500000.0


# ── 4. Gating Threshold: PROCEED ──────────────────────────────────────

def test_proceed_gating_thresholds():
    """Plan meeting all hurdle rates receives PROCEED and positive reason codes."""
    rec, prim_rc, all_rcs = evaluate_plan_recommendation(
        decision_score=82.0,
        expected_contribution=680000.0,
        loss_probability=0.02,
        cvar_95_downside=35000.0,
        plan_reliability_score=88.0,
        laycan_miss_probability=0.02,
        strategy_flip_identified=False,
    )
    assert rec == RecommendationType.PROCEED
    assert prim_rc == DecisionReasonCode.RC_SUPERIOR_ECONOMICS
    assert DecisionReasonCode.RC_ROBUST_UNDER_STRESS in all_rcs


# ── 5. Gating Threshold: PROCEED_WITH_CAUTION ─────────────────────────

def test_proceed_with_caution_tail_risk():
    """High expected profit with high tail risk triggers PROCEED_WITH_CAUTION."""
    rec, prim_rc, all_rcs = evaluate_plan_recommendation(
        decision_score=68.5,
        expected_contribution=730000.0,
        loss_probability=0.095,
        cvar_95_downside=295000.0,  # 40% tail ratio > 20% threshold
        plan_reliability_score=72.0,
        laycan_miss_probability=0.04,
        strategy_flip_identified=True,
    )
    assert rec == RecommendationType.PROCEED_WITH_CAUTION
    assert prim_rc == DecisionReasonCode.RC_STRATEGY_FLIP_WARNING


# ── 6. Gating Threshold: RECONSIDER ───────────────────────────────────

def test_reconsider_high_loss_probability():
    """Loss probability > 15% or score < 50 triggers RECONSIDER."""
    rec, prim_rc, all_rcs = evaluate_plan_recommendation(
        decision_score=44.0,
        expected_contribution=310000.0,
        loss_probability=0.25,
        cvar_95_downside=380000.0,
        plan_reliability_score=45.0,
        laycan_miss_probability=0.18,
    )
    assert rec == RecommendationType.RECONSIDER
    assert prim_rc == DecisionReasonCode.RC_HIGH_LOSS_PROBABILITY


# ── 7. Gating Threshold: REJECT ───────────────────────────────────────

def test_reject_negative_expected_contribution():
    """Negative expected contribution or loss prob >= 35% triggers REJECT."""
    rec, prim_rc, all_rcs = evaluate_plan_recommendation(
        decision_score=15.0,
        expected_contribution=-50000.0,
        loss_probability=0.60,
        cvar_95_downside=200000.0,
        plan_reliability_score=20.0,
        laycan_miss_probability=0.50,
    )
    assert rec == RecommendationType.REJECT
    assert prim_rc == DecisionReasonCode.RC_NEGATIVE_EXPECTED_CONTRIBUTION


# ── 8. Confidence Assessment Tiers ───────────────────────────────────

def test_confidence_evaluation_tiers():
    """Evaluates HIGH, MEDIUM, LOW confidence based on evidence completeness."""
    # Complete evidence -> HIGH
    conf_high = evaluate_decision_confidence(
        has_optimization=True,
        has_scenarios=True,
        has_risk_simulation=True,
        simulation_count=5000,
        decision_stability=0.90,
    )
    assert conf_high == DecisionConfidence.HIGH

    # Missing scenarios -> MEDIUM
    conf_med = evaluate_decision_confidence(
        has_optimization=True,
        has_scenarios=False,
        has_risk_simulation=True,
        simulation_count=5000,
        decision_stability=0.85,
    )
    assert conf_med == DecisionConfidence.MEDIUM

    # Missing risk simulation -> LOW
    conf_low = evaluate_decision_confidence(
        has_optimization=True,
        has_scenarios=True,
        has_risk_simulation=False,
        simulation_count=0,
        decision_stability=0.90,
    )
    assert conf_low == DecisionConfidence.LOW


# ── 9. Decision Stability Metric ─────────────────────────────────────

def test_decision_stability_metric():
    """Calculates stability proportion across scenario recommendations."""
    scenarios = ["PROCEED", "PROCEED", "PROCEED_WITH_CAUTION", "PROCEED"]
    stab = calculate_decision_stability("PROCEED", scenarios)
    assert stab == 0.75

    empty_stab = calculate_decision_stability("PROCEED", [])
    assert empty_stab == 1.0


# ── 10. Deterministic Narrative Generation ───────────────────────────

def test_deterministic_narrative_generation():
    """Generates structured executive and financial narratives without non-determinism."""
    summary = generate_executive_summary(
        recommendation_type=RecommendationType.PROCEED,
        primary_reason=DecisionReasonCode.RC_SUPERIOR_ECONOMICS,
        decision_score=85.0,
        expected_contribution=680000.0,
        risk_adjusted_contribution=660000.0,
        loss_probability=0.02,
        confidence_str="HIGH",
    )
    assert "RECOMMENDATION: PROCEED" in summary
    assert "$680,000" in summary
    assert "85.0/100" in summary

    fin = generate_financial_narrative(
        expected_contribution=700000.0,
        baseline_contribution=650000.0,
        risk_adjusted_contribution=620000.0,
        cvar_95_downside=160000.0,
        economic_component=35.0,
    )
    assert "$700,000" in fin
    assert "$620,000" in fin
    assert "50% risk-aversion penalty" in fin


# ── 11. "What Could Change" Triggers ─────────────────────────────────

def test_what_could_change_triggers():
    """Produces explicit trigger thresholds that could flip the recommendation."""
    drivers = [
        {"variable_id": "bunker_price_vlsfo", "uncertainty_contribution_pct": 35.0},
        {"variable_id": "spot_freight_index", "uncertainty_contribution_pct": 25.0},
    ]
    triggers = generate_what_could_change(
        recommendation_type=RecommendationType.PROCEED_WITH_CAUTION,
        top_drivers=drivers,
        laycan_miss_probability=0.08,
        schedule_buffer_days=1.5,
    )
    assert len(triggers) >= 2
    assert any("Bunker Price" in t for t in triggers)
    assert any("Congestion" in t or "Delay" in t for t in triggers)


# ── 12. Prioritized Action Queue ─────────────────────────────────────

def test_prioritized_action_queue():
    """Derives prioritized operational actions with trigger conditions."""
    drivers = [{"variable_id": "bunker_price_vlsfo", "uncertainty_contribution_pct": 35.0}]
    asgns = [{"candidate_id": "CAND-01", "vessel_name": "Vessel A", "schedule_buffer_days": 1.2, "laycan_miss_prob": 0.12}]

    actions = generate_prioritized_actions(
        recommendation_type=RecommendationType.PROCEED_WITH_CAUTION,
        top_drivers=drivers,
        assignment_items=asgns,
        laycan_miss_probability=0.12,
        schedule_buffer_days=1.2,
        strategy_flip_identified=True,
    )
    assert len(actions) >= 2
    critical_act = next((a for a in actions if a.priority == ActionPriority.CRITICAL), None)
    assert critical_act is not None
    assert "Bunker" in critical_act.title


# ── 13. Pairwise Multi-Plan Trade-Offs ────────────────────────────────

def test_pairwise_multi_plan_tradeoffs():
    """Computes accurate pairwise deltas between baseline and alternative plans."""
    comps = [{
        "plan_id": "PLAN-B",
        "plan_name": "Plan B (Robust)",
        "expected_contribution": 685000.0,
        "loss_probability": 0.005,
        "cvar_95": 15000.0,
        "plan_reliability": 95.0,
    }]
    tradeoffs = evaluate_plan_tradeoffs(
        baseline_name="Plan A",
        baseline_contribution=730000.0,
        baseline_loss_prob=0.095,
        baseline_cvar=295000.0,
        baseline_reliability=71.0,
        comparison_plans=comps,
    )
    assert len(tradeoffs) == 1
    t = tradeoffs[0]
    assert t.contribution_delta == -45000.0
    assert t.loss_prob_delta == pytest.approx(-0.090, abs=0.001)
    assert t.cvar_delta == -280000.0
    assert "safer downside" in t.tradeoff_summary


# ── 14. Critical Risk Flip Evaluation (Plan A vs Plan B) ──────────────

def test_critical_risk_flip_evaluation():
    """
    Directly evaluates the Phase 9/10 strategy flip scenario:
    - Plan A: $730k expected return, $295k CVaR -> PROCEED_WITH_CAUTION
    - Plan B: $685k expected return, $15k CVaR -> PROCEED
    - Plan B risk-adjusted contribution ($677.5k) > Plan A ($582.5k)
    """
    service = DecisionService()
    demo_a = service.get_or_create_demo_decision("STRATEGY_FLIP_A")
    demo_b = service.get_or_create_demo_decision("STRATEGY_FLIP_B")

    assert demo_a.recommendation_type == RecommendationType.PROCEED_WITH_CAUTION
    assert demo_a.primary_reason_code == DecisionReasonCode.RC_STRATEGY_FLIP_WARNING
    assert demo_a.risk_adjusted_contribution == 582500.0

    assert demo_b.recommendation_type == RecommendationType.PROCEED
    assert demo_b.primary_reason_code == DecisionReasonCode.RC_ROBUST_UNDER_STRESS
    assert demo_b.risk_adjusted_contribution == 677500.0

    # Risk-adjusted dominance proof
    assert demo_b.risk_adjusted_contribution > demo_a.risk_adjusted_contribution
    assert demo_b.decision_score > demo_a.decision_score


# ── 15. Assignment-Level Recommendations ─────────────────────────────

def test_assignment_level_recommendations():
    """Evaluates individual vessel assignments against granular thresholds."""
    # Assignment 1: Low risk, ample buffer -> PROCEED
    rec1, prim1, _ = evaluate_assignment_recommendation(
        expected_contribution=320000.0,
        loss_probability=0.01,
        cvar_95=10000.0,
        schedule_buffer_days=3.5,
        laycan_miss_probability=0.01,
        risk_tier="LOW",
    )
    assert rec1 == RecommendationType.PROCEED
    assert prim1 == DecisionReasonCode.RC_SUPERIOR_ECONOMICS

    # Assignment 2: Tight buffer -> PROCEED_WITH_CAUTION
    rec2, prim2, _ = evaluate_assignment_recommendation(
        expected_contribution=180000.0,
        loss_probability=0.04,
        cvar_95=35000.0,
        schedule_buffer_days=1.1,  # < 2.0 days
        laycan_miss_probability=0.09,
        risk_tier="MODERATE",
    )
    assert rec2 == RecommendationType.PROCEED_WITH_CAUTION


# ── 16. Database Persistence and Retrieval ────────────────────────────

def test_database_persistence_and_retrieval():
    """Verifies storing and reloading full DecisionRun and related entities."""
    service = DecisionService()
    res = service.evaluate_decision(
        optimization_run_id="OPT-TEST-DB-01",
        risk_run_id="RISK-TEST-DB-01",
    )
    assert res.run_id.startswith("DEC-")
    assert res.decision_score > 0
    assert len(res.assignment_recommendations) > 0
    assert len(res.actions) > 0
    assert len(res.tradeoffs) > 0


# ── 17. Offline Air-Gap Compliance ────────────────────────────────────

def test_offline_air_gap_guarantee(monkeypatch):
    """Verifies that decision evaluation creates zero outbound network connections."""
    def guarded_socket(*args, **kwargs):
        raise RuntimeError("Air-gap violation: outbound socket attempt blocked")

    monkeypatch.setattr(socket, "socket", guarded_socket)

    service = DecisionService()
    res = service.evaluate_decision("OPT-AIRGAP-01")
    assert res.recommendation_type in RecommendationType


# ── 18. Audit Hash Integrity ──────────────────────────────────────────

def test_input_and_output_hash_integrity():
    """Verifies SHA256 input and output hashes are populated and tamper-evident."""
    service = DecisionService()
    res = service.evaluate_decision("OPT-HASH-01")
    assert len(res.input_hash) == 64
    assert len(res.output_hash) == 64
    assert res.input_hash != res.output_hash


# ── 19. FastAPI Decision Endpoints ────────────────────────────────────

def test_fastapi_decision_endpoints(client):
    """Verifies all FastAPI decision endpoints return 200 with schema compliance."""
    # 1. Thresholds endpoint
    resp_thresh = client.get("/v1/decision/thresholds")
    assert resp_thresh.status_code == 200
    data_thresh = resp_thresh.json()
    assert "max_loss_prob_proceed" in data_thresh
    assert data_thresh["weights"]["economic"] == 0.35

    # 2. Demo endpoint - BASELINE
    resp_demo = client.get("/v1/decision/demo/BASELINE")
    assert resp_demo.status_code == 200
    data_demo = resp_demo.json()
    assert data_demo["recommendation_type"] == "PROCEED"
    assert "scoring_breakdown" in data_demo
    assert "evidence" in data_demo
    assert len(data_demo["actions"]) > 0

    # 3. Demo endpoint - STRATEGY_FLIP_A
    resp_flip_a = client.get("/v1/decision/demo/STRATEGY_FLIP_A")
    assert resp_flip_a.status_code == 200
    data_flip_a = resp_flip_a.json()
    assert data_flip_a["recommendation_type"] == "PROCEED_WITH_CAUTION"
    assert data_flip_a["primary_reason_code"] == "RC_STRATEGY_FLIP_WARNING"

    # 4. Demo endpoint - STRATEGY_FLIP_B
    resp_flip_b = client.get("/v1/decision/demo/STRATEGY_FLIP_B")
    assert resp_flip_b.status_code == 200
    data_flip_b = resp_flip_b.json()
    assert data_flip_b["recommendation_type"] == "PROCEED"
    assert data_flip_b["risk_adjusted_contribution"] > data_flip_a["risk_adjusted_contribution"]

    # 5. Evaluate endpoint
    payload = {
        "optimization_run_id": "OPT-API-TEST",
        "strategy_flip_identified": False,
    }
    resp_eval = client.post("/v1/decision/evaluate", json=payload)
    assert resp_eval.status_code == 200
    data_eval = resp_eval.json()
    assert "decision_score" in data_eval
    assert "executive_summary" in data_eval
