# VesselOptima — Phase 13 Implementation: Historical Backtesting & Decision Replay Engine

## File-by-File Implementation Guide & Architecture Breakdown

---

## 1. Subsystem Architecture Overview

Phase 13 integrates seamlessly with existing database models, solvers, and API endpoints:

```text
backend/
├── alembic/versions/13b4c5d6e7f8_add_backtesting_tables.py   # Database migration (11 tables)
├── app/
│   ├── api/v1/backtest.py                                    # REST router (/v1/backtest)
│   ├── engines/backtest/                                     # Core replay subsystem
│   │   ├── __init__.py                                       # Package re-exports
│   │   ├── reason_codes.py                                   # Enums & rejection codes
│   │   ├── events.py                                         # Chronological event stream
│   │   ├── snapshot.py                                       # Point-in-time state reconstruction
│   │   ├── leakage.py                                        # Look-ahead & leakage detector
│   │   ├── timeline.py                                       # Decision step generator
│   │   ├── benchmarks.py                                     # 5 industry benchmark policies
│   │   ├── outcome.py                                        # Realized voyage economics
│   │   ├── metrics.py                                        # Portfolio metrics & performance curves
│   │   ├── attribution.py                                    # Multidimensional attribution
│   │   ├── orchestrator.py                                   # Replay runner invoking Phase 7 HiGHS MILP
│   │   └── service.py                                        # Persistence, determinism & demo seed
│   ├── models/domain.py                                      # 11 SQLAlchemy ORM models
│   └── schemas/backtest.py                                   # Pydantic V2 schemas
└── tests/test_backtesting.py                                 # 44 unit & integration tests

frontend/
├── src/
│   ├── app/backtest/page.tsx                                 # Institutional backtesting console
│   ├── lib/api.ts                                            # Phase 13 API client methods
│   └── types/api.ts                                          # TypeScript interfaces & types
```

---

## 2. Database Models (`backend/app/models/domain.py`)

Alembic revision `13b4c5d6e7f8` introduced 11 institutional backtesting tables:
1. **`backtest_configurations`**: Immutable parameters, start/end timestamps, frequency, policy, seed, and SHA-256 config hash.
2. **`backtest_runs`**: Execution status, timestamps, backtest SHA-256 hash, execution time, and summary metrics.
3. **`backtest_snapshots`**: Serialized point-in-time state $\mathcal{S}_T$ at timestamp $T$ with cryptographic snapshot hash.
4. **`backtest_decisions`**: Replayed decision records containing vessel-cargo assignment dictionaries, recommendations, and foreign keys to Phase 7/8/9/10 runs.
5. **`backtest_outcomes`**: Realized revenue, bunker, port, ballast, and idle costs, delay days, and forecast error.
6. **`backtest_benchmarks`**: Benchmark configurations for comparison.
7. **`backtest_benchmark_results`**: Realized performance of each benchmark strategy at each decision step.
8. **`backtest_metrics`**: Categorized summary metrics (ECONOMIC, RELATIVE, DECISION, RISK, OPERATIONAL).
9. **`backtest_attributions`**: Performance decomposition by VESSEL, CARGO, DECISION_TYPE, and ASSOCIATED_DRIVER.
10. **`backtest_leakages`**: Audit trail of any detected look-ahead bias or future timestamp anomalies.
11. **`backtest_timelines`**: Chronological decision step milestones.

---

## 3. Core Engine Implementation Details

### 3.1 Point-in-Time Reconstruction (`engines/backtest/snapshot.py`)
Reconstructs the exact state available at timestamp $T$ by taking initial baseline entities and folding in only those events whose `availability_timestamp <= decision_timestamp`. Future cargo listings, revised vessel speeds, and forward bunker quotes are strictly invisible.

### 3.2 Look-Ahead Bias Detector (`engines/backtest/leakage.py`)
Scans every object in the snapshot and rejects any item where `information_timestamp > decision_timestamp`, recording an entry in `backtest_leakages` with severity `CRITICAL`.

### 3.3 HiGHS MILP Replay Orchestrator (`engines/backtest/orchestrator.py`)
Crucially, **no second optimizer was created**. The orchestrator constructs a Phase 7 `OptimizationRequest`, feeds it to `solve_fleet_assignment(...)` using HiGHS MILP, and records the resulting mathematical assignments and dual values.

### 3.4 Five Benchmark Engines (`engines/backtest/benchmarks.py`)
Evaluates the exact same historical snapshot across:
- `NO_ACTION`: Calculates idle port/at-anchor holding costs.
- `CONTINUE_CURRENT_EMPLOYMENT`: Continues current voyages.
- `FIRST_FEASIBLE`: Assigns first feasible cargo in index order.
- `BEST_EXPECTED_CONTRIBUTION`: Solves greedily per vessel for max expected single-voyage contribution.
- `HISTORICAL_ACTUAL`: Ingests actual chartering desk fixture records.

### 3.5 Realized Outcome Engine (`engines/backtest/outcome.py`)
Computes realized freight revenue and voyage costs, evaluating economic forecast error and schedule delay.

---

## 4. Frontend UI Console (`frontend/src/app/backtest/page.tsx`)

A dark-terminal console built with pure Vanilla CSS tokens and SVG charting:
- **Header Action Bar**: Displays runtime badges, zero outbound sockets guarantee, HiGHS MILP optimizer status, and one-click replay execution.
- **Run Registry Sidebar**: Lists historical backtest runs with status pills and leakage flags.
- **Interactive SVG Contribution Curve**: Renders cumulative realized contribution over time comparing VesselOptima against baseline benchmark and cumulative alpha.
- **5-Strategy Benchmark Scorecard**: High-density comparative table demonstrating VesselOptima's alpha against all 5 benchmarks with mathematical non-dominance proof.
- **Decision Replay Timeline**: Step-by-step visual sequence of point-in-time decisions.
- **Multidimensional Attribution Matrix**: Interactive filtering by Vessel, Cargo, Recommendation, and Market Driver.
- **Look-Ahead & Integrity Audit Panel**: 4 prominent green verification check badges and incident audit ledger.
- **Setup New Backtest Console**: Configurable form to define ISO date ranges, frequencies, and benchmark suites.
