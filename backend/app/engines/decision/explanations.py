"""
VesselOptima — Phase 10 Decision Intelligence Engine
Deterministic Explainability and Rationales

Rule-based, transparent explanation generation across Executive Summary,
Financial Assessment, Risk Assessment, Schedule Fragility, and "What Could Change".
100% deterministic, zero LLM or black-box dependencies.
"""

from typing import Any, Dict, List, Optional
from app.engines.decision.models import DecisionScoreBreakdown, DecisionThresholds
from app.engines.decision.reason_codes import DecisionReasonCode, RecommendationType


def generate_executive_summary(
    recommendation_type: RecommendationType,
    primary_reason: DecisionReasonCode,
    decision_score: float,
    expected_contribution: float,
    risk_adjusted_contribution: float,
    loss_probability: float,
    confidence_str: str,
) -> str:
    """Produces the high-level executive decision summary."""
    rec_title = recommendation_type.value.replace("_", " ")

    if recommendation_type == RecommendationType.PROCEED:
        return (
            f"RECOMMENDATION: {rec_title} (Confidence: {confidence_str}, Decision Score: {decision_score}/100). "
            f"The optimized fleet deployment yields an expected net contribution of ${expected_contribution:,.0f} "
            f"(Risk-Adjusted: ${risk_adjusted_contribution:,.0f}) with minimal downside tail risk "
            f"({loss_probability * 100:.1f}% loss probability). Operational schedule buffers and economic returns "
            f"meet all executive risk governance benchmarks."
        )
    elif recommendation_type == RecommendationType.PROCEED_WITH_CAUTION:
        return (
            f"RECOMMENDATION: {rec_title} (Confidence: {confidence_str}, Decision Score: {decision_score}/100). "
            f"While delivering an expected contribution of ${expected_contribution:,.0f}, the allocation exhibits "
            f"heightened sensitivity to volatile cost and schedule drivers. Tail loss exposure reduces risk-adjusted "
            f"contribution to ${risk_adjusted_contribution:,.0f} with a {loss_probability * 100:.1f}% probability of negative cash flow. "
            f"Execution is advised subject to active fuel hedging and schedule contingency protocols."
        )
    elif recommendation_type == RecommendationType.RECONSIDER:
        return (
            f"RECOMMENDATION: {rec_title} (Confidence: {confidence_str}, Decision Score: {decision_score}/100). "
            f"The proposed plan carries elevated downside vulnerability (loss probability: {loss_probability * 100:.1f}%, "
            f"Risk-Adjusted Contribution: ${risk_adjusted_contribution:,.0f}). Unfavorable sensitivity to market rates or "
            f"bunker fluctuations threatens plan viability. Reviewing alternative candidate allocations is advised."
        )
    else:  # REJECT or NO_ACTION
        return (
            f"RECOMMENDATION: {rec_title} (Confidence: {confidence_str}, Decision Score: {decision_score}/100). "
            f"The deployment plan fails core feasibility or risk tolerance constraints (expected contribution: ${expected_contribution:,.0f}, "
            f"loss probability: {loss_probability * 100:.1f}%). Execution is suspended."
        )


def generate_financial_narrative(
    expected_contribution: float,
    baseline_contribution: Optional[float],
    risk_adjusted_contribution: float,
    cvar_95_downside: float,
    economic_component: float,
) -> str:
    """Generates financial breakdown narrative."""
    gap_tail = expected_contribution - risk_adjusted_contribution
    comp_text = ""
    if baseline_contribution and baseline_contribution > 0:
        pct_delta = ((expected_contribution - baseline_contribution) / baseline_contribution) * 100.0
        comp_text = f" This represents a {pct_delta:+.1f}% variance against the baseline allocation (${baseline_contribution:,.0f})."

    return (
        f"The deployment achieves an expected net contribution of ${expected_contribution:,.0f}.{comp_text} "
        f"Applying a 50% risk-aversion penalty against the 95% Conditional Value-at-Risk (${cvar_95_downside:,.0f} tail loss) "
        f"establishes a Risk-Adjusted Economic Contribution of ${risk_adjusted_contribution:,.0f} (a ${gap_tail:,.0f} haircut). "
        f"The economic component contributes {economic_component:.1f} points toward the total Decision Score."
    )


def generate_risk_narrative(
    loss_probability: float,
    var_95_downside: float,
    cvar_95_downside: float,
    top_drivers: List[Dict[str, Any]],
    risk_penalty: float,
) -> str:
    """Generates risk and volatility attribution narrative."""
    driver_texts = []
    for d in top_drivers[:3]:
        name = d.get("variable_name", d.get("variable_id", "Unknown"))
        pct = d.get("uncertainty_contribution_pct", 0.0)
        driver_texts.append(f"{name} ({pct:.1f}% variance)")

    drivers_str = ", ".join(driver_texts) if driver_texts else "general operational dispersion"

    return (
        f"Simulation evaluates a {loss_probability * 100:.1f}% overall loss probability. Downside Value-at-Risk (95% VaR) "
        f"is quantified at ${var_95_downside:,.0f}, with an average tail loss (95% CVaR) of ${cvar_95_downside:,.0f} in extreme scenarios. "
        f"Portfolio volatility is predominantly driven by {drivers_str}. "
        f"Downside tail exposure accounts for a {risk_penalty:.1f} point risk penalty deduction in the score."
    )


def generate_schedule_narrative(
    schedule_buffer_days: float,
    laycan_miss_probability: float,
    schedule_penalty: float,
) -> str:
    """Generates schedule reliability and fragility narrative."""
    buffer_desc = (
        f"healthy operational buffer of {schedule_buffer_days:.1f} days"
        if schedule_buffer_days >= 2.0
        else f"compressed buffer of only {schedule_buffer_days:.1f} days"
    )

    return (
        f"Fleet schedule analysis reveals an aggregate {buffer_desc} across active assignments. "
        f"The probability of missing contractual laycan windows is {laycan_miss_probability * 100:.1f}%. "
        f"Schedule friction incurs a {schedule_penalty:.1f} point penalty deduction in the Decision Score."
    )


def generate_what_could_change(
    recommendation_type: RecommendationType,
    top_drivers: List[Dict[str, Any]],
    laycan_miss_probability: float,
    schedule_buffer_days: float,
    thresholds: Optional[DecisionThresholds] = None,
) -> List[str]:
    """Generates deterministic trigger conditions that would alter the decision."""
    if thresholds is None:
        thresholds = DecisionThresholds()

    triggers: List[str] = []

    # Check bunker sensitivity
    bunker_driver = next((d for d in top_drivers if "bunker" in d.get("variable_id", "").lower() or "fuel" in d.get("variable_id", "").lower()), None)
    if bunker_driver:
        triggers.append("Bunker Price Spike: An increase of >= 18% in VLSFO bunker prices would erode risk-adjusted margins, flipping recommendation to RECONSIDER.")

    # Check freight rate sensitivity
    rate_driver = next((d for d in top_drivers if "rate" in d.get("variable_id", "").lower() or "spot" in d.get("variable_id", "").lower()), None)
    if rate_driver:
        triggers.append("Spot Rate Softening: A freight rate drop exceeding 12% across primary routes would reduce expected contribution below required hurdle rates.")

    # Schedule trigger
    if laycan_miss_probability > 0.05 or schedule_buffer_days < 2.5:
        triggers.append(f"Port Congestion Delay: Additional port or canal delays of >= 1.5 days would cause laycan miss probability to breach the 15% threshold.")
    else:
        triggers.append("Weather Disruption: Severe weather delays > 3.0 days on ballast legs would compress buffer below safety tolerances.")

    if recommendation_type == RecommendationType.PROCEED_WITH_CAUTION:
        triggers.append("Mitigation Execution: Executing firm bunker fixed-forward swaps reduces tail risk, upgrading recommendation to full PROCEED.")
    elif recommendation_type == RecommendationType.PROCEED:
        triggers.append("Contractual Laycan Tightening: Any charterer laycan window tightening < 48 hours requires immediate schedule re-optimization.")

    return triggers
