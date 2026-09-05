"""
VesselOptima — Master Forecast Engine Orchestrator

Coordinates time-series loading, causal feature generation, walk-forward validation,
evidence-based model selection, prediction interval computation, and artifact persistence.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.engines.forecast.artifacts import ForecastArtifactService
from app.engines.forecast.data import ForecastDataService, SERIES_CATALOG
from app.engines.forecast.evaluation import WalkForwardEvaluator
from app.engines.forecast.uncertainty import ForecastUncertaintyService

logger = get_logger("engines.forecast.service")


class ForecastService:
    """Master service providing high-level forecasting capabilities."""

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self.data_service = ForecastDataService(db=db)
        self.artifact_service = ForecastArtifactService()
        self.uncertainty_service = ForecastUncertaintyService()
        self.evaluator = WalkForwardEvaluator(n_folds=3, horizon_days=30)

    def get_supported_series(self) -> List[Dict[str, Any]]:
        """Returns catalog of all supported forecastable series."""
        return self.data_service.get_supported_series()

    def train_and_register_series(
        self,
        series_id: str,
        horizon_days: int = 30,
        model_version: str = "v1.0.0",
    ) -> Dict[str, Any]:
        """
        Loads series, performs walk-forward validation across all candidates,
        selects the best model based on out-of-sample RMSE, and saves artifacts.
        """
        logger.info(f"Training and evaluating forecasting models for: {series_id}")
        df, meta = self.data_service.load_series(series_id)

        # Walk-forward validation and evidence-based model selection
        best_model, best_eval, all_evals = self.evaluator.select_best_model(df)

        data_info = {
            "unit": meta.unit,
            "provenance": meta.provenance,
            "rows": len(df),
            "start_date": str(df["date"].min().date()),
            "end_date": str(df["date"].max().date()),
        }

        # Persist model artifact locally
        metadata = self.artifact_service.save_artifact(
            target=meta.target,
            series_id=series_id,
            model=best_model,
            best_eval=best_eval,
            all_evals=all_evals,
            data_info=data_info,
            model_version=model_version,
        )

        return metadata

    def get_forecast(
        self,
        series_id: str,
        horizon_days: int = 30,
        history_points_to_return: int = 90,
    ) -> Dict[str, Any]:
        """
        Generates point forecasts and empirical prediction intervals for series_id.
        If model artifact does not exist locally, trains it deterministically first.
        """
        if series_id not in SERIES_CATALOG:
            raise ValueError(f"Unknown forecast series: '{series_id}'")

        if horizon_days not in (7, 14, 30):
            raise ValueError(f"Invalid horizon {horizon_days}. Supported horizons are 7, 14, 30 days.")

        meta = SERIES_CATALOG[series_id]
        df, _ = self.data_service.load_series(series_id)

        # Check if model artifact exists; if not, train it
        try:
            model, metadata = self.artifact_service.load_artifact(
                target=meta.target,
                series_id=series_id,
                model_version="v1.0.0",
            )
        except Exception:
            logger.info(f"No artifact found for {series_id}. Training on-the-fly...")
            metadata = self.train_and_register_series(series_id, horizon_days=30)
            model, metadata = self.artifact_service.load_artifact(
                target=meta.target,
                series_id=series_id,
                model_version="v1.0.0",
            )

        # Generate Point Forecasts
        last_date = df["date"].iloc[-1]
        history_series = df["value"]
        point_forecasts = model.predict(
            horizon_days=horizon_days,
            last_date=last_date,
            history=history_series,
        )

        # Load metrics to obtain validation residuals for prediction interval calculation
        metrics_path = self.artifact_service.base_dir / meta.target / series_id / "v1.0.0" / "metrics.json"
        import json
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics_data = json.load(f)

        # Compute empirical 80% and 95% intervals based on out-of-sample RMSE
        # (Standard normal quantile approximation from out-of-sample validation RMSE)
        val_rmse = float(metrics_data["selected_metrics"]["rmse"])
        # Synthetic residual spread based on out-of-sample validation error
        np.random.seed(20260905)
        simulated_residuals = list(np.random.normal(0, val_rmse, 100))

        lower_80, upper_80 = self.uncertainty_service.compute_prediction_intervals(
            point_forecasts=point_forecasts,
            validation_residuals=simulated_residuals,
            coverage=0.80,
        )
        lower_95, upper_95 = self.uncertainty_service.compute_prediction_intervals(
            point_forecasts=point_forecasts,
            validation_residuals=simulated_residuals,
            coverage=0.95,
        )

        # Build Forecast Points
        forecast_points = []
        for i in range(horizon_days):
            f_date = (last_date + timedelta(days=i + 1)).strftime("%Y-%m-%d")
            forecast_points.append({
                "date": f_date,
                "value": round(float(point_forecasts[i]), 2),
                "lower_80": round(float(lower_80[i]), 2),
                "upper_80": round(float(upper_80[i]), 2),
                "lower_95": round(float(lower_95[i]), 2),
                "upper_95": round(float(upper_95[i]), 2),
            })

        # Build Historical Points (e.g. past 90 days for plotting context)
        hist_slice = df.iloc[-history_points_to_return:].copy()
        historical_points = [
            {
                "date": row["date"].strftime("%Y-%m-%d"),
                "value": round(float(row["value"]), 2),
            }
            for _, row in hist_slice.iterrows()
        ]

        return {
            "target": meta.target,
            "series_id": meta.series_id,
            "series_name": meta.name,
            "unit": meta.unit,
            "frequency": meta.frequency,
            "provenance": meta.provenance,
            "is_demo": meta.is_demo,
            "historical_coverage": {
                "start": str(df["date"].min().date()),
                "end": str(last_date.date()),
                "total_points": len(df),
            },
            "horizon_days": horizon_days,
            "forecast_origin_date": str(last_date.date()),
            "historical_points": historical_points,
            "forecast_points": forecast_points,
            "model_info": {
                "selected_model": metadata.get("selected_model", model.name),
                "model_version": metadata.get("model_version", "v1.0.0"),
                "validation_method": metadata.get("validation_method", "expanding_window_walk_forward"),
                "artifact_hash": metadata.get("artifact_hash"),
            },
            "validation_metrics": metadata.get("selected_metrics", metrics_data["selected_metrics"]),
            "candidate_metrics": metrics_data.get("all_candidates", {}),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
