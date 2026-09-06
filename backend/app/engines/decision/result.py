"""
VesselOptima — Phase 10 Decision Intelligence Engine
Result Dataclasses

Final structured decision output encompassing executive summaries, deterministic scores,
evidence snapshots, assignment breakdowns, action queues, and audit hashes.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.engines.decision.models import (
    AssignmentDecisionItem,
    DecisionActionItem,
    DecisionEvidenceSnapshot,
    DecisionScoreBreakdown,
    DecisionThresholds,
    DecisionTradeoffItem,
)
from app.engines.decision.reason_codes import (
    DecisionConfidence,
    DecisionReasonCode,
    RecommendationType,
)


@dataclass
class DecisionResult:
    """Complete, immutable output of a deterministic decision run."""
    run_id: str
    optimization_run_id: str
    scenario_run_id: Optional[str]
    risk_run_id: Optional[str]
    recommendation_type: RecommendationType
    primary_reason_code: DecisionReasonCode
    reason_codes: List[DecisionReasonCode]
    confidence: DecisionConfidence
    decision_score: float
    scoring_breakdown: DecisionScoreBreakdown
    decision_stability: float
    risk_adjusted_contribution: float
    executive_summary: str
    financial_narrative: str
    risk_narrative: str
    schedule_narrative: str
    what_could_change: List[str]
    assignment_recommendations: List[AssignmentDecisionItem]
    actions: List[DecisionActionItem]
    tradeoffs: List[DecisionTradeoffItem]
    evidence: DecisionEvidenceSnapshot
    input_hash: str
    output_hash: str
    execution_time_seconds: float
    thresholds_used: DecisionThresholds = field(default_factory=DecisionThresholds)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "run_id": self.run_id,
            "optimization_run_id": self.optimization_run_id,
            "scenario_run_id": self.scenario_run_id,
            "risk_run_id": self.risk_run_id,
            "recommendation_type": self.recommendation_type.value,
            "primary_reason_code": self.primary_reason_code.value,
            "reason_codes": [rc.value for rc in self.reason_codes],
            "confidence": self.confidence.value,
            "decision_score": self.decision_score,
            "scoring_breakdown": {
                "economic_component": self.scoring_breakdown.economic_component,
                "reliability_component": self.scoring_breakdown.reliability_component,
                "robustness_component": self.scoring_breakdown.robustness_component,
                "risk_penalty": self.scoring_breakdown.risk_penalty,
                "schedule_penalty": self.scoring_breakdown.schedule_penalty,
                "composite_score": self.scoring_breakdown.composite_score,
            },
            "decision_stability": self.decision_stability,
            "risk_adjusted_contribution": self.risk_adjusted_contribution,
            "executive_summary": self.executive_summary,
            "financial_narrative": self.financial_narrative,
            "risk_narrative": self.risk_narrative,
            "schedule_narrative": self.schedule_narrative,
            "what_could_change": self.what_could_change,
            "assignment_recommendations": [
                {
                    "candidate_id": a.candidate_id,
                    "vessel_id": a.vessel_id,
                    "vessel_name": a.vessel_name,
                    "cargo_id": a.cargo_id,
                    "cargo_name": a.cargo_name,
                    "recommendation_type": a.recommendation_type.value,
                    "primary_reason_code": a.primary_reason_code.value,
                    "reason_codes": [rc.value for rc in a.reason_codes],
                    "title": a.title,
                    "summary": a.summary,
                    "action_advice": a.action_advice,
                    "expected_contribution": a.expected_contribution,
                    "contribution_std": a.contribution_std,
                    "loss_probability": a.loss_probability,
                    "cvar95": a.cvar95,
                    "schedule_buffer_days": a.schedule_buffer_days,
                    "laycan_miss_prob": a.laycan_miss_prob,
                    "economic_survival_prob": a.economic_survival_prob,
                    "schedule_survival_prob": a.schedule_survival_prob,
                    "risk_tier": a.risk_tier,
                }
                for a in self.assignment_recommendations
            ],
            "actions": [
                {
                    "action_id": act.action_id,
                    "priority": act.priority.value,
                    "title": act.title,
                    "description": act.description,
                    "affected_variable": act.affected_variable,
                    "affected_assignment_id": act.affected_assignment_id,
                    "trigger_condition": act.trigger_condition,
                    "recommended_action": act.recommended_action,
                }
                for act in self.actions
            ],
            "tradeoffs": [
                {
                    "comparison_plan_id": t.comparison_plan_id,
                    "comparison_plan_name": t.comparison_plan_name,
                    "baseline_plan_name": t.baseline_plan_name,
                    "contribution_delta": t.contribution_delta,
                    "loss_prob_delta": t.loss_prob_delta,
                    "cvar_delta": t.cvar_delta,
                    "reliability_delta": t.reliability_delta,
                    "tradeoff_summary": t.tradeoff_summary,
                    "tradeoff_details": t.tradeoff_details,
                }
                for t in self.tradeoffs
            ],
            "evidence": {
                "optimization_objective": self.evidence.optimization_objective,
                "expected_contribution": self.evidence.expected_contribution,
                "baseline_contribution": self.evidence.baseline_contribution,
                "risk_adjusted_contribution": self.evidence.risk_adjusted_contribution,
                "loss_probability": self.evidence.loss_probability,
                "cvar_95": self.evidence.cvar_95,
                "var_95_downside": self.evidence.var_95_downside,
                "assignment_survival": self.evidence.assignment_survival,
                "plan_reliability": self.evidence.plan_reliability,
                "laycan_miss_probability": self.evidence.laycan_miss_probability,
                "scenario_survival_rate": self.evidence.scenario_survival_rate,
                "robustness_tier": self.evidence.robustness_tier,
                "top_risk_drivers": self.evidence.top_risk_drivers,
                "critical_warnings": self.evidence.critical_warnings,
            },
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "execution_time_seconds": self.execution_time_seconds,
        }
