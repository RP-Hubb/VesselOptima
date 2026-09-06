"""
VesselOptima — Phase 7: MILP Optimization Reason Codes & Statuses

Deterministic status enums and audit reason codes for mathematical optimization,
opportunity selection, trade-off explanation, and solver diagnostics.
"""

import enum


class OptimizationStatus(str, enum.Enum):
    """Solver termination status. Distinguishes proved optimality from heuristic or time-limited solutions."""
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNBOUNDED = "UNBOUNDED"
    TIME_LIMIT = "TIME_LIMIT"
    SOLVER_ERROR = "SOLVER_ERROR"
    EMPTY_MODEL = "EMPTY_MODEL"


class AssignmentSelectionStatus(str, enum.Enum):
    """Categorization of individual candidate decisions."""
    SELECTED = "SELECTED"
    MODEL_REJECTED = "MODEL_REJECTED"
    INFEASIBLE_UPSTREAM = "INFEASIBLE_UPSTREAM"
    UNASSIGNED = "UNASSIGNED"


class TradeOffReasonCode(str, enum.Enum):
    """Deterministic trade-off reason codes for auditability and explainability."""
    OPTIMAL_GLOBAL_ALLOCATION = "OPTIMAL_GLOBAL_ALLOCATION"
    LOWER_NET_CONTRIBUTION = "LOWER_NET_CONTRIBUTION"
    CARGO_EXCLUSIVITY_LOST = "CARGO_EXCLUSIVITY_LOST"
    VESSEL_TIMELINE_CONFLICT = "VESSEL_TIMELINE_CONFLICT"
    COMMITMENT_PROTECTED = "COMMITMENT_PROTECTED"
    NEGATIVE_ECONOMIC_CONTRIBUTION = "NEGATIVE_ECONOMIC_CONTRIBUTION"
    IDLE_SAVINGS_INSUFFICIENT = "IDLE_SAVINGS_INSUFFICIENT"
    TRANSITION_WINDOW_VIOLATED = "TRANSITION_WINDOW_VIOLATED"
    UNSERVED_OPTIONAL_REJECTION = "UNSERVED_OPTIONAL_REJECTION"


TRADE_OFF_DESCRIPTIONS: dict[TradeOffReasonCode, str] = {
    TradeOffReasonCode.OPTIMAL_GLOBAL_ALLOCATION: "Selected in the global optimal fleet assignment to maximize portfolio contribution.",
    TradeOffReasonCode.LOWER_NET_CONTRIBUTION: "Candidate was feasible but not selected because an alternative allocation yielded a higher global objective.",
    TradeOffReasonCode.CARGO_EXCLUSIVITY_LOST: "Another vessel was allocated to this cargo parcel, delivering higher global economic value.",
    TradeOffReasonCode.VESSEL_TIMELINE_CONFLICT: "Vessel was allocated to a higher-yielding overlapping employment opportunity.",
    TradeOffReasonCode.COMMITMENT_PROTECTED: "Candidate overlaps with a confirmed commercial commitment / fixture and was excluded.",
    TradeOffReasonCode.NEGATIVE_ECONOMIC_CONTRIBUTION: "Voyage operating and fuel expenses exceed expected revenue; unassigned to avoid loss.",
    TradeOffReasonCode.IDLE_SAVINGS_INSUFFICIENT: "Avoided idle holding cost did not justify the operational positioning expenditure.",
    TradeOffReasonCode.TRANSITION_WINDOW_VIOLATED: "Insufficient inter-voyage window for ballast repositioning and port turnaround.",
    TradeOffReasonCode.UNSERVED_OPTIONAL_REJECTION: "Cargo parcel remained unserved because serving it would decrease total fleet net contribution.",
}
