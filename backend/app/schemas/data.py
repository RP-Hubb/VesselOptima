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
