"""
VesselOptima — Phase 7: MILP Optimization Engine Package
"""

from app.engines.optimization.constraints import (
    ConstraintBuilder,
    LinearConstraintDefinition,
)
from app.engines.optimization.model import OptimizationModel
from app.engines.optimization.objective import (
    ObjectiveBuilder,
    ObjectiveConfig,
    ObjectiveDecomposition,
)
from app.engines.optimization.reason_codes import (
    AssignmentSelectionStatus,
    OptimizationStatus,
    TradeOffReasonCode,
    TRADE_OFF_DESCRIPTIONS,
)
from app.engines.optimization.result import (
    AssignmentResult,
    OptimizationResult,
    UnassignedCargoResult,
)
from app.engines.optimization.service import OptimizationService
from app.engines.optimization.solver import (
    BaseSolverAdapter,
    HiGHSSolverAdapter,
    RawSolverResult,
)
from app.engines.optimization.variables import (
    CandidateVariable,
    CargoSlackVariable,
    VariableRegistry,
)

__all__ = [
    "OptimizationService",
    "OptimizationModel",
    "VariableRegistry",
    "CandidateVariable",
    "CargoSlackVariable",
    "ConstraintBuilder",
    "LinearConstraintDefinition",
    "ObjectiveBuilder",
    "ObjectiveConfig",
    "ObjectiveDecomposition",
    "BaseSolverAdapter",
    "HiGHSSolverAdapter",
    "RawSolverResult",
    "OptimizationResult",
    "AssignmentResult",
    "UnassignedCargoResult",
    "OptimizationStatus",
    "AssignmentSelectionStatus",
    "TradeOffReasonCode",
    "TRADE_OFF_DESCRIPTIONS",
]
