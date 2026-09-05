"""
VesselOptima — Pydantic Schemas: Forecast Intelligence
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class SeriesCatalogItem(BaseModel):
    target: str
    series_id: str
    name: str
    unit: str
    frequency: str
    provenance: str
    is_demo: bool
    description: str


class HistoricalPoint(BaseModel):
    date: str
    value: float


class ForecastPoint(BaseModel):
    date: str
    value: float
    lower_80: float
    upper_80: float
    lower_95: float
    upper_95: float


class ModelValidationMetrics(BaseModel):
    mae: float
    rmse: float
    smape: float
    directional_accuracy: float
    total_eval_points: int


class ModelInfo(BaseModel):
    selected_model: str
    model_version: str
    validation_method: str
    artifact_hash: Optional[str] = None


class ForecastResponse(BaseModel):
    target: str
    series_id: str
    series_name: str
    unit: str
    frequency: str
    provenance: str
    is_demo: bool
    historical_coverage: Dict[str, Any]
    horizon_days: int
    forecast_origin_date: str
    historical_points: List[HistoricalPoint]
    forecast_points: List[ForecastPoint]
    model_info: ModelInfo
    validation_metrics: ModelValidationMetrics
    candidate_metrics: Dict[str, Any]
    generated_at: str


class ForecastTrainRequest(BaseModel):
    series_id: str
    horizon_days: int = 30
    force: bool = False
