"""
Regression test for Finding 5: Forecast Intervals use Real Residuals, Not Synthetic Random Numbers.
"""

from unittest.mock import patch
import pytest
import numpy as np

from app.engines.forecast.service import ForecastService


def test_forecast_uses_real_residuals_not_random_normal():
    """Verify get_forecast uses real residuals and never calls np.random.normal."""
    service = ForecastService()

    with patch("numpy.random.normal", side_effect=AssertionError("np.random.normal was called!")):
        result = service.get_forecast(
            series_id="INDEX_BDI",
            horizon_days=14,
        )

    assert "forecast_points" in result
    points = result["forecast_points"]
    assert len(points) == 14

    for pt in points:
        assert pt["lower_95"] <= pt["lower_80"] <= pt["value"] <= pt["upper_80"] <= pt["upper_95"]
        assert pt["lower_95"] >= 0.0


def test_forecast_fails_closed_when_residuals_missing(tmp_path):
    """Verify that an artifact missing residuals raises ValueError instead of synthesizing data."""
    import json
    from app.engines.forecast.artifacts import ForecastArtifactService

    artifact_svc = ForecastArtifactService(base_dir=tmp_path)
    service = ForecastService(artifact_service=artifact_svc)
    # Train and register first so full artifact exists
    service.train_and_register_series("INDEX_BDI")

    # Now tamper metrics.json to strip residuals
    metrics_path = tmp_path / "market_index" / "INDEX_BDI" / "v1.0.0" / "metrics.json"
    with open(metrics_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["residuals"] = []
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    # Needs to fail closed with ValueError
    with pytest.raises(ValueError, match="missing authentic empirical residuals"):
        service.get_forecast("INDEX_BDI", horizon_days=7)
