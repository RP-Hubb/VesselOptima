"""
VesselOptima — Pydantic Schemas: Data Status & Offline Packages
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class DatasetStatusItem(BaseModel):
    dataset_name: str
    file_path: str
    sha256: str
    row_count: int
    schema_version: str
    provenance_type: str

    model_config = {"from_attributes": True}


class DataStatusResponse(BaseModel):
    runtime_mode: str
    package_id: Optional[str] = None
    package_version: Optional[str] = None
    integrity_status: str
    provenance: str
    loaded_at: Optional[datetime] = None
    manifest_hash: Optional[str] = None
    total_datasets: int = 0
    total_records: int = 0
    datasets: List[DatasetStatusItem] = []

    model_config = {"from_attributes": True}


class PackageVerificationResponse(BaseModel):
    status: str
    package_id: str
    package_type: str
    version: str
    manifest_hash: str
    files_verified: int
    total_rows: int
    provenance: str
    verified_at: str


# ── Phase 12 Data Governance Schemas ───────────────────────────────────

class DatasetImportRequest(BaseModel):
    dataset_type: str
    name: str
    records: List[dict]
    filename: Optional[str] = None
    description: Optional[str] = None
    actor: str = "data_engineer"
    actor_role: str = "ANALYST"
    dataset_id: Optional[str] = None


class DatasetVersionImportRequest(BaseModel):
    records: List[dict]
    change_summary: str
    filename: Optional[str] = None
    actor: str = "data_engineer"


class DatasetApprovalRequest(BaseModel):
    actor: str = "fleet_director"
    actor_role: str = "APPROVER"
    notes: Optional[str] = None


class DatasetRejectionRequest(BaseModel):
    reason: str
    actor: str = "fleet_director"
    actor_role: str = "APPROVER"


class DatasetResponse(BaseModel):
    id: Optional[int] = None
    dataset_id: str
    dataset_type: str
    name: str
    description: Optional[str] = None
    current_version: int
    status: str
    content_hash: str
    quality_score: float
    freshness_status: str
    record_count: int
    created_by: str
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    created_at: Optional[str] = None


class QuarantineItemResponse(BaseModel):
    id: Optional[int] = None
    record_identifier: Optional[str] = None
    field_name: Optional[str] = None
    original_value: Optional[str] = None
    error_code: str
    severity: str
    message: str
    raw_record: Optional[dict] = None
    quarantined_at: Optional[str] = None


class DatasetDiffResponse(BaseModel):
    dataset_id: str
    base_version: int
    target_version: int
    total_changes: int
    changes: List[dict]


class DatasetImpactResponse(BaseModel):
    dataset_id: str
    dataset_type: str
    version_number: int
    impact_level: str
    affected_engines: List[str]
    affected_runs: List[str]
    requires_recalculation: bool
    stale_decision_packages: List[str]
    rationale: str

