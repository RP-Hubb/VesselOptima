"""
VesselOptima — Phase 10 Decision Intelligence Engine
Internal Domain Dataclasses and Configuration Models

Defines deterministic threshold configurations, evidence snapshots, score breakdowns,
and structured recommendation representations.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.engines.decision.reason_codes import (
    ActionPriority,
    DecisionConfidence,
    DecisionReasonCode,
    DriverSeverity,
    RecommendationType,
)


@dataclass
class DecisionWeights:
    """Configurable weights for Decision Score formulation (sum to 1.0)."""
    economic: float = 0.35
    reliability: float = 0.25
    robustness: float = 0.20
    risk_penalty: float = 0.10
    schedule_penalty: float = 0.10


@dataclass
class DecisionThresholds:
    """
    Configurable deterministic decision thresholds for recommendation gating.
    All thresholds are versioned, documented, and fully auditable.
    """
    # Loss probability thresholds
    max_loss_prob_proceed: float = 0.05
    max_loss_prob_caution: float = 0.15
    max_loss_prob_reconsider: float = 0.35

    # Tail risk thresholds (as ratio of CVaR95 downside to expected contribution)
    max_cvar95_downside_ratio_proceed: float = 0.20
    max_cvar95_downside_ratio_caution: float = 0.50

    # Schedule buffer and laycan miss thresholds
    min_schedule_buffer_days: float = 2.0
    max_laycan_miss_prob_proceed: float = 0.05
    max_laycan_miss_prob_caution: float = 0.15

    # Plan reliability and composite score thresholds
    min_reliability_proceed: float = 80.0
    min_reliability_caution: float = 60.0
    min_score_proceed: float = 75.0
    min_score_caution: float = 50.0

    # Risk-adjusted contribution lambda weight
    risk_aversion_lambda: float = 0.50

    # Weights
    weights: DecisionWeights = field(default_factory=DecisionWeights)


@dataclass
class DecisionScoreBreakdown:
    """Itemized breakdown of the 0–100 composite decision score."""
    economic_component: float  # [0, 35] default
    reliability_component: float  # [0, 25] default
    robustness_component: float  # [0, 20] default
    risk_penalty: float  # [0, 10] default deduction
    schedule_penalty: float  # [0, 10] default deduction
    composite_score: float  # [0, 100] net


@dataclass
class DecisionDriverItem:
    """Key uncertainty driver ranked by impact on recommendation."""
    variable_id: str
    variable_name: str
    category: str
    uncertainty_pct: float
    impact_description: str
    severity: DriverSeverity


@dataclass
class DecisionActionItem:
    """Prioritized operational action, monitoring trigger, or contingency."""
    action_id: str
    priority: ActionPriority
    title: str
    description: str
    affected_variable: Optional[str] = None
    affected_assignment_id: Optional[str] = None
    trigger_condition: Optional[str] = None
    recommended_action: str = ""


@dataclass
class AssignmentDecisionItem:
    """Assignment-level recommendation and metrics."""
    candidate_id: str
    vessel_id: int
    vessel_name: str
    cargo_id: Optional[int]
    cargo_name: Optional[str]
    recommendation_type: RecommendationType
    primary_reason_code: DecisionReasonCode
    reason_codes: List[DecisionReasonCode]
    title: str
    summary: str
    action_advice: str
    expected_contribution: float
    contribution_std: float
    loss_probability: float
    cvar95: float
    schedule_buffer_days: float
    laycan_miss_prob: float
    economic_survival_prob: float
    schedule_survival_prob: float
    risk_tier: str
    thresholds_used: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionEvidenceSnapshot:
    """Stored snapshot of all upstream inputs used to derive decisions."""
    optimization_objective: float
    expected_contribution: float
    baseline_contribution: Optional[float]
    risk_adjusted_contribution: float
    loss_probability: float
    cvar_95: float
    var_95_downside: float
    assignment_survival: float
    plan_reliability: float
    laycan_miss_probability: float
    scenario_survival_rate: float
    robustness_tier: str
    top_risk_drivers: List[Dict[str, Any]]
    critical_warnings: List[str]
    evidence_payload: Dict[str, Any]


@dataclass
class DecisionTradeoffItem:
    """Pairwise trade-off analysis comparing plans."""
    comparison_plan_id: str
    comparison_plan_name: str
    baseline_plan_name: str
    contribution_delta: float
    loss_prob_delta: float
    cvar_delta: float
    reliability_delta: float
    tradeoff_summary: str
    tradeoff_details: Dict[str, Any] = field(default_factory=dict)
