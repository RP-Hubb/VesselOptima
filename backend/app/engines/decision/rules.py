"""
VesselOptima — Phase 10 Decision Intelligence Engine
Deterministic Decision Gating Rules

Evaluates plan-level and assignment-level evidence against explicit thresholds
to produce deterministic recommendation types and reason codes.
"""

from typing import List, Optional, Tuple
from app.engines.decision.models import DecisionThresholds
from app.engines.decision.reason_codes import DecisionReasonCode, RecommendationType


def evaluate_plan_recommendation(
    decision_score: float,
    expected_contribution: float,
    loss_probability: float,
    cvar_95_downside: float,
    plan_reliability_score: float,
    laycan_miss_probability: float,
    strategy_flip_identified: bool = False,
    critical_warnings: Optional[List[str]] = None,
    thresholds: Optional[DecisionThresholds] = None,
) -> Tuple[RecommendationType, DecisionReasonCode, List[DecisionReasonCode]]:
    """
    Deterministically evaluates plan recommendation type and reason codes.

    Returns:
        (RecommendationType, primary_reason_code, list_of_all_reason_codes)
    """
    if thresholds is None:
        thresholds = DecisionThresholds()

    if critical_warnings is None:
        critical_warnings = []

    reason_codes: List[DecisionReasonCode] = []

    # Calculate tail risk ratio
    base_contrib = max(abs(expected_contribution), 1.0)
    tail_ratio = max(0.0, cvar_95_downside / base_contrib)

    # 1. Check REJECT conditions
    if expected_contribution <= 0:
        reason_codes.append(DecisionReasonCode.RC_NEGATIVE_EXPECTED_CONTRIBUTION)
        return RecommendationType.REJECT, DecisionReasonCode.RC_NEGATIVE_EXPECTED_CONTRIBUTION, reason_codes

    if loss_probability >= thresholds.max_loss_prob_reconsider:
        reason_codes.append(DecisionReasonCode.RC_EXTREME_TAIL_RISK)
        return RecommendationType.REJECT, DecisionReasonCode.RC_EXTREME_TAIL_RISK, reason_codes

    # 2. Check RECONSIDER conditions
    if loss_probability > thresholds.max_loss_prob_caution:
        reason_codes.append(DecisionReasonCode.RC_HIGH_LOSS_PROBABILITY)

    if plan_reliability_score < thresholds.min_reliability_caution:
        reason_codes.append(DecisionReasonCode.RC_INSUFFICIENT_ECONOMIC_RETURN)

    if decision_score < thresholds.min_score_caution:
        if not reason_codes:
            reason_codes.append(DecisionReasonCode.RC_INSUFFICIENT_ECONOMIC_RETURN)
        return RecommendationType.RECONSIDER, reason_codes[0], reason_codes

    if reason_codes:
        return RecommendationType.RECONSIDER, reason_codes[0], reason_codes

    # 3. Check PROCEED_WITH_CAUTION conditions
    caution_triggers: List[DecisionReasonCode] = []

    if strategy_flip_identified:
        caution_triggers.append(DecisionReasonCode.RC_STRATEGY_FLIP_WARNING)

    if tail_ratio > thresholds.max_cvar95_downside_ratio_proceed:
        caution_triggers.append(DecisionReasonCode.RC_TAIL_LOSS_EXPOSURE)

    if loss_probability > thresholds.max_loss_prob_proceed:
        caution_triggers.append(DecisionReasonCode.RC_MODERATE_VOLATILITY)

    if laycan_miss_probability > thresholds.max_laycan_miss_prob_proceed:
        caution_triggers.append(DecisionReasonCode.RC_LAYCAN_MISS_RISK)

    if decision_score < thresholds.min_score_proceed:
        caution_triggers.append(DecisionReasonCode.RC_SCHEDULE_FRAGILITY)

    if caution_triggers:
        return RecommendationType.PROCEED_WITH_CAUTION, caution_triggers[0], caution_triggers

    # 4. If all checks pass -> PROCEED
    proceed_codes = [
        DecisionReasonCode.RC_SUPERIOR_ECONOMICS,
        DecisionReasonCode.RC_ROBUST_UNDER_STRESS,
        DecisionReasonCode.RC_NEGLIGIBLE_TAIL_RISK,
        DecisionReasonCode.RC_HIGH_SCHEDULE_BUFFER,
    ]
    return RecommendationType.PROCEED, DecisionReasonCode.RC_SUPERIOR_ECONOMICS, proceed_codes


def evaluate_assignment_recommendation(
    expected_contribution: float,
    loss_probability: float,
    cvar_95: float,
    schedule_buffer_days: float,
    laycan_miss_probability: float,
    risk_tier: str = "LOW",
    thresholds: Optional[DecisionThresholds] = None,
) -> Tuple[RecommendationType, DecisionReasonCode, List[DecisionReasonCode]]:
    """
    Deterministically evaluates individual assignment recommendation type and reason codes.
    """
    if thresholds is None:
        thresholds = DecisionThresholds()

    reason_codes: List[DecisionReasonCode] = []

    # 1. Reject
    if expected_contribution <= 0:
        reason_codes.append(DecisionReasonCode.RC_NEGATIVE_EXPECTED_CONTRIBUTION)
        return RecommendationType.REJECT, DecisionReasonCode.RC_NEGATIVE_EXPECTED_CONTRIBUTION, reason_codes

    # 2. Reconsider
    if loss_probability >= thresholds.max_loss_prob_caution or laycan_miss_probability >= 0.20:
        reason_codes.append(DecisionReasonCode.RC_HIGH_LOSS_PROBABILITY)
        return RecommendationType.RECONSIDER, DecisionReasonCode.RC_HIGH_LOSS_PROBABILITY, reason_codes

    # 3. Caution
    cautions: List[DecisionReasonCode] = []
    if laycan_miss_probability > thresholds.max_laycan_miss_prob_proceed:
        cautions.append(DecisionReasonCode.RC_LAYCAN_MISS_RISK)

    if schedule_buffer_days < thresholds.min_schedule_buffer_days:
        cautions.append(DecisionReasonCode.RC_SCHEDULE_FRAGILITY)

    if loss_probability > thresholds.max_loss_prob_proceed:
        cautions.append(DecisionReasonCode.RC_TAIL_LOSS_EXPOSURE)

    if risk_tier in ("HIGH", "CRITICAL"):
        cautions.append(DecisionReasonCode.RC_MODERATE_VOLATILITY)

    if cautions:
        return RecommendationType.PROCEED_WITH_CAUTION, cautions[0], cautions

    # 4. Proceed
    proceed_codes = [
        DecisionReasonCode.RC_SUPERIOR_ECONOMICS,
        DecisionReasonCode.RC_HIGH_SCHEDULE_BUFFER,
    ]
    return RecommendationType.PROCEED, DecisionReasonCode.RC_SUPERIOR_ECONOMICS, proceed_codes
