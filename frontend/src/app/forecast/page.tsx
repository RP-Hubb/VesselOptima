"use client";

import { useEffect, useState, useMemo } from "react";
import { getForecastSeries, getForecast, trainForecast } from "@/lib/api";
import type {
  SeriesCatalogItem,
  ForecastResponse,
  ForecastPoint,
  HistoricalPoint,
} from "@/types/api";

/**
 * VesselOptima — Phase 3: Forecast Intelligence Terminal
 *
 * Core Principle: "Prediction ≠ Decision"
 * Displays causal time-series forecasts, empirical prediction intervals,
 * and out-of-sample walk-forward validation evidence.
 */
export default function ForecastPage() {
  const [catalog, setCatalog] = useState<SeriesCatalogItem[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<string>("market_index");
  const [selectedSeriesId, setSelectedSeriesId] = useState<string>("INDEX_BDI");
  const [horizonDays, setHorizonDays] = useState<number>(30);
  const [forecastData, setForecastData] = useState<ForecastResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [retraining, setRetraining] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Load series catalog on mount
  useEffect(() => {
    getForecastSeries()
      .then((items) => {
        setCatalog(items);
        if (items.length > 0) {
          const defaultItem = items.find((i) => i.series_id === "INDEX_BDI") || items[0];
          setSelectedTarget(defaultItem.target);
          setSelectedSeriesId(defaultItem.series_id);
        }
      })
      .catch((err) => {
        setError(err.message || "Failed to load series catalog");
      });
  }, []);

  // Fetch forecast when series or horizon changes
  useEffect(() => {
    if (!selectedTarget || !selectedSeriesId) return;
    setLoading(true);
    setError(null);
    getForecast(selectedTarget, selectedSeriesId, horizonDays)
      .then((data) => {
        setForecastData(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to load forecast data");
        setLoading(false);
      });
  }, [selectedTarget, selectedSeriesId, horizonDays]);

  // Handle re-training
  const handleRetrain = async () => {
    if (!selectedTarget || !selectedSeriesId) return;
    setRetraining(true);
    setError(null);
    try {
      const data = await trainForecast(selectedTarget, selectedSeriesId, horizonDays, true);
      setForecastData(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Retraining failed";
      setError(msg);
    } finally {
      setRetraining(false);
    }
  };

  // Group catalog by target
  const groupedTargets = useMemo(() => {
    const map = new Map<string, SeriesCatalogItem[]>();
    catalog.forEach((item) => {
      const list = map.get(item.target) || [];
      list.push(item);
      map.set(item.target, list);
    });
    return map;
  }, [catalog]);

  // Active series metadata
  const currentSeriesInfo = useMemo(() => {
    return catalog.find((i) => i.series_id === selectedSeriesId);
  }, [catalog, selectedSeriesId]);

  // SVG Chart Computations
  const chartMetrics = useMemo(() => {
    if (!forecastData) return null;
    const hist = forecastData.historical_points.slice(-60); // Last 60 historical days for clarity
    const fcast = forecastData.forecast_points;

    const allValues: number[] = [
      ...hist.map((p) => p.value),
      ...fcast.map((p) => p.value),
      ...fcast.map((p) => p.lower_95),
      ...fcast.map((p) => p.upper_95),
    ];

    const minVal = Math.min(...allValues);
    const maxVal = Math.max(...allValues);
    const valRange = maxVal - minVal || 1;
    const paddedMin = Math.max(0, minVal - valRange * 0.08);
    const paddedMax = maxVal + valRange * 0.08;

    const width = 860;
    const height = 300;
    const padding = { top: 20, right: 30, bottom: 40, left: 65 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    const totalPoints = hist.length + fcast.length;
    const xStep = chartW / Math.max(1, totalPoints - 1);

    const getY = (val: number) => {
      const norm = (val - paddedMin) / (paddedMax - paddedMin);
      return padding.top + chartH * (1 - norm);
    };

    const histCoords = hist.map((p, i) => ({
      x: padding.left + i * xStep,
      y: getY(p.value),
      date: p.date,
      value: p.value,
    }));

    const splitX = padding.left + (hist.length - 1) * xStep;

    const fcastCoords = fcast.map((p, i) => {
      const idx = hist.length + i;
      return {
        x: padding.left + idx * xStep,
        y: getY(p.value),
        yLower80: getY(p.lower_80),
        yUpper80: getY(p.upper_80),
        yLower95: getY(p.lower_95),
        yUpper95: getY(p.upper_95),
        date: p.date,
        value: p.value,
        lower_80: p.lower_80,
        upper_80: p.upper_80,
        lower_95: p.lower_95,
        upper_95: p.upper_95,
      };
    });

    // Construct SVG paths
    const histPath = histCoords
      .map((c, i) => `${i === 0 ? "M" : "L"} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`)
      .join(" ");

    const fcastLinePoints = [
      histCoords[histCoords.length - 1],
      ...fcastCoords,
    ].filter(Boolean);

    const fcastPath = fcastLinePoints
      .map((c, i) => `${i === 0 ? "M" : "L"} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`)
      .join(" ");

    // 95% Confidence Band
    const band95Top = fcastCoords.map((c) => `${c.x.toFixed(1)} ${c.yUpper95.toFixed(1)}`);
    const band95Bottom = [...fcastCoords].reverse().map((c) => `${c.x.toFixed(1)} ${c.yLower95.toFixed(1)}`);
    const band95Path = `M ${band95Top.join(" L ")} L ${band95Bottom.join(" L ")} Z`;

    // 80% Confidence Band
    const band80Top = fcastCoords.map((c) => `${c.x.toFixed(1)} ${c.yUpper80.toFixed(1)}`);
    const band80Bottom = [...fcastCoords].reverse().map((c) => `${c.x.toFixed(1)} ${c.yLower80.toFixed(1)}`);
    const band80Path = `M ${band80Top.join(" L ")} L ${band80Bottom.join(" L ")} Z`;

    // Y Axis ticks
    const yTicks = [0, 0.25, 0.5, 0.75, 1.0].map((frac) => {
      const val = paddedMin + frac * (paddedMax - paddedMin);
      return { val, y: getY(val) };
    });

    return {
      width,
      height,
      padding,
      splitX,
      histCoords,
      fcastCoords,
      histPath,
      fcastPath,
      band95Path,
      band80Path,
      yTicks,
      paddedMin,
      paddedMax,
    };
  }, [forecastData]);

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      {/* Header bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "var(--space-3)" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-1)" }}>
            <h1 style={{ fontSize: "1rem", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", margin: 0 }}>
              Forecast Intelligence Foundation
            </h1>
            <span
              style={{
                fontSize: "0.6875rem",
                padding: "2px 6px",
                borderRadius: "3px",
                background: "rgba(56, 189, 248, 0.15)",
                color: "var(--info)",
                fontWeight: 600,
                border: "1px solid rgba(56, 189, 248, 0.3)",
              }}
            >
              PHASE 3 ACTIVE
            </span>
          </div>
          <div style={{ fontSize: "0.8125rem", color: "var(--muted)", fontFamily: "'ui-monospace', monospace" }}>
            Deterministic walk-forward time-series models & empirical prediction intervals. [Prediction ≠ Decision]
          </div>
        </div>

        {/* Provenance Banner */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-3)",
            background: "var(--surface-1)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            padding: "var(--space-2) var(--space-3)",
            fontSize: "0.75rem",
            fontFamily: "'ui-monospace', monospace",
          }}
        >
          <div>
            <span style={{ color: "var(--muted)" }}>DATA: </span>
            <span style={{ color: "var(--info)", fontWeight: 600 }}>OFFLINE DEMO</span>
          </div>
          <div style={{ color: "var(--border)" }}>|</div>
          <div>
            <span style={{ color: "var(--muted)" }}>SOURCE: </span>
            <span style={{ color: "var(--text)" }}>demo-v1</span>
          </div>
          <div style={{ color: "var(--border)" }}>|</div>
          <div>
            <span style={{ color: "var(--muted)" }}>PROVENANCE: </span>
            <span
              style={{
                color: currentSeriesInfo?.provenance === "OBSERVED" ? "var(--positive)" : "var(--warning)",
                fontWeight: 600,
              }}
            >
              {currentSeriesInfo?.provenance || "SYNTHETIC / PROXY"}
            </span>
          </div>
        </div>
      </div>

      {/* Control Panel: Target/Series Selector + Horizon Selector */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: "var(--space-3)",
          background: "var(--surface-1)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-md)",
          padding: "var(--space-3)",
        }}
      >
        {/* Series Selection */}
        <div>
          <label
            style={{
              display: "block",
              fontSize: "0.6875rem",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "var(--muted)",
              marginBottom: "var(--space-1)",
            }}
          >
            Forecasting Target & Series
          </label>
          <select
            value={selectedSeriesId}
            onChange={(e) => {
              const item = catalog.find((i) => i.series_id === e.target.value);
              if (item) {
                setSelectedTarget(item.target);
                setSelectedSeriesId(item.series_id);
              }
            }}
            style={{
              width: "100%",
              background: "var(--surface-2)",
              color: "var(--text)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)",
              padding: "6px 10px",
              fontSize: "0.8125rem",
              fontFamily: "'ui-monospace', monospace",
              outline: "none",
            }}
          >
            {Array.from(groupedTargets.entries()).map(([targetGroup, items]) => (
              <optgroup key={targetGroup} label={`TARGET: ${targetGroup.toUpperCase()}`}>
                {items.map((i) => (
                  <option key={i.series_id} value={i.series_id}>
                    {i.name} ({i.unit}) [{i.provenance}]
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>

        {/* Horizon Toggle */}
        <div>
          <label
            style={{
              display: "block",
              fontSize: "0.6875rem",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "var(--muted)",
              marginBottom: "var(--space-1)",
            }}
          >
            Forecast Horizon
          </label>
          <div style={{ display: "flex", gap: "var(--space-2)" }}>
            {[7, 14, 30].map((h) => (
              <button
                key={h}
                onClick={() => setHorizonDays(h)}
                style={{
                  flex: 1,
                  padding: "6px 12px",
                  fontSize: "0.8125rem",
                  fontFamily: "'ui-monospace', monospace",
                  fontWeight: 600,
                  borderRadius: "var(--radius-sm)",
                  border: horizonDays === h ? "1px solid var(--info)" : "1px solid var(--border)",
                  background: horizonDays === h ? "rgba(56, 189, 248, 0.15)" : "var(--surface-2)",
                  color: horizonDays === h ? "var(--info)" : "var(--muted)",
                  cursor: "pointer",
                }}
              >
                {h}D
              </button>
            ))}
          </div>
        </div>

        {/* Retrain Action */}
        <div>
          <label
            style={{
              display: "block",
              fontSize: "0.6875rem",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "var(--muted)",
              marginBottom: "var(--space-1)",
            }}
          >
            Walk-Forward Evaluation
          </label>
          <button
            onClick={handleRetrain}
            disabled={retraining || loading}
            style={{
              width: "100%",
              padding: "6px 12px",
              fontSize: "0.8125rem",
              fontFamily: "'ui-monospace', monospace",
              fontWeight: 600,
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border)",
              background: retraining ? "var(--surface-3)" : "var(--surface-2)",
              color: "var(--text)",
              cursor: retraining ? "wait" : "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "var(--space-2)",
            }}
          >
            {retraining ? "EVALUATING WALK-FORWARD..." : "RETRAIN & EVALUATE"}
          </button>
        </div>
      </div>

      {/* Error display */}
      {error && (
        <div
          style={{
            background: "rgba(239, 68, 68, 0.1)",
            border: "1px solid var(--negative)",
            color: "var(--negative)",
            padding: "var(--space-3)",
            borderRadius: "var(--radius-md)",
            fontSize: "0.8125rem",
          }}
        >
          ● ERROR: {error}
        </div>
      )}

      {/* Main Chart Section */}
      <div
        style={{
          background: "var(--surface-1)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-md)",
          padding: "var(--space-4)",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-3)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div style={{ fontSize: "0.875rem", fontWeight: 700, color: "var(--text)" }}>
              {currentSeriesInfo?.name} — {horizonDays}-Day Trajectory
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--muted)", fontFamily: "'ui-monospace', monospace" }}>
              Target: {currentSeriesInfo?.target.toUpperCase()} | Frequency: {currentSeriesInfo?.frequency} | Unit: {currentSeriesInfo?.unit}
            </div>
          </div>
          {/* Legend */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-3)",
              fontSize: "0.75rem",
              fontFamily: "'ui-monospace', monospace",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ width: "12px", height: "2px", background: "var(--text)" }} />
              <span style={{ color: "var(--muted)" }}>Historical</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ width: "12px", height: "2px", background: "var(--info)", borderTop: "2px dashed var(--info)" }} />
              <span style={{ color: "var(--info)" }}>Point Forecast</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ width: "10px", height: "10px", background: "rgba(56, 189, 248, 0.35)", borderRadius: "2px" }} />
              <span style={{ color: "var(--muted)" }}>80% Interval</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ width: "10px", height: "10px", background: "rgba(56, 189, 248, 0.15)", borderRadius: "2px" }} />
              <span style={{ color: "var(--muted)" }}>95% Interval</span>
            </div>
          </div>
        </div>

        {/* Visual SVG Chart */}
        {loading ? (
          <div style={{ height: "300px", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--muted)" }}>
            Loading forecast & uncertainty intervals...
          </div>
        ) : chartMetrics ? (
          <div style={{ overflowX: "auto" }}>
            <svg
              viewBox={`0 0 ${chartMetrics.width} ${chartMetrics.height}`}
              style={{ width: "100%", height: "auto", display: "block" }}
            >
              {/* Grid Lines */}
              {chartMetrics.yTicks.map((t, idx) => (
                <g key={idx}>
                  <line
                    x1={chartMetrics.padding.left}
                    y1={t.y}
                    x2={chartMetrics.width - chartMetrics.padding.right}
                    y2={t.y}
                    stroke="var(--border)"
                    strokeDasharray="3 3"
                  />
                  <text
                    x={chartMetrics.padding.left - 8}
                    y={t.y + 4}
                    fill="var(--muted)"
                    fontSize="10"
                    fontFamily="'ui-monospace', monospace"
                    textAnchor="end"
                  >
                    {t.val.toFixed(1)}
                  </text>
                </g>
              ))}

              {/* Historical / Forecast Separation Line */}
              <line
                x1={chartMetrics.splitX}
                y1={chartMetrics.padding.top}
                x2={chartMetrics.splitX}
                y2={chartMetrics.height - chartMetrics.padding.bottom}
                stroke="var(--warning)"
                strokeDasharray="4 4"
                strokeWidth="1.5"
              />
              <text
                x={chartMetrics.splitX}
                y={chartMetrics.padding.top - 6}
                fill="var(--warning)"
                fontSize="9"
                fontFamily="'ui-monospace', monospace"
                textAnchor="middle"
                fontWeight="600"
              >
                FORECAST ORIGIN ({forecastData?.forecast_origin_date})
              </text>

              {/* 95% Confidence Band Ribbon */}
              <path d={chartMetrics.band95Path} fill="rgba(56, 189, 248, 0.12)" />

              {/* 80% Confidence Band Ribbon */}
              <path d={chartMetrics.band80Path} fill="rgba(56, 189, 248, 0.22)" />

              {/* Historical Actuals Line */}
              <path
                d={chartMetrics.histPath}
                fill="none"
                stroke="var(--text)"
                strokeWidth="1.8"
              />

              {/* Forecast Line */}
              <path
                d={chartMetrics.fcastPath}
                fill="none"
                stroke="var(--info)"
                strokeWidth="2"
                strokeDasharray="4 2"
              />

              {/* Forecast Points Dots */}
              {chartMetrics.fcastCoords.map((c, idx) => (
                <circle
                  key={idx}
                  cx={c.x}
                  cy={c.y}
                  r="2.5"
                  fill="var(--info)"
                />
              ))}

              {/* X Axis bottom dates */}
              <text
                x={chartMetrics.padding.left}
                y={chartMetrics.height - 12}
                fill="var(--muted)"
                fontSize="10"
                fontFamily="'ui-monospace', monospace"
              >
                {chartMetrics.histCoords[0]?.date}
              </text>
              <text
                x={chartMetrics.splitX}
                y={chartMetrics.height - 12}
                fill="var(--warning)"
                fontSize="10"
                fontFamily="'ui-monospace', monospace"
                textAnchor="middle"
              >
                {forecastData?.forecast_origin_date}
              </text>
              <text
                x={chartMetrics.width - chartMetrics.padding.right}
                y={chartMetrics.height - 12}
                fill="var(--info)"
                fontSize="10"
                fontFamily="'ui-monospace', monospace"
                textAnchor="end"
              >
                {chartMetrics.fcastCoords[chartMetrics.fcastCoords.length - 1]?.date}
              </text>
            </svg>
          </div>
        ) : null}
      </div>

      {/* Model Selection Evidence & Scoreboard */}
      {forecastData && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            gap: "var(--space-3)",
          }}
        >
          {/* Selected Model Card */}
          <div
            style={{
              background: "var(--surface-1)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              padding: "var(--space-3)",
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-2)",
            }}
          >
            <div style={{ fontSize: "0.6875rem", textTransform: "uppercase", color: "var(--muted)", fontWeight: 600 }}>
              Active Model Selected by Walk-Forward Evidence
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
              <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--positive)" }}>
                {forecastData.model_info.selected_model}
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--muted)", fontFamily: "'ui-monospace', monospace" }}>
                Ver: {forecastData.model_info.model_version}
              </div>
            </div>

            <div style={{ fontSize: "0.75rem", color: "var(--muted)", borderTop: "1px solid var(--border)", paddingTop: "var(--space-2)" }}>
              <div>Validation Method: <span style={{ color: "var(--text)" }}>{forecastData.model_info.validation_method}</span></div>
              <div>Evaluation Points: <span style={{ color: "var(--text)" }}>{forecastData.validation_metrics.total_eval_points}</span></div>
              <div style={{ wordBreak: "break-all" }}>
                Artifact Hash: <span style={{ color: "var(--info)", fontSize: "0.6875rem" }}>{forecastData.model_info.artifact_hash || "N/A"}</span>
              </div>
            </div>
          </div>

          {/* Validation Metrics Scoreboard */}
          <div
            style={{
              background: "var(--surface-1)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              padding: "var(--space-3)",
            }}
          >
            <div style={{ fontSize: "0.6875rem", textTransform: "uppercase", color: "var(--muted)", fontWeight: 600, marginBottom: "var(--space-2)" }}>
              Out-of-Sample Validation Performance
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-2)" }}>
              <div style={{ background: "var(--surface-2)", padding: "var(--space-2)", borderRadius: "var(--radius-sm)" }}>
                <div style={{ fontSize: "0.6875rem", color: "var(--muted)" }}>RMSE</div>
                <div style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text)", fontFamily: "'ui-monospace', monospace" }}>
                  {forecastData.validation_metrics.rmse.toFixed(3)}
                </div>
              </div>
              <div style={{ background: "var(--surface-2)", padding: "var(--space-2)", borderRadius: "var(--radius-sm)" }}>
                <div style={{ fontSize: "0.6875rem", color: "var(--muted)" }}>MAE</div>
                <div style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text)", fontFamily: "'ui-monospace', monospace" }}>
                  {forecastData.validation_metrics.mae.toFixed(3)}
                </div>
              </div>
              <div style={{ background: "var(--surface-2)", padding: "var(--space-2)", borderRadius: "var(--radius-sm)" }}>
                <div style={{ fontSize: "0.6875rem", color: "var(--muted)" }}>sMAPE</div>
                <div style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text)", fontFamily: "'ui-monospace', monospace" }}>
                  {forecastData.validation_metrics.smape.toFixed(2)}%
                </div>
              </div>
              <div style={{ background: "var(--surface-2)", padding: "var(--space-2)", borderRadius: "var(--radius-sm)" }}>
                <div style={{ fontSize: "0.6875rem", color: "var(--muted)" }}>Directional Acc.</div>
                <div style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text)", fontFamily: "'ui-monospace', monospace" }}>
                  {forecastData.validation_metrics.directional_accuracy.toFixed(1)}%
                </div>
              </div>
            </div>
          </div>

          {/* Candidate Comparison Table */}
          <div
            style={{
              background: "var(--surface-1)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              padding: "var(--space-3)",
            }}
          >
            <div style={{ fontSize: "0.6875rem", textTransform: "uppercase", color: "var(--muted)", fontWeight: 600, marginBottom: "var(--space-2)" }}>
              Candidate Evaluation Breakdown
            </div>
            <table style={{ width: "100%", fontSize: "0.75rem", borderCollapse: "collapse", fontFamily: "'ui-monospace', monospace" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)", color: "var(--muted)", textAlign: "left" }}>
                  <th style={{ padding: "4px 6px" }}>Model</th>
                  <th style={{ padding: "4px 6px" }}>RMSE</th>
                  <th style={{ padding: "4px 6px" }}>MAE</th>
                  <th style={{ padding: "4px 6px" }}>sMAPE</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(forecastData.candidate_metrics).map(([name, m]) => {
                  const isSelected = name === forecastData.model_info.selected_model;
                  return (
                    <tr
                      key={name}
                      style={{
                        background: isSelected ? "rgba(56, 189, 248, 0.08)" : "transparent",
                        fontWeight: isSelected ? 600 : 400,
                        color: isSelected ? "var(--info)" : "var(--text)",
                      }}
                    >
                      <td style={{ padding: "4px 6px" }}>
                        {name} {isSelected && "★"}
                      </td>
                      <td style={{ padding: "4px 6px" }}>{m.rmse.toFixed(3)}</td>
                      <td style={{ padding: "4px 6px" }}>{m.mae.toFixed(3)}</td>
                      <td style={{ padding: "4px 6px" }}>{m.smape.toFixed(1)}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Forecast Output Table Preview (First 7 days) */}
      {forecastData && (
        <div
          style={{
            background: "var(--surface-1)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            padding: "var(--space-3)",
          }}
        >
          <div style={{ fontSize: "0.6875rem", textTransform: "uppercase", color: "var(--muted)", fontWeight: 600, marginBottom: "var(--space-2)" }}>
            Forecast Observation Table ({forecastData.forecast_points.length} Periods)
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", fontSize: "0.75rem", borderCollapse: "collapse", fontFamily: "'ui-monospace', monospace" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)", color: "var(--muted)", textAlign: "left" }}>
                  <th style={{ padding: "6px 8px" }}>Date</th>
                  <th style={{ padding: "6px 8px" }}>Point Forecast</th>
                  <th style={{ padding: "6px 8px" }}>80% Lower</th>
                  <th style={{ padding: "6px 8px" }}>80% Upper</th>
                  <th style={{ padding: "6px 8px" }}>95% Lower</th>
                  <th style={{ padding: "6px 8px" }}>95% Upper</th>
                  <th style={{ padding: "6px 8px" }}>Unit</th>
                </tr>
              </thead>
              <tbody>
                {forecastData.forecast_points.slice(0, 10).map((pt) => (
                  <tr key={pt.date} style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                    <td style={{ padding: "5px 8px", color: "var(--text)" }}>{pt.date}</td>
                    <td style={{ padding: "5px 8px", color: "var(--info)", fontWeight: 600 }}>{pt.value.toFixed(2)}</td>
                    <td style={{ padding: "5px 8px", color: "var(--muted)" }}>{pt.lower_80.toFixed(2)}</td>
                    <td style={{ padding: "5px 8px", color: "var(--muted)" }}>{pt.upper_80.toFixed(2)}</td>
                    <td style={{ padding: "5px 8px", color: "var(--muted)" }}>{pt.lower_95.toFixed(2)}</td>
                    <td style={{ padding: "5px 8px", color: "var(--muted)" }}>{pt.upper_95.toFixed(2)}</td>
                    <td style={{ padding: "5px 8px", color: "var(--muted)" }}>{forecastData.unit}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {forecastData.forecast_points.length > 10 && (
            <div style={{ fontSize: "0.6875rem", color: "var(--muted)", marginTop: "var(--space-2)", textAlign: "right" }}>
              Showing first 10 of {forecastData.forecast_points.length} periods.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
