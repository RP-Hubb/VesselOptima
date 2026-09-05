"""
VesselOptima — Procurement Forecast Signal Integration
Follows Section 7 of the Phase 5 Specification.

Consumes Phase 3 ForecastService outputs without duplicating forecasting logic.
Derives evidence-backed trajectory signals and uncertainty indicators.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.engines.forecast.service import ForecastService

logger = get_logger("engines.procurement.forecast_signal")

# Route/commodity to forecast series mapping
ROUTE_SERIES_MAP = {
    ("Port Hedland", "Dhamra"): "FREIGHT_AU_HEDLAND_PARADIP_CAPE",
    ("Port Hedland", "Paradip"): "FREIGHT_AU_HEDLAND_PARADIP_CAPE",
    ("Newcastle", "Krishnapatnam"): "FREIGHT_AU_NEWCASTLE_PARADIP_PANAMAX",
    ("Newcastle", "Paradip"): "FREIGHT_AU_NEWCASTLE_PARADIP_PANAMAX",
    ("Samarinda", "Paradip"): "FREIGHT_ID_SAMARINDA_PARADIP_SUPRA",
    ("Samarinda", "Ennore"): "FREIGHT_ID_SAMARINDA_PARADIP_SUPRA",
    ("Taboneo", "Ennore"): "FREIGHT_ID_SAMARINDA_PARADIP_SUPRA",
    ("Richards Bay", "Paradip"): "FREIGHT_ZA_RICHARDSBAY_PARADIP_PANAMAX",
}

CLASS_INDEX_MAP = {
    "Capesize": "INDEX_BCI",
    "Panamax": "INDEX_BPI",
    "Supramax": "INDEX_BSI",
    "Handysize": "INDEX_BHSI",
}


def resolve_forecast_series(
    origin_name: Optional[str] = None,
    destination_name: Optional[str] = None,
    vessel_class: Optional[str] = None,
) -> str:
    """Deterministically identifies the best matching forecast series."""
    if origin_name and destination_name:
        for (orig, dest), series_id in ROUTE_SERIES_MAP.items():
            if orig.lower() in origin_name.lower() and dest.lower() in destination_name.lower():
                return series_id

    if vessel_class and vessel_class in CLASS_INDEX_MAP:
        return CLASS_INDEX_MAP[vessel_class]

    return "INDEX_BDI"


class ProcurementForecastSignalService:
    """Consumes Phase 3 forecast outputs and derives procurement timing signals."""

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self.forecast_service = ForecastService(db=db)

    def get_procurement_forecast_signal(
        self,
        series_id: str,
        horizon_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Retrieves forecast and calculates trajectory slope and uncertainty metrics.
        """
        try:
            forecast_data = self.forecast_service.get_forecast(
                series_id=series_id,
                horizon_days=horizon_days,
            )
        except Exception as e:
            logger.warning(f"Could not load forecast for {series_id}: {e}")
            return {
                "has_forecast": False,
                "series_id": series_id,
                "error": str(e),
                "signal": "INSUFFICIENT_FORECAST_EVIDENCE",
                "trajectory": "UNKNOWN",
                "uncertainty_level": "UNKNOWN",
                "point_estimate": None,
                "lower_95": None,
                "upper_95": None,
                "uncertainty_spread_pct": None,
                "model_name": None,
                "provenance": {"data_type": "UNAVAILABLE"},
            }

        points = forecast_data["forecast_points"]
        if not points:
            return {
                "has_forecast": False,
                "series_id": series_id,
                "signal": "INSUFFICIENT_FORECAST_EVIDENCE",
                "trajectory": "UNKNOWN",
                "uncertainty_level": "UNKNOWN",
                "point_estimate": None,
                "lower_95": None,
                "upper_95": None,
                "uncertainty_spread_pct": None,
                "model_name": None,
                "provenance": {"data_type": "UNAVAILABLE"},
            }

        start_val = points[0]["value"]
        end_val = points[-1]["value"]
        pct_change = ((end_val - start_val) / start_val) * 100.0 if start_val != 0 else 0.0

        # Trajectory classification: +/- 2.0% threshold
        if pct_change > 2.0:
            trajectory = "FORECAST_INCREASING"
        elif pct_change < -2.0:
            trajectory = "FORECAST_DECREASING"
        else:
            trajectory = "FORECAST_STABLE"

        # Uncertainty assessment at horizon: spread between upper_95 and lower_95 relative to point estimate
        mid_idx = len(points) // 2
        ref_point = points[mid_idx]
        spread = ref_point["upper_95"] - ref_point["lower_95"]
        spread_pct = (spread / ref_point["value"]) * 100.0 if ref_point["value"] > 0 else 0.0

        uncertainty_level = "HIGH" if spread_pct > 40.0 else "MODERATE" if spread_pct > 20.0 else "LOW"

        return {
            "has_forecast": True,
            "series_id": series_id,
            "series_name": forecast_data.get("series_name", series_id),
            "unit": forecast_data.get("unit", "USD_PER_MT"),
            "trajectory": trajectory,
            "trajectory_change_pct": round(pct_change, 2),
            "uncertainty_level": uncertainty_level,
            "uncertainty_spread_pct": round(spread_pct, 1),
            "point_estimate": round(ref_point["value"], 2),
            "lower_95": round(ref_point["lower_95"], 2),
            "upper_95": round(ref_point["upper_95"], 2),
            "model_name": forecast_data.get("model_info", {}).get("selected_model", "WalkForwardModel"),
            "model_version": forecast_data.get("model_info", {}).get("model_version", "v1.0.0"),
            "provenance": {
                "package_id": "demo-v1",
                "data_type": forecast_data.get("provenance", "PROXY"),
                "is_demo": forecast_data.get("is_demo", True),
            },
        }
