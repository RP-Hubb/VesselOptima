"""
VesselOptima — Offline Package Test Suite

Tests manifest generation, SHA-256 verification, tampering detection,
domain & referential integrity validation, idempotent ingestion,
transactional rollback, and data status API endpoints.
"""

import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.domain import (
    CargoParcel,
    MarketObservation,
    OfflinePackage,
    OfflinePackageDataset,
    Port,
    VesselProfile,
)
from app.services.offline_package.exceptions import (
    DomainValidationError,
    OfflinePackageIntegrityError,
)
from app.services.offline_package.loader import OfflinePackageIngestionService
from app.services.offline_package.manifest import generate_manifest, verify_manifest
from app.services.offline_package.quality_report import generate_data_quality_report
from app.services.offline_package.validator import validate_package_data


@pytest.fixture()
def demo_package_dir():
    pkg_dir = Path(__file__).resolve().parent.parent.parent / "data" / "offline" / "packages" / "demo-v1"
    assert pkg_dir.exists(), f"Demo package directory missing: {pkg_dir}"
    return pkg_dir


# ── Manifest & Integrity Tests ─────────────────────────────────────────

def test_demo_package_structure(demo_package_dir):
    """Verify package directory exists and contains manifest.json and README.md."""
    assert (demo_package_dir / "manifest.json").exists()
    assert (demo_package_dir / "README.md").exists()
    assert (demo_package_dir / "vessels" / "vessels.csv").exists()
    assert (demo_package_dir / "market" / "market_indices.csv").exists()


def test_manifest_verification_pristine(demo_package_dir):
    """Manifest verification succeeds on pristine canonical package."""
    res = verify_manifest(demo_package_dir)
    assert res["status"] == "VALID"
    assert res["package_id"] == "demo-v1"
    assert res["files_verified"] == 19
    assert res["total_rows"] > 20000


def test_manifest_detects_file_tampering(demo_package_dir, tmp_path):
    """Tampering with a single byte in any dataset causes SHA-256 verification failure."""
    temp_pkg = tmp_path / "tampered_pkg"
    shutil.copytree(demo_package_dir, temp_pkg)

    # Tamper with vessels.csv
    vessels_file = temp_pkg / "vessels" / "vessels.csv"
    content = vessels_file.read_text(encoding="utf-8")
    vessels_file.write_text(content + "\n# TAMPERED LINE", encoding="utf-8")

    with pytest.raises(OfflinePackageIntegrityError) as excinfo:
        verify_manifest(temp_pkg)
    assert "mismatch" in str(excinfo.value).lower()


def test_manifest_detects_missing_file(demo_package_dir, tmp_path):
    """Deleting a declared file triggers an explicit integrity error."""
    temp_pkg = tmp_path / "missing_file_pkg"
    shutil.copytree(demo_package_dir, temp_pkg)

    # Delete ports.csv
    (temp_pkg / "ports" / "ports.csv").unlink()

    with pytest.raises(OfflinePackageIntegrityError) as excinfo:
        verify_manifest(temp_pkg)
    assert "missing" in str(excinfo.value).lower()


def test_manifest_detects_row_count_mismatch(demo_package_dir, tmp_path):
    """Row count discrepancy triggers an integrity error."""
    temp_pkg = tmp_path / "row_mismatch_pkg"
    shutil.copytree(demo_package_dir, temp_pkg)

    manifest_file = temp_pkg / "manifest.json"
    with open(manifest_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Artificially modify expected row count
    data["files"][0]["rows"] += 10
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    with pytest.raises(OfflinePackageIntegrityError) as excinfo:
        verify_manifest(temp_pkg)
    assert "row count mismatch" in str(excinfo.value).lower()


# ── Domain & Referential Integrity Tests ───────────────────────────────

def test_domain_validation_success(demo_package_dir):
    """Canonical demo package passes all referential and domain checks."""
    res = validate_package_data(demo_package_dir)
    assert res["status"] == "VALID"
    assert res["vessels"] == 20
    assert res["ports"] == 15


def test_domain_validation_detects_foreign_key_violation(demo_package_dir, tmp_path):
    """Vessel referencing non-existent vessel_class_id is rejected."""
    temp_pkg = tmp_path / "fk_viol_pkg"
    shutil.copytree(demo_package_dir, temp_pkg)

    vessels_file = temp_pkg / "vessels" / "vessels.csv"
    lines = vessels_file.read_text(encoding="utf-8").splitlines()
    # Modify second line's vessel_class_id to 9999
    parts = lines[1].split(",")
    parts[2] = "9999"  # vessel_class_id
    lines[1] = ",".join(parts)
    vessels_file.write_text("\n".join(lines), encoding="utf-8")

    with pytest.raises(DomainValidationError) as excinfo:
        validate_package_data(temp_pkg)
    assert "foreign key violation" in str(excinfo.value).lower()


def test_domain_validation_detects_invalid_chronology(demo_package_dir, tmp_path):
    """Cargo requirement with loading window after delivery deadline is rejected."""
    temp_pkg = tmp_path / "chrono_viol_pkg"
    shutil.copytree(demo_package_dir, temp_pkg)

    cargo_file = temp_pkg / "cargo" / "cargo_requirements.csv"
    lines = cargo_file.read_text(encoding="utf-8").splitlines()
    parts = lines[1].split(",")
    # Set loading_window_start to after delivery_deadline
    parts[5] = "2026-11-01 00:00:00"  # loading_window_start
    parts[7] = "2026-10-01 00:00:00"  # delivery_deadline
    lines[1] = ",".join(parts)
    cargo_file.write_text("\n".join(lines), encoding="utf-8")

    with pytest.raises(DomainValidationError) as excinfo:
        validate_package_data(temp_pkg)
    assert "chronology" in str(excinfo.value).lower()


# ── Database Ingestion & Idempotency Tests ──────────────────────────────

def test_database_ingestion_service(db, demo_package_dir):
    """Package loads cleanly into test database with full relational records."""
    service = OfflinePackageIngestionService(db)
    res = service.ingest_package(demo_package_dir, force_reload=True)

    assert res["status"] == "SUCCESS"
    assert res["counts"]["vessels"] == 20
    assert res["counts"]["ports"] == 15
    assert res["counts"]["cargo_parcels"] == 6
    assert res["counts"]["market_observations"] > 20000

    # Query DB to verify
    vessels_count = db.execute(select(VesselProfile)).scalars().all()
    assert len(vessels_count) == 20

    ports_count = db.execute(select(Port)).scalars().all()
    assert len(ports_count) == 15

    datasets_count = db.execute(select(OfflinePackageDataset)).scalars().all()
    assert len(datasets_count) == 19


def test_database_ingestion_idempotency(db, demo_package_dir):
    """Calling ingest_package twice does not create duplicate rows."""
    service = OfflinePackageIngestionService(db)
    # First load
    res1 = service.ingest_package(demo_package_dir, force_reload=True)
    assert res1["status"] == "SUCCESS"

    # Second load without force
    res2 = service.ingest_package(demo_package_dir, force_reload=False)
    assert res2["status"] == "ALREADY_LOADED"
    assert res2["records_loaded"] == 0

    # Verify no duplicate vessels
    vessels_count = db.execute(select(VesselProfile)).scalars().all()
    assert len(vessels_count) == 20


# ── Data Quality Audit Tests ───────────────────────────────────────────

def test_data_quality_report(demo_package_dir):
    """Data quality report computes 0 missing values and 0 duplicate rows."""
    report = generate_data_quality_report(demo_package_dir)
    assert report["total_datasets"] == 19
    assert report["total_rows"] > 20000
    assert report["total_missing_values"] == 0
    assert report["total_duplicate_rows"] == 0


# ── API Endpoint Tests ─────────────────────────────────────────────────

def test_api_data_status(client, db, demo_package_dir):
    """GET /v1/data/status returns active package and provenance."""
    # Ensure package is ingested
    service = OfflinePackageIngestionService(db)
    service.ingest_package(demo_package_dir, force_reload=False)

    resp = client.get("/v1/data/status")
    assert resp.status_code == 200
    data = resp.json()

    assert data["package_id"] == "demo-v1"
    assert data["integrity_status"] == "VALIDATED"
    assert data["provenance"] == "SYNTHETIC"
    assert data["total_datasets"] == 19
    assert data["total_records"] > 20000
    assert len(data["datasets"]) == 19


def test_api_offline_verify(client):
    """GET /v1/data/offline/verify passes on the canonical demo package."""
    resp = client.get("/v1/data/offline/verify")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "VALID"
    assert data["package_id"] == "demo-v1"
    assert data["files_verified"] == 19
