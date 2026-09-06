"""
VesselOptima — Phase 10 Decision Intelligence Engine
Public Package Interface
"""

from app.engines.decision.confidence import (
    calculate_decision_stability,
    evaluate_decision_confidence,
)
from app.engines.decision.explanations import (
    generate_executive_summary,
    generate_financial_narrative,
    generate_risk_narrative,
    generate_schedule_narrative,
    generate_what_could_change,
)
from app.engines.decision.models import (
    AssignmentDecisionItem,
    DecisionActionItem,
    DecisionDriverItem,
    DecisionEvidenceSnapshot,
    DecisionScoreBreakdown,
    DecisionThresholds,
    DecisionTradeoffItem,
    DecisionWeights,
)
from app.engines.decision.priorities import generate_prioritized_actions
from app.engines.decision.reason_codes import (
    ActionPriority,
    ActionStatus,
    DecisionConfidence,
    DecisionReasonCode,
    DriverSeverity,
    RecommendationScope,
    RecommendationType,
)
from app.engines.decision.result import DecisionResult
from app.engines.decision.rules import (
    evaluate_assignment_recommendation,
    evaluate_plan_recommendation,
)
from app.engines.decision.scoring import (
    calculate_decision_score,
    calculate_risk_adjusted_contribution,
)
from app.engines.decision.service import DecisionService
from app.engines.decision.tradeoffs import evaluate_plan_tradeoffs

__all__ = [
    "DecisionService",
    "DecisionResult",
    "DecisionThresholds",
    "DecisionWeights",
    "DecisionScoreBreakdown",
    "DecisionEvidenceSnapshot",
    "DecisionActionItem",
    "DecisionTradeoffItem",
    "AssignmentDecisionItem",
    "DecisionDriverItem",
    "RecommendationType",
    "DecisionConfidence",
    "ActionPriority",
    "ActionStatus",
    "RecommendationScope",
    "DriverSeverity",
    "DecisionReasonCode",
    "calculate_decision_score",
    "calculate_risk_adjusted_contribution",
    "evaluate_decision_confidence",
    "calculate_decision_stability",
    "evaluate_plan_recommendation",
    "evaluate_assignment_recommendation",
    "generate_executive_summary",
    "generate_financial_narrative",
    "generate_risk_narrative",
    "generate_schedule_narrative",
    "generate_what_could_change",
    "generate_prioritized_actions",
    "evaluate_plan_tradeoffs",
]
