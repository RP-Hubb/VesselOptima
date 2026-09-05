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

