# VesselOptima — Phase 8: Scenario Analysis & Sensitivity Implementation

## 1. Implementation Architecture

Phase 8 provides an institutional decision-support and stress-testing layer that safely perturbs assumptions and evaluates fleet allocation sensitivity without mutating underlying records.

```text
backend/app/engines/scenarios/
├── config.py           # ScenarioConfig dataclass, ScenarioPresets, SHA-256 config fingerprinting
├── transform.py        # Copy-on-scenario transformer with SHA-256 candidate immutability assertions
├── revalidation.py     # Upstream temporal (laycan) and operational (fleet outage/delay) revalidator
├── comparison.py       # AssignmentDifferenceEngine: UNCHANGED, ADDED, DROPPED, REPLACED classification
├── sensitivity.py      # SensitivityEngine: OVAT parameter sweeps and break-even switching threshold detector
├── robustness.py       # RobustnessEngine: Ensemble survival scoring across macro shock scenarios
├── service.py          # ScenarioService: Master orchestrator delegating re-solves to Phase 7 HiGHS MILP
└── __init__.py         # Package exports
```

---

## 2. Verification Summary

### 2.1 Backend Test Suite (`test_scenario_engine.py`)
* **Test Count**: 20 / 20 PASS (100%)
* **Execution Time**: 1.11s
* **Key Tests**:
  * `test_baseline_reproduction`: Multipliers = 1.0 reproduce baseline allocation identically (0 delta, 100% stability).
  * `test_freight_increase`: +20% freight increases revenues and global objective.
  * `test_freight_decrease`: -20% freight reduces revenue and trims marginal voyages.
  * `test_bunker_increase`: +50% bunker increases fuel costs and penalizes long ballast.
  * `test_idle_cost_increase`: +50% idle rate increases avoided idle valuation.
  * `test_multi_parameter_stress`: Compound Freight -20%, Bunker +30%, Idle +20%.
  * `test_tight_laycan_revalidation`: Tightening laycan window by 4 days disqualifies late-arriving vessels.
  * `test_vessel_unavailability`: Excluding vessel 1 disqualifies its candidates and re-allocates remaining fleet.
  * `test_baseline_immutability`: Asserts `hash(before) == hash(after)` to the exact byte.
  * `test_determinism`: Executing same scenario twice yields identical results and hashes.
  * `test_assignment_delta_classification`: Validates UNCHANGED, ADDED, DROPPED, REPLACED.
  * `test_critical_strategy_flip`: Mathematically proves the assignment flip from A->1, B->2 to A->2, B->1 under high bunker.
  * `test_sensitivity_sweep`: Sweeps bunker across 5 points and returns monotonic objective curve.
  * `test_break_even_detection`: Detects switching threshold at observed range.
  * `test_robustness_scoring`: Evaluates 3-scenario ensemble and produces CORE_ROBUST scores.
  * `test_batch_execution`: Runs batch of 4 scenarios in isolation.
  * `test_scenario_audit_and_persistence`: Tests DB storage of ScenarioEvaluation and ScenarioSensitivityRun.
  * `test_phase7_milp_solver_integration`: Proves Phase 7 HiGHS MILP is used without greedy fallback.
  * `test_air_gap_isolation`: Traps socket calls and verifies 100% offline network isolation.
  * `test_api_endpoints`: Tests `/v1/scenarios/presets`, `/run`, `/batch`, `/sensitivity`, `/robustness`.

### 2.2 Full Regression Suite
* **Phases 1–8 Combined**: 141 / 141 PASS (100% pass rate in 23.79s). Zero regressions.

### 2.3 Database & Migrations
* **Alembic Revision**: `8c9d0e1f2a3b` (`add_scenario_tables`).
* **Tables Added**:
  * `scenario_evaluations`: Stores scenario run references, comparison metrics, assignment deltas, and audit hashes.
  * `scenario_sensitivity_runs`: Stores parameter sweeps, sweep points, and break-even thresholds.

### 2.4 Frontend Production Build
* **Tool**: Next.js 16.3.4 (Turbopack).
* **Status**: Compiled successfully in 1.89s, 0 TypeScript errors.
* **Route Added**: `○ /scenarios` (Static prerendered).
