"""
VesselOptima — Phase 12 Maritime Data Integration & Quality Governance
Internal Dataclasses and Inspection Models
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.engines.data.reason_codes import (
    DataGovernanceReasonCode,
    FreshnessStatus,
    ImpactLevel,
    QuarantineSeverity,
    RecordChangeType,
    ValidationLayer,
)


@dataclass
class FieldValidationIssue:
    """Detailed validation issue identified on a specific record and field."""
    record_index: int
    business_key: Optional[str]
    field_name: Optional[str]
    original_value: Any
    layer: ValidationLayer
    error_code: DataGovernanceReasonCode
    severity: QuarantineSeverity
    message: str


@dataclass
class ValidationResult:
    """Outcome of running 4-layer validation across an ingested dataset."""
    is_valid: bool
    total_records: int
    valid_records_count: int
    quarantined_records_count: int
    rejected_records_count: int
    layer_results: Dict[str, bool]
    issues: List[FieldValidationIssue] = field(default_factory=list)
    execution_time_seconds: float = 0.0


@dataclass
class QualityScoreResult:
    """Outcome of transparent 6-factor quality score evaluation."""
    overall_score: float
    completeness_score: float
    validity_score: float
    consistency_score: float
    uniqueness_score: float
    timeliness_score: float
    provenance_score: float
    weights: Dict[str, float]
    freshness_status: FreshnessStatus
    freshness_age_hours: Optional[float] = None
    evaluated_at: Optional[datetime] = None


@dataclass
class RecordDiff:
    """Differential record comparison between two dataset versions."""
    record_identifier: str
    change_type: RecordChangeType
    field_diffs: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class DatasetDiffResult:
    """Comprehensive difference analysis between base and target dataset versions."""
    dataset_id: str
    base_version: int
    target_version: int
    total_base_records: int
    total_target_records: int
    added_count: int
    removed_count: int
    modified_count: int
    unchanged_count: int
    changes: List[RecordDiff] = field(default_factory=list)
    summary: str = ""


@dataclass
class ImpactAnalysisResult:
    """Downstream dependency and stale decision analysis across Phases 4–11."""
    dataset_id: str
    dataset_type: str
    version_number: int
    impact_level: ImpactLevel
    affected_engines: List[str]
    affected_runs: List[str]
    requires_recalculation: bool
    stale_decision_packages: List[str] = field(default_factory=list)
    rationale: str = ""
