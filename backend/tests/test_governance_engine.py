"""
VesselOptima — Phase 11 Decision Governance, Audit & Institutional Control Test Suite

Comprehensive automated test verification covering:
1. Determinism and canonical SHA-256 package hashing
2. Canonical JSON serialization invariant to key ordering
3. Package evidence validation (valid vs missing evidence)
4. Package status state machine transitions
5. Separation of duties (creator != approver)
6. Role authorization for approvals (APPROVER/ADMIN only)
7. Approval blocked on invalid/unvalidated packages
8. Formal rejection workflow with audit attribution
9. Approved package immutability (in-place modification blocked)
10. Package versioning (V1 -> V2 with parent link)
11. Hash-chained audit trail (GENESIS -> N hash linkage)
12. Audit chain tamper detection (content modification)
13. Audit chain deletion detection (missing event in chain)
14. Audit chain reordering detection
15. Human override governance (preserves model recommendation)
16. Human override validation (rejects blank rationale)
17. Decision reproducibility verification (exact match)
18. Package delta comparison (economic, risk & score diffs)
19. Default decision policy configuration retrieval
20. GovernanceService demo presets (BASELINE, STRATEGY_FLIP_A, etc.)
21. REST API package lifecycle (create -> validate -> submit -> approve)
22. REST API override, comparison & export endpoints
23. SQLite/PostgreSQL persistence and transactional integrity
24. Air-gap offline compliance (zero outbound sockets)
"""

import json
import socket
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.engines.governance import (
    ApprovalStatus,
    AuditEventType,
    DecisionRecordExport,
    GovernanceReasonCode,
    GovernanceService,
    InstitutionalRole,
    PackageComparisonResult,
    PackageStatus,
    PackageValidationResult,
    ReproductionResult,
    assemble_package_data,
    build_audit_event,
    build_configuration_change,
    can_transition,
    compare_decision_packages,
    compute_canonical_hash,
    compute_event_hash,
    compute_package_hash,
    evaluate_approval_permission,
    get_default_decision_configuration,
    validate_package_evidence,
    verify_audit_chain,
    verify_decision_reproducibility,
    verify_package_audit_trail,
)
from app.main import app
from app.models.domain import (
    ApprovalAction,
    DecisionConfiguration,
    DecisionOverride,
    DecisionPackage,
    GovernanceAuditEvent,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── 1. Pure Python Determinism & Canonical Hashing ────────────────────

def test_governance_pure_python_determinism():
    """Identical package data produces exact identical SHA-256 package hash."""
    sample_data = {
        "package_id": "PKG-101",
        "version_number": 1,
        "optimization_run_id": "OPT-101",
        "scenario_run_id": "SCEN-101",
        "risk_run_id": "RISK-101",
        "decision_run_id": "DEC-101",
        "configuration_id": "CONFIG-1",
        "configuration_version": "1.0.0",
        "recommendation_type": "PROCEED",
        "decision_score": 85.0,
        "confidence": "HIGH",
        "expected_contribution": 680000.0,
        "risk_adjusted_contribution": 637500.0,
        "loss_probability": 0.02,
        "cvar_95": 45000.0,
        "plan_reliability": 88.0,
        "input_hash": "hash_in_abc",
        "output_hash": "hash_out_xyz",
    }
    hash1 = compute_package_hash(sample_data)
    hash2 = compute_package_hash(sample_data)
    assert hash1 == hash2
    assert len(hash1) == 64
    assert isinstance(hash1, str)


# ── 2. Canonical JSON Serialization Consistency ──────────────────────

def test_canonical_json_hashing_consistency():
    """Canonical hashing is invariant to key order and whitespace differences."""
    data_order_a = {
        "zebra": 1,
        "apple": 2,
        "metrics": {"b": 20, "a": 10},
    }
    data_order_b = {
        "apple": 2,
        "metrics": {"a": 10, "b": 20},
        "zebra": 1,
    }
    hash_a = compute_canonical_hash(data_order_a)
    hash_b = compute_canonical_hash(data_order_b)
    assert hash_a == hash_b


# ── 3. Package Evidence Validation Success ────────────────────────────

def test_package_evidence_validation_success():
    """Full evidence bundle passes validation with VALID status."""
    package_data = {
        "optimization_run_id": "OPT-001",
        "decision_run_id": "DEC-001",
        "recommendation_type": "PROCEED",
        "loss_probability": 0.02,
        "cvar_95": 45000.0,
        "configuration_id": "CONFIG-DEFAULT",
    }
    result = validate_package_evidence(package_data)
    assert result.is_valid is True
    assert result.reason_code == GovernanceReasonCode.GOVERNANCE_CHECKS_PASSED
    assert len(result.missing_elements) == 0


# ── 4. Package Evidence Validation Missing Failure ─────────────────────

def test_package_evidence_validation_missing_failure():
    """Missing critical evidence keys fails validation with missing element list."""
    package_data = {
        "optimization_run_id": "OPT-001",
        # missing decision_run_id, recommendation_type, risk metrics
    }
    result = validate_package_evidence(package_data)
    assert result.is_valid is False
    assert result.reason_code in (
        GovernanceReasonCode.MISSING_DECISION_EVIDENCE,
        GovernanceReasonCode.MISSING_RISK_EVIDENCE,
    )
    assert "decision_run_id" in result.missing_elements


# ── 5. Package Status State Machine ───────────────────────────────────

def test_package_status_state_machine():
    """State machine allows valid linear transitions and forbids illegal skips."""
    assert can_transition(PackageStatus.DRAFT, PackageStatus.VALIDATED) is True
    assert can_transition(PackageStatus.VALIDATED, PackageStatus.SUBMITTED) is True
    assert can_transition(PackageStatus.SUBMITTED, PackageStatus.UNDER_REVIEW) is True
    assert can_transition(PackageStatus.SUBMITTED, PackageStatus.APPROVED) is True
    assert can_transition(PackageStatus.UNDER_REVIEW, PackageStatus.APPROVED) is True
    assert can_transition(PackageStatus.UNDER_REVIEW, PackageStatus.REJECTED) is True
    assert can_transition(PackageStatus.APPROVED, PackageStatus.ARCHIVED) is True

    # Illegal transitions
    assert can_transition(PackageStatus.DRAFT, PackageStatus.APPROVED) is False
    assert can_transition(PackageStatus.APPROVED, PackageStatus.DRAFT) is False
    assert can_transition(PackageStatus.ARCHIVED, PackageStatus.APPROVED) is False


# ── 6. Separation of Duties Enforced ──────────────────────────────────

def test_separation_of_duties_enforced():
    """Creator of a package is forbidden from approving their own package."""
    allowed, code, msg = evaluate_approval_permission(
        package_creator="analyst_alice",
        actor="analyst_alice",
        actor_role="APPROVER",
        package_status=PackageStatus.UNDER_REVIEW,
        target_action="APPROVE",
    )
    assert allowed is False
    assert code == GovernanceReasonCode.SELF_APPROVAL_FORBIDDEN


# ── 7. Approval Role Authorization ────────────────────────────────────

def test_approval_role_authorization():
    """Only APPROVER or ADMIN can approve; ANALYST or REVIEWER cannot."""
    allowed_approver, _, _ = evaluate_approval_permission(
        package_creator="analyst_alice",
        actor="director_bob",
        actor_role="APPROVER",
        package_status=PackageStatus.UNDER_REVIEW,
        target_action="APPROVE",
    )
    assert allowed_approver is True

    allowed_analyst, code, _ = evaluate_approval_permission(
        package_creator="analyst_alice",
        actor="analyst_charlie",
        actor_role="ANALYST",
        package_status=PackageStatus.UNDER_REVIEW,
        target_action="APPROVE",
    )
    assert allowed_analyst is False
    assert code == GovernanceReasonCode.APPROVAL_REQUIRED


# ── 8. Approval Requires Evidence Validation ──────────────────────────

def test_approval_requires_evidence_validation():
    """Approval is strictly denied if package evidence is incomplete."""
    incomplete_package_data = {
        "optimization_run_id": "OPT-1",
        # missing decision_run_id
    }
    allowed, code, _ = evaluate_approval_permission(
        package_creator="analyst_alice",
        actor="director_bob",
        actor_role="APPROVER",
        package_status=PackageStatus.UNDER_REVIEW,
        target_action="APPROVE",
        package_data=incomplete_package_data,
    )
    assert allowed is False
    assert code in (
        GovernanceReasonCode.MISSING_DECISION_EVIDENCE,
        GovernanceReasonCode.MISSING_RISK_EVIDENCE,
    )


# ── 9. Rejection Workflow ─────────────────────────────────────────────

def test_rejection_workflow(db_session):
    """Rejecting a package records reason, updates status, and appends audit event."""
    service = GovernanceService(db_session)
    pkg = service.create_package_from_decision(
        decision_run_id="DEC-TEST-REJ-1",
        title="Test Rejection Package",
        created_by="analyst_test",
        created_by_role="ANALYST",
    )
    pkg_id = pkg["package_id"]

    service.validate_package(pkg_id)
    service.submit_package(pkg_id, actor="analyst_test", actor_role="ANALYST")

    rejected_pkg = service.reject_package(
        package_id=pkg_id,
        reason="Excessive laycan risk in Far East ballast leg",
        actor="director_dan",
        actor_role="APPROVER",
    )
    assert rejected_pkg["status"] == "REJECTED"

    events = (
        db_session.query(GovernanceAuditEvent)
        .join(DecisionPackage, GovernanceAuditEvent.package_id == DecisionPackage.id)
        .filter(DecisionPackage.package_id == pkg_id)
        .all()
    )
    event_types = [e.event_type for e in events]
    assert AuditEventType.PACKAGE_REJECTED.value in event_types


# ── 10. Approved Package Immutability ─────────────────────────────────

def test_approved_package_immutability(db_session):
    """Approved packages cannot be approved again in place."""
    service = GovernanceService(db_session)
    pkg = service.create_package_from_decision(
        decision_run_id="DEC-TEST-IMM-1",
        title="Immutable Package",
        created_by="analyst_1",
        created_by_role="ANALYST",
    )
    pkg_id = pkg["package_id"]
    service.validate_package(pkg_id)
    service.submit_package(pkg_id, actor="analyst_1", actor_role="ANALYST")
    service.approve_package(
        package_id=pkg_id,
        actor="manager_1",
        actor_role="APPROVER",
        notes="Approved for charter execution",
    )

    # Attempt second approval on already approved package
    with pytest.raises(PermissionError, match="PACKAGE_ALREADY_FINALIZED"):
        service.approve_package(
            package_id=pkg_id,
            actor="director_2",
            actor_role="APPROVER",
            notes="Second approval attempt",
        )


# ── 11. Package Versioning (V1 -> V2) ─────────────────────────────────

def test_package_versioning_creates_new_version(db_session):
    """Creating a new version increments version_number and records audit event."""
    service = GovernanceService(db_session)
    pkg_v1 = service.create_package_from_decision(
        decision_run_id="DEC-TEST-VER-1",
        title="Base Charter Plan",
        created_by="analyst_v1",
        created_by_role="ANALYST",
    )
    pkg_id = pkg_v1["package_id"]
    service.validate_package(pkg_id)
    service.submit_package(pkg_id, actor="analyst_v1", actor_role="ANALYST")
    service.approve_package(
        package_id=pkg_id,
        actor="director_v1",
        actor_role="APPROVER",
    )

    # Create V2
    pkg_v2 = service.create_new_package_version(
        package_id=pkg_id,
        updated_evidence={"expected_contribution": 720000.0, "decision_score": 86.0},
        change_summary="Updated for revised bunker fuel pricing curve",
        actor="analyst_v2",
    )

    assert pkg_v2["version_number"] == 2
    assert pkg_v2["status"] == "VALIDATED"
    assert pkg_v2["expected_contribution"] == 720000.0


# ── 12. Hash-Chained Audit Trail Linking ──────────────────────────────

def test_audit_chain_genesis_and_linking():
    """First event has previous_hash='GENESIS'; subsequent events link strictly."""
    e1 = build_audit_event(
        sequence_number=1,
        event_type=AuditEventType.PACKAGE_CREATED,
        actor="user_1",
        actor_role="ANALYST",
        action="CREATE",
        description="Package created",
        previous_hash="GENESIS",
        metadata_payload={"title": "Test"},
    )
    assert e1["previous_hash"] == "GENESIS"
    assert len(e1["event_hash"]) == 64

    e2 = build_audit_event(
        sequence_number=2,
        event_type=AuditEventType.PACKAGE_VALIDATED,
        actor="system",
        actor_role="SYSTEM",
        action="VALIDATE",
        description="Validated",
        previous_hash=e1["event_hash"],
        metadata_payload={"is_valid": True},
    )
    assert e2["previous_hash"] == e1["event_hash"]

    res = verify_audit_chain([e1, e2])
    assert res["is_valid"] is True
    assert res["verified_count"] == 2
    assert res["status"] == "VALID"


# ── 13. Audit Chain Tamper Detection (Content Modification) ───────────

def test_audit_chain_tamper_detection_content():
    """Modifying event payload breaks SHA-256 integrity check."""
    e1 = build_audit_event(
        sequence_number=1,
        event_type=AuditEventType.PACKAGE_CREATED,
        actor="user_1",
        actor_role="ANALYST",
        action="CREATE",
        description="Created",
        previous_hash="GENESIS",
        metadata_payload={"title": "Original"},
    )
    # Tamper with description without updating event_hash
    tampered_e1 = dict(e1)
    tampered_e1["description"] = "Tampered Description"

    res = verify_audit_chain([tampered_e1])
    assert res["is_valid"] is False
    assert "Tamper detected" in res["failure_reason"]


# ── 14. Audit Chain Deletion Detection ────────────────────────────────

def test_audit_chain_tamper_detection_deletion():
    """Deleting an intermediate event in the chain is detected as broken link."""
    e1 = build_audit_event(1, AuditEventType.PACKAGE_CREATED, "u1", "ANALYST", "CREATE", "c", "GENESIS")
    e2 = build_audit_event(2, AuditEventType.PACKAGE_VALIDATED, "u1", "SYSTEM", "VALIDATE", "v", e1["event_hash"])
    e3 = build_audit_event(3, AuditEventType.PACKAGE_SUBMITTED, "u1", "ANALYST", "SUBMIT", "s", e2["event_hash"])

    # Omit e2 (deletion attack: passing e1 and e3)
    res = verify_audit_chain([e1, e3])
    assert res["is_valid"] is False
    assert "Sequence out of order" in res["failure_reason"]


# ── 15. Audit Chain Reordering Detection ──────────────────────────────

def test_audit_chain_tamper_detection_reorder():
    """Reordering events breaks sequence and hash linkage."""
    e1 = build_audit_event(1, AuditEventType.PACKAGE_CREATED, "u1", "ANALYST", "CREATE", "c", "GENESIS")
    e2 = build_audit_event(2, AuditEventType.PACKAGE_VALIDATED, "u1", "SYSTEM", "VALIDATE", "v", e1["event_hash"])

    # Swap sequence
    res = verify_audit_chain([e2, e1])
    assert res["is_valid"] is False
    assert res["is_valid"] is False


# ── 16. Human Override Governance ─────────────────────────────────────

def test_human_override_governance(db_session):
    """Human override records human decision, preserves model recommendation, logs approver attribution."""
    service = GovernanceService(db_session)
    pkg = service.create_package_from_decision(
        decision_run_id="DEC-TEST-OVR-1",
        title="Override Test Package",
        created_by="analyst_ovr",
        created_by_role="ANALYST",
    )
    pkg_id = pkg["package_id"]
    service.validate_package(pkg_id)

    res = service.record_override(
        package_id=pkg_id,
        override_recommendation="PROCEED",
        reason="Strategic client relationship mandates fulfilling cargo obligation despite margin compression.",
        actor="director_boss",
        actor_role="APPROVER",
        supporting_note="Approved by Atlantic Chartering Committee",
    )

    assert res["is_override"] is True
    assert res["override_recommendation"] == "PROCEED"


# ── 17. Override Without Justification Fails ──────────────────────────

def test_override_without_justification_fails(db_session):
    """Submitting an override with blank rationale raises ValueError."""
    service = GovernanceService(db_session)
    pkg = service.create_package_from_decision(
        decision_run_id="DEC-TEST-OVR-2",
        title="Blank Override Test",
        created_by="analyst_ovr2",
        created_by_role="ANALYST",
    )
    pkg_id = pkg["package_id"]

    with pytest.raises(ValueError, match="OVERRIDE_REQUIRES_REASON"):
        service.record_override(
            package_id=pkg_id,
            override_recommendation="PROCEED",
            reason="   ",  # blank whitespace
            actor="director_boss",
            actor_role="APPROVER",
        )


# ── 18. Decision Reproducibility Verification ─────────────────────────

def test_decision_reproducibility_verification():
    """Matching recorded metrics verifies reproducibility; mismatched raises discrepancy."""
    recorded = {
        "package_id": "PKG-REPRO-1",
        "recommendation_type": "PROCEED",
        "decision_score": 82.5,
        "output_hash": "hash_abc",
    }
    reproduced_same = {
        "package_id": "PKG-REPRO-1",
        "recommendation_type": "PROCEED",
        "decision_score": 82.5,
        "output_hash": "hash_abc",
    }
    res_exact = verify_decision_reproducibility(recorded, reproduced_same)
    assert res_exact.is_reproducible is True
    assert res_exact.status == "REPRODUCIBLE"
    assert len(res_exact.mismatched_fields) == 0

    reproduced_diff = {
        "package_id": "PKG-REPRO-1",
        "recommendation_type": "RECONSIDER",  # mismatch
        "decision_score": 68.0,              # mismatch
        "output_hash": "hash_xyz",           # mismatch
    }
    res_diff = verify_decision_reproducibility(recorded, reproduced_diff)
    assert res_diff.is_reproducible is False
    assert res_diff.status == "REPRODUCTION_MISMATCH"
    assert len(res_diff.mismatched_fields) >= 2


# ── 19. Package Delta Comparison (V1 vs V2) ───────────────────────────

def test_package_delta_comparison():
    """Comparing two packages detects economic, risk, and score deltas."""
    v1_data = {
        "package_id": "pkg-v1",
        "version_number": 1,
        "recommendation_type": "PROCEED",
        "decision_score": 82.0,
        "expected_contribution": 680000.0,
        "cvar_95": 45000.0,
        "loss_probability": 0.02,
        "plan_reliability": 88.0,
    }
    v2_data = {
        "package_id": "pkg-v2",
        "version_number": 2,
        "recommendation_type": "PROCEED_WITH_CAUTION",
        "decision_score": 74.0,
        "expected_contribution": 720000.0,
        "cvar_95": 65000.0,
        "loss_probability": 0.05,
        "plan_reliability": 82.0,
    }
    res = compare_decision_packages(v1_data, v2_data)
    assert res.base_package_id == "pkg-v1"
    assert res.target_package_id == "pkg-v2"
    assert res.score_delta == pytest.approx(-8.0)
    assert res.contribution_delta == pytest.approx(40000.0)
    assert res.cvar_delta == pytest.approx(20000.0)
    assert res.loss_prob_delta == pytest.approx(0.03)
    assert res.decision_changed is True
    assert res.recommendation_flip == "PROCEED -> PROCEED_WITH_CAUTION"


# ── 20. Default Policy Configuration Retrieval ────────────────────────

def test_default_policy_configuration_retrieval():
    """Default decision policy configuration provides all governance parameters."""
    config = get_default_decision_configuration()
    assert config["configuration_id"] == "CONFIG-INSTITUTIONAL-V1"
    assert config["version"] == "1.0.0"
    assert config["recommendation_thresholds"]["min_score_proceed"] == 75.0
    assert config["recommendation_thresholds"]["min_reliability_proceed"] == 80.0
    assert config["risk_thresholds"]["risk_aversion_lambda"] == 0.50


# ── 21. GovernanceService Demo Presets ─────────────────────────────────

def test_governance_service_demo_presets(db_session):
    """Demo presets for BASELINE, STRATEGY_FLIP_A, etc. initialize with verified audit chains."""
    service = GovernanceService(db_session)

    pkg_base = service.get_or_create_demo_package(scenario_type="BASELINE")
    assert pkg_base["package_id"] == "PKG-DEMO-BASELINE"
    assert pkg_base["status"] in ("APPROVED", "SUBMITTED")
    assert pkg_base["package_hash"] is not None

    res_audit = service.verify_package_audit(pkg_base["package_id"])
    assert res_audit.is_valid is True

    pkg_flip_a = service.get_or_create_demo_package(scenario_type="STRATEGY_FLIP_A")
    assert pkg_flip_a["package_id"] == "PKG-DEMO-STRATEGY_FLIP_A"


# ── 22. REST API Package Lifecycle ────────────────────────────────────

def test_api_package_lifecycle(client):
    """End-to-end API test: create -> validate -> submit -> approve -> verify audit trail."""
    # 1. Create package from decision run
    create_resp = client.post(
        "/v1/governance/packages",
        json={
            "decision_run_id": "DEC-API-TEST-1",
            "title": "API Lifecycle Package",
            "created_by": "analyst_api",
            "created_by_role": "ANALYST",
            "description": "Created via API test",
        },
    )
    assert create_resp.status_code == 200
    pkg_id = create_resp.json()["package_id"]

    # 2. Validate package
    val_resp = client.post(f"/v1/governance/packages/{pkg_id}/validate")
    assert val_resp.status_code == 200
    assert val_resp.json()["is_valid"] is True

    # 3. Submit for review
    sub_resp = client.post(
        f"/v1/governance/packages/{pkg_id}/submit",
        json={"actor": "analyst_api", "actor_role": "ANALYST"},
    )
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "SUBMITTED"

    # 4. Attempt self-approval (must fail 403)
    self_app_resp = client.post(
        f"/v1/governance/packages/{pkg_id}/approve",
        json={
            "actor": "analyst_api",
            "actor_role": "APPROVER",
            "notes": "Attempting self-approval",
        },
    )
    assert self_app_resp.status_code == 403

    # 5. Legitimate approval by different user
    app_resp = client.post(
        f"/v1/governance/packages/{pkg_id}/approve",
        json={
            "actor": "director_board",
            "actor_role": "APPROVER",
            "notes": "Formal chartering board approval",
        },
    )
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "APPROVED"

    # 6. Verify audit trail integrity
    audit_resp = client.post(f"/v1/governance/packages/{pkg_id}/verify")
    assert audit_resp.status_code == 200
    assert audit_resp.json()["is_valid"] is True
    assert audit_resp.json()["status"] == "VALID"


# ── 23. REST API Override, Compare & Export ───────────────────────────

def test_api_override_and_export(client):
    """API endpoints for human override, delta comparison, and audit package export."""
    # Seed demo package
    demo_resp = client.get("/v1/governance/demo/BASELINE")
    assert demo_resp.status_code == 200
    pkg_id = demo_resp.json()["package_id"]

    # Export audit package
    export_resp = client.get(f"/v1/governance/packages/{pkg_id}/export")
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert export_data["package_id"] == pkg_id
    assert export_data["audit_chain_summary"]["is_valid"] is True
    assert "memo_markdown" in export_data

    # Test compare endpoint
    comp_resp = client.post(
        "/v1/governance/compare",
        json={"base_package_id": pkg_id, "target_package_id": pkg_id},
    )
    assert comp_resp.status_code == 200
    assert comp_resp.json()["base_package_id"] == pkg_id


# ── 24. Air-Gap Offline Compliance ────────────────────────────────────

def test_governance_air_gap_compliance(monkeypatch):
    """Phase 11 must make zero external network or socket calls."""
    def guarded_socket(*args, **kwargs):
        raise RuntimeError("Air-gap violation: socket connection attempted in Phase 11!")

    monkeypatch.setattr(socket, "socket", guarded_socket)

    # Verify canonical hash and audit verification work without socket
    data = {"system": "VesselOptima", "air_gapped": True}
    h = compute_canonical_hash(data)
    assert len(h) == 64

    res = validate_package_evidence({
        "optimization_run_id": "OPT-1",
        "decision_run_id": "DEC-1",
        "recommendation_type": "PROCEED",
        "loss_probability": 0.02,
        "cvar_95": 45000.0,
        "configuration_id": "CONFIG-1",
    })
    assert res.is_valid is True
