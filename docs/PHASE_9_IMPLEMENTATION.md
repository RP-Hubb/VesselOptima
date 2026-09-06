# VesselOptima — Phase 9 Implementation Report: Risk Intelligence & Uncertainty Engine

## Technical Implementation, Verification & Visual Demonstration

---

## 1. System Implementation Overview

Phase 9 introduces the **Risk Intelligence & Uncertainty Engine** to VesselOptima, enabling institutional-grade continuous stochastic simulation of voyage operations and portfolio economics.

### 1.1 Key Technical Highlights
- **Vectorized Monte Carlo Performance**: 10,000 iterations executed in **$< 500$ ms** using vectorized NumPy multi-dimensional array operations.
- **Joint Gaussian Copula Sampling**: Cholesky decomposition of symmetric positive semi-definite correlation matrices ensures joint dependency between freight rates, bunker volatility, and multi-port congestion.
- **Physical Domain Safeguards**: Strict validation rejecting negative bunker prices, negative delays, and inverted triangular bounds with dedicated `PhysicalDomainViolation` errors.
- **Downside Tail Metrics**: Calculates VaR90, VaR95, CVaR90, CVaR95 (Expected Shortfall), Loss Probability, Expected Loss, Schedule Buffer Days, Laycan Miss Probability, and Composite Plan Reliability Score.
- **Variance Attribution (ANOVA)**: Econometric component variance attribution decomposing portfolio outcome volatility into driver percentages and sensitivity coefficients ($\beta$).
- **Critical Risk Flip Demonstration**: Built-in comparative evaluation proving when aggressive plans trade excessive downside tail risk for marginal expected returns.
- **100% Offline Air-Gap Compliance**: Validated with zero external socket calls.

---

## 2. File Map & Architecture

```text
backend/
├── alembic/versions/
│   └── 9d0e1f2a3b4c_add_risk_tables.py        # Alembic migration for risk tables
├── app/
│   ├── models/
│   │   ├── domain.py                          # RiskRun, RiskMetric, RiskAssignmentMetric, RiskDriver
│   │   └── __init__.py                        # Exported models
│   ├── schemas/
│   │   └── risk.py                            # Pydantic request/response schemas
│   ├── api/v1/
│   │   └── risk.py                            # FastAPI REST endpoints (/v1/risk/*)
│   ├── engines/risk/
│   │   ├── reason_codes.py                    # RiskReasonCode, RiskTier, ProvenanceType, RiskCategory
│   │   ├── models.py                          # DistributionType, RiskVariable, CorrelationConfig, RiskSimulationConfig
│   │   ├── distributions.py                   # DistributionValidator, DistributionSampler (ppf & sampling)
│   │   ├── correlation.py                     # CorrelationEngine (Cholesky & Copula sampling)
│   │   ├── sampling.py                        # RiskSampler (joint sampling coordinator)
│   │   ├── metrics.py                         # RiskMetricsCalculator (VaR, CVaR, reliability, ANOVA)
│   │   ├── result.py                          # PlanRiskSimulationResult, AssignmentRiskResult, etc.
│   │   ├── simulation.py                      # MonteCarloEngine (vectorized voyage simulation)
│   │   ├── risk_service.py                    # RiskService (orchestrator & persistence)
│   │   └── __init__.py                        # Package init
│   └── main.py                                # Mounted risk router
└── tests/
    └── test_risk_engine.py                    # 23 comprehensive tests

frontend/
├── src/
│   ├── types/api.ts                           # TypeScript risk interfaces
│   ├── lib/api.ts                             # Risk API client methods
│   └── app/risk/
│       └── page.tsx                           # Dark terminal institutional dashboard
```

---

## 3. Database Schema

The database migration `9d0e1f2a3b4c_add_risk_tables.py` introduces four normalized tables:

1. `risk_runs`: Monte Carlo run metadata, simulation count ($N$), random seed, execution time, and audit provenance.
2. `risk_metrics`: Portfolio-level expected contribution, standard deviation, VaR90/95, CVaR90/95, loss probability, plan reliability score, risk tier, and binned distribution histogram.
3. `risk_assignment_metrics`: Per-voyage expected contribution, CVaR95, arrival percentiles ($P_{50}, P_{90}$), schedule buffer days, laycan miss probability, and survival rates.
4. `risk_drivers`: Variance attribution percentage and sensitivity coefficient ($\beta$) for each stochastic risk factor.

---

## 4. Verification & Test Results

### 4.1 Phase 9 Unit & Integration Tests
`pytest tests/test_risk_engine.py -v`: **23 / 23 PASS (1.11s)**
- Distribution validation & domain boundaries: PASS
- Deterministic seed reproducibility: PASS
- Cholesky decomposition & Gaussian copula: PASS
- VaR90, VaR95, CVaR90, CVaR95 tail calculations: PASS
- ANOVA variance decomposition & driver attribution: PASS
- Vectorized Monte Carlo performance ($N = 10,000$ in $< 500$ ms): PASS
- Critical Risk Flip comparative detection: PASS
- Database persistence & retrieval: PASS
- Air-gap isolation (zero socket calls): PASS
- REST API integration: PASS

### 4.2 Full Regression Suite Across All Phases
`pytest tests/ -v`: **164 / 164 PASS (22.11s)**
- Phase 1 (Foundation & Runtime): PASS
- Phase 2 (Offline Data Package & Ingestion): PASS
- Phase 3 (Forecasting & Residuals): PASS
- Phase 4 (Vessel & Port Feasibility): PASS
- Phase 5 (Dynamic Procurement Strategy): PASS
- Phase 6 (Idle Management & Employment): PASS
- Phase 7 (MILP Fleet Optimization): PASS
- Phase 8 (Scenarios & Sensitivity): PASS
- Phase 9 (Risk Intelligence & Uncertainty): PASS

### 4.3 Frontend Production Build
`npm run build`: **PASS (Code 0)**
- Next.js 16.3.4 (Turbopack)
- `○ /risk` statically prerendered with 0 TypeScript or linting errors.

---

## 5. Visual Dashboard Demonstrations

All 5 core dashboard tabs were visually verified using the browser subagent, with session recorded to `risk_engine_demo_1788684290002.webp`:

1. **Portfolio Distribution & VaR Profile (`risk_main_overview.png`)**:
   - Interactive SVG frequency distribution histogram with vertical markers for Expected Mean, VaR95, and CVaR95.
   - Institutional percentiles table ($P_{05}$ to $P_{95}$).
2. **Assignment Fragility & Schedule Risk (`risk_assignment_fragility.png`)**:
   - Voyage schedule fragility matrix detailing arrival distributions, buffer days, and laycan miss probability.
3. **Risk Drivers & Variance Attribution (`risk_drivers_attribution.png`)**:
   - Econometric ANOVA breakdown and sensitivity coefficients ($\beta$).
4. **Critical Risk Flip & Trade-off (`risk_critical_flip_proof.png`)**:
   - Side-by-side comparison of Plan A (Aggressive/Tail Exposed) vs Plan B (Institutional Robust).
5. **Stochastic Parameters & Provenance (`risk_distributions_audit.png`)**:
   - Distribution parameters, physical domain bounds, and data provenance citations.
