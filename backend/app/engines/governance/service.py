"""
VesselOptima — Phase 11 Decision Governance & Institutional Control
Governance Orchestration Service
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.engines.decision.service import DecisionService
from app.engines.governance.approval import (
    can_transition,
    evaluate_approval_permission,
)
from app.engines.governance.audit import build_audit_event, verify_package_audit_trail
from app.engines.governance.configuration import (
    build_configuration_change,
    get_default_decision_configuration,
)
from app.engines.governance.hashing import (
    compute_canonical_hash,
    compute_package_hash,
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
    AuditEventType,
    GovernanceReasonCode,
    InstitutionalRole,
    PackageStatus,
)
from app.engines.governance.versioning import (
    compare_decision_packages,
    verify_decision_reproducibility,
)
from app.models.domain import (
    ApprovalAction,
    ConfigurationChange,
    DecisionConfiguration,
    DecisionOverride,
    DecisionPackage,
    DecisionPackageVersion,
    DecisionRun,
    GovernanceAuditEvent,
    OptimizationRun,
    RiskRun,
    RuntimeModeEnum,
)

logger = logging.getLogger(__name__)


class GovernanceService:
    """Institutional Governance, Audit & Approval Workflow Service."""

    def __init__(self, db: Optional[Session] = None) -> None:
        self.db = db
        self.decision_service = DecisionService(db) if db else DecisionService()

    def create_package_from_decision(
        self,
        decision_run_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        created_by: str = "analyst_user",
        created_by_role: str = "ANALYST",
    ) -> Dict[str, Any]:
        """
        Creates an initial DRAFT Decision Package from a stored Phase 10 DecisionRun.
        """
        # Fetch decision run
        dec_run = None
        if self.db:
            dec_run = self.db.query(DecisionRun).filter(DecisionRun.run_id == decision_run_id).first()

        opt_id = dec_run.optimization_run_id if dec_run else "OPT-DEMO-BASELINE"
        scen_id = dec_run.scenario_run_id if dec_run else None
        risk_id = dec_run.risk_run_id if dec_run else "RISK-DEMO-BASELINE"
        rec_type = dec_run.recommendation_type if dec_run else "PROCEED"
        score = dec_run.decision_score if dec_run else 82.5
        conf = dec_run.confidence if dec_run else "HIGH"
        risk_adj = dec_run.risk_adjusted_contribution if (dec_run and dec_run.risk_adjusted_contribution is not None) else 637500.0
        in_hash = dec_run.input_hash if (dec_run and dec_run.input_hash) else compute_canonical_hash({"opt": opt_id})
        out_hash = dec_run.output_hash if (dec_run and dec_run.output_hash) else compute_canonical_hash({"score": score})

        # Fetch evidence from decision evidence if available
        loss_prob = 0.025
        cvar = 85000.0
        exp_contrib = 680000.0
        plan_rel = 88.5

        if dec_run and dec_run.evidence:
            loss_prob = dec_run.evidence.loss_probability
            cvar = dec_run.evidence.cvar_95
            exp_contrib = dec_run.evidence.expected_contribution
            plan_rel = dec_run.evidence.plan_reliability

        pkg_data = assemble_package_data(
            optimization_run_id=opt_id,
            scenario_run_id=scen_id,
            risk_run_id=risk_id,
            decision_run_id=decision_run_id,
            recommendation_type=rec_type,
            decision_score=score,
            confidence=conf,
            expected_contribution=exp_contrib,
            risk_adjusted_contribution=risk_adj,
            loss_probability=loss_prob,
            cvar_95=cvar,
            plan_reliability=plan_rel,
            input_hash=in_hash,
            output_hash=out_hash,
            title=title,
            description=description,
            created_by=created_by,
            created_by_role=created_by_role,
        )

        # Build initial genesis audit event
        genesis_event = build_audit_event(
            sequence_number=1,
            event_type=AuditEventType.PACKAGE_CREATED,
            actor=created_by,
            actor_role=created_by_role,
            action="CREATE",
            description=f"Created Decision Package {pkg_data['package_id']} in DRAFT status.",
            previous_hash="GENESIS",
            metadata_payload={"decision_run_id": decision_run_id},
        )

        if self.db:
            db_pkg = DecisionPackage(
                package_id=pkg_data["package_id"],
                version_number=1,
                title=pkg_data["title"],
                description=pkg_data["description"],
                status=PackageStatus.DRAFT.value,
                optimization_run_id=opt_id,
                scenario_run_id=scen_id,
                risk_run_id=risk_id,
                decision_run_id=decision_run_id,
                configuration_id=pkg_data["configuration_id"],
                configuration_version=pkg_data["configuration_version"],
                engine_versions=pkg_data["engine_versions"],
                recommendation_type=rec_type,
                decision_score=score,
                confidence=conf,
                decision_stability=1.0,
                expected_contribution=exp_contrib,
                risk_adjusted_contribution=risk_adj,
                loss_probability=loss_prob,
                cvar_95=cvar,
                plan_reliability=plan_rel,
                evidence_summary=pkg_data["evidence_summary"],
                actions_summary=pkg_data["actions_summary"],
                threshold_config=pkg_data["threshold_config"],
                input_hash=in_hash,
                output_hash=out_hash,
                package_hash=pkg_data["package_hash"],
                created_by_role=created_by_role,
                created_by=created_by,
                runtime_mode=RuntimeModeEnum.OFFLINE_DEMO,
            )
            self.db.add(db_pkg)
            self.db.flush()

            # Version 1 record
            db_ver = DecisionPackageVersion(
                package_id=db_pkg.id,
                version_number=1,
                version_tag="V1.0",
                package_hash=pkg_data["package_hash"],
                input_hash=in_hash,
                output_hash=out_hash,
                change_summary="Initial version from decision evaluation.",
                evidence_snapshot=pkg_data,
                configuration_version="1.0.0",
                created_by=created_by,
            )
            self.db.add(db_ver)

            # Audit event record
            db_evt = GovernanceAuditEvent(
                package_id=db_pkg.id,
                audit_event_id=genesis_event["audit_event_id"],
                sequence_number=1,
                event_type=genesis_event["event_type"],
                actor=created_by,
                actor_role=created_by_role,
                action=genesis_event["action"],
                description=genesis_event["description"],
                previous_hash=genesis_event["previous_hash"],
                event_hash=genesis_event["event_hash"],
                metadata_payload=genesis_event["metadata_payload"],
            )
            self.db.add(db_evt)
            self.db.commit()

        pkg_data["audit_events"] = [genesis_event]
        return pkg_data

    def validate_package(self, package_id: str) -> PackageValidationResult:
        """Validates evidence and transitions package from DRAFT to VALIDATED."""
        pkg = self._get_db_package(package_id) if self.db else None
        pkg_dict = self._package_to_dict(pkg) if pkg else {"package_id": package_id}

        val_res = validate_package_evidence(pkg_dict)

        if val_res.is_valid and pkg and self.db:
            if pkg.status == PackageStatus.DRAFT.value:
                pkg.status = PackageStatus.VALIDATED.value
                self._append_audit_event(
                    package_id=pkg.id,
                    event_type=AuditEventType.PACKAGE_VALIDATED,
                    actor="governance_validator",
                    actor_role="SYSTEM",
                    action="VALIDATE",
                    description=f"Package {package_id} evidence validated successfully.",
                )
                self.db.commit()

        return val_res

    def submit_package(
        self,
        package_id: str,
        actor: str = "analyst_user",
        actor_role: str = "ANALYST",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submits a VALIDATED package for institutional review."""
        pkg = self._get_db_package(package_id)
        if not pkg:
            raise ValueError(f"Package '{package_id}' not found.")

        # Ensure validation
        pkg_dict = self._package_to_dict(pkg)
        val_res = validate_package_evidence(pkg_dict)
        if not val_res.is_valid:
            raise ValueError(f"Cannot submit: Evidence validation failed ({', '.join(val_res.missing_elements)}).")

        pkg.status = PackageStatus.SUBMITTED.value

        # Record approval action
        action = ApprovalAction(
            package_id=pkg.id,
            action_type="SUBMIT",
            actor=actor,
            actor_role=actor_role,
            status="SUBMITTED",
            notes=notes,
        )
        self.db.add(action)

        self._append_audit_event(
            package_id=pkg.id,
            event_type=AuditEventType.PACKAGE_SUBMITTED,
            actor=actor,
            actor_role=actor_role,
            action="SUBMIT",
            description=f"Package {package_id} submitted for review by {actor}.",
            metadata_payload={"notes": notes},
        )
        self.db.commit()
        return self._package_to_dict(pkg)

    def review_package(
        self,
        package_id: str,
        actor: str = "reviewer_user",
        actor_role: str = "REVIEWER",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Initiates formal review on a SUBMITTED package."""
        pkg = self._get_db_package(package_id)
        if not pkg:
            raise ValueError(f"Package '{package_id}' not found.")

        can_act, rc, reason_msg = evaluate_approval_permission(
            package_creator=pkg.created_by or "unknown",
            actor=actor,
            actor_role=actor_role,
            package_status=PackageStatus(pkg.status),
            target_action="REVIEW",
        )
        if not can_act:
            raise PermissionError(f"{rc.value}: {reason_msg}")

        pkg.status = PackageStatus.UNDER_REVIEW.value

        action = ApprovalAction(
            package_id=pkg.id,
            action_type="REVIEW",
            actor=actor,
            actor_role=actor_role,
            status="UNDER_REVIEW",
            notes=notes,
        )
        self.db.add(action)

        self._append_audit_event(
            package_id=pkg.id,
            event_type=AuditEventType.PACKAGE_REVIEW_STARTED,
            actor=actor,
            actor_role=actor_role,
            action="REVIEW",
            description=f"Review initiated on package {package_id} by {actor}.",
            metadata_payload={"notes": notes},
        )
        self.db.commit()
        return self._package_to_dict(pkg)

    def approve_package(
        self,
        package_id: str,
        actor: str = "approver_user",
        actor_role: str = "APPROVER",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Approves a package with strict separation of duties and audit integrity checks.
        """
        pkg = self._get_db_package(package_id)
        if not pkg:
            raise ValueError(f"Package '{package_id}' not found.")

        pkg_dict = self._package_to_dict(pkg)

        # 1. Separation of duties and role check
        can_act, rc, reason_msg = evaluate_approval_permission(
            package_creator=pkg.created_by or "unknown",
            actor=actor,
            actor_role=actor_role,
            package_status=PackageStatus(pkg.status),
            target_action="APPROVE",
            package_data=pkg_dict,
        )
        if not can_act:
            raise PermissionError(f"{rc.value}: {reason_msg}")

        # 2. Verify audit chain continuity before approving
        audit_res = self.verify_package_audit(package_id)
        if not audit_res.is_valid:
            raise ValueError(f"Approval blocked: Audit chain integrity failure ({audit_res.failure_reason}).")

        pkg.status = PackageStatus.APPROVED.value

        action = ApprovalAction(
            package_id=pkg.id,
            action_type="APPROVE",
            actor=actor,
            actor_role=actor_role,
            status="APPROVED",
            notes=notes,
        )
        self.db.add(action)

        self._append_audit_event(
            package_id=pkg.id,
            event_type=AuditEventType.PACKAGE_APPROVED,
            actor=actor,
            actor_role=actor_role,
            action="APPROVE",
            description=f"Package {package_id} officially APPROVED by {actor} ({actor_role}).",
            metadata_payload={"notes": notes},
        )
        self.db.commit()
        return self._package_to_dict(pkg)

    def reject_package(
        self,
        package_id: str,
        reason: str,
        actor: str = "approver_user",
        actor_role: str = "APPROVER",
    ) -> Dict[str, Any]:
        """Rejects a decision package with formal reason attribution."""
        pkg = self._get_db_package(package_id)
        if not pkg:
            raise ValueError(f"Package '{package_id}' not found.")

        can_act, rc, reason_msg = evaluate_approval_permission(
            package_creator=pkg.created_by or "unknown",
            actor=actor,
            actor_role=actor_role,
            package_status=PackageStatus(pkg.status),
            target_action="REJECT",
        )
        if not can_act:
            raise PermissionError(f"{rc.value}: {reason_msg}")

        pkg.status = PackageStatus.REJECTED.value

        action = ApprovalAction(
            package_id=pkg.id,
            action_type="REJECT",
            actor=actor,
            actor_role=actor_role,
            status="REJECTED",
            notes=reason,
        )
        self.db.add(action)

        self._append_audit_event(
            package_id=pkg.id,
            event_type=AuditEventType.PACKAGE_REJECTED,
            actor=actor,
            actor_role=actor_role,
            action="REJECT",
            description=f"Package {package_id} REJECTED by {actor}. Reason: {reason}",
            metadata_payload={"rejection_reason": reason},
        )
        self.db.commit()
        return self._package_to_dict(pkg)

    def record_override(
        self,
        package_id: str,
        override_recommendation: str,
        reason: str,
        actor: str = "fleet_director",
        actor_role: str = "APPROVER",
        supporting_note: Optional[str] = None,
        approval_actor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Records a human operational override while preserving original model recommendation.
        """
        if not reason or len(reason.strip()) < 5:
            raise ValueError(f"{GovernanceReasonCode.OVERRIDE_REQUIRES_REASON.value}: Detailed override reason required.")

        pkg = self._get_db_package(package_id)
        if not pkg:
            raise ValueError(f"Package '{package_id}' not found.")

        override_id = f"OVR-{uuid4().hex[:8].upper()}"
        override = DecisionOverride(
            package_id=pkg.id,
            override_id=override_id,
            original_recommendation=pkg.recommendation_type,
            override_recommendation=override_recommendation,
            reason=reason,
            actor=actor,
            actor_role=actor_role,
            supporting_note=supporting_note,
            approval_actor=approval_actor or actor,
            approval_status="APPROVED",
        )
        self.db.add(override)

        pkg.is_override = True

        self._append_audit_event(
            package_id=pkg.id,
            event_type=AuditEventType.OVERRIDE_RECORDED,
            actor=actor,
            actor_role=actor_role,
            action="OVERRIDE",
            description=(
                f"Human override applied on {package_id}: Model '{pkg.recommendation_type}' "
                f"overridden to '{override_recommendation}'. Reason: {reason}"
            ),
            metadata_payload={
                "override_id": override_id,
                "original_recommendation": pkg.recommendation_type,
                "override_recommendation": override_recommendation,
                "reason": reason,
            },
        )
        self.db.commit()
        return self._package_to_dict(pkg)

    def create_new_package_version(
        self,
        package_id: str,
        updated_evidence: Dict[str, Any],
        change_summary: str,
        actor: str = "analyst_user",
    ) -> Dict[str, Any]:
        """
        Creates an immutable incremental version (V1 -> V2) when updating an approved or finalized package.
        """
        pkg = self._get_db_package(package_id)
        if not pkg:
            raise ValueError(f"Package '{package_id}' not found.")

        new_version_num = pkg.version_number + 1
        version_tag = f"V{new_version_num}.0"

        # Apply updates to package
        for key, val in updated_evidence.items():
            if hasattr(pkg, key) and key not in ("id", "package_id", "created_at"):
                setattr(pkg, key, val)

        pkg.version_number = new_version_num
        pkg.status = PackageStatus.VALIDATED.value  # resets to validated for new review
        pkg_dict = self._package_to_dict(pkg)
        new_pkg_hash = compute_package_hash(pkg_dict)
        pkg.package_hash = new_pkg_hash

        # Store version record
        db_ver = DecisionPackageVersion(
            package_id=pkg.id,
            version_number=new_version_num,
            version_tag=version_tag,
            parent_version_tag=f"V{new_version_num-1}.0",
            package_hash=new_pkg_hash,
            input_hash=pkg.input_hash,
            output_hash=pkg.output_hash,
            change_summary=change_summary,
            changed_fields=updated_evidence,
            evidence_snapshot=pkg_dict,
            configuration_version=pkg.configuration_version,
            created_by=actor,
        )
        self.db.add(db_ver)

        self._append_audit_event(
            package_id=pkg.id,
            event_type=AuditEventType.PACKAGE_VERSION_CREATED,
            actor=actor,
            actor_role="ANALYST",
            action="CREATE_VERSION",
            description=f"Created Decision Package version {version_tag}. Summary: {change_summary}",
            metadata_payload={"version_tag": version_tag, "changes": updated_evidence},
        )
        self.db.commit()
        return self._package_to_dict(pkg)

    def verify_package_audit(self, package_id: str) -> AuditChainVerificationResult:
        """Verifies the append-only cryptographic hash chain of a package."""
        pkg = self._get_db_package(package_id)
        if not pkg:
            raise ValueError(f"Package '{package_id}' not found.")

        events = (
            self.db.query(GovernanceAuditEvent)
            .filter(GovernanceAuditEvent.package_id == pkg.id)
            .order_by(GovernanceAuditEvent.sequence_number.asc())
            .all()
        )
        return verify_package_audit_trail(events)

    def reproduce_package(self, package_id: str) -> ReproductionResult:
        """
        Reconstructs the deterministic decision logic for a stored package to verify reproducibility.
        """
        pkg = self._get_db_package(package_id)
        if not pkg:
            raise ValueError(f"Package '{package_id}' not found.")

        pkg_dict = self._package_to_dict(pkg)

        # Re-evaluate decision using stored references
        recomputed = self.decision_service.evaluate_decision(
            optimization_run_id=pkg.optimization_run_id,
            scenario_run_id=pkg.scenario_run_id,
            risk_run_id=pkg.risk_run_id,
        )

        return verify_decision_reproducibility(
            stored_package=pkg_dict,
            recomputed_result=recomputed.to_dict(),
        )

    def compare_package_versions(
        self,
        base_package_id: str,
        target_package_id: str,
    ) -> PackageComparisonResult:
        """Compares two decision packages or versions."""
        pkg_a = self._get_db_package(base_package_id)
        pkg_b = self._get_db_package(target_package_id)
        if not pkg_a or not pkg_b:
            raise ValueError("One or both packages not found for comparison.")

        return compare_decision_packages(
            base_pkg=self._package_to_dict(pkg_a),
            target_pkg=self._package_to_dict(pkg_b),
        )

    def export_decision_record(self, package_id: str) -> DecisionRecordExport:
        """Generates exportable JSON payload and formatted Markdown decision memo."""
        pkg = self._get_db_package(package_id)
        if not pkg:
            raise ValueError(f"Package '{package_id}' not found.")

        audit_res = self.verify_package_audit(package_id)
        events = (
            self.db.query(GovernanceAuditEvent)
            .filter(GovernanceAuditEvent.package_id == pkg.id)
            .order_by(GovernanceAuditEvent.sequence_number.asc())
            .all()
        )
        approvals = (
            self.db.query(ApprovalAction)
            .filter(ApprovalAction.package_id == pkg.id)
            .order_by(ApprovalAction.id.asc())
            .all()
        )
        overrides = (
            self.db.query(DecisionOverride)
            .filter(DecisionOverride.package_id == pkg.id)
            .order_by(DecisionOverride.id.asc())
            .all()
        )

        # Build Markdown Memo
        memo = (
            f"# INSTITUTIONAL MARITIME DECISION RECORD: {pkg.package_id} (Version {pkg.version_number})\n\n"
            f"**STATUS:** {pkg.status} | **CONFIDENCE:** {pkg.confidence} | **SCORE:** {pkg.decision_score}/100\n"
            f"**MODEL RECOMMENDATION:** {pkg.recommendation_type}\n"
        )
        if pkg.is_override and overrides:
            last_ovr = overrides[-1]
            memo += (
                f"**FINAL HUMAN DECISION:** {last_ovr.override_recommendation} (OVERRIDE: YES)\n"
                f"**OVERRIDE JUSTIFICATION:** {last_ovr.reason} (Attributed: {last_ovr.actor})\n"
            )

        memo += (
            f"\n## 1. Economic & Risk Summary\n"
            f"- Expected Net Contribution: ${pkg.expected_contribution:,.0f} USD\n"
            f"- Risk-Adjusted Economic Contribution: ${pkg.risk_adjusted_contribution:,.0f} USD (E[Π] - 0.50 × CVaR95)\n"
            f"- 95% Downside CVaR: ${pkg.cvar_95:,.0f} USD\n"
            f"- Loss Probability: {pkg.loss_probability*100:.1f}%\n"
            f"- Plan Reliability Score: {pkg.plan_reliability:.1f} pts\n\n"
            f"## 2. Upstream Cryptographic References\n"
            f"- Optimization Run ID: `{pkg.optimization_run_id}`\n"
            f"- Risk Run ID: `{pkg.risk_run_id or 'None'}`\n"
            f"- Decision Run ID: `{pkg.decision_run_id}`\n"
            f"- SHA-256 Package Hash: `{pkg.package_hash}`\n"
            f"- Audit Chain Integrity: {audit_res.status} ({audit_res.verified_count} events verified)\n"
        )

        return DecisionRecordExport(
            package_id=pkg.package_id,
            version_number=pkg.version_number,
            status=pkg.status,
            title=pkg.title,
            recommendation_type=pkg.recommendation_type,
            decision_score=pkg.decision_score,
            confidence=pkg.confidence,
            expected_contribution=pkg.expected_contribution,
            risk_adjusted_contribution=pkg.risk_adjusted_contribution,
            loss_probability=pkg.loss_probability,
            cvar_95=pkg.cvar_95,
            plan_reliability=pkg.plan_reliability,
            evidence_references={
                "optimization_run_id": pkg.optimization_run_id,
                "scenario_run_id": pkg.scenario_run_id,
                "risk_run_id": pkg.risk_run_id,
                "decision_run_id": pkg.decision_run_id,
            },
            engine_versions=pkg.engine_versions or {},
            configuration_snapshot={
                "configuration_id": pkg.configuration_id,
                "configuration_version": pkg.configuration_version,
            },
            audit_chain_summary={
                "status": audit_res.status,
                "is_valid": audit_res.is_valid,
                "event_count": audit_res.event_count,
            },
            approval_history=[
                {"action": a.action_type, "actor": a.actor, "role": a.actor_role, "status": a.status, "notes": a.notes}
                for a in approvals
            ],
            override_history=[
                {
                    "override_id": o.override_id,
                    "original": o.original_recommendation,
                    "override": o.override_recommendation,
                    "reason": o.reason,
                    "actor": o.actor,
                }
                for o in overrides
            ],
            input_hash=pkg.input_hash,
            output_hash=pkg.output_hash,
            package_hash=pkg.package_hash,
            exported_at=datetime.now(timezone.utc).isoformat(),
            memo_markdown=memo,
        )

    def get_or_create_demo_package(self, scenario_type: str = "BASELINE") -> Dict[str, Any]:
        """
        Creates canonical demo decision packages for testing and terminal inspection.
        """
        demo_pkg_id = f"PKG-DEMO-{scenario_type.upper()}"
        if self.db:
            existing = self.db.query(DecisionPackage).filter(DecisionPackage.package_id == demo_pkg_id).first()
            if existing:
                return self._package_to_dict(existing)

        # Get demo decision from Phase 10
        dec_res = self.decision_service.get_or_create_demo_decision(scenario_type=scenario_type)

        title_map = {
            "BASELINE": "Balanced Fleet Deployment (Approved)",
            "STRATEGY_FLIP_A": "Plan A: Max Nominal Yield vs High Tail Risk",
            "STRATEGY_FLIP_B": "Plan B: Robust Buffer Deployment",
            "STRESS_TEST": "Bunker Price Shock Stress Test Deployment",
        }

        # Create package
        pkg_data = assemble_package_data(
            package_id=demo_pkg_id,
            optimization_run_id=dec_res.optimization_run_id,
            scenario_run_id=dec_res.scenario_run_id,
            risk_run_id=dec_res.risk_run_id,
            decision_run_id=dec_res.run_id,
            recommendation_type=dec_res.recommendation_type.value,
            decision_score=dec_res.decision_score,
            confidence=dec_res.confidence.value,
            expected_contribution=dec_res.evidence.expected_contribution,
            risk_adjusted_contribution=dec_res.risk_adjusted_contribution,
            loss_probability=dec_res.evidence.loss_probability,
            cvar_95=dec_res.evidence.cvar_95,
            plan_reliability=dec_res.evidence.plan_reliability,
            input_hash=dec_res.input_hash,
            output_hash=dec_res.output_hash,
            title=title_map.get(scenario_type.upper(), "Demo Package"),
            description=dec_res.executive_summary,
            created_by="analyst_raj",
            created_by_role="ANALYST",
        )

        if self.db:
            db_pkg = DecisionPackage(
                package_id=demo_pkg_id,
                version_number=1,
                title=pkg_data["title"],
                description=pkg_data["description"],
                status=PackageStatus.APPROVED.value if scenario_type == "BASELINE" else PackageStatus.SUBMITTED.value,
                optimization_run_id=pkg_data["optimization_run_id"],
                scenario_run_id=pkg_data["scenario_run_id"],
                risk_run_id=pkg_data["risk_run_id"],
                decision_run_id=pkg_data["decision_run_id"],
                configuration_id="CONFIG-INSTITUTIONAL-V1",
                configuration_version="1.0.0",
                engine_versions=pkg_data["engine_versions"],
                recommendation_type=pkg_data["recommendation_type"],
                decision_score=pkg_data["decision_score"],
                confidence=pkg_data["confidence"],
                decision_stability=1.0,
                expected_contribution=pkg_data["expected_contribution"],
                risk_adjusted_contribution=pkg_data["risk_adjusted_contribution"],
                loss_probability=pkg_data["loss_probability"],
                cvar_95=pkg_data["cvar_95"],
                plan_reliability=pkg_data["plan_reliability"],
                evidence_summary=pkg_data["evidence_summary"],
                actions_summary=pkg_data["actions_summary"],
                threshold_config=pkg_data["threshold_config"],
                input_hash=pkg_data["input_hash"],
                output_hash=pkg_data["output_hash"],
                package_hash=pkg_data["package_hash"],
                created_by=pkg_data["created_by"],
                created_by_role=pkg_data["created_by_role"],
                runtime_mode=RuntimeModeEnum.OFFLINE_DEMO,
            )
            self.db.add(db_pkg)
            self.db.flush()

            # Version 1
            ver = DecisionPackageVersion(
                package_id=db_pkg.id,
                version_number=1,
                version_tag="V1.0",
                package_hash=pkg_data["package_hash"],
                input_hash=pkg_data["input_hash"],
                output_hash=pkg_data["output_hash"],
                change_summary="Initial demo institutional baseline package.",
                evidence_snapshot=pkg_data,
                configuration_version="1.0.0",
                created_by="analyst_raj",
            )
            self.db.add(ver)

            # Audit event 1: Create
            evt1 = build_audit_event(
                sequence_number=1,
                event_type=AuditEventType.PACKAGE_CREATED,
                actor="analyst_raj",
                actor_role="ANALYST",
                action="CREATE",
                description=f"Created Decision Package {demo_pkg_id}.",
                previous_hash="GENESIS",
            )
            self.db.add(GovernanceAuditEvent(package_id=db_pkg.id, **evt1))

            # Audit event 2: Validate
            evt2 = build_audit_event(
                sequence_number=2,
                event_type=AuditEventType.PACKAGE_VALIDATED,
                actor="governance_validator",
                actor_role="SYSTEM",
                action="VALIDATE",
                description="Evidence verified against Phase 7–10 models.",
                previous_hash=evt1["event_hash"],
            )
            self.db.add(GovernanceAuditEvent(package_id=db_pkg.id, **evt2))

            # Audit event 3: Submit
            evt3 = build_audit_event(
                sequence_number=3,
                event_type=AuditEventType.PACKAGE_SUBMITTED,
                actor="analyst_raj",
                actor_role="ANALYST",
                action="SUBMIT",
                description="Submitted for fleet management sign-off.",
                previous_hash=evt2["event_hash"],
            )
            self.db.add(GovernanceAuditEvent(package_id=db_pkg.id, **evt3))

            if scenario_type == "BASELINE":
                # Audit event 4: Approve (by different user: approver_sharma)
                evt4 = build_audit_event(
                    sequence_number=4,
                    event_type=AuditEventType.PACKAGE_APPROVED,
                    actor="approver_sharma",
                    actor_role="APPROVER",
                    action="APPROVE",
                    description="Formal chartering authorization granted.",
                    previous_hash=evt3["event_hash"],
                )
                self.db.add(GovernanceAuditEvent(package_id=db_pkg.id, **evt4))

                # Approval Action
                self.db.add(ApprovalAction(
                    package_id=db_pkg.id,
                    action_type="APPROVE",
                    actor="approver_sharma",
                    actor_role="APPROVER",
                    status="APPROVED",
                    notes="Approved for voyage execution. All risk governance thresholds met.",
                ))

            self.db.commit()
            return self._package_to_dict(db_pkg)

        return pkg_data

    def list_packages(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists historical decision packages."""
        if not self.db:
            return []
        pkgs = self.db.query(DecisionPackage).order_by(DecisionPackage.id.desc()).limit(limit).all()
        return [self._package_to_dict(p) for p in pkgs]

    def get_package(self, package_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single decision package by package_id."""
        pkg = self._get_db_package(package_id)
        return self._package_to_dict(pkg) if pkg else None

    # Internal helpers
    def _get_db_package(self, package_id: str) -> Optional[DecisionPackage]:
        if not self.db:
            return None
        return self.db.query(DecisionPackage).filter(DecisionPackage.package_id == package_id).first()

    def _append_audit_event(
        self,
        package_id: int,
        event_type: AuditEventType,
        actor: str,
        actor_role: str,
        action: str,
        description: str,
        metadata_payload: Optional[Dict[str, Any]] = None,
    ) -> GovernanceAuditEvent:
        """Appends next chained event to a package."""
        latest_evt = (
            self.db.query(GovernanceAuditEvent)
            .filter(GovernanceAuditEvent.package_id == package_id)
            .order_by(GovernanceAuditEvent.sequence_number.desc())
            .first()
        )
        seq = (latest_evt.sequence_number + 1) if latest_evt else 1
        prev_hash = latest_evt.event_hash if latest_evt else "GENESIS"

        evt_dict = build_audit_event(
            sequence_number=seq,
            event_type=event_type,
            actor=actor,
            actor_role=actor_role,
            action=action,
            description=description,
            previous_hash=prev_hash,
            metadata_payload=metadata_payload,
        )

        db_evt = GovernanceAuditEvent(package_id=package_id, **evt_dict)
        self.db.add(db_evt)
        return db_evt

    def _package_to_dict(self, pkg: DecisionPackage) -> Dict[str, Any]:
        """Serializes DecisionPackage model to clean dict."""
        return {
            "id": pkg.id,
            "package_id": pkg.package_id,
            "version_number": pkg.version_number,
            "parent_package_id": pkg.parent_package_id,
            "title": pkg.title,
            "description": pkg.description,
            "status": pkg.status,
            "optimization_run_id": pkg.optimization_run_id,
            "scenario_run_id": pkg.scenario_run_id,
            "risk_run_id": pkg.risk_run_id,
            "decision_run_id": pkg.decision_run_id,
            "configuration_id": pkg.configuration_id,
            "configuration_version": pkg.configuration_version,
            "engine_versions": pkg.engine_versions or {},
            "recommendation_type": pkg.recommendation_type,
            "decision_score": pkg.decision_score,
            "confidence": pkg.confidence,
            "decision_stability": pkg.decision_stability,
            "expected_contribution": pkg.expected_contribution,
            "risk_adjusted_contribution": pkg.risk_adjusted_contribution,
            "loss_probability": pkg.loss_probability,
            "cvar_95": pkg.cvar_95,
            "plan_reliability": pkg.plan_reliability,
            "evidence_summary": pkg.evidence_summary or {},
            "actions_summary": pkg.actions_summary or [],
            "threshold_config": pkg.threshold_config or {},
            "input_hash": pkg.input_hash,
            "output_hash": pkg.output_hash,
            "package_hash": pkg.package_hash,
            "created_by": pkg.created_by,
            "created_by_role": pkg.created_by_role,
            "is_override": pkg.is_override,
            "override_recommendation": pkg.overrides[-1].override_recommendation if (pkg.overrides and len(pkg.overrides) > 0) else None,
            "override_reason": pkg.overrides[-1].reason if (pkg.overrides and len(pkg.overrides) > 0) else None,
            "created_at": pkg.created_at.isoformat() if pkg.created_at else None,
        }
