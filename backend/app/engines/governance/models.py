"""
VesselOptima — Phase 11 Decision Governance & Institutional Control
Internal Governance Dataclasses and Data Models
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.engines.governance.reason_codes import (
    ApprovalStatus,
    GovernanceReasonCode,
    InstitutionalRole,
    PackageStatus,
)


@dataclass
class PackageValidationResult:
    """Outcome of validating a decision package's evidence completeness."""
    is_valid: bool
    reason_code: GovernanceReasonCode
    missing_elements: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)


@dataclass
class AuditChainVerificationResult:
    """Outcome of verifying cryptographic hash-chain continuity and tamper-freedom."""
    is_valid: bool
    status: str
    event_count: int
    verified_count: int
    broken_links: int
    first_broken_event: Optional[str] = None
    failure_reason: Optional[str] = None


@dataclass
class PackageComparisonResult:
    """Detailed differential analysis between two decision package versions."""
    base_package_id: str
    base_version: int
    target_package_id: str
    target_version: int
    decision_changed: bool
    recommendation_flip: Optional[str]
    score_delta: float
    contribution_delta: float
    cvar_delta: float
    loss_prob_delta: float
    reliability_delta: float
    changed_factors: List[str] = field(default_factory=list)
    comparison_summary: str = ""


@dataclass
class ReproductionResult:
    """Outcome of evaluating reproducibility against stored upstream references."""
    package_id: str
    status: str  # REPRODUCIBLE or REPRODUCTION_MISMATCH
    is_reproducible: bool
    original_score: float
    reproduced_score: float
    original_recommendation: str
    reproduced_recommendation: str
    mismatched_fields: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionRecordExport:
    """Exportable institutional record of an approved or governed decision."""
    package_id: str
    version_number: int
    status: str
    title: str
    recommendation_type: str
    decision_score: float
    confidence: str
    expected_contribution: float
    risk_adjusted_contribution: float
    loss_probability: float
    cvar_95: float
    plan_reliability: float
    evidence_references: Dict[str, Any]
    engine_versions: Dict[str, str]
    configuration_snapshot: Dict[str, Any]
    audit_chain_summary: Dict[str, Any]
    approval_history: List[Dict[str, Any]]
    override_history: List[Dict[str, Any]]
    input_hash: str
    output_hash: str
    package_hash: str
    exported_at: str
    memo_markdown: str
