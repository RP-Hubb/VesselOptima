"""
VesselOptima — Phase 8: Master Scenario Service

Coordinates scenario experimentation, baseline comparisons, parameter sweeps,
and robustness evaluations. Preserves strict boundaries:
- Single Source of Truth for Allocation: Delegates all optimization to Phase 7 HiGHS MILP.
- Baseline Immutability: Strictly enforces copy-on-scenario semantics and SHA-256 integrity.
- Zero External Connectivity: 100% offline air-gap execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.engines.employment.service import DEFAULT_AS_OF_DATE
from app.engines.optimization.result import OptimizationResult
from app.engines.optimization.service import OptimizationService
from app.engines.scenarios.comparison import AssignmentDifferenceEngine, ScenarioComparisonResult
from app.engines.scenarios.config import ScenarioConfig, ScenarioPresets, ScenarioType
from app.engines.scenarios.revalidation import ScenarioRevalidator
from app.engines.scenarios.robustness import RobustnessEngine, RobustnessEvaluationResult
from app.engines.scenarios.sensitivity import SensitivityEngine, SensitivityResult
from app.engines.scenarios.transform import ScenarioTransformer, hash_candidate_set
from app.models.domain import (
    OptimizationRun,
    RuntimeModeEnum,
    ScenarioEvaluation,
    ScenarioSensitivityRun,
)

logger = logging.getLogger("vesseloptima.engines.scenarios.service")


class ScenarioService:
    """
    Master service for Phase 8 Scenario Analysis & What-If Engine.
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self.opt_service = OptimizationService(db=db)

    def _get_baseline(
        self,
        baseline_scenario: str = "DEMO_FLEET",
        as_of_date: Optional[datetime] = None,
        custom_candidates: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[OptimizationResult, List[Dict[str, Any]]]:
        """
        Retrieves or computes the baseline optimization solution and baseline candidates.
        """
        eval_date = as_of_date or DEFAULT_AS_OF_DATE

        if custom_candidates is not None:
            cands = custom_candidates
        else:
            cands = self.opt_service._get_scenario_candidates(baseline_scenario, eval_date)

        # Solve baseline via Phase 7 MILP
        baseline_res = self.opt_service.solve_fleet_assignment(
            scenario=baseline_scenario,
            as_of_date=eval_date,
            persist=False,
            custom_candidates=cands,
        )
        return baseline_res, cands

    def run_scenario(
        self,
        config: ScenarioConfig,
        baseline_candidates: Optional[List[Dict[str, Any]]] = None,
        baseline_result: Optional[OptimizationResult] = None,
        as_of_date: Optional[datetime] = None,
        persist: bool = True,
    ) -> ScenarioComparisonResult:
        """
        Executes a single scenario:
        1. Establishes baseline and records SHA-256 fingerprint.
        2. Applies copy-on-scenario transformations.
        3. Revalidates operational feasibility.
        4. Re-solves through Phase 7 HiGHS MILP.
        5. Asserts zero mutation of baseline data.
        6. Computes granular deltas and difference classifications.
        7. Persists evaluation record if requested.
        """
        eval_date = as_of_date or DEFAULT_AS_OF_DATE

        # 1. Establish baseline
        if baseline_candidates is None or baseline_result is None:
            b_res, b_cands = self._get_baseline(
                baseline_scenario=config.baseline_scenario,
                as_of_date=eval_date,
                custom_candidates=baseline_candidates,
            )
            base_result = baseline_result or b_res
            base_candidates = baseline_candidates or b_cands
        else:
            base_result = baseline_result
            base_candidates = baseline_candidates

        # 2. Record baseline candidate hash before any operation
        hash_before = hash_candidate_set(base_candidates)

        # 3. Apply Copy-on-Scenario transformation
        transformed_cands, _, _ = ScenarioTransformer.transform_candidates(base_candidates, config)

        # 4. Revalidate operational & temporal boundaries
        revalidated_cands = ScenarioRevalidator.revalidate_candidates(transformed_cands, config)

        # 5. Re-solve via Phase 7 HiGHS MILP
        scenario_run_id = f"RUN-{config.scenario_id}-{datetime.now(timezone.utc).strftime('%H%M%S%f')[:10]}"
        scen_result = self.opt_service.solve_fleet_assignment(
            scenario=config.baseline_scenario,
            as_of_date=eval_date,
            alpha_idle_weight=config.alpha_idle_weight,
            beta_ballast_penalty=config.beta_ballast_penalty,
            default_unserved_penalty=config.default_unserved_penalty,
            persist=persist,
            custom_candidates=revalidated_cands,
        )
        # Override run_id for scenario identification
        scen_result.run_id = scenario_run_id

        # 6. Strict Baseline Immutability Assertion
        hash_after = hash_candidate_set(base_candidates)
        if hash_before != hash_after:
            raise AssertionError(
                f"FATAL: Baseline candidates were mutated during scenario '{config.scenario_id}' execution! "
                f"Before: {hash_before}, After: {hash_after}"
            )

        # 7. Compute Assignment Differences & KPIs
        comparison = AssignmentDifferenceEngine.compare(
            baseline_result=base_result,
            scenario_result=scen_result,
            scenario_id=config.scenario_id,
            scenario_name=config.name,
        )

        # 8. Persist to Database if requested
        if persist and self.db:
            try:
                eval_rec = ScenarioEvaluation(
                    scenario_code=config.scenario_id,
                    name=config.name,
                    description=config.description,
                    scenario_type=config.scenario_type.value if isinstance(config.scenario_type, ScenarioType) else str(config.scenario_type),
                    baseline_run_id=base_result.run_id,
                    scenario_run_id=scen_result.run_id,
                    parameters=config.to_dict(),
                    config_hash=config.get_config_hash(),
                    comparison_metrics={
                        "objective_value_delta": comparison.objective_value_delta,
                        "objective_value_pct_change": comparison.objective_value_pct_change,
                        "revenue_delta": comparison.total_revenue_delta,
                        "cost_delta": comparison.total_cost_delta,
                        "net_contribution_delta": comparison.net_contribution_delta,
                        "idle_cost_delta": comparison.idle_cost_avoided_delta,
                        "cargoes_served_delta": comparison.cargoes_served_delta,
                        "vessels_utilized_delta": comparison.vessels_utilized_delta,
                        "unchanged_assignments_count": comparison.unchanged_assignments_count,
                        "added_assignments_count": comparison.added_assignments_count,
                        "dropped_assignments_count": comparison.dropped_assignments_count,
                        "jaccard_similarity": comparison.jaccard_similarity,
                        "stability_score_pct": comparison.stability_score_pct,
                    },
                    assignment_deltas=[c.to_dict() for c in comparison.candidate_deltas],
                    cargo_deltas=[c.to_dict() for c in comparison.cargo_deltas],
                    runtime_mode=RuntimeModeEnum.OFFLINE_DEMO,
                    audit_trail={
                        "baseline_hash": hash_before,
                        "config_hash": config.get_config_hash(),
                        "solver_status": scen_result.status.value,
                        "executed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                self.db.add(eval_rec)
                self.db.commit()
            except Exception as ex:
                logger.error("Failed to persist ScenarioEvaluation to database: %s", ex)
                if self.db:
                    self.db.rollback()

        return comparison

    def run_batch_scenarios(
        self,
        configs: List[ScenarioConfig],
        baseline_candidates: Optional[List[Dict[str, Any]]] = None,
        as_of_date: Optional[datetime] = None,
        persist: bool = True,
    ) -> List[ScenarioComparisonResult]:
        """
        Executes a batch of scenarios from a single shared immutable baseline.
        """
        eval_date = as_of_date or DEFAULT_AS_OF_DATE
        base_scenario_name = configs[0].baseline_scenario if configs else "DEMO_FLEET"

        base_res, base_cands = self._get_baseline(
            baseline_scenario=base_scenario_name,
            as_of_date=eval_date,
            custom_candidates=baseline_candidates,
        )

        results: List[ScenarioComparisonResult] = []
        for cfg in configs:
            comp = self.run_scenario(
                config=cfg,
                baseline_candidates=base_cands,
                baseline_result=base_res,
                as_of_date=eval_date,
                persist=persist,
            )
            results.append(comp)

        return results

    def run_sensitivity_sweep(
        self,
        parameter_name: str,
        sweep_values: List[float],
        base_config: Optional[ScenarioConfig] = None,
        baseline_candidates: Optional[List[Dict[str, Any]]] = None,
        as_of_date: Optional[datetime] = None,
        persist: bool = True,
    ) -> SensitivityResult:
        """
        Executes a one-variable-at-a-time (OVAT) parameter sweep.
        """
        eval_date = as_of_date or DEFAULT_AS_OF_DATE
        cfg = base_config or ScenarioPresets.baseline()

        base_res, base_cands = self._get_baseline(
            baseline_scenario=cfg.baseline_scenario,
            as_of_date=eval_date,
            custom_candidates=baseline_candidates,
        )

        def solve_fn(cands: List[Dict[str, Any]], pt_cfg: ScenarioConfig) -> OptimizationResult:
            return self.opt_service.solve_fleet_assignment(
                scenario=pt_cfg.baseline_scenario,
                as_of_date=eval_date,
                alpha_idle_weight=pt_cfg.alpha_idle_weight,
                beta_ballast_penalty=pt_cfg.beta_ballast_penalty,
                default_unserved_penalty=pt_cfg.default_unserved_penalty,
                persist=False,
                custom_candidates=cands,
            )

        sweep_result = SensitivityEngine.execute_sweep(
            parameter_name=parameter_name,
            sweep_values=sweep_values,
            baseline_candidates=base_cands,
            baseline_result=base_res,
            solve_fn=solve_fn,
            base_config=cfg,
        )

        if persist and self.db:
            try:
                sweep_id = f"SWEEP-{parameter_name[:12]}-{datetime.now(timezone.utc).strftime('%H%M%S%f')[:10]}"
                rec = ScenarioSensitivityRun(
                    sweep_id=sweep_id,
                    parameter_name=parameter_name,
                    baseline_run_id=base_res.run_id,
                    parameter_range={"values": sweep_values, "min": min(sweep_values), "max": max(sweep_values)},
                    sweep_points=[p.to_dict() for p in sweep_result.points],
                    break_even_points=[t.to_dict() for t in sweep_result.break_even_thresholds],
                    robustness_scores=None,
                    runtime_mode=RuntimeModeEnum.OFFLINE_DEMO,
                    audit_trail={"executed_at": datetime.now(timezone.utc).isoformat()},
                )
                self.db.add(rec)
                self.db.commit()
            except Exception as ex:
                logger.error("Failed to persist ScenarioSensitivityRun: %s", ex)
                if self.db:
                    self.db.rollback()

        return sweep_result

    def evaluate_ensemble_robustness(
        self,
        ensemble_configs: Optional[List[ScenarioConfig]] = None,
        baseline_candidates: Optional[List[Dict[str, Any]]] = None,
        as_of_date: Optional[datetime] = None,
    ) -> RobustnessEvaluationResult:
        """
        Evaluates assignment stability across an ensemble of heterogeneous scenarios.
        """
        eval_date = as_of_date or DEFAULT_AS_OF_DATE
        configs = ensemble_configs or [
            ScenarioPresets.bunker_plus_25(),
            ScenarioPresets.bunker_plus_50(),
            ScenarioPresets.freight_minus_10(),
            ScenarioPresets.freight_minus_20(),
            ScenarioPresets.idle_plus_50(),
            ScenarioPresets.market_stress(),
            ScenarioPresets.tight_laycan(days=2.0),
        ]

        base_scenario_name = configs[0].baseline_scenario if configs else "DEMO_FLEET"
        base_res, base_cands = self._get_baseline(
            baseline_scenario=base_scenario_name,
            as_of_date=eval_date,
            custom_candidates=baseline_candidates,
        )

        scenario_results: List[Tuple[str, OptimizationResult]] = []
        for cfg in configs:
            trans_cands, _, _ = ScenarioTransformer.transform_candidates(base_cands, cfg)
            reval_cands = ScenarioRevalidator.revalidate_candidates(trans_cands, cfg)
            res = self.opt_service.solve_fleet_assignment(
                scenario=cfg.baseline_scenario,
                as_of_date=eval_date,
                alpha_idle_weight=cfg.alpha_idle_weight,
                beta_ballast_penalty=cfg.beta_ballast_penalty,
                default_unserved_penalty=cfg.default_unserved_penalty,
                persist=False,
                custom_candidates=reval_cands,
            )
            scenario_results.append((cfg.scenario_id, res))

        return RobustnessEngine.evaluate_ensemble(
            baseline_result=base_res,
            scenario_results=scenario_results,
        )
