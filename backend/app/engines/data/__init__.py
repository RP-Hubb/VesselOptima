"""
VesselOptima — Phase 12 Maritime Data Integration & Quality Governance Engine
Public Package Interface
"""

from app.engines.data.adapters.base import (
    DataSourceAdapter,
    FutureLiveApiAdapter,
)
from app.engines.data.adapters.local_file import LocalFileAdapter
from app.engines.data.contracts import (
    DatasetContract,
    FieldContract,
    get_contract,
)
from app.engines.data.hashing import (
    compute_canonical_hash,
    compute_dataset_hash,
    compute_record_hash,
    verify_dataset_integrity,
)
from app.engines.data.impact import analyze_dataset_impact
from app.engines.data.models import (
    DatasetDiffResult,
    FieldValidationIssue,
    ImpactAnalysisResult,
    QualityScoreResult,
    RecordDiff,
    ValidationResult,
)
from app.engines.data.normalization import (
    normalize_numeric_string,
    normalize_record,
    normalize_timestamp_to_utc,
)
from app.engines.data.quality import (
    calculate_data_quality_score,
    evaluate_freshness,
)
from app.engines.data.quarantine import build_quarantine_records
from app.engines.data.reason_codes import (
    DataGovernanceReasonCode,
    DatasetStatus,
    DatasetType,
    FreshnessStatus,
    ImpactLevel,
    QuarantineSeverity,
    RecordChangeType,
    ValidationLayer,
)
from app.engines.data.service import DataGovernanceService
from app.engines.data.validation import validate_dataset_records
from app.engines.data.versioning import (
    compare_datasets,
    extract_business_key,
)

__all__ = [
    "DatasetType",
    "DatasetStatus",
    "ValidationLayer",
    "QuarantineSeverity",
    "FreshnessStatus",
    "ImpactLevel",
    "RecordChangeType",
    "DataGovernanceReasonCode",
    "FieldContract",
    "DatasetContract",
    "get_contract",
    "FieldValidationIssue",
    "ValidationResult",
    "QualityScoreResult",
    "RecordDiff",
    "DatasetDiffResult",
    "ImpactAnalysisResult",
    "normalize_numeric_string",
    "normalize_timestamp_to_utc",
    "normalize_record",
    "validate_dataset_records",
    "build_quarantine_records",
    "evaluate_freshness",
    "calculate_data_quality_score",
    "compute_canonical_hash",
    "compute_record_hash",
    "compute_dataset_hash",
    "verify_dataset_integrity",
    "compare_datasets",
    "extract_business_key",
    "analyze_dataset_impact",
    "DataGovernanceService",
    "DataSourceAdapter",
    "LocalFileAdapter",
    "FutureLiveApiAdapter",
]
