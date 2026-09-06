"""
VesselOptima — Phase 13: Historical Event Model

Normalizes, validates, and freezes chronological maritime event streams.
Ensures point-in-time reconstruction without mutating source data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.engines.backtest.reason_codes import HistoricalEventType


def compute_event_hash(
    event_id: str,
    event_type: str,
    event_timestamp: datetime,
    availability_timestamp: datetime,
    source_dataset_id: str,
    source_dataset_version: int,
    entity_id: str,
    payload: Dict[str, Any],
) -> str:
    """Computes a deterministic SHA-256 hash for a historical event."""
    serialized_payload = json.dumps(payload, sort_keys=True, default=str)
    raw = (
        f"{event_id}|{event_type}|{event_timestamp.isoformat()}|"
        f"{availability_timestamp.isoformat()}|{source_dataset_id}|"
        f"{source_dataset_version}|{entity_id}|{serialized_payload}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class HistoricalEvent:
    """
    Immutable representation of an atomic historical maritime observation or state transition.
    """
    event_id: str
    event_type: HistoricalEventType
    event_timestamp: datetime
    availability_timestamp: datetime
    source_dataset_id: str
    source_dataset_version: int
    entity_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    record_hash: str = field(default="")

    def __post_init__(self):
        computed_hash = compute_event_hash(
            event_id=self.event_id,
            event_type=self.event_type.value if hasattr(self.event_type, "value") else str(self.event_type),
            event_timestamp=self.event_timestamp,
            availability_timestamp=self.availability_timestamp,
            source_dataset_id=self.source_dataset_id,
            source_dataset_version=self.source_dataset_version,
            entity_id=self.entity_id,
            payload=self.payload,
        )
        if not self.record_hash:
            object.__setattr__(self, "record_hash", computed_hash)
        elif self.record_hash != computed_hash:
            raise ValueError(
                f"HistoricalEvent hash mismatch for {self.event_id}: "
                f"provided={self.record_hash}, computed={computed_hash}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value if hasattr(self.event_type, "value") else str(self.event_type),
            "event_timestamp": self.event_timestamp.isoformat(),
            "availability_timestamp": self.availability_timestamp.isoformat(),
            "source_dataset_id": self.source_dataset_id,
            "source_dataset_version": self.source_dataset_version,
            "entity_id": self.entity_id,
            "payload": self.payload,
            "record_hash": self.record_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> HistoricalEvent:
        event_type = HistoricalEventType(data["event_type"])
        event_ts = (
            datetime.fromisoformat(data["event_timestamp"])
            if isinstance(data["event_timestamp"], str)
            else data["event_timestamp"]
        )
        avail_ts = (
            datetime.fromisoformat(data["availability_timestamp"])
            if isinstance(data["availability_timestamp"], str)
            else data["availability_timestamp"]
        )
        return cls(
            event_id=data["event_id"],
            event_type=event_type,
            event_timestamp=event_ts,
            availability_timestamp=avail_ts,
            source_dataset_id=data.get("source_dataset_id", "historical-default"),
            source_dataset_version=data.get("source_dataset_version", 1),
            entity_id=str(data.get("entity_id", "")),
            payload=data.get("payload", {}),
            record_hash=data.get("record_hash", ""),
        )


class HistoricalEventStream:
    """
    Chronologically ordered, verified collection of historical events.
    Guarantees strict monotonic ordering and deterministic retrieval.
    """
    def __init__(self, events: Optional[List[HistoricalEvent]] = None):
        self._events: List[HistoricalEvent] = []
        if events:
            for ev in events:
                self.add_event(ev)

    def add_event(self, event: HistoricalEvent) -> None:
        self._events.append(event)
        self._events.sort(key=lambda e: (e.availability_timestamp, e.event_timestamp, e.event_id))

    def get_events_available_at(self, as_of: datetime) -> List[HistoricalEvent]:
        """
        Returns events with availability_timestamp <= as_of.
        Strictly prevents look-ahead by respecting publication availability.
        """
        return [e for e in self._events if e.availability_timestamp <= as_of]

    def get_realization_events_between(self, start: datetime, end: datetime) -> List[HistoricalEvent]:
        """
        Returns events that occurred in the outcome window (start <= event_timestamp <= end).
        """
        return [e for e in self._events if start <= e.event_timestamp <= end]

    @property
    def total_count(self) -> int:
        return len(self._events)

    def compute_stream_hash(self) -> str:
        """Deterministic fingerprint of all events in chronological sequence."""
        hashes = [e.record_hash for e in self._events]
        combined = "|".join(hashes)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def to_list(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._events]
