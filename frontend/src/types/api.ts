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

