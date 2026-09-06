"""
VesselOptima — Phase 10 Decision Intelligence Engine
Action Priority and Operational Contingency Generator

Deterministically derives prioritized operational actions, monitoring triggers,
and risk mitigations for fleet managers based on identified vulnerabilities.
"""

from typing import Any, Dict, List, Optional
from app.engines.decision.models import DecisionActionItem
from app.engines.decision.reason_codes import ActionPriority, RecommendationType


def generate_prioritized_actions(
    recommendation_type: RecommendationType,
    top_drivers: List[Dict[str, Any]],
    assignment_items: List[Dict[str, Any]],
    laycan_miss_probability: float,
    schedule_buffer_days: float,
    strategy_flip_identified: bool = False,
) -> List[DecisionActionItem]:
    """
    Deterministically builds prioritized operational action items.
    """
    actions: List[DecisionActionItem] = []
    action_counter = 1

    # 1. Strategy Flip or Elevated Tail Risk Mitigation
    if strategy_flip_identified or recommendation_type == RecommendationType.PROCEED_WITH_CAUTION:
        actions.append(
            DecisionActionItem(
                action_id=f"ACT-{action_counter:03d}",
                priority=ActionPriority.CRITICAL if strategy_flip_identified else ActionPriority.HIGH,
                title="Bunker Price Hedging / Forward Procurement",
                description="Fix bunker procurement costs for upcoming ballast legs to neutralize tail volatility.",
                affected_variable="bunker_price_vlsfo",
                trigger_condition="VLSFO spot price increases by >= 5% or volatility spikes > 15%",
                recommended_action="Execute forward fuel contract or lock bunker price at load port bunker terminal.",
            )
        )
        action_counter += 1

    # 2. Schedule and Laycan Miss Protection
    fragile_assignments = [
        a for a in assignment_items
        if a.get("laycan_miss_prob", 0.0) > 0.05 or a.get("schedule_buffer_days", 99.0) < 2.0
    ]

    for fa in fragile_assignments:
        cand_id = fa.get("candidate_id", "Unknown")
        vessel_name = fa.get("vessel_name", "Vessel")
        buffer_days = fa.get("schedule_buffer_days", 0.0)
        miss_prob = fa.get("laycan_miss_prob", 0.0)

        actions.append(
            DecisionActionItem(
                action_id=f"ACT-{action_counter:03d}",
                priority=ActionPriority.HIGH if miss_prob > 0.10 else ActionPriority.MEDIUM,
                title=f"Speed & Laycan Monitoring for {vessel_name}",
                description=f"Buffer is compressed to {buffer_days:.1f} days with {miss_prob * 100:.1f}% laycan breach probability.",
                affected_variable="port_waiting_time",
                affected_assignment_id=cand_id,
                trigger_condition=f"Port turnaround or weather delay exceeds 12 hours on {vessel_name}",
                recommended_action="Instruct master to increase speed from eco-speed to normal cruising (13.5 kts) to preserve laycan window.",
            )
        )
        action_counter += 1

    # 3. Rate Sensitivity & Market Protection
    rate_driver = next((d for d in top_drivers if "rate" in d.get("variable_id", "").lower()), None)
    if rate_driver and rate_driver.get("uncertainty_contribution_pct", 0.0) > 20.0:
        actions.append(
            DecisionActionItem(
                action_id=f"ACT-{action_counter:03d}",
                priority=ActionPriority.HIGH,
                title="Freight Rate Confirmation & Fixture Finalization",
                description="Market freight volatility contributes significantly to earnings dispersion.",
                affected_variable=rate_driver.get("variable_id", "market_rate"),
                trigger_condition="Spot index fluctuates by >= 8% prior to charter party signing",
                recommended_action="Expedite clean recap fixture with charterer to lock agreed freight rates.",
            )
        )
        action_counter += 1

    # 4. Standard Monitoring if stable
    if not actions:
        actions.append(
            DecisionActionItem(
                action_id=f"ACT-{action_counter:03d}",
                priority=ActionPriority.LOW,
                title="Standard Voyage Performance Monitoring",
                description="Routine tracking of noon reports and automated tracking against benchmark itinerary.",
                affected_variable="voyage_execution",
                trigger_condition="Deviation > 24 hours from baseline schedule",
                recommended_action="Maintain standard daily operational oversight; no immediate intervention required.",
            )
        )

    return actions
