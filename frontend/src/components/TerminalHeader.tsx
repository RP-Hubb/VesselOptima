"use client";

import { useEffect, useState, useCallback } from "react";
import { getRuntimeStatus, switchRuntimeMode } from "@/lib/api";
import type { RuntimeStatusResponse } from "@/types/api";

/**
 * Terminal header bar — always visible.
 * Shows: app name, runtime mode, data source health, last sync, and mode switcher.
 */
export default function TerminalHeader() {
  const [status, setStatus] = useState<RuntimeStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSwitching, setIsSwitching] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [switchError, setSwitchError] = useState<string | null>(null);

  const fetchStatus = useCallback(() => {
    getRuntimeStatus()
      .then((s) => {
        setStatus(s);
        setError(null);
      })
      .catch((e) => setError(e.message || "Backend unavailable"));
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleModeSwitch = async (targetMode: "LIVE" | "OFFLINE_DEMO") => {
    setIsSwitching(true);
    setSwitchError(null);
    try {
      await switchRuntimeMode(
        targetMode,
        true,
        `User switched to ${targetMode} via Terminal Header`
      );
      fetchStatus();
      setShowModal(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to switch mode";
      setSwitchError(msg);
    } finally {
      setIsSwitching(false);
    }
  };

  const currentMode = status?.mode || "OFFLINE_DEMO";
  const modeLabel = currentMode === "OFFLINE_DEMO" ? "OFFLINE DEMO" : currentMode;
  const modeColor = currentMode === "LIVE" ? "var(--positive)" : "var(--info)";

  return (
    <>
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
            {currentMode === "LIVE" && (
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
            {currentMode === "OFFLINE_DEMO" && (
              <span style={{ color: "var(--muted)" }}>
                ◉ {status?.offline_package_id || "demo-v1"}
              </span>
            )}
          </span>

          {/* Quick Mode Switcher Trigger */}
          <button
            id="switch-mode-btn"
            onClick={() => {
              setSwitchError(null);
              setShowModal(true);
            }}
            style={{
              background: "var(--surface-2)",
              border: "1px solid var(--border)",
              color: "var(--text)",
              padding: "2px 8px",
              fontSize: "0.6875rem",
              borderRadius: "2px",
              cursor: "pointer",
              fontFamily: "inherit",
              display: "flex",
              alignItems: "center",
              gap: "4px",
            }}
            title="Switch between LIVE and OFFLINE_DEMO operating modes"
          >
            ⚙ Switch Mode
          </button>
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
                {status.timestamp ? new Date(status.timestamp).toLocaleTimeString("en-IN", {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                  timeZone: "Asia/Kolkata",
                }) : "—"}{" "}
                IST
              </span>
            </>
          ) : (
            <span>Loading...</span>
          )}
        </div>
      </header>

      {/* Mode Switcher Modal */}
      {showModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            width: "100vw",
            height: "100vh",
            background: "rgba(0, 0, 0, 0.65)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
            padding: "var(--space-4)",
          }}
        >
          <div
            style={{
              background: "var(--surface-1)",
              border: "1px solid var(--border)",
              borderRadius: "4px",
              maxWidth: "540px",
              width: "100%",
              padding: "var(--space-4)",
              boxShadow: "0 12px 32px rgba(0,0,0,0.5)",
              fontFamily: "var(--font-mono, monospace)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
              <h3 style={{ margin: 0, fontSize: "1rem", letterSpacing: "0.04em", textTransform: "uppercase" }}>
                Runtime Mode Configuration
              </h3>
              <button
                onClick={() => setShowModal(false)}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--muted)",
                  fontSize: "1.2rem",
                  cursor: "pointer",
                  padding: "0 4px",
                }}
              >
                ✕
              </button>
            </div>

            <p style={{ fontSize: "0.8125rem", color: "var(--muted)", lineHeight: 1.5, marginBottom: "var(--space-3)" }}>
              VesselOptima strictly supports two isolated operating modes: <strong>OFFLINE_DEMO</strong> and <strong>LIVE</strong>. There are no silent fallbacks.
            </p>

            <div style={{ display: "grid", gap: "var(--space-3)", marginBottom: "var(--space-4)" }}>
              {/* Option 1: OFFLINE_DEMO */}
              <div
                style={{
                  padding: "var(--space-3)",
                  border: currentMode === "OFFLINE_DEMO" ? "2px solid var(--info)" : "1px solid var(--border)",
                  borderRadius: "3px",
                  background: currentMode === "OFFLINE_DEMO" ? "rgba(56, 189, 248, 0.08)" : "var(--surface-2)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <span style={{ fontWeight: 700, color: "var(--info)", fontSize: "0.875rem" }}>
                    OFFLINE_DEMO
                  </span>
                  {currentMode === "OFFLINE_DEMO" && (
                    <span style={{ fontSize: "0.6875rem", background: "var(--info)", color: "#000", padding: "1px 6px", borderRadius: "2px", fontWeight: 700 }}>
                      ACTIVE
                    </span>
                  )}
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--muted)", lineHeight: 1.4 }}>
                  Air-gapped, zero external network dependencies. Uses verified local packages (<code>demo-v1</code>) for MILP optimization, Monte Carlo risk simulation, and strategy benchmarking.
                </div>
                {currentMode !== "OFFLINE_DEMO" && (
                  <button
                    disabled={isSwitching}
                    onClick={() => handleModeSwitch("OFFLINE_DEMO")}
                    style={{
                      marginTop: "var(--space-2)",
                      background: "var(--surface-3)",
                      border: "1px solid var(--border)",
                      color: "var(--text)",
                      padding: "4px 12px",
                      fontSize: "0.75rem",
                      borderRadius: "2px",
                      cursor: "pointer",
                    }}
                  >
                    Switch to OFFLINE_DEMO
                  </button>
                )}
              </div>

              {/* Option 2: LIVE */}
              <div
                style={{
                  padding: "var(--space-3)",
                  border: currentMode === "LIVE" ? "2px solid var(--positive)" : "1px solid var(--border)",
                  borderRadius: "3px",
                  background: currentMode === "LIVE" ? "rgba(34, 197, 94, 0.08)" : "var(--surface-2)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <span style={{ fontWeight: 700, color: "var(--positive)", fontSize: "0.875rem" }}>
                    LIVE (Production Enterprise)
                  </span>
                  {currentMode === "LIVE" && (
                    <span style={{ fontSize: "0.6875rem", background: "var(--positive)", color: "#000", padding: "1px 6px", borderRadius: "2px", fontWeight: 700 }}>
                      ACTIVE
                    </span>
                  )}
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--muted)", lineHeight: 1.4 }}>
                  Production real-world mode. Enforces real-time external data connectivity (AIS telemetry, Baltic Exchange fixtures, Platts bunker rates, PostgreSQL). Fails closed if live feeds are disconnected.
                </div>
                {currentMode !== "LIVE" && (
                  <button
                    disabled={isSwitching}
                    onClick={() => handleModeSwitch("LIVE")}
                    style={{
                      marginTop: "var(--space-2)",
                      background: "rgba(34, 197, 94, 0.15)",
                      border: "1px solid var(--positive)",
                      color: "var(--positive)",
                      padding: "4px 12px",
                      fontSize: "0.75rem",
                      borderRadius: "2px",
                      cursor: "pointer",
                      fontWeight: 600,
                    }}
                  >
                    Switch to LIVE Mode
                  </button>
                )}
              </div>
            </div>

            {switchError && (
              <div
                style={{
                  background: "rgba(239, 68, 68, 0.1)",
                  border: "1px solid var(--danger)",
                  color: "var(--danger)",
                  padding: "var(--space-2)",
                  fontSize: "0.75rem",
                  marginBottom: "var(--space-3)",
                  borderRadius: "2px",
                }}
              >
                {switchError}
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}>
              <button
                onClick={() => setShowModal(false)}
                style={{
                  background: "var(--surface-2)",
                  border: "1px solid var(--border)",
                  color: "var(--text)",
                  padding: "6px 14px",
                  fontSize: "0.75rem",
                  borderRadius: "2px",
                  cursor: "pointer",
                }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
