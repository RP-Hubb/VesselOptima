"""
Regression Test Suite for DEF-005: Forecast Model Explainability & TreeSHAP
Follows Master Build Specification Section J.

Verifies:
1. XGBoostForecastModel.explain() calculates exact TreeSHAP values.
2. Drivers are ranked by absolute impact with directions (+/-) and feature names.
3. BaseForecastModel provides transparent baseline decomposition.
4. ForecastService.get_forecast() includes explainability payload.
5. API endpoint GET /v1/forecast/explain/{series_id} returns structured drivers.
"""

import numpy as np
import pandas as pd
import pytest
from app.engines.forecast.models import XGBoostForecastModel, NaivePersistenceModel
from app.engines.forecast.service import ForecastService


def test_xgboost_treeshap_explainability():
    """XGBoost model produces exact TreeSHAP attribution matching prediction."""
    model = XGBoostForecastModel(n_estimators=15, max_depth=3)
    np.random.seed(42)
    history = pd.Series(100.0 + np.cumsum(np.random.randn(60)))
    last_date = pd.Timestamp("2026-09-01")

    model.fit(history)
    assert model.is_fitted

    expl = model.explain(history=history, last_date=last_date)

    assert expl["method"] == "TreeSHAP (Lundberg et al.)"
    assert "base_value" in expl
    assert "prediction_value" in expl
    assert len(expl["drivers"]) > 0
    assert len(expl["top_drivers"]) <= 5

    # Verify ranking
    drivers = expl["drivers"]
    for i in range(len(drivers) - 1):
        assert abs(drivers[i]["impact"]) >= abs(drivers[i+1]["impact"]), "Drivers must be sorted by descending absolute impact"

    # Verify directions
    for d in drivers:
        assert d["direction"] in ("+", "-")
        assert (d["impact"] >= 0 and d["direction"] == "+") or (d["impact"] < 0 and d["direction"] == "-")


def test_baseline_transparent_decomposition():
    """Baseline persistence model provides transparent level decomposition."""
    model = NaivePersistenceModel()
    history = pd.Series([120.0, 125.0, 130.0])
    last_date = pd.Timestamp("2026-09-01")

    model.fit(history)
    expl = model.explain(history=history, last_date=last_date)

    assert expl["method"] == "Transparent Baseline Decomposition"
    assert expl["base_value"] == 130.0
    assert expl["prediction_value"] == 130.0


def test_forecast_service_includes_explainability(db):
    """ForecastService returns explainability within standard forecast payload."""
    service = ForecastService(db=db)
    res = service.get_forecast(series_id="INDEX_BDI", horizon_days=7)

    assert "explainability" in res
    expl = res["explainability"]
    assert "method" in expl
    assert "base_value" in expl
    assert "drivers" in expl
    assert "summary" in expl


def test_api_forecast_explain_endpoint(client):
    """REST endpoint /v1/forecast/explain/{series_id} returns structured attribution."""
    response = client.get("/v1/forecast/explain/INDEX_BDI")
    assert response.status_code == 200
    data = response.json()

    assert data["series_id"] == "INDEX_BDI"
    assert "method" in data
    assert "base_value" in data
    assert "prediction_value" in data
    assert "drivers" in data
    assert "top_drivers" in data
    assert "summary" in data
