"""
VesselOptima — Phase 8: Scenario Analysis, Sensitivity & What-If Engine

Re-exports the core engines, models, presets, and orchestration service.
"""

from app.engines.scenarios.config import (
    ScenarioConfig,
    ScenarioPresets,
    ScenarioType,
)
from app.engines.scenarios.transform import (
    ScenarioTransformer,
    hash_candidate_set,
)
from app.engines.scenarios.revalidation import (
    ScenarioRevalidator,
)
from app.engines.scenarios.comparison import (
    AssignmentDeltaClassifier,
    AssignmentDifferenceEngine,
    CandidateDelta,
    CandidateDeltaStatus,
    CargoDelta,
    CargoDeltaStatus,
    ScenarioComparisonResult,
    VesselPlanDelta,
)
from app.engines.scenarios.sensitivity import (
    BreakEvenThreshold,
    SensitivityEngine,
    SensitivityPoint,
    SensitivityResult,
)
from app.engines.scenarios.robustness import (
    AssignmentRobustnessScore,
    RobustnessEngine,
    RobustnessEvaluationResult,
    RobustnessTier,
)
from app.engines.scenarios.service import (
    ScenarioService,
)

__all__ = [
    "ScenarioConfig",
    "ScenarioPresets",
    "ScenarioType",
    "ScenarioTransformer",
    "hash_candidate_set",
    "ScenarioRevalidator",
    "AssignmentDifferenceEngine",
    "CandidateDelta",
    "CandidateDeltaStatus",
    "CargoDelta",
    "CargoDeltaStatus",
    "ScenarioComparisonResult",
    "VesselPlanDelta",
    "BreakEvenThreshold",
    "SensitivityEngine",
    "SensitivityPoint",
    "SensitivityResult",
    "AssignmentRobustnessScore",
    "RobustnessEngine",
    "RobustnessEvaluationResult",
    "RobustnessTier",
    "ScenarioService",
]
