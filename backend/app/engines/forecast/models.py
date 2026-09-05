"""
VesselOptima — Forecasting Models Interface & Implementations

Includes:
- Baseline 1: Naive Persistence Model (y_{t+h} = y_t)
- Baseline 2: Seasonal Naive Model (y_{t+h} = y_{t+h-s})
- Candidate Statistical: Exponential Smoothing (ETS / Holt-Winters)
- Candidate Machine Learning: XGBoost Regressor with recursive multi-step forecasting
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from app.core.logging import get_logger
from app.engines.forecast.features import ForecastFeatureService

logger = get_logger("engines.forecast.models")


class BaseForecastModel(ABC):
    """Abstract base contract for all forecasting models."""

    def __init__(self, name: str):
        self.name = name
        self.is_fitted = False

    @abstractmethod
    def fit(
        self,
        history: pd.Series,
        X: Optional[pd.DataFrame] = None,
        y: Optional[pd.Series] = None,
    ) -> BaseForecastModel:
        """Fit model using historical values and optional tabular features."""
        pass

    @abstractmethod
    def predict(
        self,
        horizon_days: int,
        last_date: pd.Timestamp,
        history: pd.Series,
    ) -> np.ndarray:
        """Generate out-of-sample point forecast for horizon_days."""
        pass


class NaivePersistenceModel(BaseForecastModel):
    """
    Baseline 1: Persistence / Naive Forecast.
    y_{t+h} = y_t (latest known value carried forward).
    """

    def __init__(self):
        super().__init__(name="NaivePersistence")
        self.last_value: Optional[float] = None

    def fit(
        self,
        history: pd.Series,
        X: Optional[pd.DataFrame] = None,
        y: Optional[pd.Series] = None,
    ) -> NaivePersistenceModel:
        if len(history) == 0:
            raise ValueError("History series cannot be empty.")
        self.last_value = float(history.iloc[-1])
        self.is_fitted = True
        return self

    def predict(
        self,
        horizon_days: int,
        last_date: pd.Timestamp,
        history: pd.Series,
    ) -> np.ndarray:
        last_val = float(history.iloc[-1]) if len(history) > 0 else (self.last_value or 0.0)
        return np.full(shape=horizon_days, fill_value=last_val, dtype=np.float64)


class SeasonalNaiveModel(BaseForecastModel):
    """
    Baseline 2: Seasonal Naive Forecast.
    Repeats observations from the previous seasonal cycle (default s=7 for daily data).
    """

    def __init__(self, season_length: int = 7):
        super().__init__(name=f"SeasonalNaive_s{season_length}")
        self.season_length = season_length
        self.last_season_values: Optional[np.ndarray] = None

    def fit(
        self,
        history: pd.Series,
        X: Optional[pd.DataFrame] = None,
        y: Optional[pd.Series] = None,
    ) -> SeasonalNaiveModel:
        if len(history) < self.season_length:
            raise ValueError(
                f"History length ({len(history)}) must be >= season_length ({self.season_length})"
            )
        self.last_season_values = history.iloc[-self.season_length:].to_numpy(dtype=np.float64)
        self.is_fitted = True
        return self

    def predict(
        self,
        horizon_days: int,
        last_date: pd.Timestamp,
        history: pd.Series,
    ) -> np.ndarray:
        season_vals = (
            history.iloc[-self.season_length:].to_numpy(dtype=np.float64)
            if len(history) >= self.season_length
            else self.last_season_values
        )
        forecast = [season_vals[i % self.season_length] for i in range(horizon_days)]
        return np.array(forecast, dtype=np.float64)


class ETSModel(BaseForecastModel):
    """
    Candidate Statistical Model: Exponential Smoothing (Holt-Winters / ETS).
    Applies additive trend with damping for stable multi-step forecasting.
    """

    def __init__(self, seasonal_periods: Optional[int] = 7):
        super().__init__(name="ExponentialSmoothing_ETS")
        self.seasonal_periods = seasonal_periods
        self.fitted_model: Any = None

    def fit(
        self,
        history: pd.Series,
        X: Optional[pd.DataFrame] = None,
        y: Optional[pd.Series] = None,
    ) -> ETSModel:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        series_vals = history.to_numpy(dtype=np.float64)
        try:
            # Try Holt-Winters with additive trend and damping
            model = ExponentialSmoothing(
                series_vals,
                trend="add",
                damped_trend=True,
                initialization_method="estimated",
            )
            self.fitted_model = model.fit()
        except Exception as e:
            logger.warning(f"ETS fitting warning, falling back to simple Holt model: {e}")
            model = ExponentialSmoothing(
                series_vals,
                trend="add",
                initialization_method="heuristic",
            )
            self.fitted_model = model.fit()


        self.is_fitted = True
        return self

    def predict(
        self,
        horizon_days: int,
        last_date: pd.Timestamp,
        history: pd.Series,
    ) -> np.ndarray:
        if not self.is_fitted or self.fitted_model is None:
            raise RuntimeError("Model must be fitted before predict.")
        preds = self.fitted_model.forecast(horizon_days)
        # Ensure non-negative bounds
        return np.maximum(0.0, np.array(preds, dtype=np.float64))


class XGBoostForecastModel(BaseForecastModel):
    """
    Candidate Machine Learning Model: XGBoost Regressor.
    Trains on strictly causal lag/rolling/calendar features and generates
    recursive multi-step forecasts.
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 4,
        learning_rate: float = 0.05,
        random_state: int = 20260905,
    ):
        super().__init__(name="XGBoostRegressor")
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.random_state = random_state
        self.feature_service = ForecastFeatureService()
        self.regressor = XGBRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            random_state=self.random_state,
            n_jobs=1,
            verbosity=0,
        )

    def fit(
        self,
        history: pd.Series,
        X: Optional[pd.DataFrame] = None,
        y: Optional[pd.Series] = None,
    ) -> XGBoostForecastModel:
        if X is None or y is None:
            df = pd.DataFrame({
                "date": pd.date_range(start="2024-01-01", periods=len(history), freq="D"),
                "value": history.values,
            })
            X, y = self.feature_service.create_features(df)

        self.regressor.fit(X, y)
        self.is_fitted = True
        return self

    def predict(
        self,
        horizon_days: int,
        last_date: pd.Timestamp,
        history: pd.Series,
    ) -> np.ndarray:
        """
        Recursive multi-step forecasting: predicts t+1, appends to rolling history,
        re-extracts causal features, predicts t+2, and so on up to horizon_days.
        """
        if not self.is_fitted:
            raise RuntimeError("XGBoost model must be fitted before predict.")

        curr_history = list(history.values)
        predictions = []

        for step in range(1, horizon_days + 1):
            next_date = last_date + timedelta(days=step)
            # Extract 1-row feature vector from current history (causally closed)
            feature_row = self.feature_service.extract_inference_row(
                historical_series=pd.Series(curr_history),
                target_date=next_date,
            )
            pred_val = float(self.regressor.predict(feature_row)[0])
            # Ensure non-negative bounds for physical commodity and rate indices
            pred_val = max(0.0, pred_val)
            predictions.append(pred_val)
            curr_history.append(pred_val)

        return np.array(predictions, dtype=np.float64)
