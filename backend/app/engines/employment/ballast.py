"""VesselOptima — Employment Engine: Ballast & Repositioning Subsystem
Follows Section 9 of the Phase 6 Specification.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

# Canonical route distances between standard demo ports
CANONICAL_PORT_DISTANCES: Dict[Tuple[int, int], float] = {
    (13, 1): 1620.0,  # Singapore to Paradip
    (1, 13): 1620.0,
    (1, 2): 55.0,     # Paradip to Dhamra
    (2, 1): 55.0,
    (1, 3): 190.0,    # Paradip to Visakhapatnam
    (3, 1): 190.0,
    (6, 1): 3920.0,   # Port Hedland to Paradip
    (6, 2): 3950.0,   # Port Hedland to Dhamra
    (7, 1): 5250.0,   # Newcastle to Paradip
    (9, 1): 2740.0,   # Samarinda to Paradip
    (9, 4): 2710.0,   # Samarinda to Haldia
    (11, 1): 4620.0,  # Richards Bay to Paradip
}


def calculate_great_circle_distance_nm(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Computes great-circle nautical distance between coordinates
    with standard maritime route detour factor (1.15).
    """
    R_NM = 3440.065
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    direct_nm = R_NM * c
    return round(direct_nm * 1.15, 1)


def calculate_ballast_repositioning(
    vessel_id: int,
    current_port_id: Optional[int],
    current_port_coords: Optional[Tuple[float, float]],
    origin_port_id: int,
    origin_port_coords: Optional[Tuple[float, float]],
    availability_start: datetime,
    vessel_speed_ballast: Optional[float] = None,
    canonical_route_distance_nm: Optional[float] = None,
    default_ballast_speed_knots: float = 13.0,
    vessel_consumption_ballast: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Calculates deterministic ballast repositioning metrics:
    distance, transit duration, departure, arrival, and assumption sources.
    """
    ballast_speed = float(vessel_speed_ballast or default_ballast_speed_knots)
    speed_source = "VESSEL_REGISTRY" if vessel_speed_ballast else "CONFIG_DEFAULT"
    daily_cons = float(vessel_consumption_ballast or 16.0)

    # Same port check: 0 distance
    if current_port_id and current_port_id == origin_port_id:
        return {
            "ballast_required": False,
            "ballast_distance_nm": 0.0,
            "ballast_speed_knots": ballast_speed,
            "ballast_days": 0.0,
            "ballast_departure": availability_start.isoformat(),
            "ballast_arrival": availability_start.isoformat(),
            "bunker_consumption_vlsfo_mt": 0.0,
            "distance_source": "SAME_PORT",
            "data_source": "SAME_PORT",
            "speed_source": speed_source,
            "assumption_flag": False,
            "provenance_fallback": False,
            "notes": "Vessel is already positioned at loading origin port.",
        }

    # Canonical route check
    port_pair = (current_port_id, origin_port_id) if current_port_id else None
    if canonical_route_distance_nm is not None and canonical_route_distance_nm > 0:
        dist_nm = float(canonical_route_distance_nm)
        dist_source = "CANONICAL_DATABASE_ROUTE"
        assumption_flag = False
        provenance_fallback = False
    elif port_pair and port_pair in CANONICAL_PORT_DISTANCES:
        dist_nm = CANONICAL_PORT_DISTANCES[port_pair]
        dist_source = "CANONICAL_DATABASE_ROUTE"
        assumption_flag = False
        provenance_fallback = False
    elif current_port_coords and origin_port_coords:
        dist_nm = calculate_great_circle_distance_nm(
            current_port_coords[0], current_port_coords[1],
            origin_port_coords[0], origin_port_coords[1],
        )
        dist_source = "HAVERSINE_PROXIMITY_ESTIMATE_WITH_1.15_ROUTING_MARGIN"
        assumption_flag = True
        provenance_fallback = True
    else:
        # Benchmark fallback between Indian Ocean / SE Asia ports
        dist_nm = 1250.0
        dist_source = "REGIONAL_PROXY_FALLBACK"
        assumption_flag = True
        provenance_fallback = True

    ballast_hours = dist_nm / max(ballast_speed, 1.0)
    ballast_days = round(ballast_hours / 24.0, 2)
    ballast_arrival = availability_start + timedelta(days=ballast_days)
    bunker_consumption = round(ballast_days * daily_cons, 2)

    return {
        "ballast_required": True,
        "ballast_distance_nm": dist_nm,
        "ballast_speed_knots": ballast_speed,
        "ballast_days": ballast_days,
        "ballast_departure": availability_start.isoformat(),
        "ballast_arrival": ballast_arrival.isoformat(),
        "arrival_at_origin": ballast_arrival.isoformat(),
        "bunker_consumption_vlsfo_mt": bunker_consumption,
        "distance_source": dist_source,
        "data_source": dist_source,
        "speed_source": speed_source,
        "assumption_flag": assumption_flag,
        "provenance_fallback": provenance_fallback,
        "notes": f"Repositioning from port {current_port_id} to origin port {origin_port_id}.",
    }
