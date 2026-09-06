"""
VesselOptima — Phase 8: Robustness Analysis Engine

Evaluates assignment stability across an ensemble of heterogeneous stress scenarios.
Calculates survival rates and classifies decisions into CORE_ROBUST,
CONDITIONALLY_STABLE, and FRAGILE tiers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import logging
from typing import Any, Dict, List, Optional

from app.engines.optimization.result import OptimizationResult

logger = logging.getLogger("vesseloptima.engines.scenarios.robustness")


class RobustnessTier(str, Enum):
    CORE_ROBUST = "CORE_ROBUST"                    # >= 80% survival rate
    CONDITIONALLY_STABLE = "CONDITIONALLY_STABLE"  # 50% - 79% survival rate
    FRAGILE = "FRAGILE"                            # < 50% survival rate


@dataclass
class AssignmentRobustnessScore:
    candidate_id: str
    vessel_id: int
    vessel_name: str
    cargo_id: Optional[int]
    cargo_name: str
    total_scenarios_evaluated: int
    scenarios_preserved: int
    robustness_score_pct: float
    robustness_tier: RobustnessTier
    scenarios_selected_in: List[str]
    scenarios_dropped_in: List[str]
    advisory_notes: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["robustness_tier"] = self.robustness_tier.value
        return d


@dataclass
class RobustnessEvaluationResult:
    total_scenarios: int
    scenario_ids: List[str]
    assignments: List[AssignmentRobustnessScore] = field(default_factory=list)
    overall_fleet_robustness_pct: float = 0.0
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_scenarios": self.total_scenarios,
            "scenario_ids": self.scenario_ids,
            "overall_fleet_robustness_pct": self.overall_fleet_robustness_pct,
            "assignments": [a.to_dict() for a in self.assignments],
            "summary": self.summary,
        }


class RobustnessEngine:
    """
    Computes empirical robustness scores for baseline assignments
    across an ensemble of scenario evaluations.
    """

    @classmethod
    def evaluate_ensemble(
        cls,
        baseline_result: OptimizationResult,
        scenario_results: List[Tuple[str, OptimizationResult]],  # (scenario_id, result)
    ) -> RobustnessEvaluationResult:
        """
        Evaluates stability of baseline assignments across scenario_results.
        """
        total_scenarios = len(scenario_results)
        if total_scenarios == 0:
            return RobustnessEvaluationResult(
                total_scenarios=0,
                scenario_ids=[],
                assignments=[],
                overall_fleet_robustness_pct=100.0,
                summary="No scenarios evaluated.",
            )

        scen_ids = [sid for sid, _ in scenario_results]

        # Pre-index scenario selected candidate IDs
        scenario_selections: Dict[str, set[str]] = {
            sid: set(a.candidate_id for a in res.selected_assignments)
            for sid, res in scenario_results
        }

        assignment_scores: List[AssignmentRobustnessScore] = []
        total_score_sum = 0.0

        for base_a in baseline_result.selected_assignments:
            cid = base_a.candidate_id
            preserved_in: List[str] = []
            dropped_in: List[str] = []

            for sid in scen_ids:
                if cid in scenario_selections[sid]:
                    preserved_in.append(sid)
                else:
                    dropped_in.append(sid)

            pres_count = len(preserved_in)
            score_pct = round((pres_count / total_scenarios) * 100.0, 1)
            total_score_sum += score_pct

            if score_pct >= 80.0:
                tier = RobustnessTier.CORE_ROBUST
                notes = "Highly resilient assignment; remains optimal across virtually all market and operational stress tests."
            elif score_pct >= 50.0:
                tier = RobustnessTier.CONDITIONALLY_STABLE
                notes = "Conditionally resilient; sensitive to severe fuel cost shocks or schedule contractions."
            else:
                tier = RobustnessTier.FRAGILE
                notes = "Fragile allocation; displaced under adverse freight margins or tighter operational boundaries."

            assignment_scores.append(
                AssignmentRobustnessScore(
                    candidate_id=cid,
                    vessel_id=base_a.vessel_id,
                    vessel_name=base_a.vessel_name,
                    cargo_id=base_a.cargo_id,
                    cargo_name=base_a.cargo_name,
                    total_scenarios_evaluated=total_scenarios,
                    scenarios_preserved=pres_count,
                    robustness_score_pct=score_pct,
                    robustness_tier=tier,
                    scenarios_selected_in=preserved_in,
                    scenarios_dropped_in=dropped_in,
                    advisory_notes=notes,
                )
            )

        base_count = len(baseline_result.selected_assignments)
        overall_pct = round(total_score_sum / max(base_count, 1), 1)

        summary = (
            f"Assessed {base_count} baseline assignments across {total_scenarios} stress scenarios. "
            f"Fleet average robustness score is {overall_pct}%. "
            f"{sum(1 for a in assignment_scores if a.robustness_tier == RobustnessTier.CORE_ROBUST)}/{base_count} "
            f"assignments classified as CORE ROBUST."
        )

        return RobustnessEvaluationResult(
            total_scenarios=total_scenarios,
            scenario_ids=scen_ids,
            assignments=assignment_scores,
            overall_fleet_robustness_pct=overall_pct,
            summary=summary,
        )
