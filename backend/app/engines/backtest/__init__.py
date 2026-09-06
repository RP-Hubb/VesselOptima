"""
VesselOptima — Phase 13: Historical Backtesting & Decision Replay Package
"""

from app.engines.backtest.reason_codes import (
    AssociatedDriver,
    BacktestMode,
    BacktestRunStatus,
    BenchmarkStrategyType,
    DecisionFrequency,
    FailureReason,
    HistoricalEventType,
    LeakageCode,
)
from app.engines.backtest.events import (
    HistoricalEvent,
    HistoricalEventStream,
    compute_event_hash,
)
from app.engines.backtest.snapshot import (
    PointInTimeSnapshot,
    PointInTimeSnapshotEngine,
)
from app.engines.backtest.leakage import (
    InformationLeakageDetector,
    LeakageReport,
    LeakageViolation,
)
from app.engines.backtest.timeline import (
    DecisionTimelineEngine,
    DecisionTimelinePoint,
)
from app.engines.backtest.outcome import (
    RealizedAssignmentOutcome,
    RealizedOutcomeEngine,
)
from app.engines.backtest.benchmarks import (
    BenchmarkDecisionResult,
    BenchmarkStrategy,
    BestExpectedContributionStrategy,
    ContinueCurrentEmploymentStrategy,
    FirstFeasibleStrategy,
    HistoricalActualOutcomeBenchmark,
    NoActionStrategy,
    get_default_benchmarks,
)
from app.engines.backtest.metrics import (
    BacktestMetricsCalculator,
    BacktestMetricsSummary,
    PerformanceCurvePoint,
)
from app.engines.backtest.attribution import (
    AttributionRecord,
    DecisionAttributionEngine,
)
from app.engines.backtest.orchestrator import (
    BacktestExecutionResult,
    BacktestOrchestrator,
    ReplayDecisionRecord,
)
from app.engines.backtest.service import BacktestingService

__all__ = [
    "AssociatedDriver",
    "BacktestMode",
    "BacktestRunStatus",
    "BenchmarkStrategyType",
    "DecisionFrequency",
    "FailureReason",
    "HistoricalEventType",
    "LeakageCode",
    "HistoricalEvent",
    "HistoricalEventStream",
    "compute_event_hash",
    "PointInTimeSnapshot",
    "PointInTimeSnapshotEngine",
    "InformationLeakageDetector",
    "LeakageReport",
    "LeakageViolation",
    "DecisionTimelineEngine",
    "DecisionTimelinePoint",
    "RealizedAssignmentOutcome",
    "RealizedOutcomeEngine",
    "BenchmarkDecisionResult",
    "BenchmarkStrategy",
    "BestExpectedContributionStrategy",
    "ContinueCurrentEmploymentStrategy",
    "FirstFeasibleStrategy",
    "HistoricalActualOutcomeBenchmark",
    "NoActionStrategy",
    "get_default_benchmarks",
    "BacktestMetricsCalculator",
    "BacktestMetricsSummary",
    "PerformanceCurvePoint",
    "AttributionRecord",
    "DecisionAttributionEngine",
    "BacktestExecutionResult",
    "BacktestOrchestrator",
    "ReplayDecisionRecord",
    "BacktestingService",
]
