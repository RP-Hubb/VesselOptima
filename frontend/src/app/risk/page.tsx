"use client";

import React, { useState, useEffect } from "react";
import {
  getRiskConfigDefaults,
  simulatePlanRisk,
  getRiskFlipDemo,
  comparePlanRisk,
  getRiskRuns,
} from "@/lib/api";
import type {
  PlanRiskSimulationResponse,
  PlanRiskComparisonResponse,
  AssignmentRiskResponse,
  RiskDriverResponse,
  HistogramBinResponse,
  RiskRunSummary,
  RiskTier,
} from "@/types/api";

type ActiveTab = "overview" | "assignments" | "drivers" | "flip_proof" | "distributions";

export default function RiskPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>("overview");

  // Simulation Controls State
  const [simulationCount, setSimulationCount] = useState<number>(5000);
  const [randomSeed, setRandomSeed] = useState<number>(42);
  const [includeDemurrage, setIncludeDemurrage] = useState<boolean>(true);
  const [demurrageRate, setDemurrageRate] = useState<number>(15000);

  // Results State
  const [simulationResult, setSimulationResult] = useState<PlanRiskSimulationResponse | null>(null);
  const [flipComparison, setFlipComparison] = useState<PlanRiskComparisonResponse | null>(null);
  const [defaultConfig, setDefaultConfig] = useState<Record<string, any> | null>(null);
  const [recentRuns, setRecentRuns] = useState<RiskRunSummary[]>([]);
  const [selectedAssignment, setSelectedAssignment] = useState<AssignmentRiskResponse | null>(null);

  // Initial Load
  useEffect(() => {
    initDashboard();
  }, []);

  async function initDashboard() {
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch default configuration
      const defaults = await getRiskConfigDefaults();
      setDefaultConfig(defaults);

      // 2. Run initial baseline simulation
      const sim = await simulatePlanRisk({
        simulation_count: 5000,
        random_seed: 42,
        include_demurrage: true,
        demurrage_daily_rate: 15000,
      });
      setSimulationResult(sim);
      if (sim.assignments.length > 0) {
        setSelectedAssignment(sim.assignments[0]);
      }

      // 3. Fetch flip demo comparison
      const flip = await getRiskFlipDemo();
      setFlipComparison(flip);

      // 4. Fetch historical runs
      const runs = await getRiskRuns(10);
      setRecentRuns(runs);
    } catch (err: any) {
      setError(err?.message || "Failed to initialize Risk Intelligence Engine.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRunSimulation() {
    setLoading(true);
    setError(null);
    try {
      const res = await simulatePlanRisk({
        simulation_count: simulationCount,
        random_seed: randomSeed,
        include_demurrage: includeDemurrage,
        demurrage_daily_rate: demurrageRate,
      });
      setSimulationResult(res);
      if (res.assignments.length > 0) {
        setSelectedAssignment(res.assignments[0]);
      }
      const runs = await getRiskRuns(10);
      setRecentRuns(runs);
    } catch (err: any) {
      setError(err?.message || "Simulation execution failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleLoadFlipDemo() {
    setLoading(true);
    setError(null);
    try {
      const flip = await getRiskFlipDemo();
      setFlipComparison(flip);
      setActiveTab("flip_proof");
    } catch (err: any) {
      setError(err?.message || "Failed to load Critical Risk Flip demo.");
    } finally {
      setLoading(false);
    }
  }

  // Tier color helper
  function getTierBadgeClass(tier: RiskTier | string | null) {
    switch (tier) {
      case "LOW":
        return "bg-emerald-950/80 text-emerald-300 border-emerald-800";
      case "MODERATE":
        return "bg-cyan-950/80 text-cyan-300 border-cyan-800";
      case "HIGH":
        return "bg-amber-950/80 text-amber-300 border-amber-800";
      case "CRITICAL":
        return "bg-rose-950/80 text-rose-300 border-rose-800";
      default:
        return "bg-slate-800 text-slate-300 border-slate-700";
    }
  }

  return (
    <div className="min-h-screen bg-[#070B14] text-slate-100 font-mono p-4 md:p-6 space-y-6">
      {/* ── Top Header ────────────────────────────────────────────── */}
      <header className="border-b border-slate-800/80 pb-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
            <span className="text-cyan-400 font-semibold">VESSELOPTIMA</span>
            <span>/</span>
            <span>PHASE 9</span>
            <span>/</span>
            <span className="text-slate-200">RISK INTELLIGENCE & UNCERTAINTY</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-3">
            Risk & Uncertainty Engine
            <span className="text-xs px-2.5 py-0.5 rounded border border-cyan-500/40 bg-cyan-950/50 text-cyan-400 font-normal">
              MONTE CARLO VECTORIZED
            </span>
            <span className="text-xs px-2.5 py-0.5 rounded border border-emerald-500/40 bg-emerald-950/50 text-emerald-400 font-normal">
              100% AIR-GAP OFFLINE
            </span>
          </h1>
          <p className="text-xs text-slate-400 mt-1 max-w-3xl">
            Stochastic simulation of voyage revenues, bunker volatility, port congestion, and weather delays.
            Quantifies downside tail risk (VaR95/CVaR95), schedule fragile points, and Critical Risk Flips.
          </p>
        </div>

        {/* Quick Action Presets */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleLoadFlipDemo}
            className="text-xs px-3 py-2 rounded bg-amber-950/60 border border-amber-600/70 text-amber-300 hover:bg-amber-900/80 transition flex items-center gap-2"
          >
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span>
            Critical Risk Flip Proof
          </button>
          <button
            onClick={handleRunSimulation}
            disabled={loading}
            className="text-xs px-4 py-2 rounded bg-cyan-600 hover:bg-cyan-500 text-black font-semibold transition disabled:opacity-50"
          >
            {loading ? "Simulating..." : "Re-Simulate Plan"}
          </button>
        </div>
      </header>

      {/* ── Error Banner ──────────────────────────────────────────── */}
      {error && (
        <div className="p-3 bg-rose-950/80 border border-rose-800 text-rose-200 text-xs rounded">
          {error}
        </div>
      )}

      {/* ── Simulation Control Panel ──────────────────────────────── */}
      <section className="bg-slate-900/60 border border-slate-800 rounded-lg p-4 grid grid-cols-2 md:grid-cols-5 gap-4 items-end">
        <div>
          <label className="block text-[11px] uppercase tracking-wider text-slate-400 mb-1">
            Draws (N)
          </label>
          <select
            value={simulationCount}
            onChange={(e) => setSimulationCount(Number(e.target.value))}
            className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1.5 text-xs text-white"
          >
            <option value={1000}>1,000 iterations (Fast)</option>
            <option value={5000}>5,000 iterations (Standard)</option>
            <option value={10000}>10,000 iterations (High-Res)</option>
            <option value={25000}>25,000 iterations (Institutional)</option>
          </select>
        </div>

        <div>
          <label className="block text-[11px] uppercase tracking-wider text-slate-400 mb-1">
            Deterministic Seed
          </label>
          <input
            type="number"
            value={randomSeed}
            onChange={(e) => setRandomSeed(Number(e.target.value))}
            className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1.5 text-xs text-white"
          />
        </div>

        <div>
          <label className="block text-[11px] uppercase tracking-wider text-slate-400 mb-1">
            Demurrage Model
          </label>
          <button
            onClick={() => setIncludeDemurrage(!includeDemurrage)}
            className={`w-full py-1.5 px-3 rounded text-xs border transition ${
              includeDemurrage
                ? "bg-amber-950/50 border-amber-700 text-amber-300"
                : "bg-slate-950 border-slate-700 text-slate-400"
            }`}
          >
            {includeDemurrage ? "DEMURRAGE ACTIVE" : "EXCLUDED"}
          </button>
        </div>

        <div>
          <label className="block text-[11px] uppercase tracking-wider text-slate-400 mb-1">
            Demurrage Rate ($/Day)
          </label>
          <input
            type="number"
            value={demurrageRate}
            onChange={(e) => setDemurrageRate(Number(e.target.value))}
            className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1.5 text-xs text-white"
          />
        </div>

        <div>
          <button
            onClick={handleRunSimulation}
            disabled={loading}
            className="w-full bg-slate-800 hover:bg-slate-700 border border-slate-600 text-white py-1.5 px-3 rounded text-xs font-semibold transition"
          >
            {loading ? "Running Monte Carlo..." : "Execute Simulation"}
          </button>
        </div>
      </section>

      {/* ── Key Executive Scorecards ──────────────────────────────── */}
      {simulationResult && (
        <section className="grid grid-cols-2 md:grid-cols-6 gap-3">
          {/* Expected Contribution */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3.5 space-y-1">
            <span className="text-[10px] uppercase tracking-wider text-slate-400 block">
              Expected Contribution (E[Π])
            </span>
            <div className="text-xl font-bold text-white">
              ${simulationResult.expected_portfolio_contribution.toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-400">
              Std Dev: ±${simulationResult.portfolio_contribution_std.toLocaleString()}
            </div>
          </div>

          {/* VaR95 Downside */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3.5 space-y-1">
            <span className="text-[10px] uppercase tracking-wider text-amber-400 block">
              VaR 95% Downside (E - P05)
            </span>
            <div className="text-xl font-bold text-amber-300">
              ${simulationResult.var95_downside.toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-400">
              Level (P05): ${simulationResult.var95_level.toLocaleString()}
            </div>
          </div>

          {/* CVaR95 (Tail Expected Shortfall) */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3.5 space-y-1">
            <span className="text-[10px] uppercase tracking-wider text-rose-400 block">
              CVaR 95% (Tail Shortfall)
            </span>
            <div className="text-xl font-bold text-rose-300">
              ${simulationResult.cvar95.toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-400">
              Worst 5% Average Loss
            </div>
          </div>

          {/* Loss Probability */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3.5 space-y-1">
            <span className="text-[10px] uppercase tracking-wider text-slate-400 block">
              Loss Probability (P(Π &lt; 0))
            </span>
            <div
              className={`text-xl font-bold ${
                simulationResult.loss_probability > 0.05 ? "text-rose-400" : "text-emerald-400"
              }`}
            >
              {(simulationResult.loss_probability * 100).toFixed(1)}%
            </div>
            <div className="text-[11px] text-slate-400">
              Exp Loss: ${simulationResult.expected_loss.toLocaleString()}
            </div>
          </div>

          {/* Plan Reliability Score */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3.5 space-y-1">
            <span className="text-[10px] uppercase tracking-wider text-cyan-400 block">
              Plan Reliability Index
            </span>
            <div className="text-xl font-bold text-cyan-300">
              {simulationResult.plan_reliability_score.toFixed(1)}
              <span className="text-xs text-slate-500 font-normal"> / 100</span>
            </div>
            <div className="w-full bg-slate-950 h-1.5 rounded-full overflow-hidden">
              <div
                className="bg-cyan-400 h-full transition-all"
                style={{ width: `${Math.min(100, simulationResult.plan_reliability_score)}%` }}
              ></div>
            </div>
          </div>

          {/* Institutional Risk Tier */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3.5 space-y-1">
            <span className="text-[10px] uppercase tracking-wider text-slate-400 block">
              Portfolio Risk Tier
            </span>
            <div className="pt-1">
              <span
                className={`text-xs px-2.5 py-1 rounded border font-semibold ${getTierBadgeClass(
                  simulationResult.risk_tier
                )}`}
              >
                {simulationResult.risk_tier}
              </span>
            </div>
            <div className="text-[10px] text-slate-500 pt-1">
              {simulationResult.simulation_count.toLocaleString()} draws evaluated
            </div>
          </div>
        </section>
      )}

      {/* ── Navigation Tabs ───────────────────────────────────────── */}
      <nav className="flex gap-2 border-b border-slate-800 text-xs overflow-x-auto pb-2">
        <button
          onClick={() => setActiveTab("overview")}
          className={`px-3 py-1.5 rounded transition ${
            activeTab === "overview"
              ? "bg-cyan-950 border border-cyan-700 text-cyan-300 font-semibold"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          01. Distribution &amp; VaR Profile
        </button>
        <button
          onClick={() => setActiveTab("assignments")}
          className={`px-3 py-1.5 rounded transition ${
            activeTab === "assignments"
              ? "bg-cyan-950 border border-cyan-700 text-cyan-300 font-semibold"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          02. Assignment Fragility &amp; Schedule Risk ({simulationResult?.assignments.length || 0})
        </button>
        <button
          onClick={() => setActiveTab("drivers")}
          className={`px-3 py-1.5 rounded transition ${
            activeTab === "drivers"
              ? "bg-cyan-950 border border-cyan-700 text-cyan-300 font-semibold"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          03. Risk Drivers &amp; Variance Attribution ({simulationResult?.drivers.length || 0})
        </button>
        <button
          onClick={() => setActiveTab("flip_proof")}
          className={`px-3 py-1.5 rounded transition ${
            activeTab === "flip_proof"
              ? "bg-amber-950 border border-amber-700 text-amber-300 font-semibold"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          04. Critical Risk Flip &amp; Trade-off
        </button>
        <button
          onClick={() => setActiveTab("distributions")}
          className={`px-3 py-1.5 rounded transition ${
            activeTab === "distributions"
              ? "bg-cyan-950 border border-cyan-700 text-cyan-300 font-semibold"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          05. Stochastic Parameters &amp; Provenance
        </button>
      </nav>

      {/* ── TAB 1: Distribution & VaR Profile ─────────────────────── */}
      {activeTab === "overview" && simulationResult && (
        <div className="space-y-6">
          {/* Frequency Histogram */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold text-white">
                  Simulated Portfolio Net Contribution Frequency Distribution
                </h3>
                <p className="text-xs text-slate-400">
                  Relative frequency across {simulationResult.simulation_count.toLocaleString()} Monte Carlo draws.
                  Vertical markers indicate Expected Outcome, VaR95 Downside threshold, and CVaR95 Expected Shortfall.
                </p>
              </div>
              <div className="flex items-center gap-4 text-xs">
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-0.5 bg-cyan-400"></span>
                  <span className="text-slate-300">Expected Mean</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-0.5 bg-amber-400"></span>
                  <span className="text-slate-300">VaR 95% (P05)</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-0.5 bg-rose-400"></span>
                  <span className="text-slate-300">CVaR 95%</span>
                </span>
              </div>
            </div>

            {/* SVG Chart */}
            <div className="w-full h-64 bg-slate-950/80 rounded border border-slate-800/80 p-3 relative flex items-end">
              {simulationResult.distribution_histogram.length > 0 ? (
                (() => {
                  const hist = simulationResult.distribution_histogram;
                  const maxFreq = Math.max(...hist.map((b) => b.frequency), 0.01);
                  const minVal = hist[0].bin_start;
                  const maxVal = hist[hist.length - 1].bin_end;
                  const range = maxVal - minVal || 1.0;

                  // Percent positions for markers
                  const meanPct = Math.max(0, Math.min(100, ((simulationResult.expected_portfolio_contribution - minVal) / range) * 100));
                  const var95Pct = Math.max(0, Math.min(100, ((simulationResult.var95_level - minVal) / range) * 100));
                  const cvar95Pct = Math.max(0, Math.min(100, ((simulationResult.cvar95 - minVal) / range) * 100));

                  return (
                    <div className="w-full h-full relative">
                      {/* Vertical Grid & Markers */}
                      <div
                        className="absolute top-0 bottom-0 border-l border-cyan-400 border-dashed z-20"
                        style={{ left: `${meanPct}%` }}
                        title={`Mean: $${simulationResult.expected_portfolio_contribution.toLocaleString()}`}
                      >
                        <span className="absolute -top-1 -left-4 text-[9px] text-cyan-400 bg-slate-900 px-1 rounded border border-cyan-800">
                          E[Π]
                        </span>
                      </div>
                      <div
                        className="absolute top-0 bottom-0 border-l border-amber-400 border-dashed z-20"
                        style={{ left: `${var95Pct}%` }}
                        title={`VaR95: $${simulationResult.var95_level.toLocaleString()}`}
                      >
                        <span className="absolute top-4 -left-5 text-[9px] text-amber-400 bg-slate-900 px-1 rounded border border-amber-800">
                          VaR95
                        </span>
                      </div>
                      <div
                        className="absolute top-0 bottom-0 border-l border-rose-400 border-dashed z-20"
                        style={{ left: `${cvar95Pct}%` }}
                        title={`CVaR95: $${simulationResult.cvar95.toLocaleString()}`}
                      >
                        <span className="absolute top-9 -left-6 text-[9px] text-rose-400 bg-slate-900 px-1 rounded border border-rose-800">
                          CVaR95
                        </span>
                      </div>

                      {/* Histogram Bars */}
                      <div className="w-full h-full flex items-end gap-[1px]">
                        {hist.map((bin, idx) => {
                          const heightPct = (bin.frequency / maxFreq) * 90;
                          const isLossTail = bin.bin_end <= 0;
                          const isWorstTail = bin.bin_end <= simulationResult.var95_level;

                          return (
                            <div
                              key={idx}
                              className="flex-1 group relative transition-all"
                              style={{ height: `${heightPct}%` }}
                            >
                              <div
                                className={`w-full h-full rounded-t-sm transition-colors ${
                                  isLossTail
                                    ? "bg-rose-500/80 hover:bg-rose-400"
                                    : isWorstTail
                                    ? "bg-amber-500/80 hover:bg-amber-400"
                                    : "bg-cyan-500/70 hover:bg-cyan-300"
                                }`}
                              ></div>
                              {/* Hover Tooltip */}
                              <div className="hidden group-hover:block absolute bottom-full mb-2 left-1/2 -translate-x-1/2 bg-slate-900 border border-slate-700 text-[10px] p-2 rounded shadow-xl whitespace-nowrap z-30 pointer-events-none">
                                <div className="text-white font-semibold">
                                  ${bin.bin_start.toLocaleString()} to ${bin.bin_end.toLocaleString()}
                                </div>
                                <div className="text-slate-400">
                                  Count: {bin.count.toLocaleString()} ({(bin.frequency * 100).toFixed(2)}%)
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })()
              ) : (
                <div className="w-full h-full flex items-center justify-center text-xs text-slate-500">
                  No histogram distribution data available.
                </div>
              )}
            </div>

            {/* X-Axis Range */}
            {simulationResult.distribution_histogram.length > 0 && (
              <div className="flex justify-between text-[10px] text-slate-400 mt-2 px-1">
                <span>
                  Min: ${simulationResult.distribution_histogram[0].bin_start.toLocaleString()}
                </span>
                <span>
                  Max: ${simulationResult.distribution_histogram[simulationResult.distribution_histogram.length - 1].bin_end.toLocaleString()}
                </span>
              </div>
            )}
          </div>

          {/* Quantiles Table */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
            <h4 className="text-xs uppercase tracking-wider text-slate-300 font-semibold mb-3">
              Institutional Percentiles &amp; Tail Metrics (USD)
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-7 gap-2">
              {Object.entries(simulationResult.percentiles).map(([q, val]) => (
                <div key={q} className="bg-slate-950 border border-slate-800/80 rounded p-2.5 text-center">
                  <span className="text-[10px] uppercase text-slate-400 block font-semibold">{q}</span>
                  <span className="text-xs text-slate-100 font-bold mt-1 block">
                    ${val.toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 2: Assignment Fragility & Schedule Risk ───────────── */}
      {activeTab === "assignments" && simulationResult && (
        <div className="space-y-4">
          <div className="bg-slate-900/60 border border-slate-800 rounded-lg overflow-hidden">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-white">
                  Vessel Assignment Fragility &amp; Schedule Risk Matrix
                </h3>
                <p className="text-xs text-slate-400">
                  Quantifies schedule buffer days, arrival distributions (P50/P90), laycan miss probability,
                  and combined economic/schedule survival per voyage.
                </p>
              </div>
              <div className="text-xs text-slate-400">
                {simulationResult.assignments.length} assignments evaluated
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-950 text-slate-400 border-b border-slate-800 uppercase text-[10px] tracking-wider">
                    <th className="p-3">Candidate / Vessel</th>
                    <th className="p-3">Cargo Target</th>
                    <th className="p-3 text-right">Expected Contrib</th>
                    <th className="p-3 text-right">CVaR 95%</th>
                    <th className="p-3 text-center">Loss Prob</th>
                    <th className="p-3">Expected Arr</th>
                    <th className="p-3">P90 Arr</th>
                    <th className="p-3 text-right">Buffer Days</th>
                    <th className="p-3 text-center">Laycan Miss</th>
                    <th className="p-3 text-center">Survival</th>
                    <th className="p-3 text-center">Tier</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {simulationResult.assignments.map((asgn) => {
                    const isFragile = asgn.schedule_buffer_days < 1.0 || asgn.laycan_miss_probability > 0.15;

                    return (
                      <tr
                        key={asgn.candidate_id}
                        onClick={() => setSelectedAssignment(asgn)}
                        className={`hover:bg-slate-800/40 transition cursor-pointer ${
                          selectedAssignment?.candidate_id === asgn.candidate_id ? "bg-slate-800/60" : ""
                        }`}
                      >
                        <td className="p-3">
                          <div className="font-semibold text-white">{asgn.vessel_name}</div>
                          <div className="text-[10px] text-slate-500">{asgn.candidate_id}</div>
                        </td>
                        <td className="p-3 text-slate-300">
                          {asgn.cargo_name}
                        </td>
                        <td className="p-3 text-right font-semibold text-slate-100">
                          ${asgn.expected_net_contribution.toLocaleString()}
                        </td>
                        <td className="p-3 text-right font-semibold text-rose-300">
                          ${asgn.cvar95.toLocaleString()}
                        </td>
                        <td className="p-3 text-center">
                          <span
                            className={`${
                              asgn.loss_probability > 0.05 ? "text-rose-400 font-semibold" : "text-slate-300"
                            }`}
                          >
                            {(asgn.loss_probability * 100).toFixed(1)}%
                          </span>
                        </td>
                        <td className="p-3 text-slate-300 font-mono text-[11px]">
                          {new Date(asgn.expected_arrival).toLocaleDateString()}
                        </td>
                        <td className="p-3 text-slate-300 font-mono text-[11px]">
                          {new Date(asgn.p90_arrival).toLocaleDateString()}
                        </td>
                        <td className="p-3 text-right">
                          <span
                            className={`font-semibold ${
                              isFragile ? "text-rose-400 font-bold" : "text-emerald-400"
                            }`}
                          >
                            {asgn.schedule_buffer_days.toFixed(1)} d
                          </span>
                        </td>
                        <td className="p-3 text-center">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] ${
                              asgn.laycan_miss_probability > 0.10
                                ? "bg-rose-950 text-rose-300 border border-rose-800 font-bold"
                                : "text-slate-400"
                            }`}
                          >
                            {(asgn.laycan_miss_probability * 100).toFixed(1)}%
                          </span>
                        </td>
                        <td className="p-3 text-center text-slate-300 font-semibold">
                          {(asgn.combined_survival_probability * 100).toFixed(1)}%
                        </td>
                        <td className="p-3 text-center">
                          <span
                            className={`text-[10px] px-2 py-0.5 rounded border font-semibold ${getTierBadgeClass(
                              asgn.risk_tier
                            )}`}
                          >
                            {asgn.risk_tier}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Selected Assignment Breakdown Panel */}
          {selectedAssignment && (
            <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4 grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <span className="text-[10px] uppercase text-slate-400 block">Vessel &amp; Route</span>
                <div className="text-sm font-bold text-white mt-0.5">{selectedAssignment.vessel_name}</div>
                <div className="text-xs text-slate-400">{selectedAssignment.cargo_name}</div>
              </div>
              <div>
                <span className="text-[10px] uppercase text-slate-400 block">Schedule Buffer Days</span>
                <div
                  className={`text-lg font-bold mt-0.5 ${
                    selectedAssignment.schedule_buffer_days < 1.0 ? "text-rose-400" : "text-emerald-400"
                  }`}
                >
                  {selectedAssignment.schedule_buffer_days.toFixed(2)} Days
                </div>
                <div className="text-[10px] text-slate-500">
                  Laycan End: {new Date(selectedAssignment.laycan_end).toLocaleDateString()}
                </div>
              </div>
              <div>
                <span className="text-[10px] uppercase text-slate-400 block">Laycan Miss Risk</span>
                <div className="text-lg font-bold text-amber-300 mt-0.5">
                  {(selectedAssignment.laycan_miss_probability * 100).toFixed(1)}%
                </div>
                <div className="text-[10px] text-slate-500">
                  P90 Arrival: {new Date(selectedAssignment.p90_arrival).toLocaleDateString()}
                </div>
              </div>
              <div>
                <span className="text-[10px] uppercase text-slate-400 block">Economic Survival</span>
                <div className="text-lg font-bold text-cyan-300 mt-0.5">
                  {(selectedAssignment.economic_survival_probability * 100).toFixed(1)}%
                </div>
                <div className="text-[10px] text-slate-500">
                  CVaR95 Downside: ${selectedAssignment.cvar95.toLocaleString()}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── TAB 3: Risk Drivers & Variance Attribution ─────────────── */}
      {activeTab === "drivers" && simulationResult && (
        <div className="space-y-6">
          <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-5">
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-white">
                Stochastic Risk Drivers &amp; Variance Decomposition (ANOVA)
              </h3>
              <p className="text-xs text-slate-400">
                Quantifies the percentage contribution of each uncertain operational variable to portfolio volatility.
                Calculated via econometric regression decomposition and component variance attribution.
              </p>
            </div>

            <div className="space-y-4">
              {simulationResult.drivers.map((driver, idx) => (
                <div key={driver.variable_id} className="bg-slate-950 border border-slate-800/80 rounded p-4 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-slate-800 flex items-center justify-center text-[10px] text-slate-300 font-bold">
                        {idx + 1}
                      </span>
                      <span className="font-semibold text-white">{driver.name}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                        {driver.category}
                      </span>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-slate-400">
                        Sensitivity &beta;:{" "}
                        <span className="text-slate-200 font-bold">{driver.sensitivity_coefficient.toFixed(3)}</span>
                      </span>
                      <span className="text-sm font-bold text-cyan-400">
                        {driver.uncertainty_contribution_pct.toFixed(1)}%
                      </span>
                    </div>
                  </div>

                  {/* Horizontal Bar */}
                  <div className="w-full bg-slate-900 h-2 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        driver.uncertainty_contribution_pct > 30
                          ? "bg-amber-400"
                          : driver.uncertainty_contribution_pct > 15
                          ? "bg-cyan-400"
                          : "bg-slate-500"
                      }`}
                      style={{ width: `${Math.max(2, driver.uncertainty_contribution_pct)}%` }}
                    ></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 4: Critical Risk Flip & Plan Comparison ────────────── */}
      {activeTab === "flip_proof" && (
        <div className="space-y-6">
          {flipComparison ? (
            <div className="space-y-6">
              {/* Executive Summary Banner */}
              <div className="bg-amber-950/40 border border-amber-600/60 rounded-lg p-5 space-y-2">
                <div className="flex items-center gap-2 text-amber-400 font-bold text-sm">
                  <span className="w-3 h-3 rounded-full bg-amber-400 animate-ping"></span>
                  EXECUTIVE RISK DIVERGENCE: CRITICAL RISK FLIP IDENTIFIED
                </div>
                <p className="text-xs text-amber-200 leading-relaxed font-sans">
                  {flipComparison.trade_off_summary}
                </p>
                <p className="text-xs text-slate-300 font-sans mt-2 border-t border-amber-900/60 pt-2">
                  <strong className="text-white">Institutional Recommendation: </strong>
                  {flipComparison.recommendation_notes}
                </p>
              </div>

              {/* Side by Side Plan Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Plan A (Aggressive) */}
                <div className="bg-slate-900/70 border border-rose-900/60 rounded-lg p-5 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <div>
                      <h4 className="text-sm font-bold text-white">{flipComparison.plan_a_name}</h4>
                      <span className="text-[10px] text-rose-400 font-semibold">TIGHT SCHEDULE / FUEL-EXPOSED</span>
                    </div>
                    <span className="text-xs px-2.5 py-1 rounded bg-rose-950 border border-rose-800 text-rose-300 font-bold">
                      HIGH TAIL RISK
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="bg-slate-950 p-3 rounded border border-slate-800">
                      <span className="text-[10px] uppercase text-slate-400 block">Expected Contribution</span>
                      <span className="text-base font-bold text-emerald-400 block mt-0.5">
                        ${flipComparison.plan_a_expected_contribution.toLocaleString()}
                      </span>
                      <span className="text-[10px] text-emerald-500 font-semibold">
                        +${Math.abs(flipComparison.expected_contribution_delta).toLocaleString()} advantage
                      </span>
                    </div>

                    <div className="bg-slate-950 p-3 rounded border border-slate-800">
                      <span className="text-[10px] uppercase text-slate-400 block">Loss Probability</span>
                      <span className="text-base font-bold text-rose-400 block mt-0.5">
                        {(flipComparison.plan_a_loss_probability * 100).toFixed(1)}%
                      </span>
                      <span className="text-[10px] text-rose-500 font-semibold">
                        Severe tail exposure
                      </span>
                    </div>

                    <div className="bg-slate-950 p-3 rounded border border-slate-800">
                      <span className="text-[10px] uppercase text-slate-400 block">CVaR 95% (Tail)</span>
                      <span className="text-base font-bold text-rose-300 block mt-0.5">
                        ${flipComparison.plan_a_cvar95.toLocaleString()}
                      </span>
                    </div>

                    <div className="bg-slate-950 p-3 rounded border border-slate-800">
                      <span className="text-[10px] uppercase text-slate-400 block">Reliability Score</span>
                      <span className="text-base font-bold text-slate-300 block mt-0.5">
                        {flipComparison.plan_a_reliability_score.toFixed(1)} / 100
                      </span>
                    </div>
                  </div>
                </div>

                {/* Plan B (Robust) */}
                <div className="bg-slate-900/70 border border-emerald-900/60 rounded-lg p-5 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <div>
                      <h4 className="text-sm font-bold text-white">{flipComparison.plan_b_name}</h4>
                      <span className="text-[10px] text-emerald-400 font-semibold">STAGGERED BUFFER / CAPITAL PRESERVATION</span>
                    </div>
                    <span className="text-xs px-2.5 py-1 rounded bg-emerald-950 border border-emerald-800 text-emerald-300 font-bold">
                      INSTITUTIONAL ROBUST
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="bg-slate-950 p-3 rounded border border-slate-800">
                      <span className="text-[10px] uppercase text-slate-400 block">Expected Contribution</span>
                      <span className="text-base font-bold text-white block mt-0.5">
                        ${flipComparison.plan_b_expected_contribution.toLocaleString()}
                      </span>
                      <span className="text-[10px] text-slate-500 font-normal">
                        Insurance discount
                      </span>
                    </div>

                    <div className="bg-slate-950 p-3 rounded border border-slate-800">
                      <span className="text-[10px] uppercase text-slate-400 block">Loss Probability</span>
                      <span className="text-base font-bold text-emerald-400 block mt-0.5">
                        {(flipComparison.plan_b_loss_probability * 100).toFixed(1)}%
                      </span>
                      <span className="text-[10px] text-emerald-500 font-semibold">
                        Near-zero loss risk
                      </span>
                    </div>

                    <div className="bg-slate-950 p-3 rounded border border-slate-800">
                      <span className="text-[10px] uppercase text-slate-400 block">CVaR 95% (Tail)</span>
                      <span className="text-base font-bold text-emerald-300 block mt-0.5">
                        ${flipComparison.plan_b_cvar95.toLocaleString()}
                      </span>
                    </div>

                    <div className="bg-slate-950 p-3 rounded border border-slate-800">
                      <span className="text-[10px] uppercase text-slate-400 block">Reliability Score</span>
                      <span className="text-base font-bold text-cyan-300 block mt-0.5">
                        {flipComparison.plan_b_reliability_score.toFixed(1)} / 100
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center bg-slate-900/60 border border-slate-800 rounded-lg">
              <p className="text-xs text-slate-400 mb-4">No active plan comparison loaded.</p>
              <button
                onClick={handleLoadFlipDemo}
                className="text-xs px-4 py-2 bg-amber-600 hover:bg-amber-500 text-black font-semibold rounded transition"
              >
                Load Canonical Critical Risk Flip Proof
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── TAB 5: Stochastic Parameters & Provenance ──────────────── */}
      {activeTab === "distributions" && defaultConfig && (
        <div className="space-y-6">
          <div className="bg-slate-900/60 border border-slate-800 rounded-lg overflow-hidden">
            <div className="p-4 border-b border-slate-800">
              <h3 className="text-sm font-semibold text-white">
                Active Probability Distributions &amp; Domain Boundaries
              </h3>
              <p className="text-xs text-slate-400">
                Formal mathematical distributions parameterizing continuous uncertainty. Physical domain boundaries
                (e.g., fuel price &gt; 0, delay &ge; 0) are strictly enforced prior to Monte Carlo sampling.
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-950 text-slate-400 border-b border-slate-800 uppercase text-[10px] tracking-wider">
                    <th className="p-3">Variable</th>
                    <th className="p-3">Category</th>
                    <th className="p-3">Distribution</th>
                    <th className="p-3">Parameters</th>
                    <th className="p-3 text-right">Baseline</th>
                    <th className="p-3">Provenance Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {(defaultConfig.variables || []).map((v: any) => (
                    <tr key={v.variable_id} className="hover:bg-slate-800/30">
                      <td className="p-3">
                        <div className="font-semibold text-white">{v.name}</div>
                        <div className="text-[10px] text-slate-500">{v.variable_id}</div>
                      </td>
                      <td className="p-3 text-slate-300">{v.category}</td>
                      <td className="p-3 text-cyan-400 font-semibold">{v.distribution_type}</td>
                      <td className="p-3 text-slate-300 font-mono text-[11px]">
                        {JSON.stringify(v.parameters)}
                      </td>
                      <td className="p-3 text-right font-semibold text-slate-200">
                        {v.baseline_value ?? "—"} {v.unit}
                      </td>
                      <td className="p-3 text-slate-400 text-[11px]">
                        <span className="text-slate-300 font-semibold block">{v.provenance}</span>
                        <span className="text-[10px] text-slate-500">{v.source_ref}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
