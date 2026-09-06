"""
VesselOptima — Phase 8: Baseline vs Scenario Comparison & Assignment Difference Engine

Computes financial, operational, and assignment deltas between a baseline
optimization run and a scenario run. Implements deterministic assignment
delta classification: UNCHANGED, ADDED, DROPPED, REPLACED.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import logging
from typing import Any, Dict, List, Optional, Set

from app.engines.optimization.result import AssignmentResult, OptimizationResult

logger = logging.getLogger("vesseloptima.engines.scenarios.comparison")


class CandidateDeltaStatus(str, Enum):
    UNCHANGED = "UNCHANGED"
    ADDED = "ADDED"
    DROPPED = "DROPPED"
    REJECTED = "REJECTED"


class CargoDeltaStatus(str, Enum):
    UNCHANGED = "UNCHANGED"
    REPLACED = "REPLACED"
    DROPPED_TO_UNSERVED = "DROPPED_TO_UNSERVED"
    NEWLY_SERVED = "NEWLY_SERVED"


@dataclass
class CandidateDelta:
    candidate_id: str
    vessel_id: int
    vessel_name: str
    cargo_id: Optional[int]
    cargo_name: str
    delta_status: CandidateDeltaStatus
    in_baseline: bool
    in_scenario: bool
    baseline_revenue: float = 0.0
    scenario_revenue: float = 0.0
    baseline_cost: float = 0.0
    scenario_cost: float = 0.0
    baseline_net_contribution: float = 0.0
    scenario_net_contribution: float = 0.0
    contribution_delta: float = 0.0
    trade_off_explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["delta_status"] = self.delta_status.value
        return d


@dataclass
class CargoDelta:
    cargo_id: int
    cargo_name: str
    delta_status: CargoDeltaStatus
    baseline_vessel_id: Optional[int]
    baseline_vessel_name: Optional[str]
    scenario_vessel_id: Optional[int]
    scenario_vessel_name: Optional[str]
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["delta_status"] = self.delta_status.value
        return d


@dataclass
class VesselPlanDelta:
    vessel_id: int
    vessel_name: str
    baseline_cargo_id: Optional[int]
    baseline_cargo_name: Optional[str]
    scenario_cargo_id: Optional[int]
    scenario_cargo_name: Optional[str]
    is_assignment_changed: bool
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScenarioComparisonResult:
    scenario_id: str
    scenario_name: str
    baseline_run_id: str
    scenario_run_id: str

    # Financial & Objective KPIs
    objective_value_baseline: float
    objective_value_scenario: float
    objective_value_delta: float
    objective_value_pct_change: float

    total_revenue_baseline: float
    total_revenue_scenario: float
    total_revenue_delta: float

    total_cost_baseline: float
    total_cost_scenario: float
    total_cost_delta: float

    net_contribution_baseline: float
    net_contribution_scenario: float
    net_contribution_delta: float

    idle_cost_avoided_baseline: float
    idle_cost_avoided_scenario: float
    idle_cost_avoided_delta: float

    # Operational KPIs
    cargoes_served_baseline: int
    cargoes_served_scenario: int
    cargoes_served_delta: int

    cargoes_unserved_baseline: int
    cargoes_unserved_scenario: int
    cargoes_unserved_delta: int

    vessels_utilized_baseline: int
    vessels_utilized_scenario: int
    vessels_utilized_delta: int

    total_ballast_nm_baseline: float
    total_ballast_nm_scenario: float
    total_ballast_nm_delta: float

    # Stability & Delta Counts
    unchanged_assignments_count: int
    added_assignments_count: int
    dropped_assignments_count: int
    jaccard_similarity: float
    stability_score_pct: float

    # Granular Deltas
    candidate_deltas: List[CandidateDelta] = field(default_factory=list)
    cargo_deltas: List[CargoDelta] = field(default_factory=list)
    vessel_deltas: List[VesselPlanDelta] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["candidate_deltas"] = [c.to_dict() for c in self.candidate_deltas]
        d["cargo_deltas"] = [c.to_dict() for c in self.cargo_deltas]
        d["vessel_deltas"] = [v.to_dict() for v in self.vessel_deltas]
        return d


class AssignmentDifferenceEngine:
    """
    Deterministically compares two optimization solutions.
    """

    @classmethod
    def compare(
        cls,
        baseline_result: OptimizationResult,
        scenario_result: OptimizationResult,
        scenario_id: str = "SCENARIO",
        scenario_name: str = "What-If Scenario",
    ) -> ScenarioComparisonResult:
        """
        Executes granular delta comparison between baseline and scenario runs.
        """
        # 1. Map assignments by candidate_id
        base_sel_map: Dict[str, AssignmentResult] = {
            a.candidate_id: a for a in baseline_result.selected_assignments
        }
        base_all_map: Dict[str, AssignmentResult] = {
            a.candidate_id: a
            for a in (baseline_result.selected_assignments + baseline_result.rejected_opportunities)
        }

        scen_sel_map: Dict[str, AssignmentResult] = {
            a.candidate_id: a for a in scenario_result.selected_assignments
        }
        scen_all_map: Dict[str, AssignmentResult] = {
            a.candidate_id: a
            for a in (scenario_result.selected_assignments + scenario_result.rejected_opportunities)
        }

        all_cand_ids = sorted(list(set(base_all_map.keys()) | set(scen_all_map.keys())))

        candidate_deltas: List[CandidateDelta] = []
        unchanged_count = 0
        added_count = 0
        dropped_count = 0

        for cid in all_cand_ids:
            in_base = cid in base_sel_map
            in_scen = cid in scen_sel_map

            ref_a = scen_all_map.get(cid) or base_all_map.get(cid)
            if not ref_a:
                continue

            base_a = base_all_map.get(cid)
            scen_a = scen_all_map.get(cid)

            b_rev = base_a.expected_revenue if base_a else 0.0
            s_rev = scen_a.expected_revenue if scen_a else 0.0
            b_cost = base_a.voyage_cost if base_a else 0.0
            s_cost = scen_a.voyage_cost if scen_a else 0.0
            b_contrib = base_a.gross_contribution if base_a else 0.0
            s_contrib = scen_a.gross_contribution if scen_a else 0.0

            if in_base and in_scen:
                d_status = CandidateDeltaStatus.UNCHANGED
                unchanged_count += 1
                expl = "Candidate remained optimal in both baseline and scenario."
            elif not in_base and in_scen:
                d_status = CandidateDeltaStatus.ADDED
                added_count += 1
                expl = "Newly optimal candidate selected under scenario parameters."
            elif in_base and not in_scen:
                d_status = CandidateDeltaStatus.DROPPED
                dropped_count += 1
                expl = scen_a.trade_off_explanation if scen_a else "Displaced by alternative allocation in scenario."
            else:
                d_status = CandidateDeltaStatus.REJECTED
                expl = "Sub-optimal in both baseline and scenario."

            candidate_deltas.append(
                CandidateDelta(
                    candidate_id=cid,
                    vessel_id=ref_a.vessel_id,
                    vessel_name=ref_a.vessel_name,
                    cargo_id=ref_a.cargo_id,
                    cargo_name=ref_a.cargo_name,
                    delta_status=d_status,
                    in_baseline=in_base,
                    in_scenario=in_scen,
                    baseline_revenue=b_rev,
                    scenario_revenue=s_rev,
                    baseline_cost=b_cost,
                    scenario_cost=s_cost,
                    baseline_net_contribution=b_contrib,
                    scenario_net_contribution=s_contrib,
                    contribution_delta=round(s_contrib - b_contrib, 2),
                    trade_off_explanation=expl,
                )
            )

        # 2. Cargo Allocation Deltas
        base_cargo_to_vessel: Dict[int, Tuple[int, str, str]] = {}
        for a in baseline_result.selected_assignments:
            if a.cargo_id is not None:
                base_cargo_to_vessel[a.cargo_id] = (a.vessel_id, a.vessel_name, a.cargo_name)

        scen_cargo_to_vessel: Dict[int, Tuple[int, str, str]] = {}
        for a in scenario_result.selected_assignments:
            if a.cargo_id is not None:
                scen_cargo_to_vessel[a.cargo_id] = (a.vessel_id, a.vessel_name, a.cargo_name)

        # Include unassigned cargos in universe
        all_cargos_info: Dict[int, str] = {}
        for c in baseline_result.unassigned_cargos:
            all_cargos_info[c.cargo_id] = c.cargo_name
        for c in scenario_result.unassigned_cargos:
            all_cargos_info[c.cargo_id] = c.cargo_name
        for cid, (vid, vname, cname) in base_cargo_to_vessel.items():
            all_cargos_info[cid] = cname
        for cid, (vid, vname, cname) in scen_cargo_to_vessel.items():
            all_cargos_info[cid] = cname

        cargo_deltas: List[CargoDelta] = []
        for cid in sorted(all_cargos_info.keys()):
            cname = all_cargos_info[cid]
            base_info = base_cargo_to_vessel.get(cid)
            scen_info = scen_cargo_to_vessel.get(cid)

            b_vid = base_info[0] if base_info else None
            b_vname = base_info[1] if base_info else None
            s_vid = scen_info[0] if scen_info else None
            s_vname = scen_info[1] if scen_info else None

            if b_vid is not None and s_vid is not None:
                if b_vid == s_vid:
                    c_status = CargoDeltaStatus.UNCHANGED
                    expl = f"Maintains assignment to {b_vname}."
                else:
                    c_status = CargoDeltaStatus.REPLACED
                    expl = f"Allocation switched from {b_vname} to {s_vname}."
            elif b_vid is not None and s_vid is None:
                c_status = CargoDeltaStatus.DROPPED_TO_UNSERVED
                expl = f"Dropped from {b_vname} into unassigned pool due to economic / feasibility change."
            elif b_vid is None and s_vid is not None:
                c_status = CargoDeltaStatus.NEWLY_SERVED
                expl = f"Newly picked up by {s_vname}."
            else:
                c_status = CargoDeltaStatus.UNCHANGED
                expl = "Unserved in both baseline and scenario."

            cargo_deltas.append(
                CargoDelta(
                    cargo_id=cid,
                    cargo_name=cname,
                    delta_status=c_status,
                    baseline_vessel_id=b_vid,
                    baseline_vessel_name=b_vname,
                    scenario_vessel_id=s_vid,
                    scenario_vessel_name=s_vname,
                    explanation=expl,
                )
            )

        # 3. Vessel Allocation Deltas
        base_vessel_plan: Dict[int, Tuple[str, Optional[int], Optional[str]]] = {}
        for a in baseline_result.selected_assignments:
            base_vessel_plan[a.vessel_id] = (a.vessel_name, a.cargo_id, a.cargo_name)

        scen_vessel_plan: Dict[int, Tuple[str, Optional[int], Optional[str]]] = {}
        for a in scenario_result.selected_assignments:
            scen_vessel_plan[a.vessel_id] = (a.vessel_name, a.cargo_id, a.cargo_name)

        all_vids = sorted(list(set(base_vessel_plan.keys()) | set(scen_vessel_plan.keys())))
        vessel_deltas: List[VesselPlanDelta] = []

        for vid in all_vids:
            b_tuple = base_vessel_plan.get(vid)
            s_tuple = scen_vessel_plan.get(vid)

            vname = (s_tuple[0] if s_tuple else None) or (b_tuple[0] if b_tuple else f"Vessel {vid}")
            b_cid = b_tuple[1] if b_tuple else None
            b_cname = b_tuple[2] if b_tuple else None
            s_cid = s_tuple[1] if s_tuple else None
            s_cname = s_tuple[2] if s_tuple else None

            changed = (b_cid != s_cid)
            if changed:
                if b_cid and s_cid:
                    expl = f"Swapped cargo from {b_cname} to {s_cname}."
                elif b_cid and not s_cid:
                    expl = f"Released from {b_cname} to idle."
                else:
                    expl = f"Mobilized from idle to serve {s_cname}."
            else:
                expl = f"Preserves deployment on {s_cname}." if s_cid else "Remains idle in both plans."

            vessel_deltas.append(
                VesselPlanDelta(
                    vessel_id=vid,
                    vessel_name=vname,
                    baseline_cargo_id=b_cid,
                    baseline_cargo_name=b_cname,
                    scenario_cargo_id=s_cid,
                    scenario_cargo_name=s_cname,
                    is_assignment_changed=changed,
                    explanation=expl,
                )
            )

        # 4. Aggregate Metric Calculations
        b_decomp = baseline_result.decomposition
        s_decomp = scenario_result.decomposition

        obj_base = baseline_result.objective_value
        obj_scen = scenario_result.objective_value
        obj_delta = round(obj_scen - obj_base, 2)
        obj_pct = round((obj_delta / abs(obj_base) * 100.0), 2) if abs(obj_base) > 1e-6 else 0.0

        rev_base = getattr(b_decomp, "total_gross_revenue", getattr(b_decomp, "total_revenue", 0.0))
        rev_scen = getattr(s_decomp, "total_gross_revenue", getattr(s_decomp, "total_revenue", 0.0))
        rev_delta = round(rev_scen - rev_base, 2)

        cost_base = getattr(b_decomp, "total_voyage_cost", getattr(b_decomp, "total_cost", 0.0))
        cost_scen = getattr(s_decomp, "total_voyage_cost", getattr(s_decomp, "total_cost", 0.0))
        cost_delta = round(cost_scen - cost_base, 2)

        contrib_base = getattr(b_decomp, "total_net_contribution", getattr(b_decomp, "net_contribution", 0.0))
        contrib_scen = getattr(s_decomp, "total_net_contribution", getattr(s_decomp, "net_contribution", 0.0))
        contrib_delta = round(contrib_scen - contrib_base, 2)

        idle_base = getattr(b_decomp, "total_avoided_idle_cost", getattr(b_decomp, "idle_cost_avoided", 0.0))
        idle_scen = getattr(s_decomp, "total_avoided_idle_cost", getattr(s_decomp, "idle_cost_avoided", 0.0))
        idle_delta = round(idle_scen - idle_base, 2)


        cargo_base = len(base_cargo_to_vessel)
        cargo_scen = len(scen_cargo_to_vessel)
        cargo_delta = cargo_scen - cargo_base

        unserved_base = len(baseline_result.unassigned_cargos)
        unserved_scen = len(scenario_result.unassigned_cargos)
        unserved_delta = unserved_scen - unserved_base

        vessels_base = len(base_vessel_plan)
        vessels_scen = len(scen_vessel_plan)
        vessels_delta = vessels_scen - vessels_base

        ballast_base = round(sum(a.ballast_distance_nm for a in baseline_result.selected_assignments), 1)
        ballast_scen = round(sum(a.ballast_distance_nm for a in scenario_result.selected_assignments), 1)
        ballast_delta = round(ballast_scen - ballast_base, 1)

        # Stability
        union_count = len(set(base_sel_map.keys()) | set(scen_sel_map.keys()))
        jaccard = round((unchanged_count / union_count), 4) if union_count > 0 else 1.0
        base_sel_count = len(base_sel_map)
        stability_pct = round((unchanged_count / base_sel_count * 100.0), 1) if base_sel_count > 0 else 100.0

        return ScenarioComparisonResult(
            scenario_id=scenario_id,
            scenario_name=scenario_name,
            baseline_run_id=baseline_result.run_id,
            scenario_run_id=scenario_result.run_id,
            objective_value_baseline=round(obj_base, 2),
            objective_value_scenario=round(obj_scen, 2),
            objective_value_delta=obj_delta,
            objective_value_pct_change=obj_pct,
            total_revenue_baseline=round(rev_base, 2),
            total_revenue_scenario=round(rev_scen, 2),
            total_revenue_delta=rev_delta,
            total_cost_baseline=round(cost_base, 2),
            total_cost_scenario=round(cost_scen, 2),
            total_cost_delta=cost_delta,
            net_contribution_baseline=round(contrib_base, 2),
            net_contribution_scenario=round(contrib_scen, 2),
            net_contribution_delta=contrib_delta,
            idle_cost_avoided_baseline=round(idle_base, 2),
            idle_cost_avoided_scenario=round(idle_scen, 2),
            idle_cost_avoided_delta=idle_delta,
            cargoes_served_baseline=cargo_base,
            cargoes_served_scenario=cargo_scen,
            cargoes_served_delta=cargo_delta,
            cargoes_unserved_baseline=unserved_base,
            cargoes_unserved_scenario=unserved_scen,
            cargoes_unserved_delta=unserved_delta,
            vessels_utilized_baseline=vessels_base,
            vessels_utilized_scenario=vessels_scen,
            vessels_utilized_delta=vessels_delta,
            total_ballast_nm_baseline=ballast_base,
            total_ballast_nm_scenario=ballast_scen,
            total_ballast_nm_delta=ballast_delta,
            unchanged_assignments_count=unchanged_count,
            added_assignments_count=added_count,
            dropped_assignments_count=dropped_count,
            jaccard_similarity=jaccard,
            stability_score_pct=stability_pct,
            candidate_deltas=candidate_deltas,
            cargo_deltas=cargo_deltas,
            vessel_deltas=vessel_deltas,
        )


AssignmentDeltaClassifier = AssignmentDifferenceEngine

