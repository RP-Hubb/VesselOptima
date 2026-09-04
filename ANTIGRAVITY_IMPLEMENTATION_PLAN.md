# ANTIGRAVITY IMPLEMENTATION PLAN

## Phase 1 - Foundation
*   **EXISTING:** None
*   **REQUIRED:** Repository structure, configuration, environment handling, database schemas, common API structure, logging, error handling, runtime mode handling.
*   **GAP:** Everything is missing.
*   **IMPLEMENTATION:**
    *   Initialize backend with FastAPI and SQLAlchemy.
    *   Set up PostgreSQL database schema based on Section S of the Build Specification.
    *   Implement `/v1/runtime/mode` and `/v1/runtime/status` endpoints to handle LIVE vs OFFLINE DEMO.
    *   Setup Next.js frontend with TailwindCSS, configuring the professional institutional UI aesthetic (dark theme, data density).
*   **TEST:** Verify database migrations run, FastAPI starts, and frontend renders basic shell. Verify runtime mode toggle logic works (API rejects invalid modes).

## Phase 2 - Offline Data Package
*   **EXISTING:** None
*   **REQUIRED:** Normalized offline datasets, provenance metadata, dataset versioning, deterministic loading, offline validation.
*   **GAP:** Everything is missing.
*   **IMPLEMENTATION:**
    *   Create mock/demo datasets for vessel classes, ports (with constraints), macro data, historical market benchmarks, and cargo parcels.
    *   Implement offline package loader that validates schema/hashes on startup and loads into PostgreSQL.
    *   Ensure NO network calls are made during this process.
*   **TEST:** Start backend with `OFFLINE DEMO` mode, internet OFF, and verify data is correctly seeded and accessible via endpoints.

## Phase 3 - Forecasting
*   **EXISTING:** None
*   **REQUIRED:** Feature engineering, candidate models (baselines, statistical, ML), walk-forward validation, uncertainty (prediction intervals), SHAP explainability, forecast API.
*   **GAP:** Everything is missing.
*   **IMPLEMENTATION:**
    *   Implement time-series forecasting logic in Python (e.g. using `statsmodels` for ARIMA/ETS, or `xgboost` for ML).
    *   Implement conformal prediction for 80% and 95% intervals.
    *   Expose `/v1/forecasts` endpoint.
    *   Save and load model artifacts locally for `OFFLINE DEMO`.
*   **TEST:** Verify forecast API returns predictions with intervals without data leakage and explains drivers.

## Phase 4 - Feasibility
*   **EXISTING:** None
*   **REQUIRED:** Vessel constraints, port constraints, voyage constraints, availability, deadline checks, interpretable infeasibility reasons.
*   **GAP:** Everything is missing.
*   **IMPLEMENTATION:**
    *   Implement `FeasibilityEngine` to validate vessel profiles against port rules (draft, LOA, beam).
    *   Generate specific reason codes (e.g., `DRAFT_EXCEEDS_MAX`).
    *   Expose `/v1/feasibility/evaluate` endpoint.
*   **TEST:** Test with valid and invalid vessel/port combinations to ensure correct reason codes are returned.

## Phase 5 - Procurement
*   **EXISTING:** None
*   **REQUIRED:** Cargo requirements, procurement windows, configurable lead time, spot/short/medium/multi-voyage strategies.
*   **GAP:** Everything is missing.
*   **IMPLEMENTATION:**
    *   Implement procurement timing model to calculate `t_init`.
    *   Evaluate contract strategies (SPOT, SHORT-TERM, MEDIUM-TERM).
*   **TEST:** Test procurement initiation date calculations against various cargo deadlines.

## Phase 6 - Idle & Alternative Employment
*   **EXISTING:** None
*   **REQUIRED:** Idle-window detection, idle cost/risk, alternative employment candidates, feasibility, repositioning, deadheading, economic comparison.
*   **GAP:** Everything is missing.
*   **IMPLEMENTATION:**
    *   Detect availability-to-next-commitment windows.
    *   Generate `WAIT`, `REPOSITION`, and `ALTERNATIVE_EMPLOYMENT` candidates.
    *   Evaluate each candidate's economic value using existing cost/feasibility services.
    *   Expose `/v1/idle/*` endpoints.
*   **TEST:** Provide mock vessel availability data and verify engine produces valid actionable options with reasoned feasibility constraints.

## Phase 7 - MILP Optimizer
*   **EXISTING:** None
*   **REQUIRED:** Optimization objective (Cost + Risk), decision variables, constraints, strategy comparison, optimization results.
*   **GAP:** Everything is missing.
*   **IMPLEMENTATION:**
    *   Implement MILP formulation using `PuLP` or `SciPy`.
    *   Integrate output from Idle & Employment engine as decision variables.
    *   Expose `/v1/optimizations` endpoint.
*   **TEST:** Run optimization scenarios and verify cost minimization, constraint satisfaction, and infeasibility handling.

## Phase 8 - Risk + Scenarios
*   **EXISTING:** None
*   **REQUIRED:** Risk engine, scenario engine, sensitivity/stress testing, recommendation comparison.
*   **GAP:** Everything is missing.
*   **IMPLEMENTATION:**
    *   Implement named stress tests (e.g., `FUEL_+20`, `FREIGHT_+15`).
    *   Calculate CVaR and exposure for decisions under stress.
*   **TEST:** Apply shocks to inputs and verify optimizer recommendation changes are logged.

## Phase 9 - Backtest
*   **EXISTING:** None
*   **REQUIRED:** Historical point-in-time simulation, baseline strategies, metrics, visualization.
*   **GAP:** Everything is missing.
*   **IMPLEMENTATION:**
    *   Implement chronological simulation loops over historical offline data.
    *   Compare `Spot` vs `Forecast-Only` vs `VesselOptima` strategies.
*   **TEST:** Run backtest and ensure no future information leaks into past decisions.

## Phase 10 - FastAPI Integration
*   **EXISTING:** None
*   **REQUIRED:** Connect all backend services through clean API contracts.
*   **GAP:** Everything is missing.
*   **IMPLEMENTATION:**
    *   Ensure all endpoints are documented via OpenAPI.
    *   Implement comprehensive error handling and runtime metadata responses.
*   **TEST:** E2E API tests for all critical workflows.

## Phase 11 - Frontend Terminal
*   **EXISTING:** None
*   **REQUIRED:** Professional institutional UI (anti-AI-slop), data density, decision workflow.
*   **GAP:** Everything is missing.
*   **IMPLEMENTATION:**
    *   Build Next.js pages for Market, Forecast, Optimizer, Idle & Employment, Scenarios, Ports, Backtest, Risk, Data, Audit.
    *   Implement compact navigation, data tables (TanStack Table), and charts (ECharts).
*   **TEST:** UI testing for data rendering, empty states, loading states, and runtime mode display.

## Phase 12 - Audit + E2E
*   **EXISTING:** None
*   **REQUIRED:** Audit trail, recommendation explanation, reproducibility.
*   **GAP:** Everything is missing.
*   **IMPLEMENTATION:**
    *   Log all inputs, forecasts, constraints, optimizations to `audit_events`.
    *   Present full decision chain in UI.
*   **TEST:** Verify audit logs perfectly match system actions and UI explanations.

## Phase 13 - SIH Demo Hardening
*   **EXISTING:** None
*   **REQUIRED:** Robustness against failure, offline isolation, polished demo workflow.
*   **GAP:** Everything is missing.
*   **IMPLEMENTATION:**
    *   Polish all error/loading/empty states.
    *   Ensure OFFLINE DEMO mode completely isolates from external networks.
*   **TEST:** Final "Internet OFF" demonstration walkthrough.
