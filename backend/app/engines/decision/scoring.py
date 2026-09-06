"""
VesselOptima — Phase 10 Decision Intelligence Engine
Deterministic Scoring and Risk-Adjusted Economic Evaluation

Computes the composite Decision Score [0, 100], itemized score components,
and Risk-Adjusted Economic Contribution.
"""

from typing import Optional
from app.engines.decision.models import (
    DecisionScoreBreakdown,
    DecisionThresholds,
)


def calculate_decision_score(
    expected_contribution: float,
    baseline_contribution: Optional[float],
    plan_reliability_score: float,
    scenario_survival_rate: float,
    loss_probability: float,
    cvar_95_downside: float,
    laycan_miss_probability: float,
    schedule_buffer_days: float,
    thresholds: Optional[DecisionThresholds] = None,
) -> DecisionScoreBreakdown:
    """
    Computes deterministic composite decision score in [0, 100] and component breakdown.

    Formula:
        Score = w_e * Econ + w_rel * Rel + w_rob * Rob - w_risk * RiskPen - w_sched * SchedPen
    Default weights:
        w_e = 0.35, w_rel = 0.25, w_rob = 0.20, w_risk = 0.10, w_sched = 0.10
    """
    if thresholds is None:
        thresholds = DecisionThresholds()

    w = thresholds.weights

    # 1. Economic Sub-score [0, 100]
    benchmark = baseline_contribution if (baseline_contribution and baseline_contribution > 0) else max(expected_contribution, 1.0)
    if expected_contribution <= 0:
        econ_subscore = 0.0
    else:
        # Scale proportion against benchmark (capped at 1.0 if matching or exceeding benchmark)
        econ_ratio = min(1.0, max(0.0, expected_contribution / benchmark))
        econ_subscore = econ_ratio * 100.0

    # 2. Reliability Sub-score [0, 100]
    rel_subscore = max(0.0, min(100.0, plan_reliability_score))

    # 3. Robustness Sub-score [0, 100]
    rob_subscore = max(0.0, min(100.0, scenario_survival_rate * 100.0))

    # 4. Risk Penalty [0, 100]
    # Loss probability penalty: 0% -> 0 pts, >= 20% -> 50 pts
    loss_pen = min(1.0, max(0.0, loss_probability / 0.20)) * 50.0
    # Tail risk penalty: downside CVaR ratio to expected contribution: 0 -> 0 pts, >= 50% -> 50 pts
    base_for_tail = max(abs(expected_contribution), 1.0)
    tail_ratio = max(0.0, cvar_95_downside / base_for_tail)
    tail_pen = min(1.0, tail_ratio / 0.50) * 50.0
    risk_pen_score = min(100.0, loss_pen + tail_pen)

    # 5. Schedule Penalty [0, 100]
    # Laycan miss penalty: 0% -> 0 pts, >= 20% -> 60 pts
    laycan_pen = min(1.0, max(0.0, laycan_miss_probability / 0.20)) * 60.0
    # Buffer penalty: >= 2.0 days buffer -> 0 pts, 0 days buffer -> 40 pts
    buffer_pen = max(0.0, min(1.0, (thresholds.min_schedule_buffer_days - schedule_buffer_days) / thresholds.min_schedule_buffer_days)) * 40.0
    sched_pen_score = min(100.0, laycan_pen + buffer_pen)

    # Calculate weighted contributions
    economic_component = round(w.economic * econ_subscore, 2)
    reliability_component = round(w.reliability * rel_subscore, 2)
    robustness_component = round(w.robustness * rob_subscore, 2)
    risk_penalty = round(w.risk_penalty * risk_pen_score, 2)
    schedule_penalty = round(w.schedule_penalty * sched_pen_score, 2)

    raw_score = (
        economic_component
        + reliability_component
        + robustness_component
        - risk_penalty
        - schedule_penalty
    )

    composite_score = round(max(0.0, min(100.0, raw_score)), 1)

    return DecisionScoreBreakdown(
        economic_component=economic_component,
        reliability_component=reliability_component,
        robustness_component=robustness_component,
        risk_penalty=risk_penalty,
        schedule_penalty=schedule_penalty,
        composite_score=composite_score,
    )


def calculate_risk_adjusted_contribution(
    expected_contribution: float,
    cvar_95_downside: float,
    lambda_param: float = 0.50,
) -> float:
    """
    Computes the Risk-Adjusted Economic Contribution.

    Formula:
        Risk-Adjusted Contribution = E[Profit] - lambda * CVaR95_downside

    Note:
        This is a decision-support evaluation metric, NOT the Phase 7 MILP objective.
        Phase 7 optimizes deterministic contribution. Phase 10 penalizes expected tail loss.
    """
    cvar_downside_clean = max(0.0, cvar_95_downside)
    risk_adjusted = expected_contribution - (lambda_param * cvar_downside_clean)
    return round(risk_adjusted, 2)
