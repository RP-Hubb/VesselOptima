"""
VesselOptima — Offline Package Ingestion Engine

Loads validated offline packages into the database with full transactional safety,
idempotency, manifest verification, and zero network calls.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger

logger = get_logger("services.offline_package.loader")

from app.models.domain import (
    CandidateService,
    CargoParcel,
    ContractStrategyEnum,
    DataKindEnum,
    DataSource,
    EmploymentControlEnum,
    IdleActionEnum,
    IdleActionEvaluation,
    IdleEmploymentEvaluation,
    MarketObservation,
    OfflinePackage,
    OfflinePackageDataset,
    Port,
    PortConstraint,
    QualityStatusEnum,
    Route,
    RuntimeModeEnum,
    Scenario,
    VesselAvailabilityEvent,
    VesselClass,
    VesselCommitment,
    VesselProfile,
)
from app.services.offline_package.exceptions import (
    OfflinePackageError,
    OfflinePackageIntegrityError,
    OfflinePackageNotFoundError,
)
from app.services.offline_package.manifest import verify_manifest
from app.services.offline_package.validator import parse_datetime, validate_package_data


class OfflinePackageIngestionService:
    """
    Ingestion engine for offline demonstration data packages.
    Ensures idempotency, transactional rollback on error, and strict local execution.
    """

    def __init__(self, db: Session):
        self.db = db

    def ingest_package(
        self,
        package_dir: Path,
        force_reload: bool = False,
    ) -> Dict[str, Any]:
        """
        Main entry point for package ingestion.
        1. Verifies manifest integrity (SHA-256 and row counts)
        2. Validates schema and domain rules
        3. Checks idempotency
        4. Persists records atomically inside a transaction
        """
        logger.info(f"Starting offline package ingestion from: {package_dir}")

        # 1. Verify manifest
        manifest_meta = verify_manifest(package_dir)
        package_id = manifest_meta["package_id"]
        manifest_hash = manifest_meta["manifest_hash"]

        # 2. Validate domain data
        validate_package_data(package_dir)

        # 3. Idempotency Check
        existing_pkg = self.db.execute(
            select(OfflinePackage).where(OfflinePackage.package_id == package_id)
        ).scalar_one_or_none()

        if existing_pkg and not force_reload:
            if existing_pkg.manifest_hash == manifest_hash and existing_pkg.status == "VALIDATED":
                logger.info(f"Package {package_id} already ingested and unchanged.")
                return {
                    "status": "ALREADY_LOADED",
                    "package_id": package_id,
                    "version": existing_pkg.schema_version,
                    "manifest_hash": manifest_hash,
                    "records_loaded": 0,
                    "message": "Package already ingested with matching manifest hash.",
                }

        # 4. Atomic Ingestion Transaction
        try:
            counts = self._execute_ingestion(package_dir, manifest_meta, force_reload)
            self.db.commit()
            logger.info(f"Offline package {package_id} ingested successfully: {counts}")
            return {
                "status": "SUCCESS",
                "package_id": package_id,
                "version": manifest_meta["version"],
                "manifest_hash": manifest_hash,
                "counts": counts,
                "loaded_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"Package ingestion failed for {package_id}, rolled back cleanly: {e}")
            raise OfflinePackageError(f"Failed to ingest package {package_id}: {e}") from e


    def _execute_ingestion(
        self,
        package_dir: Path,
        manifest_meta: Dict[str, Any],
        force_reload: bool,
    ) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        package_id = manifest_meta["package_id"]

        # Ensure baseline Data Sources exist
        sources = {
            1: DataSource(id=1, name="DS-BALTIC-DEMO", licence_class="SYNTHETIC_BENCHMARK", attribution="Synthetic Baltic dry bulk index series for offline demonstration.", active=True),
            2: DataSource(id=2, name="DS-PLATTS-BUNKER-DEMO", licence_class="SYNTHETIC_BENCHMARK", attribution="Synthetic marine fuel benchmarks.", active=True),
            3: DataSource(id=3, name="DS-PORT-AUTHORITY-DEMO", licence_class="SYNTHETIC_OPERATIONAL", attribution="Synthetic port authority operational logs.", active=True),
            4: DataSource(id=4, name="DS-RESERVE-BANK-DEMO", licence_class="SYNTHETIC_MACRO", attribution="Synthetic foreign exchange rates.", active=True),
        }
        for s_id, src in sources.items():
            existing = self.db.get(DataSource, s_id)
            if not existing:
                self.db.add(src)
        self.db.flush()

        # If force reload or update, clear previous demo data in reverse FK order
        if force_reload:
            self.db.execute(delete(IdleActionEvaluation))
            self.db.execute(delete(IdleEmploymentEvaluation))
            self.db.execute(delete(CandidateService))
            self.db.execute(delete(VesselCommitment))
            self.db.execute(delete(VesselAvailabilityEvent))
            self.db.execute(delete(MarketObservation).where(MarketObservation.is_demo == True))
            self.db.execute(delete(CargoParcel).where(CargoParcel.is_demo == True))
            self.db.execute(delete(Route))
            self.db.execute(delete(PortConstraint))
            self.db.execute(delete(Port))
            self.db.execute(delete(VesselProfile).where(VesselProfile.is_demo == True))
            self.db.execute(delete(VesselClass))
            self.db.execute(delete(Scenario).where(Scenario.is_demo == True))
            self.db.execute(delete(OfflinePackageDataset).where(OfflinePackageDataset.package_id == package_id))
            self.db.execute(delete(OfflinePackage).where(OfflinePackage.package_id == package_id))
            self.db.flush()

        # 1. OfflinePackage Record
        pkg = OfflinePackage(
            package_id=package_id,
            schema_version=manifest_meta["schema_version"],
            manifest_hash=manifest_meta["manifest_hash"],
            coverage_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            coverage_end=datetime(2026, 8, 31, tzinfo=timezone.utc),
            status="VALIDATED",
        )
        self.db.add(pkg)
        self.db.flush()

        # 2. OfflinePackageDatasets
        manifest_path = package_dir / "manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)

        pkg_datasets = []
        for f_info in manifest_data.get("files", []):
            pkg_datasets.append(
                OfflinePackageDataset(
                    package_id=package_id,
                    dataset_name=f_info["dataset_name"],
                    file_path=f_info["path"],
                    sha256=f_info["sha256"],
                    row_count=f_info["rows"],
                    schema_version=f_info["schema_version"],
                    provenance_type=DataKindEnum(f_info["provenance_type"]),
                )
            )
        self.db.add_all(pkg_datasets)
        counts["offline_package_datasets"] = len(pkg_datasets)

        # 3. Vessel Classes
        vc_file = package_dir / "vessel_classes" / "vessel_classes.csv"
        with open(vc_file, "r", encoding="utf-8") as f:
            vc_objs = [
                VesselClass(
                    id=int(r["id"]),
                    name=r["name"],
                    dwt_min=float(r["dwt_min"]),
                    dwt_max=float(r["dwt_max"]),
                    typical_capacity_min=float(r["typical_capacity_min"]),
                    typical_capacity_max=float(r["typical_capacity_max"]),
                    draft_min=float(r["draft_min"]),
                    draft_max=float(r["draft_max"]),
                    loa_min=float(r["loa_min"]),
                    loa_max=float(r["loa_max"]),
                    beam_min=float(r["beam_min"]),
                    beam_max=float(r["beam_max"]),
                    speed_laden=float(r["speed_laden"]),
                    speed_ballast=float(r["speed_ballast"]),
                    consumption_laden=float(r["consumption_laden"]),
                    consumption_ballast=float(r["consumption_ballast"]),
                    source=r["source"],
                    version=int(r["version"]),
                )
                for r in csv.DictReader(f)
            ]
            self.db.add_all(vc_objs)
            counts["vessel_classes"] = len(vc_objs)
        self.db.flush()

        # 4. Ports
        ports_file = package_dir / "ports" / "ports.csv"
        with open(ports_file, "r", encoding="utf-8") as f:
            port_objs = [
                Port(
                    id=int(r["id"]),
                    name=r["name"],
                    country=r["country"],
                    unlocode=r["unlocode"],
                    latitude=float(r["latitude"]),
                    longitude=float(r["longitude"]),
                    status=r["status"],
                )
                for r in csv.DictReader(f)
            ]
            self.db.add_all(port_objs)
            counts["ports"] = len(port_objs)
        self.db.flush()

        # 5. Port Constraints
        pc_file = package_dir / "ports" / "port_constraints.csv"
        if pc_file.exists():
            with open(pc_file, "r", encoding="utf-8") as f:
                pc_objs = [
                    PortConstraint(
                        id=int(r["id"]),
                        port_id=int(r["port_id"]),
                        terminal=r["terminal"],
                        berth=r["berth"],
                        rule_type=r["rule_type"],
                        value=float(r["value"]),
                        unit=r["unit"],
                        condition=r["condition"],
                        effective_from=parse_datetime(r["effective_from"], "effective_from", "port_constraints.csv", idx),
                        effective_to=parse_datetime(r["effective_to"], "effective_to", "port_constraints.csv", idx),
                        source_url=r["source_url"],
                        source_document=r["source_document"],
                        verifier=r["verifier"],
                        quality_status=QualityStatusEnum(r["quality_status"]),
                        version=int(r["version"]),
                    )
                    for idx, r in enumerate(csv.DictReader(f), start=2)
                ]
                self.db.add_all(pc_objs)
                counts["port_constraints"] = len(pc_objs)
        self.db.flush()

        # 6. Vessels
        vessels_file = package_dir / "vessels" / "vessels.csv"
        with open(vessels_file, "r", encoding="utf-8") as f:
            vessel_objs = [
                VesselProfile(
                    id=int(r["id"]),
                    name=r["name"],
                    vessel_class_id=int(r["vessel_class_id"]),
                    imo_number=r["imo_number"],
                    dwt=float(r["dwt"]),
                    cargo_capacity=float(r["cargo_capacity"]),
                    draft=float(r["draft"]),
                    loa=float(r["loa"]),
                    beam=float(r["beam"]),
                    speed_laden=float(r["speed_laden"]),
                    speed_ballast=float(r["speed_ballast"]),
                    consumption_laden=float(r["consumption_laden"]),
                    consumption_ballast=float(r["consumption_ballast"]),
                    employment_control=EmploymentControlEnum(r["employment_control"]),
                    source=r["source"],
                    status=r["status"],
                    is_demo=True,
                    version=int(r["version"]),
                )
                for r in csv.DictReader(f)
            ]
            self.db.add_all(vessel_objs)
            counts["vessels"] = len(vessel_objs)
        self.db.flush()

        # 7. Routes
        routes_file = package_dir / "routes" / "routes.csv"
        with open(routes_file, "r", encoding="utf-8") as f:
            route_objs = [
                Route(
                    id=int(r["id"]),
                    name=r["name"],
                    origin_port_id=int(r["origin_port_id"]),
                    destination_port_id=int(r["destination_port_id"]),
                    distance_nm=float(r["distance_nm"]),
                    distance_source=r["distance_source"],
                    version=int(r["version"]),
                )
                for r in csv.DictReader(f)
            ]
            self.db.add_all(route_objs)
            counts["routes"] = len(route_objs)
        self.db.flush()

        # 8. Cargo Parcels
        cargo_file = package_dir / "cargo" / "cargo_requirements.csv"
        with open(cargo_file, "r", encoding="utf-8") as f:
            cargo_objs = [
                CargoParcel(
                    id=int(r["id"]),
                    commodity=r["commodity"],
                    volume_mt=float(r["volume_mt"]),
                    origin_port_id=int(r["origin_port_id"]),
                    destination_port_id=int(r["destination_port_id"]),
                    loading_window_start=parse_datetime(r["loading_window_start"], "loading_window_start", "cargo.csv", idx),
                    loading_window_end=parse_datetime(r["loading_window_end"], "loading_window_end", "cargo.csv", idx),
                    delivery_deadline=parse_datetime(r["delivery_deadline"], "delivery_deadline", "cargo.csv", idx),
                    tolerance_pct=float(r["tolerance_pct"]),
                    status=r["status"],
                    is_demo=True,
                )
                for idx, r in enumerate(csv.DictReader(f), start=2)
            ]
            self.db.add_all(cargo_objs)
            counts["cargo_parcels"] = len(cargo_objs)
        self.db.flush()

        # 9. Vessel Positions & Commitments
        pos_file = package_dir / "vessel_positions" / "vessel_positions.csv"
        with open(pos_file, "r", encoding="utf-8") as f:
            pos_objs = [
                VesselAvailabilityEvent(
                    id=int(r["id"]),
                    vessel_profile_id=int(r["vessel_profile_id"]),
                    available_at=parse_datetime(r["available_at"], "available_at", "pos.csv", idx),
                    location_port_id=int(r["location_port_id"]),
                    location_description=r["location_description"],
                    source=r["source"],
                    confidence=float(r["confidence"]),
                    data_kind=DataKindEnum(r["data_kind"]),
                )
                for idx, r in enumerate(csv.DictReader(f), start=2)
            ]
            self.db.add_all(pos_objs)
            counts["vessel_positions"] = len(pos_objs)

        commit_file = package_dir / "vessel_positions" / "vessel_commitments.csv"
        with open(commit_file, "r", encoding="utf-8") as f:
            commit_objs = [
                VesselCommitment(
                    id=int(r["id"]),
                    vessel_profile_id=int(r["vessel_profile_id"]),
                    commitment_start=parse_datetime(r["commitment_start"], "commitment_start", "commit.csv", idx),
                    commitment_end=parse_datetime(r["commitment_end"], "commitment_end", "commit.csv", idx),
                    route_description=r["route_description"],
                    status=r["status"],
                    is_immutable=r["is_immutable"].lower() in ("true", "1"),
                    employment_control_ref=r["employment_control_ref"],
                    source=r["source"],
                )
                for idx, r in enumerate(csv.DictReader(f), start=2)
            ]
            self.db.add_all(commit_objs)
            counts["vessel_commitments"] = len(commit_objs)
        self.db.flush()

        # 10. Idle Windows & Employment
        idle_file = package_dir / "idle" / "idle_windows.csv"
        if idle_file.exists():
            with open(idle_file, "r", encoding="utf-8") as f:
                idle_objs = [
                    IdleEmploymentEvaluation(
                        id=int(r["id"]),
                        vessel_profile_id=int(r["vessel_profile_id"]),
                        availability_event_id=int(r["availability_event_id"]),
                        commitment_id=int(r["commitment_id"]),
                        window_start=parse_datetime(r["window_start"], "window_start", "idle.csv", idx),
                        window_end=parse_datetime(r["window_end"], "window_end", "idle.csv", idx),
                        idle_days=float(r["idle_days"]),
                        employment_control=EmploymentControlEnum(r["employment_control"]),
                        is_actionable=r["is_actionable"].lower() in ("true", "1"),
                        selected_action=IdleActionEnum(r["selected_action"]),
                        runtime_mode=RuntimeModeEnum.OFFLINE_DEMO,
                        status=r["status"],
                    )
                    for idx, r in enumerate(csv.DictReader(f), start=2)
                ]
                self.db.add_all(idle_objs)
                counts["idle_windows"] = len(idle_objs)
            self.db.flush()

        cand_file = package_dir / "employment" / "employment_candidates.csv"
        if cand_file.exists():
            with open(cand_file, "r", encoding="utf-8") as f:
                cand_objs = [
                    CandidateService(
                        id=int(r["id"]),
                        vessel_profile_id=int(r["vessel_profile_id"]),
                        route_id=int(r["route_id"]),
                        cargo_parcel_id=int(r["cargo_parcel_id"]),
                        contract_strategy=ContractStrategyEnum(r["contract_strategy"]),
                        estimated_freight_cost=float(r["estimated_freight_cost"]),
                        estimated_bunker_cost=float(r["estimated_bunker_cost"]),
                        estimated_port_cost=float(r["estimated_port_cost"]),
                        estimated_total_cost=float(r["estimated_total_cost"]),
                        arrival_date=parse_datetime(r["arrival_date"], "arrival_date", "cand.csv", idx),
                        max_voyages=int(r["max_voyages"]),
                        eligibility=r["eligibility"].lower() in ("true", "1"),
                        eligibility_reason=r["eligibility_reason"],
                        data_kind=DataKindEnum(r["data_kind"]),
                        is_demo=True,
                    )
                    for idx, r in enumerate(csv.DictReader(f), start=2)
                ]
                self.db.add_all(cand_objs)
                counts["employment_candidates"] = len(cand_objs)
            self.db.flush()

        eval_file = package_dir / "employment" / "employment_evaluations.csv"
        if eval_file.exists():
            with open(eval_file, "r", encoding="utf-8") as f:
                eval_objs = [
                    IdleActionEvaluation(
                        id=int(r["id"]),
                        evaluation_id=int(r["evaluation_id"]),
                        action_type=IdleActionEnum(r["action_type"]),
                        is_feasible=r["is_feasible"].lower() in ("true", "1"),
                        feasibility_reason=r["feasibility_reason"],
                        idle_cost=float(r["idle_cost"]),
                        reposition_cost=float(r["reposition_cost"]),
                        bunker_cost=float(r["bunker_cost"]),
                        port_cost=float(r["port_cost"]),
                        expected_contribution=float(r["expected_contribution"]),
                        total_expected_cost=float(r["total_expected_cost"]),
                        risk_score=float(r["risk_score"]),
                        is_selected=r["is_selected"].lower() in ("true", "1"),
                        reason_codes=json.loads(r["reason_codes"]) if r.get("reason_codes") else None,
                    )
                    for idx, r in enumerate(csv.DictReader(f), start=2)
                ]
                self.db.add_all(eval_objs)
                counts["employment_evaluations"] = len(eval_objs)
            self.db.flush()

        # 11. Scenarios
        scen_file = package_dir / "scenarios" / "scenarios.csv"
        with open(scen_file, "r", encoding="utf-8") as f:
            scen_objs = [
                Scenario(
                    id=int(r["id"]),
                    name=r["name"],
                    description=r["description"],
                    scenario_type=r["scenario_type"],
                    parameters=json.loads(r["parameters"]) if r.get("parameters") else None,
                    input_manifest_hash=r["input_manifest_hash"],
                    runtime_mode=RuntimeModeEnum(r["runtime_mode"]),
                    is_demo=True,
                )
                for r in csv.DictReader(f)
            ]
            self.db.add_all(scen_objs)
            counts["scenarios"] = len(scen_objs)
        self.db.flush()

        # 12. Time Series: Market Observations (Batch Ingestion)
        total_obs = 0
        for ts_rel in [
            "market/market_indices.csv",
            "freight/freight_observations.csv",
            "bunker/fuel_prices.csv",
            "congestion/congestion_observations.csv",
            "fx/fx_observations.csv",
        ]:
            ts_path = package_dir / ts_rel
            with open(ts_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                batch = []
                for idx, r in enumerate(reader, start=2):
                    obs = MarketObservation(
                        series_id=r["series_id"],
                        observed_at=parse_datetime(r["observed_at"], "observed_at", ts_rel, idx),
                        available_at=parse_datetime(r["available_at"], "available_at", ts_rel, idx),
                        value=float(r["value"]),
                        unit=r["unit"],
                        source_id=int(r["source_id"]),
                        source_version=r["source_version"],
                        quality_status=QualityStatusEnum(r["quality_status"]),
                        data_kind=DataKindEnum(r["data_kind"]),
                        content_hash=r.get("content_hash"),
                        is_demo=True,
                    )
                    batch.append(obs)
                    if len(batch) >= 2000:
                        self.db.add_all(batch)
                        self.db.flush()
                        total_obs += len(batch)
                        batch = []
                if batch:
                    self.db.add_all(batch)
                    self.db.flush()
                    total_obs += len(batch)

        counts["market_observations"] = total_obs

        return counts
