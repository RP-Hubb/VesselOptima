"""
VesselOptima — Phase 10 Decision Intelligence Engine
Multi-Plan Trade-Off Analysis

Evaluates pairwise trade-offs across nominal contribution, risk-adjusted returns,
tail risk exposure (CVaR), loss probability, and plan reliability.
"""

from typing import Any, Dict, List, Optional
from app.engines.decision.models import DecisionTradeoffItem


def evaluate_plan_tradeoffs(
    baseline_name: str,
    baseline_contribution: float,
    baseline_loss_prob: float,
    baseline_cvar: float,
    baseline_reliability: float,
    comparison_plans: List[Dict[str, Any]],
) -> List[DecisionTradeoffItem]:
    """
    Computes comparative trade-off metrics between a baseline plan and alternative plans.
    """
    tradeoffs: List[DecisionTradeoffItem] = []

    for comp in comparison_plans:
        plan_id = comp.get("plan_id", "ALT-PLAN")
        plan_name = comp.get("plan_name", "Alternative Plan")
        comp_contrib = comp.get("expected_contribution", 0.0)
        comp_loss_prob = comp.get("loss_probability", 0.0)
        comp_cvar = comp.get("cvar_95", 0.0)
        comp_rel = comp.get("plan_reliability", 0.0)

        c_delta = round(comp_contrib - baseline_contribution, 2)
        lp_delta = round(comp_loss_prob - baseline_loss_prob, 4)
        cvar_delta = round(comp_cvar - baseline_cvar, 2)
        rel_delta = round(comp_rel - baseline_reliability, 2)

        # Build trade-off narrative
        contrib_phrase = (
            f"${abs(c_delta):,.0f} higher nominal return"
            if c_delta >= 0
            else f"${abs(c_delta):,.0f} lower nominal return"
        )
        tail_phrase = (
            f"increases tail risk by ${abs(cvar_delta):,.0f}"
            if cvar_delta >= 0
            else f"reduces tail risk by ${abs(cvar_delta):,.0f} (safer downside)"
        )
        lp_phrase = (
            f"{abs(lp_delta) * 100:.1f}% higher loss probability"
            if lp_delta >= 0
            else f"{abs(lp_delta) * 100:.1f}% lower loss probability"
        )

        summary = (
            f"{plan_name} offers {contrib_phrase} compared to {baseline_name}, but {tail_phrase} "
            f"and has {lp_phrase}. Reliability score changes by {rel_delta:+.1f} pts."
        )

        tradeoffs.append(
            DecisionTradeoffItem(
                comparison_plan_id=plan_id,
                comparison_plan_name=plan_name,
                baseline_plan_name=baseline_name,
                contribution_delta=c_delta,
                loss_prob_delta=lp_delta,
                cvar_delta=cvar_delta,
                reliability_delta=rel_delta,
                tradeoff_summary=summary,
                tradeoff_details={
                    "baseline_contribution": baseline_contribution,
                    "comparison_contribution": comp_contrib,
                    "baseline_loss_prob": baseline_loss_prob,
                    "comparison_loss_prob": comp_loss_prob,
                    "baseline_cvar": baseline_cvar,
                    "comparison_cvar": comp_cvar,
                    "baseline_reliability": baseline_reliability,
                    "comparison_reliability": comp_rel,
                },
            )
        )

    return tradeoffs
