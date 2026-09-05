"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import {
  getFleetEmploymentOverview,
  getVesselsEmploymentStatus,
  getVesselTimeline,
  getEmploymentOpportunities,
  getFleetIdleAssessments,
  getEmploymentCandidates,
  compareEmploymentCandidates,
  evaluateEmploymentCandidate,
} from "@/lib/api";
import type {
  FleetEmploymentOverview,
  VesselEmploymentStatus,
  VesselTimelineResponse,
  OpportunitiesResponse,
  FleetIdleResponse,
  EmploymentCandidateResponse,
  CandidateMatrixResponse,
  CandidateCompareResponse,
  EmploymentOpportunity,
  IdleAssessmentItem,
} from "@/types/api";

const DEFAULT_AS_OF_DATE = "2026-09-01";

interface DemoPreset {
  id: string;
  name: string;
  badge: string;
  vesselId: number;
  cargoId: number;
  description: string;
}

const PRESETS: DemoPreset[] = [
  {
    id: "CASE_A",
    name: "Case A: Feasible Alternative Repositioning",
    badge: "FEASIBLE",
    vesselId: 1,
    cargoId: 2,
    description:
      "Panamax Vessel 1 available at Singapore repositioning to Samarinda for 70k MT coal cargo to Paradip. Feasible with positive contribution.",
  },
  {
    id: "CASE_B",
    name: "Case B: Confirmed Commitment Overlap",
    badge: "CONFLICT",
    vesselId: 1,
    cargoId: 4,
    description:
      "Vessel 1 evaluated against Newcastle-Visakhapatnam voyage. Long voyage completes in October, violating confirmed coastal shuttle commitment on Sept 24.",
  },
  {
    id: "CASE_C",
    name: "Case C: Ballast Exceeds Laycan Window",
    badge: "BALLAST REJECT",
    vesselId: 5,
    cargoId: 2,
    description:
      "Vessel 5 available Sept 14 at Singapore attempting to reach loading port with tight laycan. Ballast transit exceeds laycan cancellation deadline.",
  },
  {
    id: "CASE_D",
    name: "Case D: Commercial Procurement Timing Rejection",
    badge: "LEAD TIME REJECT",
    vesselId: 1,
    cargoId: 3,
    description:
      "Evaluation date too close to laycan start; required administrative procurement lead-time exceeds remaining window.",
  },
  {
    id: "CASE_E",
    name: "Case E: Physical Feasibility Rejection",
    badge: "PHYSICAL REJECT",
    vesselId: 1,
    cargoId: 1,
    description:
      "Panamax Vessel 1 (34.5k DWT) evaluated against 160k MT Capesize cargo. Volume and draft exceed vessel physical capacity.",
  },
  {
    id: "CASE_F",
    name: "Case F: Multi-Cargo Alternative Fleet Evaluation",
    badge: "MULTI-CARGO",
    vesselId: 1,
    cargoId: 2,
    description:
      "Independent multi-cargo candidate evaluation across all canonical requirements for trade-off exploration.",
  },
];

export default function EmploymentPage() {
  const [asOfDate, setAsOfDate] = useState<string>(DEFAULT_AS_OF_DATE);
  const [activeTab, setActiveTab] = useState<"MATRIX" | "TIMELINE" | "IDLE" | "COMPARE">("MATRIX");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Overview data
  const [overview, setOverview] = useState<FleetEmploymentOverview | null>(null);
  const [vessels, setVessels] = useState<VesselEmploymentStatus[]>([]);
  const [opportunities, setOpportunities] = useState<EmploymentOpportunity[]>([]);
  const [idleData, setIdleData] = useState<FleetIdleResponse | null>(null);

  // Filter & Selection states
  const [selectedVesselId, setSelectedVesselId] = useState<number>(1);
  const [selectedCargoId, setSelectedCargoId] = useState<number | null>(null);
  const [filterReadyOnly, setFilterReadyOnly] = useState<boolean>(false);
  const [activePreset, setActivePreset] = useState<string>("CASE_A");

  // Candidates & Timeline
  const [candidatesMatrix, setCandidatesMatrix] = useState<CandidateMatrixResponse | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<EmploymentCandidateResponse | null>(null);
  const [timelineData, setTimelineData] = useState<VesselTimelineResponse | null>(null);
  const [compareData, setCompareData] = useState<CandidateCompareResponse | null>(null);

  // Load baseline data on mount or date change
  const loadBaselineData = useCallback(() => {
    setLoading(true);
    setError(null);

    Promise.all([
      getFleetEmploymentOverview(asOfDate),
      getVesselsEmploymentStatus(asOfDate),
      getEmploymentOpportunities(),
      getFleetIdleAssessments(asOfDate),
    ])
      .then(([ov, vList, oppRes, idleRes]) => {
        setOverview(ov);
        setVessels(vList);
        setOpportunities(oppRes.opportunities);
        setIdleData(idleRes);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to load employment baseline data");
        setLoading(false);
      });
  }, [asOfDate]);

  useEffect(() => {
    loadBaselineData();
  }, [loadBaselineData]);

  // Load candidate matrix
  const loadCandidates = useCallback(() => {
    setLoading(true);
    getEmploymentCandidates({
      vessel_id: selectedVesselId || undefined,
      cargo_id: selectedCargoId || undefined,
      ready_only: filterReadyOnly,
      as_of_date: asOfDate,
      persist: false,
    })
      .then((data) => {
        setCandidatesMatrix(data);
        if (data.candidates.length > 0) {
          setSelectedCandidate(data.candidates[0]);
        }
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to generate candidates");
        setLoading(false);
      });
  }, [selectedVesselId, selectedCargoId, filterReadyOnly, asOfDate]);

  useEffect(() => {
    loadCandidates();
  }, [loadCandidates]);

  // Load vessel timeline
  useEffect(() => {
    if (!selectedVesselId) return;
    getVesselTimeline(selectedVesselId, 45, asOfDate)
      .then((tl) => setTimelineData(tl))
      .catch(() => setTimelineData(null));
  }, [selectedVesselId, asOfDate]);

  // Load comparison data
  useEffect(() => {
    if (!selectedVesselId) return;
    compareEmploymentCandidates({
      vessel_id: selectedVesselId,
      as_of_date: asOfDate,
    })
      .then((comp) => setCompareData(comp))
      .catch(() => setCompareData(null));
  }, [selectedVesselId, asOfDate]);

  // Handle Preset Selection
  const applyPreset = (preset: DemoPreset) => {
    setActivePreset(preset.id);
    setSelectedVesselId(preset.vesselId);
    setSelectedCargoId(preset.cargoId);
    if (preset.id === "CASE_B") {
      setActiveTab("TIMELINE");
    } else {
      setActiveTab("MATRIX");
    }
  };

  return (
    <div style={{ padding: "var(--space-4)", maxWidth: "1600px", margin: "0 auto", color: "var(--text)" }}>
      {/* ── 1. Top Header & Architectural Boundary ──────────────────── */}
      <header
        style={{
          borderBottom: "1px solid var(--border)",
          paddingBottom: "var(--space-3)",
          marginBottom: "var(--space-4)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "var(--space-3)" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "4px" }}>
              <span style={{ fontFamily: "monospace", fontSize: "0.75rem", color: "var(--primary)", background: "rgba(56, 189, 248, 0.1)", padding: "2px 6px", borderRadius: "4px", border: "1px solid rgba(56, 189, 248, 0.3)" }}>
                PHASE 6 // FLEET REPOSITIONING & IDLE ENGINE
              </span>
              <span style={{ fontFamily: "monospace", fontSize: "0.75rem", color: "#10b981", background: "rgba(16, 185, 129, 0.1)", padding: "2px 6px", borderRadius: "4px", border: "1px solid rgba(16, 185, 129, 0.3)" }}>
                AIR-GAP OFFLINE DEMO
              </span>
            </div>
            <h1 style={{ margin: 0, fontSize: "1.5rem", fontWeight: 700, letterSpacing: "-0.02em" }}>
              Idle Management & Alternative Employment
            </h1>
            <p style={{ margin: "4px 0 0 0", color: "var(--muted)", fontSize: "0.875rem" }}>
              Fleet availability windows, ballast repositioning, schedule commitment conflict tracking, and transparent contribution economics.
            </p>
          </div>

          {/* Date & Mode Controls */}
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", background: "var(--surface-1)", padding: "var(--space-2) var(--space-3)", borderRadius: "6px", border: "1px solid var(--border)" }}>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <label style={{ fontSize: "0.7rem", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Evaluation Anchor Date
              </label>
              <input
                type="date"
                value={asOfDate}
                onChange={(e) => setAsOfDate(e.target.value)}
                style={{
                  background: "var(--surface-2)",
                  border: "1px solid var(--border)",
                  color: "var(--text)",
                  fontFamily: "monospace",
                  fontSize: "0.8125rem",
                  padding: "4px 8px",
                  borderRadius: "4px",
                  outline: "none",
                }}
              />
            </div>
            <button
              onClick={loadBaselineData}
              style={{
                background: "var(--surface-2)",
                border: "1px solid var(--border)",
                color: "var(--text)",
                padding: "6px 12px",
                borderRadius: "4px",
                fontSize: "0.75rem",
                fontFamily: "monospace",
                cursor: "pointer",
              }}
            >
              REFRESH
            </button>
          </div>
        </div>

        {/* Strict Architectural Notice */}
        <div
          style={{
            marginTop: "var(--space-3)",
            padding: "8px 12px",
            background: "rgba(245, 158, 11, 0.08)",
            border: "1px solid rgba(245, 158, 11, 0.25)",
            borderRadius: "4px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            fontSize: "0.8125rem",
            color: "#f59e0b",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontWeight: 700 }}>BOUNDARY PRINCIPLE:</span>
            <span>Candidate Generation ≠ Global Allocation. Phase 6 provides admissible alternatives and transparent costs. Global optimal assignment is strictly solved in Phase 7 MILP.</span>
          </div>
          <span style={{ fontFamily: "monospace", fontSize: "0.7rem", opacity: 0.85 }}>NO RANKING // NO WINNERS DECLARED</span>
        </div>
      </header>

      {/* ── 2. Demonstration Case Presets (Cases A–F) ───────────────── */}
      <section style={{ marginBottom: "var(--space-4)" }}>
        <div style={{ fontSize: "0.75rem", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "6px" }}>
          Judge Demonstration Scenarios (Pre-configured Test Cases)
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "var(--space-2)" }}>
          {PRESETS.map((p) => {
            const isSelected = activePreset === p.id;
            return (
              <div
                key={p.id}
                onClick={() => applyPreset(p)}
                style={{
                  background: isSelected ? "rgba(56, 189, 248, 0.12)" : "var(--surface-1)",
                  border: isSelected ? "1px solid var(--primary)" : "1px solid var(--border)",
                  padding: "var(--space-2) var(--space-3)",
                  borderRadius: "6px",
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <span style={{ fontWeight: 600, fontSize: "0.8125rem", color: isSelected ? "var(--primary)" : "var(--text)" }}>
                    {p.name.split(":")[0]}
                  </span>
                  <span
                    style={{
                      fontSize: "0.65rem",
                      fontFamily: "monospace",
                      padding: "1px 5px",
                      borderRadius: "3px",
                      background:
                        p.badge === "FEASIBLE"
                          ? "rgba(16, 185, 129, 0.2)"
                          : p.badge === "CONFLICT"
                          ? "rgba(239, 68, 68, 0.2)"
                          : "rgba(245, 158, 11, 0.2)",
                      color:
                        p.badge === "FEASIBLE"
                          ? "#34d399"
                          : p.badge === "CONFLICT"
                          ? "#f87171"
                          : "#fbbf24",
                    }}
                  >
                    {p.badge}
                  </span>
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--muted)", lineHeight: 1.3 }}>
                  {p.description}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── 3. High-Level Fleet KPI Strip ───────────────────────────── */}
      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "var(--space-3)", marginBottom: "var(--space-4)" }}>
        <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", padding: "var(--space-3)", borderRadius: "6px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--muted)", textTransform: "uppercase" }}>Total Fleet Vessels</div>
          <div style={{ fontSize: "1.5rem", fontWeight: 700, fontFamily: "monospace", color: "var(--text)", marginTop: "4px" }}>
            {overview?.total_vessels ?? "--"}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "2px" }}>Active tracked registry</div>
        </div>

        <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", padding: "var(--space-3)", borderRadius: "6px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--muted)", textTransform: "uppercase" }}>Available Operational</div>
          <div style={{ fontSize: "1.5rem", fontWeight: 700, fontFamily: "monospace", color: "#38bdf8", marginTop: "4px" }}>
            {overview?.available_vessels ?? "--"}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "2px" }}>Ready for employment</div>
        </div>

        <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", padding: "var(--space-3)", borderRadius: "6px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--muted)", textTransform: "uppercase" }}>Confirmed Committed</div>
          <div style={{ fontSize: "1.5rem", fontWeight: 700, fontFamily: "monospace", color: "#fb923c", marginTop: "4px" }}>
            {overview?.committed_vessels ?? "--"}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "2px" }}>Protected voyage fixtures</div>
        </div>

        <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", padding: "var(--space-3)", borderRadius: "6px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--muted)", textTransform: "uppercase" }}>Active Idle Vessels</div>
          <div style={{ fontSize: "1.5rem", fontWeight: 700, fontFamily: "monospace", color: "#f59e0b", marginTop: "4px" }}>
            {idleData?.idle_vessels_count ?? "--"}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "2px" }}>Holding in waiting state</div>
        </div>

        <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", padding: "var(--space-3)", borderRadius: "6px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--muted)", textTransform: "uppercase" }}>Fleet Idle Holding Cost</div>
          <div style={{ fontSize: "1.5rem", fontWeight: 700, fontFamily: "monospace", color: "#f87171", marginTop: "4px" }}>
            ${idleData ? (idleData.total_idle_cost / 1000).toFixed(0) : "--"}k
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "2px" }}>Accruing holding exposure</div>
        </div>
      </section>

      {/* ── 4. Main Tabs Navigation ─────────────────────────────────── */}
      <div style={{ display: "flex", gap: "var(--space-2)", borderBottom: "1px solid var(--border)", marginBottom: "var(--space-4)" }}>
        <button
          onClick={() => setActiveTab("MATRIX")}
          style={{
            background: activeTab === "MATRIX" ? "var(--surface-2)" : "transparent",
            border: "none",
            borderBottom: activeTab === "MATRIX" ? "2px solid var(--primary)" : "2px solid transparent",
            color: activeTab === "MATRIX" ? "var(--primary)" : "var(--muted)",
            padding: "8px 16px",
            fontSize: "0.875rem",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Candidate Generation Matrix ({candidatesMatrix?.candidates.length ?? 0})
        </button>

        <button
          onClick={() => setActiveTab("TIMELINE")}
          style={{
            background: activeTab === "TIMELINE" ? "var(--surface-2)" : "transparent",
            border: "none",
            borderBottom: activeTab === "TIMELINE" ? "2px solid var(--primary)" : "2px solid transparent",
            color: activeTab === "TIMELINE" ? "var(--primary)" : "var(--muted)",
            padding: "8px 16px",
            fontSize: "0.875rem",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Vessel Chronological Timeline
        </button>

        <button
          onClick={() => setActiveTab("IDLE")}
          style={{
            background: activeTab === "IDLE" ? "var(--surface-2)" : "transparent",
            border: "none",
            borderBottom: activeTab === "IDLE" ? "2px solid var(--primary)" : "2px solid transparent",
            color: activeTab === "IDLE" ? "var(--primary)" : "var(--muted)",
            padding: "8px 16px",
            fontSize: "0.875rem",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Fleet Idle Ledger & Cost Exposure
        </button>

        <button
          onClick={() => setActiveTab("COMPARE")}
          style={{
            background: activeTab === "COMPARE" ? "var(--surface-2)" : "transparent",
            border: "none",
            borderBottom: activeTab === "COMPARE" ? "2px solid var(--primary)" : "2px solid transparent",
            color: activeTab === "COMPARE" ? "var(--primary)" : "var(--muted)",
            padding: "8px 16px",
            fontSize: "0.875rem",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Non-Ranking Trade-Off Comparison
        </button>
      </div>

      {/* ── 5. Tab Content ─────────────────────────────────────────── */}
      {activeTab === "MATRIX" && (
        <div>
          {/* Controls bar */}
          <div style={{ display: "flex", gap: "var(--space-3)", alignItems: "center", marginBottom: "var(--space-3)", flexWrap: "wrap" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "0.75rem", color: "var(--muted)", textTransform: "uppercase" }}>Filter Vessel:</span>
              <select
                value={selectedVesselId}
                onChange={(e) => setSelectedVesselId(Number(e.target.value))}
                style={{
                  background: "var(--surface-1)",
                  border: "1px solid var(--border)",
                  color: "var(--text)",
                  padding: "4px 8px",
                  borderRadius: "4px",
                  fontSize: "0.8125rem",
                }}
              >
                {vessels.map((v) => (
                  <option key={v.vessel_id} value={v.vessel_id}>
                    {v.vessel_name} ({v.vessel_class})
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "0.75rem", color: "var(--muted)", textTransform: "uppercase" }}>Opportunity:</span>
              <select
                value={selectedCargoId ?? ""}
                onChange={(e) => setSelectedCargoId(e.target.value ? Number(e.target.value) : null)}
                style={{
                  background: "var(--surface-1)",
                  border: "1px solid var(--border)",
                  color: "var(--text)",
                  padding: "4px 8px",
                  borderRadius: "4px",
                  fontSize: "0.8125rem",
                }}
              >
                <option value="">All Canonical Cargos</option>
                {opportunities.map((o) => (
                  <option key={o.cargo_id} value={o.cargo_id}>
                    {o.opportunity_id}: {o.commodity} ({o.volume_mt.toLocaleString()} MT)
                  </option>
                ))}
              </select>
            </div>

            <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.8125rem", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={filterReadyOnly}
                onChange={(e) => setFilterReadyOnly(e.target.checked)}
              />
              Show Ready for Optimization Only
            </label>
          </div>

          {/* Candidates Matrix Table */}
          <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: "6px", overflowX: "auto", marginBottom: "var(--space-4)" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8125rem", textAlign: "left" }}>
              <thead>
                <tr style={{ background: "var(--surface-2)", borderBottom: "1px solid var(--border)", color: "var(--muted)", fontFamily: "monospace", fontSize: "0.75rem" }}>
                  <th style={{ padding: "8px 12px" }}>CANDIDATE ID</th>
                  <th style={{ padding: "8px 12px" }}>VESSEL</th>
                  <th style={{ padding: "8px 12px" }}>CARGO / OPPORTUNITY</th>
                  <th style={{ padding: "8px 12px" }}>ROUTE</th>
                  <th style={{ padding: "8px 12px" }}>BALLAST</th>
                  <th style={{ padding: "8px 12px" }}>VOYAGE DAYS</th>
                  <th style={{ padding: "8px 12px" }}>TOTAL COST</th>
                  <th style={{ padding: "8px 12px" }}>GROSS REVENUE</th>
                  <th style={{ padding: "8px 12px" }}>CONTRIBUTION</th>
                  <th style={{ padding: "8px 12px" }}>STATUS</th>
                  <th style={{ padding: "8px 12px" }}>PRIMARY REASON</th>
                </tr>
              </thead>
              <tbody>
                {candidatesMatrix?.candidates.map((cand) => {
                  const isSelected = selectedCandidate?.candidate_id === cand.candidate_id;
                  const isFeasible = cand.status === "FEASIBLE";
                  return (
                    <tr
                      key={cand.candidate_id}
                      onClick={() => setSelectedCandidate(cand)}
                      style={{
                        borderBottom: "1px solid var(--border)",
                        background: isSelected ? "rgba(56, 189, 248, 0.1)" : "transparent",
                        cursor: "pointer",
                      }}
                    >
                      <td style={{ padding: "8px 12px", fontFamily: "monospace", fontWeight: 600, color: "var(--primary)" }}>
                        {cand.candidate_id}
                      </td>
                      <td style={{ padding: "8px 12px" }}>
                        <div style={{ fontWeight: 600 }}>{cand.vessel_name}</div>
                        <div style={{ fontSize: "0.7rem", color: "var(--muted)" }}>{cand.vessel_class}</div>
                      </td>
                      <td style={{ padding: "8px 12px" }}>{cand.cargo_name}</td>
                      <td style={{ padding: "8px 12px" }}>
                        {cand.origin_port_name} &rarr; {cand.destination_port_name}
                      </td>
                      <td style={{ padding: "8px 12px", fontFamily: "monospace" }}>
                        {cand.ballast.ballast_days}d ({cand.ballast.ballast_distance_nm} NM)
                      </td>
                      <td style={{ padding: "8px 12px", fontFamily: "monospace" }}>
                        {cand.timeline.duration_breakdown?.total_voyage_days ?? "--"}d
                      </td>
                      <td style={{ padding: "8px 12px", fontFamily: "monospace" }}>
                        ${cand.economics.total_voyage_costs_usd?.toLocaleString() ?? "--"}
                      </td>
                      <td style={{ padding: "8px 12px", fontFamily: "monospace" }}>
                        ${cand.economics.expected_revenue_usd?.toLocaleString() ?? "--"}
                      </td>
                      <td style={{ padding: "8px 12px", fontFamily: "monospace", fontWeight: 600, color: (cand.economics.gross_contribution_usd ?? 0) >= 0 ? "#34d399" : "#f87171" }}>
                        ${cand.economics.gross_contribution_usd?.toLocaleString() ?? "--"}
                      </td>
                      <td style={{ padding: "8px 12px" }}>
                        <span
                          style={{
                            fontFamily: "monospace",
                            fontSize: "0.7rem",
                            padding: "2px 6px",
                            borderRadius: "4px",
                            background: isFeasible ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)",
                            color: isFeasible ? "#34d399" : "#f87171",
                            border: `1px solid ${isFeasible ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)"}`,
                          }}
                        >
                          {cand.optimization_status}
                        </span>
                      </td>
                      <td style={{ padding: "8px 12px", fontSize: "0.75rem", color: "var(--muted)", maxWidth: "240px" }}>
                        <div style={{ fontFamily: "monospace", color: isFeasible ? "#34d399" : "#f87171" }}>
                          {cand.primary_reason_code}
                        </div>
                        <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {cand.primary_reason_description}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Selected Candidate Detailed Inspector */}
          {selectedCandidate && (
            <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: "6px", padding: "var(--space-3)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)", borderBottom: "1px solid var(--border)", paddingBottom: "var(--space-2)" }}>
                <div>
                  <span style={{ fontSize: "0.75rem", fontFamily: "monospace", color: "var(--primary)" }}>CANDIDATE INSPECTION // </span>
                  <span style={{ fontWeight: 700, fontSize: "1rem" }}>{selectedCandidate.candidate_id}</span>
                </div>
                <span
                  style={{
                    fontFamily: "monospace",
                    fontSize: "0.75rem",
                    padding: "3px 8px",
                    borderRadius: "4px",
                    background: selectedCandidate.status === "FEASIBLE" ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)",
                    color: selectedCandidate.status === "FEASIBLE" ? "#34d399" : "#f87171",
                  }}
                >
                  {selectedCandidate.optimization_status}
                </span>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "var(--space-3)" }}>
                {/* 1. Repositioning & Ballast */}
                <div style={{ background: "var(--surface-2)", padding: "var(--space-3)", borderRadius: "4px", border: "1px solid var(--border)" }}>
                  <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--primary)", marginBottom: "8px" }}>
                    1. REPOSITIONING & BALLAST ENGINE
                  </div>
                  <div style={{ fontSize: "0.8125rem", display: "grid", gap: "6px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--muted)" }}>Ballast Distance:</span>
                      <span style={{ fontFamily: "monospace" }}>{selectedCandidate.ballast.ballast_distance_nm} NM</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--muted)" }}>Transit Days:</span>
                      <span style={{ fontFamily: "monospace" }}>{selectedCandidate.ballast.ballast_days} d</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--muted)" }}>Speed:</span>
                      <span style={{ fontFamily: "monospace" }}>{selectedCandidate.ballast.ballast_speed_knots} kts</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--muted)" }}>VLSFO Fuel:</span>
                      <span style={{ fontFamily: "monospace" }}>{selectedCandidate.ballast.bunker_consumption_vlsfo_mt} MT</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--muted)" }}>Data Provenance:</span>
                      <span style={{ fontFamily: "monospace", fontSize: "0.7rem" }}>{selectedCandidate.ballast.data_source}</span>
                    </div>
                  </div>
                </div>

                {/* 2. Physical Feasibility (Phase 4) */}
                <div style={{ background: "var(--surface-2)", padding: "var(--space-3)", borderRadius: "4px", border: "1px solid var(--border)" }}>
                  <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--primary)", marginBottom: "8px" }}>
                    2. PHASE 4 FEASIBILITY ENGINE HANDOFF
                  </div>
                  <div style={{ fontSize: "0.8125rem", display: "grid", gap: "6px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--muted)" }}>Physical Admissibility:</span>
                      <span style={{ fontFamily: "monospace", fontWeight: 600, color: selectedCandidate.feasibility.is_feasible ? "#34d399" : "#f87171" }}>
                        {selectedCandidate.feasibility.is_feasible ? "PASSED" : "REJECTED"}
                      </span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--muted)" }}>Primary Feasibility Code:</span>
                      <span style={{ fontFamily: "monospace", fontSize: "0.75rem" }}>{selectedCandidate.feasibility.primary_reason_code ?? "NONE"}</span>
                    </div>
                    <div style={{ color: "var(--muted)", fontSize: "0.75rem", marginTop: "4px" }}>
                      Failed Checks: {selectedCandidate.feasibility.failed_checks?.length > 0 ? selectedCandidate.feasibility.failed_checks.join(", ") : "None"}
                    </div>
                  </div>
                </div>

                {/* 3. Procurement Timing (Phase 5) */}
                <div style={{ background: "var(--surface-2)", padding: "var(--space-3)", borderRadius: "4px", border: "1px solid var(--border)" }}>
                  <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--primary)", marginBottom: "8px" }}>
                    3. PHASE 5 PROCUREMENT TIMING HANDOFF
                  </div>
                  <div style={{ fontSize: "0.8125rem", display: "grid", gap: "6px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--muted)" }}>Procurement Profile:</span>
                      <span style={{ fontFamily: "monospace" }}>{selectedCandidate.procurement.profile_id}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--muted)" }}>Required Lead Time:</span>
                      <span style={{ fontFamily: "monospace" }}>{selectedCandidate.procurement.lead_time_days} d</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--muted)" }}>Timing Signal:</span>
                      <span style={{ fontFamily: "monospace" }}>{selectedCandidate.procurement.timing_signal ?? "OPEN"}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--muted)" }}>Timing Compliance:</span>
                      <span style={{ fontFamily: "monospace", color: selectedCandidate.procurement.is_timing_feasible ? "#34d399" : "#f87171" }}>
                        {selectedCandidate.procurement.is_timing_feasible ? "FEASIBLE" : "INFEASIBLE"}
                      </span>
                    </div>
                  </div>
                </div>

                {/* 4. Economics & Contribution */}
                <div style={{ background: "var(--surface-2)", padding: "var(--space-3)", borderRadius: "4px", border: "1px solid var(--border)" }}>
                  <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--primary)", marginBottom: "8px" }}>
                    4. TRANSPARENT CONTRIBUTION ECONOMICS
                  </div>
                  <div style={{ fontSize: "0.8125rem", display: "grid", gap: "6px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--muted)" }}>Expected Revenue:</span>
                      <span style={{ fontFamily: "monospace" }}>${selectedCandidate.economics.expected_revenue_usd?.toLocaleString() ?? "--"}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--muted)" }}>Operating Costs:</span>
                      <span style={{ fontFamily: "monospace" }}>${selectedCandidate.economics.cost_breakdown?.operating_cost?.toLocaleString() ?? "--"}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--muted)" }}>Bunker Fuel Costs:</span>
                      <span style={{ fontFamily: "monospace" }}>${selectedCandidate.economics.cost_breakdown?.bunker_cost?.toLocaleString() ?? "--"}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--muted)" }}>Port Tariffs & Dues:</span>
                      <span style={{ fontFamily: "monospace" }}>${selectedCandidate.economics.cost_breakdown?.port_cost?.toLocaleString() ?? "--"}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", borderTop: "1px solid var(--border)", paddingTop: "4px" }}>
                      <span style={{ fontWeight: 600 }}>Gross Contribution:</span>
                      <span style={{ fontFamily: "monospace", fontWeight: 700, color: (selectedCandidate.economics.gross_contribution_usd ?? 0) >= 0 ? "#34d399" : "#f87171" }}>
                        ${selectedCandidate.economics.gross_contribution_usd?.toLocaleString() ?? "--"}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Conflict Callout if any */}
              {selectedCandidate.timeline.conflicts && selectedCandidate.timeline.conflicts.length > 0 && (
                <div style={{ marginTop: "var(--space-3)", padding: "8px 12px", background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.3)", borderRadius: "4px" }}>
                  <div style={{ color: "#f87171", fontWeight: 600, fontSize: "0.8125rem", marginBottom: "4px" }}>
                    COMMITMENT OVERLAP CONFLICT DETECTED
                  </div>
                  {selectedCandidate.timeline.conflicts.map((c, i) => (
                    <div key={i} style={{ fontSize: "0.75rem", color: "var(--text)" }}>
                      Conflict #{c.conflict_id}: Candidate completion ({c.candidate_discharge_end?.slice(0, 10)}) overlaps confirmed commitment ({c.description}) starting {c.commitment_start?.slice(0, 10)}. Overlap: {c.overlap_days} days.
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Tab 2: Chronological Timeline ───────────────────────────── */}
      {activeTab === "TIMELINE" && (
        <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: "6px", padding: "var(--space-4)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-4)", flexWrap: "wrap", gap: "8px" }}>
            <div>
              <h2 style={{ fontSize: "1.125rem", fontWeight: 700, margin: 0 }}>
                {timelineData?.vessel_name ?? "Vessel"} Timeline Schedule
              </h2>
              <p style={{ margin: "2px 0 0 0", color: "var(--muted)", fontSize: "0.8125rem" }}>
                Vessel Class: {timelineData?.vessel_class} | 45-Day Planning Horizon
              </p>
            </div>

            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>Select Vessel:</span>
              <select
                value={selectedVesselId}
                onChange={(e) => setSelectedVesselId(Number(e.target.value))}
                style={{
                  background: "var(--surface-2)",
                  border: "1px solid var(--border)",
                  color: "var(--text)",
                  padding: "4px 8px",
                  borderRadius: "4px",
                  fontSize: "0.8125rem",
                }}
              >
                {vessels.map((v) => (
                  <option key={v.vessel_id} value={v.vessel_id}>
                    {v.vessel_name} ({v.vessel_class})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Timeline Events Visualizer */}
          <div style={{ display: "grid", gap: "var(--space-3)" }}>
            {timelineData?.events.map((ev, idx) => (
              <div
                key={idx}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "var(--space-3)",
                  padding: "var(--space-3)",
                  background: "var(--surface-2)",
                  borderRadius: "6px",
                  borderLeft: `4px solid ${ev.color}`,
                }}
              >
                <div style={{ minWidth: "120px", fontFamily: "monospace", fontSize: "0.75rem", color: "var(--muted)" }}>
                  <div>{ev.start_time.slice(0, 10)}</div>
                  <div>to {ev.end_time.slice(0, 10)}</div>
                </div>

                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span
                      style={{
                        fontSize: "0.7rem",
                        fontFamily: "monospace",
                        padding: "1px 5px",
                        borderRadius: "3px",
                        background: `${ev.color}20`,
                        color: ev.color,
                        fontWeight: 600,
                      }}
                    >
                      {ev.event_type}
                    </span>
                    <span style={{ fontWeight: 600, fontSize: "0.875rem" }}>{ev.title}</span>
                  </div>
                  <div style={{ fontSize: "0.8125rem", color: "var(--muted)", marginTop: "4px" }}>
                    {ev.details}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Tab 3: Fleet Idle Ledger & Holding Costs ─────────────────── */}
      {activeTab === "IDLE" && (
        <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: "6px", overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8125rem", textAlign: "left" }}>
            <thead>
              <tr style={{ background: "var(--surface-2)", borderBottom: "1px solid var(--border)", color: "var(--muted)", fontFamily: "monospace", fontSize: "0.75rem" }}>
                <th style={{ padding: "8px 12px" }}>VESSEL ID</th>
                <th style={{ padding: "8px 12px" }}>VESSEL NAME</th>
                <th style={{ padding: "8px 12px" }}>CLASS</th>
                <th style={{ padding: "8px 12px" }}>STATUS</th>
                <th style={{ padding: "8px 12px" }}>IDLE DAYS</th>
                <th style={{ padding: "8px 12px" }}>DAILY RATE</th>
                <th style={{ padding: "8px 12px" }}>TOTAL IDLE COST</th>
                <th style={{ padding: "8px 12px" }}>RATE SOURCE</th>
                <th style={{ padding: "8px 12px" }}>IDLE REASON</th>
              </tr>
            </thead>
            <tbody>
              {idleData?.assessments.map((a) => (
                <tr key={a.vessel_id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "8px 12px", fontFamily: "monospace", color: "var(--primary)" }}>
                    #{a.vessel_id}
                  </td>
                  <td style={{ padding: "8px 12px", fontWeight: 600 }}>{a.vessel_name}</td>
                  <td style={{ padding: "8px 12px", color: "var(--muted)" }}>{a.vessel_class}</td>
                  <td style={{ padding: "8px 12px" }}>
                    <span
                      style={{
                        fontFamily: "monospace",
                        fontSize: "0.7rem",
                        padding: "2px 6px",
                        borderRadius: "4px",
                        background: a.is_idle ? "rgba(245, 158, 11, 0.15)" : "rgba(16, 185, 129, 0.15)",
                        color: a.is_idle ? "#f59e0b" : "#34d399",
                      }}
                    >
                      {a.is_idle ? "IDLE" : "ACTIVE"}
                    </span>
                  </td>
                  <td style={{ padding: "8px 12px", fontFamily: "monospace" }}>{a.idle_days} d</td>
                  <td style={{ padding: "8px 12px", fontFamily: "monospace" }}>${a.daily_idle_rate.toLocaleString()} /d</td>
                  <td style={{ padding: "8px 12px", fontFamily: "monospace", fontWeight: 600, color: a.idle_cost > 0 ? "#f87171" : "var(--muted)" }}>
                    ${a.idle_cost.toLocaleString()}
                  </td>
                  <td style={{ padding: "8px 12px", fontSize: "0.7rem", color: "var(--muted)", fontFamily: "monospace" }}>
                    {a.cost_source}
                  </td>
                  <td style={{ padding: "8px 12px", fontSize: "0.75rem", color: "var(--muted)" }}>
                    <div style={{ fontFamily: "monospace", color: "var(--text)" }}>{a.reason_code}</div>
                    <div style={{ fontSize: "0.7rem" }}>{a.reason_description}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Tab 4: Non-Ranking Trade-Off Comparison ─────────────────── */}
      {activeTab === "COMPARE" && (
        <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: "6px", padding: "var(--space-4)" }}>
          <div style={{ marginBottom: "var(--space-3)", padding: "8px 12px", background: "rgba(56, 189, 248, 0.08)", border: "1px solid rgba(56, 189, 248, 0.25)", borderRadius: "4px" }}>
            <span style={{ fontWeight: 600, color: "var(--primary)" }}>COMPARATIVE ANALYSIS NOTICE: </span>
            <span style={{ fontSize: "0.8125rem", color: "var(--text)" }}>
              {compareData?.advisory_note}
            </span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "var(--space-3)" }}>
            {compareData?.candidates.map((cand) => (
              <div
                key={cand.candidate_id}
                style={{
                  background: "var(--surface-2)",
                  border: "1px solid var(--border)",
                  borderRadius: "6px",
                  padding: "var(--space-3)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                  <span style={{ fontFamily: "monospace", fontWeight: 700, color: "var(--primary)", fontSize: "0.875rem" }}>
                    {cand.candidate_id}
                  </span>
                  <span
                    style={{
                      fontFamily: "monospace",
                      fontSize: "0.7rem",
                      padding: "2px 6px",
                      borderRadius: "4px",
                      background: cand.status === "FEASIBLE" ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)",
                      color: cand.status === "FEASIBLE" ? "#34d399" : "#f87171",
                    }}
                  >
                    {cand.optimization_status}
                  </span>
                </div>

                <div style={{ fontSize: "0.8125rem", marginBottom: "8px" }}>
                  <div style={{ fontWeight: 600 }}>{cand.cargo_name}</div>
                  <div style={{ color: "var(--muted)", fontSize: "0.75rem" }}>
                    {cand.origin_port_name} &rarr; {cand.destination_port_name}
                  </div>
                </div>

                <div style={{ fontSize: "0.75rem", display: "grid", gap: "4px", borderTop: "1px solid var(--border)", paddingTop: "6px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--muted)" }}>Ballast:</span>
                    <span style={{ fontFamily: "monospace" }}>{cand.ballast.ballast_days}d ({cand.ballast.ballast_distance_nm} NM)</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--muted)" }}>Voyage Cost:</span>
                    <span style={{ fontFamily: "monospace" }}>${cand.economics.total_voyage_costs_usd?.toLocaleString()}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--muted)" }}>Gross Revenue:</span>
                    <span style={{ fontFamily: "monospace" }}>${cand.economics.expected_revenue_usd?.toLocaleString()}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 600 }}>
                    <span>Gross Contribution:</span>
                    <span style={{ fontFamily: "monospace", color: (cand.economics.gross_contribution_usd ?? 0) >= 0 ? "#34d399" : "#f87171" }}>
                      ${cand.economics.gross_contribution_usd?.toLocaleString()}
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--muted)" }}>Utilization:</span>
                    <span style={{ fontFamily: "monospace" }}>{cand.economics.utilization_ratio_pct}%</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 6. Institutional Footer ─────────────────────────────────── */}
      <footer
        style={{
          marginTop: "var(--space-5)",
          paddingTop: "var(--space-3)",
          borderTop: "1px solid var(--border)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: "0.75rem",
          color: "var(--muted)",
          fontFamily: "monospace",
          flexWrap: "wrap",
          gap: "8px",
        }}
      >
        <div>
          VESSELOPTIMA ENGINE ARCHITECTURE // OBSERVE &rarr; FORECAST &rarr; CONSTRAIN &rarr; PROCUREMENT STRATEGY &rarr; IDLE/ALTERNATIVE EMPLOYMENT &rarr; OPTIMIZE (PHASE 7)
        </div>
        <div>DATA CONTEXT: OFFLINE-DEMO-V1 // AIR-GAP COMPLIANT</div>
      </footer>
    </div>
  );
}
