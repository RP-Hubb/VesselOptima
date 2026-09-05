"""
VesselOptima — Causal Time-Series Feature Engineering

Generates strictly causal lag, rolling, and calendar features.
Guarantees NO future-derived information or look-ahead leakage.
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pandas as pd


class ForecastFeatureService:
    """
    Causal feature extractor for time-series forecasting.
    All features computed for index t depend strictly on observations at t-1, t-2, ...
    """

    DEFAULT_LAGS = [1, 2, 3, 7, 14, 30]
    DEFAULT_ROLLING_WINDOWS = [7, 14, 30]

    def __init__(
        self,
        lags: List[int] = None,
        rolling_windows: List[int] = None,
    ):
        self.lags = lags or self.DEFAULT_LAGS
        self.rolling_windows = rolling_windows or self.DEFAULT_ROLLING_WINDOWS

    def create_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Transforms a DataFrame with ['date', 'value'] into causal features X and target y.
        Rows with NaN from initial lagging/rolling windows are dropped cleanly.
        """
        if "date" not in df.columns or "value" not in df.columns:
            raise ValueError("Input DataFrame must contain 'date' and 'value' columns.")

        data = df.copy().sort_values(by="date").reset_index(drop=True)

        feature_df = pd.DataFrame(index=data.index)
        feature_df["date"] = data["date"]

        # 1. Causal Lags (Strictly t-1, t-2, ...)
        # shift(1) means observation at t-1 is used to predict observation at t
        for lag in self.lags:
            feature_df[f"lag_{lag}"] = data["value"].shift(lag)

        # 2. Causal Rolling Statistics
        # We shift by 1 first so the current observation is excluded from the rolling window!
        shifted_val = data["value"].shift(1)
        for w in self.rolling_windows:
            feature_df[f"rolling_mean_{w}"] = shifted_val.rolling(window=w).mean()
            feature_df[f"rolling_std_{w}"] = shifted_val.rolling(window=w).std()
            feature_df[f"rolling_min_{w}"] = shifted_val.rolling(window=w).min()
            feature_df[f"rolling_max_{w}"] = shifted_val.rolling(window=w).max()

        # 3. Calendar Features
        feature_df["dayofweek"] = data["date"].dt.dayofweek
        feature_df["month"] = data["date"].dt.month
        feature_df["dayofyear"] = data["date"].dt.dayofyear

        # Target variable is current value at t
        target = data["value"].copy()

        # Drop warm-up rows where lag features are NaN
        max_lookback = max(max(self.lags), max(self.rolling_windows))
        valid_mask = feature_df.index >= max_lookback

        X = feature_df.loc[valid_mask].drop(columns=["date"]).reset_index(drop=True)
        y = target.loc[valid_mask].reset_index(drop=True)

        return X, y

    def extract_inference_row(self, historical_series: pd.Series, target_date: pd.Timestamp) -> pd.DataFrame:
        """
        Extracts a single 1-row feature DataFrame representing features as of target_date,
        using ONLY values from historical_series.
        """
        hist = historical_series.values
        if len(hist) < max(max(self.lags), max(self.rolling_windows)):
            raise ValueError("Insufficient history to construct lag/rolling features.")

        row = {}
        # Lags
        for lag in self.lags:
            row[f"lag_{lag}"] = float(hist[-lag])

        # Rolling stats (computed over historical window up to the last known point)
        for w in self.rolling_windows:
            window_slice = hist[-w:]
            row[f"rolling_mean_{w}"] = float(np.mean(window_slice))
            row[f"rolling_std_{w}"] = float(np.std(window_slice, ddof=1)) if len(window_slice) > 1 else 0.0
            row[f"rolling_min_{w}"] = float(np.min(window_slice))
            row[f"rolling_max_{w}"] = float(np.max(window_slice))

        # Calendar
        row["dayofweek"] = int(target_date.dayofweek)
        row["month"] = int(target_date.month)
        row["dayofyear"] = int(target_date.dayofyear)

        return pd.DataFrame([row])
