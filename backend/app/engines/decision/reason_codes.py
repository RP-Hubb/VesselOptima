"""
VesselOptima — Phase 10 Decision Intelligence Engine
Reason Codes and Classification Enums

Authoritative enums for recommendation statuses, confidence tiers, action
priorities, and deterministic reason codes.
"""

from enum import Enum


class RecommendationType(str, Enum):
    """Classification of plan-level or assignment-level recommendation."""
    PROCEED = "PROCEED"
    PROCEED_WITH_CAUTION = "PROCEED_WITH_CAUTION"
    MONITOR = "MONITOR"
    RECONSIDER = "RECONSIDER"
    REJECT = "REJECT"
    NO_ACTION = "NO_ACTION"


class DecisionConfidence(str, Enum):
    """Confidence level in the decision recommendation based on evidence completeness."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ActionPriority(str, Enum):
    """Priority ranking for recommended manager actions and monitoring tasks."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ActionStatus(str, Enum):
    """Execution status of a recommended action."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DISMISSED = "DISMISSED"


class RecommendationScope(str, Enum):
    """Target scope of the recommendation."""
    PLAN = "PLAN"
    ASSIGNMENT = "ASSIGNMENT"


class DriverSeverity(str, Enum):
    """Severity classification of risk drivers contributing to recommendation."""
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    TERTIARY = "TERTIARY"


class DecisionReasonCode(str, Enum):
    """Deterministic, auditable reason codes explaining recommendations."""
    # Positive / Proceed drivers
    RC_SUPERIOR_ECONOMICS = "RC_SUPERIOR_ECONOMICS"
    RC_ROBUST_UNDER_STRESS = "RC_ROBUST_UNDER_STRESS"
    RC_NEGLIGIBLE_TAIL_RISK = "RC_NEGLIGIBLE_TAIL_RISK"
    RC_HIGH_SCHEDULE_BUFFER = "RC_HIGH_SCHEDULE_BUFFER"
    RC_CORE_ROBUST_STABILITY = "RC_CORE_ROBUST_STABILITY"

    # Cautionary / Risk drivers
    RC_TAIL_LOSS_EXPOSURE = "RC_TAIL_LOSS_EXPOSURE"
    RC_SCHEDULE_FRAGILITY = "RC_SCHEDULE_FRAGILITY"
    RC_SENSITIVE_BUNKER_SHOCK = "RC_SENSITIVE_BUNKER_SHOCK"
    RC_SENSITIVE_RATE_COLLAPSE = "RC_SENSITIVE_RATE_COLLAPSE"
    RC_LAYCAN_MISS_RISK = "RC_LAYCAN_MISS_RISK"
    RC_STRATEGY_FLIP_WARNING = "RC_STRATEGY_FLIP_WARNING"
    RC_MODERATE_VOLATILITY = "RC_MODERATE_VOLATILITY"

    # Reconsider / Reject drivers
    RC_INSUFFICIENT_ECONOMIC_RETURN = "RC_INSUFFICIENT_ECONOMIC_RETURN"
    RC_NEGATIVE_EXPECTED_CONTRIBUTION = "RC_NEGATIVE_EXPECTED_CONTRIBUTION"
    RC_EXTREME_TAIL_RISK = "RC_EXTREME_TAIL_RISK"
    RC_HIGH_LOSS_PROBABILITY = "RC_HIGH_LOSS_PROBABILITY"
    RC_DATA_GAP_UNCERTAINTY = "RC_DATA_GAP_UNCERTAINTY"
    RC_INFEASIBLE_ASSIGNMENT = "RC_INFEASIBLE_ASSIGNMENT"
    RC_NO_COMMERCIALLY_VIABLE_EMPLOYMENT = "RC_NO_COMMERCIALLY_VIABLE_EMPLOYMENT"
