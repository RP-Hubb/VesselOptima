"""
VesselOptima — API Endpoints: Forecast Intelligence
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.engines.forecast.service import ForecastService
from app.schemas.forecast import (
    ForecastResponse,
    ForecastTrainRequest,
    SeriesCatalogItem,
)

router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.get("/series", response_model=List[SeriesCatalogItem])
def list_forecast_series(db: Session = Depends(get_db)):
    """
    Lists all supported time-series targets available for forecasting.
    Categorized into Market Indices, Route Freight Proxies, Bunker Prices, and Congestion.
    """
    service = ForecastService(db=db)
    return service.get_supported_series()


@router.get("/{target}/{series_id}", response_model=ForecastResponse)
def get_series_forecast(
    target: str,
    series_id: str,
    horizon: int = Query(default=30, description="Forecast horizon in days (7, 14, 30)"),
    db: Session = Depends(get_db),
):
    """
    Returns out-of-sample point forecast and empirical 80% and 95% prediction intervals
    for the specified series, alongside walk-forward validation evidence and provenance metadata.
    """
    if horizon not in (7, 14, 30):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported horizon: {horizon}. Only 7, 14, and 30 days are supported.",
        )

    service = ForecastService(db=db)
    try:
        res = service.get_forecast(series_id=series_id, horizon_days=horizon)
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecasting error: {e}")


@router.post("/train")
@router.post("/{target}/train")
def train_forecast_series(
    req: ForecastTrainRequest,
    db: Session = Depends(get_db),
):
    """
    Triggers expanding-window walk-forward validation and local artifact registration
    for a specific series.
    """
    service = ForecastService(db=db)
    try:
        metadata = service.train_and_register_series(
            series_id=req.series_id,
            horizon_days=req.horizon_days,
        )
        return {
            "status": "SUCCESS",
            "series_id": req.series_id,
            "selected_model": metadata["selected_model"],
            "metrics": metadata["selected_metrics"],
            "artifact_hash": metadata["artifact_hash"],
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training error: {e}")
