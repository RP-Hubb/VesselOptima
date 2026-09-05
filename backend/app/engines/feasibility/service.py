"""
VesselOptima — Feasibility Engine: Master Service Orchestrator

Coordinates operational, physical, and temporal feasibility checks.
Strict adherence to: Feasibility != Optimization (Prediction != Decision).
No economic ranking is performed.
Follows Sections 1, 2, 4, 19, 22, 23, 25 of the Phase 4 Specification.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.engines.feasibility.port_checks import evaluate_port_constraints
from app.engines.feasibility.reason_codes import (
    FeasibilityReasonCode,
    describe_reason_code,
)
from app.engines.feasibility.schedule_checks import (
    calculate_great_circle_distance_nm,
    evaluate_schedule_and_commitments,
)
from app.engines.feasibility.vessel_checks import (
    check_vessel_capacity,
    check_vessel_class_suitability,
)
from app.models.domain import (
    CargoParcel,
    FeasibilityCheck,
    Port,
    PortConstraint,
    Route,
    RuntimeModeEnum,
    VesselAvailabilityEvent,
    VesselClass,
    VesselCommitment,
    VesselProfile,
)

logger = get_logger("engines.feasibility.service")


class FeasibilityService:
    """
    Feasibility engine evaluating operational, physical, and temporal suitability.
    """

    def __init__(self, db: Optional[Session] = None, package_dir: Optional[Path] = None):
        self.db = db
        if package_dir:
            self.package_dir = package_dir
        else:
            repo_root = Path(__file__).resolve().parents[4]
            self.package_dir = repo_root / "data" / "offline" / "packages" / "demo-v1"

    # ── Single Assignment Evaluation ──────────────────────────────────────

    def evaluate_assignment(
        self,
        cargo_id: int,
        vessel_id: int,
        route_id: Optional[int] = None,
        persist: bool = False,
    ) -> Dict[str, Any]:
        """
        Answers: 'Can this vessel perform this cargo movement under the specified
        operational, physical, and temporal constraints?'

        Returns:
            Structured dictionary with:
            is_feasible: bool
            primary_reason_code: Optional[str]
            reason_codes: List[str]
            failed_checks: List[str]
            checks: Dict[str, Any]
            warnings: List[str]
            timing: Dict[str, Any]
            evidence: Dict[str, Any]
            provenance: Dict[str, Any]
        """
        logger.info(f"Evaluating feasibility: cargo={cargo_id}, vessel={vessel_id}, route={route_id}")

        failed_checks: List[str] = []
        reason_codes: List[FeasibilityReasonCode] = []
        checks: Dict[str, Any] = {}
        warnings: List[str] = []
        evidence: Dict[str, Any] = {}
        timing: Dict[str, Any] = {}

        # 1. Resolve Entities
        cargo = self._get_cargo(cargo_id)
        if not cargo:
            return self._build_entity_missing_result(
                "cargo", cargo_id, FeasibilityReasonCode.CARGO_NOT_FOUND
            )

        vessel = self._get_vessel(vessel_id)
        if not vessel:
            return self._build_entity_missing_result(
                "vessel", vessel_id, FeasibilityReasonCode.VESSEL_NOT_FOUND
            )

        vessel_class = self._get_vessel_class(vessel.get("vessel_class_id"))

        # Resolve Route
        route = self._resolve_route(
            cargo["origin_port_id"],
            cargo["destination_port_id"],
            route_id=route_id,
        )
        if not route:
            reason_codes.append(FeasibilityReasonCode.ROUTE_NOT_FOUND)
            failed_checks.append("route_existence")
            checks["route_existence"] = {
                "status": "FAIL",
                "message": f"No valid maritime route connects origin port {cargo['origin_port_id']} to destination port {cargo['destination_port_id']}.",
            }
            return {
                "is_feasible": False,
                "primary_reason_code": FeasibilityReasonCode.ROUTE_NOT_FOUND.value,
                "primary_reason_description": describe_reason_code(FeasibilityReasonCode.ROUTE_NOT_FOUND),
                "reason_codes": [r.value for r in reason_codes],
                "failed_checks": failed_checks,
                "cargo_id": cargo_id,
                "vessel_id": vessel_id,
                "route_id": route_id,
                "checks": checks,
                "warnings": warnings,
                "timing": {},
                "evidence": {},
                "provenance": self._get_provenance(),
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
            }

        checks["route_existence"] = {
            "status": "PASS",
            "route_id": route["id"],
            "route_name": route["name"],
            "distance_nm": route["distance_nm"],
        }

        # 2. Vessel Capacity Check
        cap_pass, cap_code, cap_ev, cap_warn = check_vessel_capacity(
            vessel_capacity=vessel["cargo_capacity"],
            cargo_volume=cargo["volume_mt"],
            tolerance_pct=cargo.get("tolerance_pct", 0.0),
        )
        checks["capacity"] = cap_ev
        evidence["capacity"] = cap_ev
        if not cap_pass and cap_code:
            failed_checks.append("capacity")
            reason_codes.append(cap_code)
        if cap_warn:
            warnings.append(cap_warn)

        # 3. Vessel Class Suitability Check
        class_pass, class_code, class_ev, class_warn = check_vessel_class_suitability(
            vessel_class_name=vessel_class.get("name") if vessel_class else None,
            cargo_volume=cargo["volume_mt"],
            commodity=cargo["commodity"],
            vessel_capacity=vessel["cargo_capacity"],
        )
        checks["vessel_class_suitability"] = class_ev
        evidence["vessel_class"] = class_ev
        if not class_pass and class_code:
            failed_checks.append("vessel_class_suitability")
            reason_codes.append(class_code)
        if class_warn:
            warnings.append(class_warn)

        # 4. Origin Port Physical Constraints
        origin_port = self._get_port(cargo["origin_port_id"])
        origin_constraints = self._get_port_constraints(cargo["origin_port_id"])
        origin_result = evaluate_port_constraints(
            port_id=cargo["origin_port_id"],
            port_name=origin_port.get("name", f"Port {cargo['origin_port_id']}"),
            role="ORIGIN",
            vessel_draft=vessel["draft"],
            vessel_loa=vessel["loa"],
            vessel_beam=vessel["beam"],
            constraints=origin_constraints,
        )
        checks.update(origin_result.checks)
        if not origin_result.is_pass:
            failed_checks.extend(origin_result.failed_checks)
            for r in origin_result.reason_codes:
                if r not in reason_codes:
                    reason_codes.append(r)
        warnings.extend(origin_result.warnings)

        # 5. Destination Port Physical Constraints
        dest_port = self._get_port(cargo["destination_port_id"])
        dest_constraints = self._get_port_constraints(cargo["destination_port_id"])
        dest_result = evaluate_port_constraints(
            port_id=cargo["destination_port_id"],
            port_name=dest_port.get("name", f"Port {cargo['destination_port_id']}"),
            role="DESTINATION",
            vessel_draft=vessel["draft"],
            vessel_loa=vessel["loa"],
            vessel_beam=vessel["beam"],
            constraints=dest_constraints,
        )
        checks.update(dest_result.checks)
        if not dest_result.is_pass:
            failed_checks.extend(dest_result.failed_checks)
            for r in dest_result.reason_codes:
                if r not in reason_codes:
                    reason_codes.append(r)
        warnings.extend(dest_result.warnings)

        # 6. Vessel Availability, Positioning & Schedule Checks
        availability = self._get_vessel_availability(vessel_id)
        available_at = availability.get("available_at")
        current_port_id = availability.get("location_port_id")
        current_port = self._get_port(current_port_id) if current_port_id else None

        current_port_coords = (
            (current_port["latitude"], current_port["longitude"])
            if current_port and current_port.get("latitude") and current_port.get("longitude")
            else None
        )
        origin_port_coords = (
            (origin_port["latitude"], origin_port["longitude"])
            if origin_port and origin_port.get("latitude") and origin_port.get("longitude")
            else None
        )

        # Direct positioning route if available
        direct_positioning_dist = None
        if current_port_id and current_port_id != cargo["origin_port_id"]:
            pos_route = self._find_route_by_ports(current_port_id, cargo["origin_port_id"])
            if pos_route:
                direct_positioning_dist = pos_route["distance_nm"]

        commitments = self._get_vessel_commitments(vessel_id)

        schedule_result = evaluate_schedule_and_commitments(
            vessel_id=vessel_id,
            vessel_speed_laden=vessel.get("speed_laden", 12.5),
            vessel_speed_ballast=vessel.get("speed_ballast", 13.0),
            available_at=available_at,
            current_port_id=current_port_id,
            current_port_coords=current_port_coords,
            origin_port_id=cargo["origin_port_id"],
            origin_port_coords=origin_port_coords,
            loading_window_start=cargo["loading_window_start"],
            loading_window_end=cargo["loading_window_end"],
            delivery_deadline=cargo["delivery_deadline"],
            route_distance_nm=route["distance_nm"],
            cargo_volume_mt=cargo["volume_mt"],
            commitments=commitments,
            direct_positioning_distance_nm=direct_positioning_dist,
        )

        checks.update(schedule_result.checks)
        timing.update(schedule_result.timing)
        if not schedule_result.is_pass:
            failed_checks.extend(schedule_result.failed_checks)
            for r in schedule_result.reason_codes:
                if r not in reason_codes:
                    reason_codes.append(r)
        warnings.extend(schedule_result.warnings)

        # 7. Final Verdict
        is_feasible = (len(failed_checks) == 0)
        primary_reason = reason_codes[0] if reason_codes else None
        primary_reason_str = primary_reason.value if primary_reason else None
        primary_desc = describe_reason_code(primary_reason) if primary_reason else None

        result_dict = {
            "is_feasible": is_feasible,
            "cargo_id": cargo_id,
            "cargo_name": f"{cargo['commodity']} ({cargo['volume_mt']:,.0f} MT)",
            "vessel_id": vessel_id,
            "vessel_name": vessel.get("name", f"Vessel {vessel_id}"),
            "vessel_class": vessel_class.get("name", "UNKNOWN") if vessel_class else "UNKNOWN",
            "route_id": route["id"],
            "route_name": route["name"],
            "origin_port": origin_port.get("name", "Unknown Origin"),
            "destination_port": dest_port.get("name", "Unknown Destination"),
            "primary_reason_code": primary_reason_str,
            "primary_reason_description": primary_desc,
            "reason_codes": [r.value for r in reason_codes],
            "failed_checks": failed_checks,
            "checks": checks,
            "warnings": warnings,
            "timing": timing,
            "evidence": evidence,
            "provenance": self._get_provenance(),
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

        # 8. Optional DB Persistence
        if persist and self.db:
            self._persist_evaluation(result_dict)

        return result_dict

    # ── Multi-Vessel Fleet Evaluation ────────────────────────────────────

    def evaluate_candidate_fleet(
        self,
        cargo_id: int,
        route_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Evaluates an entire candidate fleet against one cargo requirement.
        Strictly a feasibility filter. No economic ranking is performed.
        """
        all_vessels = self._list_all_vessels()
        results = []

        for v in all_vessels:
            eval_res = self.evaluate_assignment(
                cargo_id=cargo_id,
                vessel_id=v["id"],
                route_id=route_id,
                persist=False,
            )
            results.append({
                "vessel_id": v["id"],
                "vessel_name": v["name"],
                "vessel_class": eval_res["vessel_class"],
                "cargo_capacity": v["cargo_capacity"],
                "draft": v["draft"],
                "loa": v["loa"],
                "beam": v["beam"],
                "is_feasible": eval_res["is_feasible"],
                "primary_reason_code": eval_res["primary_reason_code"],
                "primary_reason_description": eval_res["primary_reason_description"],
                "failed_checks": eval_res["failed_checks"],
                "warnings_count": len(eval_res["warnings"]),
            })

        # Deterministic sorting by vessel ID (no economic score)
        results.sort(key=lambda x: x["vessel_id"])
        return results

    # ── Feasibility Matrix Evaluation ────────────────────────────────────

    def evaluate_feasibility_matrix(
        self,
        cargo_ids: Optional[List[int]] = None,
        vessel_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates a 2D matrix of (Cargo Requirements x Candidate Vessels).
        Produces status and primary reason code for each pair.
        """
        if not cargo_ids:
            all_cargos = self._list_all_cargos()
            cargo_ids = [c["id"] for c in all_cargos]

        if not vessel_ids:
            all_vessels = self._list_all_vessels()
            vessel_ids = [v["id"] for v in all_vessels]

        matrix = {}
        feasible_count = 0
        infeasible_count = 0

        for c_id in cargo_ids:
            matrix[str(c_id)] = {}
            for v_id in vessel_ids:
                res = self.evaluate_assignment(cargo_id=c_id, vessel_id=v_id)
                if res["is_feasible"]:
                    feasible_count += 1
                else:
                    infeasible_count += 1
                matrix[str(c_id)][str(v_id)] = {
                    "is_feasible": res["is_feasible"],
                    "primary_reason_code": res["primary_reason_code"],
                }

        return {
            "matrix": matrix,
            "cargo_ids": cargo_ids,
            "vessel_ids": vessel_ids,
            "summary": {
                "total_evaluations": feasible_count + infeasible_count,
                "feasible_pairs": feasible_count,
                "infeasible_pairs": infeasible_count,
            },
            "provenance": self._get_provenance(),
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── Entity Fetching Helpers (DB with Canonical CSV Fallback) ─────────

    def _get_cargo(self, cargo_id: int) -> Optional[Dict[str, Any]]:
        if self.db:
            c = self.db.query(CargoParcel).filter(CargoParcel.id == cargo_id).first()
            if c:
                return {
                    "id": c.id,
                    "commodity": c.commodity,
                    "volume_mt": float(c.volume_mt),
                    "origin_port_id": c.origin_port_id,
                    "destination_port_id": c.destination_port_id,
                    "loading_window_start": c.loading_window_start,
                    "loading_window_end": c.loading_window_end,
                    "delivery_deadline": c.delivery_deadline,
                    "tolerance_pct": float(c.tolerance_pct or 0.0),
                }

        # Fallback to CSV
        csv_file = self.package_dir / "cargo" / "cargo_requirements.csv"
        if csv_file.exists():
            with open(csv_file, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if int(row["id"]) == cargo_id:
                        return {
                            "id": int(row["id"]),
                            "commodity": row["commodity"],
                            "volume_mt": float(row["volume_mt"]),
                            "origin_port_id": int(row["origin_port_id"]),
                            "destination_port_id": int(row["destination_port_id"]),
                            "loading_window_start": datetime.fromisoformat(row["loading_window_start"]),
                            "loading_window_end": datetime.fromisoformat(row["loading_window_end"]),
                            "delivery_deadline": datetime.fromisoformat(row["delivery_deadline"]),
                            "tolerance_pct": float(row.get("tolerance_pct") or 0.0),
                        }
        return None

    def _list_all_cargos(self) -> List[Dict[str, Any]]:
        if self.db:
            cargos = self.db.query(CargoParcel).all()
            if cargos:
                return [
                    {
                        "id": c.id,
                        "commodity": c.commodity,
                        "volume_mt": float(c.volume_mt),
                        "origin_port_id": c.origin_port_id,
                        "destination_port_id": c.destination_port_id,
                        "loading_window_start": c.loading_window_start,
                        "loading_window_end": c.loading_window_end,
                        "delivery_deadline": c.delivery_deadline,
                        "tolerance_pct": float(c.tolerance_pct or 0.0),
                    }
                    for c in cargos
                ]

        csv_file = self.package_dir / "cargo" / "cargo_requirements.csv"
        results = []
        if csv_file.exists():
            with open(csv_file, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    results.append({
                        "id": int(row["id"]),
                        "commodity": row["commodity"],
                        "volume_mt": float(row["volume_mt"]),
                        "origin_port_id": int(row["origin_port_id"]),
                        "destination_port_id": int(row["destination_port_id"]),
                        "loading_window_start": datetime.fromisoformat(row["loading_window_start"]),
                        "loading_window_end": datetime.fromisoformat(row["loading_window_end"]),
                        "delivery_deadline": datetime.fromisoformat(row["delivery_deadline"]),
                        "tolerance_pct": float(row.get("tolerance_pct") or 0.0),
                    })
        return results

    def _get_vessel(self, vessel_id: int) -> Optional[Dict[str, Any]]:
        if self.db:
            v = self.db.query(VesselProfile).filter(VesselProfile.id == vessel_id).first()
            if v:
                return {
                    "id": v.id,
                    "name": v.name,
                    "vessel_class_id": v.vessel_class_id,
                    "dwt": float(v.dwt or 0.0),
                    "cargo_capacity": float(v.cargo_capacity or 0.0),
                    "draft": float(v.draft or 0.0),
                    "loa": float(v.loa or 0.0),
                    "beam": float(v.beam or 0.0),
                    "speed_laden": float(v.speed_laden or 12.5),
                    "speed_ballast": float(v.speed_ballast or 13.0),
                    "employment_control": v.employment_control.value if v.employment_control else "UNKNOWN",
                }

        csv_file = self.package_dir / "vessels" / "vessels.csv"
        if csv_file.exists():
            with open(csv_file, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if int(row["id"]) == vessel_id:
                        return {
                            "id": int(row["id"]),
                            "name": row["name"],
                            "vessel_class_id": int(row["vessel_class_id"]) if row.get("vessel_class_id") else None,
                            "dwt": float(row.get("dwt") or 0.0),
                            "cargo_capacity": float(row.get("cargo_capacity") or 0.0),
                            "draft": float(row.get("draft") or 0.0),
                            "loa": float(row.get("loa") or 0.0),
                            "beam": float(row.get("beam") or 0.0),
                            "speed_laden": float(row.get("speed_laden") or 12.5),
                            "speed_ballast": float(row.get("speed_ballast") or 13.0),
                            "employment_control": row.get("employment_control", "UNKNOWN"),
                        }
        return None

    def _list_all_vessels(self) -> List[Dict[str, Any]]:
        if self.db:
            vessels = self.db.query(VesselProfile).all()
            if vessels:
                return [
                    {
                        "id": v.id,
                        "name": v.name,
                        "vessel_class_id": v.vessel_class_id,
                        "dwt": float(v.dwt or 0.0),
                        "cargo_capacity": float(v.cargo_capacity or 0.0),
                        "draft": float(v.draft or 0.0),
                        "loa": float(v.loa or 0.0),
                        "beam": float(v.beam or 0.0),
                        "speed_laden": float(v.speed_laden or 12.5),
                        "speed_ballast": float(v.speed_ballast or 13.0),
                        "employment_control": v.employment_control.value if v.employment_control else "UNKNOWN",
                    }
                    for v in vessels
                ]

        csv_file = self.package_dir / "vessels" / "vessels.csv"
        results = []
        if csv_file.exists():
            with open(csv_file, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    results.append({
                        "id": int(row["id"]),
                        "name": row["name"],
                        "vessel_class_id": int(row["vessel_class_id"]) if row.get("vessel_class_id") else None,
                        "dwt": float(row.get("dwt") or 0.0),
                        "cargo_capacity": float(row.get("cargo_capacity") or 0.0),
                        "draft": float(row.get("draft") or 0.0),
                        "loa": float(row.get("loa") or 0.0),
                        "beam": float(row.get("beam") or 0.0),
                        "speed_laden": float(row.get("speed_laden") or 12.5),
                        "speed_ballast": float(row.get("speed_ballast") or 13.0),
                        "employment_control": row.get("employment_control", "UNKNOWN"),
                    })
        return results

    def _get_vessel_class(self, class_id: Optional[int]) -> Optional[Dict[str, Any]]:
        if not class_id:
            return None
        if self.db:
            vc = self.db.query(VesselClass).filter(VesselClass.id == class_id).first()
            if vc:
                return {
                    "id": vc.id,
                    "name": vc.name,
                    "typical_capacity_min": vc.typical_capacity_min,
                    "typical_capacity_max": vc.typical_capacity_max,
                }

        csv_file = self.package_dir / "vessel_classes" / "vessel_classes.csv"
        if csv_file.exists():
            with open(csv_file, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if int(row["id"]) == class_id:
                        return {
                            "id": int(row["id"]),
                            "name": row["name"],
                            "typical_capacity_min": float(row.get("typical_capacity_min") or 0.0),
                            "typical_capacity_max": float(row.get("typical_capacity_max") or 0.0),
                        }
        return None

    def _get_port(self, port_id: int) -> Dict[str, Any]:
        if self.db:
            p = self.db.query(Port).filter(Port.id == port_id).first()
            if p:
                return {
                    "id": p.id,
                    "name": p.name,
                    "country": p.country,
                    "unlocode": p.unlocode,
                    "latitude": float(p.latitude) if p.latitude is not None else None,
                    "longitude": float(p.longitude) if p.longitude is not None else None,
                }

        csv_file = self.package_dir / "ports" / "ports.csv"
        if csv_file.exists():
            with open(csv_file, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if int(row["id"]) == port_id:
                        return {
                            "id": int(row["id"]),
                            "name": row["name"],
                            "country": row.get("country"),
                            "unlocode": row.get("unlocode"),
                            "latitude": float(row["latitude"]) if row.get("latitude") else None,
                            "longitude": float(row["longitude"]) if row.get("longitude") else None,
                        }
        return {"id": port_id, "name": f"Port {port_id}"}

    def _get_port_constraints(self, port_id: int) -> List[Dict[str, Any]]:
        if self.db:
            pcs = self.db.query(PortConstraint).filter(PortConstraint.port_id == port_id).all()
            if pcs:
                return [
                    {
                        "rule_type": pc.rule_type,
                        "value": pc.value,
                        "unit": pc.unit,
                        "terminal": pc.terminal,
                        "berth": pc.berth,
                        "condition": pc.condition,
                    }
                    for pc in pcs
                ]

        csv_file = self.package_dir / "ports" / "port_constraints.csv"
        results = []
        if csv_file.exists():
            with open(csv_file, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if int(row["port_id"]) == port_id:
                        results.append({
                            "rule_type": row["rule_type"],
                            "value": float(row["value"]),
                            "unit": row.get("unit", "M"),
                            "terminal": row.get("terminal"),
                            "berth": row.get("berth"),
                            "condition": row.get("condition"),
                        })
        return results

    def _resolve_route(
        self,
        origin_port_id: int,
        destination_port_id: int,
        route_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Finds route by ID or origin/destination port pair."""
        if route_id is not None:
            r_dict = None
            if self.db:
                r = self.db.query(Route).filter(Route.id == route_id).first()
                if r:
                    r_dict = {
                        "id": r.id,
                        "name": r.name,
                        "origin_port_id": r.origin_port_id,
                        "destination_port_id": r.destination_port_id,
                        "distance_nm": float(r.distance_nm or 0.0),
                    }
            if not r_dict:
                csv_file = self.package_dir / "routes" / "routes.csv"
                if csv_file.exists():
                    with open(csv_file, "r", encoding="utf-8") as f:
                        for row in csv.DictReader(f):
                            if int(row["id"]) == route_id:
                                r_dict = {
                                    "id": int(row["id"]),
                                    "name": row["name"],
                                    "origin_port_id": int(row["origin_port_id"]),
                                    "destination_port_id": int(row["destination_port_id"]),
                                    "distance_nm": float(row["distance_nm"]),
                                }
                                break

            if not r_dict:
                return None

            # Verify that route endpoints correspond to the cargo's origin & destination
            if r_dict["origin_port_id"] != origin_port_id or r_dict["destination_port_id"] != destination_port_id:
                return None

            return r_dict

        return self._find_route_by_ports(origin_port_id, destination_port_id)

    def _find_route_by_ports(self, origin_id: int, dest_id: int) -> Optional[Dict[str, Any]]:
        if self.db:
            r = (
                self.db.query(Route)
                .filter(Route.origin_port_id == origin_id, Route.destination_port_id == dest_id)
                .first()
            )
            if r:
                return {
                    "id": r.id,
                    "name": r.name,
                    "origin_port_id": r.origin_port_id,
                    "destination_port_id": r.destination_port_id,
                    "distance_nm": float(r.distance_nm or 0.0),
                }

        csv_file = self.package_dir / "routes" / "routes.csv"
        if csv_file.exists():
            with open(csv_file, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if int(row["origin_port_id"]) == origin_id and int(row["destination_port_id"]) == dest_id:
                        return {
                            "id": int(row["id"]),
                            "name": row["name"],
                            "origin_port_id": int(row["origin_port_id"]),
                            "destination_port_id": int(row["destination_port_id"]),
                            "distance_nm": float(row["distance_nm"]),
                        }
        return None

    def _get_vessel_availability(self, vessel_id: int) -> Dict[str, Any]:
        if self.db:
            evt = (
                self.db.query(VesselAvailabilityEvent)
                .filter(VesselAvailabilityEvent.vessel_profile_id == vessel_id)
                .order_by(VesselAvailabilityEvent.available_at.desc())
                .first()
            )
            if evt:
                return {
                    "available_at": evt.available_at,
                    "location_port_id": evt.location_port_id,
                }

        csv_file = self.package_dir / "vessel_positions" / "vessel_positions.csv"
        if csv_file.exists():
            with open(csv_file, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if int(row["vessel_profile_id"]) == vessel_id:
                        return {
                            "available_at": datetime.fromisoformat(row["available_at"]),
                            "location_port_id": int(row["location_port_id"]) if row.get("location_port_id") else None,
                        }

        # Default fallback for demonstration if no position event recorded
        return {
            "available_at": datetime(2026, 9, 10, 0, 0, 0),
            "location_port_id": 1,
        }

    def _get_vessel_commitments(self, vessel_id: int) -> List[Dict[str, Any]]:
        if self.db:
            comms = (
                self.db.query(VesselCommitment)
                .filter(
                    VesselCommitment.vessel_profile_id == vessel_id,
                    VesselCommitment.status == "CONFIRMED",
                )
                .all()
            )
            if comms:
                return [
                    {
                        "id": c.id,
                        "commitment_start": c.commitment_start,
                        "commitment_end": c.commitment_end,
                        "route_description": c.route_description,
                    }
                    for c in comms
                ]

        csv_file = self.package_dir / "vessel_positions" / "vessel_commitments.csv"
        results = []
        if csv_file.exists():
            with open(csv_file, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if int(row["vessel_profile_id"]) == vessel_id and row.get("status", "CONFIRMED") == "CONFIRMED":
                        results.append({
                            "id": int(row["id"]),
                            "commitment_start": datetime.fromisoformat(row["commitment_start"]),
                            "commitment_end": datetime.fromisoformat(row["commitment_end"]) if row.get("commitment_end") else None,
                            "route_description": row.get("route_description", ""),
                        })
        return results

    def _persist_evaluation(self, result_dict: Dict[str, Any]) -> None:
        """Persists evaluation to database inside transaction."""
        try:
            fc = FeasibilityCheck(
                cargo_id=result_dict["cargo_id"],
                vessel_id=result_dict["vessel_id"],
                route_id=result_dict["route_id"],
                is_feasible=result_dict["is_feasible"],
                primary_reason_code=result_dict["primary_reason_code"],
                reason_codes=result_dict["reason_codes"],
                failed_checks=result_dict["failed_checks"],
                checks=result_dict["checks"],
                warnings=result_dict["warnings"],
                timing=result_dict["timing"],
                evidence=result_dict["evidence"],
                provenance=result_dict["provenance"],
                evaluated_at=datetime.fromisoformat(result_dict["evaluated_at"]),
                runtime_mode=RuntimeModeEnum.OFFLINE_DEMO,
            )
            self.db.add(fc)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to persist FeasibilityCheck: {e}")
            self.db.rollback()

    def _build_entity_missing_result(
        self, entity_name: str, entity_id: int, code: FeasibilityReasonCode
    ) -> Dict[str, Any]:
        return {
            "is_feasible": False,
            "primary_reason_code": code.value,
            "primary_reason_description": describe_reason_code(code),
            "reason_codes": [code.value],
            "failed_checks": [f"{entity_name}_resolution"],
            "cargo_id": entity_id if entity_name == "cargo" else None,
            "vessel_id": entity_id if entity_name == "vessel" else None,
            "route_id": None,
            "checks": {
                f"{entity_name}_resolution": {
                    "status": "FAIL",
                    "message": f"Specified {entity_name} ID {entity_id} was not found.",
                }
            },
            "warnings": [],
            "timing": {},
            "evidence": {},
            "provenance": self._get_provenance(),
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _get_provenance(self) -> Dict[str, Any]:
        return {
            "runtime_mode": "OFFLINE_DEMO",
            "package_id": "demo-v1",
            "provenance_type": "SYNTHETIC / PROXY",
            "is_authoritative_real_world_data": False,
            "disclaimer": "All constraints and vessel particulars are synthetic demonstration benchmarks for SIH26006.",
        }
