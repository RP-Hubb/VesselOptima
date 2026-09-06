"""
VesselOptima — Phase 11 Decision Governance & Institutional Control
Public Module Interface
"""

from app.engines.governance.approval import (
    can_transition,
    evaluate_approval_permission,
)
from app.engines.governance.audit import (
    build_audit_event,
    verify_package_audit_trail,
)
from app.engines.governance.configuration import (
    build_configuration_change,
    get_default_decision_configuration,
)
from app.engines.governance.hashing import (
    compute_canonical_hash,
    compute_event_hash,
    compute_package_hash,
    verify_audit_chain,
)
from app.engines.governance.models import (
    AuditChainVerificationResult,
    DecisionRecordExport,
    PackageComparisonResult,
    PackageValidationResult,
    ReproductionResult,
)
from app.engines.governance.package import (
    assemble_package_data,
    validate_package_evidence,
)
from app.engines.governance.reason_codes import (
    ApprovalStatus,
    AuditEventType,
    GovernanceReasonCode,
    InstitutionalRole,
    PackageStatus,
)
from app.engines.governance.service import GovernanceService
from app.engines.governance.versioning import (
    compare_decision_packages,
    verify_decision_reproducibility,
)

__all__ = [
    "GovernanceService",
    "PackageStatus",
    "InstitutionalRole",
    "AuditEventType",
    "ApprovalStatus",
    "GovernanceReasonCode",
    "PackageValidationResult",
    "AuditChainVerificationResult",
    "PackageComparisonResult",
    "ReproductionResult",
    "DecisionRecordExport",
    "compute_canonical_hash",
    "compute_event_hash",
    "compute_package_hash",
    "verify_audit_chain",
    "build_audit_event",
    "verify_package_audit_trail",
    "assemble_package_data",
    "validate_package_evidence",
    "evaluate_approval_permission",
    "can_transition",
    "compare_decision_packages",
    "verify_decision_reproducibility",
    "get_default_decision_configuration",
    "build_configuration_change",
]
