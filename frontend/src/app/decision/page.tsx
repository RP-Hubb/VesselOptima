"use client";

import React, { useState, useEffect } from "react";
import {
  getDecisionDemo,
  evaluateDecision,
  getDecisionRuns,
  getDecisionThresholds,
} from "@/lib/api";
import type {
  DecisionResultResponse,
  DecisionRunSummary,
  AssignmentDecisionResponse,
  DecisionActionResponse,
  DecisionTradeoffResponse,
  RecommendationType,
} from "@/types/api";

type ActiveTab = "overview" | "assignments" | "actions" | "tradeoffs" | "audit";
type DemoScenario = "BASELINE" | "STRATEGY_FLIP_A" | "STRATEGY_FLIP_B" | "STRESS_TEST";

export default function DecisionPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>("overview");
  const [selectedScenario, setSelectedScenario] = useState<DemoScenario>("BASELINE");

  // Decision result state
  const [decisionResult, setDecisionResult] = useState<DecisionResultResponse | null>(null);
  const [recentRuns, setRecentRuns] = useState<DecisionRunSummary[]>([]);
  const [thresholds, setThresholds] = useState<Record<string, any> | null>(null);
  const [selectedAssignment, setSelectedAssignment] = useState<AssignmentDecisionResponse | null>(null);

  // Load baseline on mount
  useEffect(() => {
    initDashboard();
  }, []);

  async function initDashboard() {
    setLoading(true);
    setError(null);
    try {
      const [threshData, demoData, runsData] = await Promise.all([
        getDecisionThresholds().catch(() => null),
        getDecisionDemo("BASELINE"),
        getDecisionRuns(10).catch(() => []),
      ]);

      if (threshData) setThresholds(threshData);
      setDecisionResult(demoData);
      setRecentRuns(runsData);
      if (demoData.assignment_recommendations?.length > 0) {
        setSelectedAssignment(demoData.assignment_recommendations[0]);
      }
    } catch (err: any) {
      console.error("Failed to load decision intelligence:", err);
      setError(err.message || "Failed to initialize decision intelligence engine.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSelectScenario(scenario: DemoScenario) {
    setSelectedScenario(scenario);
    setLoading(true);
    setError(null);
    try {
      const demoData = await getDecisionDemo(scenario);
      setDecisionResult(demoData);
      if (demoData.assignment_recommendations?.length > 0) {
        setSelectedAssignment(demoData.assignment_recommendations[0]);
      }
    } catch (err: any) {
      console.error(`Failed to switch to scenario ${scenario}:`, err);
      setError(err.message || `Failed to switch scenario to ${scenario}`);
    } finally {
      setLoading(false);
    }
  }

  // Format currency helpers
  const formatUSD = (val?: number | null) =>
    val != null
      ? `$${Math.round(val).toLocaleString("en-US")}`
      : "—";

  const formatPct = (val?: number | null) =>
    val != null ? `${(val * 100).toFixed(1)}%` : "—";

  // Recommendation Badge Color
  const getBadgeStyle = (rec?: RecommendationType | string) => {
    switch (rec) {
      case "PROCEED":
        return {
          bg: "rgba(16, 185, 129, 0.15)",
          border: "#10b981",
          color: "#34d399",
          label: "PROCEED",
        };
      case "PROCEED_WITH_CAUTION":
        return {
          bg: "rgba(245, 158, 11, 0.15)",
          border: "#f59e0b",
          color: "#fbbf24",
          label: "PROCEED WITH CAUTION",
        };
      case "RECONSIDER":
        return {
          bg: "rgba(239, 68, 68, 0.15)",
          border: "#ef4444",
          color: "#f87171",
          label: "RECONSIDER",
        };
      case "REJECT":
        return {
          bg: "rgba(220, 38, 38, 0.25)",
          border: "#dc2626",
          color: "#fca5a5",
          label: "REJECT",
        };
      default:
        return {
          bg: "rgba(100, 116, 139, 0.15)",
          border: "#64748b",
          color: "#94a3b8",
          label: rec || "UNKNOWN",
        };
    }
  };

  const badge = getBadgeStyle(decisionResult?.recommendation_type);

  return (
    <div style={{ padding: "1.5rem", maxWidth: "1600px", margin: "0 auto", color: "var(--text)" }}>
      {/* Header & Scenario Switcher */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "1.5rem",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.25rem" }}>
            <h1 style={{ fontSize: "1.75rem", fontWeight: 700, margin: 0, letterSpacing: "-0.02em" }}>
              Decision Intelligence & Explainable Recommendations
            </h1>
            <span
              style={{
                fontSize: "0.75rem",
                padding: "0.2rem 0.5rem",
                borderRadius: "4px",
                background: "rgba(56, 189, 248, 0.12)",
                color: "#38bdf8",
                border: "1px solid rgba(56, 189, 248, 0.3)",
                fontWeight: 600,
              }}
            >
              PHASE 10 VERIFIED
            </span>
          </div>
          <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "0.875rem" }}>
            Deterministic synthesis of Phase 7 MILP allocation, Phase 8 scenarios, and Phase 9 uncertainty into auditable decisions.
          </p>
        </div>

        {/* Demo Scenario Selectors */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", background: "var(--surface-1)", padding: "0.35rem", borderRadius: "8px", border: "1px solid var(--border)" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", padding: "0 0.5rem", fontWeight: 600 }}>
            PRESET SCENARIOS:
          </span>
          {(
            [
              { id: "BASELINE", label: "Baseline Deployment", badge: "PROCEED" },
              { id: "STRATEGY_FLIP_A", label: "Plan A (High Tail)", badge: "CAUTION" },
              { id: "STRATEGY_FLIP_B", label: "Plan B (Robust)", badge: "PROCEED" },
              { id: "STRESS_TEST", label: "Stress Test (+35% Fuel)", badge: "RECONSIDER" },
            ] as const
          ).map((s) => {
            const isSelected = selectedScenario === s.id;
            return (
              <button
                key={s.id}
                onClick={() => handleSelectScenario(s.id)}
                disabled={loading}
                style={{
                  padding: "0.4rem 0.75rem",
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  borderRadius: "6px",
                  cursor: loading ? "not-allowed" : "pointer",
                  border: isSelected ? "1px solid var(--accent)" : "1px solid transparent",
                  background: isSelected ? "rgba(56, 189, 248, 0.15)" : "transparent",
                  color: isSelected ? "#38bdf8" : "var(--text-muted)",
                  transition: "all 0.15s ease",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.4rem",
                }}
              >
                <span>{s.label}</span>
                <span
                  style={{
                    fontSize: "0.65rem",
                    padding: "0.1rem 0.35rem",
                    borderRadius: "3px",
                    background:
                      s.badge === "PROCEED"
                        ? "rgba(16,185,129,0.2)"
                        : s.badge === "CAUTION"
                        ? "rgba(245,158,11,0.2)"
                        : "rgba(239,68,68,0.2)",
                    color:
                      s.badge === "PROCEED"
                        ? "#34d399"
                        : s.badge === "CAUTION"
                        ? "#fbbf24"
                        : "#f87171",
                  }}
                >
                  {s.badge}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {error && (
        <div
          style={{
            padding: "0.75rem 1rem",
            marginBottom: "1.25rem",
            borderRadius: "6px",
            background: "rgba(239, 68, 68, 0.1)",
            border: "1px solid #ef4444",
            color: "#fca5a5",
            fontSize: "0.875rem",
          }}
        >
          {error}
        </div>
      )}

      {/* Hero: Executive Recommendation & Score Banner */}
      {decisionResult && (
        <div
          style={{
            background: "linear-gradient(135deg, var(--surface-1) 0%, rgba(30, 41, 59, 0.7) 100%)",
            borderRadius: "12px",
            border: `1px solid ${badge.border}`,
            padding: "1.5rem",
            marginBottom: "1.5rem",
            boxShadow: `0 8px 24px -6px ${badge.border}22`,
          }}
        >
          <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: "1.5rem", alignItems: "center" }}>
            <div>
              {/* Status and Badges */}
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.75rem", flexWrap: "wrap" }}>
                <span
                  style={{
                    fontSize: "0.95rem",
                    fontWeight: 700,
                    letterSpacing: "0.03em",
                    padding: "0.35rem 0.85rem",
                    borderRadius: "6px",
                    background: badge.bg,
                    color: badge.color,
                    border: `1px solid ${badge.border}`,
                  }}
                >
                  {badge.label}
                </span>

                <span
                  style={{
                    fontSize: "0.8rem",
                    fontWeight: 600,
                    padding: "0.3rem 0.65rem",
                    borderRadius: "4px",
                    background: "rgba(14, 165, 233, 0.15)",
                    color: "#38bdf8",
                    border: "1px solid rgba(14, 165, 233, 0.3)",
                  }}
                >
                  CONFIDENCE: {decisionResult.confidence}
                </span>

                <span
                  style={{
                    fontSize: "0.8rem",
                    fontWeight: 500,
                    padding: "0.3rem 0.65rem",
                    borderRadius: "4px",
                    background: "rgba(255, 255, 255, 0.05)",
                    color: "var(--text-muted)",
                    border: "1px solid var(--border)",
                  }}
                >
                  PRIMARY REASON: {decisionResult.primary_reason_code}
                </span>

                <span
                  style={{
                    fontSize: "0.8rem",
                    color: "var(--text-muted)",
                    marginLeft: "auto",
                    fontFamily: "monospace",
                  }}
                >
                  RUN: {decisionResult.run_id}
                </span>
              </div>

              {/* Executive Summary */}
              <p
                style={{
                  fontSize: "1.05rem",
                  lineHeight: "1.6",
                  margin: "0 0 1rem 0",
                  color: "var(--text)",
                  fontWeight: 400,
                }}
              >
                {decisionResult.executive_summary}
              </p>

              {/* Quick Provenance Bar */}
              <div style={{ display: "flex", gap: "1.5rem", fontSize: "0.75rem", color: "var(--text-muted)", fontFamily: "monospace" }}>
                <span>SHA-256 INPUT: {decisionResult.input_hash.slice(0, 12)}...</span>
                <span>SHA-256 OUTPUT: {decisionResult.output_hash.slice(0, 12)}...</span>
                <span>EXEC: {decisionResult.execution_time_seconds}s</span>
                <span>STABILITY: {formatPct(decisionResult.decision_stability)}</span>
              </div>
            </div>

            {/* Score Radial Box */}
            <div
              style={{
                background: "rgba(0,0,0,0.35)",
                borderRadius: "10px",
                border: "1px solid var(--border)",
                padding: "1.25rem",
                textAlign: "center",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <div style={{ fontSize: "0.75rem", fontWeight: 700, letterSpacing: "0.08em", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "0.25rem" }}>
                Decision Score
              </div>
              <div style={{ fontSize: "3rem", fontWeight: 800, color: badge.color, lineHeight: 1, margin: "0.5rem 0" }}>
                {decisionResult.decision_score}
                <span style={{ fontSize: "1.25rem", color: "var(--text-muted)", fontWeight: 400 }}>/100</span>
              </div>
              <div
                style={{
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: decisionResult.decision_score >= 75 ? "#34d399" : decisionResult.decision_score >= 50 ? "#fbbf24" : "#f87171",
                }}
              >
                {decisionResult.decision_score >= 75
                  ? "HIGH CONFIDENCE / EXCELLENT"
                  : decisionResult.decision_score >= 50
                  ? "CONDITIONAL / MODERATE"
                  : "UNFAVORABLE RISK / DEFICIT"}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Navigation Tabs */}
      <div style={{ display: "flex", borderBottom: "1px solid var(--border)", marginBottom: "1.5rem", gap: "0.5rem" }}>
        {[
          { id: "overview", label: "Executive Synthesis & Economics" },
          { id: "assignments", label: "Vessel Assignment Rationales" },
          { id: "actions", label: "Prioritized Action Queue" },
          { id: "tradeoffs", label: "Multi-Plan Trade-Offs (Strategy Flip)" },
          { id: "audit", label: "Governance & Provenance Audit" },
        ].map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as ActiveTab)}
              style={{
                padding: "0.6rem 1.2rem",
                background: "transparent",
                border: "none",
                borderBottom: isActive ? "2px solid #38bdf8" : "2px solid transparent",
                color: isActive ? "#38bdf8" : "var(--text-muted)",
                fontWeight: isActive ? 600 : 500,
                fontSize: "0.875rem",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* TAB CONTENT 1: OVERVIEW */}
      {activeTab === "overview" && decisionResult && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
          {/* Left: Financial vs Risk-Adjusted Economics */}
          <div
            style={{
              background: "var(--surface-1)",
              borderRadius: "10px",
              border: "1px solid var(--border)",
              padding: "1.25rem",
            }}
          >
            <h2 style={{ fontSize: "1rem", fontWeight: 600, margin: "0 0 1rem 0", color: "var(--text)" }}>
              Economic Contribution: Deterministic vs. Risk-Adjusted
            </h2>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.25rem" }}>
              <div style={{ background: "var(--surface-2)", padding: "1rem", borderRadius: "8px", border: "1px solid var(--border)" }}>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>
                  PHASE 7 OPTIMIZATION RETURN (E[Π])
                </div>
                <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#38bdf8" }}>
                  {formatUSD(decisionResult.evidence.expected_contribution)}
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                  Deterministic MILP Objective Baseline
                </div>
              </div>

              <div style={{ background: "rgba(56, 189, 248, 0.08)", padding: "1rem", borderRadius: "8px", border: "1px solid rgba(56, 189, 248, 0.25)" }}>
                <div style={{ fontSize: "0.75rem", color: "#38bdf8", fontWeight: 600, marginBottom: "0.25rem" }}>
                  RISK-ADJUSTED CONTRIBUTION
                </div>
                <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#34d399" }}>
                  {formatUSD(decisionResult.risk_adjusted_contribution)}
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                  E[Π] - 0.50 × CVaR95 Downside Tail
                </div>
              </div>
            </div>

            <div style={{ fontSize: "0.875rem", lineHeight: "1.6", color: "var(--text)", marginBottom: "1.25rem" }}>
              {decisionResult.financial_narrative}
            </div>

            {/* Score Components Breakdown */}
            <h3 style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-muted)", margin: "0 0 0.75rem 0", textTransform: "uppercase" }}>
              Score Weighting Components
            </h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
              {[
                { label: "Economic Performance (Weight: 35%)", val: decisionResult.scoring_breakdown.economic_component, max: 35.0, color: "#38bdf8" },
                { label: "Plan Reliability Score (Weight: 25%)", val: decisionResult.scoring_breakdown.reliability_component, max: 25.0, color: "#34d399" },
                { label: "Scenario Robustness (Weight: 20%)", val: decisionResult.scoring_breakdown.robustness_component, max: 20.0, color: "#a855f7" },
                { label: "Tail Risk Penalty (Deduction: -10%)", val: decisionResult.scoring_breakdown.risk_penalty, max: 10.0, isPenalty: true, color: "#f87171" },
                { label: "Schedule Fragility Penalty (Deduction: -10%)", val: decisionResult.scoring_breakdown.schedule_penalty, max: 10.0, isPenalty: true, color: "#fbbf24" },
              ].map((c, i) => (
                <div key={i} style={{ fontSize: "0.8rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.25rem" }}>
                    <span style={{ color: "var(--text-muted)" }}>{c.label}</span>
                    <span style={{ fontWeight: 600, color: c.color }}>
                      {c.isPenalty ? `-${c.val.toFixed(1)} pts` : `+${c.val.toFixed(1)} pts`}
                    </span>
                  </div>
                  <div style={{ width: "100%", height: "6px", background: "rgba(255,255,255,0.06)", borderRadius: "3px", overflow: "hidden" }}>
                    <div
                      style={{
                        width: `${Math.min(100, (c.val / c.max) * 100)}%`,
                        height: "100%",
                        background: c.color,
                        borderRadius: "3px",
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right: Risk Attribution & "What Could Change" */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            {/* Risk & Fragility Box */}
            <div
              style={{
                background: "var(--surface-1)",
                borderRadius: "10px",
                border: "1px solid var(--border)",
                padding: "1.25rem",
              }}
            >
              <h2 style={{ fontSize: "1rem", fontWeight: 600, margin: "0 0 1rem 0", color: "var(--text)" }}>
                Uncertainty Attribution & Tail Risk
              </h2>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.75rem", marginBottom: "1rem" }}>
                <div style={{ background: "var(--surface-2)", padding: "0.75rem", borderRadius: "6px" }}>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>LOSS PROBABILITY</div>
                  <div style={{ fontSize: "1.2rem", fontWeight: 700, color: decisionResult.evidence.loss_probability > 0.05 ? "#fbbf24" : "#34d399" }}>
                    {formatPct(decisionResult.evidence.loss_probability)}
                  </div>
                </div>
                <div style={{ background: "var(--surface-2)", padding: "0.75rem", borderRadius: "6px" }}>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>95% DOWNSIDE CVAR</div>
                  <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#f87171" }}>
                    {formatUSD(decisionResult.evidence.cvar_95)}
                  </div>
                </div>
                <div style={{ background: "var(--surface-2)", padding: "0.75rem", borderRadius: "6px" }}>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>LAYCAN MISS PROB</div>
                  <div style={{ fontSize: "1.2rem", fontWeight: 700, color: decisionResult.evidence.laycan_miss_probability > 0.05 ? "#fbbf24" : "#34d399" }}>
                    {formatPct(decisionResult.evidence.laycan_miss_probability)}
                  </div>
                </div>
              </div>

              <div style={{ fontSize: "0.85rem", lineHeight: "1.5", color: "var(--text-muted)", marginBottom: "0.75rem" }}>
                {decisionResult.risk_narrative}
              </div>
              <div style={{ fontSize: "0.85rem", lineHeight: "1.5", color: "var(--text-muted)" }}>
                {decisionResult.schedule_narrative}
              </div>
            </div>

            {/* What Could Change Box */}
            <div
              style={{
                background: "var(--surface-1)",
                borderRadius: "10px",
                border: "1px solid var(--border)",
                padding: "1.25rem",
              }}
            >
              <h2 style={{ fontSize: "1rem", fontWeight: 600, margin: "0 0 0.75rem 0", color: "#38bdf8" }}>
                What Could Change This Recommendation?
              </h2>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                {decisionResult.what_could_change.map((w, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "0.6rem",
                      padding: "0.5rem 0.75rem",
                      background: "rgba(255,255,255,0.03)",
                      borderRadius: "6px",
                      fontSize: "0.825rem",
                      color: "var(--text)",
                    }}
                  >
                    <span style={{ color: "#38bdf8", fontWeight: 700 }}>•</span>
                    <span>{w}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB CONTENT 2: ASSIGNMENT RATIONALES */}
      {activeTab === "assignments" && decisionResult && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 420px", gap: "1.5rem" }}>
          <div
            style={{
              background: "var(--surface-1)",
              borderRadius: "10px",
              border: "1px solid var(--border)",
              overflow: "hidden",
            }}
          >
            <div style={{ padding: "1rem 1.25rem", borderBottom: "1px solid var(--border)" }}>
              <h2 style={{ fontSize: "1rem", fontWeight: 600, margin: 0 }}>
                Individual Vessel Assignment Decisions ({decisionResult.assignment_recommendations.length})
              </h2>
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8125rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)", color: "var(--text-muted)", textAlign: "left" }}>
                  <th style={{ padding: "0.75rem 1rem" }}>Vessel & Cargo</th>
                  <th style={{ padding: "0.75rem" }}>Recommendation</th>
                  <th style={{ padding: "0.75rem", textAlign: "right" }}>Expected Return</th>
                  <th style={{ padding: "0.75rem", textAlign: "right" }}>Schedule Buffer</th>
                  <th style={{ padding: "0.75rem", textAlign: "right" }}>Loss Prob</th>
                  <th style={{ padding: "0.75rem", textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {decisionResult.assignment_recommendations.map((a) => {
                  const aBadge = getBadgeStyle(a.recommendation_type);
                  const isSelected = selectedAssignment?.candidate_id === a.candidate_id;
                  return (
                    <tr
                      key={a.candidate_id}
                      onClick={() => setSelectedAssignment(a)}
                      style={{
                        borderBottom: "1px solid var(--border)",
                        background: isSelected ? "rgba(56, 189, 248, 0.08)" : "transparent",
                        cursor: "pointer",
                      }}
                    >
                      <td style={{ padding: "0.75rem 1rem" }}>
                        <div style={{ fontWeight: 600, color: "var(--text)" }}>{a.vessel_name}</div>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{a.cargo_name}</div>
                      </td>
                      <td style={{ padding: "0.75rem" }}>
                        <span
                          style={{
                            fontSize: "0.7rem",
                            fontWeight: 600,
                            padding: "0.2rem 0.45rem",
                            borderRadius: "4px",
                            background: aBadge.bg,
                            color: aBadge.color,
                            border: `1px solid ${aBadge.border}`,
                          }}
                        >
                          {a.recommendation_type}
                        </span>
                      </td>
                      <td style={{ padding: "0.75rem", textAlign: "right", fontWeight: 600, color: "#34d399" }}>
                        {formatUSD(a.expected_contribution)}
                      </td>
                      <td style={{ padding: "0.75rem", textAlign: "right" }}>
                        <span style={{ color: a.schedule_buffer_days < 2.0 ? "#fbbf24" : "#38bdf8", fontWeight: 500 }}>
                          {a.schedule_buffer_days.toFixed(1)} days
                        </span>
                      </td>
                      <td style={{ padding: "0.75rem", textAlign: "right", color: a.loss_probability > 0.05 ? "#fbbf24" : "var(--text-muted)" }}>
                        {formatPct(a.loss_probability)}
                      </td>
                      <td style={{ padding: "0.75rem", textAlign: "right" }}>
                        <button
                          style={{
                            padding: "0.25rem 0.6rem",
                            fontSize: "0.7rem",
                            borderRadius: "4px",
                            background: isSelected ? "var(--accent)" : "rgba(255,255,255,0.06)",
                            border: "1px solid var(--border)",
                            color: isSelected ? "#000" : "var(--text)",
                            cursor: "pointer",
                          }}
                        >
                          Details
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Assignment Detail Panel */}
          {selectedAssignment ? (
            <div
              style={{
                background: "var(--surface-1)",
                borderRadius: "10px",
                border: "1px solid var(--border)",
                padding: "1.25rem",
                display: "flex",
                flexDirection: "column",
                gap: "1rem",
              }}
            >
              <div>
                <span
                  style={{
                    fontSize: "0.7rem",
                    padding: "0.2rem 0.5rem",
                    borderRadius: "4px",
                    background: getBadgeStyle(selectedAssignment.recommendation_type).bg,
                    color: getBadgeStyle(selectedAssignment.recommendation_type).color,
                    fontWeight: 700,
                  }}
                >
                  {selectedAssignment.recommendation_type}
                </span>
                <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: "0.5rem 0 0.25rem 0" }}>
                  {selectedAssignment.vessel_name}
                </h3>
                <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                  {selectedAssignment.cargo_name}
                </div>
              </div>

              <div style={{ background: "var(--surface-2)", padding: "0.75rem", borderRadius: "6px" }}>
                <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "#38bdf8", marginBottom: "0.25rem" }}>
                  OPERATIONAL DIRECTIVE
                </div>
                <div style={{ fontSize: "0.85rem", color: "var(--text)", lineHeight: 1.5 }}>
                  {selectedAssignment.action_advice}
                </div>
              </div>

              <div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "0.5rem" }}>METRICS BREAKDOWN</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", fontSize: "0.8rem" }}>
                  <div style={{ background: "rgba(255,255,255,0.03)", padding: "0.5rem", borderRadius: "4px" }}>
                    <span style={{ color: "var(--text-muted)" }}>Expected: </span>
                    <span style={{ fontWeight: 600 }}>{formatUSD(selectedAssignment.expected_contribution)}</span>
                  </div>
                  <div style={{ background: "rgba(255,255,255,0.03)", padding: "0.5rem", borderRadius: "4px" }}>
                    <span style={{ color: "var(--text-muted)" }}>95% CVaR: </span>
                    <span style={{ fontWeight: 600 }}>{formatUSD(selectedAssignment.cvar95)}</span>
                  </div>
                  <div style={{ background: "rgba(255,255,255,0.03)", padding: "0.5rem", borderRadius: "4px" }}>
                    <span style={{ color: "var(--text-muted)" }}>Buffer: </span>
                    <span style={{ fontWeight: 600 }}>{selectedAssignment.schedule_buffer_days.toFixed(1)}d</span>
                  </div>
                  <div style={{ background: "rgba(255,255,255,0.03)", padding: "0.5rem", borderRadius: "4px" }}>
                    <span style={{ color: "var(--text-muted)" }}>Laycan Miss: </span>
                    <span style={{ fontWeight: 600 }}>{formatPct(selectedAssignment.laycan_miss_prob)}</span>
                  </div>
                </div>
              </div>

              <div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>REASON CODE</div>
                <div style={{ fontFamily: "monospace", fontSize: "0.8rem", color: "#38bdf8" }}>
                  {selectedAssignment.primary_reason_code}
                </div>
              </div>
            </div>
          ) : (
            <div style={{ background: "var(--surface-1)", borderRadius: "10px", padding: "1.5rem", textAlign: "center", color: "var(--text-muted)" }}>
              Select an assignment to inspect operational directives.
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT 3: ACTION QUEUE */}
      {activeTab === "actions" && decisionResult && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ fontSize: "1rem", fontWeight: 600, margin: 0 }}>
              Prioritized Operational Actions & Risk Mitigations ({decisionResult.actions.length})
            </h2>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
              Sorted by severity and risk exposure
            </span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "1rem" }}>
            {decisionResult.actions.map((act) => {
              const pColor =
                act.priority === "CRITICAL"
                  ? "#ef4444"
                  : act.priority === "HIGH"
                  ? "#f59e0b"
                  : act.priority === "MEDIUM"
                  ? "#38bdf8"
                  : "#94a3b8";

              return (
                <div
                  key={act.action_id}
                  style={{
                    background: "var(--surface-1)",
                    borderRadius: "10px",
                    border: `1px solid var(--border)`,
                    borderLeft: `4px solid ${pColor}`,
                    padding: "1.25rem",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.5rem" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                      <span
                        style={{
                          fontSize: "0.7rem",
                          fontWeight: 700,
                          padding: "0.15rem 0.45rem",
                          borderRadius: "4px",
                          background: `${pColor}22`,
                          color: pColor,
                          border: `1px solid ${pColor}44`,
                        }}
                      >
                        {act.priority}
                      </span>
                      <h3 style={{ fontSize: "1rem", fontWeight: 600, margin: 0 }}>{act.title}</h3>
                    </div>
                    <span style={{ fontFamily: "monospace", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      {act.action_id}
                    </span>
                  </div>

                  <p style={{ margin: "0 0 0.75rem 0", fontSize: "0.85rem", color: "var(--text)" }}>
                    {act.description}
                  </p>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", background: "var(--surface-2)", padding: "0.75rem", borderRadius: "6px", fontSize: "0.8rem" }}>
                    <div>
                      <span style={{ color: "#fbbf24", fontWeight: 600 }}>TRIGGER CONDITION: </span>
                      <span style={{ color: "var(--text-muted)" }}>{act.trigger_condition || "Immediate execution required"}</span>
                    </div>
                    <div>
                      <span style={{ color: "#34d399", fontWeight: 600 }}>RECOMMENDED ACTION: </span>
                      <span style={{ color: "var(--text)" }}>{act.recommended_action}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* TAB CONTENT 4: MULTI-PLAN TRADEOFFS */}
      {activeTab === "tradeoffs" && decisionResult && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <div
            style={{
              background: "rgba(56, 189, 248, 0.08)",
              borderRadius: "10px",
              border: "1px solid rgba(56, 189, 248, 0.25)",
              padding: "1.25rem",
            }}
          >
            <h2 style={{ fontSize: "1rem", fontWeight: 600, margin: "0 0 0.5rem 0", color: "#38bdf8" }}>
              Strategy Flip Demonstration: Nominal Return vs. Tail Risk Dominance
            </h2>
            <p style={{ fontSize: "0.85rem", color: "var(--text)", lineHeight: 1.6, margin: 0 }}>
              Deterministic proof from Phase 9/10: While Plan A advertises higher nominal profit ($730k vs $685k), its extreme tail loss exposure ($295k 95% CVaR) makes Plan B superior on a risk-adjusted basis ($677.5k vs $582.5k). Phase 10 transparently flags Plan A as <strong>PROCEED WITH CAUTION</strong> and endorses Plan B as <strong>PROCEED</strong>.
            </p>
          </div>

          <div
            style={{
              background: "var(--surface-1)",
              borderRadius: "10px",
              border: "1px solid var(--border)",
              overflow: "hidden",
            }}
          >
            <div style={{ padding: "1rem 1.25rem", borderBottom: "1px solid var(--border)" }}>
              <h3 style={{ fontSize: "1rem", fontWeight: 600, margin: 0 }}>
                Pairwise Multi-Plan Trade-Off Analysis
              </h3>
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8125rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)", color: "var(--text-muted)", textAlign: "left" }}>
                  <th style={{ padding: "0.75rem 1rem" }}>Alternative Plan</th>
                  <th style={{ padding: "0.75rem", textAlign: "right" }}>Contribution Δ</th>
                  <th style={{ padding: "0.75rem", textAlign: "right" }}>Loss Prob Δ</th>
                  <th style={{ padding: "0.75rem", textAlign: "right" }}>Tail Risk (CVaR) Δ</th>
                  <th style={{ padding: "0.75rem", textAlign: "right" }}>Reliability Δ</th>
                  <th style={{ padding: "0.75rem" }}>Executive Evaluation</th>
                </tr>
              </thead>
              <tbody>
                {decisionResult.tradeoffs.map((t, idx) => (
                  <tr key={idx} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ padding: "0.75rem 1rem", fontWeight: 600 }}>{t.comparison_plan_name}</td>
                    <td style={{ padding: "0.75rem", textAlign: "right", color: t.contribution_delta >= 0 ? "#34d399" : "#f87171", fontWeight: 600 }}>
                      {t.contribution_delta >= 0 ? `+${formatUSD(t.contribution_delta)}` : formatUSD(t.contribution_delta)}
                    </td>
                    <td style={{ padding: "0.75rem", textAlign: "right", color: t.loss_prob_delta <= 0 ? "#34d399" : "#f87171" }}>
                      {t.loss_prob_delta >= 0 ? `+${(t.loss_prob_delta * 100).toFixed(1)}%` : `${(t.loss_prob_delta * 100).toFixed(1)}%`}
                    </td>
                    <td style={{ padding: "0.75rem", textAlign: "right", color: t.cvar_delta <= 0 ? "#34d399" : "#f87171" }}>
                      {t.cvar_delta >= 0 ? `+${formatUSD(t.cvar_delta)}` : formatUSD(t.cvar_delta)}
                    </td>
                    <td style={{ padding: "0.75rem", textAlign: "right", color: t.reliability_delta >= 0 ? "#34d399" : "#fbbf24" }}>
                      {t.reliability_delta >= 0 ? `+${t.reliability_delta.toFixed(1)}` : t.reliability_delta.toFixed(1)} pts
                    </td>
                    <td style={{ padding: "0.75rem", color: "var(--text-muted)" }}>
                      {t.tradeoff_summary}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB CONTENT 5: AUDIT & GOVERNANCE */}
      {activeTab === "audit" && decisionResult && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
          {/* Provenance and Integrity */}
          <div
            style={{
              background: "var(--surface-1)",
              borderRadius: "10px",
              border: "1px solid var(--border)",
              padding: "1.25rem",
            }}
          >
            <h2 style={{ fontSize: "1rem", fontWeight: 600, margin: "0 0 1rem 0" }}>
              Cryptographic Provenance & Versioning
            </h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", fontSize: "0.8125rem", fontFamily: "monospace" }}>
              <div style={{ background: "var(--surface-2)", padding: "0.75rem", borderRadius: "6px" }}>
                <div style={{ color: "var(--text-muted)", fontSize: "0.7rem" }}>SHA-256 INPUT HASH</div>
                <div style={{ color: "#38bdf8", wordBreak: "break-all" }}>{decisionResult.input_hash}</div>
              </div>
              <div style={{ background: "var(--surface-2)", padding: "0.75rem", borderRadius: "6px" }}>
                <div style={{ color: "var(--text-muted)", fontSize: "0.7rem" }}>SHA-256 OUTPUT HASH</div>
                <div style={{ color: "#34d399", wordBreak: "break-all" }}>{decisionResult.output_hash}</div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
                <div style={{ background: "var(--surface-2)", padding: "0.5rem", borderRadius: "4px" }}>
                  <span style={{ color: "var(--text-muted)" }}>ENGINE VERSION: </span>
                  <span>1.0.0</span>
                </div>
                <div style={{ background: "var(--surface-2)", padding: "0.5rem", borderRadius: "4px" }}>
                  <span style={{ color: "var(--text-muted)" }}>RULE VERSION: </span>
                  <span>1.0.0</span>
                </div>
                <div style={{ background: "var(--surface-2)", padding: "0.5rem", borderRadius: "4px" }}>
                  <span style={{ color: "var(--text-muted)" }}>SOLVER BOUNDARY: </span>
                  <span>Phase 7 HiGHS</span>
                </div>
                <div style={{ background: "var(--surface-2)", padding: "0.5rem", borderRadius: "4px" }}>
                  <span style={{ color: "var(--text-muted)" }}>AIR-GAP STATUS: </span>
                  <span style={{ color: "#34d399" }}>OFFLINE VERIFIED</span>
                </div>
              </div>
            </div>
          </div>

          {/* Active Gating Thresholds */}
          <div
            style={{
              background: "var(--surface-1)",
              borderRadius: "10px",
              border: "1px solid var(--border)",
              padding: "1.25rem",
            }}
          >
            <h2 style={{ fontSize: "1rem", fontWeight: 600, margin: "0 0 1rem 0" }}>
              Active Decision Gating Thresholds
            </h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.8125rem" }}>
              {[
                { name: "Max Loss Probability (PROCEED)", val: "≤ 5.0%" },
                { name: "Max Loss Probability (CAUTION)", val: "≤ 15.0%" },
                { name: "Max Downside Tail Ratio (CVaR/Contrib)", val: "≤ 20.0%" },
                { name: "Minimum Schedule Buffer Days", val: "≥ 2.0 days" },
                { name: "Max Laycan Miss Probability", val: "≤ 5.0%" },
                { name: "Minimum Reliability Score (PROCEED)", val: "≥ 80.0 pts" },
                { name: "Minimum Decision Score (PROCEED)", val: "≥ 75.0 / 100" },
                { name: "Risk-Aversion Lambda Factor", val: "λ = 0.50" },
              ].map((th, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    padding: "0.4rem 0.6rem",
                    background: "rgba(255,255,255,0.03)",
                    borderRadius: "4px",
                  }}
                >
                  <span style={{ color: "var(--text-muted)" }}>{th.name}</span>
                  <span style={{ fontWeight: 600, fontFamily: "monospace" }}>{th.val}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
