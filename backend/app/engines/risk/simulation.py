"""
VesselOptima — Phase 9: Vectorized Monte Carlo Simulation Engine

Implements high-speed vectorized simulation of maritime voyages and fleet allocations:
- Vectorized NumPy execution across N = 1,000 to 100,000 draws in milliseconds
- Integrates continuous freight rate, bunker price, port congestion, and weather delay uncertainty
- Applies joint correlation structures via Gaussian Copula / Cholesky decomposition
- Evaluates voyage economics: revenue, bunker, port dues, weather delay penalties, and demurrage
- Produces comprehensive portfolio and assignment-level risk statistics
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import numpy as np

from app.engines.risk.metrics import RiskMetricsCalculator
from app.engines.risk.models import RiskSimulationConfig, RiskVariable
from app.engines.risk.reason_codes import ProvenanceType, RiskCategory, RiskReasonCode, RiskTier
from app.engines.risk.result import (
    AssignmentRiskResult,
    PlanRiskSimulationResult,
    RiskDriverResult,
)
from app.engines.risk.sampling import RiskSampler

logger = logging.getLogger(__name__)


class MonteCarloEngine:
    """Institutional high-performance Monte Carlo simulation engine."""

    def __init__(self, default_seed: int = 42) -> None:
        self.default_seed = default_seed

    def run_simulation(
        self,
        assignments: List[Dict[str, Any]],
        config: RiskSimulationConfig,
        optimization_run_id: str = "OPT-DEFAULT",
        scenario_run_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> PlanRiskSimulationResult:
        """
        Executes an end-to-end vectorized Monte Carlo risk simulation across a fleet allocation plan.
        """
        import uuid
        actual_run_id = run_id or f"RISK-{uuid.uuid4().hex[:8].upper()}"
        num_sims = max(100, min(100000, config.simulation_count))
        seed = config.random_seed if config.random_seed is not None else self.default_seed

        # 1. Coordinate joint sampling across all specified risk variables
        var_dict = {v.variable_id: v for v in config.variables}
        sampled_arrays = RiskSampler.sample_variables(
            variables=config.variables,
            correlations=config.correlations,
            n_samples=num_sims,
            seed=seed,
        )

        # 2. Variable metadata for variance decomposition & attribution
        var_meta = {
            v.variable_id: {
                "name": v.name,
                "category": v.category.value if hasattr(v.category, "value") else str(v.category),
            }
            for v in config.variables
        }

        # 3. Identify common operational variables
        bunker_var_id = self._find_matching_var(config.variables, [RiskCategory.BUNKER, "bunker"])
        freight_var_id = self._find_matching_var(config.variables, [RiskCategory.FREIGHT, "freight"])
        port_delay_var_id = self._find_matching_var(config.variables, [RiskCategory.PORT_DELAY, "port_delay", "congestion"])
        weather_delay_var_id = self._find_matching_var(config.variables, [RiskCategory.WEATHER_DELAY, "weather"])

        # 4. Prepare portfolio arrays
        portfolio_contributions = np.zeros(num_sims, dtype=np.float64)
        portfolio_revenues = np.zeros(num_sims, dtype=np.float64)
        portfolio_costs = np.zeros(num_sims, dtype=np.float64)

        assignment_results: List[AssignmentRiskResult] = []

        # 5. Simulate each assignment across all N draws simultaneously
        for asgn in assignments:
            candidate_id = str(asgn.get("candidate_id", f"CAND-{asgn.get('vessel_id', 0)}"))
            vessel_id = int(asgn.get("vessel_id", 0))
            vessel_name = str(asgn.get("vessel_name", f"Vessel-{vessel_id}"))
            cargo_id = asgn.get("cargo_id")
            cargo_name = str(asgn.get("cargo_name", f"Cargo-{cargo_id}" if cargo_id else "Reposition / Ballast"))

            base_rev = float(asgn.get("expected_revenue") or asgn.get("revenue") or 0.0)
            base_cost = float(asgn.get("voyage_cost") or asgn.get("total_cost") or asgn.get("cost") or 0.0)
            
            # Baseline cost breakdown
            base_bunker = float(asgn.get("bunker_cost") or (base_cost * 0.48))
            base_port = float(asgn.get("port_dues") or asgn.get("port_costs") or (base_cost * 0.22))
            base_other = max(0.0, base_cost - base_bunker - base_port)

            voyage_days = max(1.0, float(asgn.get("voyage_days") or 14.0))
            sea_days = max(0.5, float(asgn.get("sea_days") or (voyage_days * 0.70)))
            port_days = max(0.5, float(asgn.get("port_days") or (voyage_days * 0.30)))

            # Timestamps
            dep_val = asgn.get("start_time") or asgn.get("start_date")
            if isinstance(dep_val, str):
                dep_dt = datetime.fromisoformat(dep_val.replace("Z", ""))
            elif isinstance(dep_val, datetime):
                dep_dt = dep_val
            else:
                dep_dt = datetime(2026, 9, 10, 8, 0)

            laycan_val = asgn.get("end_time") or asgn.get("laycan_end")
            if isinstance(laycan_val, str):
                laycan_end_iso = laycan_val
            elif isinstance(laycan_val, datetime):
                laycan_end_iso = laycan_val.isoformat()
            else:
                laycan_end_iso = (dep_dt + timedelta(days=voyage_days + 3.0)).isoformat()

            # A. Vectorized Freight Multiplier
            if freight_var_id and freight_var_id in sampled_arrays:
                f_samples = sampled_arrays[freight_var_id]
                f_var = var_dict[freight_var_id]
                f_baseline = f_var.baseline_value or (np.mean(f_samples) if np.mean(f_samples) > 0 else 1.0)
                freight_mult = f_samples / f_baseline if f_baseline > 10.0 else f_samples
            else:
                freight_mult = np.ones(num_sims, dtype=np.float64)

            sim_rev = base_rev * freight_mult

            # B. Vectorized Bunker Multiplier
            if bunker_var_id and bunker_var_id in sampled_arrays:
                b_samples = sampled_arrays[bunker_var_id]
                b_var = var_dict[bunker_var_id]
                b_baseline = b_var.baseline_value or (np.mean(b_samples) if np.mean(b_samples) > 0 else 1.0)
                bunker_mult = b_samples / b_baseline if b_baseline > 10.0 else b_samples
            else:
                bunker_mult = np.ones(num_sims, dtype=np.float64)

            # C. Vectorized Delays
            port_delays = (
                sampled_arrays[port_delay_var_id]
                if (port_delay_var_id and port_delay_var_id in sampled_arrays)
                else np.zeros(num_sims, dtype=np.float64)
            )
            weather_delays = (
                sampled_arrays[weather_delay_var_id]
                if (weather_delay_var_id and weather_delay_var_id in sampled_arrays)
                else np.zeros(num_sims, dtype=np.float64)
            )
            total_delays = np.maximum(0.0, port_delays + weather_delays)

            # Extra fuel consumption during operational delays
            daily_sea_bunker = base_bunker / sea_days
            daily_port_bunker = daily_sea_bunker * 0.20
            delay_fuel_cost = (
                weather_delays * daily_sea_bunker + port_delays * daily_port_bunker
            ) * bunker_mult

            # Demurrage calculation
            if config.include_demurrage:
                # Standard laytime allowance: 2.0 days delay buffer
                excess_port_delay = np.maximum(0.0, port_delays - 2.0)
                demurrage_cost = excess_port_delay * config.demurrage_daily_rate
            else:
                demurrage_cost = np.zeros(num_sims, dtype=np.float64)

            sim_bunker_cost = (base_bunker * bunker_mult) + delay_fuel_cost
            sim_cost = sim_bunker_cost + base_port + base_other + demurrage_cost
            sim_contrib = sim_rev - sim_cost

            # Simulated arrival day offsets from departure
            sim_arrival_days = voyage_days + total_delays

            # Accumulate in portfolio
            portfolio_revenues += sim_rev
            portfolio_costs += sim_cost
            portfolio_contributions += sim_contrib

            # Compute assignment-level metrics
            asgn_metric = RiskMetricsCalculator.calculate_assignment_metrics(
                candidate_id=candidate_id,
                vessel_id=vessel_id,
                vessel_name=vessel_name,
                cargo_id=cargo_id,
                cargo_name=cargo_name,
                revenue_samples=sim_rev,
                cost_samples=sim_cost,
                contribution_samples=sim_contrib,
                arrival_date_samples=sim_arrival_days,
                laycan_end_iso=laycan_end_iso,
                departure_date=dep_dt,
            )
            assignment_results.append(asgn_metric)

        # 6. Portfolio Level Calculations
        exp_contrib = float(np.mean(portfolio_contributions))
        std_contrib = float(np.std(portfolio_contributions))
        exp_rev = float(np.mean(portfolio_revenues))
        exp_cost = float(np.mean(portfolio_costs))

        percentiles = RiskMetricsCalculator.calculate_percentiles(portfolio_contributions)
        var_cvar = RiskMetricsCalculator.calculate_var_cvar(
            portfolio_contributions, exp_contrib, config.confidence_levels
        )
        loss_prob, exp_loss = RiskMetricsCalculator.calculate_loss_metrics(portfolio_contributions)

        # Composite schedule reliability & plan reliability
        avg_sched_survival = (
            float(np.mean([a.schedule_survival_probability for a in assignment_results]))
            if assignment_results
            else 1.0
        )
        avg_laycan_miss = (
            float(np.mean([a.laycan_miss_probability for a in assignment_results]))
            if assignment_results
            else 0.0
        )

        reliability_score = RiskMetricsCalculator.calculate_reliability_score(
            loss_prob=loss_prob,
            schedule_survival_prob=avg_sched_survival,
            expected_contribution=exp_contrib,
            var95_downside=var_cvar["var95_downside"],
        )

        risk_tier = RiskMetricsCalculator.classify_risk_tier(
            loss_prob=loss_prob, laycan_miss_prob=avg_laycan_miss
        )

        # 7. Variance Decomposition / Drivers
        drivers = RiskMetricsCalculator.decompose_variance(
            variable_samples=sampled_arrays,
            portfolio_contributions=portfolio_contributions,
            variable_metadata=var_meta,
        )

        # 8. Histogram for UI
        histogram = RiskMetricsCalculator.compute_histogram(portfolio_contributions, bins=30)

        # 9. Audit trail & provenance
        provenance_audit = [
            {
                "variable_id": v.variable_id,
                "name": v.name,
                "distribution": v.distribution_type.value,
                "provenance": v.provenance.value if hasattr(v.provenance, "value") else str(v.provenance),
                "source_ref": v.source_ref,
                "baseline_value": v.baseline_value,
            }
            for v in config.variables
        ]

        return PlanRiskSimulationResult(
            run_id=actual_run_id,
            optimization_run_id=optimization_run_id,
            scenario_run_id=scenario_run_id,
            simulation_count=num_sims,
            random_seed=seed,
            expected_portfolio_contribution=round(exp_contrib, 2),
            portfolio_contribution_std=round(std_contrib, 2),
            expected_portfolio_revenue=round(exp_rev, 2),
            expected_portfolio_cost=round(exp_cost, 2),
            percentiles=percentiles,
            var90_level=var_cvar["var90_level"],
            var95_level=var_cvar["var95_level"],
            var90_downside=var_cvar["var90_downside"],
            var95_downside=var_cvar["var95_downside"],
            cvar90=var_cvar["cvar90"],
            cvar95=var_cvar["cvar95"],
            loss_probability=loss_prob,
            expected_loss=exp_loss,
            plan_reliability_score=reliability_score,
            risk_tier=risk_tier,
            assignments=assignment_results,
            drivers=drivers,
            distribution_histogram=histogram,
            provenance_audit=provenance_audit,
        )

    def _find_matching_var(
        self, variables: Sequence[RiskVariable], match_keys: Sequence[Any]
    ) -> Optional[str]:
        """Finds variable ID matching given categories or string keywords."""
        for v in variables:
            for key in match_keys:
                if isinstance(key, RiskCategory) and v.category == key:
                    return v.variable_id
                if isinstance(key, str):
                    if key.lower() in v.variable_id.lower() or key.lower() in v.name.lower():
                        return v.variable_id
        return None
