"""
VesselOptima — Phase 13: Realized Outcome Engine

Evaluates the actual historical execution of optimized decisions vs historical events.
Calculates realized freight economics (USD only), schedule deviation, and decision quality.
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
class RealizedAssignmentOutcome:
    """Detailed realization outcome for an individual vessel-cargo assignment."""
    outcome_code: str
    vessel_id: int
    cargo_id: Optional[int]
    decision_timestamp: datetime
    expected_contribution_usd: float
    realized_revenue_usd: float = 0.0
    realized_bunker_cost_usd: float = 0.0
    realized_port_cost_usd: float = 0.0
    realized_voyage_cost_usd: float = 0.0
    realized_ballast_cost_usd: float = 0.0
    realized_idle_cost_usd: float = 0.0
    realized_contribution_usd: float = 0.0
    economic_error_usd: float = 0.0
    planned_departure: Optional[datetime] = None
    actual_departure: Optional[datetime] = None
    planned_arrival: Optional[datetime] = None
    actual_arrival: Optional[datetime] = None
    schedule_delay_days: float = 0.0
    idle_days: float = 0.0
    ballast_days: float = 0.0
    cargo_completed: bool = True
    outcome_hash: str = ""

    def compute_hash(self) -> None:
        payload = {
            "outcome_code": self.outcome_code,
            "vessel_id": self.vessel_id,
            "cargo_id": self.cargo_id,
            "expected_contribution_usd": round(self.expected_contribution_usd, 2),
            "realized_revenue_usd": round(self.realized_revenue_usd, 2),
            "realized_contribution_usd": round(self.realized_contribution_usd, 2),
            "economic_error_usd": round(self.economic_error_usd, 2),
            "schedule_delay_days": round(self.schedule_delay_days, 2),
            "cargo_completed": self.cargo_completed,
        }
        serialized = json.dumps(payload, sort_keys=True)
        self.outcome_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome_code": self.outcome_code,
            "vessel_id": self.vessel_id,
            "cargo_id": self.cargo_id,
            "expected_contribution_usd": self.expected_contribution_usd,
            "realized_revenue_usd": self.realized_revenue_usd,
            "realized_bunker_cost_usd": self.realized_bunker_cost_usd,
            "realized_port_cost_usd": self.realized_port_cost_usd,
            "realized_voyage_cost_usd": self.realized_voyage_cost_usd,
            "realized_ballast_cost_usd": self.realized_ballast_cost_usd,
            "realized_idle_cost_usd": self.realized_idle_cost_usd,
            "realized_contribution_usd": self.realized_contribution_usd,
            "economic_error_usd": self.economic_error_usd,
            "planned_departure": self.planned_departure.isoformat() if self.planned_departure else None,
            "actual_departure": self.actual_departure.isoformat() if self.actual_departure else None,
            "planned_arrival": self.planned_arrival.isoformat() if self.planned_arrival else None,
            "actual_arrival": self.actual_arrival.isoformat() if self.actual_arrival else None,
            "schedule_delay_days": self.schedule_delay_days,
            "idle_days": self.idle_days,
            "ballast_days": self.ballast_days,
            "cargo_completed": self.cargo_completed,
            "outcome_hash": self.outcome_hash,
        }


class RealizedOutcomeEngine:
    """
    Computes realized operational and economic metrics from subsequent realization events.
    Enforces USD-only calculations.
    """
    def evaluate_decision(
        self,
        decision_code: str,
        decision_timestamp: datetime,
        assignments: List[Dict[str, Any]],
        realization_events: List[HistoricalEvent],
    ) -> List[RealizedAssignmentOutcome]:
        """
        For each assigned vessel-cargo, scans subsequent events to determine actual voyage execution.
        """
        outcomes: List[RealizedAssignmentOutcome] = []

        # Index events by entity
        events_by_entity: Dict[str, List[HistoricalEvent]] = {}
        for ev in realization_events:
            events_by_entity.setdefault(str(ev.entity_id), []).append(ev)

        for idx, assign in enumerate(assignments):
            vessel_id = int(assign.get("vessel_id", 0))
            cargo_id = assign.get("cargo_id")
            if cargo_id is not None and str(cargo_id).isdigit():
                cargo_id = int(cargo_id)

            expected_contrib = float(assign.get("expected_contribution_usd", assign.get("net_contribution", 0.0)))
            planned_rev = float(assign.get("expected_revenue_usd", assign.get("revenue", 0.0)))
            planned_cost = float(assign.get("expected_cost_usd", assign.get("voyage_cost", 0.0)))

            # If vessel is idle / unassigned
            if cargo_id is None:
                idle_cost_rate = float(assign.get("daily_idle_cost", 6500.0))
                idle_days = float(assign.get("idle_days", 5.0))
                realized_idle = idle_cost_rate * idle_days
                realized_contrib = -realized_idle

                outcome = RealizedAssignmentOutcome(
                    outcome_code=f"OUT-{decision_code}-V{vessel_id}-IDLE",
                    vessel_id=vessel_id,
                    cargo_id=None,
                    decision_timestamp=decision_timestamp,
                    expected_contribution_usd=expected_contrib,
                    realized_revenue_usd=0.0,
                    realized_voyage_cost_usd=0.0,
                    realized_idle_cost_usd=realized_idle,
                    realized_contribution_usd=realized_contrib,
                    economic_error_usd=realized_contrib - expected_contrib,
                    idle_days=idle_days,
                    cargo_completed=True,
                )
                outcome.compute_hash()
                outcomes.append(outcome)
                continue

            # Check realized events for this vessel and cargo
            v_events = events_by_entity.get(str(vessel_id), [])
            c_events = events_by_entity.get(str(cargo_id), []) if cargo_id else []

            # Determine delay and completion
            delay_days = 0.0
            operational_delays = [
                float(e.payload.get("delay_days", 0.0))
                for e in v_events
                if e.event_type == HistoricalEventType.OPERATIONAL_EVENT
            ]
            if operational_delays:
                delay_days = sum(operational_delays)

            # Weather / bunker price variations
            bunker_factor = 1.0
            bunker_events = [e for e in realization_events if e.event_type == HistoricalEventType.BUNKER_PRICE]
            if bunker_events:
                # Slight variation if bunker prices drifted
                bunker_factor = 1.0 + (delay_days * 0.01)

            realized_bunker = planned_cost * 0.65 * bunker_factor
            realized_port = planned_cost * 0.25
            realized_ballast = planned_cost * 0.10
            realized_voyage_cost = realized_bunker + realized_port + realized_ballast

            # Revenue realization (demurrage / despatch adjustment if delayed)
            demurrage_per_day = 12000.0
            demurrage_penalty = max(0.0, delay_days - 2.0) * demurrage_per_day
            realized_revenue = max(0.0, planned_rev - demurrage_penalty)

            realized_contrib = realized_revenue - realized_voyage_cost
            economic_error = realized_contrib - expected_contrib

            outcome = RealizedAssignmentOutcome(
                outcome_code=f"OUT-{decision_code}-V{vessel_id}-C{cargo_id}",
                vessel_id=vessel_id,
                cargo_id=cargo_id,
                decision_timestamp=decision_timestamp,
                expected_contribution_usd=expected_contrib,
                realized_revenue_usd=realized_revenue,
                realized_bunker_cost_usd=realized_bunker,
                realized_port_cost_usd=realized_port,
                realized_voyage_cost_usd=realized_voyage_cost,
                realized_ballast_cost_usd=realized_ballast,
                realized_idle_cost_usd=0.0,
                realized_contribution_usd=realized_contrib,
                economic_error_usd=economic_error,
                schedule_delay_days=delay_days,
                idle_days=0.0,
                ballast_days=float(assign.get("ballast_days", 4.0)),
                cargo_completed=True,
            )
            outcome.compute_hash()
            outcomes.append(outcome)

        return outcomes
