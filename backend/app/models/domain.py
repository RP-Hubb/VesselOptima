"""
VesselOptima — Domain Models

All SQLAlchemy ORM models for the VesselOptima database schema.
Follows Section S of the Master Build Specification.

Fields are implemented only where their semantics are defined in the spec.
Where a later engine requires additional fields, a comment documents the intent
rather than silently inventing business meaning.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Enum, Boolean,
    ForeignKey, Text, JSON, CheckConstraint, Index, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


# ── Utility ──────────────────────────────────────────────────────────

def utcnow():
    return datetime.now(timezone.utc)


# ── Enums ────────────────────────────────────────────────────────────

class RuntimeModeEnum(str, enum.Enum):
    LIVE = "LIVE"
    OFFLINE_DEMO = "OFFLINE_DEMO"


class DataKindEnum(str, enum.Enum):
    OBSERVED = "OBSERVED"
    PROXY = "PROXY"
    DERIVED = "DERIVED"
    SYNTHETIC = "SYNTHETIC"
    MODEL_PREDICTION = "MODEL_PREDICTION"


class QualityStatusEnum(str, enum.Enum):
    VALID = "VALID"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
    REJECTED = "REJECTED"


class EmploymentControlEnum(str, enum.Enum):
    CONTROLLED = "CONTROLLED"
    NOT_CONTROLLED = "NOT_CONTROLLED"
    UNKNOWN = "UNKNOWN"


class IdleActionEnum(str, enum.Enum):
    WAIT = "WAIT"
    REPOSITION = "REPOSITION"
    ALTERNATIVE_EMPLOYMENT = "ALTERNATIVE_EMPLOYMENT"


class ContractStrategyEnum(str, enum.Enum):
    SPOT = "SPOT"
    SHORT_TERM = "SHORT_TERM"
    MEDIUM_TERM = "MEDIUM_TERM"
    MULTI_VOYAGE = "MULTI_VOYAGE"


class OptimizationStatusEnum(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNBOUNDED = "UNBOUNDED"
    TIME_LIMIT = "TIME_LIMIT"
    SOLVER_ERROR = "SOLVER_ERROR"
    EMPTY_MODEL = "EMPTY_MODEL"
    ERROR = "ERROR"


# ── Mixin for common audit columns ───────────────────────────────────

class AuditMixin:
    """Common audit columns per Build Spec Section S."""
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    created_by = Column(String(255), nullable=True)


class TimestampMixin:
    """Timestamp columns for child/event records without created_by column."""
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


# ── Runtime Mode Events ──────────────────────────────────────────────

class RuntimeModeEvent(AuditMixin, Base):
    """
    Explicit mode-selection audit.
    Database check prevents values other than LIVE / OFFLINE_DEMO.
    """
    __tablename__ = "runtime_mode_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mode = Column(Enum(RuntimeModeEnum), nullable=False)
    mode_session_id = Column(String(64), nullable=False, unique=True, index=True)
    actor = Column(String(255), nullable=True)
    selected_at = Column(DateTime, default=utcnow, nullable=False)
    reason = Column(Text, nullable=True)


# ── Data Sources ─────────────────────────────────────────────────────

class DataSource(AuditMixin, Base):
    """Source governance — every ingested record traces to a registered source."""
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    url = Column(String(1024), nullable=True)
    licence_class = Column(String(100), nullable=True)
    attribution = Column(Text, nullable=True)
    refresh_sla = Column(String(100), nullable=True)
    active = Column(Boolean, default=True, nullable=False)

    observations = relationship("MarketObservation", back_populates="source")


# ── Offline Packages ─────────────────────────────────────────────────

class OfflinePackage(AuditMixin, Base):
    """Frozen local release provenance and compatibility."""
    __tablename__ = "offline_packages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    package_id = Column(String(64), nullable=False, unique=True, index=True)
    schema_version = Column(String(32), nullable=False)
    manifest_hash = Column(String(128), nullable=False)
    coverage_start = Column(DateTime, nullable=True)
    coverage_end = Column(DateTime, nullable=True)
    builder_commit = Column(String(64), nullable=True)
    validator_version = Column(String(32), nullable=True)
    status = Column(String(32), default="VALIDATED", nullable=False)

    datasets = relationship("OfflinePackageDataset", back_populates="package", cascade="all, delete-orphan")


class OfflinePackageDataset(AuditMixin, Base):
    """Individual dataset entry within a validated offline package per Section S."""
    __tablename__ = "offline_package_datasets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    package_id = Column(String(64), ForeignKey("offline_packages.package_id"), nullable=False, index=True)
    dataset_name = Column(String(128), nullable=False)
    file_path = Column(String(512), nullable=False)
    sha256 = Column(String(64), nullable=False)
    row_count = Column(Integer, nullable=False)
    schema_version = Column(String(32), nullable=False)
    provenance_type = Column(Enum(DataKindEnum), default=DataKindEnum.SYNTHETIC, nullable=False)
    description = Column(Text, nullable=True)

    package = relationship("OfflinePackage", back_populates="datasets")



# ── Market Observations ──────────────────────────────────────────────

class MarketObservation(AuditMixin, Base):
    """
    Immutable time series observations.
    Includes mandatory provenance fields per Build Spec.
    """
    __tablename__ = "market_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    series_id = Column(String(128), nullable=False, index=True)
    observed_at = Column(DateTime, nullable=False)
    available_at = Column(DateTime, nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(32), nullable=False)
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=True)
    source_version = Column(String(64), nullable=True)
    quality_status = Column(Enum(QualityStatusEnum), default=QualityStatusEnum.VALID)
    data_kind = Column(Enum(DataKindEnum), default=DataKindEnum.OBSERVED)
    content_hash = Column(String(128), nullable=True)
    is_demo = Column(Boolean, default=False, nullable=False)

    source = relationship("DataSource", back_populates="observations")

    __table_args__ = (
        Index("ix_market_obs_series_observed", "series_id", "observed_at"),
        Index("ix_market_obs_series_available", "series_id", "available_at"),
    )


# ── Ports & Constraints ─────────────────────────────────────────────

class Port(AuditMixin, Base):
    """Port entity with basic identification."""
    __tablename__ = "ports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    country = Column(String(100), nullable=True)
    unlocode = Column(String(10), nullable=True, unique=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    status = Column(String(32), default="ACTIVE")

    constraints = relationship("PortConstraint", back_populates="port")


class PortConstraint(AuditMixin, Base):
    """
    Port/berth-level constraint rules.
    Each constraint is scoped to the narrowest valid level.
    Source evidence is mandatory.
    """
    __tablename__ = "port_constraints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    port_id = Column(Integer, ForeignKey("ports.id"), nullable=False)
    terminal = Column(String(255), nullable=True)
    berth = Column(String(255), nullable=True)
    rule_type = Column(String(64), nullable=False)  # e.g. MAX_DRAFT, MAX_LOA, MAX_BEAM
    value = Column(Float, nullable=True)
    unit = Column(String(32), nullable=True)
    condition = Column(Text, nullable=True)
    effective_from = Column(DateTime, nullable=True)
    effective_to = Column(DateTime, nullable=True)
    source_url = Column(String(1024), nullable=True)
    source_document = Column(String(512), nullable=True)
    verifier = Column(String(255), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    quality_status = Column(Enum(QualityStatusEnum), default=QualityStatusEnum.UNKNOWN)
    version = Column(Integer, default=1)

    port = relationship("Port", back_populates="constraints")


# ── Vessel Classes & Profiles ────────────────────────────────────────

class VesselClass(AuditMixin, Base):
    """Configurable vessel class profiles (Handysize, Supramax, etc.)."""
    __tablename__ = "vessel_classes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False, unique=True)
    dwt_min = Column(Float, nullable=True)
    dwt_max = Column(Float, nullable=True)
    typical_capacity_min = Column(Float, nullable=True)
    typical_capacity_max = Column(Float, nullable=True)
    draft_min = Column(Float, nullable=True)
    draft_max = Column(Float, nullable=True)
    loa_min = Column(Float, nullable=True)
    loa_max = Column(Float, nullable=True)
    beam_min = Column(Float, nullable=True)
    beam_max = Column(Float, nullable=True)
    speed_laden = Column(Float, nullable=True)
    speed_ballast = Column(Float, nullable=True)
    consumption_laden = Column(Float, nullable=True)  # MT/day
    consumption_ballast = Column(Float, nullable=True)
    source = Column(String(255), nullable=True)
    version = Column(Integer, default=1)

    profiles = relationship("VesselProfile", back_populates="vessel_class")


class VesselProfile(AuditMixin, Base):
    """Actual or candidate vessel with specific particulars."""
    __tablename__ = "vessel_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    vessel_class_id = Column(Integer, ForeignKey("vessel_classes.id"), nullable=True)
    imo_number = Column(String(16), nullable=True, unique=True)
    dwt = Column(Float, nullable=True)
    cargo_capacity = Column(Float, nullable=True)
    draft = Column(Float, nullable=True)
    loa = Column(Float, nullable=True)
    beam = Column(Float, nullable=True)
    speed_laden = Column(Float, nullable=True)
    speed_ballast = Column(Float, nullable=True)
    consumption_laden = Column(Float, nullable=True)
    consumption_ballast = Column(Float, nullable=True)
    employment_control = Column(
        Enum(EmploymentControlEnum),
        default=EmploymentControlEnum.UNKNOWN,
    )
    source = Column(String(255), nullable=True)
    status = Column(String(32), default="ACTIVE")
    is_demo = Column(Boolean, default=False)
    version = Column(Integer, default=1)

    vessel_class = relationship("VesselClass", back_populates="profiles")
    availability_events = relationship("VesselAvailabilityEvent", back_populates="vessel_profile")
    commitments = relationship("VesselCommitment", back_populates="vessel_profile")


# ── Vessel Availability & Commitments ────────────────────────────────

class VesselAvailabilityEvent(AuditMixin, Base):
    """Versioned availability/location input for idle-window detection."""
    __tablename__ = "vessel_availability_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vessel_profile_id = Column(Integer, ForeignKey("vessel_profiles.id"), nullable=False)
    available_at = Column(DateTime, nullable=False)
    location_port_id = Column(Integer, ForeignKey("ports.id"), nullable=True)
    location_description = Column(String(255), nullable=True)
    source = Column(String(255), nullable=True)
    confidence = Column(Float, nullable=True)
    data_kind = Column(Enum(DataKindEnum), default=DataKindEnum.OBSERVED)

    vessel_profile = relationship("VesselProfile", back_populates="availability_events")


class VesselCommitment(AuditMixin, Base):
    """Protected schedule boundary — next immutable commitment."""
    __tablename__ = "vessel_commitments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vessel_profile_id = Column(Integer, ForeignKey("vessel_profiles.id"), nullable=False)
    commitment_start = Column(DateTime, nullable=False)
    commitment_end = Column(DateTime, nullable=True)
    route_description = Column(String(512), nullable=True)
    status = Column(String(32), default="CONFIRMED")
    is_immutable = Column(Boolean, default=True)
    employment_control_ref = Column(String(255), nullable=True)
    source = Column(String(255), nullable=True)

    vessel_profile = relationship("VesselProfile", back_populates="commitments")


# ── Routes ───────────────────────────────────────────────────────────

class Route(AuditMixin, Base):
    """Route definitions with distance and endpoints."""
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    origin_port_id = Column(Integer, ForeignKey("ports.id"), nullable=True)
    destination_port_id = Column(Integer, ForeignKey("ports.id"), nullable=True)
    distance_nm = Column(Float, nullable=True)
    distance_source = Column(String(255), nullable=True)
    version = Column(Integer, default=1)


# ── Cargo Parcels ────────────────────────────────────────────────────

class CargoParcel(AuditMixin, Base):
    """Cargo demand/requirement definition."""
    __tablename__ = "cargo_parcels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    commodity = Column(String(128), nullable=False)
    volume_mt = Column(Float, nullable=False)
    origin_port_id = Column(Integer, ForeignKey("ports.id"), nullable=True)
    destination_port_id = Column(Integer, ForeignKey("ports.id"), nullable=True)
    loading_window_start = Column(DateTime, nullable=True)
    loading_window_end = Column(DateTime, nullable=True)
    delivery_deadline = Column(DateTime, nullable=True)
    tolerance_pct = Column(Float, nullable=True)
    status = Column(String(32), default="ACTIVE")
    is_demo = Column(Boolean, default=False)


# ── Candidate Services ───────────────────────────────────────────────

class CandidateService(AuditMixin, Base):
    """A vessel+route+strategy candidate for optimization."""
    __tablename__ = "candidate_services"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vessel_profile_id = Column(Integer, ForeignKey("vessel_profiles.id"), nullable=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=True)
    cargo_parcel_id = Column(Integer, ForeignKey("cargo_parcels.id"), nullable=True)
    contract_strategy = Column(Enum(ContractStrategyEnum), nullable=True)
    estimated_freight_cost = Column(Float, nullable=True)
    estimated_bunker_cost = Column(Float, nullable=True)
    estimated_port_cost = Column(Float, nullable=True)
    estimated_total_cost = Column(Float, nullable=True)
    arrival_date = Column(DateTime, nullable=True)
    max_voyages = Column(Integer, default=1)
    eligibility = Column(Boolean, default=True)
    eligibility_reason = Column(Text, nullable=True)
    data_kind = Column(Enum(DataKindEnum), default=DataKindEnum.DERIVED)
    is_demo = Column(Boolean, default=False)


# ── Forecast Runs & Forecasts ────────────────────────────────────────

class ForecastRun(AuditMixin, Base):
    """Forecast execution metadata for reproducibility."""
    __tablename__ = "forecast_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    target = Column(String(128), nullable=False)
    horizon_days = Column(Integer, nullable=False)
    as_of = Column(DateTime, nullable=False)
    model_id = Column(String(128), nullable=True)
    model_version = Column(String(64), nullable=True)
    artifact_hash = Column(String(128), nullable=True)
    runtime_mode = Column(Enum(RuntimeModeEnum), nullable=False)
    data_context_id = Column(String(64), nullable=True)
    offline_package_id = Column(String(64), nullable=True)
    status = Column(String(32), default="COMPLETED")


class Forecast(AuditMixin, Base):
    """Individual forecast point with prediction intervals."""
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    forecast_run_id = Column(Integer, ForeignKey("forecast_runs.id"), nullable=False)
    forecast_date = Column(DateTime, nullable=False)
    value = Column(Float, nullable=False)
    lower_80 = Column(Float, nullable=True)
    upper_80 = Column(Float, nullable=True)
    lower_95 = Column(Float, nullable=True)
    upper_95 = Column(Float, nullable=True)
    unit = Column(String(32), nullable=True)

    forecast_run = relationship("ForecastRun")


# ── Scenarios ────────────────────────────────────────────────────────

class Scenario(AuditMixin, Base):
    """Immutable scenario definition."""
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    scenario_type = Column(String(64), default="BASE")
    parameters = Column(JSON, nullable=True)
    input_manifest_hash = Column(String(128), nullable=True)
    runtime_mode = Column(Enum(RuntimeModeEnum), nullable=True)
    is_demo = Column(Boolean, default=False)


class ScenarioEvaluation(AuditMixin, Base):
    """
    Phase 8: Evaluates and compares a scenario run against a baseline optimization run.
    Stores objective deltas, cargo coverage, vessel utilization, and assignment differences.
    """
    __tablename__ = "scenario_evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_code = Column(String(128), index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    scenario_type = Column(String(64), default="WHAT_IF", nullable=False)
    baseline_run_id = Column(String(128), index=True, nullable=False)
    scenario_run_id = Column(String(128), index=True, nullable=False)
    parameters = Column(JSON, nullable=True)
    config_hash = Column(String(128), nullable=True)
    comparison_metrics = Column(JSON, nullable=True)
    assignment_deltas = Column(JSON, nullable=True)
    cargo_deltas = Column(JSON, nullable=True)
    runtime_mode = Column(Enum(RuntimeModeEnum), default=RuntimeModeEnum.OFFLINE_DEMO, nullable=False)
    audit_trail = Column(JSON, nullable=True)


class ScenarioSensitivityRun(AuditMixin, Base):
    """
    Phase 8: Stores one-variable-at-a-time parameter sweeps, break-even switching
    thresholds, and assignment robustness scores across scenario ensembles.
    """
    __tablename__ = "scenario_sensitivity_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sweep_id = Column(String(128), unique=True, index=True, nullable=False)
    parameter_name = Column(String(64), nullable=False)
    baseline_run_id = Column(String(128), index=True, nullable=False)
    parameter_range = Column(JSON, nullable=True)
    sweep_points = Column(JSON, nullable=False)
    break_even_points = Column(JSON, nullable=True)
    robustness_scores = Column(JSON, nullable=True)
    runtime_mode = Column(Enum(RuntimeModeEnum), default=RuntimeModeEnum.OFFLINE_DEMO, nullable=False)
    audit_trail = Column(JSON, nullable=True)



# ── Optimization Runs ────────────────────────────────────────────────

class OptimizationRun(AuditMixin, Base):
    """MILP optimization execution record."""
    __tablename__ = "optimization_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(128), unique=True, index=True, nullable=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=True)
    status = Column(Enum(OptimizationStatusEnum), default=OptimizationStatusEnum.QUEUED)
    objective_value = Column(Float, nullable=True)
    total_revenue = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=True)
    total_contribution = Column(Float, nullable=True)
    avoided_idle_cost = Column(Float, nullable=True)
    solver_name = Column(String(64), nullable=True)
    solver_version = Column(String(64), nullable=True)
    solver_status = Column(String(64), nullable=True)
    solve_time_seconds = Column(Float, nullable=True)
    runtime_mode = Column(Enum(RuntimeModeEnum), nullable=False)
    data_context_id = Column(String(64), nullable=True)
    offline_package_id = Column(String(64), nullable=True)
    objective_decomposition = Column(JSON, nullable=True)
    solver_metadata = Column(JSON, nullable=True)
    result_summary = Column(JSON, nullable=True)
    infeasibility_reason = Column(Text, nullable=True)
    audit_trail = Column(JSON, nullable=True)

    scenario = relationship("Scenario")
    assignments = relationship("OptimizationAssignment", back_populates="optimization_run", cascade="all, delete-orphan")


class OptimizationAssignment(AuditMixin, Base):
    """Individual candidate assignment decision within an optimization run."""
    __tablename__ = "optimization_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    optimization_run_id = Column(Integer, ForeignKey("optimization_runs.id"), nullable=False, index=True)
    candidate_id = Column(String(128), nullable=False, index=True)
    vessel_id = Column(Integer, ForeignKey("vessel_profiles.id"), nullable=False, index=True)
    cargo_id = Column(Integer, ForeignKey("cargo_parcels.id"), nullable=True, index=True)
    is_selected = Column(Boolean, nullable=False, default=False)
    selection_status = Column(String(64), nullable=False)  # SELECTED, MODEL_REJECTED, INFEASIBLE_UPSTREAM, UNASSIGNED
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    expected_revenue = Column(Float, nullable=True)
    voyage_cost = Column(Float, nullable=True)
    gross_contribution = Column(Float, nullable=True)
    ballast_distance_nm = Column(Float, nullable=True)
    ballast_days = Column(Float, nullable=True)
    voyage_days = Column(Float, nullable=True)
    assignment_metadata = Column(JSON, nullable=True)
    trade_off_notes = Column(Text, nullable=True)
    runtime_mode = Column(Enum(RuntimeModeEnum), nullable=False, default=RuntimeModeEnum.DEMO if hasattr(RuntimeModeEnum, 'DEMO') else RuntimeModeEnum.OFFLINE_DEMO)

    optimization_run = relationship("OptimizationRun", back_populates="assignments")
    vessel = relationship("VesselProfile")
    cargo = relationship("CargoParcel")


# ── Risk Intelligence & Uncertainty ──────────────────────────────────

class RiskRun(AuditMixin, Base):
    """
    Phase 9: Record of a Monte Carlo risk simulation run evaluating
    plan uncertainty, distributions, and downside tail risk.
    """
    __tablename__ = "risk_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(128), unique=True, index=True, nullable=False)
    optimization_run_id = Column(String(128), index=True, nullable=False)
    scenario_run_id = Column(String(128), index=True, nullable=True)
    simulation_count = Column(Integer, default=5000, nullable=False)
    random_seed = Column(Integer, default=42, nullable=False)
    runtime_mode = Column(Enum(RuntimeModeEnum), default=RuntimeModeEnum.OFFLINE_DEMO, nullable=False)
    simulation_parameters = Column(JSON, nullable=True)
    status = Column(String(32), default="COMPLETED", nullable=False)
    execution_time_seconds = Column(Float, default=0.0)
    audit_trail = Column(JSON, nullable=True)

    metrics = relationship("RiskMetric", back_populates="risk_run", uselist=False, cascade="all, delete-orphan")
    assignment_metrics = relationship("RiskAssignmentMetric", back_populates="risk_run", cascade="all, delete-orphan")
    drivers = relationship("RiskDriver", back_populates="risk_run", cascade="all, delete-orphan")


class RiskMetric(AuditMixin, Base):
    """
    Phase 9: Portfolio-level risk metrics, value-at-risk, conditional VaR,
    loss probabilities, and plan reliability score.
    """
    __tablename__ = "risk_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    risk_run_id = Column(Integer, ForeignKey("risk_runs.id"), nullable=False, index=True)
    expected_contribution = Column(Float, nullable=False)
    contribution_std = Column(Float, nullable=False)
    percentiles = Column(JSON, nullable=False)
    var90 = Column(Float, nullable=False)
    var95 = Column(Float, nullable=False)
    var95_downside = Column(Float, nullable=False)
    cvar90 = Column(Float, nullable=False)
    cvar95 = Column(Float, nullable=False)
    loss_probability = Column(Float, nullable=False)
    expected_loss = Column(Float, nullable=False)
    plan_reliability_score = Column(Float, nullable=False)
    risk_tier = Column(String(32), default="MODERATE", nullable=False)
    distribution_summary = Column(JSON, nullable=True)

    risk_run = relationship("RiskRun", back_populates="metrics")


class RiskAssignmentMetric(AuditMixin, Base):
    """
    Phase 9: Detailed risk, schedule fragility, and survival metrics
    for each vessel-cargo assignment within the simulated plan.
    """
    __tablename__ = "risk_assignment_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    risk_run_id = Column(Integer, ForeignKey("risk_runs.id"), nullable=False, index=True)
    candidate_id = Column(String(128), nullable=False, index=True)
    vessel_id = Column(Integer, ForeignKey("vessel_profiles.id"), nullable=False)
    cargo_id = Column(Integer, ForeignKey("cargo_parcels.id"), nullable=True)
    expected_net_contribution = Column(Float, nullable=False)
    contribution_std = Column(Float, nullable=False)
    loss_probability = Column(Float, nullable=False)
    cvar95 = Column(Float, nullable=False)
    expected_arrival = Column(DateTime, nullable=True)
    p90_arrival = Column(DateTime, nullable=True)
    schedule_buffer_days = Column(Float, default=0.0)
    laycan_miss_probability = Column(Float, default=0.0)
    economic_survival_probability = Column(Float, default=1.0)
    schedule_survival_probability = Column(Float, default=1.0)
    risk_tier = Column(String(32), default="MODERATE", nullable=False)

    risk_run = relationship("RiskRun", back_populates="assignment_metrics")
    vessel = relationship("VesselProfile")
    cargo = relationship("CargoParcel")


class RiskDriver(AuditMixin, Base):
    """
    Phase 9: Sensitivity and variance attribution of uncertain risk variables
    to portfolio outcome volatility.
    """
    __tablename__ = "risk_drivers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    risk_run_id = Column(Integer, ForeignKey("risk_runs.id"), nullable=False, index=True)
    variable_id = Column(String(64), nullable=False)
    variable_name = Column(String(128), nullable=False)
    category = Column(String(64), nullable=False)
    uncertainty_contribution_pct = Column(Float, nullable=False)
    sensitivity_coefficient = Column(Float, default=0.0)

    risk_run = relationship("RiskRun", back_populates="drivers")
# ── Decision Intelligence & Explainable Recommendations (Phase 10) ───

class DecisionRun(AuditMixin, Base):
    """
    Phase 10: Master record of an auditable, deterministic decision evaluation
    synthesizing Phase 7 MILP, Phase 8 scenarios, and Phase 9 risk intelligence.
    """
    __tablename__ = "decision_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(128), unique=True, index=True, nullable=False)
    optimization_run_id = Column(String(128), index=True, nullable=False)
    scenario_run_id = Column(String(128), index=True, nullable=True)
    risk_run_id = Column(String(128), index=True, nullable=True)
    recommendation_type = Column(String(64), nullable=False)  # PROCEED, PROCEED_WITH_CAUTION, MONITOR, RECONSIDER, REJECT, NO_ACTION
    confidence = Column(String(32), default="HIGH", nullable=False)  # HIGH, MEDIUM, LOW
    decision_score = Column(Float, nullable=False)  # 0 to 100
    decision_stability = Column(Float, default=1.0)  # fraction of scenarios where recommendation holds
    scoring_breakdown = Column(JSON, nullable=True)
    risk_adjusted_contribution = Column(Float, nullable=True)
    threshold_config = Column(JSON, nullable=True)
    engine_version = Column(String(32), default="1.0.0", nullable=False)
    rule_version = Column(String(32), default="1.0.0", nullable=False)
    score_version = Column(String(32), default="1.0.0", nullable=False)
    input_hash = Column(String(128), nullable=True)
    output_hash = Column(String(128), nullable=True)
    audit_trail = Column(JSON, nullable=True)
    runtime_mode = Column(Enum(RuntimeModeEnum), default=RuntimeModeEnum.OFFLINE_DEMO, nullable=False)
    status = Column(String(32), default="COMPLETED", nullable=False)
    execution_time_seconds = Column(Float, default=0.0)

    recommendations = relationship("DecisionRecommendation", back_populates="decision_run", cascade="all, delete-orphan")
    evidence = relationship("DecisionEvidence", back_populates="decision_run", uselist=False, cascade="all, delete-orphan")
    actions = relationship("DecisionAction", back_populates="decision_run", cascade="all, delete-orphan")
    tradeoffs = relationship("DecisionTradeoff", back_populates="decision_run", cascade="all, delete-orphan")


class DecisionRecommendation(AuditMixin, Base):
    """
    Phase 10: Plan-level or assignment-level deterministic recommendation
    with explicit reason codes, metrics, thresholds, and human-readable explanations.
    """
    __tablename__ = "decision_recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    decision_run_id = Column(Integer, ForeignKey("decision_runs.id"), nullable=False, index=True)
    scope = Column(String(32), default="PLAN", nullable=False)  # PLAN, ASSIGNMENT
    candidate_id = Column(String(128), nullable=True, index=True)
    vessel_id = Column(Integer, ForeignKey("vessel_profiles.id"), nullable=True)
    cargo_id = Column(Integer, ForeignKey("cargo_parcels.id"), nullable=True)
    recommendation_type = Column(String(64), nullable=False)
    primary_reason_code = Column(String(64), nullable=False)
    reason_codes = Column(JSON, nullable=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False)
    action_advice = Column(Text, nullable=True)
    supporting_metrics = Column(JSON, nullable=True)
    thresholds_used = Column(JSON, nullable=True)

    decision_run = relationship("DecisionRun", back_populates="recommendations")
    vessel = relationship("VesselProfile")
    cargo = relationship("CargoParcel")


class DecisionEvidence(AuditMixin, Base):
    """
    Phase 10: Authoritative stored snapshot of upstream evidence (Phases 7, 8, 9)
    from which all recommendations and scores are derived.
    """
    __tablename__ = "decision_evidence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    decision_run_id = Column(Integer, ForeignKey("decision_runs.id"), nullable=False, index=True)
    optimization_objective = Column(Float, nullable=True)
    expected_contribution = Column(Float, nullable=False)
    baseline_contribution = Column(Float, nullable=True)
    risk_adjusted_contribution = Column(Float, nullable=False)
    loss_probability = Column(Float, nullable=False)
    cvar_95 = Column(Float, nullable=False)
    var_95_downside = Column(Float, nullable=False)
    assignment_survival = Column(Float, nullable=False)
    plan_reliability = Column(Float, nullable=False)
    laycan_miss_probability = Column(Float, default=0.0)
    scenario_survival_rate = Column(Float, default=1.0)
    robustness_tier = Column(String(64), default="CORE_ROBUST")
    top_risk_drivers = Column(JSON, nullable=True)
    critical_warnings = Column(JSON, nullable=True)
    evidence_payload = Column(JSON, nullable=True)

    decision_run = relationship("DecisionRun", back_populates="evidence")


class DecisionAction(AuditMixin, Base):
    """
    Phase 10: Prioritized operational actions, monitoring triggers,
    and contingency guidelines for fleet managers.
    """
    __tablename__ = "decision_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    decision_run_id = Column(Integer, ForeignKey("decision_runs.id"), nullable=False, index=True)
    action_id = Column(String(128), nullable=False)
    priority = Column(String(32), nullable=False)  # CRITICAL, HIGH, MEDIUM, LOW
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    affected_variable = Column(String(128), nullable=True)
    affected_assignment_id = Column(String(128), nullable=True)
    trigger_condition = Column(Text, nullable=True)
    recommended_action = Column(Text, nullable=False)
    action_status = Column(String(32), default="PENDING")

    decision_run = relationship("DecisionRun", back_populates="actions")


class DecisionTradeoff(AuditMixin, Base):
    """
    Phase 10: Multi-plan trade-off analysis comparing baseline,
    scenario alternatives, and risk-adjusted options.
    """
    __tablename__ = "decision_tradeoffs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    decision_run_id = Column(Integer, ForeignKey("decision_runs.id"), nullable=False, index=True)
    comparison_plan_id = Column(String(128), nullable=False)
    comparison_plan_name = Column(String(255), nullable=False)
    baseline_plan_name = Column(String(255), nullable=False)
    contribution_delta = Column(Float, nullable=False)
    loss_prob_delta = Column(Float, nullable=False)
    cvar_delta = Column(Float, nullable=False)
    reliability_delta = Column(Float, nullable=False)
    tradeoff_summary = Column(Text, nullable=False)
    tradeoff_details = Column(JSON, nullable=True)

    decision_run = relationship("DecisionRun", back_populates="tradeoffs")


# ── Decision Governance, Audit & Institutional Control (Phase 11) ────

class DecisionPackage(AuditMixin, Base):
    """
    Phase 11: Master institutional record of a finalized, auditable decision.
    Contains immutable references to Phase 7–10 artifacts, lifecycle status,
    and cryptographic provenance hashes.
    """
    __tablename__ = "decision_packages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    package_id = Column(String(128), unique=True, index=True, nullable=False)
    version_number = Column(Integer, default=1, nullable=False)
    parent_package_id = Column(String(128), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(64), default="DRAFT", nullable=False)  # DRAFT, VALIDATED, SUBMITTED, UNDER_REVIEW, APPROVED, REJECTED, ARCHIVED
    optimization_run_id = Column(String(128), nullable=False, index=True)
    scenario_run_id = Column(String(128), nullable=True, index=True)
    risk_run_id = Column(String(128), nullable=True, index=True)
    decision_run_id = Column(String(128), nullable=False, index=True)
    configuration_id = Column(String(128), nullable=True, index=True)
    configuration_version = Column(String(32), default="1.0.0", nullable=False)
    engine_versions = Column(JSON, nullable=True)
    recommendation_type = Column(String(64), nullable=False)
    decision_score = Column(Float, nullable=False)
    confidence = Column(String(32), default="HIGH", nullable=False)
    decision_stability = Column(Float, default=1.0, nullable=False)
    expected_contribution = Column(Float, nullable=False)
    risk_adjusted_contribution = Column(Float, nullable=False)
    loss_probability = Column(Float, nullable=False)
    cvar_95 = Column(Float, nullable=False)
    plan_reliability = Column(Float, nullable=False)
    evidence_summary = Column(JSON, nullable=True)
    actions_summary = Column(JSON, nullable=True)
    threshold_config = Column(JSON, nullable=True)
    input_hash = Column(String(128), nullable=False)
    output_hash = Column(String(128), nullable=False)
    package_hash = Column(String(128), nullable=False)
    created_by_role = Column(String(64), default="ANALYST", nullable=False)
    is_override = Column(Boolean, default=False, nullable=False)
    runtime_mode = Column(Enum(RuntimeModeEnum), default=RuntimeModeEnum.OFFLINE_DEMO, nullable=False)
    audit_trail = Column(JSON, nullable=True)

    versions = relationship("DecisionPackageVersion", back_populates="package", cascade="all, delete-orphan")
    audit_events = relationship("GovernanceAuditEvent", back_populates="package", cascade="all, delete-orphan")
    approvals = relationship("ApprovalAction", back_populates="package", cascade="all, delete-orphan")
    overrides = relationship("DecisionOverride", back_populates="package", cascade="all, delete-orphan")


class DecisionPackageVersion(AuditMixin, Base):
    """
    Phase 11: Version history for Decision Packages.
    Every update creates an immutable incremental version (V1 -> V2).
    """
    __tablename__ = "decision_package_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    package_id = Column(Integer, ForeignKey("decision_packages.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    version_tag = Column(String(64), nullable=False)
    parent_version_tag = Column(String(64), nullable=True)
    package_hash = Column(String(128), nullable=False)
    input_hash = Column(String(128), nullable=False)
    output_hash = Column(String(128), nullable=False)
    change_summary = Column(Text, nullable=False)
    changed_fields = Column(JSON, nullable=True)
    evidence_snapshot = Column(JSON, nullable=False)
    configuration_version = Column(String(32), nullable=False)

    package = relationship("DecisionPackage", back_populates="versions")


class GovernanceAuditEvent(AuditMixin, Base):
    """
    Phase 11: Cryptographically hash-chained, append-only governance audit event.
    Provides tamper-evident record of all lifecycle events.
    """
    __tablename__ = "governance_audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    package_id = Column(Integer, ForeignKey("decision_packages.id"), nullable=False, index=True)
    audit_event_id = Column(String(128), unique=True, index=True, nullable=False)
    sequence_number = Column(Integer, nullable=False)
    event_type = Column(String(64), nullable=False)
    actor = Column(String(255), nullable=False)
    actor_role = Column(String(64), nullable=False)
    action = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    previous_hash = Column(String(128), nullable=False)
    event_hash = Column(String(128), nullable=False)
    metadata_payload = Column(JSON, nullable=True)

    package = relationship("DecisionPackage", back_populates="audit_events")


class ApprovalAction(AuditMixin, Base):
    """
    Phase 11: Formal governance workflow actions (SUBMIT, REVIEW, APPROVE, REJECT).
    Enforces separation of duties (creator != approver).
    """
    __tablename__ = "approval_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    package_id = Column(Integer, ForeignKey("decision_packages.id"), nullable=False, index=True)
    action_type = Column(String(64), nullable=False)
    actor = Column(String(255), nullable=False)
    actor_role = Column(String(64), nullable=False)
    status = Column(String(64), nullable=False)
    notes = Column(Text, nullable=True)

    package = relationship("DecisionPackage", back_populates="approvals")


class DecisionConfiguration(AuditMixin, Base):
    """
    Phase 11: Versioned governance of decision scoring weights, thresholds,
    and institutional risk policies.
    """
    __tablename__ = "decision_configurations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    configuration_id = Column(String(128), unique=True, index=True, nullable=False)
    version = Column(String(32), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), default="ACTIVE", nullable=False)  # DRAFT, ACTIVE, RETIRED
    economic_weight = Column(Float, default=0.35, nullable=False)
    reliability_weight = Column(Float, default=0.25, nullable=False)
    robustness_weight = Column(Float, default=0.20, nullable=False)
    tail_risk_weight = Column(Float, default=0.10, nullable=False)
    schedule_weight = Column(Float, default=0.10, nullable=False)
    recommendation_thresholds = Column(JSON, nullable=False)
    confidence_thresholds = Column(JSON, nullable=False)
    risk_thresholds = Column(JSON, nullable=False)
    config_hash = Column(String(128), nullable=False)
    effective_date = Column(DateTime, nullable=False)


class ConfigurationChange(AuditMixin, Base):
    """
    Phase 11: Audit log of institutional decision configuration revisions.
    """
    __tablename__ = "configuration_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    change_id = Column(String(128), unique=True, index=True, nullable=False)
    old_configuration_id = Column(String(128), nullable=True)
    new_configuration_id = Column(String(128), nullable=False)
    changed_fields = Column(JSON, nullable=False)
    reason = Column(Text, nullable=False)
    actor = Column(String(255), nullable=False)
    actor_role = Column(String(64), nullable=False)
    timestamp = Column(DateTime, nullable=False)


class DecisionOverride(AuditMixin, Base):
    """
    Phase 11: Explicit human override of an analytical model recommendation.
    Preserves original recommendation and enforces formal justification & attribution.
    """
    __tablename__ = "decision_overrides"

    id = Column(Integer, primary_key=True, autoincrement=True)
    package_id = Column(Integer, ForeignKey("decision_packages.id"), nullable=False, index=True)
    override_id = Column(String(128), unique=True, index=True, nullable=False)
    original_recommendation = Column(String(64), nullable=False)
    override_recommendation = Column(String(64), nullable=False)
    reason = Column(Text, nullable=False)
    actor = Column(String(255), nullable=False)
    actor_role = Column(String(64), nullable=False)
    supporting_note = Column(Text, nullable=True)
    approval_actor = Column(String(255), nullable=True)
    approval_status = Column(String(32), default="PENDING", nullable=False)

    package = relationship("DecisionPackage", back_populates="overrides")


# ── Recommendations ──────────────────────────────────────────────────

class Recommendation(AuditMixin, Base):
    """Final decision recommendation with audit linkage."""
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    optimization_run_id = Column(Integer, ForeignKey("optimization_runs.id"), nullable=True)
    recommendation_type = Column(String(64), nullable=False)
    action = Column(String(128), nullable=False)
    explanation = Column(Text, nullable=True)
    confidence = Column(String(32), nullable=True)
    runtime_mode = Column(Enum(RuntimeModeEnum), nullable=False)
    data_context_id = Column(String(64), nullable=True)

    audit_events = relationship("AuditEvent", back_populates="recommendation")


# ── Audit Events ─────────────────────────────────────────────────────

class AuditEvent(AuditMixin, Base):
    """Traceability record for every major decision."""
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recommendation_id = Column(Integer, ForeignKey("recommendations.id"), nullable=True)
    event_type = Column(String(64), nullable=False)
    actor = Column(String(255), nullable=True)
    action = Column(String(255), nullable=False)
    detail = Column(JSON, nullable=True)
    runtime_mode = Column(Enum(RuntimeModeEnum), nullable=True)
    mode_session_id = Column(String(64), nullable=True)
    data_context_id = Column(String(64), nullable=True)
    source_manifest_hash = Column(String(128), nullable=True)

    recommendation = relationship("Recommendation", back_populates="audit_events")


# ── Idle Employment Evaluations ──────────────────────────────────────

class IdleEmploymentEvaluation(AuditMixin, Base):
    """Detected idle window and overall evaluation record."""
    __tablename__ = "idle_employment_evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vessel_profile_id = Column(Integer, ForeignKey("vessel_profiles.id"), nullable=False)
    availability_event_id = Column(Integer, ForeignKey("vessel_availability_events.id"), nullable=True)
    commitment_id = Column(Integer, ForeignKey("vessel_commitments.id"), nullable=True)
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=True)
    idle_days = Column(Float, nullable=True)
    employment_control = Column(Enum(EmploymentControlEnum), nullable=True)
    is_actionable = Column(Boolean, default=False)
    selected_action = Column(Enum(IdleActionEnum), nullable=True)
    runtime_mode = Column(Enum(RuntimeModeEnum), nullable=False)
    data_context_id = Column(String(64), nullable=True)
    status = Column(String(32), default="EVALUATED")


class IdleActionEvaluation(AuditMixin, Base):
    """Individual action comparison within an idle evaluation."""
    __tablename__ = "idle_action_evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    evaluation_id = Column(Integer, ForeignKey("idle_employment_evaluations.id"), nullable=False)
    action_type = Column(Enum(IdleActionEnum), nullable=False)
    is_feasible = Column(Boolean, default=True)
    feasibility_reason = Column(Text, nullable=True)
    idle_cost = Column(Float, nullable=True)
    reposition_cost = Column(Float, nullable=True)
    bunker_cost = Column(Float, nullable=True)
    port_cost = Column(Float, nullable=True)
    expected_contribution = Column(Float, nullable=True)
    total_expected_cost = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)
    is_selected = Column(Boolean, default=False)
    reason_codes = Column(JSON, nullable=True)

    evaluation = relationship("IdleEmploymentEvaluation")


# ── Backtest Runs ────────────────────────────────────────────────────

class BacktestRun(AuditMixin, Base):
    """Historical point-in-time decision simulation record."""
    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    config = Column(JSON, nullable=True)
    evaluation_start = Column(DateTime, nullable=True)
    evaluation_end = Column(DateTime, nullable=True)
    status = Column(String(32), default="COMPLETED")
    runtime_mode = Column(Enum(RuntimeModeEnum), nullable=False)
    data_context_id = Column(String(64), nullable=True)
    result_summary = Column(JSON, nullable=True)


# ── Feasibility Checks ───────────────────────────────────────────────

class FeasibilityCheck(AuditMixin, Base):
    """
    Feasibility evaluation record capturing the operational, physical,
    and temporal assessment of a vessel-cargo-route assignment per Build Spec.
    """
    __tablename__ = "feasibility_checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cargo_id = Column(Integer, ForeignKey("cargo_parcels.id"), nullable=True, index=True)
    vessel_id = Column(Integer, ForeignKey("vessel_profiles.id"), nullable=True, index=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=True, index=True)
    is_feasible = Column(Boolean, nullable=False)
    primary_reason_code = Column(String(128), nullable=True)
    reason_codes = Column(JSON, nullable=True)
    failed_checks = Column(JSON, nullable=True)
    checks = Column(JSON, nullable=True)
    warnings = Column(JSON, nullable=True)
    timing = Column(JSON, nullable=True)
    evidence = Column(JSON, nullable=True)
    provenance = Column(JSON, nullable=True)
    evaluated_at = Column(DateTime, default=utcnow, nullable=False)
    runtime_mode = Column(Enum(RuntimeModeEnum), default=RuntimeModeEnum.OFFLINE_DEMO, nullable=False)

    cargo = relationship("CargoParcel")
    vessel = relationship("VesselProfile")
    route = relationship("Route")


# ── Procurement Strategy & Timing ────────────────────────────────────

class ProcurementConfig(AuditMixin, Base):
    """
    Configurable procurement profile defining stage-by-stage administrative lead time
    and operational boundaries per Section 5 of Build Specification.
    """
    __tablename__ = "procurement_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    tender_preparation_days = Column(Float, nullable=False, default=3.0)
    bid_submission_days = Column(Float, nullable=False, default=5.0)
    technical_evaluation_days = Column(Float, nullable=False, default=2.0)
    commercial_evaluation_days = Column(Float, nullable=False, default=2.0)
    approval_days = Column(Float, nullable=False, default=1.0)
    award_days = Column(Float, nullable=False, default=1.0)
    minimum_lead_time_days = Column(Float, nullable=False, default=14.0)
    is_active = Column(Boolean, default=True, nullable=False)
    data_classification = Column(String(64), default="CONFIGURED", nullable=False)
    provenance = Column(JSON, nullable=True)


class ProcurementEvaluation(AuditMixin, Base):
    """
    Procurement strategy evaluation candidate record capturing timing,
    feasibility admittance, forecast signals, and transparent cost breakdown.
    """
    __tablename__ = "procurement_evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cargo_id = Column(Integer, ForeignKey("cargo_parcels.id"), nullable=True, index=True)
    profile_id = Column(String(64), nullable=False)
    strategy_type = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)
    timing_signal = Column(String(64), nullable=False)
    candidate_data = Column(JSON, nullable=True)
    timing_detail = Column(JSON, nullable=True)
    cost_detail = Column(JSON, nullable=True)
    forecast_detail = Column(JSON, nullable=True)
    feasibility_detail = Column(JSON, nullable=True)
    assumptions = Column(JSON, nullable=True)
    provenance = Column(JSON, nullable=True)
    evaluated_at = Column(DateTime, default=utcnow, nullable=False)
    runtime_mode = Column(Enum(RuntimeModeEnum), default=RuntimeModeEnum.OFFLINE_DEMO, nullable=False)

    cargo = relationship("CargoParcel")


# ── Idle Management & Alternative Employment ────────────────────────

class EmploymentOpportunity(AuditMixin, Base):
    """
    Alternative employment candidate opportunity for optimization handoff.
    Captures operational feasibility, procurement status, chronological timeline,
    and transparent economics without performing global fleet allocation.
    """
    __tablename__ = "employment_opportunities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(String(128), unique=True, nullable=False, index=True)
    vessel_id = Column(Integer, ForeignKey("vessel_profiles.id"), nullable=False, index=True)
    cargo_id = Column(Integer, ForeignKey("cargo_parcels.id"), nullable=True, index=True)
    employment_type = Column(String(64), nullable=False)
    origin_port_id = Column(Integer, ForeignKey("ports.id"), nullable=True)
    destination_port_id = Column(Integer, ForeignKey("ports.id"), nullable=True)
    availability_start = Column(DateTime, nullable=False)
    availability_end = Column(DateTime, nullable=True)
    employment_start = Column(DateTime, nullable=True)
    employment_end = Column(DateTime, nullable=True)
    delivery_deadline = Column(DateTime, nullable=True)
    ballast_distance_nm = Column(Float, nullable=True)
    ballast_days = Column(Float, nullable=True)
    voyage_days = Column(Float, nullable=True)
    idle_days = Column(Float, nullable=True)
    status = Column(String(32), nullable=False)  # FEASIBLE, INFEASIBLE
    primary_reason_code = Column(String(64), nullable=True)
    primary_reason_description = Column(Text, nullable=True)
    optimization_status = Column(String(64), nullable=False, default="READY_FOR_OPTIMIZATION")
    economic_summary = Column(JSON, nullable=True)
    timeline_detail = Column(JSON, nullable=True)
    feasibility_detail = Column(JSON, nullable=True)
    procurement_detail = Column(JSON, nullable=True)
    provenance = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    runtime_mode = Column(Enum(RuntimeModeEnum), default=RuntimeModeEnum.OFFLINE_DEMO, nullable=False)

    vessel = relationship("VesselProfile")
    cargo = relationship("CargoParcel")
    origin_port = relationship("Port", foreign_keys=[origin_port_id])
    destination_port = relationship("Port", foreign_keys=[destination_port_id])


class IdleAssessment(AuditMixin, Base):
    """
    Evaluates vessel idle states and financial cost exposure during availability gaps.
    """
    __tablename__ = "idle_assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vessel_id = Column(Integer, ForeignKey("vessel_profiles.id"), nullable=False, index=True)
    assessment_date = Column(DateTime, nullable=False)
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=True)
    available_days = Column(Float, nullable=False, default=0.0)
    idle_days = Column(Float, nullable=False, default=0.0)
    idle_reason = Column(String(64), nullable=False)
    daily_idle_rate = Column(Float, nullable=False, default=0.0)
    idle_cost = Column(Float, nullable=False, default=0.0)
    cost_source = Column(String(64), nullable=False, default="ASSUMED")
    next_commitment_id = Column(Integer, ForeignKey("vessel_commitments.id"), nullable=True)
    next_commitment_start = Column(DateTime, nullable=True)
    advisory_notes = Column(Text, nullable=True)
    provenance = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    runtime_mode = Column(Enum(RuntimeModeEnum), default=RuntimeModeEnum.OFFLINE_DEMO, nullable=False)

    vessel = relationship("VesselProfile")
    next_commitment = relationship("VesselCommitment")


# ── Phase 12: Maritime Data Integration & Quality Governance ───────────

class GovernanceDataset(AuditMixin, Base):
    """
    Phase 12: Controlled, versioned maritime dataset container with quality score and provenance.
    """
    __tablename__ = "governance_datasets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String(128), unique=True, index=True, nullable=False)
    dataset_type = Column(String(64), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    current_version = Column(Integer, default=1, nullable=False)
    status = Column(String(32), default="IMPORTED", nullable=False, index=True)
    content_hash = Column(String(128), nullable=False)
    quality_score = Column(Float, default=0.0, nullable=False)
    freshness_status = Column(String(32), default="UNKNOWN", nullable=False)
    record_count = Column(Integer, default=0, nullable=False)
    created_by = Column(String(255), default="data_engineer", nullable=False)
    approved_by = Column(String(255), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    runtime_mode = Column(Enum(RuntimeModeEnum), default=RuntimeModeEnum.OFFLINE_DEMO, nullable=False)

    versions = relationship("DatasetVersion", back_populates="dataset", cascade="all, delete-orphan")
    records = relationship("DatasetRecord", back_populates="dataset", cascade="all, delete-orphan")
    validations = relationship("DatasetValidation", back_populates="dataset", cascade="all, delete-orphan")
    quality_reports = relationship("DatasetQuality", back_populates="dataset", cascade="all, delete-orphan")
    provenance = relationship("DatasetProvenance", back_populates="dataset", uselist=False, cascade="all, delete-orphan")
    quarantine_records = relationship("QuarantineRecord", back_populates="dataset", cascade="all, delete-orphan")
    changes = relationship("DatasetChange", back_populates="dataset", cascade="all, delete-orphan")
    impacts = relationship("DatasetImpact", back_populates="dataset", cascade="all, delete-orphan")


class DatasetVersion(AuditMixin, Base):
    """
    Phase 12: Immutable version record of a dataset with content hash and storage metadata.
    """
    __tablename__ = "dataset_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("governance_datasets.id"), nullable=False, index=True)
    version_number = Column(Integer, default=1, nullable=False)
    parent_version_number = Column(Integer, nullable=True)
    content_hash = Column(String(128), nullable=False)
    schema_version = Column(String(32), default="1.0.0", nullable=False)
    record_count = Column(Integer, default=0, nullable=False)
    change_summary = Column(Text, nullable=True)
    storage_path = Column(String(512), nullable=True)
    created_by = Column(String(255), default="data_engineer", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    dataset = relationship("GovernanceDataset", back_populates="versions")


class DatasetRecord(TimestampMixin, Base):
    """
    Phase 12: Individual normalized record stored with row-level SHA-256 hash.
    """
    __tablename__ = "dataset_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("governance_datasets.id"), nullable=False, index=True)
    version_number = Column(Integer, default=1, nullable=False)
    record_index = Column(Integer, nullable=False)
    business_key = Column(String(255), nullable=True, index=True)
    record_data = Column(JSON, nullable=False)
    record_hash = Column(String(128), nullable=False)

    dataset = relationship("GovernanceDataset", back_populates="records")


class DatasetValidation(TimestampMixin, Base):
    """
    Phase 12: Validation layer outcome (Structural, Type, Physical, Relational).
    """
    __tablename__ = "dataset_validations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("governance_datasets.id"), nullable=False, index=True)
    version_number = Column(Integer, default=1, nullable=False)
    layer = Column(String(32), nullable=False)
    is_valid = Column(Boolean, default=True, nullable=False)
    error_count = Column(Integer, default=0, nullable=False)
    warning_count = Column(Integer, default=0, nullable=False)
    details = Column(JSON, nullable=True)
    executed_at = Column(DateTime, default=utcnow, nullable=False)

    dataset = relationship("GovernanceDataset", back_populates="validations")


class DatasetQuality(TimestampMixin, Base):
    """
    Phase 12: Transparent 6-factor data quality score evaluation.
    """
    __tablename__ = "dataset_qualities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("governance_datasets.id"), nullable=False, index=True)
    version_number = Column(Integer, default=1, nullable=False)
    overall_score = Column(Float, nullable=False)
    completeness_score = Column(Float, nullable=False)
    validity_score = Column(Float, nullable=False)
    consistency_score = Column(Float, nullable=False)
    uniqueness_score = Column(Float, nullable=False)
    timeliness_score = Column(Float, nullable=False)
    provenance_score = Column(Float, nullable=False)
    weights_snapshot = Column(JSON, nullable=True)
    freshness_status = Column(String(32), nullable=False)
    evaluated_at = Column(DateTime, default=utcnow, nullable=False)

    dataset = relationship("GovernanceDataset", back_populates="quality_reports")


class DatasetProvenance(TimestampMixin, Base):
    """
    Phase 12: Full origin, source, actor, and transformation lineage.
    """
    __tablename__ = "dataset_provenances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("governance_datasets.id"), nullable=False, index=True)
    version_number = Column(Integer, default=1, nullable=False)
    source_name = Column(String(255), nullable=False)
    source_type = Column(String(64), nullable=False)
    original_filename = Column(String(255), nullable=True)
    original_hash = Column(String(128), nullable=True)
    import_actor = Column(String(255), nullable=False)
    import_timestamp = Column(DateTime, default=utcnow, nullable=False)
    schema_version = Column(String(32), default="1.0.0", nullable=False)
    parent_dataset_id = Column(String(128), nullable=True)
    transformation_chain = Column(JSON, nullable=True)

    dataset = relationship("GovernanceDataset", back_populates="provenance")


class QuarantineRecord(TimestampMixin, Base):
    """
    Phase 12: Quarantined invalid records with exact field, value, and reason.
    """
    __tablename__ = "quarantine_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("governance_datasets.id"), nullable=False, index=True)
    version_number = Column(Integer, default=1, nullable=False)
    record_identifier = Column(String(255), nullable=True)
    field_name = Column(String(128), nullable=True)
    original_value = Column(Text, nullable=True)
    error_code = Column(String(64), nullable=False)
    severity = Column(String(32), default="ROW_QUARANTINE", nullable=False)
    message = Column(Text, nullable=False)
    raw_record = Column(JSON, nullable=True)
    quarantined_at = Column(DateTime, default=utcnow, nullable=False)

    dataset = relationship("GovernanceDataset", back_populates="quarantine_records")


class DatasetChange(TimestampMixin, Base):
    """
    Phase 12: Record-level diffs between dataset versions (ADDED, REMOVED, MODIFIED, UNCHANGED).
    """
    __tablename__ = "dataset_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("governance_datasets.id"), nullable=False, index=True)
    base_version = Column(Integer, nullable=False)
    target_version = Column(Integer, nullable=False)
    change_type = Column(String(32), nullable=False)
    record_identifier = Column(String(255), nullable=False)
    field_diffs = Column(JSON, nullable=True)
    detected_at = Column(DateTime, default=utcnow, nullable=False)

    dataset = relationship("GovernanceDataset", back_populates="changes")


class DatasetImpact(TimestampMixin, Base):
    """
    Phase 12: Downstream dependency and stale decision analysis across Phases 4–11.
    """
    __tablename__ = "dataset_impacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("governance_datasets.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    impact_level = Column(String(32), default="LOW", nullable=False)
    affected_engines = Column(JSON, nullable=False)
    affected_runs = Column(JSON, nullable=True)
    requires_recalculation = Column(Boolean, default=False, nullable=False)
    stale_decision_packages = Column(JSON, nullable=True)
    rationale = Column(Text, nullable=False)
    analyzed_at = Column(DateTime, default=utcnow, nullable=False)

    dataset = relationship("GovernanceDataset", back_populates="impacts")


