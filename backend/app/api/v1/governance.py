"""
VesselOptima — Phase 11 Decision Governance & Institutional Control
FastAPI Router for Governance, Audit & Approval Endpoints
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.engines.governance import (
    GovernanceService,
    get_default_decision_configuration,
)
from app.schemas.governance import (
    AuditChainVerificationResponse,
    ComparePackagesRequest,
    DecisionConfigurationResponse,
    DecisionPackageResponse,
    DecisionPackageSummary,
    DecisionRecordExportResponse,
    OverrideActionRequest,
    PackageComparisonResponse,
    PackageCreateRequest,
    PackageValidationResponse,
    PackageVersionCreateRequest,
    RejectActionRequest,
    ReproductionResponse,
    WorkflowActionRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/governance", tags=["Decision Governance"])


@router.post("/packages", response_model=DecisionPackageResponse)
def create_package(
    req: PackageCreateRequest,
    db: Session = Depends(get_db),
) -> Any:
    """Creates a new DRAFT decision package from a Phase 10 DecisionRun."""
    try:
        service = GovernanceService(db)
        pkg = service.create_package_from_decision(
            decision_run_id=req.decision_run_id,
            title=req.title,
            description=req.description,
            created_by=req.created_by,
            created_by_role=req.created_by_role,
        )
        return pkg
    except Exception as e:
        logger.error(f"Error creating package: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Package creation failed: {str(e)}")


@router.get("/packages", response_model=List[DecisionPackageSummary])
def list_packages(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> Any:
    """Lists institutional decision packages."""
    try:
        service = GovernanceService(db)
        return service.list_packages(limit=limit)
    except Exception as e:
        logger.error(f"Error listing packages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list packages: {str(e)}")


@router.get("/packages/{package_id}", response_model=DecisionPackageResponse)
def get_package(
    package_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Retrieves full details of a decision package."""
    try:
        service = GovernanceService(db)
        pkg = service.get_package(package_id)
        if not pkg:
            raise HTTPException(status_code=404, detail=f"Package '{package_id}' not found")
        return pkg
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving package: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve package: {str(e)}")


@router.post("/packages/{package_id}/validate", response_model=PackageValidationResponse)
def validate_package(
    package_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Validates evidence prerequisites for a decision package."""
    try:
        service = GovernanceService(db)
        res = service.validate_package(package_id)
        return {
            "is_valid": res.is_valid,
            "reason_code": res.reason_code.value,
            "missing_elements": res.missing_elements,
            "messages": res.messages,
        }
    except Exception as e:
        logger.error(f"Error validating package: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Package validation failed: {str(e)}")


@router.post("/packages/{package_id}/submit", response_model=DecisionPackageResponse)
def submit_package(
    package_id: str,
    req: WorkflowActionRequest,
    db: Session = Depends(get_db),
) -> Any:
    """Submits a VALIDATED package for formal review."""
    try:
        service = GovernanceService(db)
        return service.submit_package(
            package_id=package_id,
            actor=req.actor,
            actor_role=req.actor_role,
            notes=req.notes,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error submitting package: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Submission failed: {str(e)}")


@router.post("/packages/{package_id}/review", response_model=DecisionPackageResponse)
def review_package(
    package_id: str,
    req: WorkflowActionRequest,
    db: Session = Depends(get_db),
) -> Any:
    """Initiates formal review on a SUBMITTED package."""
    try:
        service = GovernanceService(db)
        return service.review_package(
            package_id=package_id,
            actor=req.actor,
            actor_role=req.actor_role,
            notes=req.notes,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error reviewing package: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Review initiation failed: {str(e)}")


@router.post("/packages/{package_id}/approve", response_model=DecisionPackageResponse)
def approve_package(
    package_id: str,
    req: WorkflowActionRequest,
    db: Session = Depends(get_db),
) -> Any:
    """Approves a decision package (enforcing separation of duties creator != approver)."""
    try:
        service = GovernanceService(db)
        return service.approve_package(
            package_id=package_id,
            actor=req.actor,
            actor_role=req.actor_role,
            notes=req.notes,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error approving package: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Approval failed: {str(e)}")


@router.post("/packages/{package_id}/reject", response_model=DecisionPackageResponse)
def reject_package(
    package_id: str,
    req: RejectActionRequest,
    db: Session = Depends(get_db),
) -> Any:
    """Rejects a decision package with mandatory reason attribution."""
    try:
        service = GovernanceService(db)
        return service.reject_package(
            package_id=package_id,
            reason=req.reason,
            actor=req.actor,
            actor_role=req.actor_role,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error rejecting package: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Rejection failed: {str(e)}")


@router.post("/packages/{package_id}/override", response_model=DecisionPackageResponse)
def record_override(
    package_id: str,
    req: OverrideActionRequest,
    db: Session = Depends(get_db),
) -> Any:
    """Records a human override departing from the analytical model recommendation."""
    try:
        service = GovernanceService(db)
        return service.record_override(
            package_id=package_id,
            override_recommendation=req.override_recommendation,
            reason=req.reason,
            actor=req.actor,
            actor_role=req.actor_role,
            supporting_note=req.supporting_note,
            approval_actor=req.approval_actor,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error recording override: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Override recording failed: {str(e)}")


@router.post("/packages/{package_id}/versions", response_model=DecisionPackageResponse)
def create_package_version(
    package_id: str,
    req: PackageVersionCreateRequest,
    db: Session = Depends(get_db),
) -> Any:
    """Creates a new immutable package version (e.g. V1 -> V2) with updated evidence."""
    try:
        service = GovernanceService(db)
        return service.create_new_package_version(
            package_id=package_id,
            updated_evidence=req.updated_evidence,
            change_summary=req.change_summary,
            actor=req.actor,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error creating package version: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Version creation failed: {str(e)}")


@router.post("/packages/{package_id}/verify", response_model=AuditChainVerificationResponse)
def verify_audit_trail(
    package_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Cryptographically verifies audit hash chain continuity and detects tampering."""
    try:
        service = GovernanceService(db)
        res = service.verify_package_audit(package_id)
        return {
            "is_valid": res.is_valid,
            "status": res.status,
            "event_count": res.event_count,
            "verified_count": res.verified_count,
            "broken_links": res.broken_links,
            "first_broken_event": res.first_broken_event,
            "failure_reason": res.failure_reason,
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error verifying audit trail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.post("/packages/{package_id}/reproduce", response_model=ReproductionResponse)
def reproduce_decision(
    package_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Verifies whether a stored package is reproducibly reconstructed from its inputs."""
    try:
        service = GovernanceService(db)
        res = service.reproduce_package(package_id)
        return {
            "package_id": res.package_id,
            "status": res.status,
            "is_reproducible": res.is_reproducible,
            "original_score": res.original_score,
            "reproduced_score": res.reproduced_score,
            "original_recommendation": res.original_recommendation,
            "reproduced_recommendation": res.reproduced_recommendation,
            "mismatched_fields": res.mismatched_fields,
            "details": res.details,
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error reproducing decision: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Reproduction failed: {str(e)}")


@router.post("/compare", response_model=PackageComparisonResponse)
def compare_packages(
    req: ComparePackagesRequest,
    db: Session = Depends(get_db),
) -> Any:
    """Compares two package versions and outputs itemized evidence deltas."""
    try:
        service = GovernanceService(db)
        res = service.compare_package_versions(
            base_package_id=req.base_package_id,
            target_package_id=req.target_package_id,
        )
        return {
            "base_package_id": res.base_package_id,
            "base_version": res.base_version,
            "target_package_id": res.target_package_id,
            "target_version": res.target_version,
            "decision_changed": res.decision_changed,
            "recommendation_flip": res.recommendation_flip,
            "score_delta": res.score_delta,
            "contribution_delta": res.contribution_delta,
            "cvar_delta": res.cvar_delta,
            "loss_prob_delta": res.loss_prob_delta,
            "reliability_delta": res.reliability_delta,
            "changed_factors": res.changed_factors,
            "comparison_summary": res.comparison_summary,
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error comparing packages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")


@router.get("/packages/{package_id}/export", response_model=DecisionRecordExportResponse)
def export_decision_record(
    package_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Exports full institutional decision record in JSON and formatted Markdown."""
    try:
        service = GovernanceService(db)
        res = service.export_decision_record(package_id)
        return {
            "package_id": res.package_id,
            "version_number": res.version_number,
            "status": res.status,
            "title": res.title,
            "recommendation_type": res.recommendation_type,
            "decision_score": res.decision_score,
            "confidence": res.confidence,
            "expected_contribution": res.expected_contribution,
            "risk_adjusted_contribution": res.risk_adjusted_contribution,
            "loss_probability": res.loss_probability,
            "cvar_95": res.cvar_95,
            "plan_reliability": res.plan_reliability,
            "evidence_references": res.evidence_references,
            "engine_versions": res.engine_versions,
            "configuration_snapshot": res.configuration_snapshot,
            "audit_chain_summary": res.audit_chain_summary,
            "approval_history": res.approval_history,
            "override_history": res.override_history,
            "input_hash": res.input_hash,
            "output_hash": res.output_hash,
            "package_hash": res.package_hash,
            "exported_at": res.exported_at,
            "memo_markdown": res.memo_markdown,
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error exporting decision record: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/configurations", response_model=DecisionConfigurationResponse)
def get_active_configuration() -> Any:
    """Returns the currently active institutional decision policy configuration."""
    return get_default_decision_configuration()


@router.get("/demo/{scenario_type}", response_model=DecisionPackageResponse)
def get_demo_package(
    scenario_type: str = "BASELINE",
    db: Session = Depends(get_db),
) -> Any:
    """Retrieves or creates canonical demo decision package."""
    try:
        service = GovernanceService(db)
        return service.get_or_create_demo_package(scenario_type=scenario_type)
    except Exception as e:
        logger.error(f"Error retrieving demo package: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Demo package retrieval failed: {str(e)}")
