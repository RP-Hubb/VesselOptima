"""
VesselOptima — Walk-Forward Temporal Validation & Evaluation

Implements expanding-window walk-forward validation, comprehensive out-of-sample metrics
(MAE, RMSE, sMAPE, Directional Accuracy), and data-driven model selection.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.core.logging import get_logger
from app.engines.forecast.models import (
    BaseForecastModel,
    ETSModel,
    NaivePersistenceModel,
    SeasonalNaiveModel,
    XGBoostForecastModel,
)

logger = get_logger("engines.forecast.evaluation")


@dataclass
class ValidationMetrics:
    mae: float
    rmse: float
    smape: float
    directional_accuracy: float
    total_eval_points: int


@dataclass
class ModelEvaluationResult:
    model_name: str
    metrics: ValidationMetrics
    residuals: List[float]  # Out-of-sample residuals (actual - pred) for prediction intervals


def calculate_metrics(actuals: np.ndarray, predictions: np.ndarray, origin_value: float) -> ValidationMetrics:
    """
    Computes out-of-sample MAE, RMSE, sMAPE, and Directional Accuracy.
    All calculations strictly use out-of-sample validation data.
    """
    if len(actuals) == 0 or len(predictions) == 0:
        raise ValueError("Cannot calculate metrics on empty arrays.")

    act = np.asarray(actuals, dtype=np.float64)
    pred = np.asarray(predictions, dtype=np.float64)

    # 1. MAE
    mae = float(np.mean(np.abs(act - pred)))

    # 2. RMSE
    rmse = float(np.sqrt(np.mean((act - pred) ** 2)))

    # 3. sMAPE (Symmetric MAPE in %)
    denom = (np.abs(act) + np.abs(pred)) / 2.0
    denom = np.where(denom == 0, 1e-8, denom)
    smape = float(np.mean(np.abs(act - pred) / denom) * 100.0)

    # 4. Directional Accuracy (% of steps where predicted direction matched actual relative to origin)
    act_dir = np.sign(act - origin_value)
    pred_dir = np.sign(pred - origin_value)
    # Match if signs are identical, or if both are zero
    matches = (act_dir == pred_dir) | ((act_dir == 0) & (pred_dir == 0))
    da = float(np.mean(matches) * 100.0)

    return ValidationMetrics(
        mae=round(mae, 4),
        rmse=round(rmse, 4),
        smape=round(smape, 2),
        directional_accuracy=round(da, 2),
        total_eval_points=len(act),
    )


class WalkForwardEvaluator:
    """
    Expanding-window walk-forward evaluator.
    Strictly forbids future validation observations from leaking into training windows.
    """

    def __init__(self, n_folds: int = 3, horizon_days: int = 30):
        self.n_folds = n_folds
        self.horizon_days = horizon_days

    def evaluate_model(
        self,
        model_factory,
        df: pd.DataFrame,
    ) -> ModelEvaluationResult:
        """
        Executes expanding-window walk-forward validation for a given model factory.
        Returns aggregate metrics and out-of-sample residuals.
        """
        total_len = len(df)
        required_len = 120 + self.n_folds * self.horizon_days
        if total_len < required_len:
            raise ValueError(
                f"Insufficient data for {self.n_folds} folds of horizon {self.horizon_days}d. "
                f"Need at least {required_len} rows, got {total_len}."
            )

        all_actuals = []
        all_predictions = []
        all_origins = []
        all_residuals = []

        model_name = ""

        # Expanding window folds
        for fold in range(self.n_folds):
            # Split point for this fold
            val_start_idx = total_len - (self.n_folds - fold) * self.horizon_days
            val_end_idx = val_start_idx + self.horizon_days

            train_df = df.iloc[:val_start_idx].copy()
            val_df = df.iloc[val_start_idx:val_end_idx].copy()

            # Train on history up to val_start_idx
            model = model_factory()
            model_name = model.name
            model.fit(history=train_df["value"])

            # Forecast next horizon_days
            last_date = train_df["date"].iloc[-1]
            origin_val = float(train_df["value"].iloc[-1])

            preds = model.predict(
                horizon_days=self.horizon_days,
                last_date=last_date,
                history=train_df["value"],
            )

            actuals = val_df["value"].to_numpy(dtype=np.float64)

            all_actuals.extend(actuals)
            all_predictions.extend(preds)
            all_origins.extend([origin_val] * len(actuals))

            residuals = actuals - preds
            all_residuals.extend(residuals.tolist())

        # Compute aggregate validation metrics across all folds
        metrics = calculate_metrics(
            actuals=np.array(all_actuals),
            predictions=np.array(all_predictions),
            origin_value=float(np.mean(all_origins)),
        )

        return ModelEvaluationResult(
            model_name=model_name,
            metrics=metrics,
            residuals=all_residuals,
        )

    def select_best_model(
        self,
        df: pd.DataFrame,
    ) -> Tuple[BaseForecastModel, ModelEvaluationResult, Dict[str, ModelEvaluationResult]]:
        """
        Trains and compares all candidate models (Naive, Seasonal Naive, ETS, XGBoost)
        under identical temporal validation windows. Selects the model with lowest RMSE.
        """
        candidates = {
            "NaivePersistence": lambda: NaivePersistenceModel(),
            "SeasonalNaive_s7": lambda: SeasonalNaiveModel(season_length=7),
            "ExponentialSmoothing_ETS": lambda: ETSModel(seasonal_periods=7),
            "XGBoostRegressor": lambda: XGBoostForecastModel(n_estimators=100, max_depth=4),
        }

        results: Dict[str, ModelEvaluationResult] = {}
        for key, factory in candidates.items():
            logger.info(f"Evaluating candidate model: {key}")
            eval_res = self.evaluate_model(factory, df)
            results[key] = eval_res
            logger.info(
                f"  {key} -> RMSE: {eval_res.metrics.rmse}, MAE: {eval_res.metrics.mae}, "
                f"sMAPE: {eval_res.metrics.smape}%, DA: {eval_res.metrics.directional_accuracy}%"
            )

        # Selection criterion: lowest out-of-sample RMSE
        best_name = min(results.keys(), key=lambda k: results[k].metrics.rmse)
        best_result = results[best_name]

        logger.info(f"Selected best model: '{best_name}' with RMSE {best_result.metrics.rmse}")

        # Train final selected model on entire dataset
        final_model = candidates[best_name]()
        final_model.fit(history=df["value"])

        return final_model, best_result, results
