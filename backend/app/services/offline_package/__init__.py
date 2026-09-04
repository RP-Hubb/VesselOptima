"""
VesselOptima — Offline Package Services Package
"""

from app.services.offline_package.exceptions import (
    DomainValidationError,
    OfflinePackageError,
    OfflinePackageIntegrityError,
    OfflinePackageNotFoundError,
    SchemaValidationError,
)
from app.services.offline_package.loader import OfflinePackageIngestionService
from app.services.offline_package.manifest import (
    compute_file_sha256,
    count_csv_rows,
    generate_manifest,
    verify_manifest,
)
from app.services.offline_package.quality_report import (
    format_quality_report_markdown,
    generate_data_quality_report,
)
from app.services.offline_package.validator import validate_package_data

__all__ = [
    "OfflinePackageError",
    "OfflinePackageNotFoundError",
    "OfflinePackageIntegrityError",
    "SchemaValidationError",
    "DomainValidationError",
    "OfflinePackageIngestionService",
    "compute_file_sha256",
    "count_csv_rows",
    "generate_manifest",
    "verify_manifest",
    "validate_package_data",
    "generate_data_quality_report",
    "format_quality_report_markdown",
]
