"""
VesselOptima — Offline Package Manifest Generator & Verifier

Provides deterministic generation and verification of offline package manifests
using SHA-256 hashing and row count auditing.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.services.offline_package.exceptions import (
    OfflinePackageIntegrityError,
    OfflinePackageNotFoundError,
)


def compute_file_sha256(filepath: Path) -> str:
    """Computes SHA-256 hash for a given file deterministically."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def count_csv_rows(filepath: Path) -> int:
    """Counts data rows in a CSV file, excluding the header."""
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            next(reader)  # Skip header
        except StopIteration:
            return 0
        return sum(1 for _ in reader)


def generate_manifest(
    package_dir: Path,
    package_id: str = "demo-v1",
    version: str = "1.0.0",
    schema_version: str = "1.0.0",
    description: str = "VesselOptima canonical offline demonstration package.",
) -> Dict[str, Any]:
    """
    Generates a deterministic manifest.json for all CSV files within package_dir.
    Files are sorted alphabetically to ensure canonical output ordering.
    """
    if not package_dir.exists():
        raise OfflinePackageNotFoundError(f"Package directory not found: {package_dir}")

    csv_files: List[Path] = sorted(package_dir.rglob("*.csv"))
    if not csv_files:
        raise OfflinePackageNotFoundError(f"No CSV datasets found in: {package_dir}")

    files_manifest = []
    total_rows = 0

    for csv_file in csv_files:
        rel_path = csv_file.relative_to(package_dir).as_posix()
        file_hash = compute_file_sha256(csv_file)
        rows = count_csv_rows(csv_file)
        total_rows += rows

        dataset_name = csv_file.stem
        # Classify provenance: route freight is PROXY; employment/candidates DERIVED; others SYNTHETIC
        if "freight" in rel_path:
            provenance = "PROXY"
        elif "employment" in rel_path:
            provenance = "DERIVED"
        else:
            provenance = "SYNTHETIC"

        files_manifest.append({
            "path": rel_path,
            "dataset_name": dataset_name,
            "sha256": file_hash,
            "rows": rows,
            "schema_version": schema_version,
            "provenance_type": provenance,
        })

    manifest_data = {
        "package_id": package_id,
        "package_type": "OFFLINE_DEMO",
        "version": version,
        "schema_version": schema_version,
        "created_at": "2026-09-05T00:00:00Z",  # Fixed package release timestamp for determinism
        "provenance": "SYNTHETIC",
        "description": description,
        "coverage_start": "2024-01-01T00:00:00Z",
        "coverage_end": "2026-08-31T00:00:00Z",
        "total_files": len(files_manifest),
        "total_rows": total_rows,
        "files": files_manifest,
    }

    manifest_path = package_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    return manifest_data


def verify_manifest(package_dir: Path) -> Dict[str, Any]:
    """
    Verifies that all files declared in manifest.json exist, their SHA-256 hashes
    match precisely, and their row counts are identical.

    Raises:
        OfflinePackageNotFoundError if manifest or package does not exist.
        OfflinePackageIntegrityError if any hash or row count differs.
    """
    if not package_dir.exists():
        raise OfflinePackageNotFoundError(f"Package directory does not exist: {package_dir}")

    manifest_path = package_dir / "manifest.json"
    if not manifest_path.exists():
        raise OfflinePackageNotFoundError(f"Manifest file missing: {manifest_path}")

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        raise OfflinePackageIntegrityError(f"Failed to parse manifest JSON: {e}") from e

    files = manifest.get("files", [])
    if not files:
        raise OfflinePackageIntegrityError("Manifest contains no declared files.")

    files_verified = 0
    total_rows = 0

    for item in files:
        rel_path = item.get("path")
        expected_hash = item.get("sha256")
        expected_rows = item.get("rows")

        if not rel_path or not expected_hash:
            raise OfflinePackageIntegrityError(f"Invalid manifest entry: {item}")

        file_path = package_dir / rel_path
        if not file_path.exists():
            raise OfflinePackageIntegrityError(
                f"Declared dataset file missing from package: {rel_path}"
            )

        actual_hash = compute_file_sha256(file_path)
        if actual_hash != expected_hash:
            raise OfflinePackageIntegrityError(
                f"SHA-256 hash mismatch for {rel_path}. Expected: {expected_hash}, Actual: {actual_hash}"
            )

        actual_rows = count_csv_rows(file_path)
        if actual_rows != expected_rows:
            raise OfflinePackageIntegrityError(
                f"Row count mismatch for {rel_path}. Expected: {expected_rows}, Actual: {actual_rows}"
            )

        files_verified += 1
        total_rows += actual_rows

    manifest_bytes = manifest_path.read_bytes()
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()

    return {
        "status": "VALID",
        "package_id": manifest.get("package_id"),
        "package_type": manifest.get("package_type"),
        "version": manifest.get("version"),
        "schema_version": manifest.get("schema_version"),
        "manifest_hash": manifest_hash,
        "files_verified": files_verified,
        "total_rows": total_rows,
        "provenance": manifest.get("provenance", "SYNTHETIC"),
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
