"""VesselOptima — Employment Engine: Transparent Economics & Contribution Model
Follows Section 12, 13, 14 of the Phase 6 Specification.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def calculate_employment_economics(
    volume_mt: float,
    freight_rate_per_mt: Optional[float],
    ballast_days: float,
    sailing_days: float,
    loading_days: float,
    discharge_days: float,
    idle_days: float,
    daily_operating_cost: Optional[float] = None,
    daily_idle_rate: Optional[float] = None,
    bunker_price_per_mt: float = 620.0,
    daily_consumption_ballast: float = 16.0,
    daily_consumption_laden: float = 20.0,
    daily_consumption_port: float = 3.5,
    origin_port_dues: float = 35000.0,
    destination_port_dues: float = 42000.0,
    procurement_fee: float = 0.0,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Computes transparent cost breakdown, expected revenue, gross contribution,
    and utilization metrics for an alternative employment candidate.
    Supports flexible aliases for parameter names and returned fields.
    """
    # Parameter aliases
    fuel_vlsfo_price = float(kwargs.get("vlsfo_price_per_mt", bunker_price_per_mt))
    fuel_lsmgo_price = float(kwargs.get("lsmgo_price_per_mt", 850.0))
    orig_port_fee = float(kwargs.get("origin_port_fee", origin_port_dues))
    dest_port_fee = float(kwargs.get("dest_port_fee", destination_port_dues))

    op_rate = float(daily_operating_cost or 7500.0)
    op_source = "CANONICAL_REGISTRY" if daily_operating_cost else "ASSUMED_DEFAULT"

    idle_rate = float(daily_idle_rate or op_rate)
    idle_source = "CANONICAL_REGISTRY" if daily_idle_rate else "ASSUMED_DEFAULT"

    voyage_days = round(loading_days + sailing_days + discharge_days, 2)
    port_days = round(loading_days + discharge_days, 2)
    total_active_days = round(ballast_days + voyage_days, 2)
    total_window_days = round(total_active_days + idle_days, 2)

    # 1. Operating costs (daily operating costs across active voyage days: ballast + laden + port)
    total_active_operating_cost = round(total_active_days * op_rate, 2)
    voyage_operating_cost = round(voyage_days * op_rate, 2)
    ballast_operating_cost = round(ballast_days * op_rate, 2)

    # 2. Fuel / Bunker costs
    ballast_fuel_mt = round(ballast_days * daily_consumption_ballast, 2)
    laden_fuel_mt = round(sailing_days * daily_consumption_laden, 2)
    port_fuel_mt = round(port_days * daily_consumption_port, 2)
    total_fuel_mt = round(ballast_fuel_mt + laden_fuel_mt + port_fuel_mt, 2)

    ballast_fuel_cost = round(ballast_fuel_mt * fuel_vlsfo_price, 2)
    laden_fuel_cost = round(laden_fuel_mt * fuel_vlsfo_price, 2)
    port_fuel_cost = round(port_fuel_mt * fuel_lsmgo_price, 2)
    voyage_bunker_cost = round(laden_fuel_cost + port_fuel_cost, 2)

    # Ballast total cost = ballast operating + ballast fuel
    total_ballast_cost = round(ballast_operating_cost + ballast_fuel_cost, 2)

    # 3. Port Tariffs & Dues
    total_port_cost = round(orig_port_fee + dest_port_fee, 2)

    # 4. Idle Cost Exposure
    total_idle_cost = round(idle_days * idle_rate, 2)

    # 5. Total Employment Cost
    total_employment_cost = round(
        total_active_operating_cost
        + ballast_fuel_cost
        + laden_fuel_cost
        + port_fuel_cost
        + total_port_cost
        + total_idle_cost
        + procurement_fee,
        2,
    )

    # 6. Revenue & Contribution
    if freight_rate_per_mt is not None and freight_rate_per_mt > 0:
        expected_revenue = round(volume_mt * freight_rate_per_mt, 2)
        gross_contribution = round(expected_revenue - total_employment_cost, 2)
        revenue_source = "CANONICAL_BENCHMARK"
    else:
        expected_revenue = None
        gross_contribution = None
        revenue_source = "ECONOMIC_DATA_UNAVAILABLE"

    # 7. Operational Utilization
    utilization_ratio = round(voyage_days / max(total_window_days, 0.1), 3)
    utilization_pct = round(utilization_ratio * 100.0, 1)

    return {
        "expected_revenue": expected_revenue,
        "expected_revenue_usd": expected_revenue,
        "gross_contribution": gross_contribution,
        "gross_contribution_usd": gross_contribution,
        "total_employment_cost": total_employment_cost,
        "total_voyage_costs_usd": total_employment_cost,
        "utilization_ratio_pct": utilization_pct,
        "currency": "USD",
        "revenue_source": revenue_source,
        "cost_breakdown": {
            "operating_cost": voyage_operating_cost,
            "daily_operating_costs": total_active_operating_cost,
            "ballast_operating_cost": ballast_operating_cost,
            "ballast_cost": total_ballast_cost,
            "ballast_bunker_costs": ballast_fuel_cost,
            "laden_bunker_costs": laden_fuel_cost,
            "auxiliary_port_bunker_costs": port_fuel_cost,
            "bunker_cost": voyage_bunker_cost,
            "origin_port_costs": orig_port_fee,
            "destination_port_costs": dest_port_fee,
            "port_cost": total_port_cost,
            "idle_cost": total_idle_cost,
            "idle_holding_costs": total_idle_cost,
            "procurement_administration_fee": procurement_fee,
        },
        "operational_breakdown": {
            "ballast_days": ballast_days,
            "voyage_days": voyage_days,
            "idle_days": idle_days,
            "total_window_days": total_window_days,
            "total_bunker_fuel_mt": total_fuel_mt,
            "utilization_ratio": utilization_ratio,
        },
        "data_provenance": {
            "operating_rate_source": op_source,
            "idle_rate_source": idle_source,
            "bunker_price_source": "CANONICAL_INDEX",
            "port_dues_source": "CANONICAL_TARIFF",
        },
    }
