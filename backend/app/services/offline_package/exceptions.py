"""
VesselOptima — Offline Package Exceptions
"""


class OfflinePackageError(Exception):
    """Base exception for all offline package operations."""
    pass


class OfflinePackageNotFoundError(OfflinePackageError):
    """Raised when an offline package directory or manifest cannot be found."""
    pass


class OfflinePackageIntegrityError(OfflinePackageError):
    """Raised when SHA-256 hash, row count, or file structure does not match the manifest."""
    pass


class SchemaValidationError(OfflinePackageError):
    """Raised when a CSV dataset is missing required columns or has invalid types."""
    pass


class DomainValidationError(OfflinePackageError):
    """Raised when domain constraints (e.g. positive dimensions, valid date chronology) fail."""
    pass
