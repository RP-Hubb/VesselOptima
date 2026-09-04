"""
VesselOptima — API Endpoints: Data & Offline Packages
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

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
