"""
VesselOptima — Phase 12 Maritime Data Integration & Quality Governance
Quarantine Subsystem for Isolated Defect Retention and Tracking
"""

from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.engines.data.models import FieldValidationIssue
from app.engines.data.reason_codes import QuarantineSeverity


def build_quarantine_records(
    dataset_id_int: int,
    version_number: int,
    issues: List[FieldValidationIssue],
    raw_records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Constructs database-ready quarantine dictionaries from validation issues.
    """
    quarantine_entries: List[Dict[str, Any]] = []

    for issue in issues:
        # Get raw record if index is valid
        raw = raw_records[issue.record_index] if 0 <= issue.record_index < len(raw_records) else {}
        entry = {
            "dataset_id": dataset_id_int,
            "version_number": version_number,
            "record_identifier": issue.business_key or f"REC-{issue.record_index}",
            "field_name": issue.field_name or "schema",
            "original_value": str(issue.original_value) if issue.original_value is not None else "NULL",
            "error_code": issue.error_code.value if hasattr(issue.error_code, "value") else str(issue.error_code),
            "severity": issue.severity.value if hasattr(issue.severity, "value") else str(issue.severity),
            "message": issue.message,
            "raw_record": raw,
        }
        quarantine_entries.append(entry)

    return quarantine_entries
