"""
VesselOptima — Phase 9: Probability Distributions & Domain Validation

Implements rigorous parameter validation and sampling for supported stochastic distributions:
DETERMINISTIC, NORMAL, LOGNORMAL, TRIANGULAR, UNIFORM, EMPIRICAL.
Strictly enforces physical and economic domain constraints (e.g. bunker price > 0).
"""

from __future__ import annotations

import logging
from typing import Any, Dict
import numpy as np
import scipy.stats as stats

from app.engines.risk.models import DistributionType, RiskVariable
from app.engines.risk.reason_codes import RiskCategory, RiskReasonCode

logger = logging.getLogger("vesseloptima.engines.risk.distributions")


class InvalidRiskParameterError(ValueError):
    """Raised when a risk variable specifies mathematically or physically invalid parameters."""
    def __init__(self, message: str, reason_code: RiskReasonCode = RiskReasonCode.INVALID_RISK_PARAMETER):
        super().__init__(message)
        self.reason_code = reason_code


PhysicalDomainViolation = InvalidRiskParameterError


class DistributionValidator:
    """
    Enforces domain constraints for stochastic risk variables.
    """

    @classmethod
    def validate(cls, var: RiskVariable) -> bool:
        params = var.parameters
        dtype = var.distribution_type
        cat = var.category

        if not isinstance(params, dict):
            raise InvalidRiskParameterError(
                f"Variable '{var.variable_id}' parameters must be a dictionary, got {type(params)}."
            )

        if dtype == DistributionType.DETERMINISTIC:
            val = params.get("value", params.get("c"))
            if val is None:
                raise InvalidRiskParameterError(f"Deterministic variable '{var.variable_id}' requires 'value' parameter.")
            val = float(val)
            cls._check_domain_bounds(var.variable_id, cat, val, val)

        elif dtype == DistributionType.NORMAL:
            std_raw = params.get("std_dev", params.get("std"))
            if "mean" not in params or std_raw is None:
                raise InvalidRiskParameterError(f"Normal distribution for '{var.variable_id}' requires 'mean' and 'std_dev' (or 'std').")
            mean = float(params["mean"])
            std = float(std_raw)
            if std <= 0:
                raise InvalidRiskParameterError(f"Normal distribution std_dev must be strictly positive, got {std}.")
            if cat == RiskCategory.BUNKER and mean <= 0:
                raise InvalidRiskParameterError(
                    f"Bunker price mean must be strictly positive, got {mean}.",
                    reason_code=RiskReasonCode.NON_POSITIVE_PRICE,
                )
            if cat in (RiskCategory.PORT_DELAY, RiskCategory.WEATHER_DELAY, RiskCategory.SCHEDULE_DELAY) and mean < 0:
                raise InvalidRiskParameterError(
                    f"Delays cannot be negative, got {mean}.",
                    reason_code=RiskReasonCode.NEGATIVE_DURATION,
                )

        elif dtype == DistributionType.LOGNORMAL:
            # Can be specified as (mean, std_dev) of underlying process or (log_mean, log_std)
            if "log_mean" in params and "log_std" in params:
                log_std = float(params["log_std"])
                if log_std <= 0:
                    raise InvalidRiskParameterError(f"Lognormal log_std must be > 0, got {log_std}.")
            elif "mean" in params and ("std_dev" in params or "std" in params):
                mean = float(params["mean"])
                std = float(params.get("std_dev", params.get("std")))
                if mean <= 0 or std <= 0:
                    raise InvalidRiskParameterError(f"Lognormal mean and std_dev must be strictly positive, got mean={mean}, std={std}.")
            else:
                raise InvalidRiskParameterError(
                    f"Lognormal distribution for '{var.variable_id}' requires either ('log_mean', 'log_std') or ('mean', 'std_dev')."
                )

        elif dtype == DistributionType.TRIANGULAR:
            low = float(params.get("low", params.get("min", 0.0)))
            mode = float(params.get("mode", params.get("c", low)))
            high = float(params.get("high", params.get("max", mode)))

            if not (low <= mode <= high) or low >= high:
                raise InvalidRiskParameterError(
                    f"Triangular parameters must satisfy low <= mode <= high and low < high, got low={low}, mode={mode}, high={high}."
                )
            cls._check_domain_bounds(var.variable_id, cat, low, high)

        elif dtype == DistributionType.UNIFORM:
            low = float(params.get("low", params.get("min", 0.0)))
            high = float(params.get("high", params.get("max", 1.0)))
            if low >= high:
                raise InvalidRiskParameterError(f"Uniform distribution requires low < high, got low={low}, high={high}.")
            cls._check_domain_bounds(var.variable_id, cat, low, high)

        elif dtype == DistributionType.EMPIRICAL:
            values = params.get("values", [])
            if not isinstance(values, list) or len(values) == 0:
                raise InvalidRiskParameterError(f"Empirical distribution for '{var.variable_id}' requires a non-empty 'values' list.")
            min_val = min(float(x) for x in values)
            max_val = max(float(x) for x in values)
            cls._check_domain_bounds(var.variable_id, cat, min_val, max_val)

        else:
            raise InvalidRiskParameterError(f"Unsupported distribution type: {dtype}", reason_code=RiskReasonCode.INVALID_DISTRIBUTION)

        return True

    @classmethod
    def _check_domain_bounds(cls, var_id: str, category: RiskCategory, min_val: float, max_val: float) -> None:
        if category == RiskCategory.BUNKER:
            if min_val <= 0:
                raise InvalidRiskParameterError(
                    f"Bunker price variable '{var_id}' violates physical domain: fuel price must be strictly positive (> 0), min={min_val}.",
                    reason_code=RiskReasonCode.NON_POSITIVE_PRICE,
                )
        elif category == RiskCategory.FREIGHT:
            if min_val < 0:
                raise InvalidRiskParameterError(
                    f"Freight rate variable '{var_id}' violates domain: freight rate cannot be negative, min={min_val}."
                )
        elif category in (RiskCategory.SCHEDULE_DELAY, RiskCategory.PORT_DELAY, RiskCategory.WEATHER_DELAY):
            if min_val < 0:
                raise InvalidRiskParameterError(
                    f"Schedule delay variable '{var_id}' violates physical bounds: delay cannot be negative, min={min_val}.",
                    reason_code=RiskReasonCode.NEGATIVE_DURATION,
                )


class DistributionSampler:
    """
    Generates vectorized pseudo-random samples for validated risk variables.
    """

    @classmethod
    def sample(cls, *args, **kwargs) -> np.ndarray:
        if len(args) == 3 and isinstance(args[0], np.random.Generator):
            rng, var, size = args
        elif len(args) >= 1 and isinstance(args[0], RiskVariable):
            var = args[0]
            size = kwargs.get("n_samples", kwargs.get("size", 1000))
            seed = kwargs.get("seed", 42)
            rng = np.random.default_rng(seed)
        elif "var" in kwargs:
            var = kwargs["var"]
            size = kwargs.get("n_samples", kwargs.get("size", 1000))
            if "rng" in kwargs:
                rng = kwargs["rng"]
            else:
                rng = np.random.default_rng(kwargs.get("seed", 42))
        else:
            raise ValueError("Invalid arguments for DistributionSampler.sample")

        DistributionValidator.validate(var)
        params = var.parameters
        dtype = var.distribution_type

        if dtype == DistributionType.DETERMINISTIC:
            val = float(params.get("value", params.get("c", 0.0)))
            return np.full(size, val, dtype=np.float64)

        elif dtype == DistributionType.NORMAL:
            mean = float(params["mean"])
            std = float(params.get("std_dev", params.get("std", 1.0)))
            draws = rng.normal(loc=mean, scale=std, size=size)
            if var.category == RiskCategory.BUNKER:
                # Avoid non-physical negative price draws
                draws = np.maximum(draws, 1.0)
            return draws

        elif dtype == DistributionType.LOGNORMAL:
            if "log_mean" in params and "log_std" in params:
                mu = float(params["log_mean"])
                sigma = float(params["log_std"])
            else:
                mean = float(params["mean"])
                std = float(params.get("std_dev", params.get("std", 1.0)))
                # Convert mean, variance of lognormal to underlying normal mu, sigma
                var_val = std ** 2
                mu = np.log((mean ** 2) / np.sqrt(var_val + mean ** 2))
                sigma = np.sqrt(np.log(1.0 + (var_val / (mean ** 2))))
            return rng.lognormal(mean=mu, sigma=sigma, size=size)

        elif dtype == DistributionType.TRIANGULAR:
            low = float(params.get("low", params.get("min", 0.0)))
            mode = float(params.get("mode", params.get("c", low)))
            high = float(params.get("high", params.get("max", mode)))
            return rng.triangular(left=low, mode=mode, right=high, size=size)

        elif dtype == DistributionType.UNIFORM:
            low = float(params.get("low", params.get("min", 0.0)))
            high = float(params.get("high", params.get("max", 1.0)))
            return rng.uniform(low=low, high=high, size=size)

        elif dtype == DistributionType.EMPIRICAL:
            values = np.array(params["values"], dtype=np.float64)
            return rng.choice(values, size=size, replace=True)

        raise InvalidRiskParameterError(f"Unsupported distribution type: {dtype}")

    @classmethod
    def ppf(cls, u: np.ndarray, var: RiskVariable) -> np.ndarray:
        """
        Computes the Percent Point Function (inverse CDF / quantile function)
        for uniform draws u in (0, 1) to enable copula correlation sampling.
        """
        DistributionValidator.validate(var)
        params = var.parameters
        dtype = var.distribution_type

        # Clip u to avoid exact 0 or 1 edge singularities
        u_safe = np.clip(u, 1e-6, 1.0 - 1e-6)

        if dtype == DistributionType.DETERMINISTIC:
            val = float(params.get("value", params.get("c", 0.0)))
            return np.full_like(u_safe, val)

        elif dtype == DistributionType.NORMAL:
            mean = float(params["mean"])
            std = float(params.get("std_dev", params.get("std", 1.0)))
            draws = stats.norm.ppf(u_safe, loc=mean, scale=std)
            if var.category == RiskCategory.BUNKER:
                draws = np.maximum(draws, 1.0)
            return draws

        elif dtype == DistributionType.LOGNORMAL:
            if "log_mean" in params and "log_std" in params:
                mu = float(params["log_mean"])
                sigma = float(params["log_std"])
            else:
                mean = float(params["mean"])
                std = float(params.get("std_dev", params.get("std", 1.0)))
                var_val = std ** 2
                mu = np.log((mean ** 2) / np.sqrt(var_val + mean ** 2))
                sigma = np.sqrt(np.log(1.0 + (var_val / (mean ** 2))))
            return stats.lognorm.ppf(u_safe, s=sigma, scale=np.exp(mu))

        elif dtype == DistributionType.TRIANGULAR:
            low = float(params.get("low", params.get("min", 0.0)))
            mode = float(params.get("mode", params.get("c", low)))
            high = float(params.get("high", params.get("max", mode)))
            c = (mode - low) / (high - low)
            return stats.triang.ppf(u_safe, c=c, loc=low, scale=(high - low))

        elif dtype == DistributionType.UNIFORM:
            low = float(params.get("low", params.get("min", 0.0)))
            high = float(params.get("high", params.get("max", 1.0)))
            return stats.uniform.ppf(u_safe, loc=low, scale=(high - low))

        elif dtype == DistributionType.EMPIRICAL:
            values = np.sort(np.array(params["values"], dtype=np.float64))
            return np.quantile(values, u_safe)

        raise InvalidRiskParameterError(f"Unsupported distribution type: {dtype}")
