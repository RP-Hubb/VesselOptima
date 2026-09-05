"""
VesselOptima — Forecast Data Service

Extracts, cleans, validates, and prepares time-series datasets for forecasting.
Preserves provenance and chronological integrity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.domain import MarketObservation

logger = get_logger("engines.forecast.data")


@dataclass
class SeriesMetadata:
    target: str
    series_id: str
    name: str
    unit: str
    frequency: str
    provenance: str
    is_demo: bool
    description: str


# Catalog of supported forecast series
SERIES_CATALOG: Dict[str, SeriesMetadata] = {
    # Market Indices
    "INDEX_BDI": SeriesMetadata(
        target="market_index",
        series_id="INDEX_BDI",
        name="Baltic Dry Index (BDI)",
        unit="POINTS",
        frequency="DAILY",
        provenance="SYNTHETIC",
        is_demo=True,
        description="Synthetic Baltic Dry Index daily benchmark composite.",
    ),
    "INDEX_BCI": SeriesMetadata(
        target="market_index",
        series_id="INDEX_BCI",
        name="Baltic Capesize Index (BCI)",
        unit="POINTS",
        frequency="DAILY",
        provenance="SYNTHETIC",
        is_demo=True,
        description="Synthetic Baltic Capesize Index daily rate indicator.",
    ),
    "INDEX_BPI": SeriesMetadata(
        target="market_index",
        series_id="INDEX_BPI",
        name="Baltic Panamax Index (BPI)",
        unit="POINTS",
        frequency="DAILY",
        provenance="SYNTHETIC",
        is_demo=True,
        description="Synthetic Baltic Panamax Index daily rate indicator.",
    ),
    "INDEX_BSI": SeriesMetadata(
        target="market_index",
        series_id="INDEX_BSI",
        name="Baltic Supramax Index (BSI)",
        unit="POINTS",
        frequency="DAILY",
        provenance="SYNTHETIC",
        is_demo=True,
        description="Synthetic Baltic Supramax Index daily rate indicator.",
    ),
    "INDEX_BHSI": SeriesMetadata(
        target="market_index",
        series_id="INDEX_BHSI",
        name="Baltic Handysize Index (BHSI)",
        unit="POINTS",
        frequency="DAILY",
        provenance="SYNTHETIC",
        is_demo=True,
        description="Synthetic Baltic Handysize Index daily rate indicator.",
    ),
    # Route Freight Proxies
    "FREIGHT_AU_HEDLAND_PARADIP_CAPE": SeriesMetadata(
        target="route_freight",
        series_id="FREIGHT_AU_HEDLAND_PARADIP_CAPE",
        name="Port Hedland to Paradip (Capesize)",
        unit="USD_PER_MT",
        frequency="DAILY",
        provenance="PROXY",
        is_demo=True,
        description="Synthetic route freight rate proxy for iron ore trade.",
    ),
    "FREIGHT_AU_NEWCASTLE_PARADIP_PANAMAX": SeriesMetadata(
        target="route_freight",
        series_id="FREIGHT_AU_NEWCASTLE_PARADIP_PANAMAX",
        name="Newcastle to Paradip (Panamax)",
        unit="USD_PER_MT",
        frequency="DAILY",
        provenance="PROXY",
        is_demo=True,
        description="Synthetic route freight rate proxy for coking coal trade.",
    ),
    "FREIGHT_ID_SAMARINDA_PARADIP_SUPRA": SeriesMetadata(
        target="route_freight",
        series_id="FREIGHT_ID_SAMARINDA_PARADIP_SUPRA",
        name="Samarinda to Paradip (Supramax)",
        unit="USD_PER_MT",
        frequency="DAILY",
        provenance="PROXY",
        is_demo=True,
        description="Synthetic route freight rate proxy for thermal coal trade.",
    ),
    "FREIGHT_ZA_RICHARDSBAY_PARADIP_PANAMAX": SeriesMetadata(
        target="route_freight",
        series_id="FREIGHT_ZA_RICHARDSBAY_PARADIP_PANAMAX",
        name="Richards Bay to Paradip (Panamax)",
        unit="USD_PER_MT",
        frequency="DAILY",
        provenance="PROXY",
        is_demo=True,
        description="Synthetic route freight rate proxy for South African coal trade.",
    ),
    "FREIGHT_BR_TUBARAO_QINGDAO_CAPE": SeriesMetadata(
        target="route_freight",
        series_id="FREIGHT_BR_TUBARAO_QINGDAO_CAPE",
        name="Tubarao to Qingdao (Capesize C3)",
        unit="USD_PER_MT",
        frequency="DAILY",
        provenance="PROXY",
        is_demo=True,
        description="Synthetic benchmark C3 route freight proxy.",
    ),
    # Bunker Prices
    "BUNKER_VLSFO_SINGAPORE": SeriesMetadata(
        target="bunker_fuel",
        series_id="BUNKER_VLSFO_SINGAPORE",
        name="VLSFO Bunker (Singapore)",
        unit="USD_PER_MT",
        frequency="DAILY",
        provenance="SYNTHETIC",
        is_demo=True,
        description="Synthetic Very Low Sulphur Fuel Oil price at Singapore hub.",
    ),
    "BUNKER_VLSFO_PARADIP": SeriesMetadata(
        target="bunker_fuel",
        series_id="BUNKER_VLSFO_PARADIP",
        name="VLSFO Bunker (Paradip)",
        unit="USD_PER_MT",
        frequency="DAILY",
        provenance="SYNTHETIC",
        is_demo=True,
        description="Synthetic Very Low Sulphur Fuel Oil price at Paradip port.",
    ),
    # Congestion
    "CONGESTION_PORT_PARADIP": SeriesMetadata(
        target="port_congestion",
        series_id="CONGESTION_PORT_PARADIP",
        name="Paradip Port Congestion",
        unit="DAYS",
        frequency="DAILY",
        provenance="SYNTHETIC",
        is_demo=True,
        description="Synthetic vessel waiting days observation at Paradip.",
    ),
}


class ForecastDataService:
    """Provides validated time-series dataframes for forecasting."""

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def get_supported_series(self) -> List[Dict[str, Any]]:
        """Returns metadata for all available forecasting series."""
        return [
            {
                "target": meta.target,
                "series_id": meta.series_id,
                "name": meta.name,
                "unit": meta.unit,
                "frequency": meta.frequency,
                "provenance": meta.provenance,
                "is_demo": meta.is_demo,
                "description": meta.description,
            }
            for meta in SERIES_CATALOG.values()
        ]

    def load_series(self, series_id: str) -> Tuple[pd.DataFrame, SeriesMetadata]:
        """
        Loads and prepares a time series DataFrame with columns ['date', 'value'].
        Extracts from DB if available, or falls back to canonical offline CSV package.
        Guarantees chronological sorting and daily frequency validation.
        """
        if series_id not in SERIES_CATALOG:
            raise ValueError(f"Unknown forecast series: '{series_id}'")

        meta = SERIES_CATALOG[series_id]
        df = None

        # 1. Try loading from database
        if self.db:
            records = self.db.execute(
                select(MarketObservation.observed_at, MarketObservation.value)
                .where(MarketObservation.series_id == series_id)
                .order_by(MarketObservation.observed_at.asc())
            ).all()

            if records:
                df = pd.DataFrame(records, columns=["date", "value"])

        # 2. Fallback to offline CSV package if DB is empty or not provided
        if df is None or len(df) == 0:
            df = self._load_from_csv(series_id, meta.target)

        if df is None or len(df) == 0:
            raise ValueError(f"No observations found for series '{series_id}'")

        # Data Cleaning & Chronological Normalization
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["date", "value"])
        df = df.drop_duplicates(subset=["date"])
        df = df.sort_values(by="date").reset_index(drop=True)

        # Set daily frequency index and forward fill any minor missing days
        df = df.set_index("date")
        full_idx = pd.date_range(start=df.index.min(), end=df.index.max(), freq="D")
        df = df.reindex(full_idx)
        df["value"] = df["value"].ffill().bfill()
        df = df.reset_index().rename(columns={"index": "date"})

        logger.info(
            f"Loaded series {series_id}: {len(df)} daily points from {df['date'].min().date()} to {df['date'].max().date()}"
        )
        return df, meta

    def _load_from_csv(self, series_id: str, target: str) -> pd.DataFrame:
        repo_root = Path(__file__).resolve().parents[4]
        pkg_base = repo_root / "data" / "offline" / "packages" / "demo-v1"

        target_file_map = {
            "market_index": pkg_base / "market" / "market_indices.csv",
            "route_freight": pkg_base / "freight" / "freight_observations.csv",
            "bunker_fuel": pkg_base / "bunker" / "fuel_prices.csv",
            "port_congestion": pkg_base / "congestion" / "congestion_observations.csv",
        }

        csv_path = target_file_map.get(target)
        if not csv_path or not csv_path.exists():
            raise FileNotFoundError(f"Offline dataset not found: {csv_path}")

        raw_df = pd.read_csv(csv_path)
        series_df = raw_df[raw_df["series_id"] == series_id][["observed_at", "value"]].copy()
        series_df = series_df.rename(columns={"observed_at": "date"})
        return series_df
