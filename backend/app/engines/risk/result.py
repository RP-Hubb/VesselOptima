"""
VesselOptima — Phase 9: Risk Simulation Result Structures

Defines typed, immutable result data structures for portfolio risk metrics,
assignment-level schedule & economic risk, risk driver attribution, and plan comparisons.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from app.engines.risk.reason_codes import RiskTier


@dataclass
class AssignmentRiskResult:
    candidate_id: str
    vessel_id: int
    vessel_name: str
    cargo_id: Optional[int]
    cargo_name: str
    expected_revenue: float
    expected_cost: float
    expected_net_contribution: float
    contribution_std: float
    loss_probability: float
    var95_downside: float
    cvar95: float
    expected_arrival: str
    p50_arrival: str
    p90_arrival: str
    p95_arrival: str
    laycan_end: str
    schedule_buffer_days: float
    laycan_miss_probability: float
    economic_survival_probability: float
    schedule_survival_probability: float
    combined_survival_probability: float
    risk_tier: RiskTier

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["risk_tier"] = self.risk_tier.value
        return d


@dataclass
class RiskDriverResult:
    variable_id: str
    name: str
    category: str
    uncertainty_contribution_pct: float
    sensitivity_coefficient: float
    label: str = "CONTRIBUTION"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlanRiskSimulationResult:
    run_id: str
    optimization_run_id: str
    scenario_run_id: Optional[str]
    simulation_count: int
    random_seed: int

    # Financial Expectation & Dispersion
    expected_portfolio_contribution: float
    portfolio_contribution_std: float
    expected_portfolio_revenue: float
    expected_portfolio_cost: float

    # Percentiles
    percentiles: Dict[str, float]

    # Value at Risk & Downside Tail
    var90_level: float
    var95_level: float
    var90_downside: float
    var95_downside: float
    cvar90: float
    cvar95: float

    # Loss Probabilities
    loss_probability: float
    expected_loss: float

    # Plan Reliability & Classification
    plan_reliability_score: float
    risk_tier: RiskTier

    # Assignment & Driver Decompositions
    assignments: List[AssignmentRiskResult] = field(default_factory=list)
    drivers: List[RiskDriverResult] = field(default_factory=list)

    # Visualization Sample (binned or downsampled for chart display)
    distribution_histogram: List[Dict[str, Any]] = field(default_factory=list)
    provenance_audit: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["risk_tier"] = self.risk_tier.value
        d["assignments"] = [a.to_dict() for a in self.assignments]
        d["drivers"] = [dr.to_dict() for dr in self.drivers]
        return d


@dataclass
class PlanRiskComparisonResult:
    plan_a_id: str
    plan_a_name: str
    plan_b_id: str
    plan_b_name: str

    plan_a_expected_contribution: float
    plan_b_expected_contribution: float
    expected_contribution_delta: float

    plan_a_loss_probability: float
    plan_b_loss_probability: float

    plan_a_cvar95: float
    plan_b_cvar95: float

    plan_a_reliability_score: float
    plan_b_reliability_score: float

    trade_off_summary: str
    recommendation_notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
