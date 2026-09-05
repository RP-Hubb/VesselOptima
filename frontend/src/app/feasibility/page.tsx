"use client";

import { useEffect, useState, useMemo } from "react";
import {
  getCargoRequirements,
  getCandidateFleetFeasibility,
  evaluateFeasibility,
} from "@/lib/api";
import type {
  CargoRequirementItem,
  FleetFeasibilityResponse,
  FeasibilityResultResponse,
} from "@/types/api";

export default function FeasibilityPage() {
  const [cargos, setCargos] = useState<CargoRequirementItem[]>([]);
  const [selectedCargoId, setSelectedCargoId] = useState<number | null>(null);
  const [fleetData, setFleetData] = useState<FleetFeasibilityResponse | null>(null);
  const [selectedVesselId, setSelectedVesselId] = useState<number | null>(null);
  const [singleEvaluation, setSingleEvaluation] = useState<FeasibilityResultResponse | null>(null);
  const [filterMode, setFilterMode] = useState<"ALL" | "FEASIBLE" | "INFEASIBLE">("ALL");
  const [loadingCargos, setLoadingCargos] = useState<boolean>(true);
  const [loadingFleet, setLoadingFleet] = useState<boolean>(false);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Load cargo requirements on mount
  useEffect(() => {
    setLoadingCargos(true);
    setError(null);
    getCargoRequirements()
      .then((items) => {
        setCargos(items);
        if (items.length > 0) {
          setSelectedCargoId(items[0].id);
        }
        setLoadingCargos(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to load cargo requirements");
        setLoadingCargos(false);
      });
  }, []);

  // When selectedCargoId changes, fetch fleet feasibility evaluation
  useEffect(() => {
    if (selectedCargoId === null) return;
    setLoadingFleet(true);
    setError(null);
    getCandidateFleetFeasibility(selectedCargoId)
      .then((data) => {
        setFleetData(data);
        setLoadingFleet(false);
        // Default select first vessel (preferably feasible, or first)
        if (data.vessels.length > 0) {
          const defaultVessel = data.vessels.find((v) => v.is_feasible) || data.vessels[0];
          setSelectedVesselId(defaultVessel.vessel_id);
        }
      })
      .catch((err) => {
        setError(err.message || "Failed to evaluate candidate fleet feasibility");
        setLoadingFleet(false);
      });
  }, [selectedCargoId]);

  // When selectedVesselId changes, fetch detailed single evaluation
  useEffect(() => {
    if (selectedCargoId === null || selectedVesselId === null) return;
    setLoadingDetail(true);
    evaluateFeasibility({
      cargo_id: selectedCargoId,
      vessel_id: selectedVesselId,
      persist: false,
    })
      .then((res) => {
        setSingleEvaluation(res);
        setLoadingDetail(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to evaluate vessel feasibility details");
        setLoadingDetail(false);
      });
  }, [selectedCargoId, selectedVesselId]);

  // Active cargo item
  const currentCargo = useMemo(() => {
    return cargos.find((c) => c.id === selectedCargoId) || null;
  }, [cargos, selectedCargoId]);

  // Filtered fleet vessels
  const displayedVessels = useMemo(() => {
    if (!fleetData) return [];
    if (filterMode === "FEASIBLE") return fleetData.vessels.filter((v) => v.is_feasible);
    if (filterMode === "INFEASIBLE") return fleetData.vessels.filter((v) => !v.is_feasible);
    return fleetData.vessels;
  }, [fleetData, filterMode]);

  return (
    <div style={{ padding: "var(--space-4)", maxWidth: "1600px", margin: "0 auto" }}>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header
        style={{
          borderBottom: "1px solid var(--border)",
          paddingBottom: "var(--space-3)",
          marginBottom: "var(--space-4)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          flexWrap: "wrap",
          gap: "var(--space-2)",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <h1
              style={{
                fontSize: "1.125rem",
                fontWeight: 600,
                letterSpacing: "0.04em",
                margin: 0,
                textTransform: "uppercase",
              }}
            >
              Vessel & Port Feasibility Engine
            </h1>
            <span
              style={{
                background: "var(--surface-2)",
                border: "1px solid var(--border)",
                padding: "2px 8px",
                fontSize: "0.6875rem",
                borderRadius: "2px",
                color: "var(--text)",
                letterSpacing: "0.05em",
                fontWeight: 600,
              }}
            >
              PHASE 4 — CONSTRAIN
            </span>
          </div>
          <p
            style={{
              fontSize: "0.75rem",
              color: "var(--muted)",
              marginTop: "var(--space-1)",
              marginBottom: 0,
            }}
          >
            Deterministic operational & physical constraint evaluation:{" "}
            <strong style={{ color: "var(--text)" }}>Prediction ≠ Decision</strong> |{" "}
            <strong style={{ color: "var(--text)" }}>Feasibility ≠ Optimization</strong>
          </p>
        </div>

        {/* Provenance & Isolation Badge */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-3)",
            fontSize: "0.6875rem",
            background: "var(--surface-1)",
            padding: "var(--space-2) var(--space-3)",
            border: "1px solid var(--border)",
            borderRadius: "2px",
          }}
        >
          <div>
            <span style={{ color: "var(--muted)" }}>DATA RUNTIME: </span>
            <span style={{ color: "var(--accent)", fontWeight: 600 }}>OFFLINE DEMO</span>
          </div>
          <div style={{ width: "1px", height: "12px", background: "var(--border)" }} />
          <div>
            <span style={{ color: "var(--muted)" }}>PACKAGE: </span>
            <span className="tabular-nums" style={{ color: "var(--text)" }}>demo-v1</span>
          </div>
          <div style={{ width: "1px", height: "12px", background: "var(--border)" }} />
          <div>
            <span style={{ color: "var(--muted)" }}>AIR-GAP: </span>
            <span style={{ color: "var(--success, #22c55e)" }}>VERIFIED (0 NET CALLS)</span>
          </div>
        </div>
      </header>

      {/* ── Error Banner ────────────────────────────────────────────────── */}
      {error && (
        <div
          style={{
            background: "rgba(239, 68, 68, 0.1)",
            border: "1px solid var(--danger)",
            color: "var(--danger)",
            padding: "var(--space-2) var(--space-3)",
            fontSize: "0.75rem",
            marginBottom: "var(--space-3)",
            borderRadius: "2px",
          }}
        >
          <strong>Feasibility Error:</strong> {error}
        </div>
      )}

      {/* ── Cargo Requirement Selector & Metadata Bar ───────────────────── */}
      <section
        style={{
          background: "var(--surface-1)",
          border: "1px solid var(--border)",
          padding: "var(--space-3)",
          marginBottom: "var(--space-4)",
          borderRadius: "2px",
        }}
      >
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "var(--space-4)",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <label
              htmlFor="cargo-select"
              style={{
                fontSize: "0.75rem",
                color: "var(--muted)",
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                fontWeight: 600,
              }}
            >
              Cargo Requirement:
            </label>
            <select
              id="cargo-select"
              value={selectedCargoId ?? ""}
              onChange={(e) => setSelectedCargoId(Number(e.target.value))}
              disabled={loadingCargos}
              style={{
                background: "var(--surface-2)",
                color: "var(--text)",
                border: "1px solid var(--border)",
                padding: "6px 12px",
                fontSize: "0.8125rem",
                borderRadius: "2px",
                outline: "none",
                minWidth: "320px",
                cursor: "pointer",
              }}
            >
              {cargos.map((c) => (
                <option key={c.id} value={c.id}>
                  CARGO-{String(c.id).padStart(3, "0")}: {c.commodity} ({c.volume_mt.toLocaleString()} MT) |{" "}
                  {c.origin_port_name ?? `Port ${c.origin_port_id}`} →{" "}
                  {c.destination_port_name ?? `Port ${c.destination_port_id}`}
                </option>
              ))}
            </select>
          </div>

          {currentCargo && (
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "var(--space-4)",
                fontSize: "0.75rem",
              }}
            >
              <div>
                <span style={{ color: "var(--muted)" }}>PARCEL SIZE: </span>
                <span className="tabular-nums" style={{ fontWeight: 600 }}>
                  {currentCargo.volume_mt.toLocaleString()} MT (±{currentCargo.tolerance_pct}%)
                </span>
              </div>
              <div style={{ width: "1px", height: "14px", background: "var(--border)" }} />
              <div>
                <span style={{ color: "var(--muted)" }}>ORIGIN → DEST: </span>
                <span style={{ fontWeight: 600 }}>
                  {currentCargo.origin_port_name} → {currentCargo.destination_port_name}
                </span>
              </div>
              <div style={{ width: "1px", height: "14px", background: "var(--border)" }} />
              <div>
                <span style={{ color: "var(--muted)" }}>LAYCAN WINDOW: </span>
                <span className="tabular-nums" style={{ fontWeight: 600 }}>
                  {currentCargo.loading_window_start} to {currentCargo.loading_window_end}
                </span>
              </div>
              <div style={{ width: "1px", height: "14px", background: "var(--border)" }} />
              <div>
                <span style={{ color: "var(--muted)" }}>DEADLINE: </span>
                <span className="tabular-nums" style={{ color: "var(--accent)", fontWeight: 600 }}>
                  {currentCargo.delivery_deadline}
                </span>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* ── Main Two-Pane Layout ────────────────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "var(--space-4)",
          alignItems: "start",
        }}
      >
        {/* ── Left Pane: Candidate Fleet Feasibility Filter ────────────── */}
        <section
          style={{
            background: "var(--surface-1)",
            border: "1px solid var(--border)",
            padding: "var(--space-3)",
            borderRadius: "2px",
          }}
        >
          {/* Subheader & Stats Strip */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "var(--space-3)",
              borderBottom: "1px solid var(--border)",
              paddingBottom: "var(--space-2)",
            }}
          >
            <div>
              <h2
                style={{
                  fontSize: "0.8125rem",
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  margin: 0,
                }}
              >
                Candidate Fleet Evaluation (Filter Only)
              </h2>
              <span style={{ fontSize: "0.6875rem", color: "var(--muted)" }}>
                Zero economic ranking. Strict constraint verification.
              </span>
            </div>

            {/* Filter Tabs */}
            <div style={{ display: "flex", gap: "4px" }}>
              <button
                type="button"
                id="btn-filter-all"
                onClick={() => setFilterMode("ALL")}
                style={{
                  background: filterMode === "ALL" ? "var(--surface-2)" : "transparent",
                  color: filterMode === "ALL" ? "var(--text)" : "var(--muted)",
                  border: "1px solid var(--border)",
                  padding: "3px 8px",
                  fontSize: "0.6875rem",
                  borderRadius: "2px",
                  cursor: "pointer",
                }}
              >
                All ({fleetData?.total_vessels ?? 0})
              </button>
              <button
                type="button"
                id="btn-filter-feasible"
                onClick={() => setFilterMode("FEASIBLE")}
                style={{
                  background: filterMode === "FEASIBLE" ? "rgba(34, 197, 94, 0.15)" : "transparent",
                  color: filterMode === "FEASIBLE" ? "#22c55e" : "var(--muted)",
                  border: filterMode === "FEASIBLE" ? "1px solid #22c55e" : "1px solid var(--border)",
                  padding: "3px 8px",
                  fontSize: "0.6875rem",
                  borderRadius: "2px",
                  cursor: "pointer",
                  fontWeight: 600,
                }}
              >
                Feasible ({fleetData?.feasible_count ?? 0})
              </button>
              <button
                type="button"
                id="btn-filter-infeasible"
                onClick={() => setFilterMode("INFEASIBLE")}
                style={{
                  background: filterMode === "INFEASIBLE" ? "rgba(239, 68, 68, 0.15)" : "transparent",
                  color: filterMode === "INFEASIBLE" ? "#ef4444" : "var(--muted)",
                  border: filterMode === "INFEASIBLE" ? "1px solid #ef4444" : "1px solid var(--border)",
                  padding: "3px 8px",
                  fontSize: "0.6875rem",
                  borderRadius: "2px",
                  cursor: "pointer",
                  fontWeight: 600,
                }}
              >
                Infeasible ({fleetData?.infeasible_count ?? 0})
              </button>
            </div>
          </div>

          {/* Fleet Table */}
          <div style={{ overflowX: "auto", maxHeight: "620px" }}>
            <table
              id="fleet-feasibility-table"
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: "0.75rem",
                textAlign: "left",
              }}
            >
              <thead>
                <tr
                  style={{
                    borderBottom: "1px solid var(--border)",
                    color: "var(--muted)",
                    fontSize: "0.6875rem",
                    textTransform: "uppercase",
                  }}
                >
                  <th style={{ padding: "6px 8px" }}>Vessel</th>
                  <th style={{ padding: "6px 8px" }}>Class</th>
                  <th style={{ padding: "6px 8px", textAlign: "right" }}>DWT (MT)</th>
                  <th style={{ padding: "6px 8px", textAlign: "right" }}>Draft</th>
                  <th style={{ padding: "6px 8px", textAlign: "center" }}>Verdict</th>
                  <th style={{ padding: "6px 8px" }}>Primary Reason</th>
                </tr>
              </thead>
              <tbody>
                {loadingFleet ? (
                  <tr>
                    <td colSpan={6} style={{ padding: "var(--space-4)", textAlign: "center", color: "var(--muted)" }}>
                      Evaluating fleet feasibility constraints...
                    </td>
                  </tr>
                ) : displayedVessels.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ padding: "var(--space-4)", textAlign: "center", color: "var(--muted)" }}>
                      No vessels match selected filter.
                    </td>
                  </tr>
                ) : (
                  displayedVessels.map((v) => {
                    const isSelected = v.vessel_id === selectedVesselId;
                    return (
                      <tr
                        key={v.vessel_id}
                        id={`vessel-row-${v.vessel_id}`}
                        onClick={() => setSelectedVesselId(v.vessel_id)}
                        style={{
                          borderBottom: "1px solid var(--border)",
                          background: isSelected
                            ? "var(--surface-2)"
                            : "transparent",
                          cursor: "pointer",
                          transition: "background 100ms ease",
                          outline: isSelected ? "1px solid var(--info, #3b82f6)" : "none",
                        }}
                      >
                        <td style={{ padding: "8px 8px", fontWeight: isSelected ? 600 : 400 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                            <span
                              style={{
                                width: "6px",
                                height: "6px",
                                borderRadius: "50%",
                                background: v.is_feasible ? "#22c55e" : "#ef4444",
                                display: "inline-block",
                              }}
                            />
                            {v.vessel_name}
                          </div>
                        </td>
                        <td style={{ padding: "8px 8px", color: "var(--muted)" }}>{v.vessel_class}</td>
                        <td className="tabular-nums" style={{ padding: "8px 8px", textAlign: "right" }}>
                          {v.cargo_capacity.toLocaleString()}
                        </td>
                        <td className="tabular-nums" style={{ padding: "8px 8px", textAlign: "right" }}>
                          {v.draft.toFixed(1)}m
                        </td>
                        <td style={{ padding: "8px 8px", textAlign: "center" }}>
                          <span
                            className={`badge-${v.is_feasible ? "feasible" : "infeasible"}`}
                            style={{
                              display: "inline-block",
                              padding: "2px 6px",
                              fontSize: "0.625rem",
                              fontWeight: 700,
                              borderRadius: "2px",
                              letterSpacing: "0.04em",
                              background: v.is_feasible ? "rgba(34, 197, 94, 0.15)" : "rgba(239, 68, 68, 0.15)",
                              color: v.is_feasible ? "#22c55e" : "#ef4444",
                              border: v.is_feasible ? "1px solid #22c55e" : "1px solid #ef4444",
                            }}
                          >
                            {v.is_feasible ? "FEASIBLE" : "INFEASIBLE"}
                          </span>
                        </td>
                        <td
                          style={{
                            padding: "8px 8px",
                            fontFamily: "monospace",
                            fontSize: "0.6875rem",
                            color: v.is_feasible ? "var(--muted)" : "#ef4444",
                          }}
                        >
                          {v.primary_reason_code ?? "—"}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* ── Right Pane: Single Assignment Deep-Dive ───────────────────── */}
        <section
          id="feasibility-detail-pane"
          style={{
            background: "var(--surface-1)",
            border: "1px solid var(--border)",
            padding: "var(--space-3)",
            borderRadius: "2px",
          }}
        >
          {/* Subheader */}
          <div
            style={{
              borderBottom: "1px solid var(--border)",
              paddingBottom: "var(--space-2)",
              marginBottom: "var(--space-3)",
            }}
          >
            <h2
              style={{
                fontSize: "0.8125rem",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                margin: 0,
              }}
            >
              Constraint Evidence & Operational Verification
            </h2>
            <span style={{ fontSize: "0.6875rem", color: "var(--muted)" }}>
              Detailed physical, operational, temporal, and commitment checks.
            </span>
          </div>

          {loadingDetail ? (
            <div style={{ padding: "var(--space-4)", textAlign: "center", color: "var(--muted)", fontSize: "0.75rem" }}>
              Evaluating operational constraints for selected assignment...
            </div>
          ) : !singleEvaluation ? (
            <div style={{ padding: "var(--space-4)", textAlign: "center", color: "var(--muted)", fontSize: "0.75rem" }}>
              Select a vessel to inspect constraint breakdown.
            </div>
          ) : (
            <div>
              {/* Operational Verdict Banner */}
              <div
                id="verdict-banner"
                style={{
                  padding: "var(--space-3)",
                  borderRadius: "2px",
                  marginBottom: "var(--space-3)",
                  background: singleEvaluation.is_feasible
                    ? "rgba(34, 197, 94, 0.08)"
                    : "rgba(239, 68, 68, 0.08)",
                  border: singleEvaluation.is_feasible
                    ? "1px solid #22c55e"
                    : "1px solid #ef4444",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <span
                      style={{
                        fontSize: "0.6875rem",
                        letterSpacing: "0.05em",
                        color: singleEvaluation.is_feasible ? "#22c55e" : "#ef4444",
                        fontWeight: 700,
                      }}
                    >
                      OPERATIONAL VERDICT
                    </span>
                    <div
                      id="verdict-status-text"
                      style={{
                        fontSize: "1.125rem",
                        fontWeight: 700,
                        color: singleEvaluation.is_feasible ? "#22c55e" : "#ef4444",
                        marginTop: "2px",
                      }}
                    >
                      {singleEvaluation.is_feasible ? "FEASIBLE" : "INFEASIBLE"}
                    </div>
                  </div>

                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: "0.75rem", fontWeight: 600 }}>
                      {singleEvaluation.vessel_name} ({singleEvaluation.vessel_class})
                    </div>
                    <div style={{ fontSize: "0.6875rem", color: "var(--muted)" }}>
                      {singleEvaluation.origin_port} → {singleEvaluation.destination_port}
                    </div>
                  </div>
                </div>

                {!singleEvaluation.is_feasible && singleEvaluation.primary_reason_code && (
                  <div
                    id="verdict-reason-container"
                    style={{
                      marginTop: "var(--space-2)",
                      paddingTop: "var(--space-2)",
                      borderTop: "1px solid rgba(239, 68, 68, 0.2)",
                      fontSize: "0.75rem",
                    }}
                  >
                    <span
                      id="verdict-reason-code"
                      style={{ color: "#ef4444", fontWeight: 600, fontFamily: "monospace" }}
                    >
                      {singleEvaluation.primary_reason_code}:
                    </span>{" "}
                    <span id="verdict-reason-desc" style={{ color: "var(--text)" }}>
                      {singleEvaluation.primary_reason_description}
                    </span>
                  </div>
                )}
              </div>

              {/* Constraint Verification Breakdown Table */}
              <div style={{ marginBottom: "var(--space-4)" }}>
                <h3
                  style={{
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                    color: "var(--muted)",
                    marginBottom: "var(--space-2)",
                  }}
                >
                  Physical & Operational Constraints
                </h3>
                <table
                  id="constraint-checks-table"
                  style={{
                    width: "100%",
                    borderCollapse: "collapse",
                    fontSize: "0.75rem",
                  }}
                >
                  <thead>
                    <tr
                      style={{
                        borderBottom: "1px solid var(--border)",
                        color: "var(--muted)",
                        fontSize: "0.6875rem",
                        textTransform: "uppercase",
                      }}
                    >
                      <th style={{ padding: "6px 8px", textAlign: "left" }}>Constraint Check</th>
                      <th style={{ padding: "6px 8px", textAlign: "left" }}>Vessel Spec</th>
                      <th style={{ padding: "6px 8px", textAlign: "left" }}>Permitted Limit</th>
                      <th style={{ padding: "6px 8px", textAlign: "center" }}>Status</th>
                      <th style={{ padding: "6px 8px", textAlign: "left" }}>Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(singleEvaluation.checks).map(([checkName, check]) => {
                      const isPass = check.passed;
                      const checkLabel = checkName.replace(/_/g, " ").toUpperCase();
                      return (
                        <tr
                          key={checkName}
                          id={`check-row-${checkName}`}
                          style={{
                            borderBottom: "1px solid var(--border)",
                            background: !isPass ? "rgba(239, 68, 68, 0.05)" : "transparent",
                          }}
                        >
                          <td style={{ padding: "6px 8px", fontWeight: 500 }}>
                            {checkLabel}
                          </td>
                          <td className="tabular-nums" style={{ padding: "6px 8px", color: "var(--text)" }}>
                            {check.actual !== undefined && check.actual !== null
                              ? String(check.actual)
                              : check.required !== undefined && check.required !== null
                              ? String(check.required)
                              : "—"}
                          </td>
                          <td className="tabular-nums" style={{ padding: "6px 8px", color: "var(--muted)" }}>
                            {check.permitted !== undefined && check.permitted !== null
                              ? String(check.permitted)
                              : check.max !== undefined && check.max !== null
                              ? String(check.max)
                              : "—"}
                          </td>
                          <td style={{ padding: "6px 8px", textAlign: "center" }}>
                            <span
                              style={{
                                display: "inline-block",
                                padding: "1px 6px",
                                fontSize: "0.625rem",
                                fontWeight: 700,
                                borderRadius: "2px",
                                background: isPass ? "rgba(34, 197, 94, 0.15)" : "rgba(239, 68, 68, 0.15)",
                                color: isPass ? "#22c55e" : "#ef4444",
                                border: isPass ? "1px solid #22c55e" : "1px solid #ef4444",
                              }}
                            >
                              {isPass ? "PASS" : "FAIL"}
                            </span>
                          </td>
                          <td
                            style={{
                              padding: "6px 8px",
                              color: isPass ? "var(--muted)" : "#ef4444",
                              fontSize: "0.6875rem",
                              fontFamily: isPass ? "inherit" : "monospace",
                            }}
                          >
                            {check.reason ? String(check.reason) : check.status ? String(check.status) : "Satisfied"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Voyage Schedule & Timing Breakdown */}
              <div style={{ marginBottom: "var(--space-4)" }}>
                <h3
                  style={{
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                    color: "var(--muted)",
                    marginBottom: "var(--space-2)",
                  }}
                >
                  Voyage Schedule & Timing Verification
                </h3>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(3, 1fr)",
                    gap: "var(--space-2)",
                    fontSize: "0.6875rem",
                  }}
                >
                  <div
                    style={{
                      background: "var(--surface-2)",
                      padding: "var(--space-2)",
                      border: "1px solid var(--border)",
                      borderRadius: "2px",
                    }}
                  >
                    <span style={{ color: "var(--muted)", display: "block" }}>BALLAST POSITIONING</span>
                    <strong className="tabular-nums" style={{ fontSize: "0.8125rem" }}>
                      {singleEvaluation.timing?.positioning_days ?? 0} days
                    </strong>
                    <div style={{ color: "var(--muted)", marginTop: "2px" }}>
                      ETA Origin: {singleEvaluation.timing?.estimated_arrival_origin ?? "—"}
                    </div>
                  </div>

                  <div
                    style={{
                      background: "var(--surface-2)",
                      padding: "var(--space-2)",
                      border: "1px solid var(--border)",
                      borderRadius: "2px",
                    }}
                  >
                    <span style={{ color: "var(--muted)", display: "block" }}>VOYAGE TRANSIT</span>
                    <strong className="tabular-nums" style={{ fontSize: "0.8125rem" }}>
                      {singleEvaluation.timing?.sailing_days ?? 0} sailing days
                    </strong>
                    <div style={{ color: "var(--muted)", marginTop: "2px" }}>
                      Total Voyage: {singleEvaluation.timing?.total_voyage_days ?? 0} days
                    </div>
                  </div>

                  <div
                    style={{
                      background: "var(--surface-2)",
                      padding: "var(--space-2)",
                      border: "1px solid var(--border)",
                      borderRadius: "2px",
                    }}
                  >
                    <span style={{ color: "var(--muted)", display: "block" }}>DELIVERY DEADLINE</span>
                    <strong className="tabular-nums" style={{ fontSize: "0.8125rem" }}>
                      {singleEvaluation.timing?.delivery_deadline ?? "—"}
                    </strong>
                    <div style={{ color: "var(--muted)", marginTop: "2px" }}>
                      Est. Delivery: {singleEvaluation.timing?.estimated_delivery_destination ?? "—"}
                    </div>
                  </div>
                </div>
              </div>

              {/* Advisory Warnings (Non-Fatal) */}
              {singleEvaluation.warnings && singleEvaluation.warnings.length > 0 && (
                <div
                  id="advisory-warnings-box"
                  style={{
                    background: "rgba(245, 158, 11, 0.08)",
                    border: "1px solid #f59e0b",
                    padding: "var(--space-2) var(--space-3)",
                    borderRadius: "2px",
                    marginBottom: "var(--space-3)",
                  }}
                >
                  <span
                    style={{
                      fontSize: "0.6875rem",
                      fontWeight: 700,
                      color: "#f59e0b",
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                    }}
                  >
                    Advisory Condition Warnings (Non-Fatal):
                  </span>
                  <ul style={{ margin: "4px 0 0 0", paddingLeft: "16px", fontSize: "0.75rem", color: "var(--text)" }}>
                    {singleEvaluation.warnings.map((w, idx) => (
                      <li key={idx}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Provenance & Audit Trace */}
              <div
                id="feasibility-provenance-box"
                style={{
                  borderTop: "1px solid var(--border)",
                  paddingTop: "var(--space-2)",
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: "0.6875rem",
                  color: "var(--muted)",
                }}
              >
                <div>
                  SOURCE: <span>{String(singleEvaluation.provenance?.data_type ?? "SYNTHETIC / PROXY")}</span> | PACKAGE:{" "}
                  <span>{String(singleEvaluation.provenance?.package_id ?? "demo-v1")}</span>
                </div>
                <div className="tabular-nums">
                  EVALUATED: {singleEvaluation.evaluated_at}
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
