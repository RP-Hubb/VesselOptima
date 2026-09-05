"""
VesselOptima — Master Procurement Engine Service
Follows Sections 3, 5, 7, 9, 10, 12, 13, 16 of the Phase 5 Specification.

Coordinates lead-time profiles, timing evaluation, Phase 3 forecast signals,
Phase 4 feasibility admittance, and strategy candidate generation.
Strict adherence to: Prediction != Decision and Strategy Evaluation != Global Optimization.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.engines.procurement.lead_time import (
    DEFAULT_PROFILES,
    ProcurementProfile,
    get_procurement_profile,
)
from app.engines.procurement.strategies import (
    STRATEGY_DEFINITIONS,
    ProcurementStrategyEngine,
)
from app.models.domain import CargoParcel, Port, ProcurementConfig, ProcurementEvaluation, RuntimeModeEnum

logger = get_logger("engines.procurement.service")

DEFAULT_AS_OF_DATE = date(2026, 9, 1)


class ProcurementService:
    """Master service providing dynamic procurement strategy and timing capabilities."""

    def __init__(self, db: Optional[Session] = None, package_dir: Optional[Path] = None):
        self.db = db
        if package_dir:
            self.package_dir = package_dir
        else:
            repo_root = Path(__file__).resolve().parents[4]
            self.package_dir = repo_root / "data" / "offline" / "packages" / "demo-v1"

        self.strategy_engine = ProcurementStrategyEngine(db=db)

    # ── Profiles & Configuration ─────────────────────────────────────

    def get_profiles(self) -> List[Dict[str, Any]]:
        """Returns all active procurement lead-time profiles."""
        profiles = [p.to_dict() for p in DEFAULT_PROFILES.values()]
        if self.db:
            try:
                stmt = select(ProcurementConfig).where(ProcurementConfig.is_active == True)
                db_configs = self.db.scalars(stmt).all()
                for c in db_configs:
                    if c.profile_id not in DEFAULT_PROFILES:
                        p = ProcurementProfile(
                            profile_id=c.profile_id,
                            name=c.name,
                            tender_preparation_days=c.tender_preparation_days,
                            bid_submission_days=c.bid_submission_days,
                            technical_evaluation_days=c.technical_evaluation_days,
                            commercial_evaluation_days=c.commercial_evaluation_days,
                            approval_days=c.approval_days,
                            award_days=c.award_days,
                            description="User-configured procurement profile.",
                            data_classification=c.data_classification,
                        )
                        profiles.append(p.to_dict())
            except Exception as e:
                logger.warning(f"Could not load custom procurement profiles: {e}")
        return profiles

    def save_custom_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates or updates a procurement configuration profile."""
        profile_id = profile_data["profile_id"].upper()
        p = get_procurement_profile(profile_id=profile_id, custom_stages=profile_data)

        if self.db:
            existing = self.db.scalars(
                select(ProcurementConfig).where(ProcurementConfig.profile_id == profile_id)
            ).first()
            if existing:
                existing.name = profile_data.get("name", existing.name)
                existing.tender_preparation_days = p.tender_preparation_days
                existing.bid_submission_days = p.bid_submission_days
                existing.technical_evaluation_days = p.technical_evaluation_days
                existing.commercial_evaluation_days = p.commercial_evaluation_days
                existing.approval_days = p.approval_days
                existing.award_days = p.award_days
                existing.minimum_lead_time_days = p.minimum_lead_time_days
                self.db.commit()
            else:
                new_cfg = ProcurementConfig(
                    profile_id=profile_id,
                    name=profile_data.get("name", f"Custom {profile_id}"),
                    tender_preparation_days=p.tender_preparation_days,
                    bid_submission_days=p.bid_submission_days,
                    technical_evaluation_days=p.technical_evaluation_days,
                    commercial_evaluation_days=p.commercial_evaluation_days,
                    approval_days=p.approval_days,
                    award_days=p.award_days,
                    minimum_lead_time_days=p.minimum_lead_time_days,
                    data_classification="CONFIGURED",
                )
                self.db.add(new_cfg)
                self.db.commit()

        return p.to_dict()

    # ── Cargo Requirements Resolution ─────────────────────────────────

    def get_cargo(self, cargo_id: int) -> Optional[Dict[str, Any]]:
        """Resolves cargo requirement from DB or offline package CSV."""
        if self.db:
            parcel = self.db.get(CargoParcel, cargo_id)
            if parcel:
                origin_name = "Origin Port"
                dest_name = "Destination Port"
                if parcel.origin_port_id:
                    p = self.db.get(Port, parcel.origin_port_id)
                    if p:
                        origin_name = p.name
                if parcel.destination_port_id:
                    p = self.db.get(Port, parcel.destination_port_id)
                    if p:
                        dest_name = p.name

                return {
                    "id": parcel.id,
                    "commodity": parcel.commodity,
                    "volume_mt": parcel.volume_mt,
                    "origin_port_id": parcel.origin_port_id,
                    "destination_port_id": parcel.destination_port_id,
                    "origin_port_name": origin_name,
                    "destination_port_name": dest_name,
                    "loading_window_start": parcel.loading_window_start.date().isoformat() if parcel.loading_window_start else "2026-09-20",
                    "loading_window_end": parcel.loading_window_end.date().isoformat() if parcel.loading_window_end else "2026-09-25",
                    "delivery_deadline": parcel.delivery_deadline.date().isoformat() if parcel.delivery_deadline else "2026-10-15",
                    "tolerance_pct": parcel.tolerance_pct if parcel.tolerance_pct is not None else 5.0,
                }

        # Fallback to CSV
        PORT_NAME_MAP = {
            1: "Paradip",
            2: "Dhamra",
            3: "Krishnapatnam",
            4: "Ennore",
            6: "Port Hedland",
            7: "Newcastle",
            8: "Hay Point",
            9: "Samarinda",
            11: "Richards Bay",
        }
        cargo_csv = self.package_dir / "cargo" / "cargo_requirements.csv"
        if cargo_csv.exists():
            with open(cargo_csv, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if int(row.get("id", 0)) == cargo_id:
                        orig_id = int(row.get("origin_port_id", 1))
                        dest_id = int(row.get("destination_port_id", 2))
                        start_str = row.get("loading_window_start", "2026-09-20").split()[0]
                        end_str = row.get("loading_window_end", "2026-09-25").split()[0]
                        dl_str = row.get("delivery_deadline", "2026-10-15").split()[0]

                        return {
                            "id": int(row["id"]),
                            "commodity": row.get("commodity", "BULK_CARGO"),
                            "volume_mt": float(row.get("volume_mt", row.get("quantity_mt", 60000.0))),
                            "origin_port_id": orig_id,
                            "destination_port_id": dest_id,
                            "loading_window_start": start_str,
                            "loading_window_end": end_str,
                            "delivery_deadline": dl_str,
                            "tolerance_pct": float(row.get("tolerance_pct", 5.0)),
                            "origin_port_name": PORT_NAME_MAP.get(orig_id, f"Port {orig_id}"),
                            "destination_port_name": PORT_NAME_MAP.get(dest_id, f"Port {dest_id}"),
                        }
        return None

    # ── Strategy Evaluation & Comparison ──────────────────────────────

    def evaluate_cargo_strategies(
        self,
        cargo_id: int,
        profile_id: Optional[str] = None,
        as_of_date: Optional[date] = None,
        strategy_types: Optional[List[str]] = None,
        custom_stages: Optional[Dict[str, float]] = None,
        persist: bool = False,
    ) -> Dict[str, Any]:
        """
        Evaluates candidate procurement strategies for a cargo requirement.
        Strictly consumes Phase 4 Feasibility and Phase 3 Forecasts.
        """
        cargo = self.get_cargo(cargo_id)
        if not cargo:
            raise ValueError(f"Cargo requirement {cargo_id} not found.")

        profile = get_procurement_profile(profile_id=profile_id, custom_stages=custom_stages)
        evaluation_date = as_of_date or DEFAULT_AS_OF_DATE

        active_strategies = (
            [s.upper() for s in strategy_types]
            if strategy_types
            else ["SPOT", "SHORT_TERM", "MEDIUM_TERM", "MULTI_VOYAGE"]
        )

        results = []
        for s_type in active_strategies:
            eval_res = self.strategy_engine.evaluate_strategy_for_cargo(
                cargo=cargo,
                strategy_type=s_type,
                profile=profile,
                as_of_date=evaluation_date,
            )
            results.append(eval_res)

            # Persist to database if requested
            if persist and self.db:
                try:
                    eval_record = ProcurementEvaluation(
                        cargo_id=cargo_id,
                        profile_id=profile.profile_id,
                        strategy_type=s_type,
                        status=eval_res["status"],
                        timing_signal=eval_res.get("timing_signal", "UNKNOWN"),
                        candidate_data=eval_res.get("feasibility_summary"),
                        timing_detail=eval_res.get("timing"),
                        cost_detail=eval_res.get("cost_summary"),
                        forecast_detail=eval_res.get("forecast_evidence"),
                        feasibility_detail=eval_res.get("feasibility_summary"),
                        assumptions={
                            "as_of_date": evaluation_date.isoformat(),
                            "profile": profile.to_dict(),
                        },
                        provenance=eval_res.get("provenance"),
                        evaluated_at=datetime.now(timezone.utc),
                        runtime_mode=RuntimeModeEnum.OFFLINE_DEMO,
                    )
                    self.db.add(eval_record)
                    self.db.commit()
                except Exception as e:
                    logger.warning(f"Failed to persist procurement evaluation: {e}")
                    if self.db:
                        self.db.rollback()

        feasible_count = sum(1 for r in results if r["status"] == "FEASIBLE")
        infeasible_count = len(results) - feasible_count

        return {
            "cargo_id": cargo_id,
            "commodity": cargo["commodity"],
            "volume_mt": cargo["volume_mt"],
            "origin_port": cargo.get("origin_port_name", f"Port {cargo['origin_port_id']}"),
            "destination_port": cargo.get("destination_port_name", f"Port {cargo['destination_port_id']}"),
            "laycan_start": cargo["loading_window_start"],
            "laycan_end": cargo["loading_window_end"],
            "delivery_deadline": cargo["delivery_deadline"],
            "as_of_date": evaluation_date.isoformat(),
            "procurement_profile": profile.to_dict(),
            "procurement_lead_time_days": profile.minimum_lead_time_days,
            "strategies_evaluated_count": len(results),
            "feasible_strategies_count": feasible_count,
            "infeasible_strategies_count": infeasible_count,
            "strategies": results,
            "advisory_note": (
                "Strategy evaluations represent candidate options with transparent evidence. "
                "Final selection and allocation are performed by the MILP Optimization Engine."
            ),
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }
