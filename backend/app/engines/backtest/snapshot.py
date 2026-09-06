"""
VesselOptima — Phase 13: Point-in-Time Snapshot Engine

Reconstructs the exact operational and market reality at historical timestamp T.
Guarantees zero leakage: only data with availability_timestamp <= T is admitted.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.engines.backtest.events import HistoricalEvent, HistoricalEventStream
from app.engines.backtest.reason_codes import HistoricalEventType


@dataclass
class PointInTimeSnapshot:
    """
    State of the maritime operating environment at a precise historical timestamp T.
    """
    timestamp: datetime
    dataset_versions: Dict[str, int]
    vessels: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    cargoes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    freight_rates: Dict[str, float] = field(default_factory=dict)  # route_key -> rate $/MT
    bunker_prices: Dict[str, float] = field(default_factory=dict)  # port_unlocode -> price $/MT
    port_conditions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    commitments: List[Dict[str, Any]] = field(default_factory=list)
    operational_events: List[Dict[str, Any]] = field(default_factory=list)
    snapshot_hash: str = field(default="")
    market_state_hash: str = field(default="")

    def compute_hashes(self) -> None:
        """Computes deterministic hashes for market state and complete snapshot state."""
        # Market state hash
        market_dict = {
            "freight_rates": {k: self.freight_rates[k] for k in sorted(self.freight_rates.keys())},
            "bunker_prices": {k: self.bunker_prices[k] for k in sorted(self.bunker_prices.keys())},
            "port_conditions": {k: self.port_conditions[k] for k in sorted(self.port_conditions.keys())},
        }
        market_str = json.dumps(market_dict, sort_keys=True, default=str)
        self.market_state_hash = hashlib.sha256(market_str.encode("utf-8")).hexdigest()

        # Overall snapshot hash
        payload = {
            "timestamp": self.timestamp.isoformat(),
            "dataset_versions": {k: self.dataset_versions[k] for k in sorted(self.dataset_versions.keys())},
            "vessels": {k: self.vessels[k] for k in sorted(self.vessels.keys())},
            "cargoes": {k: self.cargoes[k] for k in sorted(self.cargoes.keys())},
            "market_state_hash": self.market_state_hash,
            "commitments": self.commitments,
            "operational_events": self.operational_events,
        }
        payload_str = json.dumps(payload, sort_keys=True, default=str)
        self.snapshot_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "dataset_versions": self.dataset_versions,
            "vessel_count": len(self.vessels),
            "cargo_count": len(self.cargoes),
            "freight_rates": self.freight_rates,
            "bunker_prices": self.bunker_prices,
            "port_conditions": self.port_conditions,
            "commitments_count": len(self.commitments),
            "operational_events_count": len(self.operational_events),
            "market_state_hash": self.market_state_hash,
            "snapshot_hash": self.snapshot_hash,
        }


class PointInTimeSnapshotEngine:
    """
    Deterministically compiles a PointInTimeSnapshot from a HistoricalEventStream.
    Processes chronological state events up to timestamp T.
    """
    def __init__(self, dataset_versions: Optional[Dict[str, int]] = None):
        self.dataset_versions = dataset_versions or {"maritime_data": 1}

    def build_snapshot(
        self,
        as_of: datetime,
        event_stream: HistoricalEventStream,
    ) -> PointInTimeSnapshot:
        """
        Filters events strictly by availability_timestamp <= as_of and reconstructs state.
        """
        available_events = event_stream.get_events_available_at(as_of)

        vessels: Dict[str, Dict[str, Any]] = {}
        cargoes: Dict[str, Dict[str, Any]] = {}
        freight_rates: Dict[str, float] = {}
        bunker_prices: Dict[str, float] = {}
        port_conditions: Dict[str, Dict[str, Any]] = {}
        commitments: List[Dict[str, Any]] = []
        operational_events: List[Dict[str, Any]] = []

        for ev in available_events:
            p = ev.payload
            etype = ev.event_type

            if etype == HistoricalEventType.VESSEL_POSITION or etype == HistoricalEventType.VESSEL_AVAILABILITY:
                vid = str(ev.entity_id)
                vessels[vid] = {
                    "vessel_id": int(vid) if vid.isdigit() else vid,
                    "name": p.get("name", f"Vessel-{vid}"),
                    "vessel_class": p.get("vessel_class", "Supramax"),
                    "dwt": p.get("dwt", 55000.0),
                    "open_port": p.get("open_port", "INBOM"),
                    "open_date": p.get("open_date", ev.event_timestamp.isoformat()),
                    "fuel_ifo_remaining": p.get("fuel_ifo_remaining", 500.0),
                    "fuel_mgo_remaining": p.get("fuel_mgo_remaining", 80.0),
                    "is_available": p.get("is_available", True),
                    "last_updated": p.get("last_updated", ev.event_timestamp.isoformat()),
                }
            elif etype == HistoricalEventType.CARGO_AVAILABLE or etype == HistoricalEventType.CARGO_UPDATED:
                cid = str(ev.entity_id)
                if p.get("is_active", True) and not p.get("is_cancelled", False):
                    cargoes[cid] = {
                        "cargo_id": int(cid) if cid.isdigit() else cid,
                        "name": p.get("name", f"Cargo-{cid}"),
                        "origin_port": p.get("origin_port", "INPRT"),
                        "destination_port": p.get("destination_port", "INBOM"),
                        "cargo_type": p.get("cargo_type", "Thermal Coal"),
                        "quantity_mt": p.get("quantity_mt", 50000.0),
                        "laycan_start": p.get("laycan_start", ev.event_timestamp.isoformat()),
                        "laycan_end": p.get("laycan_end", ev.event_timestamp.isoformat()),
                        "freight_rate_usd": p.get("freight_rate_usd", 25.0),
                        "last_updated": p.get("last_updated", ev.event_timestamp.isoformat()),
                    }
                elif p.get("is_cancelled", False) and cid in cargoes:
                    cargoes.pop(cid, None)
            elif etype == HistoricalEventType.CARGO_COMPLETED:
                cid = str(ev.entity_id)
                cargoes.pop(cid, None)
            elif etype == HistoricalEventType.FREIGHT_UPDATE:
                route_key = str(p.get("route_key", ev.entity_id))
                freight_rates[route_key] = float(p.get("rate_usd_mt", 20.0))
            elif etype == HistoricalEventType.BUNKER_PRICE:
                port_code = str(p.get("port_code", ev.entity_id))
                bunker_prices[port_code] = float(p.get("price_usd_mt", 550.0))
            elif etype == HistoricalEventType.PORT_UPDATE:
                port_code = str(p.get("port_code", ev.entity_id))
                port_conditions[port_code] = {
                    "congestion_days": float(p.get("congestion_days", 0.0)),
                    "draft_limit_m": float(p.get("draft_limit_m", 15.0)),
                    "status": p.get("status", "OPEN"),
                }
            elif etype == HistoricalEventType.VESSEL_COMMITMENT or etype == HistoricalEventType.FIXTURE_CREATED:
                commitments.append({
                    "commitment_id": p.get("commitment_id", ev.event_id),
                    "vessel_id": ev.entity_id,
                    "cargo_id": p.get("cargo_id"),
                    "start_date": p.get("start_date", ev.event_timestamp.isoformat()),
                    "end_date": p.get("end_date"),
                    "status": p.get("status", "ACTIVE"),
                })
            elif etype == HistoricalEventType.OPERATIONAL_EVENT:
                operational_events.append({
                    "event_id": ev.event_id,
                    "entity_id": ev.entity_id,
                    "event_description": p.get("description", ""),
                    "impact": p.get("impact", "NONE"),
                    "delay_days": float(p.get("delay_days", 0.0)),
                })

        snapshot = PointInTimeSnapshot(
            timestamp=as_of,
            dataset_versions=self.dataset_versions,
            vessels=vessels,
            cargoes=cargoes,
            freight_rates=freight_rates,
            bunker_prices=bunker_prices,
            port_conditions=port_conditions,
            commitments=commitments,
            operational_events=operational_events,
        )
        snapshot.compute_hashes()
        return snapshot
