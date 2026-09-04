"""
VesselOptima — Offline Package Schema & Domain Validator

Validates referential integrity, schemas, data types, chronology,
and domain physical constraints across all datasets before database persistence.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set

from app.services.offline_package.exceptions import (
    DomainValidationError,
    SchemaValidationError,
)


def parse_datetime(val: str, field_name: str, file_path: str, row_num: int) -> datetime:
    """Parses standard ISO or space-separated datetime string."""
    if not val:
        raise SchemaValidationError(f"[{file_path}] Row {row_num}: '{field_name}' is empty.")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(val.strip(), fmt)
        except ValueError:
            continue
    raise SchemaValidationError(
        f"[{file_path}] Row {row_num}: Invalid datetime format for '{field_name}': '{val}'"
    )


def parse_float(val: str, field_name: str, file_path: str, row_num: int) -> float:
    """Parses a float value and ensures it is numeric."""
    try:
        return float(val)
    except (ValueError, TypeError) as e:
        raise SchemaValidationError(
            f"[{file_path}] Row {row_num}: Invalid numeric value for '{field_name}': '{val}'"
        ) from e


def load_csv_rows(filepath: Path) -> List[Dict[str, str]]:
    """Loads a CSV into a list of row dicts."""
    if not filepath.exists():
        raise SchemaValidationError(f"Required dataset file missing: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def validate_package_data(package_dir: Path) -> Dict[str, Any]:
    """
    Performs comprehensive schema, referential integrity, chronology,
    and domain constraint validation across all CSV datasets in the package.
    """
    # 1. Vessel Classes
    vc_file = package_dir / "vessel_classes" / "vessel_classes.csv"
    vc_rows = load_csv_rows(vc_file)
    vessel_class_ids: Set[int] = set()
    for idx, r in enumerate(vc_rows, start=2):
        vc_id = int(r["id"])
        vessel_class_ids.add(vc_id)
        dwt_min = parse_float(r["dwt_min"], "dwt_min", str(vc_file.name), idx)
        dwt_max = parse_float(r["dwt_max"], "dwt_max", str(vc_file.name), idx)
        if dwt_min <= 0 or dwt_max <= dwt_min:
            raise DomainValidationError(
                f"[{vc_file.name}] Row {idx}: Invalid DWT bounds ({dwt_min} - {dwt_max})"
            )

    # 2. Ports
    ports_file = package_dir / "ports" / "ports.csv"
    ports_rows = load_csv_rows(ports_file)
    port_ids: Set[int] = set()
    for idx, r in enumerate(ports_rows, start=2):
        p_id = int(r["id"])
        port_ids.add(p_id)
        if not r.get("name") or not r.get("unlocode"):
            raise DomainValidationError(f"[{ports_file.name}] Row {idx}: Port missing name or UNLOCODE")

    # 3. Port Constraints
    pc_file = package_dir / "ports" / "port_constraints.csv"
    if pc_file.exists():
        pc_rows = load_csv_rows(pc_file)
        for idx, r in enumerate(pc_rows, start=2):
            p_id = int(r["port_id"])
            if p_id not in port_ids:
                raise DomainValidationError(
                    f"[{pc_file.name}] Row {idx}: Foreign key violation — port_id {p_id} not in ports.csv"
                )
            val = parse_float(r["value"], "value", str(pc_file.name), idx)
            if val <= 0:
                raise DomainValidationError(
                    f"[{pc_file.name}] Row {idx}: Port constraint value must be positive, got {val}"
                )

    # 4. Vessels
    vessels_file = package_dir / "vessels" / "vessels.csv"
    vessels_rows = load_csv_rows(vessels_file)
    vessel_ids: Set[int] = set()
    for idx, r in enumerate(vessels_rows, start=2):
        v_id = int(r["id"])
        vessel_ids.add(v_id)
        vc_id = int(r["vessel_class_id"])
        if vc_id not in vessel_class_ids:
            raise DomainValidationError(
                f"[{vessels_file.name}] Row {idx}: Foreign key violation — vessel_class_id {vc_id} not in vessel_classes.csv"
            )
        dwt = parse_float(r["dwt"], "dwt", str(vessels_file.name), idx)
        cap = parse_float(r["cargo_capacity"], "cargo_capacity", str(vessels_file.name), idx)
        draft = parse_float(r["draft"], "draft", str(vessels_file.name), idx)
        loa = parse_float(r["loa"], "loa", str(vessels_file.name), idx)
        beam = parse_float(r["beam"], "beam", str(vessels_file.name), idx)

        if dwt <= 0 or cap <= 0 or draft <= 0 or loa <= 0 or beam <= 0:
            raise DomainValidationError(
                f"[{vessels_file.name}] Row {idx}: Physical vessel particulars must be strictly positive."
            )
        if cap > dwt:
            raise DomainValidationError(
                f"[{vessels_file.name}] Row {idx}: Cargo capacity ({cap}) cannot exceed DWT ({dwt})."
            )

    # 5. Routes
    routes_file = package_dir / "routes" / "routes.csv"
    routes_rows = load_csv_rows(routes_file)
    route_ids: Set[int] = set()
    for idx, r in enumerate(routes_rows, start=2):
        rt_id = int(r["id"])
        route_ids.add(rt_id)
        orig_id = int(r["origin_port_id"])
        dest_id = int(r["destination_port_id"])
        if orig_id not in port_ids:
            raise DomainValidationError(
                f"[{routes_file.name}] Row {idx}: Origin port {orig_id} not in ports.csv"
            )
        if dest_id not in port_ids:
            raise DomainValidationError(
                f"[{routes_file.name}] Row {idx}: Destination port {dest_id} not in ports.csv"
            )
        dist = parse_float(r["distance_nm"], "distance_nm", str(routes_file.name), idx)
        if dist <= 0:
            raise DomainValidationError(
                f"[{routes_file.name}] Row {idx}: Route distance must be positive, got {dist}"
            )

    # 6. Cargo Requirements
    cargo_file = package_dir / "cargo" / "cargo_requirements.csv"
    cargo_rows = load_csv_rows(cargo_file)
    cargo_ids: Set[int] = set()
    for idx, r in enumerate(cargo_rows, start=2):
        c_id = int(r["id"])
        cargo_ids.add(c_id)
        orig_id = int(r["origin_port_id"])
        dest_id = int(r["destination_port_id"])
        if orig_id not in port_ids or dest_id not in port_ids:
            raise DomainValidationError(f"[{cargo_file.name}] Row {idx}: Invalid origin or destination port.")

        vol = parse_float(r["volume_mt"], "volume_mt", str(cargo_file.name), idx)
        if vol <= 0:
            raise DomainValidationError(f"[{cargo_file.name}] Row {idx}: Cargo volume must be positive, got {vol}")

        w_start = parse_datetime(r["loading_window_start"], "loading_window_start", str(cargo_file.name), idx)
        w_end = parse_datetime(r["loading_window_end"], "loading_window_end", str(cargo_file.name), idx)
        deadline = parse_datetime(r["delivery_deadline"], "delivery_deadline", str(cargo_file.name), idx)

        if not (w_start <= w_end <= deadline):
            raise DomainValidationError(
                f"[{cargo_file.name}] Row {idx}: Inconsistent loading/delivery chronology: "
                f"{w_start} <= {w_end} <= {deadline} violated."
            )

    # 7. Vessel Positions & Commitments
    pos_file = package_dir / "vessel_positions" / "vessel_positions.csv"
    pos_rows = load_csv_rows(pos_file)
    pos_ids: Set[int] = set()
    for idx, r in enumerate(pos_rows, start=2):
        p_id = int(r["id"])
        pos_ids.add(p_id)
        v_id = int(r["vessel_profile_id"])
        if v_id not in vessel_ids:
            raise DomainValidationError(f"[{pos_file.name}] Row {idx}: vessel_profile_id {v_id} not in vessels.csv")
        loc_port = int(r["location_port_id"])
        if loc_port not in port_ids:
            raise DomainValidationError(f"[{pos_file.name}] Row {idx}: location_port_id {loc_port} not in ports.csv")
        parse_datetime(r["available_at"], "available_at", str(pos_file.name), idx)

    commit_file = package_dir / "vessel_positions" / "vessel_commitments.csv"
    commit_rows = load_csv_rows(commit_file)
    commit_ids: Set[int] = set()
    for idx, r in enumerate(commit_rows, start=2):
        c_id = int(r["id"])
        commit_ids.add(c_id)
        v_id = int(r["vessel_profile_id"])
        if v_id not in vessel_ids:
            raise DomainValidationError(f"[{commit_file.name}] Row {idx}: vessel_profile_id {v_id} not in vessels.csv")
        c_start = parse_datetime(r["commitment_start"], "commitment_start", str(commit_file.name), idx)
        c_end = parse_datetime(r["commitment_end"], "commitment_end", str(commit_file.name), idx)
        if c_start >= c_end:
            raise DomainValidationError(f"[{commit_file.name}] Row {idx}: commitment_start must be before commitment_end")

    # 8. Idle Windows & Employment Candidates
    idle_file = package_dir / "idle" / "idle_windows.csv"
    if idle_file.exists():
        idle_rows = load_csv_rows(idle_file)
        idle_ids: Set[int] = set()
        for idx, r in enumerate(idle_rows, start=2):
            i_id = int(r["id"])
            idle_ids.add(i_id)
            v_id = int(r["vessel_profile_id"])
            if v_id not in vessel_ids:
                raise DomainValidationError(f"[{idle_file.name}] Row {idx}: vessel_profile_id {v_id} not in vessels.csv")
            avail_id = int(r["availability_event_id"])
            if avail_id not in pos_ids:
                raise DomainValidationError(f"[{idle_file.name}] Row {idx}: availability_event_id {avail_id} not in vessel_positions.csv")
            comm_id = int(r["commitment_id"])
            if comm_id not in commit_ids:
                raise DomainValidationError(f"[{idle_file.name}] Row {idx}: commitment_id {comm_id} not in vessel_commitments.csv")
            i_start = parse_datetime(r["window_start"], "window_start", str(idle_file.name), idx)
            i_end = parse_datetime(r["window_end"], "window_end", str(idle_file.name), idx)
            if i_start >= i_end:
                raise DomainValidationError(f"[{idle_file.name}] Row {idx}: window_start must precede window_end")
            i_days = parse_float(r["idle_days"], "idle_days", str(idle_file.name), idx)
            if i_days <= 0:
                raise DomainValidationError(f"[{idle_file.name}] Row {idx}: idle_days must be positive")

    cand_file = package_dir / "employment" / "employment_candidates.csv"
    if cand_file.exists():
        cand_rows = load_csv_rows(cand_file)
        for idx, r in enumerate(cand_rows, start=2):
            v_id = int(r["vessel_profile_id"])
            rt_id = int(r["route_id"])
            cg_id = int(r["cargo_parcel_id"])
            if v_id not in vessel_ids:
                raise DomainValidationError(f"[{cand_file.name}] Row {idx}: vessel_profile_id {v_id} not in vessels.csv")
            if rt_id not in route_ids:
                raise DomainValidationError(f"[{cand_file.name}] Row {idx}: route_id {rt_id} not in routes.csv")
            if cg_id not in cargo_ids:
                raise DomainValidationError(f"[{cand_file.name}] Row {idx}: cargo_parcel_id {cg_id} not in cargo_requirements.csv")

    # 9. Time Series Chronology (Check a sample of market, freight, bunker, congestion, fx)
    for ts_name, ts_rel in [
        ("Market Indices", "market/market_indices.csv"),
        ("Freight Observations", "freight/freight_observations.csv"),
        ("Bunker Prices", "bunker/fuel_prices.csv"),
        ("Congestion Observations", "congestion/congestion_observations.csv"),
        ("FX Rates", "fx/fx_observations.csv"),
    ]:
        ts_path = package_dir / ts_rel
        rows = load_csv_rows(ts_path)
        if not rows:
            raise SchemaValidationError(f"Time series {ts_name} is empty: {ts_rel}")

        # Verify chronology per series_id
        series_dates: Dict[str, datetime] = {}
        for idx, r in enumerate(rows[:500], start=2):  # Sample check first 500 rows for speed and fidelity
            sid = r["series_id"]
            obs_dt = parse_datetime(r["observed_at"], "observed_at", ts_rel, idx)
            avail_dt = parse_datetime(r["available_at"], "available_at", ts_rel, idx)
            if obs_dt > avail_dt:
                raise DomainValidationError(
                    f"[{ts_rel}] Row {idx}: observed_at ({obs_dt}) cannot be after available_at ({avail_dt})"
                )
            if sid in series_dates and obs_dt < series_dates[sid]:
                raise DomainValidationError(
                    f"[{ts_rel}] Row {idx}: Non-chronological ordering for series {sid}"
                )
            series_dates[sid] = obs_dt
            val = parse_float(r["value"], "value", ts_rel, idx)
            if val < 0:
                raise DomainValidationError(f"[{ts_rel}] Row {idx}: Value must be non-negative, got {val}")

    return {
        "status": "VALID",
        "vessel_classes": len(vc_rows),
        "vessels": len(vessels_rows),
        "ports": len(ports_rows),
        "routes": len(routes_rows),
        "cargo_parcels": len(cargo_rows),
        "vessel_positions": len(pos_rows),
        "vessel_commitments": len(commit_rows),
    }
