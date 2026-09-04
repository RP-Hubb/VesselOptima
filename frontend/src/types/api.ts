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
