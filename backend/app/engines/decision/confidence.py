"""
VesselOptima — Phase 10 Decision Intelligence Engine
Decision Confidence and Stability Evaluator

Deterministically assesses confidence tier (HIGH, MEDIUM, LOW) and decision stability
based on upstream evidence completeness, simulation depth, and scenario robustness.
"""

from typing import List, Optional
from app.engines.decision.reason_codes import DecisionConfidence


def evaluate_decision_confidence(
    has_optimization: bool,
    has_scenarios: bool,
    has_risk_simulation: bool,
    simulation_count: int,
    decision_stability: float,
    critical_warnings: Optional[List[str]] = None,
) -> DecisionConfidence:
    """
    Deterministically determines recommendation confidence based on evidence completeness.

    Criteria:
    - HIGH:
      - Has verified MILP optimization
      - Has scenario stress tests
      - Has Monte Carlo risk simulation with >= 1,000 samples
      - Decision stability >= 0.80
      - No critical data gaps
    - MEDIUM:
      - Has optimization and risk simulation
      - Stability between 0.50 and 0.80 OR missing scenario sensitivity run
      - Minor data gaps
    - LOW:
      - Missing risk simulation OR
      - Stability < 0.50 OR
      - Critical data gap or unverified inputs
    """
    if critical_warnings is None:
        critical_warnings = []

    # If missing fundamental optimization or critical data gap present
    if not has_optimization or any("DATA_GAP" in w or "UNVERIFIED" in w for w in critical_warnings):
        return DecisionConfidence.LOW

    # If missing risk simulation or extreme instability
    if not has_risk_simulation or decision_stability < 0.50:
        return DecisionConfidence.LOW

    # Check for High confidence prerequisites
    if (
        has_scenarios
        and has_risk_simulation
        and simulation_count >= 1000
        and decision_stability >= 0.80
        and len(critical_warnings) == 0
    ):
        return DecisionConfidence.HIGH

    return DecisionConfidence.MEDIUM


def calculate_decision_stability(
    baseline_recommendation: str,
    scenario_recommendations: List[str],
) -> float:
    """
    Calculates decision stability as the proportion of evaluated scenario variations
    where the baseline recommendation holds. Returns float in [0.0, 1.0].
    """
    if not scenario_recommendations:
        return 1.0

    matching = sum(1 for r in scenario_recommendations if r == baseline_recommendation)
    stability = matching / len(scenario_recommendations)
    return round(stability, 2)
