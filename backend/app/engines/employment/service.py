"""
VesselOptima — Master Employment & Idle Management Engine Service
Follows Sections 2, 6, 7, 8, 16, 22 of the Phase 6 Specification.
"""

from __future__ import annotations

import csv
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.domain import RuntimeModeEnum
from app.engines.employment.ballast import calculate_ballast_repositioning
from app.engines.employment.economics import calculate_employment_economics
from app.engines.employment.idle_model import evaluate_vessel_idle_state
from app.engines.employment.reason_codes import EmploymentReasonCode, describe_reason_code
from app.engines.employment.timeline import validate_employment_timeline
from app.engines.feasibility.service import FeasibilityService
from app.engines.procurement.timing import evaluate_procurement_timing
from app.engines.procurement.lead_time import get_procurement_profile
from app.models.domain import (
    CargoParcel,
    EmploymentOpportunity,
    IdleAssessment,
    Port,
    Route,
    VesselCommitment,
    VesselProfile,
)

logger = logging.getLogger("vesseloptima.engines.employment.service")

DEFAULT_AS_OF_DATE = datetime(2026, 9, 1, 0, 0, 0)


class EmploymentService:
    """
    Master service coordinating Idle State Assessment and Alternative Employment
    candidate generation. Strictly adheres to the principle that candidate generation
    is not global optimization.
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        repo_root = Path(__file__).resolve().parents[4]
        self.package_dir = repo_root / "data" / "offline" / "packages" / "demo-v1"
        self.feasibility_service = FeasibilityService(db=db, package_dir=self.package_dir)

    # ── Internal Data Resolution Helpers ──────────────────────────────

    def _get_vessel(self, vessel_id: int) -> Optional[Dict[str, Any]]:
        """Resolves vessel profile from DB or canonical CSV."""
        if self.db:
            v = self.db.get(VesselProfile, vessel_id)
            if v:
                vclass_name = v.vessel_class.name if v.vessel_class else "UNKNOWN"
                return {
                    "id": v.id,
                    "name": v.name,
                    "vessel_class": vclass_name,
                    "vessel_class_id": v.vessel_class_id,
                    "dwt": v.dwt,
                    "cargo_capacity": v.cargo_capacity,
                    "draft": v.draft,
                    "loa": v.loa,
                    "beam": v.beam,
                    "speed_laden": v.speed_laden or 12.5,
                    "speed_ballast": v.speed_ballast or 13.0,
                    "consumption_laden": v.consumption_laden or 20.0,
                    "consumption_ballast": v.consumption_ballast or 16.0,
                    "daily_operating_cost": getattr(v, "daily_operating_cost", 7500.0) or 7500.0,
                }

        # Fallback to vessels.csv
        csv_file = self.package_dir / "vessels" / "vessels.csv"
        if csv_file.exists():
            with open(csv_file, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if int(row.get("id", 0)) == vessel_id:
                        return {
                            "id": int(row["id"]),
                            "name": row.get("name", f"Vessel {vessel_id}"),
                            "vessel_class": row.get("vessel_class", "PANAMAX"),
                            "vessel_class_id": int(row.get("vessel_class_id", 1)),
                            "dwt": float(row.get("dwt", 75000.0)),
                            "cargo_capacity": float(row.get("cargo_capacity", 70000.0)),
                            "draft": float(row.get("draft", 13.5)),
                            "loa": float(row.get("loa", 225.0)),
                            "beam": float(row.get("beam", 32.2)),
                            "speed_laden": float(row.get("speed_laden", 12.5)),
                            "speed_ballast": float(row.get("speed_ballast", 13.0)),
                            "consumption_laden": float(row.get("consumption_laden", 20.0)),
                            "consumption_ballast": float(row.get("consumption_ballast", 16.0)),
                            "daily_operating_cost": float(row.get("daily_operating_cost", 7500.0)),
                        }
        return None

    def _get_all_vessels(self) -> List[Dict[str, Any]]:
        """Resolves all fleet vessels."""
        vessels = []
        if self.db:
            db_vessels = self.db.query(VesselProfile).all()
            for v in db_vessels:
                vclass_name = v.vessel_class.name if v.vessel_class else "UNKNOWN"
                vessels.append({
                    "id": v.id,
                    "name": v.name,
                    "vessel_class": vclass_name,
                    "vessel_class_id": v.vessel_class_id,
                    "dwt": v.dwt,
                    "cargo_capacity": v.cargo_capacity,
                    "draft": v.draft,
                    "loa": v.loa,
                    "beam": v.beam,
                    "speed_laden": v.speed_laden or 12.5,
                    "speed_ballast": v.speed_ballast or 13.0,
                    "consumption_laden": v.consumption_laden or 20.0,
                    "consumption_ballast": v.consumption_ballast or 16.0,
                    "daily_operating_cost": getattr(v, "daily_operating_cost", 7500.0) or 7500.0,
                })
            if vessels:
                return sorted(vessels, key=lambda x: x["id"])

        csv_file = self.package_dir / "vessels" / "vessels.csv"
        if csv_file.exists():
            with open(csv_file, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    vessels.append({
                        "id": int(row["id"]),
                        "name": row.get("name", f"Vessel {row['id']}"),
                        "vessel_class": row.get("vessel_class", "PANAMAX"),
                        "vessel_class_id": int(row.get("vessel_class_id", 1)),
                        "dwt": float(row.get("dwt", 75000.0)),
                        "cargo_capacity": float(row.get("cargo_capacity", 70000.0)),
                        "draft": float(row.get("draft", 13.5)),
                        "loa": float(row.get("loa", 225.0)),
                        "beam": float(row.get("beam", 32.2)),
                        "speed_laden": float(row.get("speed_laden", 12.5)),
                        "speed_ballast": float(row.get("speed_ballast", 13.0)),
                        "consumption_laden": float(row.get("consumption_laden", 20.0)),
                        "consumption_ballast": float(row.get("consumption_ballast", 16.0)),
                        "daily_operating_cost": float(row.get("daily_operating_cost", 7500.0)),
                    })
        return sorted(vessels, key=lambda x: x["id"])

    def _get_vessel_position(self, vessel_id: int) -> Dict[str, Any]:
        """Resolves current position and availability date of vessel."""
        pos_csv = self.package_dir / "vessel_positions" / "vessel_positions.csv"
        if pos_csv.exists():
            with open(pos_csv, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if int(row.get("vessel_profile_id", 0)) == vessel_id:
                        avail_raw = row.get("available_at", "2026-09-05 00:00:00")
                        avail_dt = datetime.fromisoformat(avail_raw)
                        return {
                            "available_at": avail_dt,
                            "location_port_id": int(row.get("location_port_id", 1)),
                            "location_description": row.get("location_description", "At sea / port"),
                            "confidence": float(row.get("confidence", 0.95)),
                        }

        # Fallback default: available at Paradip (port 1) on 2026-09-05
        return {
            "available_at": datetime(2026, 9, 5, 0, 0, 0),
            "location_port_id": 1,
            "location_description": "Default initial operational anchorage",
            "confidence": 0.90,
        }

    def _get_vessel_commitments(self, vessel_id: int) -> List[Dict[str, Any]]:
        """Resolves confirmed future commitments for vessel."""
        commitments = []
        comm_csv = self.package_dir / "vessel_positions" / "vessel_commitments.csv"
        if comm_csv.exists():
            with open(comm_csv, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if int(row.get("vessel_profile_id", 0)) == vessel_id:
                        start_dt = datetime.fromisoformat(row["commitment_start"])
                        end_dt = datetime.fromisoformat(row["commitment_end"]) if row.get("commitment_end") else None
                        commitments.append({
                            "id": int(row["id"]),
                            "vessel_profile_id": vessel_id,
                            "commitment_start": start_dt,
                            "commitment_end": end_dt,
                            "route_description": row.get("route_description", "Confirmed Fixture"),
                            "status": row.get("status", "CONFIRMED"),
                            "is_immutable": row.get("is_immutable", "True").lower() == "true",
                        })
        return sorted(commitments, key=lambda x: x["commitment_start"])

    def _get_cargo(self, cargo_id: int) -> Optional[Dict[str, Any]]:
        """Resolves cargo requirement details."""
        if self.db:
            parcel = self.db.get(CargoParcel, cargo_id)
            if parcel:
                return {
                    "id": parcel.id,
                    "commodity": parcel.commodity,
                    "volume_mt": parcel.volume_mt,
                    "origin_port_id": parcel.origin_port_id,
                    "destination_port_id": parcel.destination_port_id,
                    "loading_window_start": parcel.loading_window_start or datetime(2026, 9, 15),
                    "loading_window_end": parcel.loading_window_end or datetime(2026, 9, 22),
                    "delivery_deadline": parcel.delivery_deadline or datetime(2026, 10, 15),
                    "tolerance_pct": parcel.tolerance_pct or 5.0,
                }

        cargo_csv = self.package_dir / "cargo" / "cargo_requirements.csv"
        if cargo_csv.exists():
            with open(cargo_csv, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if int(row.get("id", 0)) == cargo_id:
                        start_str = row.get("loading_window_start", "2026-09-15 00:00:00")
                        end_str = row.get("loading_window_end", "2026-09-22 23:59:59")
                        dl_str = row.get("delivery_deadline", "2026-10-15 23:59:59")
                        return {
                            "id": int(row["id"]),
                            "commodity": row.get("commodity", "BULK_CARGO"),
                            "volume_mt": float(row.get("volume_mt", 60000.0)),
                            "origin_port_id": int(row.get("origin_port_id", 1)),
                            "destination_port_id": int(row.get("destination_port_id", 2)),
                            "loading_window_start": datetime.fromisoformat(start_str),
                            "loading_window_end": datetime.fromisoformat(end_str),
                            "delivery_deadline": datetime.fromisoformat(dl_str),
                            "tolerance_pct": float(row.get("tolerance_pct", 5.0)),
                        }
        return None

    def _get_all_cargos(self) -> List[Dict[str, Any]]:
        """Resolves all cargo requirements."""
        cargos = []
        cargo_csv = self.package_dir / "cargo" / "cargo_requirements.csv"
        if cargo_csv.exists():
            with open(cargo_csv, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    start_str = row.get("loading_window_start", "2026-09-15 00:00:00")
                    end_str = row.get("loading_window_end", "2026-09-22 23:59:59")
                    dl_str = row.get("delivery_deadline", "2026-10-15 23:59:59")
                    cargos.append({
                        "id": int(row["id"]),
                        "commodity": row.get("commodity", "BULK_CARGO"),
                        "volume_mt": float(row.get("volume_mt", 60000.0)),
                        "origin_port_id": int(row.get("origin_port_id", 1)),
                        "destination_port_id": int(row.get("destination_port_id", 2)),
                        "loading_window_start": datetime.fromisoformat(start_str),
                        "loading_window_end": datetime.fromisoformat(end_str),
                        "delivery_deadline": datetime.fromisoformat(dl_str),
                        "tolerance_pct": float(row.get("tolerance_pct", 5.0)),
                    })
        return sorted(cargos, key=lambda x: x["id"])

    def _get_port_coords(self, port_id: int) -> Optional[tuple[float, float]]:
        """Returns (latitude, longitude) for port."""
        PORT_COORDS = {
            1: (20.26, 86.67),   # Paradip
            2: (20.80, 86.97),   # Dhamra
            3: (14.25, 80.13),   # Krishnapatnam
            4: (13.26, 80.33),   # Ennore
            6: (-20.31, 118.58), # Port Hedland
            7: (-32.93, 151.78), # Newcastle
            8: (-21.28, 149.30), # Hay Point
            9: (-0.50, 117.15),  # Samarinda
            11: (-28.78, 32.04), # Richards Bay
            13: (1.29, 103.85),  # Singapore
        }
        return PORT_COORDS.get(port_id, (15.0, 85.0))

    def _get_port_name(self, port_id: int) -> str:
        """Returns port name."""
        PORT_NAMES = {
            1: "Paradip",
            2: "Dhamra",
            3: "Krishnapatnam",
            4: "Ennore",
            6: "Port Hedland",
            7: "Newcastle",
            8: "Hay Point",
            9: "Samarinda",
            11: "Richards Bay",
            13: "Singapore",
        }
        return PORT_NAMES.get(port_id, f"Port {port_id}")

    # ── Phase 6 Public Methods ────────────────────────────────────────

    def get_fleet_employment_overview(self, as_of_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Returns high-level fleet employment status counts:
        Total Vessels, Available, Committed, Idle, Alternative Candidates.
        """
        eval_date = as_of_date or DEFAULT_AS_OF_DATE
        all_vessels = self._get_all_vessels()

        available_count = 0
        committed_count = 0
        idle_count = 0

        for v in all_vessels:
            commitments = self._get_vessel_commitments(v["id"])
            pos = self._get_vessel_position(v["id"])
            avail_dt = pos["available_at"]

            # Check if active commitment exists during evaluation date
            is_active_comm = any(
                c["commitment_start"] <= eval_date <= (c["commitment_end"] or eval_date + timedelta(days=30))
                for c in commitments
            )

            if is_active_comm:
                committed_count += 1
            elif avail_dt <= eval_date:
                available_count += 1
                idle_count += 1
            else:
                committed_count += 1

        return {
            "as_of_date": eval_date.isoformat(),
            "total_vessels": len(all_vessels),
            "available_vessels": available_count,
            "committed_vessels": committed_count,
            "idle_vessels": idle_count,
            "alternative_candidates_generated": len(all_vessels) * 3,  # Candidate search space
            "provenance": {
                "package_id": "demo-v1",
                "data_mode": "OFFLINE_DEMO",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    def get_vessel_employment_status(
        self, vessel_id: int, as_of_date: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """Returns availability and known commitment details for a vessel."""
        v = self._get_vessel(vessel_id)
        if not v:
            return None

        eval_date = as_of_date or DEFAULT_AS_OF_DATE
        pos = self._get_vessel_position(vessel_id)
        commitments = self._get_vessel_commitments(vessel_id)

        # Active commitment during evaluation date
        active_comm = None
        for c in commitments:
            c_start = c["commitment_start"]
            c_end = c["commitment_end"] or c_start + timedelta(days=30)
            if c_start <= eval_date <= c_end:
                active_comm = c
                break

        # Next upcoming commitment
        next_comm = None
        for c in commitments:
            if c["commitment_start"] > eval_date:
                if next_comm is None or c["commitment_start"] < next_comm["commitment_start"]:
                    next_comm = c

        return {
            "vessel_id": v["id"],
            "vessel_name": v["name"],
            "vessel_class": v["vessel_class"],
            "current_location_port_id": pos["location_port_id"],
            "current_location_name": self._get_port_name(pos["location_port_id"]),
            "available_at": pos["available_at"].isoformat(),
            "has_active_commitment": active_comm is not None,
            "active_commitment": {
                "id": active_comm["id"],
                "description": active_comm["route_description"],
                "commitment_start": active_comm["commitment_start"].isoformat(),
                "commitment_end": active_comm["commitment_end"].isoformat() if active_comm.get("commitment_end") else None,
            } if active_comm else None,
            "next_commitment": {
                "id": next_comm["id"],
                "description": next_comm["route_description"],
                "commitment_start": next_comm["commitment_start"].isoformat(),
                "commitment_end": next_comm["commitment_end"].isoformat() if next_comm.get("commitment_end") else None,
            } if next_comm else None,
        }

    def get_vessel_timeline(
        self, vessel_id: int, as_of_date: Optional[datetime] = None, horizon_days: int = 45
    ) -> Dict[str, Any]:
        """Returns structured chronological timeline events for a vessel."""
        v = self._get_vessel(vessel_id)
        if not v:
            return {"vessel_id": vessel_id, "events": []}

        eval_date = as_of_date or DEFAULT_AS_OF_DATE
        pos = self._get_vessel_position(vessel_id)
        commitments = self._get_vessel_commitments(vessel_id)
        horizon_end = eval_date + timedelta(days=horizon_days)

        events = []

        # Event: Availability Point
        avail_dt = pos["available_at"]
        events.append({
            "event_type": "AVAILABLE",
            "title": f"Available at {self._get_port_name(pos['location_port_id'])}",
            "start_time": avail_dt.isoformat(),
            "end_time": (avail_dt + timedelta(days=1)).isoformat(),
            "color": "#38bdf8",
            "details": pos["location_description"],
        })

        # Events: Commitments
        for c in commitments:
            c_start = c["commitment_start"]
            c_end = c["commitment_end"] or c_start + timedelta(days=14)
            if c_start <= horizon_end:
                events.append({
                    "event_type": "COMMITTED",
                    "title": c["route_description"],
                    "start_time": c_start.isoformat(),
                    "end_time": c_end.isoformat(),
                    "color": "#fb923c",
                    "details": f"Status: {c['status']} | Immutable Boundary",
                })

        # Events: Idle gaps
        idle_assessment = self.assess_vessel_idle_state(vessel_id, eval_date)
        if idle_assessment["idle_days"] > 0:
            events.append({
                "event_type": "IDLE",
                "title": f"Idle Gap ({idle_assessment['idle_days']:.1f} days)",
                "start_time": idle_assessment["window_start"],
                "end_time": idle_assessment["window_end"],
                "color": "#94a3b8",
                "details": f"Idle Cost: ${idle_assessment['idle_cost']:,.0f} ({idle_assessment['cost_source']})",
            })

        events.sort(key=lambda x: x["start_time"])
        return {
            "vessel_id": vessel_id,
            "vessel_name": v["name"],
            "vessel_class": v["vessel_class"],
            "as_of_date": eval_date.isoformat(),
            "horizon_end": horizon_end.isoformat(),
            "events": events,
        }

    def assess_vessel_idle_state(
        self, vessel_id: int, as_of_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Evaluates vessel idle window and holding cost exposure."""
        v = self._get_vessel(vessel_id)
        if not v:
            raise ValueError(f"Vessel {vessel_id} not found.")

        eval_date = as_of_date or DEFAULT_AS_OF_DATE
        pos = self._get_vessel_position(vessel_id)
        commitments = self._get_vessel_commitments(vessel_id)

        return evaluate_vessel_idle_state(
            vessel_id=vessel_id,
            vessel_name=v["name"],
            vessel_class=v["vessel_class"],
            as_of_date=eval_date,
            availability_start=pos["available_at"],
            availability_end=eval_date + timedelta(days=60),
            commitments=commitments,
            daily_operating_cost=v.get("daily_operating_cost", 7500.0),
        )

    def evaluate_employment_candidate(
        self,
        vessel_id: int,
        cargo_id: int,
        as_of_date: Optional[datetime] = None,
        employment_type: str = "ALTERNATIVE_EMPLOYMENT",
        procurement_profile_id: Optional[str] = "STANDARD_COMMERCIAL",
        persist: bool = False,
    ) -> Dict[str, Any]:
        """
        Evaluates a specific vessel-cargo alternative employment candidate.
        Integrates:
        1. Ballast Repositioning
        2. Phase 4 Feasibility Engine (physical & port checks)
        3. Phase 5 Procurement Engine (lead-time compliance)
        4. Chronological Timeline & Commitment Conflict Check
        5. Transparent Cost & Gross Contribution Economics
        """
        vessel = self._get_vessel(vessel_id)
        if not vessel:
            raise ValueError(f"Vessel {vessel_id} not found.")

        cargo = self._get_cargo(cargo_id)
        if not cargo:
            raise ValueError(f"Cargo {cargo_id} not found.")

        eval_date = as_of_date or DEFAULT_AS_OF_DATE
        pos = self._get_vessel_position(vessel_id)
        commitments = self._get_vessel_commitments(vessel_id)

        current_port_id = pos["location_port_id"]
        origin_port_id = cargo["origin_port_id"]
        dest_port_id = cargo["destination_port_id"]

        current_port_coords = self._get_port_coords(current_port_id)
        origin_port_coords = self._get_port_coords(origin_port_id)

        # 1. Ballast Repositioning Engine
        ballast_result = calculate_ballast_repositioning(
            vessel_id=vessel_id,
            current_port_id=current_port_id,
            current_port_coords=current_port_coords,
            origin_port_id=origin_port_id,
            origin_port_coords=origin_port_coords,
            availability_start=pos["available_at"],
            vessel_speed_ballast=vessel.get("speed_ballast", 13.0),
        )

        # 2. Phase 4 Feasibility Engine Handoff (Physical, Dimensions, Ports)
        feasibility_result = self.feasibility_service.evaluate_assignment(
            cargo_id=cargo_id,
            vessel_id=vessel_id,
            persist=False,
        )

        # 3. Phase 5 Procurement Engine Timing Evaluation
        proc_profile = get_procurement_profile(profile_id=procurement_profile_id)
        proc_timing = evaluate_procurement_timing(
            current_date=eval_date.date() if isinstance(eval_date, datetime) else eval_date,
            laycan_start=cargo["loading_window_start"].date(),
            laycan_end=cargo["loading_window_end"].date(),
            delivery_deadline=cargo["delivery_deadline"].date(),
            profile=proc_profile,
            min_positioning_days=ballast_result["ballast_days"],
        )

        # 4. Chronological Timeline & Commitment Overlap Engine
        loading_days = round(cargo["volume_mt"] / 15000.0, 1)  # 15,000 MT/day load rate
        discharge_days = round(cargo["volume_mt"] / 12000.0, 1) # 12,000 MT/day discharge rate
        sailing_days = round(feasibility_result["timing"].get("sailing_days", 10.0), 1)

        timeline_result = validate_employment_timeline(
            vessel_id=vessel_id,
            availability_start=pos["available_at"],
            availability_end=eval_date + timedelta(days=60),
            ballast_days=ballast_result["ballast_days"],
            loading_window_start=cargo["loading_window_start"],
            loading_window_end=cargo["loading_window_end"],
            loading_days=loading_days,
            sailing_days=sailing_days,
            discharge_days=discharge_days,
            delivery_deadline=cargo["delivery_deadline"],
            commitments=commitments,
        )

        # 5. Determine Overall Candidate Admissibility
        failed_reasons = []
        primary_reason_code = None
        primary_reason_desc = None

        # Check 5a: Phase 4 Feasibility
        if not feasibility_result["is_feasible"]:
            failed_reasons.append(feasibility_result.get("primary_reason_code") or "PHYSICAL_CONSTRAINT_FAILED")
            primary_reason_code = feasibility_result.get("primary_reason_code")
            primary_reason_desc = feasibility_result.get("primary_reason_description")

        # Check 5b: Timeline & Commitments
        if not timeline_result["is_timeline_feasible"]:
            failed_reasons.extend(timeline_result["reason_codes"])
            if not primary_reason_code:
                primary_reason_code = timeline_result["primary_reason_code"]
                primary_reason_desc = describe_reason_code(primary_reason_code)

        # Check 5c: Procurement Timing
        if not proc_timing["is_timing_feasible"]:
            failed_reasons.append(EmploymentReasonCode.PROCUREMENT_TIMING_FAILED.value)
            if not primary_reason_code:
                primary_reason_code = EmploymentReasonCode.PROCUREMENT_TIMING_FAILED.value
                primary_reason_desc = (
                    f"Procurement lead time ({proc_profile.minimum_lead_time_days:.1f}d) exceeds "
                    f"available window before laycan start."
                )

        is_admissible = (len(failed_reasons) == 0)

        if is_admissible:
            primary_reason_code = EmploymentReasonCode.EMPLOYMENT_FEASIBLE.value
            primary_reason_desc = describe_reason_code(EmploymentReasonCode.EMPLOYMENT_FEASIBLE)
            status_str = "FEASIBLE"
            opt_status = "READY_FOR_OPTIMIZATION"
        else:
            status_str = "INFEASIBLE"
            opt_status = "REJECTED"

        # 6. Transparent Economics & Contribution Calculation
        benchmark_freight = 19.50  # USD/MT default proxy rate
        econ_result = calculate_employment_economics(
            volume_mt=cargo["volume_mt"],
            freight_rate_per_mt=benchmark_freight,
            ballast_days=ballast_result["ballast_days"],
            sailing_days=sailing_days,
            loading_days=loading_days,
            discharge_days=discharge_days,
            idle_days=timeline_result["duration_breakdown"]["idle_before_days"] + timeline_result["duration_breakdown"]["idle_after_days"],
            daily_operating_cost=vessel.get("daily_operating_cost", 7500.0),
            daily_idle_rate=vessel.get("daily_operating_cost", 7500.0),
        )

        candidate_id = f"EMP-V{vessel_id:02d}-C{cargo_id:02d}-{employment_type[:4]}"

        result_payload = {
            "candidate_id": candidate_id,
            "vessel_id": vessel_id,
            "vessel_name": vessel["name"],
            "vessel_class": vessel["vessel_class"],
            "cargo_id": cargo_id,
            "cargo_name": f"{cargo['commodity']} ({cargo['volume_mt']:,.0f} MT)",
            "employment_type": employment_type,
            "origin_port_id": origin_port_id,
            "origin_port_name": self._get_port_name(origin_port_id),
            "destination_port_id": dest_port_id,
            "destination_port_name": self._get_port_name(dest_port_id),
            "status": status_str,
            "optimization_status": opt_status,
            "primary_reason_code": primary_reason_code,
            "primary_reason_description": primary_reason_desc,
            "failed_reasons": failed_reasons,
            "ballast": ballast_result,
            "feasibility": {
                "is_feasible": feasibility_result["is_feasible"],
                "primary_reason_code": feasibility_result["primary_reason_code"],
                "failed_checks": feasibility_result["failed_checks"],
                "checks": feasibility_result["checks"],
            },
            "procurement": {
                "profile_id": proc_profile.profile_id,
                "lead_time_days": proc_profile.minimum_lead_time_days,
                "timing_signal": proc_timing["timing_signal"],
                "remaining_decision_window_days": proc_timing["remaining_decision_window_days"],
                "is_timing_feasible": proc_timing["is_timing_feasible"],
            },
            "timeline": timeline_result,
            "economics": econ_result,
            "provenance": {
                "package_id": "demo-v1",
                "data_mode": "OFFLINE_DEMO",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "feasibility_engine_ref": "Phase 4 FeasibilityService",
                "procurement_engine_ref": "Phase 5 ProcurementService",
            },
        }

        # Persist to database if requested
        if persist and self.db:
            try:
                rec = EmploymentOpportunity(
                    candidate_id=candidate_id,
                    vessel_id=vessel_id,
                    cargo_id=cargo_id,
                    employment_type=employment_type,
                    origin_port_id=origin_port_id,
                    destination_port_id=dest_port_id,
                    availability_start=pos["available_at"],
                    availability_end=eval_date + timedelta(days=60),
                    employment_start=datetime.fromisoformat(timeline_result["timing_milestones"]["loading_start"]),
                    employment_end=datetime.fromisoformat(timeline_result["timing_milestones"]["discharge_end"]),
                    delivery_deadline=cargo["delivery_deadline"],
                    ballast_distance_nm=ballast_result["ballast_distance_nm"],
                    ballast_days=ballast_result["ballast_days"],
                    voyage_days=timeline_result["duration_breakdown"]["total_voyage_days"],
                    idle_days=timeline_result["duration_breakdown"]["idle_before_days"],
                    status=status_str,
                    primary_reason_code=primary_reason_code,
                    primary_reason_description=primary_reason_desc,
                    optimization_status=opt_status,
                    economic_summary=econ_result,
                    timeline_detail=timeline_result,
                    feasibility_detail=result_payload["feasibility"],
                    procurement_detail=result_payload["procurement"],
                    provenance=result_payload["provenance"],
                    created_at=datetime.now(timezone.utc),
                    runtime_mode=RuntimeModeEnum.OFFLINE_DEMO,
                )
                self.db.add(rec)
                self.db.commit()
            except Exception as e:
                logger.warning(f"Failed to persist employment opportunity: {e}")
                if self.db:
                    self.db.rollback()

        return result_payload

    def generate_alternative_candidates(
        self, vessel_id: int, as_of_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Generates alternative employment candidates for a vessel across all
        canonical cargo demand requirements (multi-cargo awareness).
        Does NOT perform global allocation or ranking.
        """
        all_cargos = self._get_all_cargos()
        candidates = []
        for c in all_cargos:
            cand = self.evaluate_employment_candidate(
                vessel_id=vessel_id,
                cargo_id=c["id"],
                as_of_date=as_of_date,
                employment_type="ALTERNATIVE_EMPLOYMENT",
                persist=False,
            )
            candidates.append(cand)
        return candidates

    def get_all_opportunities(self) -> List[Dict[str, Any]]:
        """Returns all canonical employment opportunities (cargo demand requirements)."""
        cargos = self._get_all_cargos()
        opps = []
        for c in cargos:
            opps.append({
                "opportunity_id": f"OPP-C{c['id']:02d}",
                "cargo_id": c["id"],
                "commodity": c["commodity"],
                "volume_mt": c["volume_mt"],
                "origin_port_id": c["origin_port_id"],
                "origin_port_name": self._get_port_name(c["origin_port_id"]),
                "destination_port_id": c["destination_port_id"],
                "destination_port_name": self._get_port_name(c["destination_port_id"]),
                "laycan_start": c["loading_window_start"].isoformat(),
                "laycan_end": c["loading_window_end"].isoformat(),
                "delivery_deadline": c["delivery_deadline"].isoformat(),
                "tolerance_pct": c["tolerance_pct"],
                "status": "OPEN",
            })
        return opps

    def get_all_idle_assessments(
        self, as_of_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Evaluates idle state across all fleet vessels."""
        eval_date = as_of_date or DEFAULT_AS_OF_DATE
        all_vessels = self._get_all_vessels()
        assessments = []
        total_idle_days = 0.0
        total_idle_cost = 0.0
        idle_count = 0

        for v in all_vessels:
            assessment = self.assess_vessel_idle_state(v["id"], as_of_date=eval_date)
            assessments.append(assessment)
            total_idle_days += assessment["idle_days"]
            total_idle_cost += assessment["idle_cost"]
            if assessment["is_idle"]:
                idle_count += 1

        return {
            "as_of_date": eval_date.isoformat(),
            "total_vessels_assessed": len(all_vessels),
            "idle_vessels_count": idle_count,
            "active_vessels_count": len(all_vessels) - idle_count,
            "total_idle_days": round(total_idle_days, 1),
            "total_idle_cost": round(total_idle_cost, 2),
            "assessments": assessments,
            "provenance": {
                "package_id": "demo-v1",
                "data_mode": "OFFLINE_DEMO",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    def get_candidates_matrix(
        self,
        vessel_id: Optional[int] = None,
        cargo_id: Optional[int] = None,
        ready_only: bool = False,
        as_of_date: Optional[datetime] = None,
        persist: bool = False,
    ) -> Dict[str, Any]:
        """
        Generates candidate pairs across fleet and opportunities with optional filters.
        Strictly candidate generation; no global optimization or ranking.
        """
        eval_date = as_of_date or DEFAULT_AS_OF_DATE
        all_vessels = [self._get_vessel(vessel_id)] if vessel_id else self._get_all_vessels()
        all_cargos = [self._get_cargo(cargo_id)] if cargo_id else self._get_all_cargos()

        all_vessels = [v for v in all_vessels if v is not None]
        all_cargos = [c for c in all_cargos if c is not None]

        candidates = []
        feasible_count = 0
        infeasible_count = 0

        for v in all_vessels:
            for c in all_cargos:
                cand = self.evaluate_employment_candidate(
                    vessel_id=v["id"],
                    cargo_id=c["id"],
                    as_of_date=eval_date,
                    employment_type="ALTERNATIVE_EMPLOYMENT",
                    persist=persist,
                )
                if cand["status"] == "FEASIBLE":
                    feasible_count += 1
                else:
                    infeasible_count += 1

                if ready_only and cand["status"] != "FEASIBLE":
                    continue

                candidates.append(cand)

        return {
            "as_of_date": eval_date.isoformat(),
            "total_evaluated": len(all_vessels) * len(all_cargos),
            "feasible_count": feasible_count,
            "infeasible_count": infeasible_count,
            "returned_count": len(candidates),
            "candidates": candidates,
            "governing_boundary": (
                "Candidate Generation != Global Allocation. "
                "Phase 6 provides candidate generation and admissibility filtering. "
                "Global allocation is strictly deferred to Phase 7 MILP Optimization."
            ),
            "provenance": {
                "package_id": "demo-v1",
                "data_mode": "OFFLINE_DEMO",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    def compare_candidates(
        self,
        vessel_id: Optional[int] = None,
        cargo_id: Optional[int] = None,
        as_of_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Returns multi-candidate side-by-side comparison.
        Strictly objective metrics; no ranking or winner declaration.
        """
        eval_date = as_of_date or DEFAULT_AS_OF_DATE
        res = self.get_candidates_matrix(
            vessel_id=vessel_id,
            cargo_id=cargo_id,
            ready_only=False,
            as_of_date=eval_date,
            persist=False,
        )

        comp_type = "BY_VESSEL" if vessel_id and not cargo_id else ("BY_OPPORTUNITY" if cargo_id and not vessel_id else "MATRIX")

        return {
            "comparison_type": comp_type,
            "filter_vessel_id": vessel_id,
            "filter_cargo_id": cargo_id,
            "as_of_date": eval_date.isoformat(),
            "candidate_count": len(res["candidates"]),
            "candidates": res["candidates"],
            "advisory_note": (
                "Candidate Generation != Global Allocation. "
                "All presented options are strictly non-ranked alternatives for trade-off inspection. "
                "No vessel is marked winner or optimal. Global fleet allocation requires Phase 7 MILP Optimization."
            ),
            "provenance": res["provenance"],
        }

