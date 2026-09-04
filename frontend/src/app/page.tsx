"use client";

import { useEffect, useState } from "react";
import { getRuntimeMode, getRuntimeStatus } from "@/lib/api";
import type { RuntimeModeResponse, RuntimeStatusResponse } from "@/types/api";

/**
 * Market page — the default landing page.
 * Phase 1: shows system status and runtime mode overview.
 * Later phases will populate with market data, indicators, and charts.
 */
export default function MarketPage() {
  const [mode, setMode] = useState<RuntimeModeResponse | null>(null);
  const [status, setStatus] = useState<RuntimeStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getRuntimeMode(), getRuntimeStatus()])
      .then(([m, s]) => {
        setMode(m);
        setStatus(s);
      })
      .catch((e) => setError(e.message || "Failed to connect to backend"));
  }, []);

  if (error) {
    return (
      <div
        style={{
          background: "var(--surface-1)",
          border: "1px solid var(--negative)",
          borderRadius: "var(--radius-md)",
          padding: "var(--space-4)",
          maxWidth: "600px",
        }}
      >
        <div style={{ color: "var(--negative)", fontWeight: 600, marginBottom: "var(--space-2)" }}>
          ● BACKEND UNAVAILABLE
        </div>
        <div style={{ color: "var(--muted)", fontSize: "0.8125rem" }}>{error}</div>
        <div style={{ color: "var(--muted)", fontSize: "0.75rem", marginTop: "var(--space-3)" }}>
          Ensure the backend is running: <code style={{ color: "var(--info)" }}>uvicorn app.main:app --reload</code>
        </div>
      </div>
    );
  }

  if (!mode || !status) {
    return (
      <div style={{ color: "var(--muted)", fontSize: "0.8125rem" }}>
        Connecting to VesselOptima backend...
      </div>
    );
  }

  return (
    <div>
      {/* Page title */}
      <h1
        style={{
          fontSize: "0.875rem",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: "var(--muted)",
          marginBottom: "var(--space-4)",
        }}
      >
        Market Overview
      </h1>

      {/* Status panel */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "var(--space-3)",
          marginBottom: "var(--space-4)",
        }}
      >
        {/* Runtime Mode */}
        <div
          style={{
            background: "var(--surface-1)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            padding: "var(--space-3)",
          }}
        >
          <div style={{ color: "var(--muted)", fontSize: "0.6875rem", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--space-1)" }}>
            Runtime Mode
          </div>
          <div style={{ fontWeight: 600, color: mode.mode === "LIVE" ? "var(--positive)" : "var(--info)" }}>
            {mode.mode === "OFFLINE_DEMO" ? "OFFLINE DEMO" : mode.mode}
          </div>
          <div className="tabular-nums" style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "var(--space-1)" }}>
            Session: {mode.mode_session_id.slice(0, 12)}...
          </div>
        </div>

        {/* Application Status */}
        <div
          style={{
            background: "var(--surface-1)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            padding: "var(--space-3)",
          }}
        >
          <div style={{ color: "var(--muted)", fontSize: "0.6875rem", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--space-1)" }}>
            Application Status
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <span
              className="status-dot"
              style={{ background: status.app_status === "ready" ? "var(--positive)" : "var(--warning)" }}
            />
            <span style={{ fontWeight: 600 }}>{status.app_status.toUpperCase()}</span>
          </div>
          <div className="tabular-nums" style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "var(--space-1)" }}>
            DB: {status.database_status}
          </div>
        </div>

        {/* Data Context */}
        <div
          style={{
            background: "var(--surface-1)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            padding: "var(--space-3)",
          }}
        >
          <div style={{ color: "var(--muted)", fontSize: "0.6875rem", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--space-1)" }}>
            Data Context
          </div>
          <div style={{ fontWeight: 600 }}>
            {mode.data_context_id || "—"}
          </div>
          <div className="tabular-nums" style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "var(--space-1)" }}>
            Package: {mode.offline_package_id || "Not loaded (Phase 2)"}
          </div>
        </div>
      </div>

      {/* Phase 1 notice */}
      <div
        style={{
          background: "var(--surface-2)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-md)",
          padding: "var(--space-3)",
          fontSize: "0.8125rem",
          color: "var(--muted)",
          maxWidth: "640px",
        }}
      >
        <div style={{ fontWeight: 600, color: "var(--warning)", marginBottom: "var(--space-2)" }}>
          PHASE 1 — FOUNDATION
        </div>
        <p style={{ marginBottom: "var(--space-2)" }}>
          Backend API, database schema, runtime mode handling, and application shell are operational.
        </p>
        <p>
          Market data, forecasting, feasibility, optimization, and other engines will be
          implemented in subsequent phases. This page will display market indicators,
          freight benchmarks, and procurement signals.
        </p>
      </div>
    </div>
  );
}
