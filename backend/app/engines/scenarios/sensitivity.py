"""
VesselOptima — Phase 8: One-Variable-at-a-Time (OVAT) Sensitivity & Break-Even Analysis Engine

Sweeps single operational or economic variables across controlled ranges,
invokes the Phase 7 MILP engine at each step, and detects switching thresholds
where fleet allocations flip or cargoes drop.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.engines.optimization.result import OptimizationResult
from app.engines.scenarios.config import ScenarioConfig, ScenarioType
from app.engines.scenarios.revalidation import ScenarioRevalidator
from app.engines.scenarios.transform import ScenarioTransformer

logger = logging.getLogger("vesseloptima.engines.scenarios.sensitivity")


@dataclass
class SensitivityPoint:
    parameter_value: float
    parameter_label: str
    objective_value: float
    total_revenue: float
    total_cost: float
    net_contribution: float
    avoided_idle_cost: float
    cargoes_served: int
    vessels_utilized: int
    selected_candidate_ids: List[str]
    cargo_assignments: Dict[int, int]  # cargo_id -> vessel_id
    jaccard_stability: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BreakEvenThreshold:
    entity_type: str  # "CARGO", "CANDIDATE", "VESSEL"
    entity_id: Any
    entity_name: str
    event_type: str   # "DROPPED_TO_UNSERVED", "ASSIGNMENT_FLIPPED", "NEWLY_SERVED"
    threshold_type: str  # "OBSERVED_THRESHOLD", "ESTIMATED_THRESHOLD", "NOT_DETERMINABLE"
    parameter_name: str
    threshold_value: Optional[float]
    lower_bound: Optional[float]
    upper_bound: Optional[float]
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SensitivityResult:
    parameter_name: str
    baseline_run_id: str
    baseline_value: float
    points: List[SensitivityPoint] = field(default_factory=list)
    break_even_thresholds: List[BreakEvenThreshold] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parameter_name": self.parameter_name,
            "baseline_run_id": self.baseline_run_id,
            "baseline_value": self.baseline_value,
            "points": [p.to_dict() for p in self.points],
            "break_even_thresholds": [t.to_dict() for t in self.break_even_thresholds],
            "summary": self.summary,
        }


class SensitivityEngine:
    """
    Executes systematic parameter sweeps and computes break-even switching points.
    Strictly re-solves via Phase 7 MILP with copy-on-scenario semantics.
    """

    @classmethod
    def execute_sweep(
        cls,
        parameter_name: str,
        sweep_values: List[float],
        baseline_candidates: List[Dict[str, Any]],
        baseline_result: OptimizationResult,
        solve_fn: Callable[[List[Dict[str, Any]], ScenarioConfig], OptimizationResult],
        base_config: Optional[ScenarioConfig] = None,
    ) -> SensitivityResult:
        """
        Sweeps parameter_name across sweep_values.
        solve_fn is a callable (candidates, config) -> OptimizationResult (delegating to Phase 7 MILP).
        """
        cfg = base_config or ScenarioConfig(
            scenario_id="SWEEP-BASE",
            name="Sensitivity Base",
            scenario_type=ScenarioType.CUSTOM,
        )

        base_sel_ids = set(a.candidate_id for a in baseline_result.selected_assignments)
        points: List[SensitivityPoint] = []

        # Sort sweep values ascending
        sorted_vals = sorted(sweep_values)

        for val in sorted_vals:
            # Build modified config for this point
            pt_cfg = ScenarioConfig(
                scenario_id=f"SWEEP-{parameter_name}-{val:.2f}",
                name=f"Sweep {parameter_name}={val:.2f}",
                description=f"Automated sensitivity point for {parameter_name}={val:.2f}",
                scenario_type=ScenarioType.CUSTOM,
                baseline_scenario=cfg.baseline_scenario,
                freight_multiplier=val if parameter_name == "freight_multiplier" else cfg.freight_multiplier,
                bunker_multiplier=val if parameter_name == "bunker_multiplier" else cfg.bunker_multiplier,
                idle_cost_multiplier=val if parameter_name == "idle_cost_multiplier" else cfg.idle_cost_multiplier,
                port_cost_multiplier=val if parameter_name == "port_cost_multiplier" else cfg.port_cost_multiplier,
                laycan_adjustment_days=val if parameter_name == "laycan_adjustment_days" else cfg.laycan_adjustment_days,
                excluded_vessel_ids=cfg.excluded_vessel_ids,
                vessel_delay_days=cfg.vessel_delay_days,
                alpha_idle_weight=cfg.alpha_idle_weight,
                beta_ballast_penalty=cfg.beta_ballast_penalty,
                default_unserved_penalty=cfg.default_unserved_penalty,
            )

            # Copy-on-scenario transformation & revalidation
            transformed_cands, _, _ = ScenarioTransformer.transform_candidates(baseline_candidates, pt_cfg)
            revalidated_cands = ScenarioRevalidator.revalidate_candidates(transformed_cands, pt_cfg)

            # Re-solve through Phase 7 MILP
            res = solve_fn(revalidated_cands, pt_cfg)

            # Record point metrics
            sel_ids = [a.candidate_id for a in res.selected_assignments]
            sel_id_set = set(sel_ids)

            union_size = len(base_sel_ids | sel_id_set)
            inter_size = len(base_sel_ids & sel_id_set)
            jaccard = round(inter_size / union_size, 4) if union_size > 0 else 1.0

            cargo_map: Dict[int, int] = {}
            for a in res.selected_assignments:
                if a.cargo_id is not None:
                    cargo_map[a.cargo_id] = a.vessel_id

            vessels_used = len(set(a.vessel_id for a in res.selected_assignments))
            decomp = res.decomposition

            pct_diff = round((val - 1.0) * 100.0, 1)
            lbl = f"{'+' if pct_diff > 0 else ''}{pct_diff:.0f}%" if parameter_name.endswith("_multiplier") else f"{val:.1f}"

            points.append(
                SensitivityPoint(
                    parameter_value=round(val, 4),
                    parameter_label=lbl,
                    objective_value=round(res.objective_value, 2),
                    total_revenue=round(getattr(decomp, "total_gross_revenue", getattr(decomp, "total_revenue", 0.0)), 2),
                    total_cost=round(getattr(decomp, "total_voyage_cost", getattr(decomp, "total_cost", 0.0)), 2),
                    net_contribution=round(getattr(decomp, "total_net_contribution", getattr(decomp, "net_contribution", 0.0)), 2),
                    avoided_idle_cost=round(getattr(decomp, "total_avoided_idle_cost", getattr(decomp, "idle_cost_avoided", 0.0)), 2),
                    cargoes_served=len(cargo_map),
                    vessels_utilized=vessels_used,
                    selected_candidate_ids=sel_ids,
                    cargo_assignments=cargo_map,
                    jaccard_stability=jaccard,
                )
            )


        # Detect Break-Even Switching Thresholds
        thresholds = cls._detect_break_even_points(points, parameter_name, baseline_result)

        summary = (
            f"Evaluated {len(points)} sensitivity points for '{parameter_name}' across range "
            f"[{sorted_vals[0]:.2f}, {sorted_vals[-1]:.2f}]. Detected {len(thresholds)} structural allocation thresholds."
        )

        return SensitivityResult(
            parameter_name=parameter_name,
            baseline_run_id=baseline_result.run_id,
            baseline_value=1.0 if parameter_name.endswith("_multiplier") else 0.0,
            points=points,
            break_even_thresholds=thresholds,
            summary=summary,
        )

    @classmethod
    def _detect_break_even_points(
        cls,
        points: List[SensitivityPoint],
        param_name: str,
        baseline_result: OptimizationResult,
    ) -> List[BreakEvenThreshold]:
        """
        Identifies parameter boundaries where cargo allocations change, drop, or flip.
        """
        thresholds: List[BreakEvenThreshold] = []
        if len(points) < 2:
            return thresholds

        # Baseline cargo mapping
        base_cargo_map: Dict[int, Tuple[int, str, str]] = {}
        for a in baseline_result.selected_assignments:
            if a.cargo_id is not None:
                base_cargo_map[a.cargo_id] = (a.vessel_id, a.vessel_name, a.cargo_name)

        # Check consecutive points for changes
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]

            # 1. Cargo drop / flip checks
            for cid, (b_vid, b_vname, cname) in base_cargo_map.items():
                v1 = p1.cargo_assignments.get(cid)
                v2 = p2.cargo_assignments.get(cid)

                if v1 is not None and v2 is None:
                    # Dropped between p1 and p2
                    est_thresh = round((p1.parameter_value + p2.parameter_value) / 2.0, 3)
                    thresholds.append(
                        BreakEvenThreshold(
                            entity_type="CARGO",
                            entity_id=cid,
                            entity_name=cname,
                            event_type="DROPPED_TO_UNSERVED",
                            threshold_type="OBSERVED_THRESHOLD",
                            parameter_name=param_name,
                            threshold_value=est_thresh,
                            lower_bound=p1.parameter_value,
                            upper_bound=p2.parameter_value,
                            explanation=(
                                f"{cname} ceases to be economically viable and drops to unserved between "
                                f"{p1.parameter_value} and {p2.parameter_value} (observed threshold ~{est_thresh})."
                            ),
                        )
                    )
                elif v1 is not None and v2 is not None and v1 != v2:
                    # Swapped vessel
                    est_thresh = round((p1.parameter_value + p2.parameter_value) / 2.0, 3)
                    thresholds.append(
                        BreakEvenThreshold(
                            entity_type="CARGO",
                            entity_id=cid,
                            entity_name=cname,
                            event_type="ASSIGNMENT_FLIPPED",
                            threshold_type="OBSERVED_THRESHOLD",
                            parameter_name=param_name,
                            threshold_value=est_thresh,
                            lower_bound=p1.parameter_value,
                            upper_bound=p2.parameter_value,
                            explanation=(
                                f"Optimal carrier for {cname} switches from Vessel {v1} to Vessel {v2} "
                                f"between {p1.parameter_value} and {p2.parameter_value} (observed threshold ~{est_thresh})."
                            ),
                        )
                    )

        return thresholds
