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
  FleetEmploymentOverview,
  VesselEmploymentStatus,
  VesselTimelineResponse,
  OpportunitiesResponse,
  FleetIdleResponse,
  EmploymentCandidateResponse,
  CandidateMatrixResponse,
  CandidateCompareResponse,
  SolveFleetAssignmentRequest,
  OptimizationResultResponse,
  OptimizationRunSummary,
  CompareRunsResponse,
  ScenarioConfigPayload,
  ScenarioPresetItem,
  ScenarioComparisonResponse,
  SensitivitySweepResponse,
  RobustnessResponse,
  PlanRiskSimulationResponse,
  PlanRiskComparisonResponse,
  RiskRunSummary,
  RiskVariableConfig,
  DecisionResultResponse,
  DecisionRunSummary,
  DecisionPackageResponse,
  DecisionPackageSummary,
  PackageValidationResponse,
  PackageComparisonResponse,
  AuditChainVerificationResponse,
  ReproductionResponse,
  DecisionRecordExportResponse,
  DecisionConfigurationResponse,
  DatasetType,
  DatasetResponse,
  QuarantineItemResponse,
  DatasetDiffResponse,
  DatasetImpactResponse,
  DatasetImportRequest,
  DatasetVersionImportRequest,
  DatasetApprovalRequest,
  DatasetRejectionRequest,
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

// ── Employment & Idle Management (Phase 6) ──────────────────────────

export async function getFleetEmploymentOverview(
  asOfDate?: string
): Promise<FleetEmploymentOverview> {
  const query = asOfDate ? `?as_of_date=${encodeURIComponent(asOfDate)}` : "";
  return request<FleetEmploymentOverview>(`/v1/employment/overview${query}`);
}

export async function getVesselsEmploymentStatus(
  asOfDate?: string
): Promise<VesselEmploymentStatus[]> {
  const query = asOfDate ? `?as_of_date=${encodeURIComponent(asOfDate)}` : "";
  return request<VesselEmploymentStatus[]>(`/v1/employment/vessels${query}`);
}

export async function getVesselTimeline(
  vesselId: number,
  horizonDays: number = 45,
  asOfDate?: string
): Promise<VesselTimelineResponse> {
  const params = new URLSearchParams({ horizon_days: horizonDays.toString() });
  if (asOfDate) params.append("as_of_date", asOfDate);
  return request<VesselTimelineResponse>(`/v1/employment/vessels/${vesselId}/timeline?${params.toString()}`);
}

export async function getEmploymentOpportunities(): Promise<OpportunitiesResponse> {
  return request<OpportunitiesResponse>("/v1/employment/opportunities");
}

export async function getFleetIdleAssessments(
  asOfDate?: string
): Promise<FleetIdleResponse> {
  const query = asOfDate ? `?as_of_date=${encodeURIComponent(asOfDate)}` : "";
  return request<FleetIdleResponse>(`/v1/employment/idle${query}`);
}

export async function evaluateEmploymentCandidate(body: {
  vessel_id: number;
  cargo_id: number;
  as_of_date?: string;
  employment_type?: string;
  procurement_profile_id?: string;
  persist?: boolean;
}): Promise<EmploymentCandidateResponse> {
  return request<EmploymentCandidateResponse>("/v1/employment/evaluate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getEmploymentCandidates(body: {
  vessel_id?: number;
  cargo_id?: number;
  ready_only?: boolean;
  as_of_date?: string;
  persist?: boolean;
}): Promise<CandidateMatrixResponse> {
  return request<CandidateMatrixResponse>("/v1/employment/candidates", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function compareEmploymentCandidates(body: {
  vessel_id?: number;
  cargo_id?: number;
  as_of_date?: string;
}): Promise<CandidateCompareResponse> {
  return request<CandidateCompareResponse>("/v1/employment/compare", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ── Phase 7: Optimization Engine API ─────────────────────────────────

export async function solveFleetOptimization(
  body: SolveFleetAssignmentRequest
): Promise<OptimizationResultResponse> {
  return request<OptimizationResultResponse>("/v1/optimization/solve", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getOptimizationRuns(
  limit: number = 50
): Promise<OptimizationRunSummary[]> {
  return request<OptimizationRunSummary[]>(`/v1/optimization/runs?limit=${limit}`);
}

export async function getOptimizationRun(
  runId: string
): Promise<OptimizationResultResponse> {
  return request<OptimizationResultResponse>(`/v1/optimization/runs/${encodeURIComponent(runId)}`);
}

export async function compareOptimizationRuns(body: {
  run_id_a: string;
  run_id_b: string;
}): Promise<CompareRunsResponse> {
  return request<CompareRunsResponse>("/v1/optimization/compare", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ── Phase 8: Scenarios & Sensitivity API ─────────────────────────────

export async function getScenarioPresets(): Promise<ScenarioPresetItem[]> {
  return request<ScenarioPresetItem[]>("/v1/scenarios/presets");
}

export async function runScenario(
  body: ScenarioConfigPayload,
  persist: boolean = true
): Promise<ScenarioComparisonResponse> {
  return request<ScenarioComparisonResponse>(`/v1/scenarios/run?persist=${persist}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function runBatchScenarios(
  body: { scenarios: ScenarioConfigPayload[] },
  persist: boolean = true
): Promise<{ total_scenarios_executed: number; comparisons: ScenarioComparisonResponse[] }> {
  return request<{ total_scenarios_executed: number; comparisons: ScenarioComparisonResponse[] }>(
    `/v1/scenarios/batch?persist=${persist}`,
    {
      method: "POST",
      body: JSON.stringify(body),
    }
  );
}

export async function runSensitivitySweep(
  body: {
    parameter_name: string;
    sweep_values: number[];
    base_config?: ScenarioConfigPayload;
  },
  persist: boolean = true
): Promise<SensitivitySweepResponse> {
  return request<SensitivitySweepResponse>(`/v1/scenarios/sensitivity?persist=${persist}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getEnsembleRobustness(): Promise<RobustnessResponse> {
  return request<RobustnessResponse>("/v1/scenarios/robustness");
}

// ── Phase 9: Risk Intelligence & Uncertainty API ─────────────────────

export async function getRiskConfigDefaults(): Promise<Record<string, any>> {
  return request<Record<string, any>>("/v1/risk/config/defaults");
}

export async function simulatePlanRisk(body: {
  optimization_run_id?: string;
  scenario_run_id?: string;
  simulation_count?: number;
  random_seed?: number;
  variables?: RiskVariableConfig[];
  correlations?: any[];
  include_demurrage?: boolean;
  demurrage_daily_rate?: number;
}): Promise<PlanRiskSimulationResponse> {
  return request<PlanRiskSimulationResponse>("/v1/risk/simulate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function comparePlanRisk(body: {
  optimization_run_id_a?: string;
  optimization_run_id_b?: string;
  is_demo_flip?: boolean;
}): Promise<PlanRiskComparisonResponse> {
  return request<PlanRiskComparisonResponse>("/v1/risk/compare", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getRiskFlipDemo(): Promise<PlanRiskComparisonResponse> {
  return request<PlanRiskComparisonResponse>("/v1/risk/flip-demo");
}

export async function getRiskRuns(limit: number = 20): Promise<RiskRunSummary[]> {
  return request<RiskRunSummary[]>(`/v1/risk/runs?limit=${limit}`);
}

export async function getRiskRunDetails(runId: string): Promise<Record<string, any>> {
  return request<Record<string, any>>(`/v1/risk/runs/${runId}`);
}

// ── Phase 10: Decision Intelligence ─────────────────────────────────

export async function getDecisionDemo(scenarioType: string = "BASELINE"): Promise<DecisionResultResponse> {
  return request<DecisionResultResponse>(`/v1/decision/demo/${scenarioType}`);
}

export async function evaluateDecision(body: {
  optimization_run_id: string;
  scenario_run_id?: string;
  risk_run_id?: string;
  strategy_flip_identified?: boolean;
  thresholds?: Record<string, any>;
}): Promise<DecisionResultResponse> {
  return request<DecisionResultResponse>("/v1/decision/evaluate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getDecisionRuns(limit: number = 20): Promise<DecisionRunSummary[]> {
  return request<DecisionRunSummary[]>(`/v1/decision/runs?limit=${limit}`);
}

export async function getDecisionRun(runId: string): Promise<DecisionResultResponse> {
  return request<DecisionResultResponse>(`/v1/decision/runs/${runId}`);
}

export async function getDecisionThresholds(): Promise<Record<string, any>> {
  return request<Record<string, any>>("/v1/decision/thresholds");
}

// ── Phase 11: Decision Governance & Institutional Control ────────────

export async function createGovernancePackage(body: {
  decision_run_id: string;
  title?: string;
  description?: string;
  created_by?: string;
  created_by_role?: string;
}): Promise<DecisionPackageResponse> {
  return request<DecisionPackageResponse>("/v1/governance/packages", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listGovernancePackages(limit: number = 50): Promise<DecisionPackageSummary[]> {
  return request<DecisionPackageSummary[]>(`/v1/governance/packages?limit=${limit}`);
}

export async function getGovernancePackage(packageId: string): Promise<DecisionPackageResponse> {
  return request<DecisionPackageResponse>(`/v1/governance/packages/${packageId}`);
}

export async function validateGovernancePackage(packageId: string): Promise<PackageValidationResponse> {
  return request<PackageValidationResponse>(`/v1/governance/packages/${packageId}/validate`, {
    method: "POST",
  });
}

export async function submitGovernancePackage(
  packageId: string,
  body: { actor: string; actor_role: string; notes?: string }
): Promise<DecisionPackageResponse> {
  return request<DecisionPackageResponse>(`/v1/governance/packages/${packageId}/submit`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function reviewGovernancePackage(
  packageId: string,
  body: { actor: string; actor_role: string; notes?: string }
): Promise<DecisionPackageResponse> {
  return request<DecisionPackageResponse>(`/v1/governance/packages/${packageId}/review`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function approveGovernancePackage(
  packageId: string,
  body: { actor: string; actor_role: string; notes?: string }
): Promise<DecisionPackageResponse> {
  return request<DecisionPackageResponse>(`/v1/governance/packages/${packageId}/approve`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function rejectGovernancePackage(
  packageId: string,
  body: { actor: string; actor_role: string; reason: string }
): Promise<DecisionPackageResponse> {
  return request<DecisionPackageResponse>(`/v1/governance/packages/${packageId}/reject`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function recordGovernanceOverride(
  packageId: string,
  body: {
    override_recommendation: string;
    reason: string;
    actor: string;
    actor_role?: string;
    supporting_note?: string;
    approval_actor?: string;
  }
): Promise<DecisionPackageResponse> {
  return request<DecisionPackageResponse>(`/v1/governance/packages/${packageId}/override`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function createGovernancePackageVersion(
  packageId: string,
  body: { updated_evidence: Record<string, any>; change_summary: string; actor?: string }
): Promise<DecisionPackageResponse> {
  return request<DecisionPackageResponse>(`/v1/governance/packages/${packageId}/versions`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function verifyGovernanceAuditTrail(packageId: string): Promise<AuditChainVerificationResponse> {
  return request<AuditChainVerificationResponse>(`/v1/governance/packages/${packageId}/verify`, {
    method: "POST",
  });
}

export async function reproduceGovernanceDecision(packageId: string): Promise<ReproductionResponse> {
  return request<ReproductionResponse>(`/v1/governance/packages/${packageId}/reproduce`, {
    method: "POST",
  });
}

export async function compareGovernancePackages(body: {
  base_package_id: string;
  target_package_id: string;
}): Promise<PackageComparisonResponse> {
  return request<PackageComparisonResponse>("/v1/governance/compare", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function exportGovernanceDecisionRecord(packageId: string): Promise<DecisionRecordExportResponse> {
  return request<DecisionRecordExportResponse>(`/v1/governance/packages/${packageId}/export`);
}

export async function getGovernanceActiveConfiguration(): Promise<DecisionConfigurationResponse> {
  return request<DecisionConfigurationResponse>("/v1/governance/configurations");
}

export async function getGovernanceDemoPackage(scenarioType: string = "BASELINE"): Promise<DecisionPackageResponse> {
  return request<DecisionPackageResponse>(`/v1/governance/demo/${scenarioType}`);
}

// ── Phase 12: Maritime Data Integration & Quality Governance ─────────

export async function importDataset(body: DatasetImportRequest): Promise<DatasetResponse> {
  return request<DatasetResponse>("/v1/data/import", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getDatasets(
  datasetType?: DatasetType | string,
  limit: number = 50
): Promise<DatasetResponse[]> {
  const params = new URLSearchParams();
  if (datasetType) params.append("dataset_type", datasetType);
  if (limit) params.append("limit", limit.toString());
  const qs = params.toString() ? `?${params.toString()}` : "";
  return request<DatasetResponse[]>(`/v1/data/datasets${qs}`);
}

export async function getDataset(datasetId: string): Promise<DatasetResponse> {
  return request<DatasetResponse>(`/v1/data/datasets/${datasetId}`);
}

export async function importDatasetVersion(
  datasetId: string,
  body: DatasetVersionImportRequest
): Promise<DatasetResponse> {
  return request<DatasetResponse>(`/v1/data/datasets/${datasetId}/version`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function approveDataset(
  datasetId: string,
  body: DatasetApprovalRequest
): Promise<DatasetResponse> {
  return request<DatasetResponse>(`/v1/data/datasets/${datasetId}/approve`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function rejectDataset(
  datasetId: string,
  body: DatasetRejectionRequest
): Promise<DatasetResponse> {
  return request<DatasetResponse>(`/v1/data/datasets/${datasetId}/reject`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getDatasetQuarantine(
  datasetId: string
): Promise<QuarantineItemResponse[]> {
  return request<QuarantineItemResponse[]>(`/v1/data/datasets/${datasetId}/quarantine`);
}

export async function getDatasetDiff(
  datasetId: string,
  baseVersion?: number,
  currentVersion?: number
): Promise<DatasetDiffResponse> {
  const params = new URLSearchParams();
  if (baseVersion !== undefined) params.append("base_version", baseVersion.toString());
  if (currentVersion !== undefined) params.append("current_version", currentVersion.toString());
  const qs = params.toString() ? `?${params.toString()}` : "";
  return request<DatasetDiffResponse>(`/v1/data/datasets/${datasetId}/diff${qs}`);
}

export async function getDatasetImpact(
  datasetId: string,
  versionNumber?: number
): Promise<DatasetImpactResponse> {
  const params = new URLSearchParams();
  if (versionNumber !== undefined) params.append("version_number", versionNumber.toString());
  const qs = params.toString() ? `?${params.toString()}` : "";
  return request<DatasetImpactResponse>(`/v1/data/datasets/${datasetId}/impact${qs}`);
}

export async function seedDataDemo(scenario: string = "CANONICAL"): Promise<DatasetResponse> {
  return request<DatasetResponse>(`/v1/data/demo/seed?scenario=${scenario}`);
}

export { ApiError };


