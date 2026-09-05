"""
VesselOptima — Procurement Cost Model
Follows Section 11 of the Phase 5 Specification.

Transparent expected procurement economics calculation.
Does NOT perform global optimization.
All components are explicitly classified: PROXY, DERIVED, ASSUMPTION, SYNTHETIC.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def calculate_expected_procurement_costs(
    volume_mt: float,
    freight_rate_per_mt: float,
    sailing_days: float,
    daily_fuel_consumption_mt: float = 28.0,
    bunker_price_per_mt: float = 620.0,
    origin_port_dues: float = 35000.0,
    destination_port_dues: float = 40000.0,
    procurement_admin_fee: float = 5000.0,
    strategy_discount_factor: float = 1.0,
    voyage_count: int = 1,
) -> Dict[str, Any]:
    """
    Calculates transparent cost breakdown for candidate strategy.
    strategy_discount_factor represents period charter or volume economies (e.g. 0.95 for Short-Term).
    """
    # 1. Base Freight Cost
    adjusted_rate = freight_rate_per_mt * strategy_discount_factor
    freight_cost = volume_mt * adjusted_rate * voyage_count

    # 2. Bunker Cost (Fuel consumed at sea)
    bunker_cost = sailing_days * daily_fuel_consumption_mt * bunker_price_per_mt * voyage_count

    # 3. Port Costs (Origin + Destination)
    port_costs = (origin_port_dues + destination_port_dues) * voyage_count

    # 4. Administrative Procurement Overhead (Tender publication, legal, evaluation)
    procurement_cost = procurement_admin_fee

    # 5. Total Expected Cost
    total_cost = freight_cost + bunker_cost + port_costs + procurement_cost

    return {
        "expected_freight_cost": round(freight_cost, 2),
        "expected_bunker_cost": round(bunker_cost, 2),
        "expected_port_costs": round(port_costs, 2),
        "expected_procurement_overhead": round(procurement_cost, 2),
        "expected_total_cost": round(total_cost, 2),
        "rate_per_mt_used": round(adjusted_rate, 2),
        "voyage_count": voyage_count,
        "cost_breakdown_provenance": {
            "freight_rate": "PROXY (Forecast / Benchmark)",
            "bunker_price": "PROXY (Singapore VLSFO benchmark 620 USD/MT)",
            "fuel_consumption": "ASSUMPTION (28.0 MT/day laden)",
            "port_dues": "ASSUMPTION (Standard major port tariff estimates)",
            "procurement_overhead": "ASSUMPTION (Standard administrative tender expense)",
            "strategy_discount_factor": round(strategy_discount_factor, 2),
        },
    }
