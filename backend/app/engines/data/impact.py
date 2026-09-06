"""
VesselOptima — Phase 12 Maritime Data Integration & Quality Governance
Downstream Impact Analyzer & Stale Decision Package Detection
"""

from typing import Any, Dict, List, Optional

from app.engines.data.models import DatasetDiffResult, ImpactAnalysisResult
from app.engines.data.reason_codes import DatasetType, ImpactLevel


DOWNSTREAM_ENGINE_MAP: Dict[DatasetType, List[str]] = {
    DatasetType.VESSEL_MASTER: [
        "Phase 4: Vessel & Port Feasibility Engine",
        "Phase 6: Idle Management & Alternative Employment Engine",
        "Phase 7: HiGHS MILP Optimization Engine",
        "Phase 8: Scenario Analysis & Sensitivity Engine",
        "Phase 9: Risk Intelligence & Uncertainty Engine",
        "Phase 10: Decision Intelligence Engine",
        "Phase 11: Institutional Governance Layer",
    ],
    DatasetType.PORT_REFERENCE: [
        "Phase 4: Vessel & Port Feasibility Engine (Draft & LOA limits)",
        "Phase 6: Ballast & Repositioning Engine",
        "Phase 7: HiGHS MILP Optimization Engine (Port tariffs)",
        "Phase 8: Scenario Stress-Testing Engine",
    ],
    DatasetType.CARGO_DEMAND: [
        "Phase 4: Vessel & Port Feasibility Engine",
        "Phase 5: Dynamic Procurement Engine",
        "Phase 7: HiGHS MILP Optimization Engine",
        "Phase 8: Scenario Analysis & Sensitivity Engine",
        "Phase 9: Risk Intelligence Engine",
        "Phase 10: Decision Intelligence Engine",
        "Phase 11: Institutional Governance Layer",
    ],
    DatasetType.VOYAGE_FIXTURE: [
        "Phase 6: Vessel Commitment & Overlap Engine",
        "Phase 7: HiGHS MILP Optimization Engine",
        "Phase 8: Baseline Fleet Analysis",
    ],
    DatasetType.BUNKER_SERIES: [
        "Phase 5: Dynamic Procurement Cost Model",
        "Phase 6: Voyage Contribution Economics",
        "Phase 8: Bunker Price Sensitivity Sweeps",
        "Phase 9: Stochastic Fuel Price Distributions",
        "Phase 10: Economic Decision Hurdle Checks",
    ],
    DatasetType.OPERATIONAL_EVENT: [
        "Phase 6: Timeline & Milestone Validation Engine",
        "Phase 7: Fleet Availability Schedules",
        "Phase 9: Delay Probability Distributions",
    ],
}


def analyze_dataset_impact(
    dataset_id: str,
    dataset_type: DatasetType | str,
    version_number: int,
    diff_result: Optional[DatasetDiffResult] = None,
    affected_run_ids: Optional[List[str]] = None,
    dependent_package_ids: Optional[List[str]] = None,
) -> ImpactAnalysisResult:
    """
    Evaluates the systemic downstream impact across analytical Phases 4–11
    and identifies stale decision packages requiring institutional review.
    """
    dtype = DatasetType(dataset_type) if isinstance(dataset_type, str) else dataset_type
    affected_engines = DOWNSTREAM_ENGINE_MAP.get(dtype, ["Phase 7: HiGHS MILP Optimization Engine"])

    # Determine impact level based on diff scale and dataset domain
    has_changes = diff_result is not None and (diff_result.added_count > 0 or diff_result.modified_count > 0 or diff_result.removed_count > 0)

    if not has_changes and diff_result is not None:
        impact_level = ImpactLevel.NONE
        requires_recalc = False
        rationale = f"Dataset {dataset_id} V{version_number} has no record differences from prior version. Downstream runs unaffected."
    elif dtype in (DatasetType.VESSEL_MASTER, DatasetType.CARGO_DEMAND):
        impact_level = ImpactLevel.CRITICAL if diff_result and (diff_result.modified_count >= 2 or diff_result.added_count >= 2) else ImpactLevel.HIGH
        requires_recalc = True
        rationale = (
            f"Modifications to {dtype.value} alter the core feasibility admittance pool and MILP decision matrix. "
            f"Downstream allocations (Phase 7), stress testing (Phase 8), tail risk (Phase 9), and recommendations (Phase 10) "
            f"must be re-evaluated for subsequent decision packages."
        )
    elif dtype in (DatasetType.BUNKER_SERIES, DatasetType.PORT_REFERENCE):
        impact_level = ImpactLevel.MEDIUM
        requires_recalc = True
        rationale = f"Revisions to {dtype.value} impact operational cost models, voyage net contributions, and sensitivity curves."
    else:
        impact_level = ImpactLevel.LOW
        requires_recalc = False
        rationale = f"Operational updates to {dtype.value} logged for chronological tracking."

    stale_packages = dependent_package_ids or []

    return ImpactAnalysisResult(
        dataset_id=dataset_id,
        dataset_type=dtype.value,
        version_number=version_number,
        impact_level=impact_level,
        affected_engines=affected_engines,
        affected_runs=affected_run_ids or [],
        requires_recalculation=requires_recalc,
        stale_decision_packages=stale_packages,
        rationale=rationale,
    )
