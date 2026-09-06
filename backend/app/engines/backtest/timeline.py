"""
VesselOptima — Phase 13: Decision Timeline Engine

Generates chronological decision points across a backtest window.
Supports EVENT_DRIVEN (default), DAILY, WEEKLY, and CUSTOM frequencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

from app.engines.backtest.events import HistoricalEvent, HistoricalEventStream
from app.engines.backtest.reason_codes import DecisionFrequency, HistoricalEventType


@dataclass
class DecisionTimelinePoint:
    """Individual decision node on the historical simulation axis."""
    step_index: int
    decision_timestamp: datetime
    outcome_window_end: datetime
    trigger_reason: str
    trigger_event_id: Optional[str] = None

    def to_dict(self):
        return {
            "step_index": self.step_index,
            "decision_timestamp": self.decision_timestamp.isoformat(),
            "outcome_window_end": self.outcome_window_end.isoformat(),
            "trigger_reason": self.trigger_reason,
            "trigger_event_id": self.trigger_event_id,
        }


class DecisionTimelineEngine:
    """
    Constructs the sequence of decision points and outcome evaluation intervals.
    """
    def __init__(
        self,
        frequency: DecisionFrequency = DecisionFrequency.EVENT_DRIVEN,
        default_outcome_window_days: int = 14,
    ):
        self.frequency = frequency
        self.default_outcome_window = timedelta(days=default_outcome_window_days)

    def generate_timeline(
        self,
        start_time: datetime,
        end_time: datetime,
        event_stream: Optional[HistoricalEventStream] = None,
        custom_timestamps: Optional[List[datetime]] = None,
    ) -> List[DecisionTimelinePoint]:
        """
        Builds the chronological list of decision milestones.
        """
        if start_time >= end_time:
            raise ValueError(f"start_time ({start_time}) must precede end_time ({end_time})")

        points: List[DecisionTimelinePoint] = []

        if self.frequency == DecisionFrequency.CUSTOM:
            if not custom_timestamps:
                raise ValueError("CUSTOM frequency requires custom_timestamps list.")
            sorted_ts = sorted(ts for ts in custom_timestamps if start_time <= ts <= end_time)
            for idx, ts in enumerate(sorted_ts):
                next_ts = sorted_ts[idx + 1] if idx + 1 < len(sorted_ts) else min(ts + self.default_outcome_window, end_time)
                points.append(
                    DecisionTimelinePoint(
                        step_index=idx,
                        decision_timestamp=ts,
                        outcome_window_end=next_ts,
                        trigger_reason="CUSTOM_SCHEDULE",
                    )
                )
            return points

        elif self.frequency == DecisionFrequency.DAILY:
            cur = start_time
            idx = 0
            while cur <= end_time:
                next_cur = cur + timedelta(days=1)
                points.append(
                    DecisionTimelinePoint(
                        step_index=idx,
                        decision_timestamp=cur,
                        outcome_window_end=min(next_cur, end_time + self.default_outcome_window),
                        trigger_reason="DAILY_REBALANCE",
                    )
                )
                cur = next_cur
                idx += 1
            return points

        elif self.frequency == DecisionFrequency.WEEKLY:
            cur = start_time
            idx = 0
            while cur <= end_time:
                next_cur = cur + timedelta(days=7)
                points.append(
                    DecisionTimelinePoint(
                        step_index=idx,
                        decision_timestamp=cur,
                        outcome_window_end=min(next_cur, end_time + self.default_outcome_window),
                        trigger_reason="WEEKLY_REBALANCE",
                    )
                )
                cur = next_cur
                idx += 1
            return points

        elif self.frequency == DecisionFrequency.EVENT_DRIVEN:
            if not event_stream or event_stream.total_count == 0:
                # Fallback to daily if no event stream provided
                return self._generate_fallback_daily(start_time, end_time)

            # Trigger on cargo availability, vessel availability, fixture creation, or operational events
            trigger_types = {
                HistoricalEventType.CARGO_AVAILABLE,
                HistoricalEventType.VESSEL_AVAILABILITY,
                HistoricalEventType.FIXTURE_CREATED,
                HistoricalEventType.OPERATIONAL_EVENT,
            }

            all_events = event_stream.get_realization_events_between(start_time, end_time)
            trigger_events = [e for e in all_events if e.event_type in trigger_types]

            if not trigger_events:
                # If no triggers in stream, at least evaluate at start
                return [
                    DecisionTimelinePoint(
                        step_index=0,
                        decision_timestamp=start_time,
                        outcome_window_end=min(start_time + self.default_outcome_window, end_time),
                        trigger_reason="START_HORIZON",
                    )
                ]

            idx = 0
            for i, ev in enumerate(trigger_events):
                ts = ev.event_timestamp
                next_ts = trigger_events[i + 1].event_timestamp if i + 1 < len(trigger_events) else min(ts + self.default_outcome_window, end_time)
                points.append(
                    DecisionTimelinePoint(
                        step_index=idx,
                        decision_timestamp=ts,
                        outcome_window_end=next_ts,
                        trigger_reason=f"EVENT_{ev.event_type.value}",
                        trigger_event_id=ev.event_id,
                    )
                )
                idx += 1

            return points

        raise ValueError(f"Unsupported decision frequency: {self.frequency}")

    def _generate_fallback_daily(self, start_time: datetime, end_time: datetime) -> List[DecisionTimelinePoint]:
        points = []
        cur = start_time
        idx = 0
        while cur <= end_time:
            next_cur = cur + timedelta(days=1)
            points.append(
                DecisionTimelinePoint(
                    step_index=idx,
                    decision_timestamp=cur,
                    outcome_window_end=min(next_cur, end_time + self.default_outcome_window),
                    trigger_reason="EVENT_FALLBACK_DAILY",
                )
            )
            cur = next_cur
            idx += 1
        return points
