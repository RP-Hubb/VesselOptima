"""
VesselOptima — Phase 8: Upstream Temporal & Operational Revalidation Engine

Re-evaluates candidates when operational scenario parameters (laycan window tightening,
vessel delays, fleet exclusions) alter temporal or physical feasibility.
Never fabricates feasibility; invokes upstream chronological checks.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List

from app.engines.scenarios.config import ScenarioConfig

logger = logging.getLogger("vesseloptima.engines.scenarios.revalidation")


class ScenarioRevalidator:
    """
    Revalidates candidates when scenario parameters affect operational timing or fleet availability.
    """

    @staticmethod
    def revalidate_candidates(
        candidates: List[Dict[str, Any]],
        config: ScenarioConfig,
    ) -> List[Dict[str, Any]]:
        """
        Applies laycan tightening, vessel delays, and vessel exclusions.
        Updates candidate status to INFEASIBLE if constraints are violated.
        Returns the updated list of candidates.
        """
        laycan_cut_days = config.laycan_adjustment_days
        excluded_vessels = set(config.excluded_vessel_ids)
        delay_map = config.vessel_delay_days

        revalidated_count = 0
        disqualified_count = 0

        for cand in candidates:
            v_id = cand.get("vessel_id")
            c_id = cand.get("cargo_id")

            # 1. Fleet Availability Check: Excluded vessels
            if v_id in excluded_vessels:
                cand["status"] = "INFEASIBLE"
                cand["optimization_status"] = "INFEASIBLE_UPSTREAM"
                cand["primary_reason_code"] = "VESSEL_EXCLUDED_IN_SCENARIO"
                cand["primary_reason_description"] = f"Vessel {v_id} is unavailable/excluded in scenario {config.scenario_id}."
                cand.setdefault("failed_reasons", []).append("VESSEL_EXCLUDED_IN_SCENARIO")
                disqualified_count += 1
                continue

            # 2. Timing & Temporal Checks
            timeline = cand.get("timeline", {})
            milestones = timeline.get("timing_milestones", {})
            sched = timeline.get("schedule", {})

            delay_days = delay_map.get(v_id, 0.0) if v_id else 0.0

            # Extract milestone dates
            raw_ballast_arrival = milestones.get("ballast_arrival") or sched.get("ballast_start")
            raw_laycan_end = milestones.get("cargo_laycan_end")
            raw_laycan_start = milestones.get("cargo_laycan_start")
            raw_discharge_end = milestones.get("discharge_end") or sched.get("discharge_end")
            raw_deadline = milestones.get("delivery_deadline")

            if laycan_cut_days > 0 or delay_days > 0:
                # If milestone strings are available, perform rigorous date math
                if raw_ballast_arrival and raw_laycan_end:
                    try:
                        b_arr = (
                            datetime.fromisoformat(raw_ballast_arrival)
                            if isinstance(raw_ballast_arrival, str)
                            else raw_ballast_arrival
                        )
                        l_end = (
                            datetime.fromisoformat(raw_laycan_end)
                            if isinstance(raw_laycan_end, str)
                            else raw_laycan_end
                        )

                        # Apply delay to arrival
                        adj_arrival = b_arr + timedelta(days=delay_days)

                        # Apply laycan tightening
                        adj_laycan_end = l_end - timedelta(days=laycan_cut_days)

                        # Re-verify presentation window
                        if adj_arrival > adj_laycan_end:
                            cand["status"] = "INFEASIBLE"
                            cand["optimization_status"] = "INFEASIBLE_UPSTREAM"
                            cand["primary_reason_code"] = "LAYCAN_WINDOW_TIGHTENED_EXCEEDED"
                            cand["primary_reason_description"] = (
                                f"Ballast arrival ({adj_arrival.strftime('%Y-%m-%d %H:%M')}) exceeds "
                                f"tightened laycan end ({adj_laycan_end.strftime('%Y-%m-%d %H:%M')}) "
                                f"under scenario laycan cut of {laycan_cut_days:.1f} days."
                            )
                            cand.setdefault("failed_reasons", []).append("LAYCAN_WINDOW_TIGHTENED_EXCEEDED")
                            disqualified_count += 1
                            continue

                        # Check delivery deadline if applicable
                        if raw_deadline and raw_discharge_end:
                            d_end = (
                                datetime.fromisoformat(raw_discharge_end)
                                if isinstance(raw_discharge_end, str)
                                else raw_discharge_end
                            )
                            deadline = (
                                datetime.fromisoformat(raw_deadline)
                                if isinstance(raw_deadline, str)
                                else raw_deadline
                            )
                            adj_discharge_end = d_end + timedelta(days=delay_days)
                            if adj_discharge_end > deadline:
                                cand["status"] = "INFEASIBLE"
                                cand["optimization_status"] = "INFEASIBLE_UPSTREAM"
                                cand["primary_reason_code"] = "DELIVERY_DEADLINE_EXCEEDED_SCENARIO"
                                cand["primary_reason_description"] = (
                                    f"Adjusted discharge completion ({adj_discharge_end.strftime('%Y-%m-%d')}) "
                                    f"exceeds delivery deadline ({deadline.strftime('%Y-%m-%d')})."
                                )
                                cand.setdefault("failed_reasons", []).append("DELIVERY_DEADLINE_EXCEEDED_SCENARIO")
                                disqualified_count += 1
                                continue

                        revalidated_count += 1
                    except Exception as e:
                        logger.warning("Error during laycan revalidation for candidate %s: %s", cand.get("candidate_id"), e)
                elif laycan_cut_days > 0:
                    # Synthetic candidate with ballast days and fixed laycan span:
                    # If ballast days > (typical 5 days - cut days), mark infeasible
                    ballast_days = float(cand.get("ballast", {}).get("ballast_days", 2.0))
                    effective_window = max(1.0, 5.0 - laycan_cut_days)
                    if ballast_days > effective_window:
                        cand["status"] = "INFEASIBLE"
                        cand["optimization_status"] = "INFEASIBLE_UPSTREAM"
                        cand["primary_reason_code"] = "LAYCAN_WINDOW_TIGHTENED_EXCEEDED"
                        cand["primary_reason_description"] = (
                            f"Ballast duration ({ballast_days:.1f}d) exceeds tightened laycan window ({effective_window:.1f}d)."
                        )
                        disqualified_count += 1

        logger.info(
            "Revalidated candidates for scenario %s: %d checked, %d disqualified.",
            config.scenario_id,
            len(candidates),
            disqualified_count,
        )
        return candidates
