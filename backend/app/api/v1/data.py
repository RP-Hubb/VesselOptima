"""
VesselOptima — API Endpoints: Data & Offline Packages
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.domain import OfflinePackage, OfflinePackageDataset
from app.schemas.data import DataStatusResponse, DatasetStatusItem, PackageVerificationResponse
from app.services.offline_package.exceptions import OfflinePackageError, OfflinePackageIntegrityError
from app.services.offline_package.loader import OfflinePackageIngestionService
from app.services.offline_package.manifest import verify_manifest
from app.services.runtime import RuntimeService

router = APIRouter(prefix="/data", tags=["data"])


def get_offline_package_dir() -> Path:
    pkg_dir = (Path(settings.offline_package_dir) / "demo-v1").resolve()
    if pkg_dir.exists():
        return pkg_dir
    repo_root = Path(__file__).resolve().parents[4]
    fallback_dir = repo_root / "data" / "offline" / "packages" / "demo-v1"
    if fallback_dir.exists():
        return fallback_dir
    return pkg_dir



@router.get("/status", response_model=DataStatusResponse)
def get_data_status(db: Session = Depends(get_db)):
    """
    Returns current data context, runtime mode, and offline package integrity status.
    """
    svc = RuntimeService(db)
    mode_info = svc.get_current_mode()
    mode = mode_info["mode"].value if hasattr(mode_info["mode"], "value") else str(mode_info["mode"])


    pkg = db.execute(
        select(OfflinePackage).order_by(OfflinePackage.id.desc())
    ).scalars().first()

    if not pkg:
        return DataStatusResponse(
            runtime_mode=mode,
            package_id=None,
            package_version=None,
            integrity_status="UNLOADED",
            provenance="NONE",
            loaded_at=None,
            manifest_hash=None,
            total_datasets=0,
            total_records=0,
            datasets=[],
        )

    datasets = db.execute(
        select(OfflinePackageDataset).where(OfflinePackageDataset.package_id == pkg.package_id)
    ).scalars().all()

    total_records = sum(d.row_count for d in datasets)

    return DataStatusResponse(
        runtime_mode=mode,
        package_id=pkg.package_id,
        package_version=pkg.schema_version,
        integrity_status=pkg.status,
        provenance="SYNTHETIC",
        loaded_at=pkg.created_at,
        manifest_hash=pkg.manifest_hash,
        total_datasets=len(datasets),
        total_records=total_records,
        datasets=[
            DatasetStatusItem(
                dataset_name=d.dataset_name,
                file_path=d.file_path,
                sha256=d.sha256,
                row_count=d.row_count,
                schema_version=d.schema_version,
                provenance_type=d.provenance_type.value,
            )
            for d in datasets
        ],
    )


@router.get("/offline/verify", response_model=PackageVerificationResponse)
def verify_offline_package():
    """
    Validates the SHA-256 hashes and row counts of the offline demo package.
    """
    pkg_dir = get_offline_package_dir()
    try:
        res = verify_manifest(pkg_dir)
        return PackageVerificationResponse(**res)
    except OfflinePackageIntegrityError as e:
        raise HTTPException(
            status_code=422,
            detail={"code": "OFFLINE_PACKAGE_INTEGRITY_ERROR", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "OFFLINE_PACKAGE_ERROR", "message": str(e)},
        )


@router.post("/offline/load")
def load_offline_package(
    force: bool = Query(default=False, description="Force re-ingestion of the offline package"),
    db: Session = Depends(get_db),
):
    """
    Loads the offline demonstration package into the database.
    Idempotent: skips if already loaded with matching hash unless force=True.
    """
    pkg_dir = get_offline_package_dir()
    service = OfflinePackageIngestionService(db)
    try:
        res = service.ingest_package(pkg_dir, force_reload=force)
        return res
    except OfflinePackageError as e:
        raise HTTPException(
            status_code=422,
            detail={"code": "OFFLINE_INGESTION_ERROR", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "SERVER_ERROR", "message": str(e)},
        )


# ── Phase 12 Data Governance Endpoints ─────────────────────────────────

from app.engines.data import DataGovernanceService
from app.schemas.data import (
    DatasetApprovalRequest,
    DatasetDiffResponse,
    DatasetImpactResponse,
    DatasetImportRequest,
    DatasetRejectionRequest,
    DatasetResponse,
    DatasetVersionImportRequest,
    QuarantineItemResponse,
)


@router.post("/import", response_model=dict)
def import_dataset(
    req: DatasetImportRequest,
    db: Session = Depends(get_db),
):
    """Ingests untrusted maritime dataset through the 4-layer validation & governance pipeline."""
    try:
        svc = DataGovernanceService(db)
        return svc.import_dataset(
            dataset_type=req.dataset_type,
            name=req.name,
            source_payload=req.records,
            filename=req.filename,
            description=req.description,
            actor=req.actor,
            actor_role=req.actor_role,
            dataset_id=req.dataset_id,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.get("/datasets", response_model=List[DatasetResponse])
def list_datasets(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Lists registered maritime datasets."""
    svc = DataGovernanceService(db)
    return svc.list_datasets(limit=limit)


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
def get_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
):
    """Retrieves full details of a specific dataset."""
    svc = DataGovernanceService(db)
    ds = svc.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found.")
    return ds


@router.post("/datasets/{dataset_id}/version", response_model=dict)
def import_dataset_version(
    dataset_id: str,
    req: DatasetVersionImportRequest,
    db: Session = Depends(get_db),
):
    """Ingests an incremental immutable version (V1 -> V2) with diffing and impact analysis."""
    try:
        svc = DataGovernanceService(db)
        return svc.import_new_version(
            dataset_id=dataset_id,
            source_payload=req.records,
            change_summary=req.change_summary,
            filename=req.filename,
            actor=req.actor,
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Version import failed: {str(e)}")


@router.post("/datasets/{dataset_id}/approve", response_model=DatasetResponse)
def approve_dataset(
    dataset_id: str,
    req: DatasetApprovalRequest,
    db: Session = Depends(get_db),
):
    """Formally approves a validated dataset for consumption by decision engines."""
    try:
        svc = DataGovernanceService(db)
        return svc.approve_dataset(
            dataset_id=dataset_id,
            actor=req.actor,
            actor_role=req.actor_role,
            notes=req.notes,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Approval failed: {str(e)}")


@router.post("/datasets/{dataset_id}/reject", response_model=DatasetResponse)
def reject_dataset(
    dataset_id: str,
    req: DatasetRejectionRequest,
    db: Session = Depends(get_db),
):
    """Formally rejects a dataset with recorded reason."""
    try:
        svc = DataGovernanceService(db)
        return svc.reject_dataset(
            dataset_id=dataset_id,
            reason=req.reason,
            actor=req.actor,
            actor_role=req.actor_role,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rejection failed: {str(e)}")


@router.get("/datasets/{dataset_id}/quarantine", response_model=List[QuarantineItemResponse])
def get_dataset_quarantine(
    dataset_id: str,
    db: Session = Depends(get_db),
):
    """Returns quarantined records and defect reason codes for a dataset."""
    svc = DataGovernanceService(db)
    return svc.get_quarantine_records(dataset_id)


@router.get("/datasets/{dataset_id}/diff", response_model=Optional[DatasetDiffResponse])
def get_dataset_diff(
    dataset_id: str,
    db: Session = Depends(get_db),
):
    """Retrieves differential record comparison between current and prior version."""
    svc = DataGovernanceService(db)
    diff = svc.get_dataset_diff(dataset_id)
    if not diff:
        raise HTTPException(status_code=404, detail=f"No diff available for '{dataset_id}'.")
    return diff


@router.get("/datasets/{dataset_id}/impact", response_model=Optional[DatasetImpactResponse])
def get_dataset_impact(
    dataset_id: str,
    db: Session = Depends(get_db),
):
    """Retrieves downstream dependency and stale decision impact analysis."""
    svc = DataGovernanceService(db)
    impact = svc.get_dataset_impact(dataset_id)
    if not impact:
        raise HTTPException(status_code=404, detail=f"No impact analysis found for '{dataset_id}'.")
    return impact


@router.get("/demo/seed", response_model=DatasetResponse)
def seed_demo_datasets(
    db: Session = Depends(get_db),
):
    """Seeds canonical demonstration datasets (V1 and V2) with verified quality and diffs."""
    try:
        svc = DataGovernanceService(db)
        return svc.seed_canonical_demo_data()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Seed failed: {str(e)}")

