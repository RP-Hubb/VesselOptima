"use client";

import React, { useState, useEffect } from "react";
import {
  getDatasets,
  getDataset,
  importDataset,
  importDatasetVersion,
  approveDataset,
  rejectDataset,
  getDatasetQuarantine,
  getDatasetDiff,
  getDatasetImpact,
  seedDataDemo,
} from "@/lib/api";
import type {
  DatasetResponse,
  DatasetType,
  DatasetStatus,
  QuarantineItemResponse,
  DatasetDiffResponse,
  DatasetImpactResponse,
  DatasetQualityReport,
} from "@/types/api";

type ActiveTab = "registry" | "import" | "quality" | "quarantine" | "diff_impact" | "approval";

const DATASET_TYPE_LABELS: Record<DatasetType, string> = {
  VESSEL_MASTER: "Vessel Master Registry",
  PORT_REFERENCE: "Port Reference & Restrictions",
  CARGO_DEMAND: "Cargo Demand & Commitments",
  VOYAGE_FIXTURE: "Market Fixtures & Benchmarks",
  BUNKER_SERIES: "Bunker Fuel Spot & Futures",
  OPERATIONAL_EVENT: "Operational Events & Logs",
};

const SAMPLE_CSV_PAYLOAD = `vessel_id,vessel_name,dwt,loa,beam,draft,service_speed,fuel_consumption
VO-VL-01,VO Amber Leader,75200.0,225.0,32.26,14.2,13.5,28.5
VO-VL-02,VO Atlantic Pioneer,82150.0,229.0,32.26,14.5,14.0,31.0
VO-VL-03,VO Pacific Voyager,181200.0,292.0,45.0,18.2,14.5,52.0`;

export default function DataGovernancePage() {
  const [loading, setLoading] = useState<boolean>(false);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>("registry");

  // Main state
  const [datasets, setDatasets] = useState<DatasetResponse[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [currentDataset, setCurrentDataset] = useState<DatasetResponse | null>(null);
  const [quarantineItems, setQuarantineItems] = useState<QuarantineItemResponse[]>([]);
  const [diffResult, setDiffResult] = useState<DatasetDiffResponse | null>(null);
  const [impactResult, setImpactResult] = useState<DatasetImpactResponse | null>(null);

  // Ingestion form state
  const [importType, setImportType] = useState<DatasetType>("VESSEL_MASTER");
  const [importName, setImportName] = useState<string>("Bulk Fleet Master Registry");
  const [importDesc, setImportDesc] = useState<string>("Air-gapped vessel operational specifications");
  const [rawContent, setRawContent] = useState<string>(SAMPLE_CSV_PAYLOAD);
  const [actorName, setActorName] = useState<string>("data_steward_raj");
  const [actorRole, setActorRole] = useState<string>("DATA_STEWARD");

  // Approval form state
  const [approvalNotes, setApprovalNotes] = useState<string>("Validated against physical naval architecture specifications.");
  const [rejectReason, setRejectReason] = useState<string>("");

  useEffect(() => {
    loadDatasets();
  }, []);

  useEffect(() => {
    if (selectedDatasetId) {
      loadDatasetDetails(selectedDatasetId);
    }
  }, [selectedDatasetId]);

  async function loadDatasets() {
    setLoading(true);
    setError(null);
    try {
      let list = await getDatasets();
      if (list.length === 0) {
        // Automatically seed canonical demo if empty
        const seeded = await seedDataDemo("CANONICAL");
        list = await getDatasets();
        setSelectedDatasetId(seeded.dataset_id);
      } else {
        if (!selectedDatasetId && list.length > 0) {
          setSelectedDatasetId(list[0].dataset_id);
        }
      }
      setDatasets(list);
    } catch (err: any) {
      console.error("Failed to load datasets:", err);
      setError(err.message || "Failed to load data governance registry.");
    } finally {
      setLoading(false);
    }
  }

  async function loadDatasetDetails(dsId: string) {
    setError(null);
    try {
      const [ds, quar, diff, impact] = await Promise.all([
        getDataset(dsId),
        getDatasetQuarantine(dsId).catch(() => []),
        getDatasetDiff(dsId).catch(() => null),
        getDatasetImpact(dsId).catch(() => null),
      ]);
      setCurrentDataset(ds);
      setQuarantineItems(quar);
      setDiffResult(diff);
      setImpactResult(impact);
    } catch (err: any) {
      console.error("Failed to load dataset details:", err);
      setError(err.message || "Failed to load dataset details.");
    }
  }

  async function handleSeedDemo() {
    setActionLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const seeded = await seedDataDemo("CANONICAL");
      setSuccessMsg(`Canonical datasets seeded successfully: ${seeded.dataset_id} (Version ${seeded.current_version})`);
      await loadDatasets();
      setSelectedDatasetId(seeded.dataset_id);
      setActiveTab("diff_impact");
    } catch (err: any) {
      setError(err.message || "Failed to seed demo data.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleImportSubmit(e: React.FormEvent) {
    e.preventDefault();
    setActionLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await importDataset({
        dataset_type: importType,
        name: importName,
        description: importDesc,
        raw_content: rawContent,
        filename: `${importType.toLowerCase()}_import.csv`,
        actor: actorName,
        actor_role: actorRole,
      });
      setSuccessMsg(`Dataset ${res.dataset_id} ingested successfully with status ${res.status}. Quality Score: ${res.quality_score.toFixed(1)}%`);
      await loadDatasets();
      setSelectedDatasetId(res.dataset_id);
      setActiveTab("quality");
    } catch (err: any) {
      setError(err.message || "Dataset ingestion failed.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleApprove() {
    if (!currentDataset) return;
    setActionLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await approveDataset(currentDataset.dataset_id, {
        actor: actorName,
        actor_role: actorRole,
        notes: approvalNotes,
      });
      setSuccessMsg(`Dataset ${res.dataset_id} APPROVED by ${actorName} (${actorRole}).`);
      await loadDatasetDetails(res.dataset_id);
      await loadDatasets();
    } catch (err: any) {
      setError(err.message || "Dataset approval failed.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReject() {
    if (!currentDataset || !rejectReason.trim()) {
      setError("A formal rejection reason is mandatory.");
      return;
    }
    setActionLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await rejectDataset(currentDataset.dataset_id, {
        actor: actorName,
        actor_role: actorRole,
        reason: rejectReason,
        notes: approvalNotes,
      });
      setSuccessMsg(`Dataset ${res.dataset_id} marked REJECTED.`);
      await loadDatasetDetails(res.dataset_id);
      await loadDatasets();
    } catch (err: any) {
      setError(err.message || "Dataset rejection failed.");
    } finally {
      setActionLoading(false);
    }
  }

  // Helpers
  const getStatusBadge = (status: DatasetStatus | string) => {
    const s = String(status).toUpperCase();
    let bg = "var(--surface-3)";
    let border = "var(--border)";
    let text = "var(--text)";

    if (s === "APPROVED" || s === "VALID") {
      bg = "rgba(16, 185, 129, 0.15)";
      border = "rgba(16, 185, 129, 0.4)";
      text = "#10b981";
    } else if (s === "QUARANTINED") {
      bg = "rgba(245, 158, 11, 0.15)";
      border = "rgba(245, 158, 11, 0.4)";
      text = "#f59e0b";
    } else if (s === "INVALID" || s === "REJECTED") {
      bg = "rgba(239, 68, 68, 0.15)";
      border = "rgba(239, 68, 68, 0.4)";
      text = "#ef4444";
    } else if (s === "SUPERSEDED") {
      bg = "rgba(100, 116, 139, 0.15)";
      border = "rgba(100, 116, 139, 0.4)";
      text = "#94a3b8";
    }

    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "4px",
          padding: "2px 8px",
          borderRadius: "4px",
          fontSize: "0.6875rem",
          fontWeight: 700,
          background: bg,
          border: `1px solid ${border}`,
          color: text,
          letterSpacing: "0.05em",
        }}
      >
        <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: text }} />
        {s}
      </span>
    );
  };

  const getFreshnessBadge = (fresh: string) => {
    let color = "#94a3b8";
    if (fresh === "CURRENT") color = "#10b981";
    if (fresh === "AGING") color = "#f59e0b";
    if (fresh === "STALE") color = "#ef4444";

    return (
      <span
        style={{
          padding: "2px 6px",
          borderRadius: "3px",
          fontSize: "0.6875rem",
          fontWeight: 600,
          background: "var(--surface-2)",
          border: `1px solid ${color}`,
          color: color,
        }}
      >
        {fresh}
      </span>
    );
  };

  const getImpactBadge = (lvl: string) => {
    let color = "#94a3b8";
    if (lvl === "CRITICAL" || lvl === "HIGH") color = "#ef4444";
    if (lvl === "MEDIUM") color = "#f59e0b";
    if (lvl === "LOW") color = "#3b82f6";
    if (lvl === "NONE") color = "#10b981";

    return (
      <span
        style={{
          padding: "2px 6px",
          borderRadius: "3px",
          fontSize: "0.6875rem",
          fontWeight: 700,
          background: "var(--surface-2)",
          border: `1px solid ${color}`,
          color: color,
        }}
      >
        {lvl} IMPACT
      </span>
    );
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "var(--bg)",
        color: "var(--text)",
        overflow: "hidden",
        fontSize: "0.8125rem",
      }}
    >
      {/* ── TOP BANNER & INSTITUTIONAL CONTROLS ── */}
      <header
        style={{
          padding: "var(--space-3) var(--space-4)",
          background: "var(--surface-1)",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "var(--space-3)",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <h1 style={{ fontSize: "1.125rem", fontWeight: 700, margin: 0, letterSpacing: "-0.01em" }}>
              Maritime Data Integration & Data Quality Governance
            </h1>
            <span
              style={{
                fontSize: "0.6875rem",
                padding: "2px 6px",
                background: "rgba(14, 165, 233, 0.15)",
                color: "var(--info)",
                border: "1px solid var(--info)",
                borderRadius: "3px",
                fontWeight: 600,
              }}
            >
              PHASE 12 ACTIVE
            </span>
          </div>
          <p style={{ margin: 0, fontSize: "0.75rem", color: "var(--muted)", marginTop: "2px" }}>
            Air-gapped data foundation • 4-tier validation • 6-factor quality scoring • Cryptographic SHA-256 integrity • Stale decision tracking
          </p>
        </div>

        {/* Global Action Bar */}
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <div
            style={{
              padding: "4px 8px",
              background: "rgba(16, 185, 129, 0.1)",
              border: "1px solid rgba(16, 185, 129, 0.3)",
              borderRadius: "4px",
              fontSize: "0.6875rem",
              color: "#10b981",
              fontWeight: 600,
            }}
          >
            AIR-GAP: ZERO OUTBOUND SOCKETS
          </div>

          <button
            onClick={handleSeedDemo}
            disabled={actionLoading}
            style={{
              padding: "6px 12px",
              background: "var(--surface-3)",
              border: "1px solid var(--border)",
              borderRadius: "4px",
              color: "var(--text)",
              cursor: actionLoading ? "not-allowed" : "pointer",
              fontWeight: 600,
              fontSize: "0.75rem",
            }}
          >
            {actionLoading ? "Seeding..." : "Seed Canonical Demo (V1 & V2)"}
          </button>

          <button
            onClick={loadDatasets}
            disabled={loading}
            style={{
              padding: "6px 12px",
              background: "var(--surface-2)",
              border: "1px solid var(--border)",
              borderRadius: "4px",
              color: "var(--text)",
              cursor: loading ? "not-allowed" : "pointer",
              fontSize: "0.75rem",
            }}
          >
            Refresh
          </button>
        </div>
      </header>

      {/* ── NOTIFICATION TOASTS ── */}
      {error && (
        <div
          style={{
            padding: "var(--space-2) var(--space-4)",
            background: "rgba(239, 68, 68, 0.15)",
            borderBottom: "1px solid rgba(239, 68, 68, 0.4)",
            color: "#f87171",
            fontSize: "0.75rem",
            display: "flex",
            justifyContent: "space-between",
          }}
        >
          <span>{error}</span>
          <button onClick={() => setError(null)} style={{ background: "none", border: "none", color: "#f87171", cursor: "pointer" }}>
            ✕
          </button>
        </div>
      )}
      {successMsg && (
        <div
          style={{
            padding: "var(--space-2) var(--space-4)",
            background: "rgba(16, 185, 129, 0.15)",
            borderBottom: "1px solid rgba(16, 185, 129, 0.4)",
            color: "#34d399",
            fontSize: "0.75rem",
            display: "flex",
            justifyContent: "space-between",
          }}
        >
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} style={{ background: "none", border: "none", color: "#34d399", cursor: "pointer" }}>
            ✕
          </button>
        </div>
      )}

      {/* ── MAIN WORKSPACE: SIDEBAR + CONTENT ── */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* LEFT DATASET SELECTOR LIST */}
        <aside
          style={{
            width: "280px",
            minWidth: "280px",
            borderRight: "1px solid var(--border)",
            background: "var(--surface-1)",
            display: "flex",
            flexDirection: "column",
            overflowY: "auto",
          }}
        >
          <div style={{ padding: "var(--space-3)", borderBottom: "1px solid var(--border)", fontWeight: 700, fontSize: "0.75rem", color: "var(--muted)" }}>
            GOVERNANCE DATASET REGISTRY ({datasets.length})
          </div>

          <div style={{ flex: 1, overflowY: "auto" }}>
            {datasets.map((ds) => {
              const isSelected = selectedDatasetId === ds.dataset_id;
              return (
                <div
                  key={ds.dataset_id}
                  onClick={() => setSelectedDatasetId(ds.dataset_id)}
                  style={{
                    padding: "var(--space-3)",
                    borderBottom: "1px solid var(--border)",
                    cursor: "pointer",
                    background: isSelected ? "var(--surface-2)" : "transparent",
                    borderLeft: isSelected ? "3px solid var(--info)" : "3px solid transparent",
                    transition: "all 120ms ease",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "4px" }}>
                    <span style={{ fontWeight: 700, color: isSelected ? "var(--text)" : "var(--text)", fontSize: "0.8125rem" }}>
                      {ds.name}
                    </span>
                    {getStatusBadge(ds.status)}
                  </div>
                  <div style={{ fontSize: "0.6875rem", color: "var(--muted)", marginBottom: "4px" }}>
                    ID: <span className="tabular-nums" style={{ color: "var(--text)" }}>{ds.dataset_id}</span> • v{ds.current_version}
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.6875rem" }}>
                    <span>
                      Quality: <strong style={{ color: ds.quality_score >= 80 ? "#10b981" : "#f59e0b" }}>{ds.quality_score.toFixed(1)}%</strong>
                    </span>
                    <span>{getFreshnessBadge(ds.freshness_status)}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* User Persona Switcher */}
          <div style={{ padding: "var(--space-3)", borderTop: "1px solid var(--border)", background: "var(--surface-2)", fontSize: "0.6875rem" }}>
            <div style={{ fontWeight: 700, color: "var(--muted)", marginBottom: "4px" }}>ACTOR CREDENTIALS</div>
            <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
              <input
                type="text"
                value={actorName}
                onChange={(e) => setActorName(e.target.value)}
                style={{
                  flex: 1,
                  padding: "4px",
                  background: "var(--surface-1)",
                  border: "1px solid var(--border)",
                  color: "var(--text)",
                  borderRadius: "3px",
                  fontSize: "0.6875rem",
                }}
              />
              <select
                value={actorRole}
                onChange={(e) => setActorRole(e.target.value)}
                style={{
                  padding: "4px",
                  background: "var(--surface-1)",
                  border: "1px solid var(--border)",
                  color: "var(--text)",
                  borderRadius: "3px",
                  fontSize: "0.6875rem",
                }}
              >
                <option value="DATA_STEWARD">DATA_STEWARD</option>
                <option value="APPROVER">APPROVER</option>
                <option value="ANALYST">ANALYST</option>
                <option value="ADMIN">ADMIN</option>
              </select>
            </div>
          </div>
        </aside>

        {/* RIGHT MAIN VIEW AREA */}
        <main style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {/* TAB NAVIGATION */}
          <div
            style={{
              display: "flex",
              borderBottom: "1px solid var(--border)",
              background: "var(--surface-1)",
              padding: "0 var(--space-4)",
            }}
          >
            {(
              [
                { id: "registry", label: "Dataset Overview" },
                { id: "import", label: "Air-Gapped Ingestion" },
                { id: "quality", label: "Quality & 4-Tier Validation" },
                { id: "quarantine", label: `Quarantine Defect Ledger (${quarantineItems.length})` },
                { id: "diff_impact", label: "Version Diff & Stale Decisions" },
                { id: "approval", label: "Institutional Sign-Off" },
              ] as { id: ActiveTab; label: string }[]
            ).map((tab) => {
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    padding: "var(--space-3) var(--space-4)",
                    background: "none",
                    border: "none",
                    borderBottom: active ? "2px solid var(--info)" : "2px solid transparent",
                    color: active ? "var(--text)" : "var(--muted)",
                    fontWeight: active ? 700 : 500,
                    cursor: "pointer",
                    fontSize: "0.8125rem",
                    transition: "all 120ms ease",
                  }}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* TAB CONTENT AREA */}
          <div style={{ flex: 1, overflowY: "auto", padding: "var(--space-4)" }}>
            {/* 1. OVERVIEW TAB */}
            {activeTab === "registry" && (
              <div>
                {currentDataset ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
                    {/* Top Dataset Metrics Card */}
                    <div
                      style={{
                        background: "var(--surface-1)",
                        border: "1px solid var(--border)",
                        borderRadius: "6px",
                        padding: "var(--space-4)",
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                        gap: "var(--space-3)",
                      }}
                    >
                      <div>
                        <div style={{ fontSize: "0.6875rem", color: "var(--muted)", textTransform: "uppercase" }}>Dataset Type</div>
                        <div style={{ fontSize: "0.9375rem", fontWeight: 700, marginTop: "2px" }}>
                          {DATASET_TYPE_LABELS[currentDataset.dataset_type] || currentDataset.dataset_type}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: "0.6875rem", color: "var(--muted)", textTransform: "uppercase" }}>Version / Status</div>
                        <div style={{ fontSize: "0.9375rem", fontWeight: 700, marginTop: "2px", display: "flex", gap: "6px", alignItems: "center" }}>
                          <span>v{currentDataset.current_version}</span>
                          {getStatusBadge(currentDataset.status)}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: "0.6875rem", color: "var(--muted)", textTransform: "uppercase" }}>Quality Score</div>
                        <div style={{ fontSize: "0.9375rem", fontWeight: 700, marginTop: "2px", color: currentDataset.quality_score >= 80 ? "#10b981" : "#f59e0b" }}>
                          {currentDataset.quality_score.toFixed(1)}% ({currentDataset.freshness_status})
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: "0.6875rem", color: "var(--muted)", textTransform: "uppercase" }}>Record Count</div>
                        <div style={{ fontSize: "0.9375rem", fontWeight: 700, marginTop: "2px" }}>
                          <span className="tabular-nums">{currentDataset.record_count}</span> rows
                        </div>
                      </div>
                    </div>

                    {/* Cryptographic Content Hash & Provenance Card */}
                    <div
                      style={{
                        background: "var(--surface-1)",
                        border: "1px solid var(--border)",
                        borderRadius: "6px",
                        padding: "var(--space-4)",
                      }}
                    >
                      <h3 style={{ margin: "0 0 var(--space-3) 0", fontSize: "0.875rem", fontWeight: 700 }}>
                        Cryptographic SHA-256 Provenance & Audit Hash
                      </h3>
                      <div
                        style={{
                          padding: "var(--space-2) var(--space-3)",
                          background: "var(--surface-2)",
                          borderRadius: "4px",
                          fontFamily: "monospace",
                          fontSize: "0.75rem",
                          wordBreak: "break-all",
                          color: "var(--info)",
                        }}
                      >
                        {currentDataset.content_hash}
                      </div>

                      <div style={{ marginTop: "var(--space-3)", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)", fontSize: "0.75rem" }}>
                        <div>
                          <span style={{ color: "var(--muted)" }}>Created By:</span>{" "}
                          <strong>{currentDataset.created_by}</strong> ({new Date(currentDataset.created_at).toLocaleString()})
                        </div>
                        <div>
                          <span style={{ color: "var(--muted)" }}>Approved By:</span>{" "}
                          <strong>{currentDataset.approved_by || "Pending Approval"}</strong>
                          {currentDataset.approved_at && ` (${new Date(currentDataset.approved_at).toLocaleString()})`}
                        </div>
                      </div>
                    </div>

                    {/* Sample Records View */}
                    {currentDataset.sample_records && currentDataset.sample_records.length > 0 && (
                      <div
                        style={{
                          background: "var(--surface-1)",
                          border: "1px solid var(--border)",
                          borderRadius: "6px",
                          padding: "var(--space-4)",
                        }}
                      >
                        <h3 style={{ margin: "0 0 var(--space-3) 0", fontSize: "0.875rem", fontWeight: 700 }}>
                          Sample Ingested Records ({currentDataset.sample_records.length} shown)
                        </h3>
                        <div style={{ overflowX: "auto" }}>
                          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.6875rem" }}>
                            <thead>
                              <tr style={{ background: "var(--surface-2)", borderBottom: "1px solid var(--border)" }}>
                                {Object.keys(currentDataset.sample_records[0]).map((col) => (
                                  <th key={col} style={{ padding: "6px 10px", textAlign: "left", color: "var(--muted)", fontWeight: 600 }}>
                                    {col}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {currentDataset.sample_records.map((r, i) => (
                                <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                                  {Object.values(r).map((val: any, j) => (
                                    <td key={j} style={{ padding: "6px 10px" }}>
                                      {typeof val === "number" ? val.toLocaleString() : String(val ?? "—")}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ color: "var(--muted)", textAlign: "center", padding: "var(--space-8)" }}>
                    Select a dataset from the registry or click "Seed Canonical Demo".
                  </div>
                )}
              </div>
            )}

            {/* 2. AIR-GAPPED INGESTION TAB */}
            {activeTab === "import" && (
              <div style={{ maxWidth: "800px" }}>
                <div
                  style={{
                    background: "var(--surface-1)",
                    border: "1px solid var(--border)",
                    borderRadius: "6px",
                    padding: "var(--space-4)",
                  }}
                >
                  <h3 style={{ margin: "0 0 var(--space-2) 0", fontSize: "0.875rem", fontWeight: 700 }}>
                    Air-Gapped Data Ingestion Console
                  </h3>
                  <p style={{ margin: "0 0 var(--space-4) 0", fontSize: "0.75rem", color: "var(--muted)" }}>
                    Ingest local maritime CSV or JSON files. Ingested datasets undergo 4-tier validation, unit normalization, and SHA-256 canonical hashing before acceptance.
                  </p>

                  <form onSubmit={handleImportSubmit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
                      <div>
                        <label style={{ display: "block", fontSize: "0.6875rem", color: "var(--muted)", marginBottom: "4px" }}>
                          DATASET DOMAIN SCHEMA
                        </label>
                        <select
                          value={importType}
                          onChange={(e) => setImportType(e.target.value as DatasetType)}
                          style={{
                            width: "100%",
                            padding: "6px 10px",
                            background: "var(--surface-2)",
                            border: "1px solid var(--border)",
                            color: "var(--text)",
                            borderRadius: "4px",
                            fontSize: "0.75rem",
                          }}
                        >
                          <option value="VESSEL_MASTER">VESSEL_MASTER (Specifications, Speed, Consumption)</option>
                          <option value="PORT_REFERENCE">PORT_REFERENCE (Coordinates, Max Draft, LOA Limits)</option>
                          <option value="CARGO_DEMAND">CARGO_DEMAND (Laycan Windows, Quantities, Ports)</option>
                          <option value="VOYAGE_FIXTURE">VOYAGE_FIXTURE (Freight Rates, USD Benchmarks)</option>
                          <option value="BUNKER_SERIES">BUNKER_SERIES (VLSFO / MGO Port Prices)</option>
                          <option value="OPERATIONAL_EVENT">OPERATIONAL_EVENT (Weather, Port Delays)</option>
                        </select>
                      </div>

                      <div>
                        <label style={{ display: "block", fontSize: "0.6875rem", color: "var(--muted)", marginBottom: "4px" }}>
                          DATASET NAME
                        </label>
                        <input
                          type="text"
                          value={importName}
                          onChange={(e) => setImportName(e.target.value)}
                          required
                          style={{
                            width: "100%",
                            padding: "6px 10px",
                            background: "var(--surface-2)",
                            border: "1px solid var(--border)",
                            color: "var(--text)",
                            borderRadius: "4px",
                            fontSize: "0.75rem",
                          }}
                        />
                      </div>
                    </div>

                    <div>
                      <label style={{ display: "block", fontSize: "0.6875rem", color: "var(--muted)", marginBottom: "4px" }}>
                        DESCRIPTION & AUDIT PURPOSE
                      </label>
                      <input
                        type="text"
                        value={importDesc}
                        onChange={(e) => setImportDesc(e.target.value)}
                        style={{
                          width: "100%",
                          padding: "6px 10px",
                          background: "var(--surface-2)",
                          border: "1px solid var(--border)",
                          color: "var(--text)",
                          borderRadius: "4px",
                          fontSize: "0.75rem",
                        }}
                      />
                    </div>

                    <div>
                      <label style={{ display: "block", fontSize: "0.6875rem", color: "var(--muted)", marginBottom: "4px" }}>
                        PAYLOAD (CSV OR JSON TEXT)
                      </label>
                      <textarea
                        rows={8}
                        value={rawContent}
                        onChange={(e) => setRawContent(e.target.value)}
                        style={{
                          width: "100%",
                          padding: "8px 10px",
                          background: "var(--surface-2)",
                          border: "1px solid var(--border)",
                          color: "var(--text)",
                          borderRadius: "4px",
                          fontFamily: "monospace",
                          fontSize: "0.75rem",
                        }}
                      />
                    </div>

                    <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}>
                      <button
                        type="submit"
                        disabled={actionLoading}
                        style={{
                          padding: "8px 16px",
                          background: "var(--info)",
                          border: "none",
                          borderRadius: "4px",
                          color: "#fff",
                          fontWeight: 700,
                          cursor: actionLoading ? "not-allowed" : "pointer",
                          fontSize: "0.75rem",
                        }}
                      >
                        {actionLoading ? "Validating & Ingesting..." : "Ingest & Validate Dataset"}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}

            {/* 3. QUALITY & 4-TIER VALIDATION TAB */}
            {activeTab === "quality" && (
              <div>
                {currentDataset ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
                    {/* 4-Tier Validation Gates */}
                    <div
                      style={{
                        background: "var(--surface-1)",
                        border: "1px solid var(--border)",
                        borderRadius: "6px",
                        padding: "var(--space-4)",
                      }}
                    >
                      <h3 style={{ margin: "0 0 var(--space-3) 0", fontSize: "0.875rem", fontWeight: 700 }}>
                        4-Tier Validation Engine Summary
                      </h3>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
                        {[
                          {
                            name: "Tier 1: Structural",
                            desc: "Mandatory contract fields & business-key presence",
                            pass: currentDataset.validation_summary?.STRUCTURAL ?? true,
                          },
                          {
                            name: "Tier 2: Type & Units",
                            desc: "Numeric casting, timestamp UTC parsing, explicit currency",
                            pass: currentDataset.validation_summary?.TYPE ?? true,
                          },
                          {
                            name: "Tier 3: Physical Bounds",
                            desc: "DWT > 0, speed > 0, draft, latitude [-90,90]",
                            pass: currentDataset.validation_summary?.PHYSICAL ?? true,
                          },
                          {
                            name: "Tier 4: Relational Rules",
                            desc: "Origin != Destination, Laycan Start <= End, Uniqueness",
                            pass: currentDataset.validation_summary?.RELATIONAL ?? true,
                          },
                        ].map((gate) => (
                          <div
                            key={gate.name}
                            style={{
                              padding: "var(--space-3)",
                              background: "var(--surface-2)",
                              border: `1px solid ${gate.pass ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.4)"}`,
                              borderRadius: "4px",
                            }}
                          >
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                              <span style={{ fontWeight: 700, fontSize: "0.75rem" }}>{gate.name}</span>
                              <span
                                style={{
                                  fontSize: "0.6875rem",
                                  fontWeight: 700,
                                  color: gate.pass ? "#10b981" : "#ef4444",
                                }}
                              >
                                {gate.pass ? "PASSED" : "FAILED"}
                              </span>
                            </div>
                            <div style={{ fontSize: "0.6875rem", color: "var(--muted)", marginTop: "4px" }}>{gate.desc}</div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Transparent 6-Factor Quality Radar/Scorecards */}
                    {currentDataset.quality_report && (
                      <div
                        style={{
                          background: "var(--surface-1)",
                          border: "1px solid var(--border)",
                          borderRadius: "6px",
                          padding: "var(--space-4)",
                        }}
                      >
                        <h3 style={{ margin: "0 0 var(--space-3) 0", fontSize: "0.875rem", fontWeight: 700 }}>
                          Transparent 6-Factor Quality Score: {currentDataset.quality_score.toFixed(1)}%
                        </h3>
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
                          {[
                            { name: "Completeness", weight: "25%", score: currentDataset.quality_report.completeness_score },
                            { name: "Validity", weight: "25%", score: currentDataset.quality_report.validity_score },
                            { name: "Consistency", weight: "20%", score: currentDataset.quality_report.consistency_score },
                            { name: "Uniqueness", weight: "10%", score: currentDataset.quality_report.uniqueness_score },
                            { name: "Timeliness", weight: "10%", score: currentDataset.quality_report.timeliness_score },
                            { name: "Provenance", weight: "10%", score: currentDataset.quality_report.provenance_score },
                          ].map((fac) => (
                            <div
                              key={fac.name}
                              style={{
                                padding: "var(--space-3)",
                                background: "var(--surface-2)",
                                borderRadius: "4px",
                                border: "1px solid var(--border)",
                              }}
                            >
                              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.6875rem", color: "var(--muted)" }}>
                                <span>{fac.name}</span>
                                <span>wt {fac.weight}</span>
                              </div>
                              <div style={{ fontSize: "1.125rem", fontWeight: 700, marginTop: "4px", color: fac.score >= 80 ? "#10b981" : "#f59e0b" }}>
                                {fac.score.toFixed(1)}%
                              </div>
                              <div style={{ width: "100%", height: "4px", background: "var(--surface-3)", borderRadius: "2px", marginTop: "4px" }}>
                                <div
                                  style={{
                                    width: `${Math.min(100, Math.max(0, fac.score))}%`,
                                    height: "100%",
                                    background: fac.score >= 80 ? "#10b981" : "#f59e0b",
                                    borderRadius: "2px",
                                  }}
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ color: "var(--muted)", textAlign: "center", padding: "var(--space-8)" }}>Select a dataset to view quality metrics.</div>
                )}
              </div>
            )}

            {/* 4. QUARANTINE DEFECT LEDGER TAB */}
            {activeTab === "quarantine" && (
              <div>
                <div
                  style={{
                    background: "var(--surface-1)",
                    border: "1px solid var(--border)",
                    borderRadius: "6px",
                    padding: "var(--space-4)",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
                    <div>
                      <h3 style={{ margin: 0, fontSize: "0.875rem", fontWeight: 700 }}>
                        Quarantine Defect Ledger
                      </h3>
                      <p style={{ margin: "2px 0 0 0", fontSize: "0.6875rem", color: "var(--muted)" }}>
                        Records violating physical or relational maritime rules are quarantined without halting the pipeline.
                      </p>
                    </div>
                    <span
                      style={{
                        padding: "2px 8px",
                        background: quarantineItems.length > 0 ? "rgba(245, 158, 11, 0.15)" : "rgba(16, 185, 129, 0.15)",
                        color: quarantineItems.length > 0 ? "#f59e0b" : "#10b981",
                        border: `1px solid ${quarantineItems.length > 0 ? "#f59e0b" : "#10b981"}`,
                        borderRadius: "4px",
                        fontWeight: 700,
                        fontSize: "0.6875rem",
                      }}
                    >
                      {quarantineItems.length} DEFECTS RECORDED
                    </span>
                  </div>

                  {quarantineItems.length > 0 ? (
                    <div style={{ overflowX: "auto" }}>
                      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.6875rem" }}>
                        <thead>
                          <tr style={{ background: "var(--surface-2)", borderBottom: "1px solid var(--border)" }}>
                            <th style={{ padding: "6px 10px", textAlign: "left" }}>Row #</th>
                            <th style={{ padding: "6px 10px", textAlign: "left" }}>Business Key</th>
                            <th style={{ padding: "6px 10px", textAlign: "left" }}>Defect Field</th>
                            <th style={{ padding: "6px 10px", textAlign: "left" }}>Reason Code</th>
                            <th style={{ padding: "6px 10px", textAlign: "left" }}>Original Value</th>
                            <th style={{ padding: "6px 10px", textAlign: "left" }}>Severity</th>
                            <th style={{ padding: "6px 10px", textAlign: "left" }}>Audit Explanation</th>
                          </tr>
                        </thead>
                        <tbody>
                          {quarantineItems.map((q) => (
                            <tr key={q.id} style={{ borderBottom: "1px solid var(--border)" }}>
                              <td style={{ padding: "6px 10px" }} className="tabular-nums">
                                {q.record_index + 1}
                              </td>
                              <td style={{ padding: "6px 10px", fontWeight: 600 }}>{q.business_key}</td>
                              <td style={{ padding: "6px 10px", color: "var(--info)" }}>{q.field_name}</td>
                              <td style={{ padding: "6px 10px" }}>
                                <span
                                  style={{
                                    padding: "1px 4px",
                                    background: "rgba(239, 68, 68, 0.1)",
                                    color: "#ef4444",
                                    borderRadius: "2px",
                                  }}
                                >
                                  {q.error_code}
                                </span>
                              </td>
                              <td style={{ padding: "6px 10px", fontFamily: "monospace" }}>{q.original_value ?? "null"}</td>
                              <td style={{ padding: "6px 10px" }}>{q.severity}</td>
                              <td style={{ padding: "6px 10px", color: "var(--muted)" }}>{q.message}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div style={{ textAlign: "center", padding: "var(--space-6)", color: "var(--muted)" }}>
                      Zero defect records found in quarantine ledger. All rows passed physical and relational checks.
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* 5. VERSION DIFF & STALE DECISION IMPACT TAB */}
            {activeTab === "diff_impact" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
                {/* Impact Analysis Banner */}
                {impactResult && (
                  <div
                    style={{
                      background: "var(--surface-1)",
                      border: "1px solid var(--border)",
                      borderRadius: "6px",
                      padding: "var(--space-4)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "var(--space-3)" }}>
                      <div>
                        <h3 style={{ margin: 0, fontSize: "0.875rem", fontWeight: 700 }}>
                          Downstream Decision Impact & Stale Input Analysis
                        </h3>
                        <p style={{ margin: "2px 0 0 0", fontSize: "0.6875rem", color: "var(--muted)" }}>
                          When a dataset changes (V1 to V2), historical decision packages are never mutated; dependent runs are flagged for operational review.
                        </p>
                      </div>
                      {getImpactBadge(impactResult.impact_level || "LOW")}
                    </div>

                    <div
                      style={{
                        padding: "var(--space-3)",
                        background: "var(--surface-2)",
                        borderRadius: "4px",
                        fontSize: "0.75rem",
                        marginBottom: "var(--space-3)",
                      }}
                    >
                      <strong>Rationale:</strong> {impactResult.rationale}
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)", marginBottom: "var(--space-3)" }}>
                      <div style={{ padding: "var(--space-2) var(--space-3)", background: "var(--surface-2)", borderRadius: "4px" }}>
                        <div style={{ fontSize: "0.6875rem", color: "var(--muted)", fontWeight: 600 }}>AFFECTED ENGINES</div>
                        <div style={{ marginTop: "4px", fontSize: "0.75rem" }}>
                          {(impactResult.affected_engines || []).map((eng, idx) => (
                            <div key={idx} style={{ padding: "2px 0" }}>• {eng}</div>
                          ))}
                        </div>
                      </div>

                      <div style={{ padding: "var(--space-2) var(--space-3)", background: "var(--surface-2)", borderRadius: "4px" }}>
                        <div style={{ fontSize: "0.6875rem", color: "var(--muted)", fontWeight: 600 }}>RECALCULATION STATUS</div>
                        <div style={{ marginTop: "4px", fontSize: "0.75rem", color: impactResult.requires_recalculation ? "#f59e0b" : "#10b981", fontWeight: 700 }}>
                          {impactResult.requires_recalculation ? "REQUIRES DOWNSTREAM RECOMPUTATION" : "NO RECOMPUTATION REQUIRED"}
                        </div>
                      </div>
                    </div>

                    <div style={{ fontSize: "0.6875rem", fontWeight: 700, color: "var(--muted)", marginBottom: "6px" }}>
                      STALE DECISION PACKAGES FLAGGED ({(impactResult.stale_decision_packages || []).length})
                    </div>

                    {(impactResult.stale_decision_packages || []).length > 0 ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                        {impactResult.stale_decision_packages.map((pkgId, idx) => (
                          <div
                            key={idx}
                            style={{
                              padding: "var(--space-2) var(--space-3)",
                              background: "var(--surface-2)",
                              border: "1px solid var(--border)",
                              borderRadius: "4px",
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                            }}
                          >
                            <div>
                              <span style={{ fontWeight: 700 }}>{pkgId}</span>
                              <div style={{ fontSize: "0.6875rem", color: "var(--muted)", marginTop: "2px" }}>
                                Inputs superseded by dataset update. Historical decision remains immutable per institutional governance.
                              </div>
                            </div>
                            <span
                              style={{
                                padding: "2px 6px",
                                background: "rgba(245, 158, 11, 0.15)",
                                border: "1px solid #f59e0b",
                                color: "#f59e0b",
                                borderRadius: "3px",
                                fontSize: "0.6875rem",
                                fontWeight: 700,
                              }}
                            >
                              STALE_INPUT / REVIEW REQUIRED
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={{ color: "var(--muted)", fontSize: "0.75rem" }}>
                        No active Phase 11 decision packages depend on this dataset version.
                      </div>
                    )}
                  </div>
                )}

                {/* Granular Diff Viewer */}
                {diffResult && (
                  <div
                    style={{
                      background: "var(--surface-1)",
                      border: "1px solid var(--border)",
                      borderRadius: "6px",
                      padding: "var(--space-4)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
                      <div>
                        <h3 style={{ margin: 0, fontSize: "0.875rem", fontWeight: 700 }}>
                          Dataset Version Diff: v{diffResult.base_version} &rarr; v{diffResult.target_version}
                        </h3>
                        <p style={{ margin: "2px 0 0 0", fontSize: "0.6875rem", color: "var(--muted)" }}>
                          Total changes: {diffResult.total_changes}
                        </p>
                      </div>
                    </div>

                    {(diffResult.changes || []).length > 0 ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                        {diffResult.changes.map((rd, i) => (
                          <div
                            key={i}
                            style={{
                              padding: "var(--space-2) var(--space-3)",
                              background: "var(--surface-2)",
                              border: "1px solid var(--border)",
                              borderRadius: "4px",
                            }}
                          >
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                              <span style={{ fontWeight: 700, fontSize: "0.75rem" }}>
                                {rd.record_identifier}
                              </span>
                              <span
                                style={{
                                  padding: "1px 6px",
                                  borderRadius: "3px",
                                  fontSize: "0.6875rem",
                                  fontWeight: 700,
                                  background:
                                    rd.change_type === "ADDED"
                                      ? "rgba(16, 185, 129, 0.15)"
                                      : rd.change_type === "MODIFIED"
                                      ? "rgba(59, 130, 246, 0.15)"
                                      : rd.change_type === "REMOVED"
                                      ? "rgba(239, 68, 68, 0.15)"
                                      : "rgba(100, 116, 139, 0.15)",
                                  color:
                                    rd.change_type === "ADDED" ? "#10b981" : rd.change_type === "MODIFIED" ? "#3b82f6" : rd.change_type === "REMOVED" ? "#ef4444" : "#94a3b8",
                                }}
                              >
                                {rd.change_type}
                              </span>
                            </div>

                            {rd.field_diffs && Object.entries(rd.field_diffs).map(([fName, diffVals]) => (
                              <div key={fName} style={{ fontSize: "0.6875rem", color: "var(--muted)", marginLeft: "8px" }}>
                                <strong style={{ color: "var(--text)" }}>{fName}:</strong>{" "}
                                <span style={{ textDecoration: "line-through", color: "#ef4444" }}>{String(diffVals.old ?? "null")}</span>{" "}
                                &rarr; <span style={{ color: "#10b981", fontWeight: 700 }}>{String(diffVals.new ?? "null")}</span>
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={{ textAlign: "center", padding: "var(--space-4)", color: "var(--muted)" }}>
                        Zero changes between versions.
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* 6. INSTITUTIONAL SIGN-OFF & APPROVAL TAB */}
            {activeTab === "approval" && (
              <div style={{ maxWidth: "800px" }}>
                <div
                  style={{
                    background: "var(--surface-1)",
                    border: "1px solid var(--border)",
                    borderRadius: "6px",
                    padding: "var(--space-4)",
                  }}
                >
                  <h3 style={{ margin: "0 0 var(--space-2) 0", fontSize: "0.875rem", fontWeight: 700 }}>
                    Institutional Dataset Approval Workflow
                  </h3>
                  <p style={{ margin: "0 0 var(--space-4) 0", fontSize: "0.75rem", color: "var(--muted)" }}>
                    Separation of duties requires that only institutional approvers or data stewards approve datasets. Datasets in INVALID or QUARANTINED status cannot be approved until defects are resolved.
                  </p>

                  {currentDataset ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                      <div style={{ padding: "var(--space-3)", background: "var(--surface-2)", borderRadius: "4px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                          <span>Target Dataset: <strong>{currentDataset.name}</strong></span>
                          {getStatusBadge(currentDataset.status)}
                        </div>
                        <div style={{ fontSize: "0.6875rem", color: "var(--muted)" }}>
                          Current Quality Score: <strong>{currentDataset.quality_score.toFixed(1)}%</strong> • Version {currentDataset.current_version}
                        </div>
                      </div>

                      <div>
                        <label style={{ display: "block", fontSize: "0.6875rem", color: "var(--muted)", marginBottom: "4px" }}>
                          AUDIT APPROVAL NOTES
                        </label>
                        <textarea
                          rows={3}
                          value={approvalNotes}
                          onChange={(e) => setApprovalNotes(e.target.value)}
                          style={{
                            width: "100%",
                            padding: "8px 10px",
                            background: "var(--surface-2)",
                            border: "1px solid var(--border)",
                            color: "var(--text)",
                            borderRadius: "4px",
                            fontSize: "0.75rem",
                          }}
                        />
                      </div>

                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "var(--space-2)" }}>
                        <div style={{ display: "flex", gap: "var(--space-2)" }}>
                          <input
                            type="text"
                            placeholder="Rejection reason..."
                            value={rejectReason}
                            onChange={(e) => setRejectReason(e.target.value)}
                            style={{
                              padding: "6px 10px",
                              background: "var(--surface-2)",
                              border: "1px solid var(--border)",
                              color: "var(--text)",
                              borderRadius: "4px",
                              fontSize: "0.75rem",
                              width: "220px",
                            }}
                          />
                          <button
                            type="button"
                            onClick={handleReject}
                            disabled={actionLoading}
                            style={{
                              padding: "6px 12px",
                              background: "rgba(239, 68, 68, 0.2)",
                              border: "1px solid rgba(239, 68, 68, 0.4)",
                              borderRadius: "4px",
                              color: "#ef4444",
                              fontWeight: 700,
                              cursor: actionLoading ? "not-allowed" : "pointer",
                              fontSize: "0.75rem",
                            }}
                          >
                            Reject Dataset
                          </button>
                        </div>

                        <button
                          type="button"
                          onClick={handleApprove}
                          disabled={actionLoading || currentDataset.status === "APPROVED"}
                          style={{
                            padding: "8px 18px",
                            background: currentDataset.status === "APPROVED" ? "var(--surface-3)" : "#10b981",
                            border: "none",
                            borderRadius: "4px",
                            color: "#fff",
                            fontWeight: 700,
                            cursor: actionLoading || currentDataset.status === "APPROVED" ? "not-allowed" : "pointer",
                            fontSize: "0.75rem",
                          }}
                        >
                          {actionLoading
                            ? "Signing..."
                            : currentDataset.status === "APPROVED"
                            ? "Dataset Already Approved"
                            : "Formal Institutional Sign-Off (APPROVE)"}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div style={{ color: "var(--muted)", textAlign: "center", padding: "var(--space-6)" }}>
                      Select a dataset from the registry first.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
