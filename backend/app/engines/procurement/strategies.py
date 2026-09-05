"""
VesselOptima — Procurement Strategy Candidate Evaluator
Follows Section 4, 9, 10, 12 of the Phase 5 Specification.

Evaluates 4 core strategy structures:
  - SPOT
  - SHORT_TERM
  - MEDIUM_TERM
  - MULTI_VOYAGE

Integrates strictly with Phase 4 FeasibilityService:
Only FEASIBLE vessels from Phase 4 are admitted into candidate pools.
No economic ranking. Candidate strategies are prepared for future MILP optimization.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.engines.feasibility.service import FeasibilityService
from app.engines.procurement.cost_model import calculate_expected_procurement_costs
from app.engines.procurement.forecast_signal import (
    ProcurementForecastSignalService,
    resolve_forecast_series,
)
from app.engines.procurement.lead_time import ProcurementProfile
from app.engines.procurement.reason_codes import ProcurementReasonCode
from app.engines.procurement.timing import evaluate_procurement_timing, parse_date

logger = get_logger("engines.procurement.strategies")


@dataclass
class StrategyDefinition:
    strategy_type: str
    name: str
    description: str
    duration_days: int
    voyage_count: int
    discount_factor: float
    market_exposure: str
    commitment_level: str


STRATEGY_DEFINITIONS: Dict[str, StrategyDefinition] = {
    "SPOT": StrategyDefinition(
        strategy_type="SPOT",
        name="Spot Voyage Charter",
        description="Single voyage spot fixture for immediate cargo requirement. Maximum operational flexibility.",
        duration_days=30,
        voyage_count=1,
        discount_factor=1.0,
        market_exposure="High (Current prompt market)",
        commitment_level="Low (Single voyage only)",
    ),
    "SHORT_TERM": StrategyDefinition(
        strategy_type="SHORT_TERM",
        name="Short-Term Time Charter / Multi-Trip",
        description="Short-duration contract (45-60 days) covering 2 sequential voyage movements.",
        duration_days=60,
        voyage_count=2,
        discount_factor=0.95,
        market_exposure="Moderate (Near-term rate hedge)",
        commitment_level="Moderate (2 consecutive voyages)",
    ),
    "MEDIUM_TERM": StrategyDefinition(
        strategy_type="MEDIUM_TERM",
        name="Medium-Term Contract of Affreightment (COA)",
        description="Period arrangement (120 days) securing 4 voyages with volume commitment discount.",
        duration_days=120,
        voyage_count=4,
        discount_factor=0.92,
        market_exposure="Low (Protected against spot surges)",
        commitment_level="High (Multi-month commitment)",
    ),
    "MULTI_VOYAGE": StrategyDefinition(
        strategy_type="MULTI_VOYAGE",
        name="Multi-Voyage Structured Contract",
        description="Structured consecutive voyage commitment covering linked cargo requirements.",
        duration_days=75,
        voyage_count=2,
        discount_factor=0.94,
        market_exposure="Moderate (Linked forward freight hedge)",
        commitment_level="Moderate (Structured consecutive voyages)",
    ),
}


class ProcurementStrategyEngine:
    """Evaluates viable procurement candidates across the 4 strategy structures."""

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self.feasibility_service = FeasibilityService(db=db)
        self.forecast_signal_service = ProcurementForecastSignalService(db=db)

    def evaluate_strategy_for_cargo(
        self,
        cargo: Dict[str, Any],
        strategy_type: str,
        profile: ProcurementProfile,
        as_of_date: date,
        route_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates a specific strategy against a cargo requirement.
        Strictly consumes Phase 4 for vessel feasibility.
        """
        strat_def = STRATEGY_DEFINITIONS.get(strategy_type.upper(), STRATEGY_DEFINITIONS["SPOT"])

        cargo_id = cargo["id"]
        commodity = cargo.get("commodity", "BULK_CARGO")
        volume_mt = float(cargo.get("volume_mt", 60000.0))
        laycan_start = parse_date(cargo["loading_window_start"])
        laycan_end = parse_date(cargo["loading_window_end"])
        delivery_deadline = parse_date(cargo["delivery_deadline"])
        origin_name = cargo.get("origin_port_name", "Origin Port")
        destination_name = cargo.get("destination_port_name", "Destination Port")

        # 1. Phase 4 Feasibility Evaluation (Admittance Filter)
        fleet_feasibility = self.feasibility_service.evaluate_candidate_fleet(cargo_id)
        if isinstance(fleet_feasibility, dict):
            all_vessels = fleet_feasibility.get("vessels", [])
        else:
            all_vessels = fleet_feasibility
        feasible_vessels = [v for v in all_vessels if v.get("is_feasible")]
        infeasible_vessels = [v for v in all_vessels if not v.get("is_feasible")]

        # Forecast Evidence Integration (Resolved early so all returns include forecast evidence)
        primary_class = feasible_vessels[0].get("vessel_class", "Panamax") if feasible_vessels else "Panamax"
        series_id = resolve_forecast_series(
            origin_name=origin_name,
            destination_name=destination_name,
            vessel_class=primary_class,
        )
        forecast_signal = self.forecast_signal_service.get_procurement_forecast_signal(
            series_id=series_id,
            horizon_days=30,
        )

        # 2. Timing Evaluation
        # Assume minimum 1.5 days ballast positioning for feasible candidates
        timing_result = evaluate_procurement_timing(
            current_date=as_of_date,
            laycan_start=laycan_start,
            laycan_end=laycan_end,
            delivery_deadline=delivery_deadline,
            profile=profile,
            min_positioning_days=1.5,
            estimated_sailing_days=12.0,
        )

        # 3. Transparent Expected Cost Breakdown (calculated for benchmark transparency)
        base_rate = (
            forecast_signal.get("point_estimate")
            if forecast_signal.get("has_forecast") and forecast_signal.get("point_estimate")
            else 18.50
        )
        cost_breakdown = calculate_expected_procurement_costs(
            volume_mt=volume_mt,
            freight_rate_per_mt=base_rate,
            sailing_days=12.0,
            strategy_discount_factor=strat_def.discount_factor,
            voyage_count=strat_def.voyage_count,
        )

        # Check if lead time makes procurement impossible
        if not timing_result["is_timing_feasible"]:
            return {
                "strategy_type": strat_def.strategy_type,
                "strategy_name": strat_def.name,
                "description": strat_def.description,
                "status": "INFEASIBLE",
                "primary_reason_code": timing_result["reason_code"],
                "primary_reason_description": timing_result["reason_description"],
                "timing_signal": timing_result["timing_signal"],
                "contract_duration_days": strat_def.duration_days,
                "voyage_count": strat_def.voyage_count,
                "market_exposure": strat_def.market_exposure,
                "commitment_level": strat_def.commitment_level,
                "timing": timing_result,
                "feasibility_summary": {
                    "total_fleet_evaluated": len(all_vessels),
                    "feasible_vessel_count": len(feasible_vessels),
                    "infeasible_vessel_count": len(infeasible_vessels),
                    "viable_candidate_vessel_ids": [v["vessel_id"] for v in feasible_vessels],
                },
                "forecast_evidence": forecast_signal,
                "cost_summary": cost_breakdown,
                "provenance": {
                    "package_id": "demo-v1",
                    "data_mode": "OFFLINE_DEMO",
                    "feasibility_reference": "Phase 4 FeasibilityEngine",
                    "forecast_reference": f"Phase 3 ForecastService ({series_id})",
                },
            }

        # Infeasibility check: No vessels passed Phase 4
        if not feasible_vessels:
            # Build reason breakdown from failed vessels
            top_reasons = {}
            for v in infeasible_vessels:
                r = v.get("primary_reason_code", "UNKNOWN")
                top_reasons[r] = top_reasons.get(r, 0) + 1

            return {
                "strategy_type": strat_def.strategy_type,
                "strategy_name": strat_def.name,
                "description": strat_def.description,
                "status": "INFEASIBLE",
                "primary_reason_code": ProcurementReasonCode.NO_FEASIBLE_VESSEL.value,
                "primary_reason_description": (
                    f"All {len(all_vessels)} fleet vessels failed Phase 4 operational feasibility. "
                    f"Primary causes: {dict(top_reasons)}"
                ),
                "timing_signal": timing_result["timing_signal"],
                "contract_duration_days": strat_def.duration_days,
                "voyage_count": strat_def.voyage_count,
                "market_exposure": strat_def.market_exposure,
                "commitment_level": strat_def.commitment_level,
                "timing": timing_result,
                "feasibility_summary": {
                    "total_fleet_evaluated": len(all_vessels),
                    "feasible_vessel_count": 0,
                    "infeasible_vessel_count": len(infeasible_vessels),
                    "viable_candidate_vessel_ids": [],
                    "excluded_reasons": top_reasons,
                },
                "forecast_evidence": forecast_signal,
                "cost_summary": cost_breakdown,
                "provenance": {
                    "package_id": "demo-v1",
                    "data_mode": "OFFLINE_DEMO",
                    "feasibility_reference": "Phase 4 FeasibilityEngine",
                    "forecast_reference": f"Phase 3 ForecastService ({series_id})",
                },
            }

        # Refine timing signal with forecast trajectory
        combined_signal = timing_result["timing_signal"]
        if timing_result["timing_signal"] == "WINDOW_OPEN":
            if forecast_signal.get("trajectory") == "FORECAST_INCREASING":
                combined_signal = "EARLY_PROCURE"
            elif forecast_signal.get("trajectory") == "FORECAST_DECREASING":
                combined_signal = "WAIT"

        # 4. Transparent Expected Cost Breakdown
        # Benchmark freight rate from forecast or default proxy 18.50 USD/MT
        base_rate = (
            forecast_signal.get("point_estimate")
            if forecast_signal.get("has_forecast") and forecast_signal.get("point_estimate")
            else 18.50
        )
        cost_breakdown = calculate_expected_procurement_costs(
            volume_mt=volume_mt,
            freight_rate_per_mt=base_rate,
            sailing_days=12.0,
            strategy_discount_factor=strat_def.discount_factor,
            voyage_count=strat_def.voyage_count,
        )

        # 5. Assemble Candidate Strategy Object
        viable_candidate_vessels = [
            {
                "vessel_id": v["vessel_id"],
                "vessel_name": v["vessel_name"],
                "vessel_class": v["vessel_class"],
                "cargo_capacity": v["cargo_capacity"],
                "draft": v["draft"],
            }
            for v in feasible_vessels
        ]

        return {
            "strategy_type": strat_def.strategy_type,
            "strategy_name": strat_def.name,
            "description": strat_def.description,
            "status": "FEASIBLE",
            "primary_reason_code": None,
            "primary_reason_description": "All physical, operational, and procurement lead-time constraints satisfied.",
            "timing_signal": combined_signal,
            "contract_duration_days": strat_def.duration_days,
            "voyage_count": strat_def.voyage_count,
            "market_exposure": strat_def.market_exposure,
            "commitment_level": strat_def.commitment_level,
            "timing": timing_result,
            "forecast_evidence": forecast_signal,
            "cost_summary": cost_breakdown,
            "feasibility_summary": {
                "total_fleet_evaluated": len(all_vessels),
                "feasible_vessel_count": len(feasible_vessels),
                "infeasible_vessel_count": len(infeasible_vessels),
                "viable_candidate_vessels": viable_candidate_vessels,
            },
            "candidate_metadata": {
                "admitted_for_optimization": True,
                "optimization_status": "READY FOR OPTIMIZATION",
            },
            "provenance": {
                "package_id": "demo-v1",
                "data_mode": "OFFLINE_DEMO",
                "feasibility_reference": "Phase 4 FeasibilityEngine",
                "forecast_reference": f"Phase 3 ForecastService ({series_id})",
                "procurement_profile": profile.profile_id,
            },
        }
