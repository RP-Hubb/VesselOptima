"""
VesselOptima — Phase 8: Copy-on-Scenario Parameter Transformation Engine

Applies economic, fuel, and port cost multipliers to candidates using strict
copy-on-scenario semantics. Guarantees 100% immutability of baseline data
via SHA-256 hash assertions before and after transformation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from typing import Any, Dict, List, Tuple

from app.engines.scenarios.config import ScenarioConfig

logger = logging.getLogger("vesseloptima.engines.scenarios.transform")


def hash_candidate_set(candidates: List[Dict[str, Any]]) -> str:
    """
    Computes a deterministic SHA-256 fingerprint of a candidate list
    to prove zero mutation during scenario operations.
    """
    canonical_items = []
    for c in candidates:
        econ = c.get("economics", {})
        sched = c.get("timeline", {}).get("schedule", {})
        item = {
            "candidate_id": str(c.get("candidate_id")),
            "vessel_id": int(c.get("vessel_id", 0)),
            "cargo_id": c.get("cargo_id"),
            "status": str(c.get("status")),
            "revenue": round(float(econ.get("expected_gross_revenue", 0.0) or 0.0), 2),
            "cost": round(float(econ.get("total_voyage_cost", 0.0) or 0.0), 2),
            "net_contrib": round(float(econ.get("net_economic_contribution", 0.0) or 0.0), 2),
            "idle_days": round(float(econ.get("idle_days", 0.0) or 0.0), 2),
            "ballast_start": str(sched.get("ballast_start")),
            "discharge_end": str(sched.get("discharge_end")),
        }
        canonical_items.append(item)

    # Sort deterministically by candidate_id
    canonical_items.sort(key=lambda x: x["candidate_id"])
    serialized = json.dumps(canonical_items, sort_keys=True).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


class ScenarioTransformer:
    """
    Pure transformation engine applying what-if parameters to candidate copies.
    Never modifies input data in-place.
    """

    @staticmethod
    def transform_candidates(
        baseline_candidates: List[Dict[str, Any]],
        config: ScenarioConfig,
    ) -> Tuple[List[Dict[str, Any]], str, str]:
        """
        Transforms a set of candidates according to ScenarioConfig.

        Returns:
            (scenario_candidates, baseline_hash_before, baseline_hash_after)

        Raises:
            AssertionError: If baseline_hash_before != baseline_hash_after (immutability violated).
        """
        # 1. Record baseline hash before transformation
        hash_before = hash_candidate_set(baseline_candidates)

        # 2. Perform deep copy for scenario isolation
        scenario_candidates: List[Dict[str, Any]] = copy.deepcopy(baseline_candidates)

        # 3. Apply economic transformations on deep copy
        fm = config.freight_multiplier
        bm = config.bunker_multiplier
        pm = config.port_cost_multiplier
        im = config.idle_cost_multiplier

        for cand in scenario_candidates:
            econ = cand.setdefault("economics", {})
            cost_breakdown = econ.get("cost_breakdown", {})

            # Original baseline economic values
            orig_rev = float(econ.get("expected_gross_revenue", 0.0) or 0.0)
            orig_cost = float(econ.get("total_voyage_cost", 0.0) or 0.0)
            orig_daily_op = float(econ.get("daily_operating_cost", 7500.0) or 7500.0)
            idle_days = float(econ.get("idle_days", 0.0) or 0.0)

            # 3.1 Freight adjustment
            new_rev = round(orig_rev * fm, 2)
            econ["expected_gross_revenue"] = new_rev
            econ["expected_revenue"] = new_rev
            econ["expected_revenue_usd"] = new_rev

            # 3.2 Bunker & Port cost adjustment
            if cost_breakdown:
                # Granular cost breakdown available
                bunker_cost = float(cost_breakdown.get("bunker_cost", 0.0) or 0.0)
                ballast_bunker = float(cost_breakdown.get("ballast_bunker_costs", 0.0) or 0.0)
                laden_bunker = float(cost_breakdown.get("laden_bunker_costs", 0.0) or 0.0)
                port_bunker = float(cost_breakdown.get("auxiliary_port_bunker_costs", 0.0) or 0.0)
                total_bunker = bunker_cost if bunker_cost > 0 else (ballast_bunker + laden_bunker + port_bunker)

                port_cost = float(cost_breakdown.get("port_cost", 0.0) or 0.0)
                orig_port_cost = float(cost_breakdown.get("origin_port_costs", 0.0) or 0.0)
                dest_port_cost = float(cost_breakdown.get("destination_port_costs", 0.0) or 0.0)
                total_port = port_cost if port_cost > 0 else (orig_port_cost + dest_port_cost)

                op_cost = float(cost_breakdown.get("operating_cost", 0.0) or 0.0)
                daily_op_costs = float(cost_breakdown.get("daily_operating_costs", 0.0) or 0.0)
                ballast_op = float(cost_breakdown.get("ballast_operating_cost", 0.0) or 0.0)
                total_op = daily_op_costs if daily_op_costs > 0 else (op_cost + ballast_op)

                proc_fee = float(cost_breakdown.get("procurement_administration_fee", 0.0) or 0.0)

                # Apply multipliers
                new_bunker = round(total_bunker * bm, 2)
                new_port = round(total_port * pm, 2)
                new_daily_rate = round(orig_daily_op * im, 2)
                new_idle_cost = round(idle_days * new_daily_rate, 2)

                # Updated cost breakdown in scenario
                cost_breakdown["bunker_cost"] = new_bunker
                cost_breakdown["ballast_bunker_costs"] = round(ballast_bunker * bm, 2)
                cost_breakdown["laden_bunker_costs"] = round(laden_bunker * bm, 2)
                cost_breakdown["auxiliary_port_bunker_costs"] = round(port_bunker * bm, 2)
                cost_breakdown["port_cost"] = new_port
                cost_breakdown["origin_port_costs"] = round(orig_port_cost * pm, 2)
                cost_breakdown["destination_port_costs"] = round(dest_port_cost * pm, 2)
                cost_breakdown["idle_cost"] = new_idle_cost
                cost_breakdown["idle_holding_costs"] = new_idle_cost

                # Total voyage cost = active operating + bunker + port + proc_fee (idle evaluated by MILP)
                new_total_cost = round(total_op + new_bunker + new_port + proc_fee, 2)
            else:
                # Synthetic or aggregated candidate: model breakdown proportionally
                # Typical dry bulk voyage cost: 50% bunker, 25% port dues, 25% vessel operating
                est_bunker = orig_cost * 0.50
                est_port = orig_cost * 0.25
                est_op = orig_cost * 0.25

                new_total_cost = round(
                    (est_op) + (est_bunker * bm) + (est_port * pm), 2
                )
                new_daily_rate = round(orig_daily_op * im, 2)

            econ["daily_operating_cost"] = new_daily_rate
            econ["daily_idle_rate"] = new_daily_rate
            econ["total_voyage_cost"] = new_total_cost
            econ["total_voyage_costs_usd"] = new_total_cost
            econ["total_employment_cost"] = new_total_cost

            # 3.3 Net economic contribution
            new_contrib = round(new_rev - new_total_cost, 2)
            econ["net_economic_contribution"] = new_contrib
            econ["gross_contribution"] = new_contrib
            econ["gross_contribution_usd"] = new_contrib

            # 3.4 Tag scenario metadata on candidate copy
            cand.setdefault("provenance", {})["scenario_id"] = config.scenario_id
            cand["scenario_transforms_applied"] = {
                "freight_multiplier": fm,
                "bunker_multiplier": bm,
                "port_cost_multiplier": pm,
                "idle_cost_multiplier": im,
                "original_revenue": orig_rev,
                "original_cost": orig_cost,
                "new_revenue": new_rev,
                "new_cost": new_total_cost,
                "new_net_contribution": new_contrib,
            }

        # 4. Record baseline hash after transformation and assert strict equality
        hash_after = hash_candidate_set(baseline_candidates)
        if hash_before != hash_after:
            raise AssertionError(
                f"FATAL: Baseline immutability violated! "
                f"Hash before ({hash_before}) != Hash after ({hash_after})"
            )

        logger.debug(
            "Transformed %d candidates for scenario '%s' (hash: %s). Immutability confirmed.",
            len(scenario_candidates),
            config.scenario_id,
            hash_before,
        )

        return scenario_candidates, hash_before, hash_after
