"""
VesselOptima — Comprehensive Forecast Engine Test Suite

Tests:
1. Data loading, chronological sorting, and frequency normalization.
2. Leakage prevention: strictly causal lag and rolling features.
3. Forecasting models: Naive, Seasonal Naive, ETS, XGBoost.
4. Walk-forward temporal validation and out-of-sample metrics.
5. Prediction intervals and structural invariance (lower <= forecast <= upper).
6. Local model artifact persistence, metadata, and SHA-256 manifests.
7. FastAPI forecast endpoints (/v1/forecast/series, /v1/forecast/{t}/{s}).
8. Offline isolation (zero external network calls during training & inference).
"""

import socket
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.engines.forecast.artifacts import ForecastArtifactService
from app.engines.forecast.data import ForecastDataService, SERIES_CATALOG
from app.engines.forecast.evaluation import (
    WalkForwardEvaluator,
    calculate_metrics,
)
from app.engines.forecast.features import ForecastFeatureService
from app.engines.forecast.models import (
    ETSModel,
    NaivePersistenceModel,
    SeasonalNaiveModel,
    XGBoostForecastModel,
)
from app.engines.forecast.service import ForecastService
from app.engines.forecast.uncertainty import ForecastUncertaintyService


@pytest.fixture()
def sample_series_df():
    """Generates a clean synthetic daily series for testing."""
    dates = pd.date_range(start="2025-01-01", periods=200, freq="D")
    values = 100.0 + np.sin(np.linspace(0, 4 * np.pi, 200)) * 15.0 + np.arange(200) * 0.1
    return pd.DataFrame({"date": dates, "value": values})


# ── 1. Data Service Tests ───────────────────────────────────────────────

def test_forecast_data_catalog():
    """Catalog contains Market Indices, Route Freight, Bunker, and Congestion series."""
    svc = ForecastDataService()
    catalog = svc.get_supported_series()
    assert len(catalog) >= 10

    series_ids = [s["series_id"] for s in catalog]
    assert "INDEX_BDI" in series_ids
    assert "FREIGHT_AU_HEDLAND_PARADIP_CAPE" in series_ids
    assert "BUNKER_VLSFO_SINGAPORE" in series_ids
    assert "CONGESTION_PORT_PARADIP" in series_ids


def test_forecast_data_loading_and_chronology():
    """Loaded series is strictly chronological with daily frequency."""
    svc = ForecastDataService()
    df, meta = svc.load_series("INDEX_BDI")
    assert len(df) > 900
    assert df["date"].is_monotonic_increasing
    assert meta.unit == "POINTS"
    assert meta.provenance == "SYNTHETIC"


def test_forecast_data_unknown_series():
    """Requesting an unknown series raises ValueError."""
    svc = ForecastDataService()
    with pytest.raises(ValueError) as excinfo:
        svc.load_series("NON_EXISTENT_SERIES")
    assert "unknown" in str(excinfo.value).lower()


# ── 2. Leakage Prevention Tests ─────────────────────────────────────────

def test_feature_engineering_strict_causality():
    """
    CRITICAL TEST: Verifies that lag and rolling features NEVER use future or current values.
    For any observation at row i, lag_1 must be row i-1, and rolling_mean must exclude row i.
    """
    svc = ForecastFeatureService(lags=[1, 2, 7], rolling_windows=[7])
    dates = pd.date_range(start="2025-01-01", periods=50, freq="D")
    # Strictly increasing sequence so values equal their row index
    values = np.arange(50, dtype=np.float64)
    df = pd.DataFrame({"date": dates, "value": values})

    X, y = svc.create_features(df)

    # After warm-up (7 days), row 0 in X corresponds to index 7 in df (value = 7)
    # y[0] should be 7
    assert y.iloc[0] == 7.0

    # lag_1 for row 0 must be 6.0 (value at t-1)
    assert X.iloc[0]["lag_1"] == 6.0
    # lag_2 for row 0 must be 5.0 (value at t-2)
    assert X.iloc[0]["lag_2"] == 5.0
    # lag_7 for row 0 must be 0.0 (value at t-7)
    assert X.iloc[0]["lag_7"] == 0.0

    # rolling_mean_7 at row 0 must be mean of [0, 1, 2, 3, 4, 5, 6] = 3.0 (strictly excludes current value 7!)
    assert X.iloc[0]["rolling_mean_7"] == 3.0

    # Future values (e.g. 8, 9, 10...) must NEVER appear anywhere in lag/rolling features of row 0
    lag_and_rolling_cols = [c for c in X.columns if "lag" in c or "rolling" in c]
    assert (X.iloc[0][lag_and_rolling_cols].values < 7.0).all()



# ── 3. Forecasting Models Tests ─────────────────────────────────────────

def test_naive_persistence_model(sample_series_df):
    """Naive persistence model forecasts the latest known value across all horizons."""
    history = sample_series_df["value"]
    model = NaivePersistenceModel()
    model.fit(history)

    last_val = history.iloc[-1]
    preds = model.predict(horizon_days=14, last_date=sample_series_df["date"].iloc[-1], history=history)

    assert len(preds) == 14
    assert np.all(preds == last_val)


def test_seasonal_naive_model(sample_series_df):
    """Seasonal naive model repeats the cyclical pattern of the last s steps."""
    history = sample_series_df["value"]
    s = 7
    model = SeasonalNaiveModel(season_length=s)
    model.fit(history)

    preds = model.predict(horizon_days=14, last_date=sample_series_df["date"].iloc[-1], history=history)
    assert len(preds) == 14
    # The first 7 predictions must match the second 7 predictions
    assert np.allclose(preds[:7], preds[7:])


def test_ets_model(sample_series_df):
    """ETS Holt-Winters model generates smooth predictions."""
    history = sample_series_df["value"]
    model = ETSModel(seasonal_periods=7)
    model.fit(history)

    preds = model.predict(horizon_days=30, last_date=sample_series_df["date"].iloc[-1], history=history)
    assert len(preds) == 30
    assert (preds >= 0).all()


def test_xgboost_model(sample_series_df):
    """XGBoost model fits causal features and generates multi-step predictions."""
    history = sample_series_df["value"]
    model = XGBoostForecastModel(n_estimators=30, max_depth=3)
    model.fit(history)

    preds = model.predict(horizon_days=30, last_date=sample_series_df["date"].iloc[-1], history=history)
    assert len(preds) == 30
    assert (preds >= 0).all()
    # Forecasts should not be flat
    assert np.std(preds) > 0.0


# ── 4. Walk-Forward Validation & Metrics Tests ──────────────────────────

def test_metrics_calculation():
    """Verifies MAE, RMSE, sMAPE, and Directional Accuracy formulas."""
    actuals = np.array([10.0, 12.0, 14.0])
    predictions = np.array([11.0, 11.0, 15.0])
    origin = 9.0

    metrics = calculate_metrics(actuals, predictions, origin_value=origin)
    # MAE = (|10-11| + |12-11| + |14-15|) / 3 = (1 + 1 + 1) / 3 = 1.0
    assert metrics.mae == 1.0
    # RMSE = sqrt((1 + 1 + 1) / 3) = 1.0
    assert metrics.rmse == 1.0
    assert metrics.smape > 0.0
    # Both actual and pred moved UP relative to origin 9.0 for all 3 points -> 100% DA
    assert metrics.directional_accuracy == 100.0


def test_walk_forward_evaluator_model_selection(sample_series_df):
    """Walk-forward evaluator compares all candidates and selects the lowest RMSE model."""
    evaluator = WalkForwardEvaluator(n_folds=2, horizon_days=14)
    best_model, best_eval, all_evals = evaluator.select_best_model(sample_series_df)

    assert best_model is not None
    assert best_eval.metrics.rmse > 0.0
    assert len(all_evals) == 4
    assert "NaivePersistence" in all_evals
    assert "XGBoostRegressor" in all_evals

    # Selected model must have the minimum RMSE among all candidates
    min_rmse = min(v.metrics.rmse for v in all_evals.values())
    assert best_eval.metrics.rmse == min_rmse


# ── 5. Uncertainty & Prediction Interval Tests ─────────────────────────

def test_prediction_interval_structural_invariance():
    """
    CRITICAL TEST: Prediction interval must obey:
    lower_bound <= point_forecast <= upper_bound, and lower_bound >= 0.
    """
    service = ForecastUncertaintyService()
    point_forecasts = np.array([20.0, 22.5, 19.0, 25.0])
    residuals = [-1.5, 2.0, -0.8, 1.2, -2.5, 0.5, 1.8, -1.0, 0.2, -0.4, 1.1]

    lower_80, upper_80 = service.compute_prediction_intervals(
        point_forecasts=point_forecasts,
        validation_residuals=residuals,
        coverage=0.80,
    )
    lower_95, upper_95 = service.compute_prediction_intervals(
        point_forecasts=point_forecasts,
        validation_residuals=residuals,
        coverage=0.95,
    )

    for i in range(len(point_forecasts)):
        pt = point_forecasts[i]
        assert lower_80[i] <= pt <= upper_80[i]
        assert lower_95[i] <= pt <= upper_95[i]
        assert lower_80[i] >= 0.0
        assert lower_95[i] >= 0.0
        # 95% interval must be at least as wide as 80% interval
        assert (upper_95[i] - lower_95[i]) >= (upper_80[i] - lower_80[i])


# ── 6. Artifact Registry Tests ──────────────────────────────────────────

def test_artifact_persistence_and_loading(tmp_path, sample_series_df):
    """Model weights, metadata, metrics, and manifests save and load deterministically."""
    artifact_svc = ForecastArtifactService(base_dir=tmp_path)

    model = NaivePersistenceModel().fit(sample_series_df["value"])
    evaluator = WalkForwardEvaluator(n_folds=2, horizon_days=7)
    best_eval = evaluator.evaluate_model(lambda: NaivePersistenceModel(), sample_series_df)

    metadata = artifact_svc.save_artifact(
        target="market_index",
        series_id="TEST_SERIES",
        model=model,
        best_eval=best_eval,
        all_evals={"NaivePersistence": best_eval},
        data_info={"unit": "POINTS", "rows": len(sample_series_df)},
        model_version="v1.0.0",
    )

    assert metadata["artifact_hash"] is not None

    loaded_model, loaded_meta = artifact_svc.load_artifact(
        target="market_index",
        series_id="TEST_SERIES",
        model_version="v1.0.0",
    )
    assert loaded_model.name == "NaivePersistence"
    assert loaded_meta["target"] == "market_index"

    registry = artifact_svc.list_registry()
    assert len(registry) == 1
    assert registry[0]["series_id"] == "TEST_SERIES"


# ── 7. Master Forecast Service & API Tests ──────────────────────────────

def test_forecast_service_end_to_end():
    """ForecastService produces complete forecast with history and bounds."""
    service = ForecastService()
    res = service.get_forecast("INDEX_BDI", horizon_days=14)

    assert res["target"] == "market_index"
    assert res["series_id"] == "INDEX_BDI"
    assert res["horizon_days"] == 14
    assert len(res["forecast_points"]) == 14
    assert len(res["historical_points"]) > 0

    first_pt = res["forecast_points"][0]
    assert "value" in first_pt
    assert "lower_80" in first_pt
    assert "upper_80" in first_pt
    assert first_pt["lower_80"] <= first_pt["value"] <= first_pt["upper_80"]

    assert res["model_info"]["selected_model"] is not None
    assert "rmse" in res["validation_metrics"]


def test_forecast_api_endpoints(client):
    """FastAPI routes /v1/forecast/series and /v1/forecast/{target}/{series_id}."""
    # 1. Catalog
    resp1 = client.get("/v1/forecast/series")
    assert resp1.status_code == 200
    series_list = resp1.json()
    assert len(series_list) >= 10

    # 2. Get Forecast for Baltic Dry Index (30 days)
    resp2 = client.get("/v1/forecast/market_index/INDEX_BDI?horizon=30")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["series_id"] == "INDEX_BDI"
    assert data2["horizon_days"] == 30
    assert len(data2["forecast_points"]) == 30

    # 3. Invalid horizon returns 400
    resp3 = client.get("/v1/forecast/market_index/INDEX_BDI?horizon=45")
    assert resp3.status_code == 400

    # 4. Unknown series returns 404
    resp4 = client.get("/v1/forecast/market_index/NON_EXISTENT_SERIES?horizon=14")
    assert resp4.status_code == 404


# ── 8. Air-Gapped Network Isolation Test ────────────────────────────────

def test_forecast_engine_zero_network_calls(client, monkeypatch):
    """
    Verifies that model training, inference, and API response generation
    execute 100% offline with zero outbound network calls.
    """
    original_connect = socket.socket.connect

    def blocked_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) and address else str(address)
        if host not in ("127.0.0.1", "localhost", "::1", "testserver"):
            raise ConnectionRefusedError(
                f"Outbound network connectivity to {host} is forbidden in OFFLINE_DEMO mode!"
            )
        return original_connect(self, address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)

    # Calling forecast endpoint under blocked network
    resp = client.get("/v1/forecast/route_freight/FREIGHT_AU_HEDLAND_PARADIP_CAPE?horizon=14")
    assert resp.status_code == 200
    data = resp.json()
    assert data["provenance"] == "PROXY"
    assert len(data["forecast_points"]) == 14


# ── 9. Determinism Test ────────────────────────────────────────────────

def test_forecast_training_determinism(sample_series_df):
    """
    Verifies that identical seed and configuration produces byte/numerical
    reproducible metrics and predictions.
    """
    evaluator1 = WalkForwardEvaluator(n_folds=2, horizon_days=7)
    evaluator2 = WalkForwardEvaluator(n_folds=2, horizon_days=7)

    eval1 = evaluator1.evaluate_model(lambda: XGBoostForecastModel(random_state=42), sample_series_df)
    eval2 = evaluator2.evaluate_model(lambda: XGBoostForecastModel(random_state=42), sample_series_df)

    assert eval1.metrics.rmse == eval2.metrics.rmse
    assert eval1.metrics.mae == eval2.metrics.mae
    assert eval1.metrics.smape == eval2.metrics.smape
    assert eval1.residuals == eval2.residuals

    # Direct model inference determinism
    m1 = XGBoostForecastModel(random_state=42).fit(sample_series_df["value"])
    m2 = XGBoostForecastModel(random_state=42).fit(sample_series_df["value"])
    p1 = m1.predict(14, sample_series_df["date"].iloc[-1], sample_series_df["value"])
    p2 = m2.predict(14, sample_series_df["date"].iloc[-1], sample_series_df["value"])
    assert np.allclose(p1, p2)


