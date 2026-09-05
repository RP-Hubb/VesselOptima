"""
VesselOptima — Prediction Interval & Forecast Uncertainty Service

Calculates defensible prediction intervals based on out-of-sample empirical
residual distributions calibrated during walk-forward validation.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

import numpy as np


class ForecastUncertaintyService:
    """
    Computes empirical residual-based prediction intervals for multi-step forecasts.
    Guarantees structural invariance: lower <= point_forecast <= upper, and lower >= 0.
    """

    DEFAULT_COVERAGES = [0.80, 0.95]

    def __init__(self, coverages: List[float] = None):
        self.coverages = coverages or self.DEFAULT_COVERAGES

    def compute_prediction_intervals(
        self,
        point_forecasts: np.ndarray,
        validation_residuals: List[float],
        coverage: float = 0.80,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Derives lower and upper prediction intervals for point_forecasts using
        the empirical distribution of out-of-sample validation residuals.

        Args:
            point_forecasts: 1D array of point forecasts for horizon 1..H
            validation_residuals: list of out-of-sample errors (actual - pred)
            coverage: nominal coverage level (e.g. 0.80 for 80% interval, 0.95 for 95%)

        Returns:
            Tuple of (lower_bounds, upper_bounds)
        """
        if len(validation_residuals) < 10:
            # Fallback to standard deviation of whatever residuals exist or 5% default
            std_err = np.std(validation_residuals) if len(validation_residuals) > 1 else 0.05
            lower_q = -1.28 * std_err
            upper_q = 1.28 * std_err
        else:
            residuals = np.asarray(validation_residuals, dtype=np.float64)
            alpha = 1.0 - coverage
            q_low = (alpha / 2.0) * 100.0
            q_high = (1.0 - alpha / 2.0) * 100.0
            lower_q = float(np.percentile(residuals, q_low))
            upper_q = float(np.percentile(residuals, q_high))

        lower_bounds = []
        upper_bounds = []

        for h_step, pt_val in enumerate(point_forecasts, start=1):
            # Variance expands gracefully with forecast horizon (sqrt growth factor)
            horizon_expansion = math.sqrt(1.0 + 0.05 * (h_step - 1))

            raw_lower = pt_val + lower_q * horizon_expansion
            raw_upper = pt_val + upper_q * horizon_expansion

            # Invariance enforcement:
            # 1. Lower bound must be <= point forecast
            # 2. Upper bound must be >= point forecast
            # 3. Non-negative constraint for bulk shipping freight/commodity rates
            safe_lower = max(0.0, min(float(pt_val), float(raw_lower)))
            safe_upper = max(float(pt_val), float(raw_upper))

            lower_bounds.append(round(safe_lower, 2))
            upper_bounds.append(round(safe_upper, 2))

        return np.array(lower_bounds), np.array(upper_bounds)
