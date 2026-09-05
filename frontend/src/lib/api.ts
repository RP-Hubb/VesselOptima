/**
 * VesselOptima — Centralized API Client
 *
 * All API access goes through this module.
 * No raw fetch calls scattered in components.
 */

import type {
  RuntimeModeResponse,
  RuntimeStatusResponse,
  HealthResponse,
  ErrorResponse,
  SeriesCatalogItem,
  ForecastResponse,
  CargoRequirementItem,
  FleetFeasibilityResponse,
  FeasibilityEvaluateRequest,
  FeasibilityResultResponse,
  ProcurementProfileItem,
  ProcurementCompareRequest,
  ProcurementCompareResponse,
} from "@/types/api";

function getApiBase(): string {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== "undefined" && window.location.hostname) {
    return `http://${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}

class ApiError extends Error {
  code: string;
  status: number;
  recovery_actions?: string[];

  constructor(status: number, error: ErrorResponse) {
    super(error.message);
    this.name = "ApiError";
    this.code = error.code;
    this.status = status;
    this.recovery_actions = error.recovery_actions;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${getApiBase()}${path}`;

  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    let error: ErrorResponse;
    try {
      error = await response.json();
    } catch {
      error = {
        code: "NETWORK_ERROR",
        message: `Request failed with status ${response.status}`,
      };
    }
    throw new ApiError(response.status, error);
  }

  return response.json();
}

// ── Runtime ─────────────────────────────────────────────────────────

export async function getRuntimeMode(): Promise<RuntimeModeResponse> {
  return request<RuntimeModeResponse>("/v1/runtime/mode");
}

export async function switchRuntimeMode(
  mode: "LIVE" | "OFFLINE_DEMO",
  confirmation: boolean,
  reason?: string
): Promise<RuntimeModeResponse> {
  return request<RuntimeModeResponse>("/v1/runtime/mode", {
    method: "PUT",
    body: JSON.stringify({ mode, confirmation, reason }),
  });
}

export async function getRuntimeStatus(): Promise<RuntimeStatusResponse> {
  return request<RuntimeStatusResponse>("/v1/runtime/status");
}

// ── Health ──────────────────────────────────────────────────────────

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

// ── Forecast ────────────────────────────────────────────────────────

export async function getForecastSeries(): Promise<SeriesCatalogItem[]> {
  return request<SeriesCatalogItem[]>("/v1/forecast/series");
}

export async function getForecast(
  target: string,
  seriesId: string,
  horizonDays: number = 30
): Promise<ForecastResponse> {
  return request<ForecastResponse>(
    `/v1/forecast/${target}/${seriesId}?horizon_days=${horizonDays}`
  );
}

export async function trainForecast(
  target: string,
  seriesId: string,
  horizonDays: number = 30,
  force: boolean = false
): Promise<ForecastResponse> {
  await request<{ status: string }>("/v1/forecast/train", {
    method: "POST",
    body: JSON.stringify({ series_id: seriesId, horizon_days: horizonDays, force }),
  });
  return getForecast(target, seriesId, horizonDays);
}

// ── Feasibility ──────────────────────────────────────────────────────

export async function getCargoRequirements(): Promise<CargoRequirementItem[]> {
  return request<CargoRequirementItem[]>("/v1/feasibility/cargos");
}

export async function getCandidateFleetFeasibility(
  cargoId: number
): Promise<FleetFeasibilityResponse> {
  return request<FleetFeasibilityResponse>(`/v1/feasibility/vessels/${cargoId}`);
}

export async function evaluateFeasibility(
  body: FeasibilityEvaluateRequest
): Promise<FeasibilityResultResponse> {
  return request<FeasibilityResultResponse>("/v1/feasibility/evaluate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ── Procurement ──────────────────────────────────────────────────────

export interface ProcurementProfilesResponse {
  profiles: ProcurementProfileItem[];
  default_profile_id: string;
}

export async function getProcurementProfiles(): Promise<ProcurementProfilesResponse> {
  return request<ProcurementProfilesResponse>("/v1/procurement/config");
}

export async function getProcurementCandidates(
  cargoId: number,
  profileId?: string,
  asOfDate?: string
): Promise<ProcurementCompareResponse> {
  const params = new URLSearchParams();
  if (profileId) params.append("profile_id", profileId);
  if (asOfDate) params.append("as_of_date", asOfDate);
  const query = params.toString() ? `?${params.toString()}` : "";
  return request<ProcurementCompareResponse>(`/v1/procurement/candidates/${cargoId}${query}`);
}

export async function compareProcurementStrategies(
  body: ProcurementCompareRequest
): Promise<ProcurementCompareResponse> {
  return request<ProcurementCompareResponse>("/v1/procurement/compare", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export { ApiError };

