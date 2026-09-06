"""
VesselOptima — Phase 9: Correlation Matrix Validation & Copula Sampling Engine

Validates correlation matrix properties (dimensions, symmetry, unit diagonal,
positive semi-definiteness) and generates correlated draws via Gaussian Copula
and Cholesky decomposition.
"""

from __future__ import annotations

import logging
from typing import Dict, List
import numpy as np
import scipy.stats as stats

from app.engines.risk.distributions import DistributionSampler, InvalidRiskParameterError
from app.engines.risk.models import CorrelationConfig, RiskVariable
from app.engines.risk.reason_codes import RiskReasonCode

logger = logging.getLogger("vesseloptima.engines.risk.correlation")


class CorrelationEngine:
    """
    Validates correlation structures and generates joint stochastic samples.
    """

    @classmethod
    def validate_matrix(cls, matrix: np.ndarray, expected_dim: int) -> None:
        """
        Ensures correlation matrix is square, symmetric, has unit diagonal,
        and is positive semi-definite.
        """
        if not isinstance(matrix, np.ndarray):
            matrix = np.array(matrix, dtype=np.float64)

        if matrix.ndim != 2:
            raise InvalidRiskParameterError(
                f"Correlation matrix must be 2-dimensional, got {matrix.ndim}D.",
                reason_code=RiskReasonCode.INVALID_CORRELATION_MATRIX,
            )

        rows, cols = matrix.shape
        if rows != cols:
            raise InvalidRiskParameterError(
                f"Correlation matrix must be square, got shape ({rows}, {cols}).",
                reason_code=RiskReasonCode.INVALID_CORRELATION_MATRIX,
            )

        if rows != expected_dim:
            raise InvalidRiskParameterError(
                f"Correlation matrix dimension ({rows}) does not match number of variables ({expected_dim}).",
                reason_code=RiskReasonCode.INVALID_CORRELATION_MATRIX,
            )

        # Symmetry check
        if not np.allclose(matrix, matrix.T, atol=1e-5):
            raise InvalidRiskParameterError(
                "Correlation matrix must be symmetric (C[i,j] == C[j,i]).",
                reason_code=RiskReasonCode.INVALID_CORRELATION_MATRIX,
            )

        # Unit diagonal check
        diag = np.diag(matrix)
        if not np.allclose(diag, 1.0, atol=1e-5):
            raise InvalidRiskParameterError(
                "Correlation matrix diagonal elements must all equal 1.0.",
                reason_code=RiskReasonCode.INVALID_CORRELATION_MATRIX,
            )

        # Correlation bound check: all elements in [-1, 1]
        if np.any(matrix < -1.0 - 1e-5) or np.any(matrix > 1.0 + 1e-5):
            raise InvalidRiskParameterError(
                "All correlation matrix coefficients must lie in the interval [-1.0, 1.0].",
                reason_code=RiskReasonCode.INVALID_CORRELATION_MATRIX,
            )

        # Positive semi-definiteness: eigenvalues >= -1e-6
        eigenvalues = np.linalg.eigvalsh(matrix)
        min_eig = np.min(eigenvalues)
        if min_eig < -1e-6:
            raise InvalidRiskParameterError(
                f"Correlation matrix must be positive semi-definite. Minimum eigenvalue is {min_eig:.6f} < 0.",
                reason_code=RiskReasonCode.INVALID_CORRELATION_MATRIX,
            )
        return True

    @classmethod
    def validate_and_decompose(cls, matrix: Any, expected_dim: int) -> np.ndarray:
        """Validates matrix and returns lower-triangular Cholesky factor L."""
        if not isinstance(matrix, np.ndarray):
            matrix = np.array(matrix, dtype=np.float64)
        cls.validate_matrix(matrix, expected_dim)

        min_eig = np.min(np.linalg.eigvalsh(matrix))
        if min_eig < 1e-7:
            reg_matrix = matrix + np.eye(expected_dim) * (1e-6 - min_eig)
            d_inv = 1.0 / np.sqrt(np.diag(reg_matrix))
            reg_matrix = d_inv[:, None] * reg_matrix * d_inv[None, :]
        else:
            reg_matrix = matrix

        return np.linalg.cholesky(reg_matrix)

    @classmethod
    def sample_correlated_group(
        cls,
        *args,
        **kwargs,
    ) -> Dict[str, np.ndarray]:
        """
        Samples correlated variables using a Gaussian Copula.
        Supports:
        - sample_correlated_group(rng, variables, correlation_matrix, size)
        - sample_correlated_group(variables, corr_cfg, n_samples=..., seed=...)
        """
        if len(args) == 4 and isinstance(args[0], np.random.Generator):
            rng = args[0]
            variables = args[1]
            correlation_matrix = np.array(args[2], dtype=np.float64)
            size = args[3]
        elif len(args) >= 2 and isinstance(args[0], list):
            variables = args[0]
            corr_input = args[1]
            if isinstance(corr_input, CorrelationConfig):
                correlation_matrix = np.array(corr_input.matrix, dtype=np.float64)
            else:
                correlation_matrix = np.array(corr_input, dtype=np.float64)
            size = kwargs.get("n_samples", kwargs.get("size", 1000))
            seed = kwargs.get("seed", 42)
            rng = np.random.default_rng(seed)
        else:
            variables = kwargs["variables"]
            corr_input = kwargs.get("correlation_matrix", kwargs.get("corr_cfg"))
            if isinstance(corr_input, CorrelationConfig):
                correlation_matrix = np.array(corr_input.matrix, dtype=np.float64)
            else:
                correlation_matrix = np.array(corr_input, dtype=np.float64)
            size = kwargs.get("n_samples", kwargs.get("size", 1000))
            if "rng" in kwargs:
                rng = kwargs["rng"]
            else:
                rng = np.random.default_rng(kwargs.get("seed", 42))

        k = len(variables)
        L = cls.validate_and_decompose(correlation_matrix, expected_dim=k)

        # Uncorrelated standard normal draws (k, size)
        z_uncorr = rng.standard_normal(size=(k, size))

        # Correlated standard normal draws (k, size)
        z_corr = L @ z_uncorr

        # Map to uniform via standard normal CDF
        u_copula = stats.norm.cdf(z_corr)

        # Map to target marginal distributions
        results: Dict[str, np.ndarray] = {}
        for idx, var in enumerate(variables):
            u_var = u_copula[idx, :]
            results[var.variable_id] = DistributionSampler.ppf(u_var, var)

        return results
