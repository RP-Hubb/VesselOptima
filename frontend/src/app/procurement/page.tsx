"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import {
  getCargoRequirements,
  getProcurementProfiles,
  compareProcurementStrategies,
} from "@/lib/api";
import type {
  CargoRequirementItem,
  ProcurementProfileItem,
  ProcurementCompareResponse,
  StrategyEvaluationItem,
} from "@/types/api";

const DEFAULT_AS_OF_DATE = "2026-09-01";

export default function ProcurementPage() {
  const [cargos, setCargos] = useState<CargoRequirementItem[]>([]);
  const [selectedCargoId, setSelectedCargoId] = useState<number | null>(null);
  const [profiles, setProfiles] = useState<ProcurementProfileItem[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string>("STANDARD_COMMERCIAL");
  const [asOfDate, setAsOfDate] = useState<string>(DEFAULT_AS_OF_DATE);
  const [comparisonData, setComparisonData] = useState<ProcurementCompareResponse | null>(null);
  const [selectedStrategyType, setSelectedStrategyType] = useState<string>("SPOT");
  const [filterMode, setFilterMode] = useState<"ALL" | "FEASIBLE" | "INFEASIBLE">("ALL");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Custom stage sliders toggle & state
  const [showCustomSliders, setShowCustomSliders] = useState<boolean>(false);
  const [customStages, setCustomStages] = useState({
    tender_preparation_days: 3.0,
    bid_submission_days: 4.0,
    technical_evaluation_days: 2.0,
    commercial_evaluation_days: 2.0,
    approval_days: 2.0,
    award_days: 1.0,
  });

  // Load cargo requirements and procurement profiles on mount
  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([getCargoRequirements(), getProcurementProfiles()])
      .then(([cargoItems, profileRes]) => {
        setCargos(cargoItems);
        if (cargoItems.length > 0) {
          setSelectedCargoId(cargoItems[0].id);
        }
        setProfiles(profileRes.profiles);
        if (profileRes.default_profile_id) {
          setSelectedProfileId(profileRes.default_profile_id);
        }
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to initialize procurement workspace");
        setLoading(false);
      });
  }, []);

  // Fetch strategy evaluation whenever cargo, profile, asOfDate, or customStages change
  const runEvaluation = useCallback(() => {
    if (selectedCargoId === null) return;
    setLoading(true);
    setError(null);

    const isCustom = selectedProfileId === "CUSTOM";
    compareProcurementStrategies({
      cargo_id: selectedCargoId,
      profile_id: isCustom ? undefined : selectedProfileId,
      as_of_date: asOfDate,
      custom_stages: isCustom ? customStages : undefined,
      persist: false,
    })
      .then((data) => {
        setComparisonData(data);
        setLoading(false);
        // Ensure selected strategy exists in results
        if (data.strategies.length > 0) {
          const exists = data.strategies.some((s) => s.strategy_type === selectedStrategyType);
          if (!exists) {
            setSelectedStrategyType(data.strategies[0].strategy_type);
          }
        }
      })
      .catch((err) => {
        setError(err.message || "Failed to evaluate procurement strategies");
        setLoading(false);
      });
  }, [selectedCargoId, selectedProfileId, asOfDate, customStages, selectedStrategyType]);

  useEffect(() => {
    runEvaluation();
  }, [runEvaluation]);

  // Active cargo requirement
  const currentCargo = useMemo(() => {
    return cargos.find((c) => c.id === selectedCargoId) || null;
  }, [cargos, selectedCargoId]);

  // Active profile object
  const currentProfile = useMemo(() => {
    if (selectedProfileId === "CUSTOM") {
      const sum = Object.values(customStages).reduce((a, b) => a + b, 0);
      return {
        profile_id: "CUSTOM",
        name: "Custom User-Defined Profile",
        ...customStages,
        minimum_lead_time_days: sum,
        description: "User-defined procurement lead time stages",
      };
    }
    return profiles.find((p) => p.profile_id === selectedProfileId) || null;
  }, [profiles, selectedProfileId, customStages]);

  // Selected strategy evaluation object
  const selectedStrategy = useMemo(() => {
    if (!comparisonData) return null;
    return comparisonData.strategies.find((s) => s.strategy_type === selectedStrategyType) || comparisonData.strategies[0] || null;
  }, [comparisonData, selectedStrategyType]);

  // Filtered strategies for the table
  const displayedStrategies = useMemo(() => {
    if (!comparisonData) return [];
    if (filterMode === "FEASIBLE") return comparisonData.strategies.filter((s) => s.status === "FEASIBLE");
    if (filterMode === "INFEASIBLE") return comparisonData.strategies.filter((s) => s.status === "INFEASIBLE");
    return comparisonData.strategies;
  }, [comparisonData, filterMode]);

  // Demonstration test presets
  const handleSelectScenario = (scenario: "A" | "B" | "C" | "D") => {
    if (scenario === "A") {
      // Spot Viable: Cargo 1, Standard Commercial (14d), asOf 2026-09-01 -> laycan 2026-09-18 (viable window)
      setSelectedCargoId(1);
      setSelectedProfileId("STANDARD_COMMERCIAL");
      setShowCustomSliders(false);
      setAsOfDate("2026-09-01");
      setSelectedStrategyType("SPOT");
    } else if (scenario === "B") {
      // Lead Time Infeasible: Cargo 1, Strict Government (21d), asOf 2026-09-01 -> 21d completion 2026-09-22 > laycan 2026-09-18
      setSelectedCargoId(1);
      setSelectedProfileId("STRICT_GOVERNMENT");
      setShowCustomSliders(false);
      setAsOfDate("2026-09-01");
      setSelectedStrategyType("SPOT");
    } else if (scenario === "C") {
      // Forecast Trajectory / Spread: Expedited Spot (4d), Cargo 2 or 3
      setSelectedCargoId(2);
      setSelectedProfileId("EXPEDITED_SPOT");
      setShowCustomSliders(false);
      setAsOfDate("2026-09-01");
      setSelectedStrategyType("SHORT_TERM");
    } else if (scenario === "D") {
      // Feasibility Constrained Fleet: Cargo 4
      setSelectedCargoId(4);
      setSelectedProfileId("STANDARD_COMMERCIAL");
      setShowCustomSliders(false);
      setAsOfDate("2026-09-01");
      setSelectedStrategyType("MULTI_VOYAGE");
    }
  };

  // Helper formatting badges
  const renderTimingBadge = (signal?: string | null, remainingDays?: number) => {
    if (!signal) return <span style={{ color: "var(--muted)" }}>N/A</span>;
    let bg = "var(--surface-2)";
    let border = "var(--border)";
    let text = "var(--text)";
    const label = signal.replace(/_/g, " ");

    if (signal === "WINDOW_OPEN") {
      bg = "rgba(34, 197, 94, 0.15)";
      border = "var(--success, #22c55e)";
      text = "var(--success, #22c55e)";
    } else if (signal === "WINDOW_CLOSING") {
      bg = "rgba(234, 179, 8, 0.15)";
      border = "#eab308";
      text = "#facc15";
    } else if (signal === "IMMEDIATE_PROCURE") {
      bg = "rgba(249, 115, 22, 0.2)";
      border = "#f97316";
      text = "#fb923c";
    } else if (signal === "LEAD_TIME_EXCEEDED" || signal === "DEADLINE_MISSED" || signal === "WINDOW_INVALID") {
      bg = "rgba(239, 68, 68, 0.18)";
      border = "var(--danger, #ef4444)";
      text = "var(--danger, #ef4444)";
    }

    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "4px",
          background: bg,
          border: `1px solid ${border}`,
          color: text,
          fontSize: "0.6875rem",
          fontWeight: 600,
          padding: "2px 8px",
          borderRadius: "2px",
          fontFamily: "var(--font-mono, monospace)",
          textTransform: "uppercase",
        }}
      >
        {label}
        {remainingDays !== undefined && (
          <span style={{ opacity: 0.85, fontSize: "0.625rem" }}>
            ({remainingDays >= 0 ? `+${remainingDays.toFixed(1)}d` : `${remainingDays.toFixed(1)}d`})
          </span>
        )}
      </span>
    );
  };

  const renderStatusBadge = (status: string) => {
    const isFeasible = status === "FEASIBLE";
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          padding: "2px 8px",
          borderRadius: "2px",
          fontSize: "0.6875rem",
          fontWeight: 700,
          letterSpacing: "0.04em",
          background: isFeasible ? "rgba(34, 197, 94, 0.15)" : "rgba(239, 68, 68, 0.15)",
          border: `1px solid ${isFeasible ? "var(--success, #22c55e)" : "var(--danger, #ef4444)"}`,
          color: isFeasible ? "var(--success, #22c55e)" : "var(--danger, #ef4444)",
        }}
      >
        {status}
      </span>
    );
  };

  const renderTrajectoryBadge = (slope?: string, uncertainty?: string) => {
    if (!slope) return <span style={{ color: "var(--muted)" }}>N/A</span>;
    let arrow = "→";
    let color = "var(--text)";
    if (slope === "FORECAST_DECREASING") {
      arrow = "↓";
      color = "#60a5fa";
    } else if (slope === "FORECAST_INCREASING") {
      arrow = "↑";
      color = "#f87171";
    } else {
      arrow = "↔";
      color = "#a3a3a3";
    }

    return (
      <span style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono, monospace)" }}>
        <span style={{ color, fontWeight: 700, marginRight: "4px" }}>{arrow} {slope.replace("FORECAST_", "")}</span>
        {uncertainty && (
          <span
            style={{
              fontSize: "0.625rem",
              padding: "1px 4px",
              borderRadius: "2px",
              background: "var(--surface-3)",
              color: uncertainty === "HIGH" ? "#fb923c" : "var(--muted)",
              marginLeft: "4px",
            }}
          >
            UNCERTAINTY: {uncertainty}
          </span>
        )}
      </span>
    );
  };

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
              Dynamic Procurement Strategy & Timing Engine
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
              PHASE 5 — PROCUREMENT STRATEGY
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
            Decision boundary layer between Feasibility & MILP Optimization:{" "}
            <strong style={{ color: "var(--text)" }}>Observe → Forecast → Constrain → Procurement Strategy → Optimize</strong>
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

      {/* ── Demonstration Scenario Quick Selectors ──────────────────────── */}
      <section
        style={{
          background: "var(--surface-1)",
          border: "1px solid var(--border)",
          padding: "var(--space-2) var(--space-3)",
          marginBottom: "var(--space-4)",
          borderRadius: "2px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "var(--space-2)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <span
            style={{
              fontSize: "0.6875rem",
              color: "var(--muted)",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.04em",
            }}
          >
            Audit Presets:
          </span>
          <button
            id="preset-scenario-a"
            onClick={() => handleSelectScenario("A")}
            style={{
              background: "var(--surface-2)",
              border: "1px solid var(--border)",
              color: "var(--text)",
              padding: "4px 10px",
              fontSize: "0.75rem",
              borderRadius: "2px",
              cursor: "pointer",
            }}
            title="Cargo 1 with Standard 14d Commercial profile — Spot and Short-term viable"
          >
            Case A: Spot Feasible (14d Lead Time)
          </button>
          <button
            id="preset-scenario-b"
            onClick={() => handleSelectScenario("B")}
            style={{
              background: "rgba(239, 68, 68, 0.1)",
              border: "1px solid var(--danger, #ef4444)",
              color: "var(--danger, #ef4444)",
              padding: "4px 10px",
              fontSize: "0.75rem",
              borderRadius: "2px",
              cursor: "pointer",
              fontWeight: 600,
            }}
            title="Cargo 1 with Strict 21d Government profile — Laycan exceeded, flags INFEASIBLE"
          >
            Case B: Lead Time Infeasible (21d Govt Profile)
          </button>
          <button
            id="preset-scenario-c"
            onClick={() => handleSelectScenario("C")}
            style={{
              background: "var(--surface-2)",
              border: "1px solid var(--border)",
              color: "var(--text)",
              padding: "4px 10px",
              fontSize: "0.75rem",
              borderRadius: "2px",
              cursor: "pointer",
            }}
            title="Expedited 4d Spot profile showing forecast signal and 95% spread"
          >
            Case C: Expedited Spot + Forecast Spread
          </button>
          <button
            id="preset-scenario-d"
            onClick={() => handleSelectScenario("D")}
            style={{
              background: "var(--surface-2)",
              border: "1px solid var(--border)",
              color: "var(--text)",
              padding: "4px 10px",
              fontSize: "0.75rem",
              borderRadius: "2px",
              cursor: "pointer",
            }}
            title="Fleet Feasibility Filtering (Phase 4 handoff verification)"
          >
            Case D: Fleet Feasibility Admittance
          </button>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "0.75rem" }}>
          <span style={{ color: "var(--muted)" }}>Evaluation Date:</span>
          <input
            type="date"
            value={asOfDate}
            onChange={(e) => setAsOfDate(e.target.value)}
            style={{
              background: "var(--surface-2)",
              border: "1px solid var(--border)",
              color: "var(--text)",
              padding: "2px 6px",
              fontSize: "0.75rem",
              borderRadius: "2px",
              fontFamily: "var(--font-mono, monospace)",
            }}
          />
        </div>
      </section>

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
          <strong>Procurement Evaluation Error:</strong> {error}
        </div>
      )}

      {/* ── Cargo & Profile Configuration Bar ───────────────────────────── */}
      <section
        style={{
          background: "var(--surface-1)",
          border: "1px solid var(--border)",
          padding: "var(--space-3)",
          marginBottom: "var(--space-4)",
          borderRadius: "2px",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "var(--space-3)",
        }}
      >
        {/* Cargo Selector */}
        <div>
          <label
            htmlFor="cargo-select"
            style={{
              fontSize: "0.6875rem",
              color: "var(--muted)",
              textTransform: "uppercase",
              letterSpacing: "0.04em",
              fontWeight: 600,
              display: "block",
              marginBottom: "4px",
            }}
          >
            Cargo Requirement
          </label>
          <select
            id="cargo-select"
            value={selectedCargoId ?? ""}
            onChange={(e) => setSelectedCargoId(Number(e.target.value))}
            style={{
              width: "100%",
              background: "var(--surface-2)",
              color: "var(--text)",
              border: "1px solid var(--border)",
              padding: "6px 10px",
              fontSize: "0.8125rem",
              borderRadius: "2px",
              outline: "none",
              cursor: "pointer",
            }}
          >
            {cargos.map((c) => (
              <option key={c.id} value={c.id}>
                CARGO-{String(c.id).padStart(3, "0")}: {c.commodity} ({c.volume_mt.toLocaleString()} MT) | {c.origin_port_name ?? `Port ${c.origin_port_id}`} → {c.destination_port_name ?? `Port ${c.destination_port_id}`}
              </option>
            ))}
          </select>
          {currentCargo && (
            <div
              style={{
                fontSize: "0.6875rem",
                color: "var(--muted)",
                marginTop: "6px",
                display: "flex",
                gap: "12px",
                flexWrap: "wrap",
                fontFamily: "var(--font-mono, monospace)",
              }}
            >
              <span>Laycan: <strong style={{ color: "var(--text)" }}>{currentCargo.loading_window_start}</strong> → <strong style={{ color: "var(--text)" }}>{currentCargo.loading_window_end}</strong></span>
              <span>Deadline: <strong style={{ color: "var(--text)" }}>{currentCargo.delivery_deadline}</strong></span>
            </div>
          )}
        </div>

        {/* Profile Selector */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
            <label
              htmlFor="profile-select"
              style={{
                fontSize: "0.6875rem",
                color: "var(--muted)",
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                fontWeight: 600,
              }}
            >
              Procurement Lead Time Profile
            </label>
            <button
              onClick={() => {
                setShowCustomSliders(!showCustomSliders);
                if (!showCustomSliders) setSelectedProfileId("CUSTOM");
              }}
              style={{
                background: "transparent",
                border: "none",
                color: "var(--accent, #38bdf8)",
                fontSize: "0.6875rem",
                cursor: "pointer",
                padding: 0,
                textDecoration: "underline",
              }}
            >
              {showCustomSliders ? "Use Presets" : "Configure Custom Stages"}
            </button>
          </div>
          <select
            id="profile-select"
            value={selectedProfileId}
            onChange={(e) => {
              setSelectedProfileId(e.target.value);
              if (e.target.value !== "CUSTOM") setShowCustomSliders(false);
            }}
            style={{
              width: "100%",
              background: "var(--surface-2)",
              color: "var(--text)",
              border: "1px solid var(--border)",
              padding: "6px 10px",
              fontSize: "0.8125rem",
              borderRadius: "2px",
              outline: "none",
              cursor: "pointer",
            }}
          >
            {profiles.map((p) => (
              <option key={p.profile_id} value={p.profile_id}>
                {p.name} ({p.minimum_lead_time_days} days total)
              </option>
            ))}
            <option value="CUSTOM">Custom User-Defined Profile ({Object.values(customStages).reduce((a, b) => a + b, 0)} days)</option>
          </select>

          {currentProfile && (
            <div style={{ fontSize: "0.6875rem", color: "var(--muted)", marginTop: "6px" }}>
              {currentProfile.description}
            </div>
          )}
        </div>

        {/* Lead Time Summary Box */}
        <div
          style={{
            background: "var(--surface-2)",
            border: "1px solid var(--border)",
            padding: "8px 12px",
            borderRadius: "2px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <span style={{ fontSize: "0.6875rem", color: "var(--muted)", textTransform: "uppercase" }}>Minimum Required Lead Time</span>
            <span style={{ fontSize: "1.125rem", fontWeight: 700, fontFamily: "var(--font-mono, monospace)" }}>
              {currentProfile?.minimum_lead_time_days.toFixed(1)} <span style={{ fontSize: "0.75rem", fontWeight: 400, color: "var(--muted)" }}>days</span>
            </span>
          </div>

          {comparisonData && comparisonData.strategies.length > 0 && (
            <div style={{ marginTop: "6px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.6875rem", color: "var(--muted)" }}>Timing Window Status:</span>
              {renderTimingBadge(
                comparisonData.strategies[0].timing_signal,
                comparisonData.strategies[0].timing?.remaining_decision_window_days
              )}
            </div>
          )}
        </div>
      </section>

      {/* ── Custom Stage Sliders (Visible if configured) ────────────────── */}
      {showCustomSliders && (
        <section
          style={{
            background: "var(--surface-2)",
            border: "1px solid var(--border)",
            padding: "var(--space-3)",
            marginBottom: "var(--space-4)",
            borderRadius: "2px",
          }}
        >
          <div style={{ fontSize: "0.75rem", fontWeight: 600, marginBottom: "var(--space-2)", textTransform: "uppercase" }}>
            Stage Duration Tuning (Days)
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
            {Object.entries(customStages).map(([key, val]) => (
              <div key={key}>
                <label style={{ fontSize: "0.6875rem", color: "var(--muted)", textTransform: "capitalize" }}>
                  {key.replace(/_/g, " ").replace("days", "")}: <strong>{val}d</strong>
                </label>
                <input
                  type="range"
                  min="0.5"
                  max="10"
                  step="0.5"
                  value={val}
                  onChange={(e) =>
                    setCustomStages((prev) => ({
                      ...prev,
                      [key]: parseFloat(e.target.value),
                    }))
                  }
                  style={{ width: "100%" }}
                />
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Lead Time Stage Breakdown Bar ───────────────────────────────── */}
      {currentProfile && (
        <section
          style={{
            background: "var(--surface-1)",
            border: "1px solid var(--border)",
            padding: "var(--space-3)",
            marginBottom: "var(--space-4)",
            borderRadius: "2px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <span style={{ fontSize: "0.6875rem", color: "var(--muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em" }}>
              Procurement Process Stage Distribution ({currentProfile.minimum_lead_time_days.toFixed(1)} Days Total)
            </span>
            <span style={{ fontSize: "0.6875rem", color: "var(--muted)", fontFamily: "var(--font-mono, monospace)" }}>
              As of: {asOfDate} → Earliest Completion:{" "}
              <strong style={{ color: "var(--text)" }}>
                {comparisonData?.strategies[0]?.timing?.procurement_completion_date ?? "Calculating..."}
              </strong>
            </span>
          </div>

          {/* Segmented Bar */}
          <div
            style={{
              display: "flex",
              height: "22px",
              width: "100%",
              borderRadius: "2px",
              overflow: "hidden",
              border: "1px solid var(--border)",
            }}
          >
            {[
              { label: "Prep", days: currentProfile.tender_preparation_days, color: "#38bdf8" },
              { label: "Bids", days: currentProfile.bid_submission_days, color: "#818cf8" },
              { label: "Tech Eval", days: currentProfile.technical_evaluation_days, color: "#c084fc" },
              { label: "Comm Eval", days: currentProfile.commercial_evaluation_days, color: "#f472b6" },
              { label: "Approval", days: currentProfile.approval_days, color: "#fb923c" },
              { label: "Award", days: currentProfile.award_days, color: "#4ade80" },
            ].map((stage, idx) => {
              const pct = (stage.days / (currentProfile.minimum_lead_time_days || 1)) * 100;
              return (
                <div
                  key={idx}
                  style={{
                    width: `${pct}%`,
                    background: stage.color,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#0f172a",
                    fontSize: "0.625rem",
                    fontWeight: 700,
                    overflow: "hidden",
                    whiteSpace: "nowrap",
                    textOverflow: "ellipsis",
                    padding: "0 2px",
                  }}
                  title={`${stage.label}: ${stage.days} days (${pct.toFixed(1)}%)`}
                >
                  {stage.days >= 1 ? `${stage.label} (${stage.days}d)` : stage.days}
                </div>
              );
            })}
          </div>

          {/* Milestone timeline markers */}
          {comparisonData && comparisonData.strategies[0]?.timing && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: "var(--space-2)",
                marginTop: "10px",
                fontSize: "0.6875rem",
                fontFamily: "var(--font-mono, monospace)",
                color: "var(--muted)",
              }}
            >
              <div>
                <span>Evaluation Start (As-of): </span>
                <strong style={{ color: "var(--text)" }}>{comparisonData.strategies[0].timing.as_of_date}</strong>
              </div>
              <div>
                <span>Earliest Procurement Completion: </span>
                <strong style={{ color: "var(--text)" }}>{comparisonData.strategies[0].timing.procurement_completion_date}</strong>
              </div>
              <div>
                <span>Laycan Window Start: </span>
                <strong style={{ color: "var(--text)" }}>{comparisonData.strategies[0].timing.origin_laycan_start}</strong>
              </div>
              <div>
                <span>Latest Safe Procurement Date: </span>
                <strong style={{ color: "var(--text)" }}>{comparisonData.strategies[0].timing.latest_safe_procurement_date}</strong>
              </div>
            </div>
          )}
        </section>
      )}

      {/* ── Candidate Strategy Comparison Table ─────────────────────────── */}
      <section style={{ marginBottom: "var(--space-4)" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "var(--space-2)",
            flexWrap: "wrap",
            gap: "var(--space-2)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <h2
              style={{
                fontSize: "0.875rem",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                margin: 0,
              }}
            >
              Candidate Strategy Evaluation Matrix
            </h2>
            <span style={{ fontSize: "0.6875rem", color: "var(--muted)" }}>
              ({displayedStrategies.length} strategies evaluated | Select row to inspect evidence)
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <span style={{ fontSize: "0.6875rem", color: "var(--muted)", textTransform: "uppercase" }}>Filter:</span>
            {(["ALL", "FEASIBLE", "INFEASIBLE"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setFilterMode(mode)}
                style={{
                  background: filterMode === mode ? "var(--surface-3)" : "var(--surface-1)",
                  border: `1px solid ${filterMode === mode ? "var(--accent)" : "var(--border)"}`,
                  color: filterMode === mode ? "var(--text)" : "var(--muted)",
                  padding: "2px 8px",
                  fontSize: "0.6875rem",
                  borderRadius: "2px",
                  cursor: "pointer",
                }}
              >
                {mode}
              </button>
            ))}
          </div>
        </div>

        {/* Table */}
        <div
          style={{
            background: "var(--surface-1)",
            border: "1px solid var(--border)",
            borderRadius: "2px",
            overflowX: "auto",
          }}
        >
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "0.75rem",
              textAlign: "left",
            }}
          >
            <thead>
              <tr style={{ background: "var(--surface-2)", borderBottom: "1px solid var(--border)" }}>
                <th style={{ padding: "8px 12px", color: "var(--muted)", fontWeight: 600 }}>STRATEGY TYPE</th>
                <th style={{ padding: "8px 12px", color: "var(--muted)", fontWeight: 600 }}>STATUS</th>
                <th style={{ padding: "8px 12px", color: "var(--muted)", fontWeight: 600 }}>TIMING WINDOW</th>
                <th style={{ padding: "8px 12px", color: "var(--muted)", fontWeight: 600 }}>STRUCTURE / VOYAGES</th>
                <th style={{ padding: "8px 12px", color: "var(--muted)", fontWeight: 600 }}>FORECAST SIGNAL</th>
                <th style={{ padding: "8px 12px", color: "var(--muted)", fontWeight: 600 }}>ADMITTED FLEET</th>
                <th style={{ padding: "8px 12px", color: "var(--muted)", fontWeight: 600, textAlign: "right" }}>EXPECTED TOTAL COST</th>
                <th style={{ padding: "8px 12px", color: "var(--muted)", fontWeight: 600 }}>OPTIMIZATION CANDIDACY</th>
              </tr>
            </thead>
            <tbody>
              {displayedStrategies.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ padding: "24px", textAlign: "center", color: "var(--muted)" }}>
                    {loading ? "Evaluating candidate strategies..." : "No strategies match the active filter."}
                  </td>
                </tr>
              ) : (
                displayedStrategies.map((strat) => {
                  const isSelected = selectedStrategyType === strat.strategy_type;
                  const isFeasible = strat.status === "FEASIBLE";
                  const candidateCount = strat.feasibility_summary?.feasible_vessels_count ?? 0;
                  const fleetSize = strat.feasibility_summary?.candidate_fleet_size ?? 0;
                  const totalCost = strat.cost_summary?.expected_total_cost;

                  return (
                    <tr
                      key={strat.strategy_type}
                      onClick={() => setSelectedStrategyType(strat.strategy_type)}
                      style={{
                        borderBottom: "1px solid var(--border)",
                        background: isSelected ? "var(--surface-2)" : "transparent",
                        cursor: "pointer",
                        transition: "background 100ms ease",
                      }}
                    >
                      <td style={{ padding: "10px 12px" }}>
                        <div style={{ fontWeight: 600, color: "var(--text)" }}>{strat.strategy_name}</div>
                        <div style={{ fontSize: "0.6875rem", color: "var(--muted)" }}>{strat.strategy_type}</div>
                      </td>
                      <td style={{ padding: "10px 12px" }}>
                        {renderStatusBadge(strat.status)}
                      </td>
                      <td style={{ padding: "10px 12px" }}>
                        {renderTimingBadge(
                          strat.timing_signal,
                          strat.timing?.remaining_decision_window_days
                        )}
                      </td>
                      <td style={{ padding: "10px 12px", fontFamily: "var(--font-mono, monospace)" }}>
                        <div>{strat.contract_duration_days ? `${strat.contract_duration_days}d` : "Spot"}</div>
                        <div style={{ fontSize: "0.6875rem", color: "var(--muted)" }}>
                          {strat.voyage_count ?? 1} voyage{strat.voyage_count && strat.voyage_count > 1 ? "s" : ""}
                        </div>
                      </td>
                      <td style={{ padding: "10px 12px" }}>
                        {renderTrajectoryBadge(
                          strat.forecast_evidence?.trajectory_slope,
                          strat.forecast_evidence?.uncertainty_level
                        )}
                      </td>
                      <td style={{ padding: "10px 12px", fontFamily: "var(--font-mono, monospace)" }}>
                        <span style={{ color: candidateCount > 0 ? "var(--text)" : "var(--danger)" }}>
                          {candidateCount}
                        </span>
                        <span style={{ color: "var(--muted)" }}> / {fleetSize} vessels</span>
                      </td>
                      <td style={{ padding: "10px 12px", textAlign: "right", fontFamily: "var(--font-mono, monospace)" }}>
                        {totalCost !== undefined ? (
                          <>
                            <div style={{ fontWeight: 600 }}>${totalCost.toLocaleString()}</div>
                            {currentCargo?.volume_mt && (
                              <div style={{ fontSize: "0.6875rem", color: "var(--muted)" }}>
                                ${(totalCost / currentCargo.volume_mt).toFixed(2)}/MT
                              </div>
                            )}
                          </>
                        ) : (
                          <span style={{ color: "var(--muted)" }}>N/A</span>
                        )}
                      </td>
                      <td style={{ padding: "10px 12px" }}>
                        {isFeasible ? (
                          <span
                            style={{
                              fontSize: "0.6875rem",
                              fontWeight: 600,
                              color: "var(--accent, #38bdf8)",
                              background: "rgba(56, 189, 248, 0.1)",
                              border: "1px solid rgba(56, 189, 248, 0.3)",
                              padding: "2px 6px",
                              borderRadius: "2px",
                              letterSpacing: "0.03em",
                            }}
                          >
                            READY FOR OPTIMIZATION
                          </span>
                        ) : (
                          <span
                            style={{
                              fontSize: "0.6875rem",
                              fontWeight: 500,
                              color: "var(--muted)",
                            }}
                          >
                            REJECTED ({strat.primary_reason_code ?? "INADMISSIBLE"})
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Deep-Dive Diagnostic & Audit Panel ──────────────────────────── */}
      {selectedStrategy && (
        <section
          style={{
            background: "var(--surface-1)",
            border: "1px solid var(--border)",
            borderRadius: "2px",
            padding: "var(--space-3)",
            marginBottom: "var(--space-4)",
          }}
        >
          <div
            style={{
              borderBottom: "1px solid var(--border)",
              paddingBottom: "var(--space-2)",
              marginBottom: "var(--space-3)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "var(--space-2)",
            }}
          >
            <div>
              <span style={{ fontSize: "0.6875rem", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                Deep-Dive Strategy Inspection:
              </span>
              <div style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text)", display: "flex", alignItems: "center", gap: "8px" }}>
                {selectedStrategy.strategy_name} ({selectedStrategy.strategy_type})
                {renderStatusBadge(selectedStrategy.status)}
              </div>
            </div>

            <div style={{ fontSize: "0.6875rem", color: "var(--muted)", fontFamily: "var(--font-mono, monospace)" }}>
              Candidacy Boundary:{" "}
              <strong style={{ color: selectedStrategy.status === "FEASIBLE" ? "var(--success)" : "var(--danger)" }}>
                {selectedStrategy.status === "FEASIBLE" ? "Admitted to MILP Fleet Allocation" : "Excluded from Downstream Optimizer"}
              </strong>
            </div>
          </div>

          {/* Infeasibility Reason Alert if failed */}
          {selectedStrategy.status === "INFEASIBLE" && (
            <div
              style={{
                background: "rgba(239, 68, 68, 0.12)",
                border: "1px solid var(--danger)",
                padding: "10px 14px",
                borderRadius: "2px",
                marginBottom: "var(--space-3)",
                fontSize: "0.75rem",
              }}
            >
              <div style={{ fontWeight: 700, color: "var(--danger)", display: "flex", alignItems: "center", gap: "6px" }}>
                <span>⚠ EXCLUSION EVIDENCE: {selectedStrategy.primary_reason_code}</span>
              </div>
              <div style={{ color: "var(--text)", marginTop: "4px" }}>
                {selectedStrategy.primary_reason_description}
              </div>
            </div>
          )}

          {/* Grid of Evidence Cards */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
              gap: "var(--space-3)",
            }}
          >
            {/* Card 1: Timing & Lead Time Proof */}
            <div
              style={{
                background: "var(--surface-2)",
                border: "1px solid var(--border)",
                padding: "var(--space-3)",
                borderRadius: "2px",
              }}
            >
              <div style={{ fontSize: "0.6875rem", fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", marginBottom: "8px" }}>
                1. Timing Window & Lead-Time Audit
              </div>
              <div style={{ fontSize: "0.75rem", display: "flex", flexDirection: "column", gap: "6px", fontFamily: "var(--font-mono, monospace)" }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--muted)" }}>Timing Signal:</span>
                  <span>{selectedStrategy.timing_signal ?? "N/A"}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--muted)" }}>Total Required Lead Time:</span>
                  <span style={{ fontWeight: 600 }}>{selectedStrategy.timing?.total_lead_time_days ?? 0} days</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--muted)" }}>Earliest Completion Date:</span>
                  <span>{selectedStrategy.timing?.procurement_completion_date ?? "N/A"}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--muted)" }}>Laycan Window Start:</span>
                  <span>{selectedStrategy.timing?.origin_laycan_start ?? "N/A"}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--muted)" }}>Latest Safe Procure Date:</span>
                  <span>{selectedStrategy.timing?.latest_safe_procurement_date ?? "N/A"}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", borderTop: "1px solid var(--border)", paddingTop: "4px" }}>
                  <span style={{ color: "var(--muted)" }}>Remaining Decision Window:</span>
                  <span style={{ fontWeight: 700, color: (selectedStrategy.timing?.remaining_decision_window_days ?? 0) < 0 ? "var(--danger)" : "var(--success)" }}>
                    {selectedStrategy.timing?.remaining_decision_window_days !== undefined
                      ? `${selectedStrategy.timing.remaining_decision_window_days.toFixed(1)} days`
                      : "N/A"}
                  </span>
                </div>
              </div>
            </div>

            {/* Card 2: Forecast Trajectory & Uncertainty Ribbon */}
            <div
              style={{
                background: "var(--surface-2)",
                border: "1px solid var(--border)",
                padding: "var(--space-3)",
                borderRadius: "2px",
              }}
            >
              <div style={{ fontSize: "0.6875rem", fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", marginBottom: "8px" }}>
                2. Market Forecast Evidence (Phase 3 Integration)
              </div>
              {selectedStrategy.forecast_evidence ? (
                <div style={{ fontSize: "0.75rem", display: "flex", flexDirection: "column", gap: "6px", fontFamily: "var(--font-mono, monospace)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--muted)" }}>Target Series:</span>
                    <span style={{ fontWeight: 600 }}>{selectedStrategy.forecast_evidence.forecast_series_id}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--muted)" }}>Current Rate:</span>
                    <span>${selectedStrategy.forecast_evidence.current_rate?.toLocaleString()}/day</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--muted)" }}>Forecast Mean (30d):</span>
                    <span style={{ fontWeight: 600 }}>${selectedStrategy.forecast_evidence.forecast_rate_mean?.toLocaleString()}/day</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--muted)" }}>95% Confidence Interval:</span>
                    <span>
                      ${selectedStrategy.forecast_evidence.lower_bound_95?.toLocaleString()} – ${selectedStrategy.forecast_evidence.upper_bound_95?.toLocaleString()}
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--muted)" }}>Interval Spread Ratio:</span>
                    <span>{selectedStrategy.forecast_evidence.interval_spread_ratio ? (selectedStrategy.forecast_evidence.interval_spread_ratio * 100).toFixed(1) + "%" : "N/A"}</span>
                  </div>
                  <div style={{ borderTop: "1px solid var(--border)", paddingTop: "4px", fontSize: "0.6875rem", color: "var(--muted)", fontFamily: "inherit" }}>
                    {selectedStrategy.forecast_evidence.evidence_note}
                  </div>
                </div>
              ) : (
                <div style={{ fontSize: "0.75rem", color: "var(--muted)" }}>No forecast evidence attached.</div>
              )}
            </div>

            {/* Card 3: Feasibility Admittance (Phase 4 Handoff) */}
            <div
              style={{
                background: "var(--surface-2)",
                border: "1px solid var(--border)",
                padding: "var(--space-3)",
                borderRadius: "2px",
              }}
            >
              <div style={{ fontSize: "0.6875rem", fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", marginBottom: "8px" }}>
                3. Feasibility Admittance (Phase 4 Handoff)
              </div>
              <div style={{ fontSize: "0.75rem", display: "flex", flexDirection: "column", gap: "6px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "var(--font-mono, monospace)" }}>
                  <span style={{ color: "var(--muted)" }}>Admitted Candidate Fleet:</span>
                  <span style={{ fontWeight: 600, color: (selectedStrategy.feasibility_summary?.feasible_vessels_count ?? 0) > 0 ? "var(--success)" : "var(--danger)" }}>
                    {selectedStrategy.feasibility_summary?.feasible_vessels_count ?? 0} vessels admitted
                  </span>
                </div>

                {selectedStrategy.feasibility_summary?.feasible_vessel_names && selectedStrategy.feasibility_summary.feasible_vessel_names.length > 0 && (
                  <div style={{ marginTop: "4px" }}>
                    <span style={{ fontSize: "0.6875rem", color: "var(--muted)" }}>Feasible Ships:</span>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", marginTop: "4px" }}>
                      {selectedStrategy.feasibility_summary.feasible_vessel_names.map((vname, idx) => (
                        <span
                          key={idx}
                          style={{
                            fontSize: "0.6875rem",
                            background: "var(--surface-3)",
                            border: "1px solid var(--border)",
                            padding: "2px 6px",
                            borderRadius: "2px",
                            color: "var(--text)",
                            fontFamily: "var(--font-mono, monospace)",
                          }}
                        >
                          {vname}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Rejection summary breakdown */}
                {selectedStrategy.feasibility_summary?.rejection_summary &&
                  Object.keys(selectedStrategy.feasibility_summary.rejection_summary).length > 0 && (
                    <div style={{ borderTop: "1px solid var(--border)", paddingTop: "6px", marginTop: "4px" }}>
                      <span style={{ fontSize: "0.6875rem", color: "var(--muted)" }}>Rejections by Constraint:</span>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "4px" }}>
                        {Object.entries(selectedStrategy.feasibility_summary.rejection_summary).map(([code, count]) => (
                          <span
                            key={code}
                            style={{
                              fontSize: "0.625rem",
                              background: "rgba(239, 68, 68, 0.1)",
                              border: "1px solid rgba(239, 68, 68, 0.2)",
                              color: "var(--danger)",
                              padding: "1px 5px",
                              borderRadius: "2px",
                              fontFamily: "var(--font-mono, monospace)",
                            }}
                          >
                            {code}: {count}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
              </div>
            </div>

            {/* Card 4: Cost Structure Breakdown */}
            <div
              style={{
                background: "var(--surface-2)",
                border: "1px solid var(--border)",
                padding: "var(--space-3)",
                borderRadius: "2px",
              }}
            >
              <div style={{ fontSize: "0.6875rem", fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", marginBottom: "8px" }}>
                4. Cost Model & Rate Structure
              </div>
              {selectedStrategy.cost_summary ? (
                <div style={{ fontSize: "0.75rem", display: "flex", flexDirection: "column", gap: "6px", fontFamily: "var(--font-mono, monospace)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--muted)" }}>Base Freight:</span>
                    <span>${selectedStrategy.cost_summary.estimated_freight_cost?.toLocaleString()}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--muted)" }}>Bunker Fuel Component:</span>
                    <span>${selectedStrategy.cost_summary.estimated_bunker_cost?.toLocaleString()}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--muted)" }}>Port Dues & Tariffs:</span>
                    <span>${selectedStrategy.cost_summary.estimated_port_dues?.toLocaleString()}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--muted)" }}>Procurement Admin Fee:</span>
                    <span>${selectedStrategy.cost_summary.procurement_administration_fee?.toLocaleString()}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", borderTop: "1px solid var(--border)", paddingTop: "4px" }}>
                    <span style={{ color: "var(--muted)", fontWeight: 600 }}>Expected Total Cost:</span>
                    <span style={{ fontWeight: 700, color: "var(--accent, #38bdf8)" }}>
                      ${selectedStrategy.cost_summary.expected_total_cost?.toLocaleString()}
                    </span>
                  </div>
                  <div style={{ fontSize: "0.6875rem", color: "var(--muted)", fontFamily: "inherit" }}>
                    {selectedStrategy.cost_summary.note}
                  </div>
                </div>
              ) : (
                <div style={{ fontSize: "0.75rem", color: "var(--muted)" }}>No cost summary available.</div>
              )}
            </div>
          </div>
        </section>
      )}

      {/* ── Downstream Handoff Notice (Strict Architectural Principle) ──── */}
      <footer
        style={{
          background: "var(--surface-1)",
          border: "1px solid var(--border)",
          padding: "var(--space-3)",
          borderRadius: "2px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "var(--space-2)",
          fontSize: "0.6875rem",
          color: "var(--muted)",
        }}
      >
        <div>
          <strong style={{ color: "var(--text)" }}>ARCHITECTURAL CONTRACT:</strong> Phase 5 identifies viable candidate procurement strategies and evaluates timing windows.
          Candidate options marked <span style={{ color: "var(--accent)" }}>READY FOR OPTIMIZATION</span> are passed to the <strong>MILP Optimization Engine</strong> for simultaneous fleet scheduling and global cost minimization.
        </div>
        <div style={{ fontFamily: "var(--font-mono, monospace)" }}>
          PIPELINE: FEASIBILITY → STRATEGY EVALUATION → MILP OPTIMIZER
        </div>
      </footer>
    </div>
  );
}
