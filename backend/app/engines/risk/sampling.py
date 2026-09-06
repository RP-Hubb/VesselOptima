"""
VesselOptima — Phase 9: Joint Risk Sampler

Coordinates joint stochastic sampling across independent and correlated
risk variable groups for Monte Carlo simulations.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Sequence, Union
import numpy as np

from app.engines.risk.correlation import CorrelationEngine
from app.engines.risk.distributions import DistributionSampler
from app.engines.risk.models import CorrelationConfig, RiskVariable

logger = logging.getLogger("vesseloptima.engines.risk.sampling")


class RiskSampler:
    """
    Coordinates joint sampling of risk variables for a simulation run.
    """

    @classmethod
    def sample_all(
        cls,
        rng: np.random.Generator,
        variables: List[RiskVariable],
        correlation_config: Optional[CorrelationConfig],
        size: int,
    ) -> Dict[str, np.ndarray]:
        """
        Generates `size` stochastic realizations for each variable in `variables`.
        Respects `correlation_config` where specified.
        """
        corrs = [correlation_config] if correlation_config else []
        return cls._sample_internal(rng, variables, corrs, size)

    @classmethod
    def sample_variables(
        cls,
        variables: Sequence[RiskVariable],
        correlations: Optional[Union[Sequence[CorrelationConfig], CorrelationConfig]] = None,
        n_samples: int = 5000,
        seed: int = 42,
    ) -> Dict[str, np.ndarray]:
        """
        Main sampling interface for Monte Carlo simulation engine.
        Handles multiple correlation blocks and deterministic seeding.
        """
        rng = np.random.default_rng(seed)
        if correlations is None:
            corrs = []
        elif isinstance(correlations, CorrelationConfig):
            corrs = [correlations]
        else:
            corrs = list(correlations)

        return cls._sample_internal(rng, list(variables), corrs, n_samples)

    @classmethod
    def _sample_internal(
        cls,
        rng: np.random.Generator,
        variables: List[RiskVariable],
        correlations: List[CorrelationConfig],
        size: int,
    ) -> Dict[str, np.ndarray]:
        var_map = {v.variable_id: v for v in variables}
        samples: Dict[str, np.ndarray] = {}
        correlated_var_ids: set[str] = set()

        # 1. Correlated group sampling across all correlation matrices
        for corr in correlations:
            if not corr or not corr.variable_ids:
                continue
            corr_ids = corr.variable_ids
            corr_matrix = np.array(corr.matrix, dtype=np.float64)
            corr_vars = [var_map[vid] for vid in corr_ids if vid in var_map]

            if len(corr_vars) == len(corr_ids):
                corr_samples = CorrelationEngine.sample_correlated_group(
                    rng=rng,
                    variables=corr_vars,
                    correlation_matrix=corr_matrix,
                    size=size,
                )
                samples.update(corr_samples)
                correlated_var_ids.update(corr_ids)
            else:
                logger.warning(
                    f"Correlation group {corr_ids} has missing variables in simulation set. Falling back."
                )

        # 2. Independent variable sampling
        for var in variables:
            if var.variable_id not in correlated_var_ids:
                samples[var.variable_id] = DistributionSampler.sample(
                    rng,
                    var,
                    size,
                )

        return samples
