"use client";

import { useEffect, useState } from "react";
import { getRuntimeStatus } from "@/lib/api";
import type { RuntimeStatusResponse } from "@/types/api";

/**
 * Terminal header bar — always visible.
 * Shows: app name, runtime mode, data source health, last sync.
 *
 * Per Build Spec Section W:
 * "DATA: LIVE ● 4/5 SOURCES HEALTHY" or
 * "DATA: OFFLINE DEMO ◉ PACKAGE VO-YYYY.MM.DD"
 */
export default function TerminalHeader() {
  const [status, setStatus] = useState<RuntimeStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getRuntimeStatus()
      .then(setStatus)
      .catch((e) => setError(e.message || "Backend unavailable"));
  }, []);

  const modeLabel = status?.mode === "OFFLINE_DEMO" ? "OFFLINE DEMO" : status?.mode || "—";
  const modeColor = status?.mode === "LIVE" ? "var(--positive)" : "var(--info)";

  return (
    <header
      style={{
        background: "var(--surface-1)",
        borderBottom: "1px solid var(--border)",
        padding: "var(--space-2) var(--space-4)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        fontSize: "0.8125rem",
        fontFamily: "'ui-monospace', 'SFMono-Regular', monospace",
        minHeight: "36px",
      }}
    >
      {/* Left: App name + mode */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
        <span style={{ fontWeight: 700, fontSize: "0.875rem", letterSpacing: "0.05em" }}>
          VESSELOPTIMA
        </span>

        <span
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-2)",
          }}
        >
          <span style={{ color: "var(--muted)" }}>DATA:</span>
          <span style={{ color: modeColor, fontWeight: 600 }}>{modeLabel}</span>
          {status?.mode === "LIVE" && (
            <span
              className="status-dot"
              style={{
                background: status?.app_status === "ready" ? "var(--positive)" : "var(--warning)",
              }}
              title={`Status: ${status?.app_status}`}
              role="img"
              aria-label={`Status: ${status?.app_status}`}
            />
          )}
          {status?.mode === "OFFLINE_DEMO" && (
            <span style={{ color: "var(--muted)" }}>
              ◉ {status?.offline_package_id || "NO PACKAGE"}
            </span>
          )}
        </span>
      </div>

      {/* Right: Status indicators */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)", color: "var(--muted)" }}>
        {error ? (
          <span style={{ color: "var(--negative)" }}>
            ● BACKEND UNAVAILABLE
          </span>
        ) : status ? (
          <>
            <span>
              DB: <span style={{ color: status.database_status === "healthy" ? "var(--positive)" : "var(--negative)" }}>
                {status.database_status.toUpperCase()}
              </span>
            </span>
            <span style={{ fontSize: "0.75rem" }}>
              {new Date(status.timestamp).toLocaleTimeString("en-IN", {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
                timeZone: "Asia/Kolkata",
              })}{" "}
              IST
            </span>
          </>
        ) : (
          <span>Loading...</span>
        )}
      </div>
    </header>
  );
}
