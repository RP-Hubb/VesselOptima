/**
 * VesselOptima — TypeScript API Types
 *
 * Aligned with backend Pydantic schemas.
 * No `any` types.
 */

export type RuntimeMode = "LIVE" | "OFFLINE_DEMO";

export interface RuntimeModeResponse {
  mode: RuntimeMode;
  mode_session_id: string;
  selected_at: string;
  data_context_id: string | null;
  offline_package_id: string | null;
}

export interface SourceHealth {
  name: string;
  status: "healthy" | "stale" | "unavailable" | "unknown";
  last_success: string | null;
  error: string | null;
  recovery_action: string | null;
}

export interface RuntimeStatusResponse {
  mode: RuntimeMode;
  mode_session_id: string | null;
  app_status: "ready" | "degraded" | "error";
  database_status: "healthy" | "unhealthy";
  sources: SourceHealth[];
  offline_package_id: string | null;
  offline_package_coverage: string | null;
  model_artifacts_status: string | null;
  timestamp: string;
}

export interface HealthResponse {
  status: "healthy" | "degraded" | "unhealthy";
  database: string;
  runtime_mode: string;
  timestamp: string;
  version: string;
  detail: string | null;
}

export interface ErrorResponse {
  code: string;
  message: string;
  details?: { field: string | null; message: string }[];
  trace_id?: string;
  recovery_actions?: string[];
}

// ── Forecast Types ───────────────────────────────────────────────────

export interface SeriesCatalogItem {
  target: string;
  series_id: string;
  name: string;
  unit: string;
  frequency: string;
  provenance: string;
  is_demo: boolean;
  description: string;
}

export interface HistoricalPoint {
  date: string;
  value: number;
}

export interface ForecastPoint {
  date: string;
  value: number;
  lower_80: number;
  upper_80: number;
  lower_95: number;
  upper_95: number;
}

export interface ModelValidationMetrics {
  mae: number;
  rmse: number;
  smape: number;
  directional_accuracy: number;
  total_eval_points: number;
}

export interface ModelInfo {
  selected_model: string;
  model_version: string;
  validation_method: string;
  artifact_hash: string | null;
}

export interface ForecastResponse {
  target: string;
  series_id: string;
  series_name: string;
  unit: string;
  frequency: string;
  provenance: string;
  is_demo: boolean;
  historical_coverage: {
    start_date: string;
    end_date: string;
    total_observations: number;
  };
  horizon_days: number;
  forecast_origin_date: string;
  historical_points: HistoricalPoint[];
  forecast_points: ForecastPoint[];
  model_info: ModelInfo;
  validation_metrics: ModelValidationMetrics;
  candidate_metrics: Record<string, {
    mae: number;
    rmse: number;
    smape: number;
    directional_accuracy: number;
  }>;
  generated_at: string;
}

export interface ForecastTrainRequest {
  series_id: string;
  horizon_days?: number;
  force?: boolean;
}

// ── Feasibility Types ─────────────────────────────────────────────────

export interface CargoRequirementItem {
  id: number;
  commodity: string;
  volume_mt: number;
  origin_port_id: number;
  destination_port_id: number;
  origin_port_name?: string | null;
  destination_port_name?: string | null;
  loading_window_start: string;
  loading_window_end: string;
  delivery_deadline: string;
  tolerance_pct: number;
}

export interface FleetVesselItem {
  vessel_id: number;
  vessel_name: string;
  vessel_class: string;
  cargo_capacity: number;
  draft: number;
  loa: number;
  beam: number;
  is_feasible: boolean;
  primary_reason_code: string | null;
  primary_reason_description: string | null;
  failed_checks: string[];
  warnings_count: number;
}

export interface FleetFeasibilityResponse {
  cargo_id: number;
  cargo_name: string;
  total_vessels: number;
  feasible_count: number;
  infeasible_count: number;
  vessels: FleetVesselItem[];
  provenance: Record<string, unknown>;
  evaluated_at: string;
}

export interface FeasibilityEvaluateRequest {
  cargo_id: number;
  vessel_id: number;
  route_id?: number | null;
  persist?: boolean;
}

export interface CheckEvidenceDetail {
  passed: boolean;
  required?: number | string | null;
  permitted?: number | string | null;
  actual?: number | string | null;
  max?: number | string | null;
  status?: string;
  reason?: string | null;
  [key: string]: unknown;
}

export interface FeasibilityResultResponse {
  is_feasible: boolean;
  cargo_id: number | null;
  cargo_name: string | null;
  vessel_id: number | null;
  vessel_name: string | null;
  vessel_class: string | null;
  route_id: number | null;
  route_name: string | null;
  origin_port: string | null;
  destination_port: string | null;
  primary_reason_code: string | null;
  primary_reason_description: string | null;
  reason_codes: string[];
  failed_checks: string[];
  checks: Record<string, CheckEvidenceDetail>;
  warnings: string[];
  timing: {
    origin_laycan_start?: string;
    origin_laycan_end?: string;
    delivery_deadline?: string;
    positioning_days?: number;
    estimated_arrival_origin?: string;
    loading_days?: number;
    sailing_days?: number;
    discharge_days?: number;
    total_voyage_days?: number;
    estimated_delivery_destination?: string;
    [key: string]: unknown;
  };
  evidence: Record<string, unknown>;
  provenance: {
    package_id?: string;
    package_version?: string;
    data_type?: string;
    notes?: string;
    [key: string]: unknown;
  };
  evaluated_at: string;
}

// ── Procurement ──────────────────────────────────────────────────────

export interface ProcurementProfileItem {
  profile_id: string;
  name: string;
  tender_preparation_days: number;
  bid_submission_days: number;
  technical_evaluation_days: number;
  commercial_evaluation_days: number;
  approval_days: number;
  award_days: number;
  minimum_lead_time_days: number;
  description: string;
  data_classification?: string;
}

export interface StrategyEvaluationItem {
  strategy_type: string;
  strategy_name: string;
  description?: string | null;
  status: "FEASIBLE" | "INFEASIBLE";
  primary_reason_code?: string | null;
  primary_reason_description?: string | null;
  timing_signal?: "WINDOW_OPEN" | "WINDOW_CLOSING" | "IMMEDIATE_PROCURE" | "LEAD_TIME_EXCEEDED" | "DEADLINE_MISSED" | "WINDOW_INVALID" | null;
  contract_duration_days?: number | null;
  voyage_count?: number | null;
  market_exposure?: string | null;
  commitment_level?: string | null;
  timing?: {
    origin_laycan_start?: string;
    origin_laycan_end?: string;
    delivery_deadline?: string;
    as_of_date?: string;
    total_lead_time_days?: number;
    earliest_procurement_date?: string;
    procurement_completion_date?: string;
    latest_safe_procurement_date?: string;
    remaining_decision_window_days?: number;
    timing_signal?: string;
    lead_time_stages?: Record<string, number>;
    [key: string]: unknown;
  } | null;
  forecast_evidence?: {
    forecast_target?: string;
    forecast_series_id?: string;
    current_rate?: number;
    forecast_horizon_days?: number;
    forecast_rate_mean?: number;
    lower_bound_95?: number;
    upper_bound_95?: number;
    interval_spread_ratio?: number;
    trajectory_slope?: string;
    uncertainty_level?: string;
    evidence_note?: string;
    provenance?: Record<string, unknown>;
    [key: string]: unknown;
  } | null;
  cost_summary?: {
    estimated_freight_cost?: number;
    estimated_bunker_cost?: number;
    estimated_port_dues?: number;
    procurement_administration_fee?: number;
    expected_total_cost?: number;
    discount_factor?: number;
    currency?: string;
    note?: string;
    [key: string]: unknown;
  } | null;
  feasibility_summary?: {
    candidate_fleet_size?: number;
    feasible_vessels_count?: number;
    feasible_vessel_ids?: number[];
    feasible_vessel_names?: string[];
    rejection_summary?: Record<string, number>;
    [key: string]: unknown;
  } | null;
  candidate_metadata?: {
    candidate_status?: string;
    optimization_ready?: boolean;
    contract_structure?: string;
    audit_trail?: Record<string, unknown>;
    [key: string]: unknown;
  } | null;
  provenance?: {
    package_id?: string;
    package_version?: string;
    data_type?: string;
    air_gap_verified?: boolean;
    [key: string]: unknown;
  } | null;
}

export interface ProcurementCompareRequest {
  cargo_id: number;
  profile_id?: string | null;
  strategy_types?: string[] | null;
  as_of_date?: string | null;
  custom_stages?: Record<string, number> | null;
  persist?: boolean;
}

export interface ProcurementCompareResponse {
  cargo_id: number;
  commodity: string;
  volume_mt: number;
  origin_port: string;
  destination_port: string;
  laycan_start: string;
  laycan_end: string;
  delivery_deadline: string;
  as_of_date: string;
  procurement_profile: Record<string, unknown>;
  procurement_lead_time_days: number;
  strategies_evaluated_count: number;
  feasible_strategies_count: number;
  infeasible_strategies_count: number;
  strategies: StrategyEvaluationItem[];
  advisory_note: string;
  evaluated_at: string;
}

// ── Employment & Idle Management (Phase 6) ──────────────────────────

export interface FleetEmploymentOverview {
  as_of_date: string;
  total_vessels: number;
  available_vessels: number;
  committed_vessels: number;
  idle_vessels: number;
  alternative_candidates_generated: number;
  provenance: Record<string, unknown>;
}

export interface CommitmentDetail {
  id: number;
  description: string;
  commitment_start: string;
  commitment_end?: string | null;
}

export interface VesselEmploymentStatus {
  vessel_id: number;
  vessel_name: string;
  vessel_class: string;
  current_location_port_id: number;
  current_location_name: string;
  available_at: string;
  has_active_commitment: boolean;
  active_commitment?: CommitmentDetail | null;
  next_commitment?: CommitmentDetail | null;
}

export interface TimelineEvent {
  event_type: "AVAILABLE" | "COMMITTED" | "IDLE" | string;
  title: string;
  start_time: string;
  end_time: string;
  color: string;
  details: string;
}

export interface VesselTimelineResponse {
  vessel_id: number;
  vessel_name: string;
  vessel_class: string;
  as_of_date: string;
  horizon_end: string;
  events: TimelineEvent[];
}

export interface EmploymentOpportunity {
  opportunity_id: string;
  cargo_id: number;
  commodity: string;
  volume_mt: number;
  origin_port_id: number;
  origin_port_name: string;
  destination_port_id: number;
  destination_port_name: string;
  laycan_start: string;
  laycan_end: string;
  delivery_deadline: string;
  tolerance_pct: number;
  status: string;
}

export interface OpportunitiesResponse {
  opportunities: EmploymentOpportunity[];
  total_count: number;
}

export interface IdleAssessmentItem {
  vessel_id: number;
  vessel_name: string;
  vessel_class: string;
  as_of_date: string;
  is_idle: boolean;
  idle_days: number;
  window_start: string;
  window_end?: string | null;
  daily_idle_rate: number;
  idle_cost: number;
  cost_source: string;
  reason_code: string;
  reason_description: string;
  active_commitment?: Record<string, unknown> | null;
  next_commitment?: Record<string, unknown> | null;
  provenance: Record<string, unknown>;
}

export interface FleetIdleResponse {
  as_of_date: string;
  total_vessels_assessed: number;
  idle_vessels_count: number;
  active_vessels_count: number;
  total_idle_days: number;
  total_idle_cost: number;
  assessments: IdleAssessmentItem[];
  provenance: Record<string, unknown>;
}

export interface EmploymentCandidateResponse {
  candidate_id: string;
  vessel_id: number;
  vessel_name: string;
  vessel_class: string;
  cargo_id: number;
  cargo_name: string;
  employment_type: string;
  origin_port_id: number;
  origin_port_name: string;
  destination_port_id: number;
  destination_port_name: string;
  status: "FEASIBLE" | "INFEASIBLE";
  optimization_status: "READY_FOR_OPTIMIZATION" | "REJECTED";
  primary_reason_code: string;
  primary_reason_description: string;
  failed_reasons: string[];
  ballast: {
    ballast_required: boolean;
    ballast_distance_nm: number;
    ballast_speed_knots: number;
    ballast_days: number;
    ballast_departure: string;
    ballast_arrival: string;
    arrival_at_origin?: string;
    bunker_consumption_vlsfo_mt: number;
    distance_source: string;
    data_source: string;
    speed_source: string;
    assumption_flag: boolean;
    provenance_fallback: boolean;
    notes?: string;
    [key: string]: unknown;
  };
  feasibility: {
    is_feasible: boolean;
    primary_reason_code: string | null;
    failed_checks: string[];
    checks: Record<string, unknown>;
    [key: string]: unknown;
  };
  procurement: {
    profile_id: string;
    lead_time_days: number;
    timing_signal?: string | null;
    remaining_decision_window_days?: number | null;
    is_timing_feasible: boolean;
    [key: string]: unknown;
  };
  timeline: {
    is_timeline_feasible: boolean;
    primary_reason_code: string;
    failed_checks: string[];
    reason_codes: string[];
    conflicts?: Array<{
      conflict_id?: number;
      conflicting_commitment_id?: number;
      description: string;
      conflict_start: string;
      commitment_start?: string;
      conflict_end?: string | null;
      commitment_end?: string | null;
      candidate_completion: string;
      candidate_discharge_end?: string;
      overlap_days: number;
    }>;
    timing_milestones: Record<string, string | null>;
    duration_breakdown: Record<string, number>;
    warnings: string[];
    [key: string]: unknown;
  };
  economics: {
    expected_revenue?: number | null;
    expected_revenue_usd?: number | null;
    gross_contribution?: number | null;
    gross_contribution_usd?: number | null;
    total_employment_cost: number;
    total_voyage_costs_usd: number;
    utilization_ratio_pct: number;
    currency: string;
    revenue_source: string;
    cost_breakdown: Record<string, number>;
    operational_breakdown: Record<string, number>;
    data_provenance: Record<string, string>;
    [key: string]: unknown;
  };
  provenance: Record<string, unknown>;
}

export interface CandidateMatrixResponse {
  as_of_date: string;
  total_evaluated: number;
  feasible_count: number;
  infeasible_count: number;
  returned_count: number;
  candidates: EmploymentCandidateResponse[];
  governing_boundary: string;
  provenance: Record<string, unknown>;
}

export interface CandidateCompareResponse {
  comparison_type: string;
  filter_vessel_id?: number | null;
  filter_cargo_id?: number | null;
  as_of_date: string;
  candidate_count: number;
  candidates: EmploymentCandidateResponse[];
  advisory_note: string;
  provenance: Record<string, unknown>;
}


// ── Phase 7: Optimization Engine Types ───────────────────────────────

export interface SolveFleetAssignmentRequest {
  scenario?: string | null;
  as_of_date?: string | null;
  vessel_id?: number | null;
  cargo_id?: number | null;
  alpha_idle_weight?: number;
  beta_ballast_penalty?: number;
  default_unserved_penalty?: number;
  cargo_penalties?: Record<number, number> | null;
  time_limit_seconds?: number | null;
  mip_gap?: number;
  persist?: boolean;
}

export interface ObjectiveDecomposition {
  total_gross_revenue: number;
  total_voyage_cost: number;
  total_net_contribution: number;
  total_avoided_idle_cost: number;
  total_ballast_penalty: number;
  total_unserved_penalty: number;
  global_objective_value: number;
}

export interface AssignmentItem {
  candidate_id: string;
  vessel_id: number;
  vessel_name: string;
  cargo_id: number | null;
  cargo_name: string;
  is_selected: boolean;
  selection_status: "SELECTED" | "MODEL_REJECTED" | "INFEASIBLE_UPSTREAM" | "UNASSIGNED" | string;
  start_time: string | null;
  end_time: string | null;
  expected_revenue: number;
  voyage_cost: number;
  gross_contribution: number;
  idle_days_saved: number;
  avoided_idle_cost: number;
  ballast_distance_nm: number;
  ballast_days: number;
  voyage_days: number;
  trade_off_reason_code: string;
  trade_off_explanation: string;
  assignment_metadata?: Record<string, unknown> | null;
}

export interface UnassignedCargoItem {
  cargo_id: number;
  cargo_name: string;
  unserved_penalty: number;
  reason_code: string;
  reason_explanation: string;
}

export interface OptimizationResultResponse {
  run_id: string;
  status: "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "UNBOUNDED" | "TIME_LIMIT" | "SOLVER_ERROR" | "EMPTY_MODEL" | string;
  objective_value: number;
  decomposition: ObjectiveDecomposition;
  selected_assignments: AssignmentItem[];
  rejected_opportunities: AssignmentItem[];
  unassigned_cargos: UnassignedCargoItem[];
  vessel_utilization: {
    total_vessels: number;
    assigned_vessels: number;
    idle_vessels: number;
    utilization_pct: number;
    total_voyage_days: number;
    total_ballast_days: number;
    assigned_vessel_ids?: number[];
    [key: string]: unknown;
  };
  solver_metadata: Record<string, unknown>;
  constraint_summary: {
    total_constraints: number;
    breakdown?: Record<string, number>;
    [key: string]: unknown;
  };
  audit_trail: Array<{
    timestamp: string;
    event: string;
    [key: string]: unknown;
  }>;
  solve_time_seconds: number;
  created_at: string;
}

export interface OptimizationRunSummary {
  run_id: string;
  status: string;
  objective_value: number | null;
  total_revenue: number | null;
  total_cost: number | null;
  total_contribution: number | null;
  avoided_idle_cost: number | null;
  solver_name: string | null;
  solve_time_seconds: number | null;
  result_summary: Record<string, unknown> | null;
  created_at: string | null;
}

export interface CompareRunsResponse {
  run_a: {
    run_id: string;
    status: string;
    objective_value: number;
    total_revenue: number;
    total_cost: number;
    total_contribution: number;
    assignments_count: number;
  };
  run_b: {
    run_id: string;
    status: string;
    objective_value: number;
    total_revenue: number;
    total_cost: number;
    total_contribution: number;
    assignments_count: number;
  };
  comparison: {
    objective_delta: number;
    pct_improvement: number;
    superior_run: string;
  };
}


