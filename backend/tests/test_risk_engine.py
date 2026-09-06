"""
VesselOptima — Phase 9: Risk Intelligence & Uncertainty Engine Test Suite

Comprehensive tests covering:
1. Probability distributions and physical domain boundary validation
2. Deterministic seed reproducibility
3. Correlation matrices, Cholesky decomposition, and Gaussian copulas
4. Value at Risk (VaR), Conditional VaR (CVaR), and loss metrics
5. Schedule fragility, laycan miss probabilities, and buffer calculations
6. Variance decomposition and risk driver attribution
7. Vectorized Monte Carlo performance (10,000 iterations in < 500ms)
8. Critical Risk Flip comparative evaluation
9. Database persistence of runs, metrics, and assignment fragile points
10. Air-gap network isolation (0 external socket connections)
11. REST API endpoints integration
"""

import socket
import time
from datetime import datetime, timedelta
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import engine, get_db
from app.engines.risk.correlation import CorrelationEngine
from app.engines.risk.distributions import (
    DistributionSampler,
    DistributionValidator,
    PhysicalDomainViolation,
)
from app.engines.risk.metrics import RiskMetricsCalculator
from app.engines.risk.models import (
    CorrelationConfig,
    DistributionType,
    RiskSimulationConfig,
    RiskVariable,
)
from app.engines.risk.reason_codes import (
    ProvenanceType,
    RiskCategory,
    RiskTier,
)
from app.engines.risk.result import PlanRiskSimulationResult
from app.engines.risk.risk_service import RiskService
from app.engines.risk.sampling import RiskSampler
from app.engines.risk.simulation import MonteCarloEngine
from app.main import app
from app.models.domain import RiskDriver, RiskMetric, RiskRun


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ── 1. Distribution Validation & Physical Domain Safety ──────────────

def test_distribution_validator_valid_parameters():
    var_normal = RiskVariable(
        variable_id="freight_test",
        name="Freight Normal",
        category=RiskCategory.FREIGHT,
        distribution_type=DistributionType.NORMAL,
        parameters={"mean": 20.0, "std": 3.0},
    )
    assert DistributionValidator.validate(var_normal) is True

    var_lognormal = RiskVariable(
        variable_id="bunker_test",
        name="Bunker Lognormal",
        category=RiskCategory.BUNKER,
        distribution_type=DistributionType.LOGNORMAL,
        parameters={"mean": 600.0, "std": 50.0},
    )
    assert DistributionValidator.validate(var_lognormal) is True

    var_triangular = RiskVariable(
        variable_id="port_delay_test",
        name="Port Delay Triangular",
        category=RiskCategory.PORT_DELAY,
        distribution_type=DistributionType.TRIANGULAR,
        parameters={"min": 0.5, "mode": 1.5, "max": 4.0},
    )
    assert DistributionValidator.validate(var_triangular) is True


def test_distribution_validator_physical_domain_bunker_violation():
    """Bunker prices cannot be zero or negative."""
    var_bad_bunker = RiskVariable(
        variable_id="bunker_bad",
        name="Bad Bunker",
        category=RiskCategory.BUNKER,
        distribution_type=DistributionType.UNIFORM,
        parameters={"low": -50.0, "high": 200.0},
    )
    with pytest.raises(PhysicalDomainViolation, match="fuel price must be strictly positive"):
        DistributionValidator.validate(var_bad_bunker)


def test_distribution_validator_physical_domain_delay_violation():
    """Delays cannot be negative."""
    var_bad_delay = RiskVariable(
        variable_id="delay_bad",
        name="Negative Delay",
        category=RiskCategory.PORT_DELAY,
        distribution_type=DistributionType.NORMAL,
        parameters={"mean": -2.0, "std": 1.0},
    )
    with pytest.raises(PhysicalDomainViolation, match="Delays cannot be negative"):
        DistributionValidator.validate(var_bad_delay)


def test_distribution_validator_triangular_ordering():
    var_bad_tri = RiskVariable(
        variable_id="tri_bad",
        name="Bad Triangular",
        category=RiskCategory.OPERATIONAL,
        distribution_type=DistributionType.TRIANGULAR,
        parameters={"min": 5.0, "mode": 2.0, "max": 4.0},
    )
    with pytest.raises(ValueError, match="low <= mode <= high"):
        DistributionValidator.validate(var_bad_tri)


# ── 2. Sampling & Deterministic Seed Reproducibility ──────────────────

def test_sampling_deterministic_reproducibility():
    """Two simulation runs with identical seed produce bit-identical draws."""
    var = RiskVariable(
        variable_id="vlsfo",
        name="VLSFO",
        category=RiskCategory.BUNKER,
        distribution_type=DistributionType.LOGNORMAL,
        parameters={"mean": 550.0, "std": 45.0},
    )
    
    samples_1 = DistributionSampler.sample(var, n_samples=5000, seed=42)
    samples_2 = DistributionSampler.sample(var, n_samples=5000, seed=42)
    samples_3 = DistributionSampler.sample(var, n_samples=5000, seed=999)

    assert np.array_equal(samples_1, samples_2), "Identical seed must yield identical samples"
    assert not np.array_equal(samples_1, samples_3), "Different seed must yield different samples"
    assert len(samples_1) == 5000
    assert np.all(samples_1 > 0), "All bunker samples must be strictly positive"


# ── 3. Correlation Matrix & Cholesky Decomposition ────────────────────

def test_correlation_matrix_validation_success():
    valid_matrix = [
        [1.0, 0.4, 0.2],
        [0.4, 1.0, 0.1],
        [0.2, 0.1, 1.0],
    ]
    chol = CorrelationEngine.validate_and_decompose(valid_matrix, 3)
    assert chol.shape == (3, 3)
    # Check that L * L^T reconstructs correlation matrix
    reconstructed = np.dot(chol, chol.T)
    np.testing.assert_allclose(reconstructed, np.array(valid_matrix), atol=1e-6)


def test_correlation_matrix_asymmetric_rejection():
    asymmetric_matrix = [
        [1.0, 0.5],
        [0.2, 1.0],
    ]
    with pytest.raises(ValueError, match="Correlation matrix must be symmetric"):
        CorrelationEngine.validate_and_decompose(asymmetric_matrix, 2)


def test_correlation_matrix_non_positive_definite_rejection():
    non_psd = [
        [1.0, 0.99, 0.99],
        [0.99, 1.0, -0.99],
        [0.99, -0.99, 1.0],
    ]
    with pytest.raises(ValueError, match="positive semi-definite"):
        CorrelationEngine.validate_and_decompose(non_psd, 3)


def test_gaussian_copula_correlation_preservation():
    """Verifies that Gaussian copula preserves the rank correlation direction."""
    vars_list = [
        RiskVariable(
            variable_id="bunker",
            name="Bunker",
            category=RiskCategory.BUNKER,
            distribution_type=DistributionType.LOGNORMAL,
            parameters={"mean": 580.0, "std": 60.0},
        ),
        RiskVariable(
            variable_id="freight",
            name="Freight",
            category=RiskCategory.FREIGHT,
            distribution_type=DistributionType.NORMAL,
            parameters={"mean": 18.0, "std": 2.0},
        ),
    ]
    corr_cfg = CorrelationConfig(
        variable_ids=["bunker", "freight"],
        matrix=[[1.0, 0.60], [0.60, 1.0]],
    )
    samples = CorrelationEngine.sample_correlated_group(vars_list, corr_cfg, n_samples=10000, seed=42)
    sample_corr = np.corrcoef(samples["bunker"], samples["freight"])[0, 1]
    
    # Due to non-linear transformation, rank/pearson corr should be within [0.45, 0.65]
    assert 0.45 <= sample_corr <= 0.65, f"Expected correlation around 0.60, got {sample_corr:.3f}"


# ── 4. Statistical Metrics: VaR, CVaR, Loss Probabilities ────────────

def test_metrics_calculator_var_and_cvar():
    # Synthetic normal profit distribution with Mean = 100,000, Std = 20,000
    np.random.seed(42)
    profits = np.random.normal(loc=100000, scale=20000, size=10000)
    exp_val = float(np.mean(profits))

    metrics = RiskMetricsCalculator.calculate_var_cvar(profits, exp_val)
    
    # 5th percentile for Normal(100k, 20k) is ~ 100k - 1.645*20k = ~67,100
    assert 65000 <= metrics["var95_level"] <= 69000
    # VaR95 Downside is E[X] - P05 = ~32,900
    assert 30000 <= metrics["var95_downside"] <= 35000
    # CVaR95 is the average of the worst 5%, which must be <= VaR95_level
    assert metrics["cvar95"] < metrics["var95_level"]
    # Similarly, CVaR90 <= VaR90_level
    assert metrics["cvar90"] < metrics["var90_level"]


def test_metrics_calculator_loss_metrics():
    # Distribution with 10% negative outcomes
    draws = np.array([-1000.0, -500.0] + [2000.0] * 18)
    loss_prob, exp_loss = RiskMetricsCalculator.calculate_loss_metrics(draws)
    
    assert loss_prob == 0.10
    assert exp_loss == 750.0  # Mean of negative draws


def test_risk_tier_classification():
    assert RiskMetricsCalculator.classify_risk_tier(0.02, 0.01) == RiskTier.LOW
    assert RiskMetricsCalculator.classify_risk_tier(0.08, 0.04) == RiskTier.MODERATE
    assert RiskMetricsCalculator.classify_risk_tier(0.18, 0.05) == RiskTier.HIGH
    assert RiskMetricsCalculator.classify_risk_tier(0.35, 0.02) == RiskTier.CRITICAL


def test_reliability_score_bounds():
    score_healthy = RiskMetricsCalculator.calculate_reliability_score(
        loss_prob=0.01,
        schedule_survival_prob=0.98,
        expected_contribution=500000.0,
        var95_downside=50000.0,
    )
    score_risky = RiskMetricsCalculator.calculate_reliability_score(
        loss_prob=0.45,
        schedule_survival_prob=0.60,
        expected_contribution=100000.0,
        var95_downside=150000.0,
    )
    assert 90.0 <= score_healthy <= 100.0
    assert 0.0 <= score_risky < 45.0


def test_histogram_generation():
    values = np.random.normal(500, 50, 1000)
    histogram = RiskMetricsCalculator.compute_histogram(values, bins=20)
    assert len(histogram) == 20
    total_freq = sum(b["frequency"] for b in histogram)
    assert pytest.approx(total_freq, abs=1e-3) == 1.0
    total_count = sum(b["count"] for b in histogram)
    assert total_count == 1000


# ── 5. Variance Decomposition & Risk Drivers ─────────────────────────

def test_variance_decomposition():
    np.random.seed(42)
    n = 5000
    bunker_var = np.random.normal(580, 50, n)
    freight_var = np.random.normal(18, 2, n)
    delay_var = np.random.exponential(1.5, n)

    # Portfolio profit dominated by freight variability
    portfolio = (freight_var * 50000) - (bunker_var * 500) - (delay_var * 10000)

    samples = {
        "freight": freight_var,
        "bunker": bunker_var,
        "delay": delay_var,
    }
    drivers = RiskMetricsCalculator.decompose_variance(samples, portfolio)
    
    assert len(drivers) == 3
    # Freight should be the dominant driver
    assert drivers[0].variable_id == "freight"
    total_pct = sum(d.uncertainty_contribution_pct for d in drivers)
    assert pytest.approx(total_pct, abs=0.5) == 100.0


# ── 6. Monte Carlo Engine Vectorized Execution & Performance ─────────

def test_monte_carlo_performance_and_vectorization():
    """Guarantees 10,000 Monte Carlo iterations execute in under 500ms."""
    engine = MonteCarloEngine()
    cfg = RiskService.get_default_risk_config()
    cfg.simulation_count = 10000

    assignments = [
        {
            "candidate_id": "CAND-PERF-1",
            "vessel_id": 1,
            "vessel_name": "APJ JAD",
            "cargo_id": 101,
            "cargo_name": "Coal Paradip",
            "expected_revenue": 500000.0,
            "voyage_cost": 220000.0,
            "bunker_cost": 100000.0,
            "voyage_days": 14.0,
        },
        {
            "candidate_id": "CAND-PERF-2",
            "vessel_id": 2,
            "vessel_name": "APJ KAIS",
            "cargo_id": 102,
            "cargo_name": "Iron Ore Haldia",
            "expected_revenue": 600000.0,
            "voyage_cost": 240000.0,
            "bunker_cost": 110000.0,
            "voyage_days": 15.0,
        },
    ]

    t0 = time.time()
    result = engine.run_simulation(assignments, cfg)
    elapsed_ms = (time.time() - t0) * 1000.0

    assert elapsed_ms < 500.0, f"Monte Carlo 10,000 runs took {elapsed_ms:.1f}ms, expected < 500ms"
    assert result.simulation_count == 10000
    assert result.expected_portfolio_contribution > 0
    assert len(result.assignments) == 2
    assert len(result.drivers) > 0


# ── 7. Critical Risk Flip Demonstration (Institutional Proof) ────────

def test_critical_risk_flip_comparison():
    """
    Evaluates:
    - Plan A: higher expected contribution ($750k) but severe tail risk (loss prob 12%, CVaR95 low)
    - Plan B: slightly lower expected contribution ($702k) but near-zero tail risk (loss prob 0.4%, CVaR95 high)
    Verifies that Phase 9 detects and articulates the Critical Risk Flip.
    """
    service = RiskService()
    comparison = service.get_critical_risk_flip_demo()

    assert comparison.plan_a_expected_contribution > comparison.plan_b_expected_contribution
    assert comparison.plan_a_loss_probability > comparison.plan_b_loss_probability
    assert comparison.plan_a_cvar95 < comparison.plan_b_cvar95
    assert comparison.plan_b_reliability_score > comparison.plan_a_reliability_score
    assert "CRITICAL RISK FLIP" in comparison.trade_off_summary


# ── 8. Database Persistence & Retrieval ──────────────────────────────

def test_risk_service_persistence(client):
    db = next(get_db())
    service = RiskService(db=db)

    # Execute and persist simulation
    res = service.simulate_plan_risk(
        optimization_run_id="BASELINE_OPTIMAL",
        persist=True,
    )
    assert res.run_id.startswith("RISK-")

    # Verify run exists in DB
    run_rec = db.query(RiskRun).filter(RiskRun.run_id == res.run_id).first()
    assert run_rec is not None
    assert run_rec.simulation_count == 5000
    assert run_rec.metrics is not None
    assert run_rec.metrics.expected_contribution == res.expected_portfolio_contribution
    assert len(run_rec.assignment_metrics) == len(res.assignments)
    assert len(run_rec.drivers) == len(res.drivers)


# ── 9. 100% Offline Air-Gap Network Isolation ────────────────────────

def test_air_gap_zero_outbound_network(monkeypatch):
    """Verifies simulation executes 100% locally with zero network sockets."""
    original_socket = socket.socket

    def forbidden_socket(*args, **kwargs):
        raise RuntimeError("AIR-GAP VIOLATION: Outbound network call intercepted in Phase 9!")

    monkeypatch.setattr(socket, "socket", forbidden_socket)

    service = RiskService()
    cfg = service.get_default_risk_config()
    cfg.simulation_count = 1000

    assignments = [
        {
            "candidate_id": "CAND-AIRGAP-1",
            "vessel_id": 1,
            "vessel_name": "APJ JAD",
            "expected_revenue": 500000.0,
            "voyage_cost": 200000.0,
            "voyage_days": 12.0,
        }
    ]

    # Must complete without calling socket.socket
    res = service.engine.run_simulation(assignments, cfg)
    assert res.expected_portfolio_contribution > 0


# ── 10. API Endpoints Integration ────────────────────────────────────

def test_api_get_default_config(client):
    response = client.get("/v1/risk/config/defaults")
    assert response.status_code == 200
    data = response.json()
    assert data["simulation_count"] == 5000
    assert len(data["variables"]) >= 4
    assert len(data["correlations"]) >= 1


def test_api_simulate_endpoint(client):
    payload = {
        "optimization_run_id": "BASELINE_OPTIMAL",
        "simulation_count": 1000,
        "random_seed": 42,
    }
    response = client.post("/v1/risk/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["simulation_count"] == 1000
    assert "percentiles" in data
    assert "P50" in data["percentiles"]
    assert "var95_downside" in data
    assert "cvar95" in data
    assert len(data["assignments"]) > 0
    assert len(data["drivers"]) > 0
    assert len(data["distribution_histogram"]) > 0


def test_api_flip_demo_endpoint(client):
    response = client.get("/v1/risk/flip-demo")
    assert response.status_code == 200
    data = response.json()
    assert "CRITICAL RISK FLIP" in data["trade_off_summary"]
    assert data["plan_a_expected_contribution"] > data["plan_b_expected_contribution"]
    assert data["plan_a_loss_probability"] > data["plan_b_loss_probability"]


def test_api_list_runs_endpoint(client):
    response = client.get("/v1/risk/runs?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
