"""
VesselOptima — Phase 11 Decision Governance & Institutional Control
Pydantic Schemas for Governance API
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PackageCreateRequest(BaseModel):
    decision_run_id: str = Field(..., description="ID of Phase 10 DecisionRun to package")
    title: Optional[str] = Field(None, description="Title for decision package")
    description: Optional[str] = Field(None, description="Detailed operational context")
    created_by: str = Field("analyst_user", description="Identifier of creator")
    created_by_role: str = Field("ANALYST", description="Role of creator")


class WorkflowActionRequest(BaseModel):
    actor: str = Field(..., description="Actor performing workflow action")
    actor_role: str = Field(..., description="Institutional role of actor")
    notes: Optional[str] = Field(None, description="Optional review or approval notes")


class RejectActionRequest(BaseModel):
    actor: str = Field(..., description="Actor performing rejection")
    actor_role: str = Field(..., description="Institutional role of actor")
    reason: str = Field(..., min_length=5, description="Mandatory reason for rejection")


class OverrideActionRequest(BaseModel):
    override_recommendation: str = Field(..., description="Final human decision verdict")
    reason: str = Field(..., min_length=5, description="Justification for departing from model recommendation")
    actor: str = Field(..., description="Actor requesting override")
    actor_role: str = Field("APPROVER", description="Role of overriding actor")
    supporting_note: Optional[str] = Field(None, description="Technical or operational supporting notes")
    approval_actor: Optional[str] = Field(None, description="Sign-off authority")


class PackageVersionCreateRequest(BaseModel):
    updated_evidence: Dict[str, Any] = Field(..., description="Modified evidence fields")
    change_summary: str = Field(..., min_length=5, description="Summary of version changes")
    actor: str = Field("analyst_user", description="Author of version revision")


class ComparePackagesRequest(BaseModel):
    base_package_id: str = Field(..., description="ID of base package (e.g. V1)")
    target_package_id: str = Field(..., description="ID of target package (e.g. V2)")


class DecisionPackageResponse(BaseModel):
    id: Optional[int] = None
    package_id: str
    version_number: int
    parent_package_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    status: str
    optimization_run_id: str
    scenario_run_id: Optional[str] = None
    risk_run_id: Optional[str] = None
    decision_run_id: str
    configuration_id: Optional[str] = None
    configuration_version: str
    engine_versions: Dict[str, str] = Field(default_factory=dict)
    recommendation_type: str
    decision_score: float
    confidence: str
    decision_stability: float
    expected_contribution: float
    risk_adjusted_contribution: float
    loss_probability: float
    cvar_95: float
    plan_reliability: float
    evidence_summary: Dict[str, Any] = Field(default_factory=dict)
    actions_summary: List[Dict[str, Any]] = Field(default_factory=list)
    threshold_config: Dict[str, Any] = Field(default_factory=dict)
    input_hash: str
    output_hash: str
    package_hash: str
    created_by: Optional[str] = None
    created_by_role: str
    is_override: bool = False
    override_recommendation: Optional[str] = None
    override_reason: Optional[str] = None
    created_at: Optional[str] = None


class DecisionPackageSummary(BaseModel):
    package_id: str
    version_number: int
    title: str
    status: str
    recommendation_type: str
    decision_score: float
    confidence: str
    expected_contribution: float
    risk_adjusted_contribution: float
    created_by: Optional[str] = None
    is_override: bool = False
    created_at: Optional[str] = None


class PackageValidationResponse(BaseModel):
    is_valid: bool
    reason_code: str
    missing_elements: List[str]
    messages: List[str]


class AuditChainVerificationResponse(BaseModel):
    is_valid: bool
    status: str
    event_count: int
    verified_count: int
    broken_links: int
    first_broken_event: Optional[str] = None
    failure_reason: Optional[str] = None


class PackageComparisonResponse(BaseModel):
    base_package_id: str
    base_version: int
    target_package_id: str
    target_version: int
    decision_changed: bool
    recommendation_flip: Optional[str] = None
    score_delta: float
    contribution_delta: float
    cvar_delta: float
    loss_prob_delta: float
    reliability_delta: float
    changed_factors: List[str]
    comparison_summary: str


class ReproductionResponse(BaseModel):
    package_id: str
    status: str
    is_reproducible: bool
    original_score: float
    reproduced_score: float
    original_recommendation: str
    reproduced_recommendation: str
    mismatched_fields: List[str]
    details: Dict[str, Any]


class DecisionRecordExportResponse(BaseModel):
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


class DecisionConfigurationResponse(BaseModel):
    configuration_id: str
    version: str
    name: str
    description: Optional[str] = None
    status: str
    economic_weight: float
    reliability_weight: float
    robustness_weight: float
    tail_risk_weight: float
    schedule_weight: float
    recommendation_thresholds: Dict[str, Any]
    confidence_thresholds: Dict[str, Any]
    risk_thresholds: Dict[str, Any]
    config_hash: str
    effective_date: str
