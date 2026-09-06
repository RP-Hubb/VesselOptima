"""
VesselOptima — Phase 9: Risk Metrics & Statistical Calculations

Computes portfolio-level and assignment-level risk statistics:
- Expectation, Dispersion, and Percentiles (P05 through P95)
- Value at Risk (VaR90, VaR95) and Conditional Value at Risk / Expected Shortfall (CVaR90, CVaR95)
- Loss Probability & Expected Downside Loss
- Schedule Arrival Percentiles, Buffer Days, and Laycan Miss Probability
- Economic, Schedule, and Combined Survival Probabilities
- Composite Plan Reliability Score & Risk Tier Classification
- Risk Driver Sensitivity Coefficients & Variance Attribution
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np

from app.engines.risk.reason_codes import RiskTier
from app.engines.risk.result import AssignmentRiskResult, RiskDriverResult


class RiskMetricsCalculator:
    """Institutional-grade financial and operational risk metric engine."""

    @staticmethod
    def calculate_percentiles(values: np.ndarray) -> Dict[str, float]:
        """Calculates standard risk percentiles (P05 to P95) in USD."""
        if len(values) == 0:
            return {f"P{q:02d}": 0.0 for q in [5, 10, 25, 50, 75, 90, 95]}

        qs = [5, 10, 25, 50, 75, 90, 95]
        computed = np.percentile(values, qs)
        return {f"P{q:02d}": round(float(val), 2) for q, val in zip(qs, computed)}

    @staticmethod
    def calculate_var_cvar(
        values: np.ndarray,
        expected_val: float,
        confidence_levels: Sequence[float] = (0.90, 0.95),
    ) -> Dict[str, float]:
        """
        Calculates VaR level, VaR downside, and CVaR (Expected Shortfall).
        
        Sign convention:
        - var_level: The lower tail quantile (e.g. 5th percentile outcome).
        - var_downside: The gap between expected value and the quantile (E[X] - P05).
        - cvar: The expected value conditional on falling into the worst tail (mean of values <= var_level).
        """
        if len(values) == 0:
            return {
                "var90_level": 0.0,
                "var90_downside": 0.0,
                "cvar90": 0.0,
                "var95_level": 0.0,
                "var95_downside": 0.0,
                "cvar95": 0.0,
            }

        res = {}
        for cl in confidence_levels:
            tail_pct = (1.0 - cl) * 100.0
            var_level = float(np.percentile(values, tail_pct))
            var_downside = float(expected_val - var_level)

            tail_mask = values <= var_level
            if np.any(tail_mask):
                cvar = float(np.mean(values[tail_mask]))
            else:
                cvar = var_level

            cl_int = int(cl * 100)
            res[f"var{cl_int}_level"] = round(var_level, 2)
            res[f"var{cl_int}_downside"] = round(max(0.0, var_downside), 2)
            res[f"cvar{cl_int}"] = round(cvar, 2)

        return res

    @staticmethod
    def calculate_loss_metrics(values: np.ndarray) -> Tuple[float, float]:
        """
        Calculates:
        1. Loss probability: fraction of draws where contribution < 0
        2. Expected loss: mean of negative outcomes (or 0.0 if all >= 0)
        """
        if len(values) == 0:
            return 0.0, 0.0

        losses = values[values < 0.0]
        loss_prob = float(len(losses) / len(values))
        expected_loss = float(np.mean(losses)) if len(losses) > 0 else 0.0
        return round(loss_prob, 4), round(abs(expected_loss), 2)

    @staticmethod
    def classify_risk_tier(loss_prob: float, laycan_miss_prob: float = 0.0) -> RiskTier:
        """
        Classifies risk into standardized institutional tiers based on
        loss and schedule miss probabilities.
        """
        max_risk = max(loss_prob, laycan_miss_prob)
        if max_risk < 0.05:
            return RiskTier.LOW
        elif max_risk < 0.15:
            return RiskTier.MODERATE
        elif max_risk < 0.30:
            return RiskTier.HIGH
        else:
            return RiskTier.CRITICAL

    @staticmethod
    def calculate_reliability_score(
        loss_prob: float,
        schedule_survival_prob: float,
        expected_contribution: float,
        var95_downside: float,
    ) -> float:
        """
        Computes composite institutional plan reliability score in [0.0, 100.0].
        Incorporates economic survival (50%), schedule reliability (30%),
        and tail downside risk dampener (20%).
        """
        econ_score = max(0.0, 1.0 - 2.0 * loss_prob)
        sched_score = max(0.0, schedule_survival_prob)

        # Downside tail penalty relative to expected return
        if expected_contribution > 0:
            dispersion_ratio = var95_downside / (expected_contribution + 1e-4)
            tail_factor = max(0.0, 1.0 - min(1.0, dispersion_ratio * 0.35))
        else:
            tail_factor = 0.0

        score = (0.50 * econ_score + 0.30 * sched_score + 0.20 * tail_factor) * 100.0
        return round(float(np.clip(score, 0.0, 100.0)), 1)

    @staticmethod
    def compute_histogram(values: np.ndarray, bins: int = 25) -> List[Dict[str, Any]]:
        """Generates binned frequency distribution for UI rendering."""
        if len(values) == 0:
            return []

        counts, bin_edges = np.histogram(values, bins=bins)
        total = float(len(values))

        histogram = []
        for i in range(len(counts)):
            histogram.append(
                {
                    "bin_start": round(float(bin_edges[i]), 2),
                    "bin_end": round(float(bin_edges[i + 1]), 2),
                    "count": int(counts[i]),
                    "frequency": round(float(counts[i] / total), 4),
                }
            )
        return histogram

    @classmethod
    def decompose_variance(
        cls,
        variable_samples: Dict[str, np.ndarray],
        portfolio_contributions: np.ndarray,
        variable_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[RiskDriverResult]:
        """
        Calculates uncertainty contribution percentage and sensitivity coefficients
        for each stochastic risk variable using variance decomposition and covariance attribution.
        """
        if len(portfolio_contributions) == 0 or not variable_samples:
            return []

        var_total = float(np.var(portfolio_contributions))
        if var_total < 1e-9:
            # Zero variance fallback
            drivers = []
            for var_id in variable_samples.keys():
                meta = (variable_metadata or {}).get(var_id, {})
                drivers.append(
                    RiskDriverResult(
                        variable_id=var_id,
                        name=meta.get("name", var_id),
                        category=meta.get("category", "OPERATIONAL"),
                        uncertainty_contribution_pct=round(100.0 / len(variable_samples), 2),
                        sensitivity_coefficient=0.0,
                    )
                )
            return drivers

        comp_variances: Dict[str, float] = {}
        sensitivities: Dict[str, float] = {}

        for var_id, samples in variable_samples.items():
            var_x = float(np.var(samples))
            if var_x > 1e-9:
                cov = float(np.cov(samples, portfolio_contributions)[0, 1])
                beta = cov / var_x
                comp_var = (beta ** 2) * var_x
            else:
                cov = 0.0
                beta = 0.0
                comp_var = 0.0

            comp_variances[var_id] = comp_var
            sensitivities[var_id] = beta

        total_comp_var = sum(comp_variances.values())
        drivers = []
        for var_id, c_var in comp_variances.items():
            meta = (variable_metadata or {}).get(var_id, {})
            pct = (c_var / total_comp_var * 100.0) if total_comp_var > 1e-9 else (100.0 / len(variable_samples))
            drivers.append(
                RiskDriverResult(
                    variable_id=var_id,
                    name=meta.get("name", var_id),
                    category=meta.get("category", "OPERATIONAL"),
                    uncertainty_contribution_pct=round(pct, 2),
                    sensitivity_coefficient=round(sensitivities[var_id], 4),
                )
            )

        # Sort descending by uncertainty contribution
        drivers.sort(key=lambda d: d.uncertainty_contribution_pct, reverse=True)
        return drivers

    @classmethod
    def calculate_assignment_metrics(
        cls,
        candidate_id: str,
        vessel_id: int,
        vessel_name: str,
        cargo_id: Optional[int],
        cargo_name: str,
        revenue_samples: np.ndarray,
        cost_samples: np.ndarray,
        contribution_samples: np.ndarray,
        arrival_date_samples: np.ndarray,
        laycan_end_iso: str,
        departure_date: datetime,
    ) -> AssignmentRiskResult:
        """Computes comprehensive risk metrics for an individual vessel-cargo assignment."""
        exp_rev = float(np.mean(revenue_samples))
        exp_cost = float(np.mean(cost_samples))
        exp_contrib = float(np.mean(contribution_samples))
        std_contrib = float(np.std(contribution_samples))

        var_cvar = cls.calculate_var_cvar(contribution_samples, exp_contrib)
        loss_prob, _ = cls.calculate_loss_metrics(contribution_samples)

        # Schedule Arrival Calculations
        laycan_end_dt = datetime.fromisoformat(laycan_end_iso.replace("Z", ""))
        
        # arrival_date_samples are simulated days from departure
        p50_days = float(np.percentile(arrival_date_samples, 50))
        p90_days = float(np.percentile(arrival_date_samples, 90))
        p95_days = float(np.percentile(arrival_date_samples, 95))
        exp_days = float(np.mean(arrival_date_samples))

        exp_arrival_dt = departure_date + timedelta(days=exp_days)
        p50_arrival_dt = departure_date + timedelta(days=p50_days)
        p90_arrival_dt = departure_date + timedelta(days=p90_days)
        p95_arrival_dt = departure_date + timedelta(days=p95_days)

        buffer_days = (laycan_end_dt - exp_arrival_dt).total_seconds() / 86400.0

        # Laycan miss probability: fraction of arrivals past laycan_end_dt
        simulated_arrivals_dt = [departure_date + timedelta(days=float(d)) for d in arrival_date_samples]
        miss_count = sum(1 for arr in simulated_arrivals_dt if arr > laycan_end_dt)
        laycan_miss_prob = float(miss_count / len(arrival_date_samples)) if len(arrival_date_samples) > 0 else 0.0

        econ_survival = 1.0 - loss_prob
        sched_survival = 1.0 - laycan_miss_prob

        # Combined survival: contribution > 0 AND arrival <= laycan_end
        combined_count = sum(
            1 for c, arr in zip(contribution_samples, simulated_arrivals_dt)
            if c > 0.0 and arr <= laycan_end_dt
        )
        combined_survival = float(combined_count / len(contribution_samples)) if len(contribution_samples) > 0 else 0.0

        risk_tier = cls.classify_risk_tier(loss_prob, laycan_miss_prob)

        return AssignmentRiskResult(
            candidate_id=candidate_id,
            vessel_id=vessel_id,
            vessel_name=vessel_name,
            cargo_id=cargo_id,
            cargo_name=cargo_name,
            expected_revenue=round(exp_rev, 2),
            expected_cost=round(exp_cost, 2),
            expected_net_contribution=round(exp_contrib, 2),
            contribution_std=round(std_contrib, 2),
            loss_probability=round(loss_prob, 4),
            var95_downside=var_cvar["var95_downside"],
            cvar95=var_cvar["cvar95"],
            expected_arrival=exp_arrival_dt.isoformat(),
            p50_arrival=p50_arrival_dt.isoformat(),
            p90_arrival=p90_arrival_dt.isoformat(),
            p95_arrival=p95_arrival_dt.isoformat(),
            laycan_end=laycan_end_iso,
            schedule_buffer_days=round(buffer_days, 2),
            laycan_miss_probability=round(laycan_miss_prob, 4),
            economic_survival_probability=round(econ_survival, 4),
            schedule_survival_probability=round(sched_survival, 4),
            combined_survival_probability=round(combined_survival, 4),
            risk_tier=risk_tier,
        )
