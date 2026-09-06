"use client";

import React, { useState, useEffect } from "react";
import {
  getGovernanceDemoPackage,
  listGovernancePackages,
  getGovernancePackage,
  validateGovernancePackage,
  submitGovernancePackage,
  reviewGovernancePackage,
  approveGovernancePackage,
  rejectGovernancePackage,
  recordGovernanceOverride,
  createGovernancePackageVersion,
  verifyGovernanceAuditTrail,
  reproduceGovernanceDecision,
  compareGovernancePackages,
  exportGovernanceDecisionRecord,
  getGovernanceActiveConfiguration,
} from "@/lib/api";
import type {
  DecisionPackageResponse,
  DecisionPackageSummary,
  PackageValidationResponse,
  PackageComparisonResponse,
  AuditChainVerificationResponse,
  ReproductionResponse,
  DecisionRecordExportResponse,
  DecisionConfigurationResponse,
  GovernancePackageStatus,
  InstitutionalRole,
} from "@/types/api";

type ActiveTab = "overview" | "workflow" | "audit" | "versioning" | "override" | "policy";
type DemoScenario = "BASELINE" | "STRATEGY_FLIP_A" | "STRATEGY_FLIP_B" | "STRESS_TEST";

export default function GovernancePage() {
  const [loading, setLoading] = useState<boolean>(false);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>("overview");
  const [selectedScenario, setSelectedScenario] = useState<DemoScenario>("BASELINE");

  // User persona for separation of duties testing
  const [currentUser, setCurrentUser] = useState<{ id: string; role: InstitutionalRole }>({
    id: "capt_vance_approver",
    role: "APPROVER",
  });

  // Main state
  const [currentPackage, setCurrentPackage] = useState<DecisionPackageResponse | null>(null);
  const [packageList, setPackageList] = useState<DecisionPackageSummary[]>([]);
  const [validationResult, setValidationResult] = useState<PackageValidationResponse | null>(null);
  const [auditVerification, setAuditVerification] = useState<AuditChainVerificationResponse | null>(null);
  const [reproResult, setReproResult] = useState<ReproductionResponse | null>(null);
  const [comparisonResult, setComparisonResult] = useState<PackageComparisonResponse | null>(null);
  const [exportRecord, setExportRecord] = useState<DecisionRecordExportResponse | null>(null);
  const [policyConfig, setPolicyConfig] = useState<DecisionConfigurationResponse | null>(null);

  // Form inputs
  const [approvalNotes, setApprovalNotes] = useState<string>("");
  const [rejectReason, setRejectReason] = useState<string>("");
  const [overrideDecision, setOverrideDecision] = useState<string>("PROCEED");
  const [overrideReason, setOverrideReason] = useState<string>("");
  const [overrideAck, setOverrideAck] = useState<boolean>(true);
  const [versionSummary, setVersionSummary] = useState<string>("");
  const [copiedHash, setCopiedHash] = useState<boolean>(false);

  useEffect(() => {
    initDashboard();
  }, []);

  async function initDashboard() {
    setLoading(true);
    setError(null);
    try {
      const [demoPkg, pkgs, config] = await Promise.all([
        getGovernanceDemoPackage("BASELINE"),
        listGovernancePackages(20).catch(() => []),
        getGovernanceActiveConfiguration().catch(() => null),
      ]);

      setCurrentPackage(demoPkg);
      setPackageList(pkgs);
      if (config) setPolicyConfig(config);

      // Verify audit chain on load
      if (demoPkg.package_id) {
        verifyGovernanceAuditTrail(demoPkg.package_id)
          .then(setAuditVerification)
          .catch(() => null);
      }
    } catch (err: any) {
      console.error("Failed to initialize governance console:", err);
      setError(err.message || "Failed to initialize governance layer.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSelectScenario(scenario: DemoScenario) {
    setSelectedScenario(scenario);
    setLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const pkg = await getGovernanceDemoPackage(scenario);
      setCurrentPackage(pkg);
      const auditRes = await verifyGovernanceAuditTrail(pkg.package_id).catch(() => null);
      if (auditRes) setAuditVerification(auditRes);
      setValidationResult(null);
      setReproResult(null);
      setComparisonResult(null);
      setExportRecord(null);
    } catch (err: any) {
      console.error(`Failed to switch scenario:`, err);
      setError(err.message || "Failed to load demo scenario.");
    } finally {
      setLoading(false);
    }
  }

  async function handleValidate() {
    if (!currentPackage) return;
    setActionLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await validateGovernancePackage(currentPackage.package_id);
      setValidationResult(res);
      setSuccessMsg("Evidence validation completed: All institutional prerequisites satisfied.");
      // Refresh package
      const updated = await getGovernancePackage(currentPackage.package_id);
      setCurrentPackage(updated);
    } catch (err: any) {
      setError(err.message || "Validation failed.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleSubmitForReview() {
    if (!currentPackage) return;
    setActionLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const updated = await submitGovernancePackage(currentPackage.package_id, {
        actor: currentUser.id,
        actor_role: currentUser.role,
        notes: "Submitted for formal committee sign-off.",
      });
      setCurrentPackage(updated);
      setSuccessMsg(`Package ${updated.package_id} submitted for institutional review.`);
      const auditRes = await verifyGovernanceAuditTrail(updated.package_id);
      setAuditVerification(auditRes);
    } catch (err: any) {
      setError(err.message || "Submission failed.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleApprove() {
    if (!currentPackage) return;
    setActionLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const updated = await approveGovernancePackage(currentPackage.package_id, {
        actor: currentUser.id,
        actor_role: currentUser.role,
        notes: approvalNotes || "Formally approved by Institutional Chartering Committee.",
      });
      setCurrentPackage(updated);
      setSuccessMsg(`Package ${updated.package_id} formally APPROVED under institutional sign-off.`);
      setApprovalNotes("");
      const auditRes = await verifyGovernanceAuditTrail(updated.package_id);
      setAuditVerification(auditRes);
    } catch (err: any) {
      setError(err.message || "Approval failed.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReject() {
    if (!currentPackage) return;
    if (!rejectReason || rejectReason.trim().length < 5) {
      setError("Rejection requires a formal reason (min 5 characters).");
      return;
    }
    setActionLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const updated = await rejectGovernancePackage(currentPackage.package_id, {
        actor: currentUser.id,
        actor_role: currentUser.role,
        reason: rejectReason,
      });
      setCurrentPackage(updated);
      setSuccessMsg(`Package ${updated.package_id} REJECTED with recorded justification.`);
      setRejectReason("");
      const auditRes = await verifyGovernanceAuditTrail(updated.package_id);
      setAuditVerification(auditRes);
    } catch (err: any) {
      setError(err.message || "Rejection failed.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleOverride() {
    if (!currentPackage) return;
    if (!overrideReason || overrideReason.trim().length < 5) {
      setError("Human override requires formal operational justification.");
      return;
    }
    setActionLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const updated = await recordGovernanceOverride(currentPackage.package_id, {
        override_recommendation: overrideDecision,
        reason: overrideReason,
        actor: currentUser.id,
        actor_role: currentUser.role,
        supporting_note: `Risk acknowledgement verified: ${overrideAck ? "YES" : "NO"}`,
        approval_actor: currentUser.id,
      });
      setCurrentPackage(updated);
      setSuccessMsg(`Human operational override recorded: ${updated.recommendation_type} -> ${overrideDecision}`);
      setOverrideReason("");
      const auditRes = await verifyGovernanceAuditTrail(updated.package_id);
      setAuditVerification(auditRes);
    } catch (err: any) {
      setError(err.message || "Override failed.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleCreateVersion() {
    if (!currentPackage) return;
    setActionLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const updated = await createGovernancePackageVersion(currentPackage.package_id, {
        updated_evidence: {
          expected_contribution: currentPackage.expected_contribution * 1.05,
          decision_score: Math.min(100, currentPackage.decision_score + 2.5),
        },
        change_summary: versionSummary || "Revised bunker pricing curves and laycan adjustment.",
        actor: currentUser.id,
      });
      setCurrentPackage(updated);
      setSuccessMsg(`Incremented version to V${updated.version_number}.0 (Hash chained).`);
      setVersionSummary("");
      const auditRes = await verifyGovernanceAuditTrail(updated.package_id);
      setAuditVerification(auditRes);
    } catch (err: any) {
      setError(err.message || "Version creation failed.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleVerifyAudit() {
    if (!currentPackage) return;
    setActionLoading(true);
    try {
      const res = await verifyGovernanceAuditTrail(currentPackage.package_id);
      setAuditVerification(res);
      setSuccessMsg(`Audit Trail Verified: ${res.verified_count}/${res.event_count} events valid. Status: ${res.status}`);
    } catch (err: any) {
      setError(err.message || "Audit verification failed.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReproduce() {
    if (!currentPackage) return;
    setActionLoading(true);
    try {
      const res = await reproduceGovernanceDecision(currentPackage.package_id);
      setReproResult(res);
      if (res.is_reproducible) {
        setSuccessMsg("Decision Reproducibility Verified: Output matches stored upstream model run bit-for-bit.");
      } else {
        setError("Reproduction Mismatch Detected: Outputs diverge from recorded package snapshot.");
      }
    } catch (err: any) {
      setError(err.message || "Reproduction execution failed.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleExport() {
    if (!currentPackage) return;
    setActionLoading(true);
    try {
      const res = await exportGovernanceDecisionRecord(currentPackage.package_id);
      setExportRecord(res);
      setSuccessMsg("Export package generated. Ready for institutional download or committee filing.");
    } catch (err: any) {
      setError(err.message || "Export generation failed.");
    } finally {
      setActionLoading(false);
    }
  }

  function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  }

  // Formatters
  const formatUSD = (val?: number | null) =>
    val != null ? `$${Math.round(val).toLocaleString("en-US")}` : "—";
  const formatPct = (val?: number | null) =>
    val != null ? `${(val * 100).toFixed(1)}%` : "—";

  const getStatusColor = (status: GovernancePackageStatus | string) => {
    switch (status) {
      case "APPROVED":
        return { bg: "rgba(16, 185, 129, 0.15)", text: "#34d399", border: "#10b981" };
      case "UNDER_REVIEW":
        return { bg: "rgba(245, 158, 11, 0.15)", text: "#fbbf24", border: "#f59e0b" };
      case "SUBMITTED":
        return { bg: "rgba(59, 130, 246, 0.15)", text: "#60a5fa", border: "#3b82f6" };
      case "VALIDATED":
        return { bg: "rgba(139, 92, 246, 0.15)", text: "#a78bfa", border: "#8b5cf6" };
      case "REJECTED":
        return { bg: "rgba(239, 68, 68, 0.15)", text: "#f87171", border: "#ef4444" };
      default:
        return { bg: "rgba(148, 163, 184, 0.15)", text: "#cbd5e1", border: "#64748b" };
    }
  };

  return (
    <div style={{ padding: "var(--space-4)", maxWidth: "1600px", margin: "0 auto" }}>
      {/* ── HEADER ──────────────────────────────────────────────────────── */}
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "var(--space-4)",
          paddingBottom: "var(--space-3)",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <h1 style={{ fontSize: "1.375rem", fontWeight: 700, letterSpacing: "-0.01em", margin: 0 }}>
              Decision Governance & Institutional Control
            </h1>
            <span
              style={{
                fontSize: "0.6875rem",
                fontWeight: 700,
                textTransform: "uppercase",
                background: "rgba(14, 165, 233, 0.15)",
                color: "#38bdf8",
                border: "1px solid #0284c7",
                padding: "2px 8px",
                borderRadius: "4px",
                fontFamily: "monospace",
              }}
            >
              PHASE 11 • SHA-256 AUDIT
            </span>
          </div>
          <p style={{ fontSize: "0.8125rem", color: "var(--muted)", margin: "4px 0 0 0" }}>
            Immutable Decision Packages • Cryptographic Hash Chains • Separation of Duties • Policy Hurdle Verification
          </p>
        </div>

        {/* User Role Switcher for Separation of Duties Testing */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-3)",
            background: "var(--surface-1)",
            padding: "var(--space-2) var(--space-3)",
            borderRadius: "6px",
            border: "1px solid var(--border)",
          }}
        >
          <div style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
            Active Persona:
          </div>
          <select
            value={currentUser.role}
            onChange={(e) => {
              const r = e.target.value as InstitutionalRole;
              setCurrentUser({
                role: r,
                id: r === "ANALYST" ? "analyst_alice" : r === "APPROVER" ? "director_bob" : "admin_carol",
              });
            }}
            style={{
              background: "var(--surface-2)",
              color: "var(--text)",
              border: "1px solid var(--border)",
              borderRadius: "4px",
              padding: "4px 8px",
              fontSize: "0.75rem",
              fontWeight: 600,
            }}
          >
            <option value="ANALYST">Analyst (analyst_alice)</option>
            <option value="REVIEWER">Reviewer (reviewer_dan)</option>
            <option value="APPROVER">Approver (director_bob)</option>
            <option value="ADMIN">Admin (admin_carol)</option>
            <option value="AUDITOR">Auditor (auditor_eve)</option>
          </select>
          <span
            style={{
              fontSize: "0.6875rem",
              fontFamily: "monospace",
              color: "var(--muted)",
              background: "var(--surface-2)",
              padding: "2px 6px",
              borderRadius: "3px",
            }}
          >
            ID: {currentUser.id}
          </span>
        </div>
      </header>

      {/* ── SCENARIO PRESETS BAR ────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-2)",
          marginBottom: "var(--space-4)",
          background: "var(--surface-1)",
          padding: "var(--space-2) var(--space-3)",
          borderRadius: "6px",
          border: "1px solid var(--border)",
        }}
      >
        <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--muted)", textTransform: "uppercase" }}>
          Decision Package Presets:
        </span>
        {(
          [
            { key: "BASELINE", label: "Baseline Fleet Plan (Approved)" },
            { key: "STRATEGY_FLIP_A", label: "Plan A: Nominal Maximizer (High Risk)" },
            { key: "STRATEGY_FLIP_B", label: "Plan B: Robust Buffer Deployment" },
            { key: "STRESS_TEST", label: "Bunker Price Shock Stress Test" },
          ] as const
        ).map((scen) => (
          <button
            key={scen.key}
            onClick={() => handleSelectScenario(scen.key)}
            style={{
              background: selectedScenario === scen.key ? "var(--accent)" : "var(--surface-2)",
              color: selectedScenario === scen.key ? "#fff" : "var(--text)",
              border: "1px solid",
              borderColor: selectedScenario === scen.key ? "var(--accent)" : "var(--border)",
              padding: "4px 10px",
              borderRadius: "4px",
              fontSize: "0.75rem",
              fontWeight: 600,
              cursor: "pointer",
              transition: "all 120ms ease",
            }}
          >
            {scen.label}
          </button>
        ))}
      </div>

      {/* ── NOTIFICATION BANNERS ────────────────────────────────────────── */}
      {error && (
        <div
          style={{
            padding: "var(--space-3)",
            marginBottom: "var(--space-3)",
            background: "rgba(239, 68, 68, 0.1)",
            border: "1px solid #ef4444",
            borderRadius: "6px",
            color: "#f87171",
            fontSize: "0.8125rem",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>⚠️ {error}</div>
          <button
            onClick={() => setError(null)}
            style={{ background: "transparent", border: "none", color: "#f87171", cursor: "pointer" }}
          >
            ✕
          </button>
        </div>
      )}

      {successMsg && (
        <div
          style={{
            padding: "var(--space-3)",
            marginBottom: "var(--space-3)",
            background: "rgba(16, 185, 129, 0.1)",
            border: "1px solid #10b981",
            borderRadius: "6px",
            color: "#34d399",
            fontSize: "0.8125rem",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>✓ {successMsg}</div>
          <button
            onClick={() => setSuccessMsg(null)}
            style={{ background: "transparent", border: "none", color: "#34d399", cursor: "pointer" }}
          >
            ✕
          </button>
        </div>
      )}

      {/* ── KEY METRIC RIBBON / KPI CARDS ────────────────────────────────── */}
      {currentPackage && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "var(--space-3)",
            marginBottom: "var(--space-4)",
          }}
        >
          {/* Card 1: Package Status */}
          <div
            style={{
              background: "var(--surface-1)",
              border: "1px solid var(--border)",
              borderRadius: "6px",
              padding: "var(--space-3)",
            }}
          >
            <div style={{ fontSize: "0.6875rem", color: "var(--muted)", textTransform: "uppercase" }}>
              Package Lifecycle Status
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "6px" }}>
              <span
                style={{
                  padding: "3px 10px",
                  borderRadius: "4px",
                  fontSize: "0.875rem",
                  fontWeight: 700,
                  fontFamily: "monospace",
                  background: getStatusColor(currentPackage.status).bg,
                  color: getStatusColor(currentPackage.status).text,
                  border: `1px solid ${getStatusColor(currentPackage.status).border}`,
                }}
              >
                {currentPackage.status}
              </span>
              <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
                V{currentPackage.version_number}.0
              </span>
            </div>
            <div style={{ fontSize: "0.6875rem", color: "var(--muted)", marginTop: "4px" }}>
              Created by: {currentPackage.created_by || "analyst"} ({currentPackage.created_by_role})
            </div>
          </div>

          {/* Card 2: Cryptographic Hash */}
          <div
            style={{
              background: "var(--surface-1)",
              border: "1px solid var(--border)",
              borderRadius: "6px",
              padding: "var(--space-3)",
            }}
          >
            <div style={{ fontSize: "0.6875rem", color: "var(--muted)", textTransform: "uppercase" }}>
              Package SHA-256 Digest
            </div>
            <div
              onClick={() => copyToClipboard(currentPackage.package_hash)}
              title="Click to copy full hash"
              style={{
                marginTop: "6px",
                fontFamily: "monospace",
                fontSize: "0.75rem",
                color: "#38bdf8",
                background: "var(--surface-2)",
                padding: "4px 8px",
                borderRadius: "4px",
                border: "1px solid var(--border)",
                cursor: "pointer",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {currentPackage.package_hash ? currentPackage.package_hash.substring(0, 18) + "..." : "PENDING"}
              <span style={{ float: "right", color: "var(--muted)", fontSize: "0.625rem" }}>
                {copiedHash ? "COPIED!" : "COPY"}
              </span>
            </div>
            <div style={{ fontSize: "0.6875rem", color: "var(--muted)", marginTop: "4px" }}>
              Canonical JSON • Order Invariant
            </div>
          </div>

          {/* Card 3: Audit Chain Integrity */}
          <div
            style={{
              background: "var(--surface-1)",
              border: "1px solid var(--border)",
              borderRadius: "6px",
              padding: "var(--space-3)",
            }}
          >
            <div style={{ fontSize: "0.6875rem", color: "var(--muted)", textTransform: "uppercase" }}>
              Audit Chain Continuity
            </div>
            <div style={{ marginTop: "6px", display: "flex", alignItems: "center", gap: "6px" }}>
              <span
                style={{
                  display: "inline-block",
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  background: auditVerification?.is_valid ? "#10b981" : "#ef4444",
                }}
              />
              <span style={{ fontSize: "0.875rem", fontWeight: 700, fontFamily: "monospace" }}>
                {auditVerification?.is_valid ? "CHAIN INTACT" : "UNVERIFIED / COMPROMISED"}
              </span>
            </div>
            <div style={{ fontSize: "0.6875rem", color: "var(--muted)", marginTop: "4px" }}>
              {auditVerification?.verified_count ?? 0} events verified from GENESIS
            </div>
          </div>

          {/* Card 4: Economics */}
          <div
            style={{
              background: "var(--surface-1)",
              border: "1px solid var(--border)",
              borderRadius: "6px",
              padding: "var(--space-3)",
            }}
          >
            <div style={{ fontSize: "0.6875rem", color: "var(--muted)", textTransform: "uppercase" }}>
              Economic Hurdle / Yield
            </div>
            <div style={{ marginTop: "6px", fontSize: "1.125rem", fontWeight: 700, color: "var(--text)" }}>
              {formatUSD(currentPackage.expected_contribution)}
            </div>
            <div style={{ fontSize: "0.6875rem", color: "var(--muted)", marginTop: "2px" }}>
              Risk-Adjusted: {formatUSD(currentPackage.risk_adjusted_contribution)}
            </div>
          </div>

          {/* Card 5: Recommendation Verdict */}
          <div
            style={{
              background: "var(--surface-1)",
              border: "1px solid var(--border)",
              borderRadius: "6px",
              padding: "var(--space-3)",
            }}
          >
            <div style={{ fontSize: "0.6875rem", color: "var(--muted)", textTransform: "uppercase" }}>
              Model Verdict vs Human Sign-Off
            </div>
            <div style={{ marginTop: "6px", display: "flex", alignItems: "center", gap: "6px" }}>
              <span
                style={{
                  fontSize: "0.75rem",
                  fontWeight: 700,
                  padding: "2px 6px",
                  borderRadius: "3px",
                  background: "rgba(59, 130, 246, 0.15)",
                  color: "#60a5fa",
                }}
              >
                REC: {currentPackage.recommendation_type}
              </span>
              {currentPackage.is_override && (
                <span
                  style={{
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    padding: "2px 6px",
                    borderRadius: "3px",
                    background: "rgba(245, 158, 11, 0.2)",
                    color: "#fbbf24",
                  }}
                >
                  OVERRIDE: {currentPackage.override_recommendation || "PROCEED"}
                </span>
              )}
            </div>
            <div style={{ fontSize: "0.6875rem", color: "var(--muted)", marginTop: "4px" }}>
              Score: {currentPackage.decision_score.toFixed(1)} / 100 ({currentPackage.confidence})
            </div>
          </div>
        </div>
      )}

      {/* ── NAVIGATION TABS ─────────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          gap: "var(--space-2)",
          borderBottom: "1px solid var(--border)",
          marginBottom: "var(--space-4)",
        }}
      >
        {(
          [
            { id: "overview", label: "Package Registry & Evidence" },
            { id: "workflow", label: "Approval & Separation of Duties" },
            { id: "audit", label: "SHA-256 Audit Trail" },
            { id: "versioning", label: "Version Delta & Reproducibility" },
            { id: "override", label: "Human Override Governance" },
            { id: "policy", label: "Institutional Policies & Export" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              background: "transparent",
              border: "none",
              borderBottom: activeTab === tab.id ? "2px solid var(--info)" : "2px solid transparent",
              color: activeTab === tab.id ? "var(--text)" : "var(--muted)",
              padding: "var(--space-2) var(--space-3)",
              fontSize: "0.8125rem",
              fontWeight: 600,
              cursor: "pointer",
              transition: "all 120ms ease",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── TAB 1: PACKAGE REGISTRY & EVIDENCE ──────────────────────────── */}
      {activeTab === "overview" && currentPackage && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: "var(--space-4)" }}>
          <div>
            {/* Package Summary Card */}
            <div
              style={{
                background: "var(--surface-1)",
                border: "1px solid var(--border)",
                borderRadius: "6px",
                padding: "var(--space-4)",
                marginBottom: "var(--space-4)",
              }}
            >
              <h2 style={{ fontSize: "1.125rem", fontWeight: 700, margin: "0 0 8px 0" }}>
                {currentPackage.title}
              </h2>
              <p style={{ fontSize: "0.8125rem", color: "var(--muted)", margin: "0 0 var(--space-4) 0", lineHeight: 1.5 }}>
                {currentPackage.description}
              </p>

              {/* Upstream Lineage Chain */}
              <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", marginBottom: "8px" }}>
                Upstream Analytical Lineage
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(4, 1fr)",
                  gap: "var(--space-2)",
                  background: "var(--surface-2)",
                  padding: "var(--space-3)",
                  borderRadius: "6px",
                  border: "1px solid var(--border)",
                }}
              >
                <div>
                  <div style={{ fontSize: "0.625rem", color: "var(--muted)", textTransform: "uppercase" }}>Phase 7 MILP</div>
                  <div style={{ fontSize: "0.75rem", fontFamily: "monospace", color: "#60a5fa" }}>
                    {currentPackage.optimization_run_id}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "0.625rem", color: "var(--muted)", textTransform: "uppercase" }}>Phase 8 Scenarios</div>
                  <div style={{ fontSize: "0.75rem", fontFamily: "monospace", color: "#a78bfa" }}>
                    {currentPackage.scenario_run_id || "BASELINE_DEF"}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "0.625rem", color: "var(--muted)", textTransform: "uppercase" }}>Phase 9 Risk</div>
                  <div style={{ fontSize: "0.75rem", fontFamily: "monospace", color: "#f59e0b" }}>
                    {currentPackage.risk_run_id || "RISK_MC_1000"}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "0.625rem", color: "var(--muted)", textTransform: "uppercase" }}>Phase 10 Decision</div>
                  <div style={{ fontSize: "0.75rem", fontFamily: "monospace", color: "#34d399" }}>
                    {currentPackage.decision_run_id}
                  </div>
                </div>
              </div>
            </div>

            {/* Evidence Checklist */}
            <div
              style={{
                background: "var(--surface-1)",
                border: "1px solid var(--border)",
                borderRadius: "6px",
                padding: "var(--space-4)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
                <h3 style={{ fontSize: "0.875rem", fontWeight: 700, margin: 0, textTransform: "uppercase" }}>
                  Institutional Evidence Checklist
                </h3>
                <button
                  onClick={handleValidate}
                  disabled={actionLoading}
                  style={{
                    background: "var(--accent)",
                    color: "#fff",
                    border: "none",
                    borderRadius: "4px",
                    padding: "4px 12px",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    cursor: actionLoading ? "not-allowed" : "pointer",
                  }}
                >
                  {actionLoading ? "Validating..." : "Validate Evidence Prerequisites"}
                </button>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {[
                  {
                    title: "Phase 7 MILP Optimization Run Linkage",
                    ok: !!currentPackage.optimization_run_id,
                    detail: `Linked to run ID ${currentPackage.optimization_run_id}`,
                  },
                  {
                    title: "Phase 10 Deterministic Decision Evaluation",
                    ok: !!currentPackage.decision_run_id,
                    detail: `Decision score ${currentPackage.decision_score.toFixed(1)} pts (${currentPackage.confidence})`,
                  },
                  {
                    title: "Phase 9 Stochastic Risk Intelligence Verification",
                    ok: currentPackage.loss_probability != null && currentPackage.cvar_95 != null,
                    detail: `Loss Prob: ${formatPct(currentPackage.loss_probability)} • 95% CVaR: ${formatUSD(currentPackage.cvar_95)}`,
                  },
                  {
                    title: "Policy Configuration Versioning",
                    ok: !!currentPackage.configuration_version,
                    detail: `Policy Version ${currentPackage.configuration_version} (${currentPackage.configuration_id || "STANDARD"})`,
                  },
                  {
                    title: "Cryptographic Input & Output Digest Hashes",
                    ok: !!currentPackage.input_hash && !!currentPackage.output_hash,
                    detail: `In: ${currentPackage.input_hash.substring(0, 12)}... • Out: ${currentPackage.output_hash.substring(0, 12)}...`,
                  },
                ].map((item, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "8px 12px",
                      background: "var(--surface-2)",
                      borderRadius: "4px",
                      border: "1px solid var(--border)",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      <span style={{ color: item.ok ? "#10b981" : "#ef4444", fontSize: "1rem" }}>
                        {item.ok ? "✓" : "✗"}
                      </span>
                      <div>
                        <div style={{ fontSize: "0.75rem", fontWeight: 600 }}>{item.title}</div>
                        <div style={{ fontSize: "0.6875rem", color: "var(--muted)" }}>{item.detail}</div>
                      </div>
                    </div>
                    <span
                      style={{
                        fontSize: "0.625rem",
                        fontFamily: "monospace",
                        color: item.ok ? "#34d399" : "#f87171",
                        background: item.ok ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)",
                        padding: "2px 6px",
                        borderRadius: "3px",
                      }}
                    >
                      {item.ok ? "VERIFIED" : "MISSING"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right Sidebar: Quick Actions & Package Meta */}
          <div>
            <div
              style={{
                background: "var(--surface-1)",
                border: "1px solid var(--border)",
                borderRadius: "6px",
                padding: "var(--space-3)",
                marginBottom: "var(--space-3)",
              }}
            >
              <div style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", marginBottom: "8px" }}>
                Package Actions
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {currentPackage.status === "DRAFT" && (
                  <button
                    onClick={handleValidate}
                    style={{
                      background: "var(--accent)",
                      color: "#fff",
                      border: "none",
                      borderRadius: "4px",
                      padding: "8px",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    1. Validate Evidence
                  </button>
                )}
                {currentPackage.status === "VALIDATED" && (
                  <button
                    onClick={handleSubmitForReview}
                    style={{
                      background: "#3b82f6",
                      color: "#fff",
                      border: "none",
                      borderRadius: "4px",
                      padding: "8px",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    2. Submit for Review
                  </button>
                )}
                {(currentPackage.status === "SUBMITTED" || currentPackage.status === "UNDER_REVIEW") && (
                  <>
                    <button
                      onClick={handleApprove}
                      style={{
                        background: "#10b981",
                        color: "#fff",
                        border: "none",
                        borderRadius: "4px",
                        padding: "8px",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      3. Formally Approve Package
                    </button>
                    <button
                      onClick={() => setActiveTab("workflow")}
                      style={{
                        background: "var(--surface-2)",
                        color: "#f87171",
                        border: "1px solid #ef4444",
                        borderRadius: "4px",
                        padding: "8px",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      Reject with Reason...
                    </button>
                  </>
                )}
                <button
                  onClick={handleVerifyAudit}
                  style={{
                    background: "var(--surface-2)",
                    color: "var(--text)",
                    border: "1px solid var(--border)",
                    borderRadius: "4px",
                    padding: "8px",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Verify Audit Chain Continuity
                </button>
                <button
                  onClick={handleExport}
                  style={{
                    background: "var(--surface-2)",
                    color: "var(--text)",
                    border: "1px solid var(--border)",
                    borderRadius: "4px",
                    padding: "8px",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Export Decision Record (JSON/MD)
                </button>
              </div>
            </div>

            {/* Engine Versions Snapshot */}
            <div
              style={{
                background: "var(--surface-1)",
                border: "1px solid var(--border)",
                borderRadius: "6px",
                padding: "var(--space-3)",
              }}
            >
              <div style={{ fontSize: "0.6875rem", fontWeight: 700, textTransform: "uppercase", color: "var(--muted)", marginBottom: "6px" }}>
                Engine Build Provenance
              </div>
              <div style={{ fontSize: "0.75rem", display: "flex", flexDirection: "column", gap: "4px" }}>
                {Object.entries(currentPackage.engine_versions || {}).map(([k, v]) => (
                  <div key={k} style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--muted)", textTransform: "capitalize" }}>{k}</span>
                    <span style={{ fontFamily: "monospace" }}>v{v}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 2: APPROVAL & SEPARATION OF DUTIES ───────────────────────── */}
      {activeTab === "workflow" && currentPackage && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
          {/* Left: State Progression Visualizer */}
          <div
            style={{
              background: "var(--surface-1)",
              border: "1px solid var(--border)",
              borderRadius: "6px",
              padding: "var(--space-4)",
            }}
          >
            <h3 style={{ fontSize: "0.875rem", fontWeight: 700, margin: "0 0 var(--space-4) 0", textTransform: "uppercase" }}>
              Formal Lifecycle Progression
            </h3>

            <div style={{ display: "flex", flexDirection: "column", gap: "12px", position: "relative" }}>
              {[
                { stage: "DRAFT", label: "1. Draft Assembly", desc: "Package assembled from Phase 10 Decision Run and upstream models." },
                { stage: "VALIDATED", label: "2. Evidence Validated", desc: "Automated verification of MILP optimality, CVaR tail risk, and thresholds." },
                { stage: "SUBMITTED", label: "3. Submitted for Sign-Off", desc: "Analyst seals package hash and submits to chartering authority." },
                { stage: "UNDER_REVIEW", label: "4. Under Committee Review", desc: "Active review by designated fleet director or chartering approver." },
                { stage: "APPROVED", label: "5. Formally Approved", desc: "Irreversible sign-off. Execution authorized. Modification in-place blocked." },
              ].map((s, idx) => {
                const isPassed =
                  currentPackage.status === "APPROVED" ||
                  (currentPackage.status === "UNDER_REVIEW" && idx <= 3) ||
                  (currentPackage.status === "SUBMITTED" && idx <= 2) ||
                  (currentPackage.status === "VALIDATED" && idx <= 1) ||
                  (currentPackage.status === "DRAFT" && idx === 0);
                const isCurrent = currentPackage.status === s.stage;

                return (
                  <div
                    key={s.stage}
                    style={{
                      display: "flex",
                      gap: "12px",
                      padding: "10px",
                      background: isCurrent ? "var(--surface-2)" : "transparent",
                      border: isCurrent ? "1px solid var(--info)" : "1px solid var(--border)",
                      borderRadius: "6px",
                    }}
                  >
                    <div
                      style={{
                        width: "24px",
                        height: "24px",
                        borderRadius: "50%",
                        background: isPassed ? "#10b981" : "var(--surface-2)",
                        color: isPassed ? "#fff" : "var(--muted)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                      }}
                    >
                      {isPassed ? "✓" : idx + 1}
                    </div>
                    <div>
                      <div style={{ fontSize: "0.8125rem", fontWeight: 700 }}>{s.label}</div>
                      <div style={{ fontSize: "0.6875rem", color: "var(--muted)", marginTop: "2px" }}>{s.desc}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right: Separation of Duties & Sign-off Panel */}
          <div
            style={{
              background: "var(--surface-1)",
              border: "1px solid var(--border)",
              borderRadius: "6px",
              padding: "var(--space-4)",
            }}
          >
            <h3 style={{ fontSize: "0.875rem", fontWeight: 700, margin: "0 0 var(--space-3) 0", textTransform: "uppercase" }}>
              Separation of Duties Gatekeeper
            </h3>

            {/* Rule Callout */}
            <div
              style={{
                padding: "var(--space-3)",
                background: "rgba(59, 130, 246, 0.1)",
                border: "1px solid #3b82f6",
                borderRadius: "6px",
                marginBottom: "var(--space-4)",
                fontSize: "0.75rem",
                lineHeight: 1.5,
              }}
            >
              <div style={{ fontWeight: 700, color: "#60a5fa", marginBottom: "2px" }}>
                Institutional Governance Rule: Creator ≠ Approver
              </div>
              <div>
                Package Creator: <strong style={{ color: "var(--text)" }}>{currentPackage.created_by || "analyst_alice"}</strong>
                <br />
                Active Signer: <strong style={{ color: "var(--text)" }}>{currentUser.id}</strong> ({currentUser.role})
              </div>
              {currentPackage.created_by === currentUser.id && (
                <div style={{ marginTop: "4px", color: "#f87171", fontWeight: 600 }}>
                  ⚠️ Self-Approval Forbidden: You created this package and cannot approve it. Switch persona to Approver.
                </div>
              )}
            </div>

            {/* Approval / Rejection Controls */}
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
              <div>
                <label style={{ fontSize: "0.75rem", color: "var(--muted)", display: "block", marginBottom: "4px" }}>
                  Sign-Off Notes / Operational Directives:
                </label>
                <textarea
                  value={approvalNotes}
                  onChange={(e) => setApprovalNotes(e.target.value)}
                  placeholder="e.g. Approved for spot charter execution. Ensure bunker hedge is executed prior to laycan."
                  rows={3}
                  style={{
                    width: "100%",
                    background: "var(--surface-2)",
                    border: "1px solid var(--border)",
                    borderRadius: "4px",
                    padding: "8px",
                    color: "var(--text)",
                    fontSize: "0.75rem",
                    resize: "vertical",
                  }}
                />
              </div>

              <div style={{ display: "flex", gap: "var(--space-2)" }}>
                <button
                  onClick={handleApprove}
                  disabled={actionLoading || currentPackage.created_by === currentUser.id}
                  style={{
                    flex: 1,
                    background: currentPackage.created_by === currentUser.id ? "var(--surface-2)" : "#10b981",
                    color: currentPackage.created_by === currentUser.id ? "var(--muted)" : "#fff",
                    border: "none",
                    borderRadius: "4px",
                    padding: "10px",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    cursor: currentPackage.created_by === currentUser.id ? "not-allowed" : "pointer",
                  }}
                >
                  ✓ Formal Sign-Off (APPROVE)
                </button>
              </div>

              <div style={{ borderTop: "1px solid var(--border)", paddingTop: "var(--space-3)" }}>
                <label style={{ fontSize: "0.75rem", color: "#f87171", display: "block", marginBottom: "4px" }}>
                  Rejection Reason (Mandatory if rejecting):
                </label>
                <input
                  type="text"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="e.g. Unacceptable ballast fuel consumption on trans-Pacific leg."
                  style={{
                    width: "100%",
                    background: "var(--surface-2)",
                    border: "1px solid var(--border)",
                    borderRadius: "4px",
                    padding: "6px 8px",
                    color: "var(--text)",
                    fontSize: "0.75rem",
                    marginBottom: "8px",
                  }}
                />
                <button
                  onClick={handleReject}
                  disabled={actionLoading || !rejectReason}
                  style={{
                    width: "100%",
                    background: "rgba(239, 68, 68, 0.15)",
                    color: "#f87171",
                    border: "1px solid #ef4444",
                    borderRadius: "4px",
                    padding: "8px",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    cursor: !rejectReason ? "not-allowed" : "pointer",
                  }}
                >
                  ✗ Formally Reject Package
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 3: SHA-256 AUDIT TRAIL ──────────────────────────────────── */}
      {activeTab === "audit" && currentPackage && (
        <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: "6px", padding: "var(--space-4)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-4)" }}>
            <div>
              <h3 style={{ fontSize: "0.875rem", fontWeight: 700, margin: 0, textTransform: "uppercase" }}>
                Tamper-Evident SHA-256 Hash Chain
              </h3>
              <p style={{ fontSize: "0.75rem", color: "var(--muted)", margin: "2px 0 0 0" }}>
                Append-only ledger. Event N cryptographically incorporates hash of Event N-1. Any content edit breaks verification.
              </p>
            </div>
            <button
              onClick={handleVerifyAudit}
              disabled={actionLoading}
              style={{
                background: "#0284c7",
                color: "#fff",
                border: "none",
                borderRadius: "4px",
                padding: "6px 14px",
                fontSize: "0.75rem",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Verify Hash Chain Now
            </button>
          </div>

          {/* Audit Chain Verification Banner */}
          {auditVerification && (
            <div
              style={{
                padding: "var(--space-3)",
                borderRadius: "6px",
                marginBottom: "var(--space-4)",
                background: auditVerification.is_valid ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)",
                border: `1px solid ${auditVerification.is_valid ? "#10b981" : "#ef4444"}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span style={{ fontSize: "1.25rem", color: auditVerification.is_valid ? "#10b981" : "#ef4444" }}>
                  {auditVerification.is_valid ? "🛡️" : "⚠️"}
                </span>
                <div>
                  <div style={{ fontSize: "0.8125rem", fontWeight: 700, color: auditVerification.is_valid ? "#34d399" : "#f87171" }}>
                    {auditVerification.is_valid ? "CRYPTOGRAPHIC AUDIT CHAIN VERIFIED" : "CHAIN INTEGRITY COMPROMISED"}
                  </div>
                  <div style={{ fontSize: "0.6875rem", color: "var(--muted)" }}>
                    {auditVerification.verified_count} of {auditVerification.event_count} events cryptographically confirmed from GENESIS. Broken links: {auditVerification.broken_links}.
                  </div>
                </div>
              </div>
              <span style={{ fontSize: "0.75rem", fontFamily: "monospace", color: "var(--muted)" }}>
                SHA-256 HASH-CHAINING
              </span>
            </div>
          )}

          {/* Simulated Visual Hash Blocks */}
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {[
              {
                seq: 1,
                type: "PACKAGE_CREATED",
                actor: currentPackage.created_by || "analyst_alice",
                role: currentPackage.created_by_role,
                desc: `Created Decision Package ${currentPackage.package_id} in DRAFT status.`,
                prev: "GENESIS",
                hash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
              },
              {
                seq: 2,
                type: "PACKAGE_VALIDATED",
                actor: "governance_validator",
                role: "SYSTEM",
                desc: `Package evidence validated against Phase 7–10 prerequisite schemas.`,
                prev: "e3b0c44298fc1c14...",
                hash: "a4f89d31c28b5e907a123f4581290d8102f9c8d193e87a20bc129487bcf91283",
              },
              {
                seq: 3,
                type: "PACKAGE_SUBMITTED",
                actor: currentPackage.created_by || "analyst_alice",
                role: currentPackage.created_by_role,
                desc: `Submitted for formal Institutional Committee review and sign-off.`,
                prev: "a4f89d31c28b5e90...",
                hash: "c782190efb2890a12903bc1840294819dcf982a0192837bc9018247dbac81923",
              },
              {
                seq: 4,
                type: currentPackage.status === "APPROVED" ? "PACKAGE_APPROVED" : "REVIEW_PROGRESS",
                actor: "director_bob",
                role: "APPROVER",
                desc: currentPackage.status === "APPROVED" ? `Formally APPROVED by Institutional Authority.` : `Active deliberation under Committee review.`,
                prev: "c782190efb2890a1...",
                hash: currentPackage.package_hash || "89f1029ba8d1928bc9012847ab91823bc019283849182bc819230ab981273612",
              },
            ].map((block) => (
              <div
                key={block.seq}
                style={{
                  background: "var(--surface-2)",
                  border: "1px solid var(--border)",
                  borderRadius: "6px",
                  padding: "var(--space-3)",
                  fontFamily: "monospace",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                  <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "#60a5fa" }}>
                    EVENT #{block.seq}: {block.type}
                  </span>
                  <span style={{ fontSize: "0.6875rem", color: "var(--muted)" }}>
                    Actor: {block.actor} ({block.role})
                  </span>
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text)", fontFamily: "sans-serif", marginBottom: "8px" }}>
                  {block.desc}
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", fontSize: "0.6875rem" }}>
                  <div style={{ background: "var(--surface-1)", padding: "4px 8px", borderRadius: "4px" }}>
                    <span style={{ color: "var(--muted)" }}>PREV_HASH: </span>
                    <span style={{ color: block.prev === "GENESIS" ? "#10b981" : "#a78bfa" }}>{block.prev}</span>
                  </div>
                  <div style={{ background: "var(--surface-1)", padding: "4px 8px", borderRadius: "4px" }}>
                    <span style={{ color: "var(--muted)" }}>EVENT_HASH: </span>
                    <span style={{ color: "#38bdf8" }}>{block.hash.substring(0, 24)}...</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── TAB 4: VERSION DELTA & REPRODUCIBILITY ───────────────────────── */}
      {activeTab === "versioning" && currentPackage && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
          {/* Version Increment & Diff */}
          <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: "6px", padding: "var(--space-4)" }}>
            <h3 style={{ fontSize: "0.875rem", fontWeight: 700, margin: "0 0 8px 0", textTransform: "uppercase" }}>
              Immutable Package Versioning
            </h3>
            <p style={{ fontSize: "0.75rem", color: "var(--muted)", margin: "0 0 var(--space-4) 0" }}>
              Approved packages cannot be altered in place. Modifications spawn an incremental child version (V1 → V2) linking back to parent package.
            </p>

            <div style={{ marginBottom: "var(--space-3)" }}>
              <label style={{ fontSize: "0.75rem", color: "var(--muted)", display: "block", marginBottom: "4px" }}>
                Revision Change Summary / Rationale:
              </label>
              <input
                type="text"
                value={versionSummary}
                onChange={(e) => setVersionSummary(e.target.value)}
                placeholder="e.g. Updated for revised bunker fuel pricing and canal delay."
                style={{
                  width: "100%",
                  background: "var(--surface-2)",
                  border: "1px solid var(--border)",
                  borderRadius: "4px",
                  padding: "6px 8px",
                  color: "var(--text)",
                  fontSize: "0.75rem",
                  marginBottom: "8px",
                }}
              />
              <button
                onClick={handleCreateVersion}
                disabled={actionLoading || !versionSummary}
                style={{
                  width: "100%",
                  background: "#8b5cf6",
                  color: "#fff",
                  border: "none",
                  borderRadius: "4px",
                  padding: "8px",
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  cursor: !versionSummary ? "not-allowed" : "pointer",
                }}
              >
                Create Incremental Child Version (V{currentPackage.version_number + 1}.0)
              </button>
            </div>

            {/* Version History Table */}
            <div style={{ borderTop: "1px solid var(--border)", paddingTop: "var(--space-3)" }}>
              <div style={{ fontSize: "0.6875rem", fontWeight: 700, textTransform: "uppercase", color: "var(--muted)", marginBottom: "6px" }}>
                Version Lineage
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 10px", background: "var(--surface-2)", borderRadius: "4px", fontSize: "0.75rem" }}>
                  <span>V{currentPackage.version_number}.0 (Current)</span>
                  <span style={{ fontFamily: "monospace", color: "#38bdf8" }}>{currentPackage.package_hash.substring(0, 16)}...</span>
                  <span style={{ color: "#34d399", fontWeight: 600 }}>{currentPackage.status}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Decision Reproducibility Verification */}
          <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: "6px", padding: "var(--space-4)" }}>
            <h3 style={{ fontSize: "0.875rem", fontWeight: 700, margin: "0 0 8px 0", textTransform: "uppercase" }}>
              Decision Reproducibility Verification
            </h3>
            <p style={{ fontSize: "0.75rem", color: "var(--muted)", margin: "0 0 var(--space-4) 0" }}>
              Re-executes the deterministic decision scoring pipeline from recorded upstream inputs to confirm bit-for-bit mathematical reproducibility.
            </p>

            <button
              onClick={handleReproduce}
              disabled={actionLoading}
              style={{
                width: "100%",
                background: "var(--accent)",
                color: "#fff",
                border: "none",
                borderRadius: "4px",
                padding: "10px",
                fontSize: "0.75rem",
                fontWeight: 700,
                cursor: "pointer",
                marginBottom: "var(--space-3)",
              }}
            >
              Verify Bit-for-Bit Decision Reproducibility
            </button>

            {reproResult && (
              <div
                style={{
                  padding: "var(--space-3)",
                  background: reproResult.is_reproducible ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)",
                  border: `1px solid ${reproResult.is_reproducible ? "#10b981" : "#ef4444"}`,
                  borderRadius: "6px",
                  fontSize: "0.75rem",
                }}
              >
                <div style={{ fontWeight: 700, color: reproResult.is_reproducible ? "#34d399" : "#f87171", marginBottom: "4px" }}>
                  {reproResult.is_reproducible ? "✓ REPRODUCIBILITY CONFIRMED" : "✗ REPRODUCTION MISMATCH"}
                </div>
                <div>Original Recommendation: <strong>{reproResult.original_recommendation}</strong></div>
                <div>Reproduced Recommendation: <strong>{reproResult.reproduced_recommendation}</strong></div>
                <div>Original Score: <strong>{reproResult.original_score.toFixed(1)}</strong> • Reproduced: <strong>{reproResult.reproduced_score.toFixed(1)}</strong></div>
                {reproResult.mismatched_fields.length > 0 && (
                  <div style={{ color: "#f87171", marginTop: "4px" }}>
                    Mismatches: {reproResult.mismatched_fields.join(", ")}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── TAB 5: HUMAN OVERRIDE GOVERNANCE ────────────────────────────── */}
      {activeTab === "override" && currentPackage && (
        <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: "6px", padding: "var(--space-4)" }}>
          <h3 style={{ fontSize: "0.875rem", fontWeight: 700, margin: "0 0 8px 0", textTransform: "uppercase" }}>
            Institutional Human Override Governance
          </h3>
          <p style={{ fontSize: "0.75rem", color: "var(--muted)", margin: "0 0 var(--space-4) 0" }}>
            When commercial or strategic imperatives require departing from the analytical model verdict, the departure is recorded with mandatory justification, approver attribution, and risk acknowledgement. The model recommendation is NEVER mutated or erased.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
            {/* Side-by-side: Model vs Human */}
            <div style={{ background: "var(--surface-2)", padding: "var(--space-3)", borderRadius: "6px", border: "1px solid var(--border)" }}>
              <div style={{ fontSize: "0.6875rem", color: "var(--muted)", textTransform: "uppercase", marginBottom: "4px" }}>
                1. Analytical Model Verdict
              </div>
              <div style={{ fontSize: "1.125rem", fontWeight: 700, color: "#60a5fa", marginBottom: "8px" }}>
                {currentPackage.recommendation_type}
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
                Score: {currentPackage.decision_score.toFixed(1)} pts • Confidence: {currentPackage.confidence}
                <br />
                Net Contribution: {formatUSD(currentPackage.expected_contribution)}
                <br />
                95% CVaR Tail Risk: {formatUSD(currentPackage.cvar_95)}
              </div>
            </div>

            <div style={{ background: "var(--surface-2)", padding: "var(--space-3)", borderRadius: "6px", border: "1px solid var(--border)" }}>
              <div style={{ fontSize: "0.6875rem", color: "var(--muted)", textTransform: "uppercase", marginBottom: "4px" }}>
                2. Final Institutional Decision
              </div>
              <div style={{ fontSize: "1.125rem", fontWeight: 700, color: currentPackage.is_override ? "#fbbf24" : "#34d399", marginBottom: "8px" }}>
                {currentPackage.is_override
                  ? `OVERRIDDEN TO: ${currentPackage.override_recommendation}`
                  : `CONCURRED WITH MODEL (${currentPackage.recommendation_type})`}
              </div>
              {currentPackage.is_override ? (
                <div style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
                  Reason: <em style={{ color: "var(--text)" }}>{currentPackage.override_reason}</em>
                </div>
              ) : (
                <div style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
                  No human override recorded. Operating strictly on analytical model guidance.
                </div>
              )}
            </div>
          </div>

          {/* Form to Apply Human Override */}
          <div style={{ marginTop: "var(--space-4)", borderTop: "1px solid var(--border)", paddingTop: "var(--space-4)" }}>
            <h4 style={{ fontSize: "0.8125rem", fontWeight: 700, margin: "0 0 var(--space-3) 0", textTransform: "uppercase" }}>
              Apply Commercial / Operational Override
            </h4>

            <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: "var(--space-3)", marginBottom: "var(--space-3)" }}>
              <div>
                <label style={{ fontSize: "0.75rem", color: "var(--muted)", display: "block", marginBottom: "4px" }}>
                  Override Verdict:
                </label>
                <select
                  value={overrideDecision}
                  onChange={(e) => setOverrideDecision(e.target.value)}
                  style={{
                    width: "100%",
                    background: "var(--surface-2)",
                    border: "1px solid var(--border)",
                    borderRadius: "4px",
                    padding: "6px",
                    color: "var(--text)",
                    fontSize: "0.75rem",
                  }}
                >
                  <option value="PROCEED">PROCEED (Commit Fleet)</option>
                  <option value="PROCEED_WITH_CAUTION">PROCEED_WITH_CAUTION</option>
                  <option value="RECONSIDER">RECONSIDER</option>
                  <option value="REJECT">REJECT</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: "0.75rem", color: "var(--muted)", display: "block", marginBottom: "4px" }}>
                  Mandatory Commercial Justification:
                </label>
                <input
                  type="text"
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                  placeholder="e.g. Strategic client relationship mandates fulfilling cargo obligation despite compressed margin."
                  style={{
                    width: "100%",
                    background: "var(--surface-2)",
                    border: "1px solid var(--border)",
                    borderRadius: "4px",
                    padding: "6px 8px",
                    color: "var(--text)",
                    fontSize: "0.75rem",
                  }}
                />
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "var(--space-3)" }}>
              <input
                type="checkbox"
                id="riskAck"
                checked={overrideAck}
                onChange={(e) => setOverrideAck(e.target.checked)}
              />
              <label htmlFor="riskAck" style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
                I acknowledge the tail risk and loss probability quantified by Phase 9 stochastic simulations and accept the commercial variance.
              </label>
            </div>

            <button
              onClick={handleOverride}
              disabled={actionLoading || !overrideReason || !overrideAck}
              style={{
                background: "#f59e0b",
                color: "#000",
                border: "none",
                borderRadius: "4px",
                padding: "8px 16px",
                fontSize: "0.75rem",
                fontWeight: 700,
                cursor: !overrideReason || !overrideAck ? "not-allowed" : "pointer",
              }}
            >
              Sign and Seal Operational Override
            </button>
          </div>
        </div>
      )}

      {/* ── TAB 6: INSTITUTIONAL POLICY & EXPORT ─────────────────────────── */}
      {activeTab === "policy" && currentPackage && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
          {/* Active Policy Config */}
          <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: "6px", padding: "var(--space-4)" }}>
            <h3 style={{ fontSize: "0.875rem", fontWeight: 700, margin: "0 0 8px 0", textTransform: "uppercase" }}>
              Active Decision Policy Configuration
            </h3>
            <p style={{ fontSize: "0.75rem", color: "var(--muted)", margin: "0 0 var(--space-4) 0" }}>
              Versioned policy parameters governing composite scoring weights and hurdle gates.
            </p>

            {policyConfig ? (
              <div style={{ fontSize: "0.75rem", display: "flex", flexDirection: "column", gap: "8px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border)", paddingBottom: "4px" }}>
                  <span style={{ color: "var(--muted)" }}>Policy ID / Version:</span>
                  <span style={{ fontWeight: 600 }}>{policyConfig.configuration_id} (v{policyConfig.version})</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--muted)" }}>Economic Weight (Phase 7 MILP):</span>
                  <span>{(policyConfig.economic_weight * 100).toFixed(0)}%</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--muted)" }}>Reliability Weight (Phase 8 Scenarios):</span>
                  <span>{(policyConfig.reliability_weight * 100).toFixed(0)}%</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--muted)" }}>Robustness Weight (What-If):</span>
                  <span>{(policyConfig.robustness_weight * 100).toFixed(0)}%</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--muted)" }}>Tail Risk Weight (Phase 9 CVaR):</span>
                  <span>{(policyConfig.tail_risk_weight * 100).toFixed(0)}%</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--muted)" }}>Schedule Buffer Weight (Laycan):</span>
                  <span>{(policyConfig.schedule_weight * 100).toFixed(0)}%</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", borderTop: "1px solid var(--border)", paddingTop: "4px" }}>
                  <span style={{ color: "var(--muted)" }}>Min Score to PROCEED:</span>
                  <span>{policyConfig.recommendation_thresholds?.min_score_proceed ?? 75.0} pts</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--muted)" }}>Max Loss Probability Gate:</span>
                  <span>{((policyConfig.recommendation_thresholds?.max_loss_prob_proceed ?? 0.05) * 100).toFixed(1)}%</span>
                </div>
              </div>
            ) : (
              <div style={{ fontSize: "0.75rem", color: "var(--muted)" }}>Loading active configuration...</div>
            )}
          </div>

          {/* Export Decision Record */}
          <div style={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: "6px", padding: "var(--space-4)" }}>
            <h3 style={{ fontSize: "0.875rem", fontWeight: 700, margin: "0 0 8px 0", textTransform: "uppercase" }}>
              Export Institutional Decision Record
            </h3>
            <p style={{ fontSize: "0.75rem", color: "var(--muted)", margin: "0 0 var(--space-4) 0" }}>
              Generates a self-contained, air-gap-compliant decision memo in Markdown and structured JSON for audit filing.
            </p>

            <button
              onClick={handleExport}
              disabled={actionLoading}
              style={{
                width: "100%",
                background: "var(--accent)",
                color: "#fff",
                border: "none",
                borderRadius: "4px",
                padding: "10px",
                fontSize: "0.75rem",
                fontWeight: 700,
                cursor: "pointer",
                marginBottom: "var(--space-3)",
              }}
            >
              Generate Decision Record Memo
            </button>

            {exportRecord && (
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                  <span style={{ fontSize: "0.75rem", fontWeight: 600 }}>Formatted Board Memorandum:</span>
                  <button
                    onClick={() => copyToClipboard(exportRecord.memo_markdown)}
                    style={{
                      background: "transparent",
                      border: "none",
                      color: "#38bdf8",
                      cursor: "pointer",
                      fontSize: "0.6875rem",
                    }}
                  >
                    Copy Markdown
                  </button>
                </div>
                <pre
                  style={{
                    background: "var(--surface-2)",
                    border: "1px solid var(--border)",
                    borderRadius: "4px",
                    padding: "var(--space-3)",
                    fontSize: "0.6875rem",
                    color: "var(--text)",
                    maxHeight: "260px",
                    overflowY: "auto",
                    whiteSpace: "pre-wrap",
                    fontFamily: "monospace",
                  }}
                >
                  {exportRecord.memo_markdown}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
