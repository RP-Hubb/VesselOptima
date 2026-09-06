"""
VesselOptima — Phase 7: Optimization Result Models

Defines the rich, auditable output data structures representing the optimal fleet allocation,
trade-off explanations, objective decomposition, and solver diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from app.engines.optimization.objective import ObjectiveDecomposition
from app.engines.optimization.reason_codes import (
    AssignmentSelectionStatus,
    OptimizationStatus,
    TradeOffReasonCode,
    TRADE_OFF_DESCRIPTIONS,
)


@dataclass
class AssignmentResult:
    """Detailed assignment record for a candidate voyage considered by the optimization engine."""
    candidate_id: str
    vessel_id: int
    vessel_name: str
    cargo_id: Optional[int]
    cargo_name: str
    is_selected: bool
    selection_status: AssignmentSelectionStatus
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    expected_revenue: float
    voyage_cost: float
    gross_contribution: float
    idle_days_saved: float = 0.0
    avoided_idle_cost: float = 0.0
    ballast_distance_nm: float = 0.0
    ballast_days: float = 0.0
    voyage_days: float = 0.0
    trade_off_reason_code: TradeOffReasonCode = TradeOffReasonCode.OPTIMAL_GLOBAL_ALLOCATION
    trade_off_explanation: str = ""
    assignment_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "vessel_id": self.vessel_id,
            "vessel_name": self.vessel_name,
            "cargo_id": self.cargo_id,
            "cargo_name": self.cargo_name,
            "is_selected": self.is_selected,
            "selection_status": self.selection_status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "expected_revenue": round(self.expected_revenue, 2),
            "voyage_cost": round(self.voyage_cost, 2),
            "gross_contribution": round(self.gross_contribution, 2),
            "idle_days_saved": round(self.idle_days_saved, 2),
            "avoided_idle_cost": round(self.avoided_idle_cost, 2),
            "ballast_distance_nm": round(self.ballast_distance_nm, 1),
            "ballast_days": round(self.ballast_days, 2),
            "voyage_days": round(self.voyage_days, 2),
            "trade_off_reason_code": self.trade_off_reason_code.value,
            "trade_off_explanation": self.trade_off_explanation or TRADE_OFF_DESCRIPTIONS.get(self.trade_off_reason_code, ""),
            "assignment_metadata": self.assignment_metadata,
        }


@dataclass
class UnassignedCargoResult:
    """Record of a cargo parcel left unserved by the global optimization allocation."""
    cargo_id: int
    cargo_name: str
    unserved_penalty: float = 0.0
    reason_code: TradeOffReasonCode = TradeOffReasonCode.UNSERVED_OPTIONAL_REJECTION
    reason_explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cargo_id": self.cargo_id,
            "cargo_name": self.cargo_name,
            "unserved_penalty": round(self.unserved_penalty, 2),
            "reason_code": self.reason_code.value,
            "reason_explanation": self.reason_explanation or TRADE_OFF_DESCRIPTIONS.get(self.reason_code, ""),
        }


@dataclass
class OptimizationResult:
    """Comprehensive, auditable result of a global fleet MILP optimization run."""
    run_id: str
    status: OptimizationStatus
    objective_value: float
    decomposition: ObjectiveDecomposition
    selected_assignments: list[AssignmentResult] = field(default_factory=list)
    rejected_opportunities: list[AssignmentResult] = field(default_factory=list)
    unassigned_cargos: list[UnassignedCargoResult] = field(default_factory=list)
    vessel_utilization: dict[str, Any] = field(default_factory=dict)
    solver_metadata: dict[str, Any] = field(default_factory=dict)
    constraint_summary: dict[str, Any] = field(default_factory=dict)
    audit_trail: list[dict[str, Any]] = field(default_factory=list)
    solve_time_seconds: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status.value,
            "objective_value": round(self.objective_value, 2),
            "decomposition": self.decomposition.to_dict(),
            "selected_assignments": [a.to_dict() for a in self.selected_assignments],
            "rejected_opportunities": [a.to_dict() for a in self.rejected_opportunities],
            "unassigned_cargos": [c.to_dict() for c in self.unassigned_cargos],
            "vessel_utilization": self.vessel_utilization,
            "solver_metadata": self.solver_metadata,
            "constraint_summary": self.constraint_summary,
            "audit_trail": self.audit_trail,
            "solve_time_seconds": round(self.solve_time_seconds, 4),
            "created_at": self.created_at.isoformat(),
        }
