"""
VesselOptima — Phase 11 Decision Governance & Institutional Control
Approval Workflow & Separation of Duties State Machine
"""

from typing import Any, Dict, Optional, Tuple

from app.engines.governance.models import PackageValidationResult
from app.engines.governance.package import validate_package_evidence
from app.engines.governance.reason_codes import (
    ApprovalStatus,
    GovernanceReasonCode,
    InstitutionalRole,
    PackageStatus,
)


def can_transition(current_status: PackageStatus, target_status: PackageStatus) -> bool:
    """Validates allowed state machine transitions."""
    allowed = {
        PackageStatus.DRAFT: [PackageStatus.VALIDATED, PackageStatus.REJECTED],
        PackageStatus.VALIDATED: [PackageStatus.SUBMITTED, PackageStatus.REJECTED],
        PackageStatus.SUBMITTED: [PackageStatus.UNDER_REVIEW, PackageStatus.APPROVED, PackageStatus.REJECTED],
        PackageStatus.UNDER_REVIEW: [PackageStatus.APPROVED, PackageStatus.REJECTED],
        PackageStatus.APPROVED: [PackageStatus.ARCHIVED],
        PackageStatus.REJECTED: [PackageStatus.ARCHIVED, PackageStatus.DRAFT],
        PackageStatus.ARCHIVED: [],
    }
    return target_status in allowed.get(current_status, [])


def evaluate_approval_permission(
    package_creator: str,
    actor: str,
    actor_role: str,
    package_status: PackageStatus,
    target_action: str,  # "APPROVE", "REJECT", "SUBMIT", "REVIEW", "OVERRIDE"
    package_data: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, GovernanceReasonCode, str]:
    """
    Evaluates institutional governance rules, separation of duties, and evidence prerequisites.
    """
    # 1. Check if package is already finalized
    if package_status in (PackageStatus.APPROVED, PackageStatus.ARCHIVED) and target_action in ("APPROVE", "REJECT"):
        return (
            False,
            GovernanceReasonCode.PACKAGE_ALREADY_FINALIZED,
            f"Package is already {package_status.value} and cannot be modified in place. Create a new version.",
        )

    # 2. Separation of Duties check on APPROVE
    if target_action == "APPROVE":
        if actor == package_creator:
            return (
                False,
                GovernanceReasonCode.SELF_APPROVAL_FORBIDDEN,
                f"Separation of duties violation: Creator '{package_creator}' cannot approve their own package.",
            )

        if actor_role not in (InstitutionalRole.APPROVER.value, InstitutionalRole.ADMIN.value):
            return (
                False,
                GovernanceReasonCode.APPROVAL_REQUIRED,
                f"Role '{actor_role}' is not authorized to grant formal decision approval.",
            )

        # Evidence validation before approval
        if package_data:
            val_res: PackageValidationResult = validate_package_evidence(package_data)
            if not val_res.is_valid:
                return (
                    False,
                    val_res.reason_code,
                    f"Approval blocked: Evidence verification failed ({', '.join(val_res.missing_elements)}).",
                )

    # 3. Review Action check
    if target_action == "REVIEW":
        if actor_role not in (InstitutionalRole.REVIEWER.value, InstitutionalRole.APPROVER.value, InstitutionalRole.ADMIN.value):
            return (
                False,
                GovernanceReasonCode.REVIEW_REQUIRED,
                f"Role '{actor_role}' is not authorized to review packages.",
            )

    # 4. Rejection Action check
    if target_action == "REJECT":
        if actor_role not in (InstitutionalRole.REVIEWER.value, InstitutionalRole.APPROVER.value, InstitutionalRole.ADMIN.value):
            return (
                False,
                GovernanceReasonCode.APPROVAL_REQUIRED,
                f"Role '{actor_role}' is not authorized to reject packages.",
            )

    return True, GovernanceReasonCode.GOVERNANCE_CHECKS_PASSED, "Action authorized under institutional governance."
