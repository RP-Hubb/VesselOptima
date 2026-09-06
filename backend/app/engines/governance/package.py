"""
VesselOptima — Phase 11 Decision Governance & Institutional Control
Decision Package Assembly, Validation & Lifecycle Management
"""

from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.engines.governance.hashing import (
    compute_canonical_hash,
    compute_package_hash,
)
from app.engines.governance.models import PackageValidationResult
from app.engines.governance.reason_codes import (
    GovernanceReasonCode,
    PackageStatus,
)


def validate_package_evidence(package_data: Dict[str, Any]) -> PackageValidationResult:
    """
    Validates that a decision package contains all mandatory upstream evidence
    required for institutional sign-off.
    """
    missing: List[str] = []
    messages: List[str] = []

    # 1. Phase 7 Optimization evidence check
    if not package_data.get("optimization_run_id"):
        missing.append("optimization_run_id")
        messages.append("Missing Phase 7 MILP optimization run linkage.")

    # 2. Phase 10 Decision Run evidence check
    if not package_data.get("decision_run_id"):
        missing.append("decision_run_id")
        messages.append("Missing Phase 10 decision evaluation run linkage.")

    # 3. Decision Recommendation check
    if not package_data.get("recommendation_type"):
        missing.append("recommendation_type")
        messages.append("Missing deterministic recommendation verdict.")

    # 4. Phase 9 Risk evidence check
    loss_prob = package_data.get("loss_probability")
    cvar = package_data.get("cvar_95")
    if loss_prob is None or cvar is None:
        missing.append("risk_intelligence_evidence")
        messages.append("Missing Phase 9 stochastic risk metrics (loss probability / 95% CVaR).")

    # 5. Configuration and Thresholds check
    if not package_data.get("threshold_config") and not package_data.get("configuration_id"):
        missing.append("threshold_configuration")
        messages.append("Missing versioned decision threshold configuration.")

    if missing:
        if "optimization_run_id" in missing:
            rc = GovernanceReasonCode.MISSING_OPTIMIZATION_EVIDENCE
        elif "risk_intelligence_evidence" in missing:
            rc = GovernanceReasonCode.MISSING_RISK_EVIDENCE
        else:
            rc = GovernanceReasonCode.MISSING_DECISION_EVIDENCE

        return PackageValidationResult(
            is_valid=False,
            reason_code=rc,
            missing_elements=missing,
            messages=messages,
        )

    return PackageValidationResult(
        is_valid=True,
        reason_code=GovernanceReasonCode.GOVERNANCE_CHECKS_PASSED,
        missing_elements=[],
        messages=["All required analytical evidence references and thresholds verified."],
    )


def assemble_package_data(
    optimization_run_id: str,
    decision_run_id: str,
    recommendation_type: str,
    decision_score: float,
    confidence: str,
    expected_contribution: float,
    risk_adjusted_contribution: float,
    loss_probability: float,
    cvar_95: float,
    plan_reliability: float,
    input_hash: str,
    output_hash: str,
    scenario_run_id: Optional[str] = None,
    risk_run_id: Optional[str] = None,
    configuration_id: Optional[str] = None,
    configuration_version: str = "1.0.0",
    engine_versions: Optional[Dict[str, str]] = None,
    evidence_summary: Optional[Dict[str, Any]] = None,
    actions_summary: Optional[List[Dict[str, Any]]] = None,
    threshold_config: Optional[Dict[str, Any]] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    created_by: str = "analyst_user",
    created_by_role: str = "ANALYST",
    package_id: Optional[str] = None,
    version_number: int = 1,
    parent_package_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Constructs an immutable decision package dictionary with cryptographic hashes.
    """
    pkg_id = package_id or f"PKG-{uuid4().hex[:10].upper()}"
    default_title = title or f"Decision Package: {recommendation_type} ({pkg_id})"

    pkg_dict: Dict[str, Any] = {
        "package_id": pkg_id,
        "version_number": version_number,
        "parent_package_id": parent_package_id,
        "title": default_title,
        "description": description or "Institutional governed decision package.",
        "status": PackageStatus.DRAFT.value,
        "optimization_run_id": optimization_run_id,
        "scenario_run_id": scenario_run_id,
        "risk_run_id": risk_run_id,
        "decision_run_id": decision_run_id,
        "configuration_id": configuration_id or "CONFIG-DEFAULT",
        "configuration_version": configuration_version,
        "engine_versions": engine_versions or {
            "optimization": "1.0.0",
            "scenarios": "1.0.0",
            "risk": "1.0.0",
            "decision": "1.0.0",
            "governance": "1.0.0",
        },
        "recommendation_type": recommendation_type,
        "decision_score": decision_score,
        "confidence": confidence,
        "decision_stability": 1.0,
        "expected_contribution": expected_contribution,
        "risk_adjusted_contribution": risk_adjusted_contribution,
        "loss_probability": loss_probability,
        "cvar_95": cvar_95,
        "plan_reliability": plan_reliability,
        "evidence_summary": evidence_summary or {},
        "actions_summary": actions_summary or [],
        "threshold_config": threshold_config or {},
        "input_hash": input_hash,
        "output_hash": output_hash,
        "created_by": created_by,
        "created_by_role": created_by_role,
        "is_override": False,
    }

    pkg_dict["package_hash"] = compute_package_hash(pkg_dict)
    return pkg_dict
